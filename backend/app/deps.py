"""Shared FastAPI dependencies.

Owner: P2
Provides get_db and get_current_user as injectable dependencies.
get_current_user delegates to auth.security which is owned by P6.
"""

import logging
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db  # noqa: F401 – re-exported for convenience
from app.schemas import CurrentUser

logger = logging.getLogger(__name__)

# P6 provides this; imported here so the rest of the app only needs to
# import from app.deps, not directly from app.auth.security.
from app.auth.security import get_current_user  # noqa: E402

DbDep = Annotated[AsyncSession, Depends(get_db)]
CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]
