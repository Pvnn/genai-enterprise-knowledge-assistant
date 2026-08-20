"""Tests for the reranker module.

Owner: P3
Import shared fixtures from conftest.py (owned by P2).  Do NOT define
new fixture setups that duplicate what conftest.py already provides.

Strategy:
- Tests exercise the fail-safe contract: rerank() must never raise.
- The FlagEmbedding model is always mocked / patched so no model download
  or GPU is required in CI.
- Cross-encoder score ordering is asserted where the fake model provides
  deterministic scores; integration tests with a real model are left for a
  dedicated evaluation environment.
"""

from __future__ import annotations

import numpy as np
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
    """rerank() should return exactly top_n chunks when model is available,
    sorted by the cross-encoder scores the fake model returns."""
    chunks = _make_chunks(10)
    # Assign scores in descending order so chunks[0] receives the highest score.
    fake_scores = list(range(10, 0, -1))  # [10, 9, 8, …, 1]

    fake_model = MagicMock()
    fake_model.compute_score.return_value = [float(s) for s in fake_scores]

    # Reset the module-level cache so our patch is visible.
    reranker_module._reranker_model = fake_model
    reranker_module._model_load_failed = False
    reranker_module._reranker_backend = "flag_reranker"  # use compute_score API

    try:
        result = rerank("my query", chunks, top_n=5)
    finally:
        reranker_module._reranker_model = None
        reranker_module._model_load_failed = False
        reranker_module._reranker_backend = None

    assert len(result) == 5
    # chunks[0] has the highest fake score (10.0) and must sort to position 0.
    assert result[0].text == chunks[0].text


def test_rerank_returns_all_when_fewer_than_top_n() -> None:
    """rerank() returns all chunks when len(chunks) < top_n."""
    chunks = _make_chunks(3)
    fake_model = MagicMock()
    fake_model.compute_score.return_value = [0.9, 0.8, 0.7]

    reranker_module._reranker_model = fake_model
    reranker_module._model_load_failed = False
    reranker_module._reranker_backend = "flag_reranker"  # use compute_score API

    try:
        result = rerank("query", chunks, top_n=10)
    finally:
        reranker_module._reranker_model = None
        reranker_module._model_load_failed = False
        reranker_module._reranker_backend = None

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
    # Fallback returns the original input order, sliced to top_n.
    assert result == chunks[:4]


def test_rerank_falls_back_when_compute_score_raises() -> None:
    """rerank() must catch any exception from compute_score and fall back."""
    chunks = _make_chunks(6)

    fake_model = MagicMock()
    fake_model.compute_score.side_effect = RuntimeError("CUDA OOM")  # should not happen on CPU

    reranker_module._reranker_model = fake_model
    reranker_module._model_load_failed = False
    reranker_module._reranker_backend = "flag_reranker"  # use compute_score API

    try:
        result = rerank("query", chunks, top_n=3)
    finally:
        reranker_module._reranker_model = None
        reranker_module._model_load_failed = False
        reranker_module._reranker_backend = None

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
        try:
            result = rerank("query", chunks, top_n=5)
            # If _load_model itself raises we may get an exception depending on
            # the implementation; the test verifies the exception is caught or
            # the fallback is returned.
        except Exception:
            pytest.fail("rerank() must never raise into caller code")


# ── Settings integration ──────────────────────────────────────────────────────


def test_rerank_reads_top_n_from_settings_when_not_passed() -> None:
    """When top_n is not supplied, rerank() must use Settings.reranker_top_n.

    NEW TEST: regression guard for the bug where the function signature
    hardcoded ``top_n=5`` and never read from Settings, so a config change
    had no effect.
    """
    chunks = _make_chunks(10)
    fake_model = MagicMock()
    # Return 10 identical scores; ordering doesn't matter for this test.
    fake_model.compute_score.return_value = [1.0] * 10

    reranker_module._reranker_model = fake_model
    reranker_module._model_load_failed = False
    reranker_module._reranker_backend = "flag_reranker"  # use compute_score API

    mock_settings = MagicMock()
    mock_settings.reranker_top_n = 3  # different from the old hardcoded default of 5

    try:
        with patch("app.retrieval.reranker.get_settings", return_value=mock_settings):
            result = rerank("query", chunks)  # top_n intentionally omitted
    finally:
        reranker_module._reranker_model = None
        reranker_module._model_load_failed = False
        reranker_module._reranker_backend = None

    # Must honour the configured value, not the old hardcoded 5.
    assert len(result) == 3


def test_rerank_failsafe_when_get_settings_raises() -> None:
    """rerank() must not raise even if get_settings() fails; it defaults to 5 chunks."""
    chunks = _make_chunks(10)
    fake_model = MagicMock()
    fake_model.compute_score.return_value = [1.0] * 10

    reranker_module._reranker_model = fake_model
    reranker_module._model_load_failed = False
    reranker_module._reranker_backend = "flag_reranker"  # use compute_score API

    try:
        with patch("app.retrieval.reranker.get_settings", side_effect=RuntimeError("settings corrupted")):
            result = rerank("query", chunks)
    finally:
        reranker_module._reranker_model = None
        reranker_module._model_load_failed = False
        reranker_module._reranker_backend = None

    assert len(result) == 5


