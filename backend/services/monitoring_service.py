"""Monitoring and performance logging service (reduced)."""

from typing import Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from utils.logging import get_logger

logger = get_logger(__name__)


class MonitoringService:
    """Service for system monitoring and performance tracking."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def record_api_performance(
        self, endpoint: str, method: str, duration_ms: float, status_code: int, error: Optional[str] = None
    ) -> None:
        """Record API endpoint performance metrics via logging only."""
        try:
            # Log performance metrics instead of storing in database
            logger.info(
                f"API Performance: {method} {endpoint}",
                extra={
                    "endpoint": f"{method} {endpoint}",
                    "duration_ms": duration_ms,
                    "status_code": status_code,
                    "error": error,
                    "metric_type": "api_performance",
                },
            )

            # Log slow endpoints
            if duration_ms > 1000:
                logger.warning(f"Slow API call: {method} {endpoint} took {duration_ms}ms")

        except Exception as e:
            logger.error(f"Failed to record API performance: {e}")

    async def cleanup_old_metrics(self, days_to_keep: int = 30) -> Dict[str, int]:
        """No-op: retention policy set to keep all analytics and metrics forever."""
        logger.info(
            "Cleanup disabled by retention policy; keeping all metrics/events",
            extra={"days_to_keep": days_to_keep},
        )
        return {"performance_metrics": 0, "analytics_events": 0, "cutoff_date": None}

    # Removed: get_performance_alerts (alerts endpoint removed)
