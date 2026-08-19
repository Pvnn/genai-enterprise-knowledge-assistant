"""Eval – Failure-by-stage attribution report.

Owner: P8  |  Priority: 2
Generates stage-level attribution analysis:
  - Routing failures (Stage 2)
  - Retrieval failures (Stage 3)
  - Generation / Faithfulness failures (Stage 5)
"""

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def generate_report(per_question_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate a failure-by-stage attribution summary.

    Args:
        per_question_results: Per-question evaluation output list.

    Returns:
        dict: Stage-level error breakdown and ablation summary table.
    """
    total = len(per_question_results)
    if total == 0:
        return {
            "total_queries": 0,
            "stage_failures": {"routing": 0, "retrieval": 0, "generation": 0},
            "success_rate": 1.0,
        }

    routing_failures = 0
    retrieval_failures = 0
    generation_failures = 0
    successful = 0

    for r in per_question_results:
        expected_type = r.get("expected_type", "factual")
        refused = r.get("refused", False)
        hit_at_k = r.get("hit_at_k", False)
        faithfulness = r.get("faithfulness", True)
        routed_correctly = r.get("routed_correctly", True)

        if expected_type == "refusal":
            if not refused:
                # Generation/Grounding failed to refuse an unanswerable query
                generation_failures += 1
            else:
                successful += 1
        else:
            # Factual query attribution breakdown
            if not routed_correctly:
                routing_failures += 1
            elif not hit_at_k:
                retrieval_failures += 1
            elif refused or faithfulness is False:
                generation_failures += 1
            else:
                successful += 1

    total_failures = routing_failures + retrieval_failures + generation_failures
    success_rate = (total - total_failures) / total if total > 0 else 0.0

    report = {
        "total_evaluated": total,
        "successful_queries": successful,
        "total_failures": total_failures,
        "success_rate": round(success_rate, 4),
        "stage_breakdown": {
            "routing_failures_stage2": routing_failures,
            "retrieval_failures_stage3": retrieval_failures,
            "generation_failures_stage5": generation_failures,
        },
        "ablation_summary": {
            "routing_accuracy": round((total - routing_failures) / total, 4),
            "retrieval_accuracy": round((total - retrieval_failures) / total, 4),
            "generation_accuracy": round((total - generation_failures) / total, 4),
        },
    }

    logger.info("Failure-by-stage attribution report generated: %s", report)
    return report