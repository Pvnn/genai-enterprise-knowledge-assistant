"""
Unit tests for the evaluation harness.
Run with: pytest tests/test_harness.py -v
"""

import json
import pytest
import sys
from pathlib import Path
from dataclasses import asdict

# Add the project root to the path so we can import the harness
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from eval.harness import (
    load_gold_questions,
    compute_metrics,
    EvalResult,
    GoldQuestion,
    ChatResponse,
    MockChatAPI,
)


# ---------- Fixtures ----------
@pytest.fixture
def sample_gold_data():
    """Sample gold QA data for testing."""
    return [
        {
            "question": "What is the Human Rights Policy?",
            "answer": "Cognizant's Human Rights Policy applies to all associates.",
            "document_id": "human-rights-policy.pdf",
            "section_path": "Scope",
            "expected_response_type": "factual",
        },
        {
            "question": "How many vacation days do I get?",
            "answer": "Refusal",
            "document_id": "Not in corpus",
            "section_path": "N/A",
            "expected_response_type": "refusal",
        },
    ]


@pytest.fixture
def sample_results():
    """Sample evaluation results for testing metrics."""
    return [
        EvalResult(
            question="Test question 1",
            expected_type="factual",
            expected_doc="doc1.pdf",
            expected_section="Section 1",
            actual_answer="Test answer",
            refused=False,
            retrieved_docs=["doc1.pdf", "doc2.pdf", "doc3.pdf"],
            retrieved_sections=["Section 1", "Section 2", "Section 3"],
            hit_at_5=True,
            hit_at_10=True,
            reciprocal_rank=1.0,
            faithfulness=True,
            faithfulness_reason="Faithful",
            error=None,
        ),
        EvalResult(
            question="Test question 2",
            expected_type="factual",
            expected_doc="doc1.pdf",
            expected_section="Section 1",
            actual_answer="Test answer",
            refused=False,
            retrieved_docs=["doc2.pdf", "doc3.pdf", "doc4.pdf"],
            retrieved_sections=["Section 2", "Section 3", "Section 4"],
            hit_at_5=False,
            hit_at_10=False,
            reciprocal_rank=0.0,
            faithfulness=False,
            faithfulness_reason="Not supported",
            error=None,
        ),
        EvalResult(
            question="Refusal test",
            expected_type="refusal",
            expected_doc="Not in corpus",
            expected_section="N/A",
            actual_answer="I couldn't find a passage...",
            refused=True,
            retrieved_docs=[],
            retrieved_sections=[],
            hit_at_5=False,
            hit_at_10=False,
            reciprocal_rank=0.0,
            faithfulness=None,
            faithfulness_reason=None,
            error=None,
        ),
    ]


# ---------- Tests ----------
class TestLoadGoldQuestions:
    """Tests for loading gold questions from JSON."""

    def test_load_valid_file(self, tmp_path, sample_gold_data):
        """Test loading a valid gold QA file."""
        file_path = tmp_path / "gold_qa.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(sample_gold_data, f)

        questions = load_gold_questions(str(file_path))

        assert len(questions) == 2
        assert questions[0].question == "What is the Human Rights Policy?"
        assert questions[0].expected_response_type == "factual"
        assert questions[1].expected_response_type == "refusal"

    def test_load_with_bom(self, tmp_path, sample_gold_data):
        """Test loading a file with UTF-8 BOM (Windows common issue)."""
        file_path = tmp_path / "gold_qa.json"
        # Write with BOM
        with open(file_path, "wb") as f:
            f.write(b"\xef\xbb\xbf")  # UTF-8 BOM
            f.write(json.dumps(sample_gold_data).encode("utf-8"))

        questions = load_gold_questions(str(file_path))

        assert len(questions) == 2
        assert questions[0].question == "What is the Human Rights Policy?"

    def test_load_empty_file(self, tmp_path):
        """Test loading an empty file (should succeed with empty list)."""
        file_path = tmp_path / "gold_qa.json"
        file_path.write_text("[]", encoding="utf-8")

        questions = load_gold_questions(str(file_path))
        assert len(questions) == 0

    def test_load_invalid_file(self, tmp_path):
        """Test loading an invalid JSON file."""
        file_path = tmp_path / "gold_qa.json"
        file_path.write_text("{ invalid json }", encoding="utf-8")

        with pytest.raises(json.JSONDecodeError):
            load_gold_questions(str(file_path))


