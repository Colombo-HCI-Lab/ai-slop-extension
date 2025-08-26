"""Monitoring and performance optimization service."""

import asyncio
import time
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text

from db.models import AnalyticsEvent, PerformanceMetric, User, UserSessionEnhanced
from utils.logging import get_logger

logger = get_logger(__name__)


class MonitoringService:
    """Service for system monitoring and performance tracking."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def record_api_performance(
        self, endpoint: str, method: str, duration_ms: float, status_code: int, error: Optional[str] = None
    ) -> None:
        """Record API endpoint performance metrics."""
        try:
            metric = PerformanceMetric(
                metric_name="api_response_time",
                metric_value=duration_ms,
                metric_unit="ms",
                endpoint=f"{method} {endpoint}",
                metric_metadata={"method": method, "status_code": status_code, "error": error, "timestamp": datetime.utcnow().isoformat()},
            )

            self.db.add(metric)
            await self.db.commit()

            # Log slow endpoints
            if duration_ms > 1000:
                logger.warning(f"Slow API call: {method} {endpoint} took {duration_ms}ms")

        except Exception as e:
            logger.error(f"Failed to record API performance: {e}")

    async def get_system_health(self) -> Dict[str, any]:
        """Get overall system health metrics."""
        try:
            # Run health checks in parallel
            tasks = [
                self._check_database_health(),
                self._get_api_performance_stats(),
                self._get_user_activity_stats(),
                self._get_error_rate_stats(),
                self._check_memory_usage(),
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            return {
                "status": "healthy" if all(not isinstance(r, Exception) for r in results) else "degraded",
                "timestamp": datetime.utcnow().isoformat(),
                "checks": {
                    "database": results[0] if not isinstance(results[0], Exception) else {"status": "error", "error": str(results[0])},
                    "api_performance": results[1]
                    if not isinstance(results[1], Exception)
                    else {"status": "error", "error": str(results[1])},
                    "user_activity": results[2] if not isinstance(results[2], Exception) else {"status": "error", "error": str(results[2])},
                    "error_rate": results[3] if not isinstance(results[3], Exception) else {"status": "error", "error": str(results[3])},
                    "memory": results[4] if not isinstance(results[4], Exception) else {"status": "error", "error": str(results[4])},
                },
            }

        except Exception as e:
            logger.error(f"Failed to get system health: {e}")
            return {"status": "error", "timestamp": datetime.utcnow().isoformat(), "error": str(e)}

    async def _check_database_health(self) -> Dict[str, any]:
        """Check database connectivity and performance."""
        try:
            start_time = time.time()

            # Simple connectivity test
            result = await self.db.execute(text("SELECT 1"))
            result.fetchall()

            response_time = (time.time() - start_time) * 1000

            # Check connection pool status if available
            pool_status = {}
            if hasattr(self.db.bind, "pool"):
                pool = self.db.bind.pool
                pool_status = {
                    "size": pool.size(),
                    "checked_in": pool.checkedin(),
                    "checked_out": pool.checkedout(),
                    "overflow": pool.overflow(),
                }

            return {"status": "healthy", "response_time_ms": response_time, "pool": pool_status}

        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    async def _get_api_performance_stats(self) -> Dict[str, any]:
        """Get API performance statistics for the last hour."""
        try:
            one_hour_ago = datetime.utcnow() - timedelta(hours=1)

            stmt = select(
                func.avg(PerformanceMetric.metric_value).label("avg_response_time"),
                func.max(PerformanceMetric.metric_value).label("max_response_time"),
                func.count(PerformanceMetric.id).label("total_requests"),
                func.count(PerformanceMetric.id).filter(PerformanceMetric.metric_value > 1000).label("slow_requests"),
            ).where(PerformanceMetric.metric_name == "api_response_time", PerformanceMetric.timestamp >= one_hour_ago)

            result = await self.db.execute(stmt)
            row = result.first()

            if not row or row.total_requests == 0:
                return {"status": "no_data", "message": "No API performance data available"}

            slow_request_rate = (row.slow_requests / row.total_requests) * 100 if row.total_requests > 0 else 0

            return {
                "status": "healthy" if slow_request_rate < 5 else "degraded",
                "avg_response_time_ms": float(row.avg_response_time) if row.avg_response_time else 0,
                "max_response_time_ms": float(row.max_response_time) if row.max_response_time else 0,
                "total_requests": row.total_requests,
                "slow_requests": row.slow_requests,
                "slow_request_rate_percent": slow_request_rate,
            }

        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def _get_user_activity_stats(self) -> Dict[str, any]:
        """Get user activity statistics."""
        try:
            one_hour_ago = datetime.utcnow() - timedelta(hours=1)

            # Active users in last hour
            active_users_stmt = select(func.count(func.distinct(User.id))).where(User.last_active_at >= one_hour_ago)

            # Active sessions in last hour
            active_sessions_stmt = select(func.count(UserSessionEnhanced.id)).where(
                UserSessionEnhanced.started_at >= one_hour_ago, UserSessionEnhanced.ended_at.is_(None)
            )

            # Events in last hour
            events_stmt = select(func.count(AnalyticsEvent.id)).where(AnalyticsEvent.created_at >= one_hour_ago)

            results = await asyncio.gather(
                self.db.execute(active_users_stmt), self.db.execute(active_sessions_stmt), self.db.execute(events_stmt)
            )

            active_users = results[0].scalar() or 0
            active_sessions = results[1].scalar() or 0
            events_count = results[2].scalar() or 0

            return {
                "status": "healthy",
                "active_users_last_hour": active_users,
                "active_sessions": active_sessions,
                "events_last_hour": events_count,
            }

        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def _get_error_rate_stats(self) -> Dict[str, any]:
        """Get error rate statistics."""
        try:
            one_hour_ago = datetime.utcnow() - timedelta(hours=1)

            stmt = select(
                func.count(AnalyticsEvent.id).label("total_events"),
                func.count(AnalyticsEvent.id).filter(AnalyticsEvent.event_category == "error").label("error_events"),
            ).where(AnalyticsEvent.created_at >= one_hour_ago)

            result = await self.db.execute(stmt)
            row = result.first()

            if not row or row.total_events == 0:
                return {"status": "healthy", "error_rate_percent": 0}

            error_rate = (row.error_events / row.total_events) * 100

            return {
                "status": "healthy" if error_rate < 1 else "degraded",
                "error_rate_percent": error_rate,
                "total_events": row.total_events,
                "error_events": row.error_events,
            }

        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def _check_memory_usage(self) -> Dict[str, any]:
        """Check memory usage (basic implementation)."""
        try:
            import psutil
            import os

            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()

            return {
                "status": "healthy",
                "rss_mb": memory_info.rss / 1024 / 1024,
                "vms_mb": memory_info.vms / 1024 / 1024,
                "cpu_percent": process.cpu_percent(),
            }

        except ImportError:
            return {"status": "not_available", "message": "psutil not installed"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def cleanup_old_metrics(self, days_to_keep: int = 30) -> Dict[str, int]:
        """Clean up old performance metrics to manage database size."""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)

            # Delete old performance metrics
            perf_stmt = text("DELETE FROM performance_metric WHERE created_at < :cutoff_date")
            perf_result = await self.db.execute(perf_stmt, {"cutoff_date": cutoff_date})

            # Delete old analytics events (keep essential events longer)
            events_stmt = text(
                """DELETE FROM analytics_event 
                WHERE created_at < :cutoff_date 
                AND event_category NOT IN ('error', 'security')"""
            )
            events_result = await self.db.execute(events_stmt, {"cutoff_date": cutoff_date})

            await self.db.commit()

            cleaned = {
                "performance_metrics": perf_result.rowcount,
                "analytics_events": events_result.rowcount,
                "cutoff_date": cutoff_date.isoformat(),
            }

            logger.info(f"Cleaned up old metrics: {cleaned}")
            return cleaned

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to cleanup old metrics: {e}")
            raise

    async def get_performance_alerts(self) -> List[Dict[str, any]]:
        """Get performance alerts that need attention."""
        alerts = []

        try:
            # Check for high error rate
            error_stats = await self._get_error_rate_stats()
            if error_stats.get("error_rate_percent", 0) > 5:
                alerts.append(
                    {
                        "type": "high_error_rate",
                        "severity": "warning",
                        "message": f"Error rate is {error_stats['error_rate_percent']:.1f}%",
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )

            # Check for slow API responses
            api_stats = await self._get_api_performance_stats()
            if api_stats.get("avg_response_time_ms", 0) > 500:
                alerts.append(
                    {
                        "type": "slow_api_responses",
                        "severity": "warning",
                        "message": f"Average API response time is {api_stats['avg_response_time_ms']:.0f}ms",
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )

            return alerts

        except Exception as e:
            logger.error(f"Failed to get performance alerts: {e}")
            return [
                {
                    "type": "monitoring_error",
                    "severity": "error",
                    "message": f"Failed to check performance alerts: {str(e)}",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ]
