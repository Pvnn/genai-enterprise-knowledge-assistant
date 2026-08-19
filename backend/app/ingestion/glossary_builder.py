"""Stage 0, Priority 2 – Acronym / entity glossary builder.

Owner: P1  |  Priority: 2
Auto-builds a corpus-wide acronym/entity glossary and stores it in the
glossary table.  Used by Stage 1 query rewriting (P4) for acronym expansion.
Fallback: if this module is unavailable, acronym expansion is skipped.
"""

import json
import logging
from openai import AsyncOpenAI
from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()
_client = AsyncOpenAI(api_key=settings.openai_api_key)

async def build_glossary(tenant_id: str, chunks: list[dict]) -> list[dict]:
    """Build or update the acronym/entity glossary from ingested chunks.

    Args:
        tenant_id: The tenant whose corpus is being indexed.
        chunks: List of chunk dicts (must include text field).

    Returns:
        list[dict]: List of glossary entries, each with keys:
            - term (str): The acronym or entity.
            - expansion (str): The expanded form.
    """
    if not settings.openai_api_key:
        logger.warning("No OpenAI API key provided. Skipping glossary builder.")
        raise ValueError("Missing OpenAI API key")

    # Combine a sample of text to fit within context limits
    combined_text = "\n\n".join([c.get("text", "") for c in chunks])
    combined_text = combined_text[:100000]  # Truncate to avoid context limits

    prompt = (
        "Extract all unique acronyms and their full expansions from the following text.\n"
        "Return the result ONLY as a valid JSON list of objects, with each object having exactly two string keys: 'term' and 'expansion'.\n"
        "If no acronyms are found, return an empty JSON list [].\n"
        "Do not include any markdown formatting like ```json ... ```, just output the raw JSON array.\n\n"
        f"Text:\n{combined_text}"
    )

    messages = [
        {"role": "system", "content": "You are a helpful assistant that extracts acronyms and entities into strict JSON format."},
        {"role": "user", "content": prompt},
    ]

    response = await _client.chat.completions.create(
        model=settings.llm_model,
        messages=messages,
        temperature=0.1,
    )

    content = response.choices[0].message.content or "[]"
    
    # Clean up common LLM markdown formatting around JSON
    if content.startswith("```json"):
        content = content[7:]
    if content.endswith("```"):
        content = content[:-3]
    content = content.strip()

    try:
        glossary_entries = json.loads(content)
        if not isinstance(glossary_entries, list):
            return []
        
        # Validate format
        valid_entries = []
        for entry in glossary_entries:
            if isinstance(entry, dict) and "term" in entry and "expansion" in entry:
                valid_entries.append({
                    "term": str(entry["term"]).strip(),
                    "expansion": str(entry["expansion"]).strip()
                })
        return valid_entries
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse glossary JSON: {e}")
        return []
