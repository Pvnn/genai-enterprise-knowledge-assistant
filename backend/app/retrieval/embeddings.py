"""Embeddings API wrapper for Google Gemini.

Owner: P3  |  Priority: 1
Provider: Google Gemini gemini-embedding-001 API (768 dimensions).

Used by the indexer (Stage 0) and dense retrieval (Stage 3).

Dimension: 768 dimensions.

All settings are sourced from app.config.get_settings(); never os.environ directly.
All I/O is async. Errors surface as EmbeddingError so callers receive a typed exception
rather than a raw Gemini SDK or HTTP exception.

Retry Policy:
- Transient failures (network errors, timeouts, rate limits 429, server errors 5xx) on Gemini
  are retried using binary exponential backoff up to Settings.embedding_max_retries.
- Permanent failures (401 auth, 403 forbidden, 400 invalid argument, 404 model not found)
  are NOT retried and raise immediately.
- If retries exhaust for transient failures, EmbeddingError is raised.
"""

from __future__ import annotations

import asyncio
import logging
import socket
from functools import lru_cache
from typing import Any

import httpx
from google import genai
from google.genai import types

from app.config import get_settings

logger = logging.getLogger(__name__)

# Default embedding dimension for gemini-embedding-001
EMBEDDING_DIMENSION = 768
MAX_RETRIES = 3


# ── Typed exceptions ──────────────────────────────────────────────────────────


class EmbeddingError(Exception):
    """Base exception raised when an embedding operation fails.

    Wraps underlying provider, SDK, or network exceptions so callers receive
    a typed error rather than leaking raw implementation details.
    """


class EmbeddingConfigurationError(EmbeddingError):
    """Raised when embedding configuration is invalid (e.g. missing API key)."""


class TransientEmbeddingError(EmbeddingError):
    """Raised internally when a transient/retryable embedding failure occurs."""


class PermanentEmbeddingError(EmbeddingError):
    """Raised internally when a permanent/non-retryable embedding failure occurs."""


# ── Error Classification ──────────────────────────────────────────────────────


def _is_transient_error(exc: Exception) -> bool:
    """Classify whether an exception represents a transient or permanent error.

    Transient (retryable) errors:
        - Network/connection errors (httpx, socket, asyncio connection resets)
        - Request timeouts
        - HTTP 429 / Rate Limit / Resource Exhausted
        - HTTP 5xx Server Errors (500, 502, 503, 504, etc.)
        - Temporary service unavailability / deadline exceeded

    Permanent (non-retryable) errors:
        - Invalid API key, 401 Unauthorized, 403 Forbidden / Permission Denied
        - 400 Bad Request, Invalid Argument, Malformed request
        - 404 Not Found, Unsupported/Missing Model
        - Invalid model configuration, ValueError, TypeError, configuration errors
    """
    try:
        if isinstance(exc, TransientEmbeddingError):
            return True
        if isinstance(exc, (PermanentEmbeddingError, EmbeddingConfigurationError, ValueError, TypeError)):
            return False

        # Check google.genai.errors if present
        try:
            from google.genai import errors as genai_errors

            if isinstance(exc, genai_errors.ServerError):
                return True
            if isinstance(exc, genai_errors.ClientError):
                code = getattr(exc, "code", None)
                if code in (408, 429):
                    return True
                return False
            if isinstance(exc, genai_errors.APIError):
                code = getattr(exc, "code", None)
                if isinstance(code, int):
                    if code in (408, 429) or 500 <= code <= 599:
                        return True
                    if 400 <= code < 500:
                        return False
        except Exception:
            pass

        # Check standard library and HTTP transport network/timeout exceptions
        if isinstance(
            exc,
            (
                TimeoutError,
                asyncio.TimeoutError,
                ConnectionError,
                ConnectionResetError,
                ConnectionRefusedError,
                ConnectionAbortedError,
                socket.timeout,
                socket.gaierror,
                socket.error,
                httpx.TimeoutException,
                httpx.NetworkError,
                httpx.ConnectError,
                httpx.ConnectTimeout,
                httpx.ReadTimeout,
                httpx.WriteTimeout,
                httpx.RemoteProtocolError,
            ),
        ):
            return True

        # Check numeric HTTP status code attributes if present on custom or mock exceptions
        code = getattr(exc, "status_code", getattr(exc, "code", getattr(exc, "http_status", None)))
        if isinstance(code, int):
            if code in (408, 429) or 500 <= code <= 599:
                return True
            if 400 <= code < 500:
                return False

        # Check status string if present (e.g. gRPC or GenAI error status)
        status = getattr(exc, "status", None)
        if isinstance(status, str):
            status_upper = status.upper()
            if status_upper in (
                "RESOURCE_EXHAUSTED",
                "UNAVAILABLE",
                "DEADLINE_EXCEEDED",
                "INTERNAL",
                "ABORTED",
            ):
                return True
            if status_upper in (
                "INVALID_ARGUMENT",
                "NOT_FOUND",
                "PERMISSION_DENIED",
                "UNAUTHENTICATED",
                "FAILED_PRECONDITION",
                "ALREADY_EXISTS",
            ):
                return False

        # String inspection heuristics for mock or unclassified exceptions
        msg = str(exc).lower().replace("_", " ")

        # Match permanent indicators first
        permanent_keywords = (
            "401",
            "403",
            "400",
            "404",
            "422",
            "unauthorized",
            "unauthenticated",
            "invalid api key",
            "api key not valid",
            "permission denied",
            "forbidden",
            "invalid argument",
            "bad request",
            "not found",
            "unsupported model",
        )
        if any(kw in msg for kw in permanent_keywords) and not any(
            trans in msg for trans in ("429", "500", "502", "503", "504")
        ):
            return False

        # Match transient indicators
        transient_keywords = (
            "429",
            "500",
            "502",
            "503",
            "504",
            "508",
            "rate limit",
            "too many requests",
            "resource exhausted",
            "service unavailable",
            "temporarily unavailable",
            "deadline exceeded",
            "timeout",
            "timed out",
            "connection reset",
            "connection refused",
            "connection error",
            "network error",
            "server error",
            "unavailable",
        )
        if any(kw in msg for kw in transient_keywords):
            return True

        return False
    except Exception:
        return False


