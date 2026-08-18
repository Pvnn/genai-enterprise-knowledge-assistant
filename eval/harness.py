#!/usr/bin/env python3
"""
P8 Evaluation Harness for GenAI Enterprise Knowledge Assistant.

Reads gold_qa.json, calls the /chat endpoint (or a mock), and computes:
- Hit-Rate@k (k=5,10)
- Mean Reciprocal Rank (MRR)
- Faithfulness (LLM-based)
- Refusal accuracy

Usage:
    python harness.py --gold eval/gold_qa.json
    python harness.py --gold eval/gold_qa.json --mock
    python harness.py --gold eval/gold_qa.json --api-url http://localhost:8000
"""

import asyncio
import argparse
import json
import logging
import sys
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path

import aiohttp
import openai
from openai import AsyncOpenAI

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# ---------- Data Models ----------
@dataclass
class GoldQuestion:
    question: str
    answer: str
    document_id: str
    section_path: str
    expected_response_type: str  # "factual" or "refusal"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GoldQuestion":
        return cls(
            question=data["question"],
            answer=data["answer"],
            document_id=data["document_id"],
            section_path=data["section_path"],
            expected_response_type=data.get("expected_response_type", "factual"),
        )


@dataclass
class ChatResponse:
    answer: str
    refused: bool
    chunks: List[Dict[str, Any]]  # each should have document_id, section_path, text
    confidence: Optional[float] = None
    conflict: Optional[Dict] = None
    error: Optional[str] = None


@dataclass
class EvalResult:
    question: str
    expected_type: str
    expected_doc: str
    expected_section: str
    actual_answer: str
    refused: bool
    retrieved_docs: List[str]  # list of document_ids from top chunks
    retrieved_sections: List[str]  # list of section_paths
    hit_at_5: bool
    hit_at_10: bool
    reciprocal_rank: float
    faithfulness: Optional[bool] = None
    faithfulness_reason: Optional[str] = None
    error: Optional[str] = None


# ---------- Mock API ----------
class MockChatAPI:
    """Simulates the /chat endpoint for early testing."""

    async def chat(self, question: str) -> ChatResponse:
        # Simple mock: if question contains "refusal" (case-insensitive) or is about topics not in docs, refuse
        refusal_keywords = [
            "vacation", "remote work", "leave of absence", "dress code",
            "bonus", "insurance", "holiday", "laptop", "phone",
            "performance review", "password", "social media", "gym",
            "telemedicine", "desk", "travel reimbursement", "pet",
            "overtime", "401(k)", "email", "discount", "meeting room",
            "freelancing", "name change", "office supplies", "tuition",
            "vehicle", "software license", "carryover", "daycare",
            "paternity", "unpaid time off", "parking", "credit card",
            "cab", "address", "ID card", "study leave", "snacks",
            "fitness", "IT equipment", "payslip", "wellness", "visitors",
            "conference room", "employee assistance", "salary certificate",
            "office seating", "work from home", "mobile phone", "maintenance",
            "language training", "booking a meeting room", "expense reimbursement",
            "printer"
        ]
        q_lower = question.lower()
        if any(kw in q_lower for kw in refusal_keywords) or "not in corpus" in question:
            return ChatResponse(
                answer="I couldn't find a passage in the current policy documents that directly answers this. You may want to check with the appropriate department or rephrase your question.",
                refused=True,
                chunks=[],
                confidence=0.2
            )
        else:
            # Mock: return fake chunks with the expected document and section
            # For simplicity, we assume the gold document/section are returned.
            # In real eval, we'd parse from the actual response.
            return ChatResponse(
                answer="This is a mock answer. The policy states that all associates must comply with the relevant guidelines.",
                refused=False,
                chunks=[
                    {
                        "document_id": "mock-doc-1",
                        "section_path": "Section 1.1",
                        "text": "All associates must comply with company policies."
                    }
                ],
                confidence=0.9
            )