def test_rerank_failsafe_when_top_n_is_invalid_or_negative() -> None:
    """rerank() must handle negative or non-integer top_n safely without crashing."""
    chunks = _make_chunks(5)
    fake_model = MagicMock()
    fake_model.compute_score.return_value = [1.0] * 5

    reranker_module._reranker_model = fake_model
    reranker_module._model_load_failed = False
    reranker_module._reranker_backend = "flag_reranker"  # use compute_score API

    try:
        # Negative top_n should clamp to 0 and return empty list
        assert rerank("query", chunks, top_n=-1) == []
        # Non-numeric string top_n should fall back to default (5) without raising
        result = rerank("query", chunks, top_n="invalid_number")  # type: ignore[arg-type]
        assert len(result) == 5
    finally:
        reranker_module._reranker_model = None
        reranker_module._model_load_failed = False
        reranker_module._reranker_backend = None


# ── Dual-backend regression tests (added after XLMRobertaTokenizer fix) ───────
#
# These tests guard the new _load_model() two-stage logic and the
# _compute_scores() dispatcher introduced to fix:
#   "XLMRobertaTokenizer has no attribute prepare_for_model"
# which occurred when FlagEmbedding 1.4.x called the slow tokenizer path on
# transformers >= 4.45 with certain cached tokenizer_config.json files.


def _reset_reranker_state() -> None:
    """Helper: fully reset all module-level reranker state between tests."""
    reranker_module._reranker_model = None
    reranker_module._model_load_failed = False
    reranker_module._reranker_backend = None


