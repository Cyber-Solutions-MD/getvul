"""Shared FastAPI dependencies used across routers."""

from typing import Annotated

from fastapi import Depends

from app.auth.dependencies import get_current_user
from app.auth.schemas import CurrentUser
from app.db.session import AsyncSession, get_db

# Type aliases for cleaner route signatures
DBSession = Annotated[AsyncSession, Depends(get_db)]
AuthenticatedUser = Annotated[CurrentUser, Depends(get_current_user)]