# ---------- Real API Client ----------
class ChatAPIClient:
    def __init__(self, api_url: str, timeout: int = 30):
        self.api_url = api_url.rstrip("/")
        self.timeout = timeout
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout))
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def chat(self, question: str) -> ChatResponse:
        """Call the actual /chat endpoint."""
        if not self.session:
            raise RuntimeError("Session not initialized. Use async context manager.")
        payload = {"query": question, "tenant_id": "default"}  # adjust as per API contract
        try:
            async with self.session.post(f"{self.api_url}/chat", json=payload) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    return ChatResponse(
                        answer="",
                        refused=True,
                        chunks=[],
                        error=f"API returned {resp.status}: {error_text}"
                    )
                data = await resp.json()
                # Parse according to expected API response (see Section 5 of spec)
                # Expected shape: { "answer": "...", "refused": bool, "citations": [ { "document_id": "...", "section_path": "...", "text": "..." } ], "confidence": float, "conflict": {...} }
                answer = data.get("answer", "")
                refused = data.get("refused", False)
                chunks = data.get("citations", [])
                # Ensure each chunk has document_id and section_path
                for chunk in chunks:
                    chunk.setdefault("document_id", "unknown")
                    chunk.setdefault("section_path", "unknown")
                confidence = data.get("confidence")
                conflict = data.get("conflict")
                return ChatResponse(
                    answer=answer,
                    refused=refused,
                    chunks=chunks,
                    confidence=confidence,
                    conflict=conflict
                )
        except asyncio.TimeoutError:
            return ChatResponse(answer="", refused=True, chunks=[], error="Request timeout")
        except Exception as e:
            logger.exception("Error calling /chat")
            return ChatResponse(answer="", refused=True, chunks=[], error=str(e))


# ---------- Faithfulness Evaluator ----------
class FaithfulnessEvaluator:
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    async def evaluate(self, question: str, answer: str, chunks: List[Dict[str, Any]]) -> Tuple[bool, str]:
        """Use LLM to judge if answer is supported by chunks."""
        if not answer or not chunks:
            return False, "No answer or no chunks to verify."

        # Build context from chunks
        context = "\n".join([chunk.get("text", "") for chunk in chunks if chunk.get("text")])
        if not context:
            return False, "No text in chunks."

        prompt = f"""
You are a faithfulness judge. Given a question, a set of retrieved passages (context), and an answer, determine whether the answer is fully supported by the context.

Question: {question}

Context:
{context}

Answer: {answer}

Is the answer completely supported by the context? Answer only "YES" or "NO". If "NO", briefly explain why.
"""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=100,
            )
            verdict = response.choices[0].message.content.strip().upper()
            if verdict.startswith("YES"):
                return True, "Faithful"
            else:
                # Extract reason if any
                reason = verdict if len(verdict) > 3 else "Unsupported"
                return False, reason
        except Exception as e:
            logger.error(f"Faithfulness evaluation failed: {e}")
            return False, f"Evaluation error: {str(e)}"


# ---------- Evaluation Core ----------
def load_gold_questions(file_path: str) -> List[GoldQuestion]:
    with open(file_path, "r", encoding="utf-8-sig") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("Gold file must contain a JSON array.")
    return [GoldQuestion.from_dict(item) for item in data]


def compute_metrics(results: List[EvalResult]) -> Dict[str, Any]:
    total = len(results)
    factual = [r for r in results if r.expected_type == "factual"]
    refusal = [r for r in results if r.expected_type == "refusal"]

    def calc_for_group(group: List[EvalResult]) -> Dict:
        n = len(group)
        if n == 0:
            return {k: 0.0 for k in ("hit_at_5", "hit_at_10", "mrr", "faithfulness_accuracy", "refusal_accuracy")}
        hit5 = sum(1 for r in group if r.hit_at_5) / n
        hit10 = sum(1 for r in group if r.hit_at_10) / n
        mrr = sum(r.reciprocal_rank for r in group) / n
        # Faithfulness only for factual non-refused
        faithful_items = [r for r in group if r.expected_type == "factual" and not r.refused and r.faithfulness is not None]
        faithfulness_accuracy = sum(1 for r in faithful_items if r.faithfulness) / len(faithful_items) if faithful_items else 0.0
        # Refusal accuracy: for refusal group, check if refused is True; for factual, check if refused is False
        if group and group[0].expected_type == "refusal":
            refusal_acc = sum(1 for r in group if r.refused) / n
        else:
            # factual: should not refuse
            refusal_acc = sum(1 for r in group if not r.refused) / n
        return {
            "hit_at_5": hit5,
            "hit_at_10": hit10,
            "mrr": mrr,
            "faithfulness_accuracy": faithfulness_accuracy,
            "refusal_accuracy": refusal_acc,
            "count": n,
        }

    overall = calc_for_group(results)
    factual_stats = calc_for_group(factual)
    refusal_stats = calc_for_group(refusal)

    return {
        "overall": overall,
        "factual": factual_stats,
        "refusal": refusal_stats,
        "total_questions": total,
        "errors": sum(1 for r in results if r.error),
    }


