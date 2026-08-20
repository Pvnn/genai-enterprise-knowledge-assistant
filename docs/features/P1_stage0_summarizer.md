# Stage 0: Summarizer

**Priority:** 2
**Owner:** P1

## Overview
The Summarizer is executed per document during the ingestion pipeline. It generates a concise summary (<=200 words) of the document's content, which is stored in `documents.summary`. This is utilized by Stage 2a routing to narrow the candidate document set.

## Implementation Details
The summarizer leverages the LLM via OpenAI's structured outputs (`responses.parse`). The logic resides in `backend/app/ingestion/summarizer.py`.

### Structured Output Generation
To guarantee a machine-readable string, the prompt strictly requests the core purpose and key rules without introductory fluff. We enforce this constraint by using a Pydantic schema:

```python
class SummaryResponse(BaseModel):
    summary: str = Field(description="A concise summary of the document, up to 200 words. Extract the core purpose and key rules of the provided document. Do not include introductory fluff.")
```

The request is sent using `_client.responses.parse(..., text_format=SummaryResponse)`. The returned validated object ensures we only capture the pure summary string.

## Fallback Behavior
In accordance with the fallback requirements, if the API key is missing, or the API call times out/fails (e.g., due to rate limits or API outage), the exception is logged and caught smoothly in `run_ingestion.py`. The `documents.summary` field is left `NULL`, and Stage 2a falls back to metadata-only filtering without crashing the ingestion pipeline.
