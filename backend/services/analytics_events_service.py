from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import AnalyticsEvent, User


class AnalyticsEventsService:
    """Analytics events service - tracking with priority and rich metadata."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # Legacy basic tracking removed

    async def track_event(
        self,
        *,
        event_type: Union[str],
        event_category: str,
        priority: str = "medium",
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        post_id: Optional[str] = None,
        event_data: Optional[Dict[str, Any]] = None,
        event_value: Optional[float] = None,
        event_label: Optional[str] = None,
        client_timestamp: Optional[datetime] = None,
        user_agent: Optional[str] = None,
        page_url: Optional[str] = None,
        referrer: Optional[str] = None,
    ) -> AnalyticsEvent:
        """Event tracking with priority and extended metadata."""

        # Convert user_id string to UUID if provided
        user_uuid = None
        if user_id:
            try:
                user_uuid = uuid.UUID(user_id)
            except (ValueError, TypeError):
                # Invalid UUID, ignore user_id
                user_uuid = None

        # Convert session_id string to UUID if provided
        session_uuid = None
        if session_id:
            try:
                session_uuid = uuid.UUID(session_id)
            except (ValueError, TypeError):
                session_uuid = None

        # Merge additional metadata into event_data
        enhanced_data = event_data or {}
        if user_agent:
            enhanced_data["user_agent"] = user_agent
        if page_url:
            enhanced_data["page_url"] = page_url
        if referrer:
            enhanced_data["referrer"] = referrer
        if priority:
            enhanced_data["priority"] = priority

        event = AnalyticsEvent(
            event_type=event_type,
            event_category=event_category,
            event_priority=priority,
            user_id=user_uuid,
            session_id=session_uuid,
            post_id=post_id,
            event_data=enhanced_data,
            event_value=event_value,
            event_label=event_label,
            client_timestamp=client_timestamp,
        )

        self.db.add(event)
        await self.db.commit()
        await self.db.refresh(event)
        return event

    async def track_event_batch(
        self, events: List[Dict[str, Any]], batch_id: Optional[str] = None, batch_metadata: Optional[Dict[str, Any]] = None
    ) -> List[AnalyticsEvent]:
        """Batch event tracking with batch metadata."""

        models: List[AnalyticsEvent] = []
        for e in events:
            # Convert user_id to UUID
            user_uuid = None
            if user_id_str := e.get("user_id"):
                try:
                    user_uuid = uuid.UUID(user_id_str)
                except (ValueError, TypeError):
                    pass

            # Convert session_id to UUID
            session_uuid = None
            if session_id_str := e.get("session_id"):
                try:
                    session_uuid = uuid.UUID(session_id_str)
                except (ValueError, TypeError):
                    pass

            # Merge batch metadata if provided
            enhanced_data = e.get("event_data", {})
            if batch_id:
                enhanced_data["batch_id"] = batch_id
            if batch_metadata:
                enhanced_data["batch_metadata"] = batch_metadata

            models.append(
                AnalyticsEvent(
                    event_type=e["event_type"],
                    event_category=e.get("event_category"),
                    event_priority=e.get("priority", "medium"),
                    user_id=user_uuid,
                    session_id=session_uuid,
                    post_id=e.get("post_id"),
                    event_data=enhanced_data,
                    event_value=e.get("event_value"),
                    event_label=e.get("event_label"),
                    client_timestamp=e.get("client_timestamp"),
                )
            )

        self.db.add_all(models)
        await self.db.commit()
        return models

    # Legacy batch tracking removed: use enhanced batch
