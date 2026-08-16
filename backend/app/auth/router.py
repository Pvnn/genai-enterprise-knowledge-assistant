"""Auth router – POST /auth/login, GET /auth/me, POST /feedback.

Owner: P6
Contracts from Section 5 of the engineering spec are fixed; do not alter
field names or response shapes.
"""

import logging

from fastapi import APIRouter

from app.schemas import (
    CurrentUser,
    FeedbackRequest,
    FeedbackResponse,
    LoginRequest,
    LoginResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest) -> LoginResponse:
    """Authenticate a user and return a JWT.

    POST /auth/login  →  { access_token, tenant_id, user_id, role }
    """
    raise NotImplementedError("P6: implement /auth/login in auth/router.py")


@router.get("/me", response_model=CurrentUser)
async def me() -> CurrentUser:
    """Return the current authenticated user s identity.

    GET /auth/me  →  { user_id, tenant_id, email, role }
    """
    raise NotImplementedError("P6: implement /auth/me in auth/router.py")


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(request: FeedbackRequest) -> FeedbackResponse:
    """Submit thumbs-up/down feedback for an answer (Priority 2).

    POST /feedback  →  { status: "ok" }
    """
    raise NotImplementedError("P6: implement /feedback in auth/router.py")
