"""Tests for grounding module.

Owner: P5
Import shared fixtures from conftest.py (owned by P2).  Do NOT define
new fixture setups that duplicate what conftest.py already provides.
"""

import pytest
import uuid
from unittest.mock import AsyncMock, patch

from app.schemas import ChunkResult
from app.generation.grounding import (
    ConfidenceLLMResponse,
    ConfidenceLevel,
    decide_refusal,
)


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
    mock_response.choices[0].message.parsed = ConfidenceLLMResponse(confidence=ConfidenceLevel.high)
    mock_client.beta.chat.completions.parse.return_value = mock_response

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


@pytest.mark.asyncio
@patch("app.generation.grounding.AsyncOpenAI")
async def test_decide_refusal_low_confidence_model_reason(mock_openai_class):
    mock_client = AsyncMock()
    mock_openai_class.return_value = mock_client
    
    custom_reason = "The passages do not mention holiday rollover rules. Please check with HR."
    mock_response = AsyncMock()
    mock_response.choices = [AsyncMock()]
    mock_response.choices[0].message.parsed = ConfidenceLLMResponse(
        confidence=ConfidenceLevel.low,
        refusal_reason=custom_reason,
    )
    mock_client.beta.chat.completions.parse.return_value = mock_response

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
    assert res.refused is True
    assert res.confidence == 0.0
    assert res.reason == custom_reason


@pytest.mark.asyncio
@patch("asyncio.sleep", new_callable=AsyncMock)
@patch("app.generation.grounding.AsyncOpenAI")
async def test_decide_refusal_transient_error_retry(mock_openai_class, mock_sleep):
    mock_client = AsyncMock()
    mock_openai_class.return_value = mock_client
    
    mock_response = AsyncMock()
    mock_response.choices = [AsyncMock()]
    mock_response.choices[0].message.parsed = ConfidenceLLMResponse(confidence=ConfidenceLevel.high)
    
    # 1st call fails with timeout (transient), 2nd call succeeds
    mock_client.beta.chat.completions.parse.side_effect = [
        TimeoutError("Connection timed out"),
        mock_response,
    ]

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
    assert mock_client.beta.chat.completions.parse.call_count == 2
    mock_sleep.assert_called_once_with(1)


@pytest.mark.asyncio
@patch("asyncio.sleep", new_callable=AsyncMock)
@patch("app.generation.grounding.AsyncOpenAI")
async def test_decide_refusal_permanent_error_no_retry(mock_openai_class, mock_sleep):
    mock_client = AsyncMock()
    mock_openai_class.return_value = mock_client
    
    # Non-transient error (e.g. invalid credentials)
    mock_client.beta.chat.completions.parse.side_effect = ValueError("Invalid API credentials")

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
    # On permanent failure, defaults to medium confidence rather than crashing
    assert res.refused is False
    assert res.confidence == 0.5
    # Should abort immediately on permanent error without retrying
    assert mock_client.beta.chat.completions.parse.call_count == 1
    mock_sleep.assert_not_called()


