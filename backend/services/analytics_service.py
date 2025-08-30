"""Analytics service: minimal user initialization utilities (consolidated analytics events)."""

import hashlib
from typing import Any, Dict, List
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import User
from utils.logging import get_logger

logger = get_logger(__name__)


class AnalyticsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def initialize_user(self, browser_info: Dict[str, Any], timezone: str, locale: str) -> User:
        try:
            user = User(browser_info=browser_info, timezone=timezone, locale=locale)
            self.db.add(user)
            await self.db.commit()
            await self.db.refresh(user)

            user.experiment_groups = self._assign_experiment_groups(user.id)
            await self.db.commit()
            await self.db.refresh(user)
            return user
        except Exception as e:
            await self.db.rollback()
            logger.error("User initialization failed", extra={"error": str(e)}, exc_info=True)
            raise

    def _assign_experiment_groups(self, user_id: str) -> List[str]:
        groups: List[str] = []
        user_hash = int(hashlib.md5(user_id.encode()).hexdigest(), 16)
        groups.append("detailed_metrics" if user_hash % 2 == 0 else "basic_metrics")
        if user_hash % 5 == 0:
            groups.append("experimental_features")
        return groups
