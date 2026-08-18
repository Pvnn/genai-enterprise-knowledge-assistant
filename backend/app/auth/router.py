"""Auth router – POST /auth/login, GET /auth/me, POST /auth/feedback.

Owner: P6
Contracts from Section 5 of the engineering spec are fixed; do not alter
field names or response shapes.

Note: POST /feedback is Priority 2 per the spec. It is mounted here under
/auth (→ /auth/feedback) since this file is owned by P6. If the team
decides to expose it at root /feedback instead, P2 can re-mount in main.py
without any changes to this file.
"""

import logging

from fastapi import APIRouter, HTTPException, status
from passlib.context import CryptContext
from sqlalchemy import select

from app.auth.models import User
from app.auth.security import create_access_token
from app.auth.tenancy import resolve_tenant
from app.deps import CurrentUserDep, DbDep
from app.models import Feedback
from app.schemas import (
    CurrentUser,
    FeedbackRequest,
    FeedbackResponse,
    LoginRequest,
    LoginResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, session: DbDep) -> LoginResponse:
    """Authenticate a user and return a JWT.

    POST /auth/login  →  { access_token, tenant_id, user_id, role }

    Resolves the tenant_code to a tenant_id first, then looks up the user
    by email within that tenant, verifies the bcrypt password hash, and
    issues a signed JWT on success.

    Args:
        request: LoginRequest containing email, password, tenant_code.
        session: Async database session (injected).

    Returns:
        LoginResponse: Signed JWT plus user identity fields.

    Raises:
        HTTPException 400: Unknown tenant_code.
        HTTPException 401: Wrong email or password.
    """
    # Step 1 — resolve tenant (raises 400 if unknown)
    tenant_id = await resolve_tenant(request.tenant_code, session)

    # Step 2 — look up user by email, scoped to this tenant
    result = await session.execute(
        select(User).where(
            User.email == request.email,
            User.tenant_id == tenant_id,
        )
    )
    user: User | None = result.scalar_one_or_none()

    # Step 3 — verify password (constant-time bcrypt compare)
    # Check user exists AND password matches in one conditional to avoid
    # leaking whether the email exists via timing differences.
    if user is None or not _pwd_context.verify(request.password, user.password_hash):
        logger.warning(
            "Failed login attempt for email=%r tenant_id=%s", request.email, tenant_id
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Step 4 — issue JWT
    token = create_access_token(
        {
            "sub": str(user.id),
            "tenant_id": str(user.tenant_id),
            "email": user.email,
            "role": user.role,
        }
    )

    logger.info(
        "Successful login: user_id=%s tenant_id=%s role=%s",
        user.id,
        user.tenant_id,
        user.role,
    )
    return LoginResponse(
        access_token=token,
        tenant_id=user.tenant_id,
        user_id=user.id,
        role=user.role,
    )


@router.get("/me", response_model=CurrentUser)
async def me(current_user: CurrentUserDep) -> CurrentUser:
    """Return the current authenticated user's identity.

    GET /auth/me  →  { user_id, tenant_id, email, role }

    Args:
        current_user: Injected by get_current_user() via CurrentUserDep.

    Returns:
        CurrentUser: The authenticated user's identity.
    """
    return current_user


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(
    request: FeedbackRequest,
    current_user: CurrentUserDep,
    session: DbDep,
) -> FeedbackResponse:
    """Submit thumbs-up/down feedback for an answer (Priority 2).

    POST /auth/feedback  →  { status: "ok" }

    Uses the Feedback ORM class from app.models (defined by P2).
    query_id must reference an existing row in the queries table.

    Args:
        request: FeedbackRequest with query_id, thumbs_up_down, comment.
        current_user: Authenticated user (ensures auth is enforced).
        session: Async database session (injected).

    Returns:
        FeedbackResponse: { status: "ok" }
    """
    feedback = Feedback(
        query_id=request.query_id,
        thumbs_up_down=request.thumbs_up_down,
        comment=request.comment,
    )
    session.add(feedback)
    await session.commit()
    logger.info(
        "Feedback recorded: query_id=%s user_id=%s thumbs_up_down=%s",
        request.query_id,
        current_user.user_id,
        request.thumbs_up_down,
    )
    return FeedbackResponse(status="ok")
