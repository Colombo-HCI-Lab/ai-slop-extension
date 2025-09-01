"""Users service: user and session initialization and experiment assignment."""

import hashlib
import uuid
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Session, User
from utils.logging import get_logger

logger = get_logger(__name__)


class UsersService:
    """Handles user lifecycle and session issuance (no analytics coupling)."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def initialize_user(self, *, browser_info: Dict[str, Any], timezone: str, locale: str) -> User:
        """Create a user, assign experiment groups, and persist."""
        logger.debug("Creating new user", extra={"timezone": timezone, "locale": locale})

        user = User(browser_info=browser_info, timezone=timezone, locale=locale)
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)

        logger.debug("User created in database", extra={"user_id": str(user.id)})

        # Assign experiments deterministically based on UUID
        user.experiment_groups = self._assign_experiment_groups(user.id)
        await self.db.commit()
        await self.db.refresh(user)

        logger.info(
            "User initialized with experiment groups",
            extra={"user_id": str(user.id), "experiment_groups": user.experiment_groups},
        )
        return user

    async def initialize_session(self, *, user_id: str) -> str:
        """Return a new server-generated session id (UUID string)."""
        logger.debug("Creating new session", extra={"user_id": user_id})

        # Best-effort validation that the user exists; do not block session issuance
        try:
            result = await self.db.execute(select(User).where(User.id == uuid.UUID(str(user_id))))
            user = result.scalar_one_or_none()
            if user:
                logger.debug("User validated for session creation", extra={"user_id": user_id})
            else:
                logger.warning("User not found for session creation", extra={"user_id": user_id})
        except Exception as e:
            logger.warning("User validation failed during session creation", extra={"user_id": user_id, "error": str(e)})

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
            session_id = str(session_row.id)
            logger.info("Session created successfully", extra={"user_id": user_id, "session_id": session_id})
            return session_id
        except Exception as e:
            await self.db.rollback()
            # Fall back to ephemeral session id if DB write fails
            ephemeral_id = str(uuid.uuid4())
            logger.warning(
                "Failed to persist session, using ephemeral ID",
                extra={"user_id": user_id, "session_id": ephemeral_id, "error": str(e)},
            )
            return ephemeral_id

    async def verify_user(self, *, user_id: str) -> bool:
        """Verify if a user ID exists and is valid."""
        logger.debug("Verifying user", extra={"user_id": user_id})
        try:
            user_uuid = uuid.UUID(str(user_id))
            result = await self.db.execute(select(User).where(User.id == user_uuid))
            user = result.scalar_one_or_none()
            is_valid = user is not None

            if is_valid:
                logger.debug("User verification successful", extra={"user_id": user_id})
            else:
                logger.debug("User not found during verification", extra={"user_id": user_id})

            return is_valid
        except ValueError as e:
            logger.debug("Invalid UUID format for user verification", extra={"user_id": user_id, "error": str(e)})
            return False
        except Exception as e:
            logger.warning("User verification error", extra={"user_id": user_id, "error": str(e)})
            return False

    async def verify_session(self, *, session_id: str, user_id: str | None = None) -> bool:
        """Verify if a session ID exists and is valid, optionally for a specific user."""
        log_extra = {"session_id": session_id}
        if user_id:
            log_extra["user_id"] = user_id

        logger.debug("Verifying session", extra=log_extra)

        try:
            session_uuid = uuid.UUID(str(session_id))
            query = select(Session).where(Session.id == session_uuid)

            # If user_id is provided, also verify it belongs to that user
            if user_id:
                user_uuid = uuid.UUID(str(user_id))
                query = query.where(Session.user_id == user_uuid)
                logger.debug("Verifying session ownership", extra={"session_id": session_id, "user_id": user_id})

            result = await self.db.execute(query)
            session = result.scalar_one_or_none()
            is_valid = session is not None

            if is_valid:
                logger.debug("Session verification successful", extra=log_extra)
            else:
                logger.debug("Session not found or invalid during verification", extra=log_extra)

            return is_valid
        except ValueError as e:
            logger.debug("Invalid UUID format for session verification", extra={**log_extra, "error": str(e)})
            return False
        except Exception as e:
            logger.warning("Session verification error", extra={**log_extra, "error": str(e)})
            return False

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