class TestComputeMetrics:
    """Tests for metric computation."""

    def test_all_correct(self, sample_results):
        """Test metrics when all results are correct."""
        # Only take the first result (all correct)
        results = [sample_results[0]]
        metrics = compute_metrics(results)

        assert metrics["overall"]["hit_at_5"] == 1.0
        assert metrics["overall"]["hit_at_10"] == 1.0
        assert metrics["overall"]["mrr"] == 1.0
        assert metrics["overall"]["faithfulness_accuracy"] == 1.0
        assert metrics["overall"]["refusal_accuracy"] == 1.0

    def test_all_wrong(self, sample_results):
        """Test metrics when all results are wrong."""
        # Only take the second result (all wrong)
        results = [sample_results[1]]
        metrics = compute_metrics(results)

        assert metrics["overall"]["hit_at_5"] == 0.0
        assert metrics["overall"]["hit_at_10"] == 0.0
        assert metrics["overall"]["mrr"] == 0.0
        assert metrics["overall"]["faithfulness_accuracy"] == 0.0

    def test_refusal_accuracy(self, sample_results):
        """Test that refusal accuracy is computed correctly."""
        results = [sample_results[2]]  # Refusal question
        metrics = compute_metrics(results)

        assert metrics["refusal"]["refusal_accuracy"] == 1.0  # Should refuse
        assert metrics["refusal"]["count"] == 1

    def test_factual_refusal_accuracy(self, sample_results):
        """Test that factual questions are marked as inaccurate if they refuse."""
        results = [
            EvalResult(
                question="Factual question",
                expected_type="factual",
                expected_doc="doc1.pdf",
                expected_section="Section 1",
                actual_answer="I couldn't find...",
                refused=True,  # Wrong! Should not refuse
                retrieved_docs=[],
                retrieved_sections=[],
                hit_at_5=False,
                hit_at_10=False,
                reciprocal_rank=0.0,
                faithfulness=None,
                faithfulness_reason=None,
                error=None,
            )
        ]
        metrics = compute_metrics(results)

        assert metrics["factual"]["refusal_accuracy"] == 0.0  # Should be 0%

    def test_mixed_results(self, sample_results):
        """Test metrics with mixed correct/incorrect results."""
        metrics = compute_metrics(sample_results)

        # 3 results: 1 perfect, 1 wrong, 1 refusal
        assert metrics["overall"]["hit_at_5"] == 1.0 / 3  # Only first one hits
        assert metrics["overall"]["hit_at_10"] == 1.0 / 3
        assert metrics["overall"]["mrr"] == 1.0 / 3
        assert metrics["overall"]["count"] == 3
        assert metrics["factual"]["count"] == 2
        assert metrics["refusal"]["count"] == 1


class TestMockChatAPI:
    """Tests for the mock chat API."""

    @pytest.mark.asyncio
    async def test_refusal_keywords(self):
        """Test that refusal keywords trigger refusal."""
        api = MockChatAPI()

        # Test various refusal keywords
        refusal_questions = [
            "How many vacation days do I get?",
            "What is the policy on remote work?",
            "Can I apply for a leave of absence?",
            "What is the dress code?",
            "Does Cognizant offer free parking?",
        ]

        for question in refusal_questions:
            response = await api.chat(question)
            assert response.refused is True, f"Should refuse: {question}"
            assert "couldn't find" in response.answer.lower()

    @pytest.mark.asyncio
    async def test_non_refusal_questions(self):
        """Test that non-refusal questions don't trigger refusal."""
        api = MockChatAPI()

        factual_questions = [
            "What is the Human Rights Policy?",
            "Who does the Code of Ethics apply to?",
            "What is Cognizant's policy on discrimination?",
        ]

        for question in factual_questions:
            response = await api.chat(question)
            assert response.refused is False, f"Should NOT refuse: {question}"
            assert response.chunks is not None


class TestGoldQuestionModel:
    """Tests for the GoldQuestion dataclass."""

    def test_from_dict(self, sample_gold_data):
        """Test creating GoldQuestion from dictionary."""
        q = GoldQuestion.from_dict(sample_gold_data[0])

        assert q.question == "What is the Human Rights Policy?"
        assert q.answer == "Cognizant's Human Rights Policy applies to all associates."
        assert q.document_id == "human-rights-policy.pdf"
        assert q.section_path == "Scope"
        assert q.expected_response_type == "factual"

    def test_from_dict_missing_fields(self):
        """Test creating GoldQuestion with missing optional fields."""
        data = {
            "question": "Test?",
            "answer": "Answer.",
            "document_id": "test.pdf",
            "section_path": "Section 1",
            # expected_response_type is missing - should default to factual
        }
        q = GoldQuestion.from_dict(data)

        assert q.expected_response_type == "factual"  # Default value


class TestEvalResultModel:
    """Tests for the EvalResult dataclass."""

    def test_default_values(self):
        """Test that EvalResult has default values for optional fields."""
        result = EvalResult(
            question="Test?",
            expected_type="factual",
            expected_doc="doc.pdf",
            expected_section="Section 1",
            actual_answer="Answer.",
            refused=False,
            retrieved_docs=[],
            retrieved_sections=[],
            hit_at_5=False,
            hit_at_10=False,
            reciprocal_rank=0.0,
            # faithfulness and error are optional with defaults
        )

        assert result.faithfulness is None
        assert result.faithfulness_reason is None
        assert result.error is None


# ---------- Run Tests ----------
if __name__ == "__main__":
    pytest.main([__file__, "-v"])