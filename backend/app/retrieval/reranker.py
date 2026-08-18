"""Stage 4, Priority 2 – Cross-encoder reranking.

Owner: P3  |  Priority: 2
Uses bge-reranker-base (via FlagEmbedding) to jointly score (query, chunk_text)
pairs.  Reranks the fused top-~25 candidates (from hybrid retrieval) down to
the top-n results that are passed to the generator.

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


def _load_model() -> Any:
    """Load and cache the bge-reranker-base FlagReranker model.

    Attempts import of FlagEmbedding.  If the library is not installed or the
    model cannot be fetched, logs a warning and returns None so that rerank()
    can fall back gracefully.

    Returns:
        FlagReranker instance, or None if loading failed.
    """
    global _reranker_model, _model_load_failed  # noqa: PLW0603

    if _model_load_failed:
        return None
    if _reranker_model is not None:
        return _reranker_model

    try:
        from FlagEmbedding import FlagReranker  # type: ignore[import-untyped]  # noqa: PLC0415

        logger.info("Loading reranker model '%s' (CPU-only)…", _BGE_MODEL_NAME)
        _reranker_model = FlagReranker(_BGE_MODEL_NAME, use_fp16=False)
        logger.info("Reranker model loaded successfully.")
        return _reranker_model
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Could not load reranker model '%s': %s. "
            "rerank() will fall back to returning input order.",
            _BGE_MODEL_NAME,
            exc,
        )
        _model_load_failed = True
        return None


# ── Public API ────────────────────────────────────────────────────────────────


def rerank(query: str, chunks: list[ChunkResult], top_n: int = 5) -> list[ChunkResult]:
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
        top_n: Number of top chunks to return after reranking.  Defaults to
               the value of ``Settings.reranker_top_n`` (5 by spec).

    Returns:
        list[ChunkResult]: Top-n chunks sorted by cross-encoder score (desc).
        If reranking fails, returns ``chunks[:top_n]`` in original order.
    """
    if not chunks:
        return []

    # Clamp top_n to the number of available chunks.
    effective_top_n = min(top_n, len(chunks))

    try:
        model = _load_model()
        if model is None:
            logger.warning(
                "Reranker model unavailable – returning top_%d chunks in retrieval order.",
                effective_top_n,
            )
            return list(chunks[:effective_top_n])

        # Build sentence pairs expected by FlagReranker.
        pairs: list[tuple[str, str]] = [(query, chunk.text) for chunk in chunks]

        # compute_score returns a list of float scores, index-aligned with pairs.
        scores: list[float] = model.compute_score(pairs, normalize=True)

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
            query[:80],
            len(chunks),
            exc,
        )
        return list(chunks[:effective_top_n])