# ── Gemini Client (lazily initialised; cached per process) ───────────────────


@lru_cache(maxsize=1)
def _get_client() -> genai.Client:
    """Return a cached Gemini client initialised from settings.

    Returns:
        genai.Client: Shared client for the process lifetime.

    Raises:
        EmbeddingConfigurationError: If GEMINI_API_KEY is not configured.
    """
    settings = get_settings()
    api_key = getattr(settings, "gemini_api_key", None)
    if not api_key:
        raise EmbeddingConfigurationError("GEMINI_API_KEY is not configured")
    return genai.Client(api_key=api_key)


def _call_gemini_sync(
    client: genai.Client, model: str, texts: list[str], dimension: int
) -> list[list[float]]:
    """Synchronously call Gemini embed_content API and validate dimension."""
    response = client.models.embed_content(
        model=model,
        contents=texts,  # type: ignore[arg-type]
        config=types.EmbedContentConfig(
            output_dimensionality=dimension,
        ),
    )
    if not response.embeddings:
        raise EmbeddingError(
            f"Gemini model '{model}' returned empty or null embeddings response"
        )

    embeddings: list[list[float]] = []
    for e in response.embeddings:
        if e.values is None:
            raise EmbeddingError(
                f"Gemini model '{model}' returned an embedding with null values"
            )
        embeddings.append([float(v) for v in e.values])

    for i, vec in enumerate(embeddings):
        if len(vec) != dimension:
            raise EmbeddingError(
                f"Gemini model '{model}' returned dimension {len(vec)} for embedding[{i}], expected {dimension}"
            )

    # Validate count: one vector per input text. A mismatch here would cause
    # silent data loss in indexer.py where zip() truncates without error.
    if len(embeddings) != len(texts):
        raise EmbeddingError(
            f"Gemini model '{model}' returned {len(embeddings)} embedding(s) "
            f"for {len(texts)} input text(s)"
        )
    return embeddings


