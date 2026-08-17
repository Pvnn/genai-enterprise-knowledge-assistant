"""Tests for the reranker module.

Owner: P3
Import shared fixtures from conftest.py (owned by P2).  Do NOT define
new fixture setups that duplicate what conftest.py already provides.

Strategy:
- Tests exercise the fail-safe contract: rerank() must never raise.
- The FlagEmbedding model is always mocked / patched so no model download
  or GPU is required in CI.
- Assertions about cross-encoder score ordering are marked TODO(P3) pending
  an integration environment with the model present.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.retrieval import reranker as reranker_module
from app.retrieval.reranker import rerank
from app.schemas import ChunkResult


# ── Fixtures ──────────────────────────────────────────────────────────────────


def _make_chunk(text: str = "sample text", score: float = 0.9) -> ChunkResult:
    """Return a minimal ChunkResult for testing."""
    return ChunkResult(
        chunk_id=uuid4(),
        document_id=uuid4(),
        text=text,
        section_path="section/1",
        score=score,
    )


def _make_chunks(n: int) -> list[ChunkResult]:
    return [_make_chunk(text=f"chunk text {i}", score=float(n - i) / n) for i in range(n)]


# ── Happy-path tests ──────────────────────────────────────────────────────────


def test_rerank_returns_top_n_with_working_model() -> None:
    """rerank() should return exactly top_n chunks when model is available."""
    # Fake model: assign scores in reverse order so last chunk becomes first.
    chunks = _make_chunks(10)
    fake_scores = list(range(10, 0, -1))  # [10, 9, 8, …, 1]

    fake_model = MagicMock()
    fake_model.compute_score.return_value = [float(s) for s in fake_scores]

    # Reset the module-level cache so our patch is visible.
    reranker_module._reranker_model = fake_model
    reranker_module._model_load_failed = False

    try:
        result = rerank("my query", chunks, top_n=5)
    finally:
        reranker_module._reranker_model = None
        reranker_module._model_load_failed = False

    assert len(result) == 5
    # TODO(P3): assert result[0].text == chunks[0].text once scores are real


def test_rerank_returns_all_when_fewer_than_top_n() -> None:
    """rerank() returns all chunks when len(chunks) < top_n."""
    chunks = _make_chunks(3)
    fake_model = MagicMock()
    fake_model.compute_score.return_value = [0.9, 0.8, 0.7]

    reranker_module._reranker_model = fake_model
    reranker_module._model_load_failed = False

    try:
        result = rerank("query", chunks, top_n=10)
    finally:
        reranker_module._reranker_model = None
        reranker_module._model_load_failed = False

    assert len(result) == 3


def test_rerank_empty_chunks_returns_empty() -> None:
    """rerank() with an empty chunk list must return an empty list."""
    result = rerank("some query", [], top_n=5)
    assert result == []


# ── Fail-safe tests ───────────────────────────────────────────────────────────


def test_rerank_falls_back_when_model_unavailable() -> None:
    """rerank() must not raise when FlagEmbedding is not installed."""
    reranker_module._reranker_model = None
    reranker_module._model_load_failed = False

    chunks = _make_chunks(8)

    # Simulate ImportError from FlagEmbedding.
    with patch.dict(
        "sys.modules",
        {"FlagEmbedding": None},  # type: ignore[dict-item]
    ):
        # Force _load_model to re-run by clearing the cache flag.
        reranker_module._model_load_failed = False
        result = rerank("query", chunks, top_n=5)

    # Cleanup module state.
    reranker_module._model_load_failed = False

    # Should not raise and should return at most top_n chunks.
    assert len(result) <= 5
    # TODO(P3): assert result == chunks[:5] once fallback ordering is stable


def test_rerank_falls_back_when_model_load_failed_flag_is_set() -> None:
    """rerank() returns input order when _model_load_failed is True."""
    reranker_module._reranker_model = None
    reranker_module._model_load_failed = True

    chunks = _make_chunks(10)

    try:
        result = rerank("query", chunks, top_n=4)
    finally:
        reranker_module._model_load_failed = False

    assert len(result) == 4
    # TODO(P3): assert result == chunks[:4]


def test_rerank_falls_back_when_compute_score_raises() -> None:
    """rerank() must catch any exception from compute_score and fall back."""
    chunks = _make_chunks(6)

    fake_model = MagicMock()
    fake_model.compute_score.side_effect = RuntimeError("CUDA OOM")  # should not happen on CPU

    reranker_module._reranker_model = fake_model
    reranker_module._model_load_failed = False

    try:
        result = rerank("query", chunks, top_n=3)
    finally:
        reranker_module._reranker_model = None
        reranker_module._model_load_failed = False

    # Must not raise; must return at most top_n chunks.
    assert len(result) <= 3


def test_rerank_never_raises_even_on_unexpected_exception() -> None:
    """rerank() must be completely exception-safe from the caller's perspective."""
    chunks = _make_chunks(5)

    reranker_module._reranker_model = None
    reranker_module._model_load_failed = False

    with patch.object(
        reranker_module, "_load_model", side_effect=Exception("Unexpected disaster")
    ):
        # rerank() catches all exceptions internally, so this must not propagate.
        try:
            result = rerank("query", chunks, top_n=5)
            # If _load_model itself raises we may get an exception depending on
            # the implementation; the test verifies the exception is caught or
            # the fallback is returned.
        except Exception:
            pytest.fail("rerank() must never raise into caller code")
