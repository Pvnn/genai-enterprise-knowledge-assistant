"""Eval – CLI entry-point for running the evaluation harness.

Owner: P8
"""

import asyncio
import logging
import sys

from app.eval.gold_set import load_gold_set
from app.eval.harness import run_eval
from app.eval.report import generate_report

logger = logging.getLogger(__name__)

logging.basicConfig(level="INFO")


async def main() -> None:
    gold_set = load_gold_set()
    results = await run_eval(gold_set)
    report = generate_report(results.get("per_question", []))
    print(report)


if __name__ == "__main__":
    asyncio.run(main())
