"""Analytics API endpoints for metrics collection system."""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from schemas.analytics import UserInitRequest, UserInitResponse
from services.analytics_service import AnalyticsService
from services.monitoring_service import MonitoringService
from db.async_session import get_async_session
from db.models import UserSession
from utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.post("/users/initialize", response_model=UserInitResponse)
async def initialize_user(request: UserInitRequest, background_tasks: BackgroundTasks, http_request: Request = None):
    """Initialize or update user profile with metrics."""
    start_time = datetime.now()
    logger.info(
        f"POST /analytics/users/initialize - Initializing user",
        extra={
            "endpoint": "/analytics/users/initialize",
            "method": "POST",
            "user_id": None,
            "timezone": request.timezone,
            "locale": request.locale,
            "browser_name": request.browser_info.get("name"),
            "client_ip": request.client_ip or "unknown",
        },
    )

    try:
        async with get_async_session() as db:
            # Extract client IP for rate limiting and geolocation
            client_ip = request.client_ip or (http_request.client.host if http_request else "unknown")

            service = AnalyticsService(db)
            user = await service.initialize_user(
                browser_info=request.browser_info,
                timezone=request.timezone,
                locale=request.locale,
            )

            # Ensure chat UserSession is created early to anchor chat history using backend user id
            await _ensure_chat_user_session(db, user.id)

            # Background task for additional processing if needed
            background_tasks.add_task(_enrich_user_data, service, user.id, client_ip)

            response = UserInitResponse(user_id=user.id, experiment_groups=user.experiment_groups or [])

            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            logger.info(
                f"POST /analytics/users/initialize - Success",
                extra={
                    "endpoint": "/analytics/users/initialize",
                    "method": "POST",
                    "user_id": str(user.id),
                    "duration_ms": round(duration_ms, 2),
                    "experiment_groups": user.experiment_groups,
                    "status": "success",
                },
            )

            return response

    except Exception as e:
        duration_ms = (datetime.now() - start_time).total_seconds() * 1000
        logger.error(
            f"POST /analytics/users/initialize - Failed",
            extra={
                "endpoint": "/analytics/users/initialize",
                "method": "POST",
                "user_id": None,
                "error": str(e),
                "error_type": type(e).__name__,
                "duration_ms": round(duration_ms, 2),
                "status": "error",
            },
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Failed to initialize user")


## Legacy: /sessions/start removed (consolidated analytics events track session lifecycle)


## Legacy: /sessions/end removed (consolidated analytics events track session lifecycle)


# Legacy events batch endpoint removed in favor of consolidated analytics events


## Legacy: /posts/{post_id}/interactions removed (consolidated via analytics events)


## Legacy: /dashboard/{user_id} removed (aggregation removed; events are stored for offline analysis)


## Legacy: /chat/sessions removed (chat analytics captured via analytics events)


@router.get("/health")
async def health_check():
    """Analytics service health check."""
    return {"status": "healthy", "service": "analytics", "timestamp": datetime.utcnow().isoformat()}


@router.get("/system/health")
async def system_health_check():
    """Comprehensive system health check."""
    try:
        async with get_async_session() as db:
            monitoring_service = MonitoringService(db)
            health_data = await monitoring_service.get_system_health()
            return health_data
    except Exception as e:
        logger.error(f"System health check failed: {e}")
        return {"status": "error", "timestamp": datetime.utcnow().isoformat(), "error": str(e)}


@router.get("/system/alerts")
async def get_performance_alerts():
    """Get current performance alerts."""
    try:
        async with get_async_session() as db:
            monitoring_service = MonitoringService(db)
            alerts = await monitoring_service.get_performance_alerts()
            return {"alerts": alerts}
    except Exception as e:
        logger.error(f"Failed to get performance alerts: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve alerts")


@router.post("/system/cleanup")
async def cleanup_old_data(days_to_keep: int = 30, background_tasks: BackgroundTasks = BackgroundTasks()):
    """No-op: analytics cleanup disabled to retain all records."""
    try:
        # Explicitly do nothing; return a disabled status
        return {"status": "disabled", "message": "Cleanup disabled by retention policy", "days_to_keep": days_to_keep}
    except Exception as e:
        logger.error(f"Unexpected error in cleanup endpoint: {e}")
        raise HTTPException(status_code=500, detail="Cleanup endpoint error")


"""Background task functions and legacy handlers removed for consolidated analytics."""


async def _enrich_user_data(service: AnalyticsService, user_id: str, client_ip: str) -> None:
    """Enrich user data with geolocation and other info."""
    try:
        # This could include geolocation lookup, device fingerprinting, etc.
        # For now, it's a placeholder for future enhancements
        logger.debug(f"Enriching user data for {user_id} from IP {client_ip}")

    except Exception as e:
        logger.error(f"User data enrichment failed: {e}")


def _hash_ip(ip: str) -> str:
    """Hash IP address for privacy."""
    import hashlib

    return hashlib.sha256(ip.encode()).hexdigest()[:16]


async def _ensure_chat_user_session(db: AsyncSession, user_identifier: str) -> UserSession:
    """Create a chat UserSession if missing, used to anchor chat history.

    This uses the extension's persistent user identifier so that chat
    history queries always have a corresponding session.
    """
    result = await db.execute(select(UserSession).where(UserSession.user_identifier == user_identifier))
    existing = result.scalar_one_or_none()
    if existing:
        # Update last_active to now for freshness
        existing.last_active = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(existing)
        return existing

    new_session = UserSession(user_identifier=user_identifier, last_active=datetime.now(timezone.utc))
    db.add(new_session)
    await db.commit()
    await db.refresh(new_session)
    return new_session
