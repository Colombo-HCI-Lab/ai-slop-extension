"""User API endpoints for user and session initialization."""

from fastapi import APIRouter, HTTPException

from db.async_session import get_async_session
from schemas.users import SessionInitRequest, SessionInitResponse, UserInitRequest, UserInitResponse
from services.users_service import UsersService
from utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/initialize", response_model=UserInitResponse)
async def initialize_user(request: UserInitRequest) -> UserInitResponse:
    """Create a new user and return the backend-generated user id."""
    logger.info("User initialization request received", extra={"timezone": request.timezone, "locale": request.locale})
    try:
        async with get_async_session() as db:
            service = UsersService(db)
            user = await service.initialize_user(browser_info=request.browser_info, timezone=request.timezone, locale=request.locale)
            logger.info(
                "User initialized successfully",
                extra={"user_id": str(user.id), "experiment_groups": user.experiment_groups or []},
            )
            return UserInitResponse(user_id=user.id, experiment_groups=user.experiment_groups or [])
    except Exception as exc:  # pragma: no cover - safety net
        logger.error("User initialization failed", extra={"error": str(exc)}, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to initialize user")


@router.post("/session/initialize", response_model=SessionInitResponse)
async def initialize_session(request: SessionInitRequest) -> SessionInitResponse:
    """Create a new session id for an existing user and return it."""
    logger.info("Session initialization request received", extra={"user_id": str(request.user_id)})
    try:
        async with get_async_session() as db:
            service = UsersService(db)
            session_id = await service.initialize_session(user_id=str(request.user_id))
            logger.info(
                "Session initialized successfully",
                extra={"user_id": str(request.user_id), "session_id": session_id},
            )
            return SessionInitResponse(session_id=session_id)
    except Exception as exc:  # pragma: no cover - safety net
        logger.error("Session initialization failed", extra={"error": str(exc), "user_id": str(request.user_id)}, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to initialize session")


@router.get("/verify/{user_id}")
async def verify_user(user_id: str) -> dict:
    """Verify if a user ID exists and is valid."""
    logger.debug("User verification request received", extra={"user_id": user_id})
    try:
        async with get_async_session() as db:
            service = UsersService(db)
            is_valid = await service.verify_user(user_id=user_id)
            logger.info(
                "User verification completed",
                extra={"user_id": user_id, "valid": is_valid},
            )
            return {"valid": is_valid, "user_id": user_id}
    except Exception as exc:
        logger.error("User verification failed", extra={"error": str(exc), "user_id": user_id}, exc_info=True)
        return {"valid": False, "user_id": user_id}


@router.get("/session/verify/{session_id}")
async def verify_session(session_id: str, user_id: str | None = None) -> dict:
    """Verify if a session ID exists and is valid, optionally for a specific user."""
    logger.debug(
        "Session verification request received",
        extra={"session_id": session_id, "user_id": user_id if user_id else "not_provided"},
    )
    try:
        async with get_async_session() as db:
            service = UsersService(db)
            is_valid = await service.verify_session(session_id=session_id, user_id=user_id)
            logger.info(
                "Session verification completed",
                extra={
                    "session_id": session_id,
                    "user_id": user_id if user_id else "not_provided",
                    "valid": is_valid,
                },
            )
            return {"valid": is_valid, "session_id": session_id}
    except Exception as exc:
        logger.error(
            "Session verification failed",
            extra={"error": str(exc), "session_id": session_id, "user_id": user_id if user_id else "not_provided"},
            exc_info=True,
        )
        return {"valid": False, "session_id": session_id}