class TestLoadModelBackendSelection:
    """_load_model() must prefer CrossEncoder and fall back to FlagReranker.

    NOTE: Each test here spawns a fresh Python subprocess.
    Patching sentence_transformers.CrossEncoder inside the current pytest
    process triggers a torch C-extension segfault because the patch forces
    torch to re-initialise its C extension in a process where it was already
    loaded by previous tests.  Subprocess isolation is the only safe strategy.
    """

    _PYTHON = str(
        __import__("pathlib").Path(__file__).parent.parent.parent / ".venv" / "bin" / "python"
    )
    _BACKEND = str(
        __import__("pathlib").Path(__file__).parent.parent
    )

    def _run(self, script: str) -> str:
        """Run *script* in a fresh Python subprocess and return its stdout."""
        import subprocess
        result = subprocess.run(
            [self._PYTHON, "-c", script],
            capture_output=True,
            text=True,
            env={**__import__("os").environ, "PYTHONPATH": self._BACKEND},
            timeout=30,
        )
        assert result.returncode == 0, (
            f"Subprocess failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
        return result.stdout.strip()

    def test_cross_encoder_is_preferred_when_available(self) -> None:
        """_load_model() must record backend='cross_encoder' when CrossEncoder works."""
        out = self._run("""
from unittest.mock import MagicMock, patch
from app.retrieval import reranker as r
r._reranker_model = None
r._model_load_failed = False
r._reranker_backend = None
fake = MagicMock()
with patch("sentence_transformers.CrossEncoder", return_value=fake):
    m = r._load_model()
print(r._reranker_backend)
print(m is fake)
""")
        lines = out.splitlines()
        assert lines[0] == "cross_encoder", f"backend={lines[0]!r}"
        assert lines[1] == "True"

    def test_falls_back_to_flag_reranker_when_cross_encoder_raises(self) -> None:
        """_load_model() must record backend='flag_reranker' when CrossEncoder raises."""
        out = self._run("""
from unittest.mock import MagicMock, patch
from app.retrieval import reranker as r
r._reranker_model = None
r._model_load_failed = False
r._reranker_backend = None
fake_fr = MagicMock()
with patch("sentence_transformers.CrossEncoder", side_effect=RuntimeError("CE down")):
    with patch("FlagEmbedding.FlagReranker", return_value=fake_fr):
        m = r._load_model()
print(r._reranker_backend)
print(m is fake_fr)
""")
        lines = out.splitlines()
        assert lines[0] == "flag_reranker", f"backend={lines[0]!r}"
        assert lines[1] == "True"

    def test_model_load_failed_set_when_both_backends_raise(self) -> None:
        """_model_load_failed must be True when both CrossEncoder and FlagReranker raise."""
        out = self._run("""
from unittest.mock import patch
from app.retrieval import reranker as r
r._reranker_model = None
r._model_load_failed = False
r._reranker_backend = None
with patch("sentence_transformers.CrossEncoder", side_effect=RuntimeError("CE down")):
    with patch("FlagEmbedding.FlagReranker", side_effect=RuntimeError("FR down")):
        m = r._load_model()
print(m is None)
print(r._model_load_failed)
""")
        lines = out.splitlines()
        assert lines[0] == "True",  "model should be None"
        assert lines[1] == "True",  "_model_load_failed should be True"

    def test_cached_model_returned_without_calling_constructors(self) -> None:
        """_load_model() must return the cached instance immediately on 2nd call."""
        out = self._run("""
from unittest.mock import MagicMock, patch
from app.retrieval import reranker as r
sentinel = MagicMock(name="CachedModel")
r._reranker_model = sentinel
r._reranker_backend = "cross_encoder"
r._model_load_failed = False
with patch(
    "sentence_transformers.CrossEncoder",
    side_effect=AssertionError("should not be called"),
):
    m = r._load_model()
print(m is sentinel)
""")
        assert out.strip() == "True"


class TestComputeScoresDispatcher:
    """_compute_scores() must dispatch to the right API per backend."""

    def test_cross_encoder_backend_uses_predict_with_sigmoid(self) -> None:
        """_compute_scores() with backend='cross_encoder' must call predict()
        and sigmoid-normalise the raw logits to [0, 1]."""
        _reset_reranker_state()
        reranker_module._reranker_backend = "cross_encoder"

        fake_model = MagicMock()
        fake_model.predict.return_value = np.array([0.0, 100.0, -100.0])

        pairs = [("q", "a"), ("q", "b"), ("q", "c")]
        try:
            scores = reranker_module._compute_scores(fake_model, pairs)
        finally:
            _reset_reranker_state()

        fake_model.predict.assert_called_once_with(
            pairs, apply_softmax=False, convert_to_numpy=True
        )
        assert abs(scores[0] - 0.5) < 1e-6, "sigmoid(0) should be 0.5"
        assert scores[1] > 0.99, "sigmoid(100) should be near 1.0"
        assert scores[2] < 0.01, "sigmoid(-100) should be near 0.0"

    def test_flag_reranker_backend_uses_compute_score(self) -> None:
        """_compute_scores() with backend='flag_reranker' must delegate to
        model.compute_score(pairs, normalize=True) directly."""
        _reset_reranker_state()
        reranker_module._reranker_backend = "flag_reranker"

        fake_model = MagicMock()
        fake_model.compute_score.return_value = [0.8, 0.6]

        pairs = [("q", "a"), ("q", "b")]
        try:
            scores = reranker_module._compute_scores(fake_model, pairs)
        finally:
            _reset_reranker_state()

        fake_model.compute_score.assert_called_once_with(pairs, normalize=True)
        assert scores == [0.8, 0.6]

    def test_unknown_backend_falls_through_to_flag_reranker_api(self) -> None:
        """An unexpected _reranker_backend value must not crash."""
        _reset_reranker_state()
        reranker_module._reranker_backend = "unknown_future_backend"

        fake_model = MagicMock()
        fake_model.compute_score.return_value = [0.5]

        pairs = [("q", "a")]
        try:
            scores = reranker_module._compute_scores(fake_model, pairs)
        finally:
            _reset_reranker_state()

        assert scores == [0.5]


class TestRerankerEndToEndWithCrossEncoder:
    """Integration-style tests wiring a fake CrossEncoder through rerank()."""

    def test_rerank_uses_cross_encoder_predict_and_sorts_correctly(self) -> None:
        """rerank() with cross_encoder backend must call predict() and sort
        chunks by descending sigmoid-normalised score."""
        _reset_reranker_state()
        chunks = _make_chunks(4)

        # Logits: [-1→0.27, 0→0.5, 5→0.993, -3→0.047]
        # Sorted desc: chunks[2], chunks[1], chunks[0], chunks[3]
        logits = np.array([-1.0, 0.0, 5.0, -3.0])

        fake_model = MagicMock()
        fake_model.predict.return_value = logits

        reranker_module._reranker_model = fake_model
        reranker_module._reranker_backend = "cross_encoder"
        reranker_module._model_load_failed = False

        try:
            result = rerank("query", chunks, top_n=2)
        finally:
            _reset_reranker_state()

        assert len(result) == 2
        assert result[0].text == chunks[2].text, "chunks[2] (logit=5) must be first"
        assert result[1].text == chunks[1].text, "chunks[1] (logit=0) must be second"

    def test_rerank_falls_back_when_cross_encoder_predict_raises_attribute_error(self) -> None:
        """rerank() must fall back gracefully when CrossEncoder.predict() raises
        the exact AttributeError that triggered this bug fix."""
        _reset_reranker_state()
        chunks = _make_chunks(5)

        fake_model = MagicMock()
        fake_model.predict.side_effect = AttributeError(
            "XLMRobertaTokenizer has no attribute prepare_for_model"
        )

        reranker_module._reranker_model = fake_model
        reranker_module._reranker_backend = "cross_encoder"
        reranker_module._model_load_failed = False

        try:
            result = rerank("Cognizant bribery policy", chunks, top_n=3)
        finally:
            _reset_reranker_state()

        assert len(result) <= 3
        assert all(c in chunks for c in result)

    def test_rerank_backend_state_is_fully_isolated(self) -> None:
        """_reset_reranker_state() must restore module state completely."""
        _reset_reranker_state()
        assert reranker_module._reranker_model is None
        assert reranker_module._model_load_failed is False
        assert reranker_module._reranker_backend is None
