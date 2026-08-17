"""Tests for conflict_detector module.

Owner: P5
"""

import pytest
import uuid
from unittest.mock import AsyncMock, patch

from app.schemas import ChunkResult
from app.generation.conflict_detector import check_conflict


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
    mock_response.choices[0].message.content = "YES"
    mock_client.chat.completions.create.return_value = mock_response

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
