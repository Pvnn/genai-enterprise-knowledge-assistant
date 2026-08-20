"""Eval – Failure-by-stage attribution report.

Owner: P8  |  Priority: 2
Generates stage-level attribution analysis:
  - Routing failures (Stage 2)
  - Retrieval failures (Stage 3)
  - Generation / Faithfulness failures (Stage 5)
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def generate_report(per_question_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate a failure-by-stage attribution summary."""
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
                generation_failures += 1
            else:
                successful += 1
        else:
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


def save_markdown_report(report: Dict[str, Any], output_path: Path):
    """Write report to a clean Markdown artifact."""
    md_content = f"""# Failure-by-Stage Attribution Report (Priority 2)

| Metric | Value |
| :--- | :--- |
| **Total Evaluated** | {report['total_evaluated']} |
| **Successful Queries** | {report['successful_queries']} |
| **Total Failures** | {report['total_failures']} |
| **Overall Success Rate** | **{report['success_rate'] * 100:.2f}%** |

---

## 1. Stage-Level Error Breakdown

| Pipeline Stage | Failures | Error Description |
| :--- | :---: | :--- |
| **Stage 2 (Metadata Routing)** | {report['stage_breakdown']['routing_failures_stage2']} | Incorrect department/document_type routing |
| **Stage 3 (Dense & BM25 Retrieval)** | {report['stage_breakdown']['retrieval_failures_stage3']} | Target passage not present in top-k chunks |
| **Stage 5 (Grounded Generation)** | {report['stage_breakdown']['generation_failures_stage5']} | Unfaithful answer or uncalibrated refusal |

---

## 2. Stage Ablation Summary

| Component | Ablation Accuracy |
| :--- | :---: |
| **Routing Accuracy** | {report['ablation_summary']['routing_accuracy'] * 100:.2f}% |
| **Retrieval Accuracy** | {report['ablation_summary']['retrieval_accuracy'] * 100:.2f}% |
| **Generation Accuracy** | {report['ablation_summary']['generation_accuracy'] * 100:.2f}% |
"""
    output_path.write_text(md_content, encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate failure-by-stage attribution report.")
    parser.add_argument("--results", required=True, help="Path to results.json from harness.py")
    parser.add_argument("--md", help="Path to save markdown report", default="eval/results/attribution_report.md")
    args = parser.parse_args()

    results_file = Path(args.results)
    if not results_file.exists():
        print(f"Error: File not found: {results_file}", file=sys.stderr)
        sys.exit(1)

    with open(results_file, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    details = raw_data.get("details", raw_data if isinstance(raw_data, list) else [])

    for item in details:
        if "hit_at_k" not in item:
            item["hit_at_k"] = item.get("hit_at_5", False) or item.get("hit_at_10", False)

    report = generate_report(details)

    print("\n" + "=" * 60)
    print("STAGE-BY-STAGE FAILURE ATTRIBUTION REPORT (PRIORITY 2)")
    print("=" * 60)
    print(f"Total Evaluated:       {report['total_evaluated']}")
    print(f"Successful Queries:    {report['successful_queries']}")
    print(f"Total Failures:        {report['total_failures']}")
    print(f"Overall Success Rate:  {report['success_rate'] * 100:.2f}%\n")
    print("Stage Failure Breakdown:")
    print(f"  • Stage 2 (Routing):    {report['stage_breakdown']['routing_failures_stage2']}")
    print(f"  • Stage 3 (Retrieval):  {report['stage_breakdown']['retrieval_failures_stage3']}")
    print(f"  • Stage 5 (Generation): {report['stage_breakdown']['generation_failures_stage5']}\n")
    print("Stage Ablation Accuracy:")
    print(f"  • Routing Accuracy:     {report['ablation_summary']['routing_accuracy'] * 100:.2f}%")
    print(f"  • Retrieval Accuracy:   {report['ablation_summary']['retrieval_accuracy'] * 100:.2f}%")
    print(f"  • Generation Accuracy:  {report['ablation_summary']['generation_accuracy'] * 100:.2f}%")
    print("=" * 60)

    if args.md:
        md_path = Path(args.md)
        md_path.parent.mkdir(parents=True, exist_ok=True)
        save_markdown_report(report, md_path)
        print(f"\nMarkdown report generated at: {md_path}")