async def _embed_gemini_with_retry(
    texts: list[str],
    model: str,
    dimension: int,
    max_retries: int,
) -> list[list[float]]:
    """Embed texts using Gemini with exponential backoff on transient errors only."""
    client = _get_client()

    for attempt in range(max_retries + 1):
        try:
            logger.debug(
                "Requesting Gemini embeddings (attempt %d/%d, model=%s, batch_size=%d, dim=%d)",
                attempt + 1,
                max_retries + 1,
                model,
                len(texts),
                dimension,
            )
            embeddings = await asyncio.to_thread(
                _call_gemini_sync, client, model, texts, dimension
            )
            logger.debug(
                "Received %d embedding(s) from Gemini, dimension=%d",
                len(embeddings),
                len(embeddings[0]) if embeddings else 0,
            )
            return embeddings
        except Exception as exc:
            is_transient = _is_transient_error(exc)
            error_nature = "transient" if is_transient else "permanent"

            if is_transient and attempt < max_retries:
                delay = 2**attempt  # Binary exponential backoff: 1s, 2s, 4s…
                logger.warning(
                    "Gemini embeddings API %s error on attempt %d/%d (model=%s, batch_size=%d): %s. "
                    "Retrying in %ds...",
                    error_nature,
                    attempt + 1,
                    max_retries + 1,
                    model,
                    len(texts),
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)
            elif is_transient:
                logger.error(
                    "Gemini embeddings API transient failure after %d retries (model=%s, batch_size=%d): %s",
                    max_retries,
                    model,
                    len(texts),
                    exc,
                )
                raise TransientEmbeddingError(
                    f"Gemini embeddings call failed for model '{model}' after {max_retries} retries: {exc}"
                ) from exc
            else:
                logger.error(
                    "Gemini embeddings API permanent failure on attempt %d/%d (model=%s, batch_size=%d): %s. "
                    "Not retrying.",
                    attempt + 1,
                    max_retries + 1,
                    model,
                    len(texts),
                    exc,
                )
                raise PermanentEmbeddingError(
                    f"Gemini embeddings call failed permanently for model '{model}': {exc}"
                ) from exc

    # Unreachable fallback to guarantee static type checkers that all paths raise or return.
    raise EmbeddingError(
        f"Gemini embeddings call failed for model '{model}' after {max_retries} attempts"
    )


# ── Public API ────────────────────────────────────────────────────────────────


async def embed_text(text: str) -> list[float]:
    """Embed a single text string using Google Gemini.

    Delegates to embed_batch() so all retry and validation logic lives in one place.

    Args:
        text: The text to embed. Must be non-empty.

    Returns:
        list[float]: The 768-dimensional embedding vector.

    Raises:
        EmbeddingConfigurationError: If the Gemini API key is missing.
        EmbeddingError: If the embedding call fails.
        ValueError: If *text* is empty.
    """
    if not text:
        raise ValueError("embed_text() received an empty string")
    results = await embed_batch([text])
    return results[0]


async def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed a batch of text strings using Google Gemini.

    Uses ``gemini-embedding-001`` (768-dim). Transient failures (rate limits,
    timeouts, 5xx errors) retry up to ``embedding_max_retries`` times with
    binary exponential backoff. Permanent errors (auth, bad request) fail immediately.

    Args:
        texts: List of strings to embed. Must be non-empty; individual strings
               must also be non-empty.

    Returns:
        list[list[float]]: One 768-dimensional embedding vector per input
        string, in the same order as *texts*.

    Raises:
        EmbeddingConfigurationError: If the Gemini API key is missing.
        EmbeddingError: If embedding generation fails.
        ValueError: If *texts* is empty or any element is an empty string.
    """
    if not texts:
        raise ValueError("embed_batch() received an empty list")
    if any(not t for t in texts):
        raise ValueError("embed_batch() received one or more empty strings")

    settings = get_settings()

    gemini_model = getattr(
        settings,
        "gemini_embedding_model",
        getattr(settings, "embedding_model", "gemini-embedding-001"),
    )
    dimension = getattr(
        settings,
        "gemini_embedding_dimension",
        getattr(settings, "embedding_dimension", EMBEDDING_DIMENSION),
    )
    max_retries = getattr(settings, "embedding_max_retries", MAX_RETRIES)

    logger.debug(
        "Requesting Gemini embeddings for %d text(s) (model=%s, dim=%d)",
        len(texts),
        gemini_model,
        dimension,
    )

    try:
        return await _embed_gemini_with_retry(
            texts, gemini_model, dimension, max_retries
        )
    except EmbeddingConfigurationError:
        raise
    except Exception as exc:
        logger.error("Gemini embedding failed: %s", exc)
        raise EmbeddingError(
            f"Gemini embeddings call failed for model '{gemini_model}': {exc}"
        ) from exc