async def evaluate_single(
    question: GoldQuestion,
    chat_client,
    faithfulness_eval: Optional[FaithfulnessEvaluator] = None,
) -> EvalResult:
    """Evaluate a single gold question."""
    try:
        resp = await chat_client.chat(question.question)
    except Exception as e:
        return EvalResult(
            question=question.question,
            expected_type=question.expected_response_type,
            expected_doc=question.document_id,
            expected_section=question.section_path,
            actual_answer="",
            refused=True,
            retrieved_docs=[],
            retrieved_sections=[],
            hit_at_5=False,
            hit_at_10=False,
            reciprocal_rank=0.0,
            error=str(e),
        )

    retrieved_docs = [chunk.get("document_id", "unknown") for chunk in resp.chunks]
    retrieved_sections = [chunk.get("section_path", "unknown") for chunk in resp.chunks]

    # Determine if expected document/section is present
    expected_doc = question.document_id
    expected_section = question.section_path

    # Hit if the expected doc appears in top-k (we'll use k=5 and 10)
    # For simplicity, we consider a hit if the document_id matches and section_path matches (or partial match)
    # If the gold document is "Not in corpus", we can't expect a hit.
    hit_at_5 = False
    hit_at_10 = False
    reciprocal_rank = 0.0

    if expected_doc != "Not in corpus":
        # Find first occurrence of expected doc and section
        for idx, (doc, sec) in enumerate(zip(retrieved_docs, retrieved_sections), start=1):
            if doc == expected_doc and expected_section in sec:  # section may be exact or substring
                reciprocal_rank = 1.0 / idx
                if idx <= 5:
                    hit_at_5 = True
                if idx <= 10:
                    hit_at_10 = True
                break

    # Faithfulness: if factual and not refused and we have chunks
    faithfulness = None
    faithfulness_reason = None
    if question.expected_response_type == "factual" and not resp.refused and resp.chunks and faithfulness_eval:
        faithful, reason = await faithfulness_eval.evaluate(
            question.question,
            resp.answer,
            resp.chunks
        )
        faithfulness = faithful
        faithfulness_reason = reason

    return EvalResult(
        question=question.question,
        expected_type=question.expected_response_type,
        expected_doc=expected_doc,
        expected_section=expected_section,
        actual_answer=resp.answer,
        refused=resp.refused,
        retrieved_docs=retrieved_docs,
        retrieved_sections=retrieved_sections,
        hit_at_5=hit_at_5,
        hit_at_10=hit_at_10,
        reciprocal_rank=reciprocal_rank,
        faithfulness=faithfulness,
        faithfulness_reason=faithfulness_reason,
        error=resp.error,
    )


