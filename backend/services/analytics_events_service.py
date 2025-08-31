from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Union
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from db.models import AnalyticsEvent


class AnalyticsEventsService:
    """Analytics events service - stores events without aggregation."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def track_event(
        self,
        *,
        event_type: str,
        event_category: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        post_id: Optional[str] = None,
        event_data: Optional[Dict[str, Any]] = None,
        client_timestamp: Optional[datetime] = None,
    ) -> AnalyticsEvent:
        """Universal event tracking method - no aggregation."""

        event = AnalyticsEvent(
            event_type=event_type,
            event_category=event_category,
            user_id=user_id,
            session_id=session_id,
            post_id=post_id,
            event_data=event_data or {},
            client_timestamp=client_timestamp,
        )

        self.db.add(event)
        await self.db.commit()
        await self.db.refresh(event)
        return event

    async def track_enhanced_event(
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
        """Enhanced event tracking with priority and extended metadata."""

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
            user_id=user_id,
            session_id=session_id,
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

    async def track_enhanced_event_batch(
        self, events: List[Dict[str, Any]], batch_id: Optional[str] = None, batch_metadata: Optional[Dict[str, Any]] = None
    ) -> List[AnalyticsEvent]:
        """Enhanced batch event tracking with batch metadata."""

        models: List[AnalyticsEvent] = []
        for e in events:
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
                    user_id=e.get("user_id"),
                    session_id=e.get("session_id"),
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

    async def track_event_batch(self, events: List[Dict[str, Any]]) -> List[AnalyticsEvent]:
        """Batch event tracking - no aggregation."""

        models: List[AnalyticsEvent] = []
        for e in events:
            models.append(
                AnalyticsEvent(
                    event_type=e["event_type"],
                    event_category=e.get("event_category"),
                    user_id=e.get("user_id"),
                    session_id=e.get("session_id"),
                    post_id=e.get("post_id"),
                    event_data=e.get("event_data", {}),
                    client_timestamp=e.get("client_timestamp"),
                )
            )

        self.db.add_all(models)
        await self.db.commit()
        return models
