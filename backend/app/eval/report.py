"""Eval – Failure-by-stage attribution report (Priority 2).

Owner: P8  |  Priority: 2
Analyses eval results to attribute failures to specific pipeline stages:
routing, retrieval, or generation.
"""

import logging

logger = logging.getLogger(__name__)


def generate_report(eval_results: list[dict]) -> dict:
    """Generate a failure-attribution report from eval run results.

    Args:
        eval_results: Per-question result dicts from the harness.

    Returns:
        dict: Stage-level failure counts and rates.
    """
    raise NotImplementedError("P8: implement generate_report() in report.py")