async def run_evaluation(
    gold_file: str,
    api_url: Optional[str] = None,
    mock: bool = False,
    openai_api_key: Optional[str] = None,
    max_concurrent: int = 10,
) -> Dict[str, Any]:
    """Run the full evaluation."""
    gold_questions = load_gold_questions(gold_file)
    logger.info(f"Loaded {len(gold_questions)} gold questions.")

    # Setup chat client
    if mock:
        chat_client = MockChatAPI()
        # Need to wrap mock to match async interface
        class MockWrapper:
            async def chat(self, question):
                return await chat_client.chat(question)
        chat_client = MockWrapper()
    else:
        if not api_url:
            raise ValueError("API URL must be provided when not in mock mode.")
        chat_client = await ChatAPIClient(api_url).__aenter__()

    # Setup faithfulness evaluator if API key provided
    faithfulness_eval = None
    if openai_api_key:
        faithfulness_eval = FaithfulnessEvaluator(api_key=openai_api_key)
    else:
        logger.warning("No OpenAI API key provided; skipping faithfulness evaluation.")

    # Evaluate with concurrency limit
    semaphore = asyncio.Semaphore(max_concurrent)

    async def eval_with_semaphore(q):
        async with semaphore:
            return await evaluate_single(q, chat_client, faithfulness_eval)

    tasks = [eval_with_semaphore(q) for q in gold_questions]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Filter out exceptions
    valid_results = []
    for r in results:
        if isinstance(r, Exception):
            logger.error(f"Evaluation failed: {r}")
            # Create an error result
            valid_results.append(EvalResult(
                question="unknown",
                expected_type="unknown",
                expected_doc="unknown",
                expected_section="unknown",
                actual_answer="",
                refused=True,
                retrieved_docs=[],
                retrieved_sections=[],
                hit_at_5=False,
                hit_at_10=False,
                reciprocal_rank=0.0,
                error=str(r),
            ))
        else:
            valid_results.append(r)

    # Compute metrics
    metrics = compute_metrics(valid_results)

    # Also compute per-question details for reporting
    details = []
    for r in valid_results:
        details.append({
            "question": r.question,
            "expected_type": r.expected_type,
            "expected_doc": r.expected_doc,
            "expected_section": r.expected_section,
            "actual_answer": r.actual_answer,
            "refused": r.refused,
            "hit_at_5": r.hit_at_5,
            "hit_at_10": r.hit_at_10,
            "reciprocal_rank": r.reciprocal_rank,
            "faithfulness": r.faithfulness,
            "faithfulness_reason": r.faithfulness_reason,
            "error": r.error,
        })

    return {
        "metrics": metrics,
        "details": details,
        "total_questions": len(gold_questions),
    }


# ---------- Main ----------
async def main():
    parser = argparse.ArgumentParser(description="Evaluate RAG system with gold QA set.")
    parser.add_argument("--gold", required=True, help="Path to gold_qa.json")
    parser.add_argument("--api-url", help="Base URL of the /chat endpoint (e.g., http://localhost:8000)")
    parser.add_argument("--mock", action="store_true", help="Use mock API instead of real endpoint")
    parser.add_argument("--openai-key", help="OpenAI API key for faithfulness evaluation (or set OPENAI_API_KEY env var)")
    parser.add_argument("--output", help="Output JSON file for detailed results")
    parser.add_argument("--concurrency", type=int, default=10, help="Max concurrent requests")
    args = parser.parse_args()

    if not args.mock and not args.api_url:
        parser.error("Either --api-url or --mock must be provided.")

    # Get OpenAI key from env if not provided
    openai_key = args.openai_key or os.environ.get("OPENAI_API_KEY")
    if openai_key:
        logger.info("Faithfulness evaluation enabled.")
    else:
        logger.info("Faithfulness evaluation disabled (no API key).")

    # Run evaluation
    try:
        result = await run_evaluation(
            gold_file=args.gold,
            api_url=args.api_url,
            mock=args.mock,
            openai_api_key=openai_key,
            max_concurrent=args.concurrency,
        )
    except Exception as e:
        logger.exception("Evaluation failed")
        sys.exit(1)

    # Print summary
    metrics = result["metrics"]
    print("\n" + "=" * 60)
    print("EVALUATION SUMMARY")
    print("=" * 60)
    print(f"Total questions: {metrics['total_questions']}")
    print(f"Errors: {metrics['errors']}")
    print("\nOverall Metrics:")
    for k, v in metrics["overall"].items():
        if k != "count":
            print(f"  {k}: {v:.4f}")
    print("\nFactual Questions:")
    for k, v in metrics["factual"].items():
        if k != "count":
            print(f"  {k}: {v:.4f}")
    print("\nRefusal Questions:")
    for k, v in metrics["refusal"].items():
        if k != "count":
            print(f"  {k}: {v:.4f}")
    print("=" * 60)

    # Save details if output file specified
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, default=str)
        logger.info(f"Detailed results saved to {args.output}")


if __name__ == "__main__":
    import os
    asyncio.run(main())