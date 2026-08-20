#!/usr/bin/env python3
"""
P8 Evaluation Harness for GenAI Enterprise Knowledge Assistant.

Reads gold_qa.json, calls the /chat endpoint (or a mock), prints verbose
per-question evaluation logs, and computes:
- Hit-Rate@k (k=5,10)
- Mean Reciprocal Rank (MRR)
- Faithfulness (LLM-based)
- Refusal accuracy
"""

import asyncio
import argparse
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

import aiohttp
from openai import AsyncOpenAI

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# ---------- Data Models ----------
@dataclass
class GoldQuestion:
    question: str
    answer: str
    document_id: str
    section_path: str
    expected_response_type: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GoldQuestion":
        return cls(
            question=data["question"],
            answer=data.get("answer", ""),
            document_id=data.get("document_id", "Not in corpus"),
            section_path=data.get("section_path", ""),
            expected_response_type=data.get("expected_response_type", "factual"),
        )


@dataclass
class ChatResponse:
    answer: str
    refused: bool
    chunks: List[Dict[str, Any]]
    confidence: Optional[float] = None
    conflict: Optional[Dict] = None
    error: Optional[str] = None


@dataclass
class EvalResult:
    question: str
    expected_type: str
    expected_answer: str
    expected_doc: str
    expected_section: str
    actual_answer: str
    refused: bool
    retrieved_docs: List[str]
    retrieved_sections: List[str]
    hit_at_5: bool
    hit_at_10: bool
    reciprocal_rank: float
    faithfulness: Optional[bool] = None
    faithfulness_reason: Optional[str] = None
    error: Optional[str] = None


# ---------- Mock API ----------
class MockChatAPI:
    """Simulates the /chat endpoint for offline testing."""

    async def chat(self, question: str) -> ChatResponse:
        refusal_keywords = [
            "vacation", "remote work", "leave of absence", "dress code",
            "crypto", "pet", "trading", "losses", "bonus", "insurance"
        ]
        q_lower = question.lower()
        if any(kw in q_lower for kw in ["crypto", "pet", "not in corpus"]):
            return ChatResponse(
                answer="",
                refused=True,
                chunks=[],
                confidence=0.2
            )
        else:
            return ChatResponse(
                answer="Associates must follow standard leave request protocols.",
                refused=False,
                chunks=[
                    {
                        "document_id": "95ac8579-5a57-4c64-860c-31aa8a90115e",
                        "section_path": "Leaves of Absence.pdf",
                        "text": "Associates must apply for leaves according to guidelines."
                    }
                ],
                confidence=0.9
            )


