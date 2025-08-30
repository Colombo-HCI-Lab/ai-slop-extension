"""Analytics events API endpoints for unified event storage."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from db.async_session import get_async_session
from services.analytics_events_service import AnalyticsEventsService


router = APIRouter(prefix="/analytics", tags=["analytics"])


class EventTrackingRequest(BaseModel):
    event_type: str
    event_category: str
    user_id: Optional[str] = None
    post_id: Optional[str] = None
    session_identifier: Optional[str] = None
    event_data: Dict[str, Any] = Field(default_factory=dict)
    client_timestamp: Optional[datetime] = None


class EventBatchTrackingRequest(BaseModel):
    events: List[EventTrackingRequest]


@router.post("/events")
async def track_event(request: EventTrackingRequest):
    """Universal event tracking endpoint - event storage only."""
    try:
        async with get_async_session() as db:
            service = AnalyticsEventsService(db)
            event = await service.track_event(
                event_type=request.event_type,
                event_category=request.event_category,
                user_id=request.user_id,
                post_id=request.post_id,
                session_identifier=request.session_identifier,
                event_data=request.event_data,
                client_timestamp=request.client_timestamp,
            )
            return {"event_id": event.id, "status": "tracked"}
    except Exception as exc:  # pragma: no cover - safety net
        raise HTTPException(status_code=500, detail=f"Failed to track event: {exc}")


@router.post("/events/batch")
async def track_event_batch(request: EventBatchTrackingRequest, background_tasks: BackgroundTasks):
    """Batch event tracking endpoint - event storage only."""
    if not request.events:
        return {"events_queued": 0, "status": "accepted"}

    # Process asynchronously to keep the endpoint snappy
    background_tasks.add_task(_process_event_batch, [e.dict() for e in request.events])
    return {"events_queued": len(request.events), "status": "accepted"}


async def _process_event_batch(events: List[Dict[str, Any]]):
    async with get_async_session() as db:
        service = AnalyticsEventsService(db)
        await service.track_event_batch(events)
