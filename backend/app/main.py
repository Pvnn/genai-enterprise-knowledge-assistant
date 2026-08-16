"""FastAPI application entry-point.

Owner: P2
Wires all routers together, configures CORS, and sets up global exception
handling so every unhandled error returns the shared { error, detail }
envelope defined in Section 5.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.schemas import ErrorResponse

# ── Routers (each owned by their respective person) ───────────────────────────
from app.auth.router import router as auth_router          # P6
from app.retrieval.router import router as retrieval_router  # P2
from app.generation.router import router as generation_router  # P4
from app.ingestion.router import router as ingestion_router  # P1

logger = logging.getLogger(__name__)
settings = get_settings()

logging.basicConfig(level=settings.log_level)

app = FastAPI(
    title="GenAI Enterprise Knowledge Assistant",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.vite_api_base_url, "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Global exception handler ──────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return the shared error envelope for any unhandled exception."""
    logger.exception("Unhandled exception on %s", request.url)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="internal_server_error",
            detail=str(exc),
        ).model_dump(),
    )


# ── Router registration ───────────────────────────────────────────────────────
app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(retrieval_router, tags=["retrieval"])
app.include_router(generation_router, tags=["generation"])
app.include_router(ingestion_router, tags=["ingestion"])


@app.get("/health", tags=["health"])
async def health_check() -> dict:
    """Liveness probe."""
    return {"status": "ok"}
