"""Eval – Evaluation harness.

Owner: P8  |  Priority: 1
Scores the system against the gold set on:
  - Retrieval hit-rate@k
  - Answer faithfulness
  - Hallucination rate
"""

import logging

logger = logging.getLogger(__name__)


async def run_eval(gold_set: list[dict], top_k: int = 5) -> dict:
    """Run the evaluation harness against the live system.

    Args:
        gold_set: Gold Q&A pairs from gold_set.load_gold_set().
        top_k: k value for hit-rate@k metric.

    Returns:
        dict: Metrics dict with keys: hit_rate_at_k, faithfulness, hallucination_rate.
    """
    raise NotImplementedError("P8: implement run_eval() in harness.py")
