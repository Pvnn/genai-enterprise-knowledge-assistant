"""Tests for conflict_detector module.

Owner: P5
"""

import pytest
import uuid
from unittest.mock import AsyncMock, patch

from app.schemas import ChunkResult
from app.generation.conflict_detector import ConflictLLMResponse, check_conflict


@pytest.mark.asyncio
async def test_check_conflict_empty():
    res = await check_conflict([])
    assert res.conflict is False


@pytest.mark.asyncio
async def test_check_conflict_same_document():
    doc_id = uuid.uuid4()
    chunks = [
        ChunkResult(
            chunk_id=uuid.uuid4(),
            document_id=doc_id,
            text="Text 1",
            section_path="/sec1",
            score=0.9,
            version_status="current",
        ),
        ChunkResult(
            chunk_id=uuid.uuid4(),
            document_id=doc_id,
            text="Text 2",
            section_path="/sec2",
            score=0.8,
            version_status="current",
        ),
    ]
    res = await check_conflict(chunks)
    # Should be false because they are from the same document
    assert res.conflict is False


@pytest.mark.asyncio
@patch("app.generation.conflict_detector.AsyncOpenAI")
async def test_check_conflict_contradiction(mock_openai_class):
    mock_client = AsyncMock()
    mock_openai_class.return_value = mock_client
    
    mock_response = AsyncMock()
    mock_response.choices = [AsyncMock()]
    mock_response.choices[0].message.parsed = ConflictLLMResponse(has_contradiction=True)
    mock_client.beta.chat.completions.parse.return_value = mock_response

    doc_id1 = uuid.uuid4()
    doc_id2 = uuid.uuid4()
    chunks = [
        ChunkResult(
            chunk_id=uuid.uuid4(),
            document_id=doc_id1,
            text="Policy says 5 days",
            section_path="/sec1",
            score=0.9,
            version_status="current",
        ),
        ChunkResult(
            chunk_id=uuid.uuid4(),
            document_id=doc_id2,
            text="Policy says 10 days",
            section_path="/sec1",
            score=0.8,
            version_status="current",
        ),
    ]
    
    res = await check_conflict(chunks)
    assert res.conflict is True
    assert len(res.conflicting_chunks) == 2


@pytest.mark.asyncio
@patch("asyncio.sleep", new_callable=AsyncMock)
@patch("app.generation.conflict_detector.AsyncOpenAI")
async def test_check_conflict_retry_on_transient_error(mock_openai_class, mock_sleep):
    mock_client = AsyncMock()
    mock_openai_class.return_value = mock_client
    
    mock_response = AsyncMock()
    mock_response.choices = [AsyncMock()]
    mock_response.choices[0].message.parsed = ConflictLLMResponse(has_contradiction=True)
    
    # First call raises a transient exception, second call succeeds
    mock_client.beta.chat.completions.parse.side_effect = [
        TimeoutError("Transient network timeout"),
        mock_response,
    ]

    doc_id1 = uuid.uuid4()
    doc_id2 = uuid.uuid4()
    chunks = [
        ChunkResult(
            chunk_id=uuid.uuid4(),
            document_id=doc_id1,
            text="Policy says 5 days",
            section_path="/sec1",
            score=0.9,
            version_status="current",
        ),
        ChunkResult(
            chunk_id=uuid.uuid4(),
            document_id=doc_id2,
            text="Policy says 10 days",
            section_path="/sec1",
            score=0.8,
            version_status="current",
        ),
    ]
    
    res = await check_conflict(chunks)
    assert res.conflict is True
    assert len(res.conflicting_chunks) == 2
    assert mock_client.beta.chat.completions.parse.call_count == 2
    mock_sleep.assert_called_once_with(1)  # 2 ** 0 = 1s backoff


@pytest.mark.asyncio
@patch("asyncio.sleep", new_callable=AsyncMock)
@patch("app.generation.conflict_detector.AsyncOpenAI")
async def test_check_conflict_retries_exhausted_fallback(mock_openai_class, mock_sleep):
    mock_client = AsyncMock()
    mock_openai_class.return_value = mock_client
    
    # All attempts fail with transient error
    mock_client.beta.chat.completions.parse.side_effect = ConnectionError("Persistent connection error")

    doc_id1 = uuid.uuid4()
    doc_id2 = uuid.uuid4()
    chunks = [
        ChunkResult(
            chunk_id=uuid.uuid4(),
            document_id=doc_id1,
            text="Policy says 5 days",
            section_path="/sec1",
            score=0.9,
            version_status="current",
        ),
        ChunkResult(
            chunk_id=uuid.uuid4(),
            document_id=doc_id2,
            text="Policy says 10 days",
            section_path="/sec1",
            score=0.8,
            version_status="current",
        ),
    ]
    
    res = await check_conflict(chunks)
    assert res.conflict is False
    assert res.conflicting_chunks == []
    assert mock_client.beta.chat.completions.parse.call_count == 3


@pytest.mark.asyncio
@patch("asyncio.sleep", new_callable=AsyncMock)
@patch("app.generation.conflict_detector.AsyncOpenAI")
async def test_check_conflict_no_retry_on_permanent_error(mock_openai_class, mock_sleep):
    mock_client = AsyncMock()
    mock_openai_class.return_value = mock_client
    
    # Non-transient / permanent error (e.g. 401 Authentication or 400 Bad Request)
    mock_client.beta.chat.completions.parse.side_effect = ValueError("Invalid authentication key")

    doc_id1 = uuid.uuid4()
    doc_id2 = uuid.uuid4()
    chunks = [
        ChunkResult(
            chunk_id=uuid.uuid4(),
            document_id=doc_id1,
            text="Policy says 5 days",
            section_path="/sec1",
            score=0.9,
            version_status="current",
        ),
        ChunkResult(
            chunk_id=uuid.uuid4(),
            document_id=doc_id2,
            text="Policy says 10 days",
            section_path="/sec1",
            score=0.8,
            version_status="current",
        ),
    ]
    
    res = await check_conflict(chunks)
    assert res.conflict is False
    assert res.conflicting_chunks == []
    # Should abort immediately on permanent error without retrying
    assert mock_client.beta.chat.completions.parse.call_count == 1
    mock_sleep.assert_not_called()