# ---------- Real API Client ----------
class ChatAPIClient:
    def __init__(self, api_url: str, timeout: int = 90):
        self.api_url = api_url.rstrip("/")
        self.timeout = timeout
        self.token = None
        self.tenant_id = "e8ae3da0-adad-4d0f-9893-67470bcab06f"
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout))
        await self._authenticate()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def _authenticate(self):
        login_url = f"{self.api_url}/auth/login"
        payload = {
            "email": "admin@acme.com",
            "password": "Pass1234",
            "tenant_code": "Acme Corp"
        }
        try:
            async with self.session.post(login_url, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self.token = data.get("access_token")
                    self.tenant_id = data.get("tenant_id") or self.tenant_id
                    logger.info("Authenticated successfully with fresh token.")
        except Exception as e:
            logger.error(f"Authentication failed: {e}")

    async def chat(self, question: str) -> ChatResponse:
        if not self.token:
            await self._authenticate()

        headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
        payload = {"query": question, "tenant_id": self.tenant_id}

        for attempt in range(2):
            try:
                async with self.session.post(f"{self.api_url}/chat", json=payload, headers=headers) as resp:
                    if resp.status == 401 and attempt == 0:
                        await self._authenticate()
                        headers["Authorization"] = f"Bearer {self.token}"
                        continue

                    if resp.status != 200:
                        return ChatResponse(answer="", refused=True, chunks=[], error=f"HTTP {resp.status}")

                    content_type = resp.headers.get("Content-Type", "")
                    final_data = {}

                    if "text/event-stream" in content_type:
                        accumulated_tokens = []
                        async for line_bytes in resp.content:
                            line = line_bytes.decode("utf-8").strip()
                            if line.startswith("data:"):
                                raw_json = line[5:].strip()
                                if not raw_json:
                                    continue
                                try:
                                    evt = json.loads(raw_json)
                                    evt_type = evt.get("type")
                                    if evt_type == "token":
                                        accumulated_tokens.append(evt.get("content", ""))
                                    elif evt_type == "final":
                                        final_data = evt
                                        if not final_data.get("answer") and accumulated_tokens:
                                            final_data["answer"] = "".join(accumulated_tokens)
                                        break
                                except Exception:
                                    continue
                        data = final_data
                    else:
                        data = await resp.json()

                    answer = data.get("answer", "")
                    refused = data.get("refused", False)
                    chunks = data.get("citations", []) or data.get("chunks", [])

                    for chunk in chunks:
                        chunk.setdefault("document_id", "unknown")
                        chunk.setdefault("section_path", "unknown")

                    return ChatResponse(
                        answer=answer,
                        refused=refused,
                        chunks=chunks,
                        confidence=data.get("confidence"),
                        conflict=data.get("conflict")
                    )
            except Exception as e:
                if attempt == 1:
                    return ChatResponse(answer="", refused=True, chunks=[], error=str(e))


# ---------- Faithfulness Evaluator ----------
class FaithfulnessEvaluator:
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    async def evaluate(self, question: str, answer: str, chunks: List[Dict[str, Any]]) -> Tuple[bool, str]:
        if not answer or not chunks:
            return False, "No answer or no chunks to verify."

        context = "\n".join([chunk.get("text", "") or chunk.get("snippet", "") for chunk in chunks])
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
                reason = verdict if len(verdict) > 3 else "Unsupported"
                return False, reason
        except Exception as e:
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
        faithful_items = [r for r in group if r.expected_type == "factual" and not r.refused and r.faithfulness is not None]
        faithfulness_accuracy = sum(1 for r in faithful_items if r.faithfulness) / len(faithful_items) if faithful_items else 0.0
        if group and group[0].expected_type == "refusal":
            refusal_acc = sum(1 for r in group if r.refused) / n
        else:
            refusal_acc = sum(1 for r in group if not r.refused) / n
        return {
            "hit_at_5": hit5,
            "hit_at_10": hit10,
            "mrr": mrr,
            "faithfulness_accuracy": faithfulness_accuracy,
            "refusal_accuracy": refusal_acc,
            "count": n,
        }

    return {
        "overall": calc_for_group(results),
        "factual": calc_for_group(factual),
        "refusal": calc_for_group(refusal),
        "total_questions": total,
        "errors": sum(1 for r in results if r.error),
    }


async def evaluate_single(
    idx: int,
    total: int,
    question: GoldQuestion,
    chat_client,
    faithfulness_eval: Optional[FaithfulnessEvaluator] = None,
) -> EvalResult:
    try:
        resp = await chat_client.chat(question.question)
    except Exception as e:
        resp = ChatResponse(answer="", refused=True, chunks=[], error=str(e))

    retrieved_docs = [chunk.get("document_id", "unknown") for chunk in resp.chunks]
    retrieved_sections = [chunk.get("section_path", "unknown") for chunk in resp.chunks]

    expected_doc = question.document_id
    expected_section = question.section_path

    hit_at_5 = False
    hit_at_10 = False
    reciprocal_rank = 0.0

    if expected_doc != "Not in corpus":
        for pos, (doc, sec) in enumerate(zip(retrieved_docs, retrieved_sections), start=1):
            if (doc == expected_doc or expected_doc in doc) and (expected_section in sec or sec in expected_section):
                reciprocal_rank = 1.0 / pos
                if pos <= 5:
                    hit_at_5 = True
                if pos <= 10:
                    hit_at_10 = True
                break

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

    # Verbose logging per question
    print(f"\n[{idx}/{total}] Expected Type: {question.expected_response_type.upper()}")
    print(f"  QUESTION:         {question.question}")
    print(f"  EXPECTED ANSWER:  {question.answer if question.answer else '[REFUSAL / OUT OF CORPUS]'}")
    print(f"  GENERATED ANSWER: {resp.answer[:160]}..." if len(resp.answer) > 160 else f"  GENERATED ANSWER: {resp.answer if resp.answer else '[REFUSED]'}")
    print(f"  EXPECTED DOC:     {expected_doc}")
    print(f"  RETRIEVED DOCS:   {retrieved_docs[:3]}")
    print(f"  METRICS:          Hit@5: {hit_at_5} | MRR: {reciprocal_rank:.2f} | Refused: {resp.refused}")
    print("-" * 60)

    return EvalResult(
        question=question.question,
        expected_type=question.expected_response_type,
        expected_answer=question.answer,
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
    max_concurrent: int = 1,
) -> Dict[str, Any]:
    gold_questions = load_gold_questions(gold_file)
    total_q = len(gold_questions)
    logger.info(f"Loaded {total_q} gold questions.")

    if mock:
        mock_api = MockChatAPI()
        class MockWrapper:
            async def chat(self, question):
                return await mock_api.chat(question)
        chat_client = MockWrapper()
        client_cm = None
    else:
        if not api_url:
            raise ValueError("API URL must be provided when not in mock mode.")
        client_cm = ChatAPIClient(api_url)
        chat_client = await client_cm.__aenter__()

    try:
        faithfulness_eval = FaithfulnessEvaluator(api_key=openai_api_key) if openai_api_key else None
        semaphore = asyncio.Semaphore(max_concurrent)

        async def eval_with_semaphore(idx, q):
            async with semaphore:
                return await evaluate_single(idx, total_q, q, chat_client, faithfulness_eval)

        tasks = [eval_with_semaphore(i, q) for i, q in enumerate(gold_questions, start=1)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        valid_results = []
        for r in results:
            if isinstance(r, Exception):
                valid_results.append(EvalResult(
                    question="unknown",
                    expected_type="unknown",
                    expected_answer="",
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

        metrics = compute_metrics(valid_results)
        details = [
            {
                "question": r.question,
                "expected_type": r.expected_type,
                "expected_answer": r.expected_answer,
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
            }
            for r in valid_results
        ]

        return {
            "metrics": metrics,
            "details": details,
            "total_questions": len(gold_questions),
        }
    finally:
        if client_cm:
            await client_cm.__aexit__(None, None, None)


# ---------- Main ----------
async def main():
    parser = argparse.ArgumentParser(description="Evaluate RAG system with gold QA set.")
    parser.add_argument("--gold", required=True, help="Path to gold_qa.json")
    parser.add_argument("--api-url", help="Base URL of the /chat endpoint")
    parser.add_argument("--mock", action="store_true", help="Use mock API instead of real endpoint")
    parser.add_argument("--openai-key", help="OpenAI API key for faithfulness evaluation")
    parser.add_argument("--output", help="Output JSON file for detailed results", default="eval/results/results.json")
    parser.add_argument("--concurrency", type=int, default=1, help="Max concurrent requests")
    args = parser.parse_args()

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

    if not args.mock and not args.api_url:
        parser.error("Either --api-url or --mock must be provided.")

    openai_key = args.openai_key or os.environ.get("OPENAI_API_KEY")

    result = await run_evaluation(
        gold_file=args.gold,
        api_url=args.api_url,
        mock=args.mock,
        openai_api_key=openai_key,
        max_concurrent=args.concurrency,
    )

    metrics = result["metrics"]
    print("\n" + "=" * 60)
    print("EVALUATION SUMMARY")
    print("=" * 60)
    print(f"Total questions: {metrics['total_questions']}")
    print(f"Errors:          {metrics['errors']}")
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

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, default=str)
        logger.info(f"Detailed results saved to {args.output}")


if __name__ == "__main__":
    asyncio.run(main())