"""JWT creation, validation, and get_current_user dependency.

Owner: P6  |  Priority: 1
get_current_user() is imported once into P2 s deps.py; all other code uses
it from there.
"""

import logging
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.schemas import CurrentUser

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
) -> CurrentUser:
    """Validate a JWT and return the authenticated user.

    Args:
        token: Bearer token from the Authorization header.

    Returns:
        CurrentUser: Parsed user identity including tenant_id.

    Raises:
        HTTPException: 401 if token is missing, invalid, or expired.
    """
    raise NotImplementedError("P6: implement get_current_user() in security.py")
