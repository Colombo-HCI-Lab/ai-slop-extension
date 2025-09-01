"""Users service: user and session initialization and experiment assignment."""

import hashlib
import time
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Session, User
from utils.logging import get_logger

logger = get_logger(__name__)


class UsersService:
    """Handles user lifecycle and session issuance (no analytics coupling)."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def initialize_user(self, *, browser_info: Dict[str, Any], timezone: str, locale: str, client_ip: Optional[str] = None) -> User:
        """Create a user, assign experiment groups, and persist."""
        start_time = time.time()
        operation_id = str(uuid.uuid4())[:8]

        logger.info(
            "Starting user initialization",
            extra={
                "operation": "user_initialization",
                "operation_id": operation_id,
                "timezone": timezone,
                "locale": locale,
                "client_ip": client_ip,
                "browser_info": {
                    "name": browser_info.get("name"),
                    "platform": browser_info.get("platform"),
                    "language": browser_info.get("language"),
                },
            },
        )

        try:
            # Create user entity
            user = User(browser_info=browser_info, timezone=timezone, locale=locale)
            self.db.add(user)
            await self.db.commit()
            await self.db.refresh(user)

            logger.debug(
                "User entity created in database",
                extra={
                    "operation_id": operation_id,
                    "user_id": str(user.id),
                    "created_at": user.created_at.isoformat() if user.created_at else None,
                },
            )

            # Assign experiments deterministically based on UUID
            user.experiment_groups = self._assign_experiment_groups(user.id)
            await self.db.commit()
            await self.db.refresh(user)

            duration_ms = (time.time() - start_time) * 1000

            logger.info(
                "User initialization completed successfully",
                extra={
                    "operation": "user_initialization",
                    "operation_id": operation_id,
                    "user_id": str(user.id),
                    "experiment_groups": user.experiment_groups,
                    "duration_ms": round(duration_ms, 2),
                    "is_new_user": True,
                    "security_context": {"timezone": timezone, "locale": locale, "client_ip": client_ip},
                },
            )

            return user

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000

            logger.error(
                "User initialization failed",
                extra={
                    "operation": "user_initialization",
                    "operation_id": operation_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "duration_ms": round(duration_ms, 2),
                    "recovery_action": "client_should_retry",
                    "timezone": timezone,
                    "locale": locale,
                },
                exc_info=True,
            )

            # Re-raise to let caller handle
            raise

    async def initialize_session(self, *, user_id: str, client_data: Optional[Dict[str, Any]] = None) -> str:
        """Return a new server-generated session id (UUID string)."""
        start_time = time.time()
        operation_id = str(uuid.uuid4())[:8]

        logger.info(
            "Starting session initialization",
            extra={
                "operation": "session_initialization",
                "operation_id": operation_id,
                "user_id": user_id,
                "client_data": {
                    "user_agent": client_data.get("user_agent") if client_data else None,
                    "page_url": client_data.get("page_url") if client_data else None,
                    "timezone": client_data.get("timezone") if client_data else None,
                    "locale": client_data.get("locale") if client_data else None,
                },
            },
        )

        # Best-effort validation that the user exists; do not block session issuance
        user_exists = False
        try:
            result = await self.db.execute(select(User).where(User.id == uuid.UUID(str(user_id))))
            user = result.scalar_one_or_none()
            user_exists = user is not None

            if user_exists:
                logger.debug(
                    "User validated for session creation",
                    extra={
                        "operation_id": operation_id,
                        "user_id": user_id,
                        "user_created_at": user.created_at.isoformat() if user.created_at else None,
                        "user_experiment_groups": user.experiment_groups,
                    },
                )
            else:
                logger.warning(
                    "User not found for session creation - proceeding with ephemeral session",
                    extra={
                        "operation_id": operation_id,
                        "user_id": user_id,
                        "security_risk": "orphaned_session",
                        "recovery_action": "session_will_be_ephemeral",
                    },
                )
        except ValueError as e:
            logger.warning(
                "Invalid user ID format during session creation",
                extra={
                    "operation_id": operation_id,
                    "user_id": user_id,
                    "error_type": "invalid_uuid",
                    "error_message": str(e),
                    "recovery_action": "using_ephemeral_session",
                },
            )
        except Exception as e:
            logger.error(
                "User validation failed during session creation",
                extra={
                    "operation_id": operation_id,
                    "user_id": user_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "recovery_action": "proceeding_with_session_creation",
                },
                exc_info=True,
            )

        # Create a new session row tied to the user
        try:
            session_row = Session(
                user_id=uuid.UUID(str(user_id)),
                user_agent=client_data.get("user_agent") if client_data else None,
                page_url=client_data.get("page_url") if client_data else None,
                referrer=client_data.get("referrer") if client_data else None,
                client_timezone=client_data.get("timezone") if client_data else None,
                client_locale=client_data.get("locale") if client_data else None,
            )
            self.db.add(session_row)
            await self.db.commit()
            await self.db.refresh(session_row)
            session_id = str(session_row.id)

            duration_ms = (time.time() - start_time) * 1000

            logger.info(
                "Session initialization completed successfully",
                extra={
                    "operation": "session_initialization",
                    "operation_id": operation_id,
                    "user_id": user_id,
                    "session_id": session_id,
                    "duration_ms": round(duration_ms, 2),
                    "is_new_session": True,
                    "session_type": "persistent",
                    "user_exists": user_exists,
                    "started_at": session_row.started_at.isoformat() if session_row.started_at else None,
                    "security_context": {
                        "user_agent": client_data.get("user_agent") if client_data else None,
                        "page_url": client_data.get("page_url") if client_data else None,
                        "timezone": client_data.get("timezone") if client_data else None,
                    },
                },
            )

            return session_id

        except Exception as e:
            await self.db.rollback()
            duration_ms = (time.time() - start_time) * 1000

            # Fall back to ephemeral session id if DB write fails
            ephemeral_id = str(uuid.uuid4())

            logger.warning(
                "Session persistence failed - using ephemeral session",
                extra={
                    "operation": "session_initialization",
                    "operation_id": operation_id,
                    "user_id": user_id,
                    "session_id": ephemeral_id,
                    "session_type": "ephemeral",
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "duration_ms": round(duration_ms, 2),
                    "recovery_action": "ephemeral_session_issued",
                    "data_persistence": "none",
                },
            )

            return ephemeral_id

    async def verify_user(self, *, user_id: str) -> bool:
        """Verify if a user ID exists and is valid."""
        start_time = time.time()
        operation_id = str(uuid.uuid4())[:8]

        logger.debug(
            "Starting user verification", extra={"operation": "user_verification", "operation_id": operation_id, "user_id": user_id}
        )

        try:
            user_uuid = uuid.UUID(str(user_id))
            result = await self.db.execute(select(User).where(User.id == user_uuid))
            user = result.scalar_one_or_none()
            is_valid = user is not None

            duration_ms = (time.time() - start_time) * 1000

            if is_valid:
                logger.info(
                    "User verification successful",
                    extra={
                        "operation": "user_verification",
                        "operation_id": operation_id,
                        "user_id": user_id,
                        "verification_result": "valid",
                        "duration_ms": round(duration_ms, 2),
                        "user_created_at": user.created_at.isoformat() if user.created_at else None,
                        "user_experiment_groups": user.experiment_groups,
                        "security_context": "authenticated_user",
                    },
                )
            else:
                logger.warning(
                    "User verification failed - user not found",
                    extra={
                        "operation": "user_verification",
                        "operation_id": operation_id,
                        "user_id": user_id,
                        "verification_result": "invalid",
                        "duration_ms": round(duration_ms, 2),
                        "security_risk": "unknown_user_id",
                        "recommended_action": "user_re_initialization",
                    },
                )

            return is_valid

        except ValueError as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.warning(
                "User verification failed - invalid UUID format",
                extra={
                    "operation": "user_verification",
                    "operation_id": operation_id,
                    "user_id": user_id,
                    "verification_result": "invalid",
                    "error_type": "invalid_uuid",
                    "error_message": str(e),
                    "duration_ms": round(duration_ms, 2),
                    "security_risk": "malformed_user_id",
                    "recommended_action": "client_validation_required",
                },
            )
            return False

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                "User verification error - database exception",
                extra={
                    "operation": "user_verification",
                    "operation_id": operation_id,
                    "user_id": user_id,
                    "verification_result": "error",
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "duration_ms": round(duration_ms, 2),
                    "recovery_action": "retry_with_backoff",
                },
                exc_info=True,
            )
            return False

    async def verify_session(self, *, session_id: str, user_id: str | None = None) -> bool:
        """Verify if a session ID exists and is valid, optionally for a specific user."""
        start_time = time.time()
        operation_id = str(uuid.uuid4())[:8]

        log_extra = {
            "operation": "session_verification",
            "operation_id": operation_id,
            "session_id": session_id,
            "user_id": user_id,
            "ownership_check": user_id is not None,
        }

        logger.debug("Starting session verification", extra=log_extra)

        try:
            session_uuid = uuid.UUID(str(session_id))
            query = select(Session).where(Session.id == session_uuid)

            # If user_id is provided, also verify it belongs to that user
            if user_id:
                user_uuid = uuid.UUID(str(user_id))
                query = query.where(Session.user_id == user_uuid)
                logger.debug(
                    "Verifying session ownership",
                    extra={
                        "operation_id": operation_id,
                        "session_id": session_id,
                        "user_id": user_id,
                        "verification_type": "ownership_validation",
                    },
                )

            result = await self.db.execute(query)
            session = result.scalar_one_or_none()
            is_valid = session is not None

            duration_ms = (time.time() - start_time) * 1000

            if is_valid:
                logger.info(
                    "Session verification successful",
                    extra={
                        "operation": "session_verification",
                        "operation_id": operation_id,
                        "session_id": session_id,
                        "user_id": user_id or str(session.user_id),
                        "verification_result": "valid",
                        "duration_ms": round(duration_ms, 2),
                        "session_started_at": session.started_at.isoformat() if session.started_at else None,
                        "session_last_active": session.last_active.isoformat() if session.last_active else None,
                        "security_context": "authenticated_session",
                        "ownership_verified": user_id is not None,
                    },
                )
            else:
                security_risk = "unknown_session_id"
                if user_id:
                    security_risk = "session_ownership_mismatch"

                logger.warning(
                    "Session verification failed",
                    extra={
                        "operation": "session_verification",
                        "operation_id": operation_id,
                        "session_id": session_id,
                        "user_id": user_id,
                        "verification_result": "invalid",
                        "duration_ms": round(duration_ms, 2),
                        "security_risk": security_risk,
                        "recommended_action": "session_re_initialization",
                        "ownership_check": user_id is not None,
                    },
                )

            return is_valid

        except ValueError as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.warning(
                "Session verification failed - invalid UUID format",
                extra={
                    "operation": "session_verification",
                    "operation_id": operation_id,
                    "session_id": session_id,
                    "user_id": user_id,
                    "verification_result": "invalid",
                    "error_type": "invalid_uuid",
                    "error_message": str(e),
                    "duration_ms": round(duration_ms, 2),
                    "security_risk": "malformed_session_id",
                    "recommended_action": "client_validation_required",
                },
            )
            return False

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                "Session verification error - database exception",
                extra={
                    "operation": "session_verification",
                    "operation_id": operation_id,
                    "session_id": session_id,
                    "user_id": user_id,
                    "verification_result": "error",
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "duration_ms": round(duration_ms, 2),
                    "recovery_action": "retry_with_backoff",
                },
                exc_info=True,
            )
            return False

    def _assign_experiment_groups(self, user_id: Any) -> List[str]:
        """Assign A/B test groups using a stable hash of the user id."""
        operation_id = str(uuid.uuid4())[:8]

        logger.debug(
            "Starting experiment group assignment",
            extra={
                "operation": "experiment_assignment",
                "operation_id": operation_id,
                "user_id": str(user_id),
                "assignment_method": "deterministic_hash",
            },
        )

        if isinstance(user_id, str):
            data = user_id.encode("utf-8")
        elif isinstance(user_id, uuid.UUID):
            data = user_id.bytes
        else:
            data = str(user_id).encode("utf-8")

        user_hash = int(hashlib.md5(data).hexdigest(), 16)
        groups: List[str] = []

        # Assign primary metrics group
        metrics_group = "detailed_metrics" if user_hash % 2 == 0 else "basic_metrics"
        groups.append(metrics_group)

        # Assign experimental features (20% of users)
        if user_hash % 5 == 0:
            groups.append("experimental_features")

        logger.info(
            "Experiment groups assigned successfully",
            extra={
                "operation": "experiment_assignment",
                "operation_id": operation_id,
                "user_id": str(user_id),
                "assigned_groups": groups,
                "hash_value": str(user_hash)[-8:],  # Last 8 chars for debugging
                "metrics_group": metrics_group,
                "experimental_features": "experimental_features" in groups,
                "assignment_ratios": {"detailed_metrics": "50%", "basic_metrics": "50%", "experimental_features": "20%"},
            },
        )

        return groups
