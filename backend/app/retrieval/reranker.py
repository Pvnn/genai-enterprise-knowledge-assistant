"""Stage 4, Priority 2 – Cross-encoder reranking.

Owner: P3  |  Priority: 2
Uses bge-reranker-base to jointly score (query, chunk_text) pairs.  Reranks
the fused top-~25 candidates (from hybrid retrieval) down to the top-n results
that are passed to the generator.

Backend selection (tried in order):
    1. sentence_transformers.CrossEncoder  – preferred; always uses the fast
       XLMRobertaTokenizerFast so ``prepare_for_model`` is always available.
    2. FlagEmbedding.FlagReranker          – secondary fallback.

This two-stage approach resolves the ``XLMRobertaTokenizer has no attribute
prepare_for_model`` AttributeError that occurs when FlagEmbedding 1.4.x calls
the slow tokenizer path on transformers ≥ 4.45 with certain cached configs.

CPU-only; no GPU required.

Fail-safe contract (Rule 7):
    If bge-reranker-base is unavailable, fails to load, or raises during
    scoring, this module catches the exception, logs a warning, and returns
    the input chunks unchanged (truncated to top_n).  The request is never
    crashed.  P4's generator.py documents this behaviour as its fallback.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from app.config import get_settings
from app.schemas import ChunkResult

logger = logging.getLogger(__name__)


# ── Typed exception ───────────────────────────────────────────────────────────


class RerankerError(Exception):
    """Raised internally when the cross-encoder model fails.

    This exception is always caught within rerank(); it never crosses into
    caller code.  It is defined here so that internal helpers can raise it
    explicitly rather than using a bare ``raise``.
    """


# ── Model loader (lazy; cached per process) ───────────────────────────────────

_reranker_model: Any = None
_model_load_failed: bool = False
_BGE_MODEL_NAME: str = "BAAI/bge-reranker-base"

# Tracks which backend was successfully loaded so _compute_scores dispatches
# to the correct API.  Values: "cross_encoder" | "flag_reranker" | None
_reranker_backend: str | None = None


def _load_model() -> Any:
    """Load and cache the bge-reranker-base model using the best available backend.

    Tries backends in this order:
        1. sentence_transformers.CrossEncoder  – preferred because it always
           uses XLMRobertaTokenizerFast, which has ``prepare_for_model``.
        2. FlagEmbedding.FlagReranker          – secondary; may fail on
           transformers ≥ 4.45 when the cached tokenizer_config.json specifies
           the slow XLMRobertaTokenizer class.

    Returns:
        Loaded model instance, or None if both backends failed.
    """
    global _reranker_model, _model_load_failed, _reranker_backend  # noqa: PLW0603

    if _model_load_failed:
        return None
    if _reranker_model is not None:
        return _reranker_model

    # ── Attempt 1: sentence-transformers CrossEncoder ─────────────────────────
    try:
        from sentence_transformers import CrossEncoder  # type: ignore[import-untyped]  # noqa: PLC0415

        logger.info(
            "Loading reranker model '%s' via CrossEncoder (CPU-only)…",
            _BGE_MODEL_NAME,
        )
        _reranker_model = CrossEncoder(_BGE_MODEL_NAME, max_length=512)
        _reranker_backend = "cross_encoder"
        logger.info("Reranker model loaded successfully (backend: CrossEncoder).")
        return _reranker_model
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "CrossEncoder backend unavailable for '%s': %s. "
            "Trying FlagEmbedding fallback…",
            _BGE_MODEL_NAME,
            exc,
        )

    # ── Attempt 2: FlagEmbedding FlagReranker ─────────────────────────────────
    try:
        from FlagEmbedding import FlagReranker  # type: ignore[import-untyped]  # noqa: PLC0415

        logger.info(
            "Loading reranker model '%s' via FlagReranker (CPU-only)…",
            _BGE_MODEL_NAME,
        )
        _reranker_model = FlagReranker(_BGE_MODEL_NAME, use_fp16=False)
        _reranker_backend = "flag_reranker"
        logger.info("Reranker model loaded successfully (backend: FlagReranker).")
        return _reranker_model
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Could not load reranker model '%s' with any backend: %s. "
            "rerank() will fall back to returning input order.",
            _BGE_MODEL_NAME,
            exc,
        )
        _model_load_failed = True
        return None


def _compute_scores(model: Any, pairs: list[tuple[str, str]]) -> list[float]:
    """Dispatch to the correct scoring API for the loaded backend.

    Args:
        model: The loaded reranker model instance.
        pairs: List of (query, passage) string pairs.

    Returns:
        List of float scores, index-aligned with ``pairs``.
    """
    if _reranker_backend == "cross_encoder":
        # CrossEncoder.predict returns a numpy array; convert to plain list.
        raw = model.predict(pairs, apply_softmax=False, convert_to_numpy=True)
        import numpy as np  # noqa: PLC0415
        # Sigmoid-normalise to [0, 1] to match FlagReranker normalize=True.
        scores = (1.0 / (1.0 + np.exp(-raw))).tolist()
        return scores  # type: ignore[return-value]
    else:
        # FlagReranker: compute_score(pairs, normalize=True) → list[float]
        return model.compute_score(pairs, normalize=True)  # type: ignore[return-value]


# ── Sentinel for unset top_n ──────────────────────────────────────────────────

_UNSET: object = object()


# ── Public API ────────────────────────────────────────────────────────────────


def rerank(query: str, chunks: list[ChunkResult], top_n: int | object = _UNSET) -> list[ChunkResult]:
    """Cross-encoder rerank a list of candidate chunks.

    Scores each (query, chunk.text) pair using bge-reranker-base and returns
    the top-n chunks sorted by descending cross-encoder score.

    Fail-safe: if the model is unavailable or scoring raises for any reason,
    the function logs a warning and returns ``chunks[:top_n]`` unchanged.
    This module will never raise into caller code.

    Args:
        query: The (possibly rewritten) user query.
        chunks: Candidate chunks from Stage 3 (dense or hybrid retrieval).
                Typically ~25 candidates.
        top_n: Number of top chunks to return after reranking. Defaults to
               ``Settings.reranker_top_n`` (currently 5). Pass an explicit
               integer to override the configured value for a single call.

    Returns:
        list[ChunkResult]: Top-n chunks sorted by cross-encoder score (desc).
        If reranking fails, returns ``chunks[:top_n]`` in original order.
    """
    if not chunks:
        return []

    # Fail-safe top_n resolution: handle missing settings or non-numeric/negative values.
    try:
        if top_n is _UNSET:
            try:
                top_n = get_settings().reranker_top_n
            except Exception:
                top_n = 5
        top_n_int = int(top_n)  # type: ignore[arg-type]
        effective_top_n = max(0, min(top_n_int, len(chunks)))
    except Exception:
        effective_top_n = min(5, len(chunks))

    if effective_top_n == 0:
        return []

    try:
        model = _load_model()
        if model is None:
            logger.warning(
                "Reranker model unavailable – returning top_%d chunks in retrieval order.",
                effective_top_n,
            )
            return list(chunks[:effective_top_n])

        # Build sentence pairs for the cross-encoder.
        pairs: list[tuple[str, str]] = [(query, chunk.text) for chunk in chunks]

        # Dispatch to the appropriate backend scoring API.
        scores: list[float] = _compute_scores(model, pairs)

        # Pair each chunk with its reranker score and sort descending.
        scored: list[tuple[float, ChunkResult]] = sorted(
            zip(scores, chunks),
            key=lambda t: t[0],
            reverse=True,
        )

        reranked = [chunk for _, chunk in scored[:effective_top_n]]

        logger.debug(
            "Reranked %d candidate(s) → top %d; "
            "top_score=%.4f, bottom_score=%.4f",
            len(chunks),
            len(reranked),
            scored[0][0] if scored else 0.0,
            scored[effective_top_n - 1][0] if scored else 0.0,
        )
        return reranked

    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Reranking failed (query=%r, n_chunks=%d): %s. "
            "Falling back to retrieval order.",
            query[:80] if isinstance(query, str) else "",
            len(chunks),
            exc,
        )
        return list(chunks[:effective_top_n])
