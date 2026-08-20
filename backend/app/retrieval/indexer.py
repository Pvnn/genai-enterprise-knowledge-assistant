"""Stage 0 – Batch embedding and pgvector storage.

Owner: P3  |  Priority: 1
Reads un-embedded chunks from the DB, calls embed_batch(), and writes the
vectors back to chunks.embedding as a JSON-serialised list of floats (stored
in the Text column; P2 owns the Alembic migration that converts it to
vector(768) on production Neon).

Designed to run as an offline job after loader.py has populated the chunks
table.  Safe to re-run: chunks whose embedding column is already populated
are skipped (idempotent).

Batch size is configured via Settings.embed_batch_size (default: 256).
Batches are processed sequentially to keep memory use predictable;
increase embed_batch_size for higher throughput if the API quota allows.
"""

from __future__ import annotations

import json
import logging
from uuid import UUID

# FIX (issue 3): 'text' promoted to a top-level import alongside the other
# sqlalchemy names.  The original deferred import inside the function body was
# inconsistent — 'select' and 'update' were already imported at the top of the
# file, proving the circular-import concern cited in the comment did not
# actually apply here.
#
# FIX (issue 1): 'select' and 'update' removed — neither was used anywhere in
# this module.  The code switched to raw text() queries at some point but the
# dead imports were never cleaned up.
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.retrieval.embeddings import EmbeddingError, embed_batch

logger = logging.getLogger(__name__)

# Default maximum number of chunks sent to the embedding API in a single call.
EMBED_BATCH_SIZE: int = 256


# ── Typed exception ───────────────────────────────────────────────────────────


class IndexerError(Exception):
    """Raised when the indexer encounters an unrecoverable error.

    Wraps the underlying exception so callers receive a typed error from this
    module rather than a raw database or embedding exception.
    """


# ── Public API ────────────────────────────────────────────────────────────────


async def index_chunks(session: AsyncSession, tenant_id: str) -> int:
    """Embed all unindexed chunks for a tenant and write vectors to the DB.

    A chunk is considered *unindexed* when its ``embedding`` column is NULL.
    This function is idempotent: running it twice on the same tenant is safe
    and will only process chunks that are still missing embeddings.

    Args:
        session: Async database session.  The caller owns commit/rollback.
        tenant_id: UUID string of the tenant whose chunks should be indexed.

    Returns:
        int: Total number of chunks successfully indexed in this call.

    Raises:
        IndexerError: If a database query fails, the tenant_id is invalid, or
            embed_batch() returns a different number of vectors than texts sent
            (which would otherwise cause silent data loss via zip() truncation).
        EmbeddingError: Propagated from embed_batch() if the embeddings API
            fails after retries; partial progress is *not* rolled back —
            successfully embedded batches are committed individually so the
            job can be resumed.
    """
    try:
        tenant_uuid = UUID(tenant_id)
    except ValueError as exc:
        raise IndexerError(f"Invalid tenant_id '{tenant_id}': {exc}") from exc

    settings = get_settings()
    batch_size = getattr(settings, "embed_batch_size", EMBED_BATCH_SIZE)

    logger.info("Starting indexing for tenant_id=%s", tenant_id)

    # Fetch IDs + text of all un-embedded chunks for this tenant.
    try:
        result = await session.execute(
            text(
                "SELECT id, text FROM chunks "
                "WHERE tenant_id = :tenant_id AND embedding IS NULL"
            ),
            {"tenant_id": str(tenant_uuid)},
        )
        rows = result.fetchall()
    except Exception as exc:
        raise IndexerError(
            f"Failed to fetch unindexed chunks for tenant {tenant_id}: {exc}"
        ) from exc

    if not rows:
        logger.info("No unindexed chunks found for tenant_id=%s", tenant_id)
        return 0

    logger.info(
        "Found %d unindexed chunk(s) for tenant_id=%s; batch_size=%d",
        len(rows),
        tenant_id,
        batch_size,
    )

    total_indexed = 0

    # Process in batches.
    for batch_start in range(0, len(rows), batch_size):
        batch = rows[batch_start : batch_start + batch_size]
        batch_ids = [str(row[0]) for row in batch]
        batch_texts = [row[1] for row in batch]

        logger.debug(
            "Embedding batch %d/%d (size=%d)",
            batch_start // batch_size + 1,
            (len(rows) + batch_size - 1) // batch_size,
            len(batch),
        )

        # EmbeddingError propagates to the caller as-is per the contract above.
        vectors: list[list[float]] = await embed_batch(batch_texts)

        # FIX (issue 2): guard against embed_batch() returning a different
        # number of vectors than texts.  embed_batch() validates this itself,
        # but a defensive check here prevents silent data loss in the unlikely
        # event that a future provider implementation slips through without
        # raising.  Without this check, zip() would silently truncate to the
        # shorter side, leaving some chunks un-indexed while total_indexed
        # over-counted them as successfully written.
        if len(vectors) != len(batch):
            raise IndexerError(
                f"embed_batch() returned {len(vectors)} vector(s) for {len(batch)} "
                f"text(s) in batch starting at index {batch_start} "
                f"(tenant={tenant_id}); aborting to prevent partial writes"
            )

        # Write embeddings back to the DB for this batch.
        try:
            for chunk_id, vector in zip(batch_ids, vectors):
                await session.execute(
                    text(
                        "UPDATE chunks SET embedding = :embedding WHERE id = :chunk_id"
                    ),
                    {
                        "embedding": json.dumps(vector),
                        "chunk_id": chunk_id,
                    },
                )
            await session.commit()
        except Exception as exc:
            await session.rollback()
            raise IndexerError(
                f"Failed to write embeddings for batch starting at index "
                f"{batch_start} (tenant={tenant_id}): {exc}"
            ) from exc

        total_indexed += len(batch)
        logger.info(
            "Indexed %d/%d chunks for tenant_id=%s",
            total_indexed,
            len(rows),
            tenant_id,
        )

    logger.info(
        "Indexing complete: %d chunk(s) embedded for tenant_id=%s",
        total_indexed,
        tenant_id,
    )
    return total_indexed