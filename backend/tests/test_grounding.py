"""Tests for grounding module.

Owner: P5
Import shared fixtures from conftest.py (owned by P2).  Do NOT define
new fixture setups that duplicate what conftest.py already provides.
"""

import pytest
import uuid
from unittest.mock import AsyncMock, patch

from app.schemas import ChunkResult
from app.generation.grounding import decide_refusal


@pytest.mark.asyncio
async def test_decide_refusal_empty_chunks():
    res = await decide_refusal("query", [], "draft")
    assert res.refused is True
    assert res.confidence == 0.0
    assert "couldn't find a passage" in res.reason


@pytest.mark.asyncio
async def test_decide_refusal_low_score():
    chunks = [
        ChunkResult(
            chunk_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            text="Text 1",
            section_path="/sec1",
            score=0.5, # Below 0.72 threshold
        )
    ]
    res = await decide_refusal("query", chunks, "draft")
    assert res.refused is True
    assert res.confidence == 0.0
    assert "couldn't find a passage" in res.reason


@pytest.mark.asyncio
@patch("app.generation.grounding.AsyncOpenAI")
async def test_decide_refusal_high_confidence(mock_openai_class):
    mock_client = AsyncMock()
    mock_openai_class.return_value = mock_client
    
    mock_response = AsyncMock()
    mock_response.choices = [AsyncMock()]
    mock_response.choices[0].message.content = "HIGH"
    mock_client.chat.completions.create.return_value = mock_response

    chunks = [
        ChunkResult(
            chunk_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            text="Text 1",
            section_path="/sec1",
            score=0.9,
        )
    ]
    
    res = await decide_refusal("query", chunks, "draft")
    assert res.refused is False
    assert res.confidence == 1.0
    assert res.reason is None
