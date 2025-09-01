"""Analytics events API endpoints for unified event storage."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException

from db.async_session import get_async_session
from schemas.analytics import EventBatchRequest, EventBatchTrackingResponse, EventTrackingRequest, EventTrackingResponse
from services.analytics_events_service import AnalyticsEventsService

router = APIRouter(prefix="/analytics", tags=["analytics"])


"""
Analytics endpoints (single and batch) support priority and rich metadata. Legacy simple endpoints have been removed.
"""


# Event analytics endpoints (priority + metadata)
@router.post("/events", response_model=EventTrackingResponse)
async def track_event(request: EventTrackingRequest):
    """Event tracking endpoint with priority support and metadata."""
    try:
        async with get_async_session() as db:
            service = AnalyticsEventsService(db)
            event = await service.track_event(
                event_type=request.event_type,
                event_category=request.event_category,
                priority=request.priority,
                user_id=request.user_id,
                session_id=request.session_id,
                post_id=request.post_id,
                event_data=request.event_data,
                event_value=request.event_value,
                event_label=request.event_label,
                client_timestamp=request.client_timestamp,
                user_agent=request.user_agent,
                page_url=request.page_url,
                referrer=request.referrer,
            )
            return EventTrackingResponse(
                event_id=event.id, status="tracked", priority=request.priority, processed_at=event.server_timestamp
            )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to track event: {exc}")


@router.post("/events/batch", response_model=EventBatchTrackingResponse)
async def track_event_batch(request: EventBatchRequest, background_tasks: BackgroundTasks):
    """Batch event tracking endpoint with priority support."""
    if not request.events:
        return EventBatchTrackingResponse(events_accepted=0, events_rejected=0, status="accepted")

    # Generate batch ID for tracking
    batch_id = str(uuid.uuid4())

    # Separate events by priority for processing order
    critical_events = [e for e in request.events if e.priority == "critical"]
    other_events = [e for e in request.events if e.priority != "critical"]

    # Process critical events immediately
    if critical_events:
        try:
            async with get_async_session() as db:
                service = AnalyticsEventsService(db)
                await service.track_event_batch([e.dict() for e in critical_events])
        except Exception as exc:
            return EventBatchTrackingResponse(
                events_accepted=0,
                events_rejected=len(request.events),
                status="rejected",
                batch_id=batch_id,
                errors=[f"Critical events processing failed: {exc}"],
            )

    # Process other events in background
    if other_events:
        background_tasks.add_task(_process_event_batch, [e.dict() for e in other_events], batch_id, request.batch_metadata)

    return EventBatchTrackingResponse(events_accepted=len(request.events), events_rejected=0, status="accepted", batch_id=batch_id)


# Batch processing
async def _process_event_batch(events: List[Dict[str, Any]], batch_id: str, batch_metadata: Optional[Dict[str, Any]] = None):
    """Process event batch with priority handling."""
    try:
        async with get_async_session() as db:
            service = AnalyticsEventsService(db)
            await service.track_event_batch(events, batch_id, batch_metadata)
    except Exception as exc:
        # Log error but don't raise - background task
        print(f"Batch processing failed for batch {batch_id}: {exc}")
