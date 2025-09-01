"""Users service: user and session initialization and experiment assignment."""

import hashlib
import uuid
from typing import Any, Dict, List

from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select

from db.models import Session, User


class UsersService:
    """Handles user lifecycle and session issuance (no analytics coupling)."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def initialize_user(self, *, browser_info: Dict[str, Any], timezone: str, locale: str) -> User:
        """Create a user, assign experiment groups, and persist."""
        user = User(browser_info=browser_info, timezone=timezone, locale=locale)
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)

        # Assign experiments deterministically based on UUID
        user.experiment_groups = self._assign_experiment_groups(user.id)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def initialize_session(self, *, user_id: str) -> str:
        """Return a new server-generated session id (UUID string)."""
        # Best-effort validation that the user exists; do not block session issuance
        try:
            result = await self.db.execute(select(User).where(User.id == uuid.UUID(str(user_id))))
            _ = result.scalar_one_or_none()
        except Exception:
            pass

        # Create a new session row tied to the user
        try:
            session_row = Session(
                user_id=uuid.UUID(str(user_id)),
                user_agent=None,
                page_url=None,
                referrer=None,
                client_timezone=None,
                client_locale=None,
            )
            self.db.add(session_row)
            await self.db.commit()
            await self.db.refresh(session_row)
            return str(session_row.id)
        except Exception:
            await self.db.rollback()
            # Fall back to ephemeral session id if DB write fails
            return str(uuid.uuid4())

    def _assign_experiment_groups(self, user_id: Any) -> List[str]:
        """Assign A/B test groups using a stable hash of the user id."""
        if isinstance(user_id, str):
            data = user_id.encode("utf-8")
        elif isinstance(user_id, uuid.UUID):
            data = user_id.bytes
        else:
            data = str(user_id).encode("utf-8")

        user_hash = int(hashlib.md5(data).hexdigest(), 16)
        groups: List[str] = []
        groups.append("detailed_metrics" if user_hash % 2 == 0 else "basic_metrics")
        if user_hash % 5 == 0:
            groups.append("experimental_features")
        return groups
