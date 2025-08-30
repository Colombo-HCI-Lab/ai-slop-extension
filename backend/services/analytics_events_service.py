from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

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
        post_id: Optional[str] = None,
        session_identifier: Optional[str] = None,
        event_data: Optional[Dict[str, Any]] = None,
        client_timestamp: Optional[datetime] = None,
    ) -> AnalyticsEvent:
        """Universal event tracking method - no aggregation."""

        event = AnalyticsEvent(
            event_type=event_type,
            event_category=event_category,
            user_id=user_id,
            post_id=post_id,
            session_identifier=session_identifier,
            event_data=event_data or {},
            client_timestamp=client_timestamp,
        )

        self.db.add(event)
        await self.db.commit()
        await self.db.refresh(event)
        return event

    async def track_event_batch(self, events: List[Dict[str, Any]]) -> List[AnalyticsEvent]:
        """Batch event tracking - no aggregation."""

        models: List[AnalyticsEvent] = []
        for e in events:
            models.append(
                AnalyticsEvent(
                    event_type=e["event_type"],
                    event_category=e.get("event_category"),
                    user_id=e.get("user_id"),
                    post_id=e.get("post_id"),
                    session_identifier=e.get("session_identifier"),
                    event_data=e.get("event_data", {}),
                    client_timestamp=e.get("client_timestamp"),
                )
            )

        self.db.add_all(models)
        await self.db.commit()
        return models
