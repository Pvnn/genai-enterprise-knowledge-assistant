"""JWT creation, validation, and get_current_user dependency.

Owner: P6  |  Priority: 1
get_current_user() is imported once into P2's deps.py; all other code uses
it from there. The public spec contract (Section 6) is:

    get_current_user(token) -> CurrentUser

FastAPI's dependency injection adds the DB session internally via
Depends(get_db) — it does not appear in the caller-visible signature.
"""

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.config import get_settings
from app.database import get_db
from app.schemas import CurrentUser

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# Module-level constant — avoids constructing a new HTTPException on every
# failed request and deliberately keeps the error message generic so callers
# cannot distinguish between expired, malformed, or deleted-user failures.
_CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def create_access_token(data: dict) -> str:
    """Create a signed JWT from a payload dict.

    Adds an 'exp' claim automatically using
    Settings.access_token_expire_minutes. Called by auth/router.py
    immediately after a successful login check.

    Args:
        data: Payload key/value pairs to encode. Must contain at minimum:
              'sub'       – str(user.id)
              'tenant_id' – str(user.tenant_id)
              'email'     – user.email
              'role'      – user.role

    Returns:
        str: Signed JWT string ready to return to the client as
             LoginResponse.access_token.
    """
    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    to_encode["exp"] = expire
    token: str = jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return token


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_db),
) -> CurrentUser:
    """Validate a JWT and return the authenticated user.

    This is the dependency that gates every protected endpoint via
    CurrentUserDep in deps.py. FastAPI injects both parameters
    automatically — callers never pass them explicitly.

    Steps:
      1. Decode and verify JWT signature + expiry (python-jose handles expiry).
      2. Extract 'sub' (user_id UUID string) from the payload.
      3. Load the User row from the DB to confirm the account still exists.
      4. Return a CurrentUser Pydantic model (never a raw dict).

    Args:
        token: Bearer token extracted from the Authorization header by
               OAuth2PasswordBearer. Not passed by callers directly.
        session: Async DB session injected by get_db. Not passed by
                 callers directly.

    Returns:
        CurrentUser: Typed identity model with user_id, tenant_id,
                     email, and role — ready for use in any route handler.

    Raises:
        HTTPException: 401 with detail "Could not validate credentials"
                       if the token is missing, malformed, expired, or
                       the user_id in the token no longer exists in the DB.
    """
    settings = get_settings()

    # Step 1 — decode and verify JWT (jose raises JWTError on any problem
    # including expiry, bad signature, malformed structure)
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError:
        logger.debug("JWT decode failed", exc_info=True)
        raise _CREDENTIALS_EXCEPTION

    # Step 2 — extract user_id from 'sub' claim
    user_id_str: str | None = payload.get("sub")
    if user_id_str is None:
        logger.warning("JWT missing 'sub' claim")
        raise _CREDENTIALS_EXCEPTION

    try:
        user_uuid = UUID(user_id_str)
    except ValueError:
        logger.warning("JWT 'sub' is not a valid UUID: %r", user_id_str)
        raise _CREDENTIALS_EXCEPTION

    # Step 3 — confirm user still exists in the DB
    # (catches deleted/suspended accounts whose tokens haven't expired yet)
    result = await session.execute(select(User).where(User.id == user_uuid))
    user: User | None = result.scalar_one_or_none()
    if user is None:
        logger.warning("JWT references unknown user_id=%s", user_uuid)
        raise _CREDENTIALS_EXCEPTION

    # Step 4 — return typed Pydantic model (never a raw dict — Section 10)
    return CurrentUser(
        user_id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        role=user.role,
    )
