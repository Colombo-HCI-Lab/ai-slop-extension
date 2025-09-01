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
    try:
        async with get_async_session() as db:
            service = UsersService(db)
            user = await service.initialize_user(browser_info=request.browser_info, timezone=request.timezone, locale=request.locale)
            return UserInitResponse(user_id=user.id, experiment_groups=user.experiment_groups or [])
    except Exception as exc:  # pragma: no cover - safety net
        logger.error("User initialization failed", extra={"error": str(exc)}, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to initialize user")


@router.post("/session/initialize", response_model=SessionInitResponse)
async def initialize_session(request: SessionInitRequest) -> SessionInitResponse:
    """Create a new session id for an existing user and return it."""
    try:
        async with get_async_session() as db:
            service = UsersService(db)
            session_id = await service.initialize_session(user_id=str(request.user_id))
            return SessionInitResponse(session_id=session_id)
    except Exception as exc:  # pragma: no cover - safety net
        logger.error("Session initialization failed", extra={"error": str(exc)}, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to initialize session")
