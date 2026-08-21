"""Eval – Gold Q&A set loader.

Owner: P8  |  Priority: 1
Loads the gold_qa.json file (30-50 curated question-answer pairs) for use
by the evaluation harness.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

GOLD_QA_PATH = Path(__file__).parent.parent.parent.parent / "eval" / "gold_qa.json"


def load_gold_set() -> list[dict]:
    """Load the gold Q&A set from eval/gold_qa.json.

    Returns:
        list[dict]: List of QA pairs, each with keys: question, answer,
                    document_id, section_path, tenant_id.
    """
    with GOLD_QA_PATH.open("r", encoding="utf-8-sig") as f:
        return json.load(f)
