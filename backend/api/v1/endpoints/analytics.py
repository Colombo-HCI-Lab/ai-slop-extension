"""Analytics API endpoints for metrics collection system."""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from sqlalchemy.ext.asyncio import AsyncSession

from schemas.analytics import (
    UserInitRequest,
    UserInitResponse,
    SessionStartRequest,
    SessionEndRequest,
    EventBatchRequest,
    AnalyticsEvent,
    PostInteractionRequest,
    ChatSessionMetrics,
    UserDashboardResponse,
    UserPerformanceAnalyticsRequest,
)
from services.analytics_service import AnalyticsService
from services.monitoring_service import MonitoringService
from db.session import get_db
from utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.post("/users/initialize", response_model=UserInitResponse)
async def initialize_user(
    request: UserInitRequest, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db), http_request: Request = None
):
    """Initialize or update user profile with metrics."""
    start_time = datetime.now()
    logger.info(
        f"POST /analytics/users/initialize - Initializing user",
        extra={
            "endpoint": "/analytics/users/initialize",
            "method": "POST",
            "extension_user_id": request.extension_user_id[:8] + "...",
            "timezone": request.timezone,
            "locale": request.locale,
            "browser_name": request.browser_info.get("name"),
            "client_ip": request.client_ip or "unknown",
        },
    )

    try:
        # Extract client IP for rate limiting and geolocation
        client_ip = request.client_ip or (http_request.client.host if http_request else "unknown")

        service = AnalyticsService(db)
        user = await service.initialize_user(
            extension_user_id=request.extension_user_id, browser_info=request.browser_info, timezone=request.timezone, locale=request.locale
        )

        # Start new session
        session = await service.start_session(
            user.id, {**request.browser_info, "ip_hash": _hash_ip(client_ip) if client_ip != "unknown" else None}
        )

        # Background task for additional processing if needed
        background_tasks.add_task(_enrich_user_data, service, user.id, client_ip)

        response = UserInitResponse(user_id=user.id, session_id=session.id, experiment_groups=user.experiment_groups or [])

        duration_ms = (datetime.now() - start_time).total_seconds() * 1000
        logger.info(
            f"POST /analytics/users/initialize - Success",
            extra={
                "endpoint": "/analytics/users/initialize",
                "method": "POST",
                "user_id": str(user.id),
                "session_id": str(session.id),
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
                "extension_user_id": request.extension_user_id[:8] + "...",
                "error": str(e),
                "error_type": type(e).__name__,
                "duration_ms": round(duration_ms, 2),
                "status": "error",
            },
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Failed to initialize user")


@router.post("/sessions/start")
async def start_session(request: SessionStartRequest, db: AsyncSession = Depends(get_db)):
    """Start a new user session."""
    start_time = datetime.now()
    logger.info(
        f"POST /analytics/sessions/start - Starting session",
        extra={
            "endpoint": "/analytics/sessions/start",
            "method": "POST",
            "user_id": request.user_id[:8] + "...",
            "browser_name": request.browser_info.get("name"),
            "ip_hash": request.ip_hash[:8] + "..." if request.ip_hash else None,
        },
    )

    try:
        service = AnalyticsService(db)
        session = await service.start_session(user_id=request.user_id, browser_info=request.browser_info)

        duration_ms = (datetime.now() - start_time).total_seconds() * 1000
        logger.info(
            f"POST /analytics/sessions/start - Success",
            extra={
                "endpoint": "/analytics/sessions/start",
                "method": "POST",
                "user_id": request.user_id[:8] + "...",
                "session_id": str(session.id),
                "duration_ms": round(duration_ms, 2),
                "status": "success",
            },
        )

        return {"session_id": session.id, "status": "started"}

    except Exception as e:
        duration_ms = (datetime.now() - start_time).total_seconds() * 1000
        logger.error(
            f"POST /analytics/sessions/start - Failed",
            extra={
                "endpoint": "/analytics/sessions/start",
                "method": "POST",
                "user_id": request.user_id[:8] + "...",
                "error": str(e),
                "error_type": type(e).__name__,
                "duration_ms": round(duration_ms, 2),
                "status": "error",
            },
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Failed to start session")


@router.post("/sessions/end")
async def end_session(request: SessionEndRequest, db: AsyncSession = Depends(get_db)):
    """End a user session."""
    try:
        service = AnalyticsService(db)
        await service.end_session(session_id=request.session_id, end_reason=request.end_reason, duration_seconds=request.duration_seconds)

        return {"status": "ended"}

    except Exception as e:
        logger.error(f"Session end failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to end session")


@router.post("/events/batch")
async def submit_event_batch(request: EventBatchRequest, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    """Submit batch of analytics events with optional user_id."""
    start_time = datetime.now()
    logger.info(
        f"POST /analytics/events/batch - Processing event batch",
        extra={
            "endpoint": "/analytics/events/batch",
            "method": "POST",
            "session_id": request.session_id[:8] + "..." if request.session_id else None,
            "user_id": request.user_id[:8] + "..." if request.user_id else None,
            "event_count": len(request.events),
            "event_types": list(set(event.type for event in request.events)),
        },
    )

    try:
        # Validate event batch size
        if len(request.events) > 1000:
            raise HTTPException(status_code=400, detail="Batch size exceeds limit (1000)")

        # Validate timestamps (prevent future events)
        from datetime import timezone

        current_time = datetime.now(timezone.utc)
        valid_events = []

        for event in request.events:
            # Ensure event timestamp is timezone-aware for comparison
            event_time = event.client_timestamp
            if event_time.tzinfo is None:
                event_time = event_time.replace(tzinfo=timezone.utc)

            if event_time > current_time:
                logger.warning(f"Skipping future event: {event.type}")
                continue

            # Check if event is too old (>7 days)
            if current_time - event_time > timedelta(days=7):
                logger.debug(f"Skipping old event: {event.type}")
                continue

            valid_events.append(event)

        if not valid_events:
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            logger.warning(
                f"POST /analytics/events/batch - No valid events",
                extra={
                    "endpoint": "/analytics/events/batch",
                    "method": "POST",
                    "session_id": request.session_id[:8] + "..." if request.session_id else None,
                    "total_events": len(request.events),
                    "valid_events": 0,
                    "duration_ms": round(duration_ms, 2),
                    "status": "no_valid_events",
                },
            )
            return {"status": "no_valid_events", "count": 0}

        # Process events asynchronously with optional user_id (fresh DB session inside task)
        background_tasks.add_task(_process_events_background, request.session_id, valid_events, request.user_id)

        duration_ms = (datetime.now() - start_time).total_seconds() * 1000
        logger.info(
            f"POST /analytics/events/batch - Success",
            extra={
                "endpoint": "/analytics/events/batch",
                "method": "POST",
                "session_id": request.session_id[:8] + "..." if request.session_id else None,
                "user_id": request.user_id[:8] + "..." if request.user_id else None,
                "total_events": len(request.events),
                "valid_events": len(valid_events),
                "filtered_events": len(request.events) - len(valid_events),
                "duration_ms": round(duration_ms, 2),
                "status": "accepted",
            },
        )

        return {"status": "accepted", "count": len(valid_events)}

    except Exception as e:
        duration_ms = (datetime.now() - start_time).total_seconds() * 1000
        logger.error(
            f"POST /analytics/events/batch - Failed",
            extra={
                "endpoint": "/analytics/events/batch",
                "method": "POST",
                "session_id": request.session_id[:8] + "..." if request.session_id else None,
                "user_id": request.user_id[:8] + "..." if request.user_id else None,
                "event_count": len(request.events),
                "error": str(e),
                "error_type": type(e).__name__,
                "duration_ms": round(duration_ms, 2),
                "status": "error",
            },
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Failed to process events")


@router.post("/posts/{post_id}/interactions")
async def track_post_interaction(post_id: str, request: PostInteractionRequest, db: AsyncSession = Depends(get_db)):
    """Track user interaction with a post."""
    try:
        service = AnalyticsService(db)

        # Validate interaction type
        valid_types = ["viewed", "clicked", "ignored", "chatted", "feedback_positive", "feedback_negative", "feedback_unsure"]
        if request.interaction_type not in valid_types:
            raise HTTPException(status_code=400, detail=f"Invalid interaction type: {request.interaction_type}")

        analytics = await service.track_post_interaction(
            user_id=request.user_id,
            post_id=post_id,
            interaction_type=request.interaction_type,
            metrics={
                "backend_response_time_ms": request.backend_response_time_ms,
                "time_to_interaction_ms": request.time_to_interaction_ms,
                "reading_time_ms": request.reading_time_ms,
                "scroll_depth_percentage": request.scroll_depth_percentage,
                "viewport_time_ms": request.viewport_time_ms,
            },
        )

        return {"status": "tracked", "analytics_id": analytics.id}

    except Exception as e:
        logger.error(f"Post interaction tracking failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to track interaction")


@router.get("/dashboard/{user_id}", response_model=Dict[str, Any])
async def get_user_dashboard(
    user_id: str, date_from: Optional[datetime] = None, date_to: Optional[datetime] = None, db: AsyncSession = Depends(get_db)
):
    """Get user analytics dashboard data."""
    try:
        service = AnalyticsService(db)

        # Default to last 30 days
        if not date_from:
            date_from = datetime.utcnow() - timedelta(days=30)
        if not date_to:
            date_to = datetime.utcnow()

        # Validate date range
        if date_from > date_to:
            raise HTTPException(status_code=400, detail="Invalid date range")

        dashboard_data = await service.get_user_dashboard(user_id=user_id, date_from=date_from, date_to=date_to)

        return dashboard_data

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Dashboard retrieval failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve dashboard")


@router.post("/performance/metrics")
async def record_performance_metric(
    request: UserPerformanceAnalyticsRequest, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)
):
    """Record system performance metric."""
    start_time = datetime.now()
    logger.info(
        f"POST /analytics/performance/metrics - Recording performance metric",
        extra={
            "endpoint": "/analytics/performance/metrics",
            "method": "POST",
            "metric_name": request.metric_name,
            "metric_value": request.metric_value,
            "metric_unit": request.metric_unit,
            "target_endpoint": request.endpoint,
        },
    )

    try:
        # Process in background with fresh DB session to avoid leaks
        background_tasks.add_task(_record_performance_metric_background, request)

        duration_ms = (datetime.now() - start_time).total_seconds() * 1000
        logger.info(
            f"POST /analytics/performance/metrics - Success",
            extra={
                "endpoint": "/analytics/performance/metrics",
                "method": "POST",
                "metric_name": request.metric_name,
                "metric_value": request.metric_value,
                "duration_ms": round(duration_ms, 2),
                "status": "accepted",
            },
        )

        return {"status": "accepted"}

    except Exception as e:
        duration_ms = (datetime.now() - start_time).total_seconds() * 1000
        logger.error(
            f"POST /analytics/performance/metrics - Failed",
            extra={
                "endpoint": "/analytics/performance/metrics",
                "method": "POST",
                "metric_name": request.metric_name,
                "error": str(e),
                "error_type": type(e).__name__,
                "duration_ms": round(duration_ms, 2),
                "status": "error",
            },
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Failed to record metric")


@router.post("/chat/sessions")
async def create_chat_session(request: ChatSessionMetrics, db: AsyncSession = Depends(get_db)):
    """Create or update chat session metrics."""
    try:
        # This would integrate with the existing chat system
        # For now, return a placeholder response
        return {"status": "created", "session_id": request.session_id}

    except Exception as e:
        logger.error(f"Chat session creation failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to create chat session")


@router.get("/health")
async def health_check():
    """Analytics service health check."""
    return {"status": "healthy", "service": "analytics", "timestamp": datetime.utcnow().isoformat()}


@router.get("/system/health")
async def system_health_check(db: AsyncSession = Depends(get_db)):
    """Comprehensive system health check."""
    try:
        monitoring_service = MonitoringService(db)
        health_data = await monitoring_service.get_system_health()
        return health_data
    except Exception as e:
        logger.error(f"System health check failed: {e}")
        return {"status": "error", "timestamp": datetime.utcnow().isoformat(), "error": str(e)}


@router.get("/system/alerts")
async def get_performance_alerts(db: AsyncSession = Depends(get_db)):
    """Get current performance alerts."""
    try:
        monitoring_service = MonitoringService(db)
        alerts = await monitoring_service.get_performance_alerts()
        return {"alerts": alerts}
    except Exception as e:
        logger.error(f"Failed to get performance alerts: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve alerts")


@router.post("/system/cleanup")
async def cleanup_old_data(
    days_to_keep: int = 30, background_tasks: BackgroundTasks = BackgroundTasks(), db: AsyncSession = Depends(get_db)
):
    """No-op: analytics cleanup disabled to retain all records."""
    try:
        # Explicitly do nothing; return a disabled status
        return {"status": "disabled", "message": "Cleanup disabled by retention policy", "days_to_keep": days_to_keep}
    except Exception as e:
        logger.error(f"Unexpected error in cleanup endpoint: {e}")
        raise HTTPException(status_code=500, detail="Cleanup endpoint error")


# Background task functions


async def _process_events_background(session_id: str, events: List[AnalyticsEvent], user_id: Optional[str] = None) -> None:
    """Process events in background using a fresh DB session."""
    from db.pool import database_pool

    db_session = await database_pool.get_session()
    try:
        # Use provided user_id or generate anonymous one
        if not user_id:
            user_id = f"anon_{session_id[:8]}"

        service = AnalyticsService(db_session)
        await service.process_event_batch(session_id=session_id, events=events, user_id=user_id)

        logger.info(f"Background processed {len(events)} events for session {session_id}")
    except Exception as e:
        logger.error(f"Background event processing failed: {e}")
    finally:
        await db_session.close()


async def _record_performance_metric_background(request: UserPerformanceAnalyticsRequest) -> None:
    """Record performance metric in background using a fresh DB session."""
    from db.pool import database_pool

    db_session = await database_pool.get_session()
    try:
        service = AnalyticsService(db_session)
        await service.record_performance_metric(request)
        logger.debug(f"Background recorded metric: {request.metric_name}")
    except Exception as e:
        logger.error(f"Background metric recording failed: {e}")
    finally:
        await db_session.close()


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
