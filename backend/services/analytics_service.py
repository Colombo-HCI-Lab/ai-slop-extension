"""Analytics service for metrics collection and processing."""

import hashlib
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func, and_, desc, asc
from sqlalchemy.orm import selectinload

from db.models import User, UserPostAnalytics, UserSessionAnalytics, ChatSession, AnalyticsEvent, UserPerformanceAnalytics, Post
from schemas.analytics import (
    AnalyticsEvent as EventSchema,
    UserCreate,
    UserPostAnalyticsCreate,
    UserSessionAnalyticsCreate,
    ChatSessionCreate,
    AnalyticsEventCreate,
    UserPerformanceAnalyticsRequest,
)
from utils.logging import get_logger

logger = get_logger(__name__)


class AnalyticsService:
    """Service for analytics data operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def initialize_user(self, extension_user_id: str, browser_info: Dict[str, Any], timezone: str, locale: str) -> User:
        """Initialize or update user with deduplication."""
        logger.info(
            f"Initializing user: {extension_user_id[:8]}...",
            extra={
                "extension_user_id": extension_user_id,
                "timezone": timezone,
                "locale": locale,
                "browser_name": browser_info.get("name"),
                "browser_version": browser_info.get("version"),
            },
        )

        try:
            # Check for existing user
            stmt = select(User).where(User.extension_user_id == extension_user_id)
            result = await self.db.execute(stmt)
            user = result.scalar_one_or_none()

            if user:
                # Update existing user
                user.last_active_at = datetime.utcnow()
                user.browser_info = browser_info
                user.timezone = timezone
                user.locale = locale
                logger.info(
                    f"Updated existing user: {extension_user_id[:8]}...",
                    extra={"user_id": str(user.id), "action": "update_user", "last_active_at": user.last_active_at.isoformat()},
                )
            else:
                # Create new user with A/B test assignment
                user = User(
                    extension_user_id=extension_user_id,
                    browser_info=browser_info,
                    timezone=timezone,
                    locale=locale,
                    experiment_groups=self._assign_experiment_groups(extension_user_id),
                )
                self.db.add(user)
                logger.info(
                    f"Created new user: {extension_user_id[:8]}...",
                    extra={
                        "user_id": str(user.id) if hasattr(user, "id") else "pending",
                        "action": "create_user",
                        "experiment_groups": user.experiment_groups,
                    },
                )

            await self.db.commit()
            await self.db.refresh(user)
            return user

        except Exception as e:
            await self.db.rollback()
            logger.error(
                f"User initialization failed for {extension_user_id[:8]}...",
                extra={
                    "extension_user_id": extension_user_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "action": "initialize_user",
                },
                exc_info=True,
            )
            raise

    async def start_session(self, user_id: str, browser_info: Dict[str, Any]) -> UserSessionAnalytics:
        """Start a new user session."""
        logger.info(
            f"Starting session for user {user_id[:8]}...",
            extra={
                "user_id": user_id,
                "ip_hash": browser_info.get("ip_hash", "unknown")[:8] + "..." if browser_info.get("ip_hash") else "none",
                "browser_name": browser_info.get("name"),
                "action": "start_session",
            },
        )

        try:
            session_token = self._generate_session_token()
            ip_hash = browser_info.get("ip_hash")
            user_agent = browser_info.get("user_agent")

            session = UserSessionAnalytics(user_id=user_id, session_token=session_token, ip_hash=ip_hash, user_agent=user_agent)

            self.db.add(session)
            await self.db.commit()
            await self.db.refresh(session)

            logger.info(
                f"Started session {session.id} for user {user_id[:8]}...",
                extra={
                    "session_id": str(session.id),
                    "user_id": user_id,
                    "session_token": session_token[:12] + "...",
                    "action": "session_started",
                    "created_at": session.created_at.isoformat(),
                },
            )
            return session

        except Exception as e:
            await self.db.rollback()
            logger.error(
                f"Failed to start session for user {user_id[:8]}...",
                extra={"user_id": user_id, "error": str(e), "error_type": type(e).__name__, "action": "start_session"},
                exc_info=True,
            )
            raise

    async def end_session(self, session_id: str, end_reason: str, duration_seconds: int) -> None:
        """End a user session."""
        logger.info(
            f"Ending session {session_id[:8]}...",
            extra={"session_id": session_id, "end_reason": end_reason, "duration_seconds": duration_seconds, "action": "end_session"},
        )

        try:
            stmt = select(UserSessionAnalytics).where(UserSessionAnalytics.id == session_id)
            result = await self.db.execute(stmt)
            session = result.scalar_one_or_none()

            if session:
                session.ended_at = datetime.utcnow()
                session.end_reason = end_reason
                session.duration_seconds = duration_seconds

                await self.db.commit()
                logger.info(
                    f"Ended session {session_id[:8]}...",
                    extra={
                        "session_id": session_id,
                        "user_id": session.user_id,
                        "end_reason": end_reason,
                        "duration_seconds": duration_seconds,
                        "ended_at": session.ended_at.isoformat(),
                        "action": "session_ended",
                    },
                )
            else:
                logger.warning(
                    f"Session {session_id[:8]}... not found for ending",
                    extra={"session_id": session_id, "end_reason": end_reason, "action": "session_not_found"},
                )

        except Exception as e:
            await self.db.rollback()
            logger.error(
                f"Failed to end session {session_id[:8]}...",
                extra={
                    "session_id": session_id,
                    "end_reason": end_reason,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "action": "end_session",
                },
                exc_info=True,
            )
            raise

    async def process_event_batch(self, session_id: str, events: List[EventSchema], user_id: str) -> None:
        """Process analytics events with deduplication and aggregation."""
        logger.info(
            f"Processing event batch for session {session_id[:8]}...",
            extra={
                "session_id": session_id,
                "user_id": user_id[:8] + "..." if user_id else None,
                "event_count": len(events),
                "event_types": [e.type for e in events],
                "action": "process_event_batch",
            },
        )

        try:
            # Check if user and session exist (they may not for anonymous tracking)
            user_exists = False
            session_exists = False

            if user_id and not user_id.startswith("anon_"):
                # Check if user exists
                stmt = select(User).where(User.id == user_id)
                result = await self.db.execute(stmt)
                user_exists = result.scalar_one_or_none() is not None

            if session_id:
                # Check if session exists
                stmt = select(UserSessionAnalytics).where(UserSessionAnalytics.id == session_id)
                result = await self.db.execute(stmt)
                session_exists = result.scalar_one_or_none() is not None

            # Deduplicate events by hash
            seen_hashes = set()
            unique_events = []

            for event in events:
                event_hash = self._hash_event(event)
                if event_hash not in seen_hashes:
                    seen_hashes.add(event_hash)
                    unique_events.append(event)

            if not unique_events:
                logger.debug("No unique events to process")
                return

            # Batch insert events with post_id validation
            event_models = []
            for event in unique_events:
                # Validate post_id exists before setting it
                post_id = None
                if event.metadata and event.metadata.get("post_id"):
                    potential_post_id = event.metadata.get("post_id")

                    # Check if post exists
                    stmt = select(Post).where(Post.post_id == potential_post_id)
                    result = await self.db.execute(stmt)
                    post_exists = result.scalar_one_or_none() is not None

                    if post_exists:
                        post_id = potential_post_id
                    else:
                        logger.warning(f"Post {potential_post_id} does not exist, setting post_id to None for event {event.type}")

                event_models.append(
                    AnalyticsEvent(
                        user_id=user_id if user_exists else None,  # Only set if user exists
                        session_id=session_id if session_exists else None,  # Only set if session exists
                        event_type=event.type,
                        event_category=event.category,
                        event_value=event.value,
                        event_label=event.label,
                        event_metadata=event.metadata,
                        client_timestamp=event.client_timestamp,
                        post_id=post_id,  # Only set if post exists
                    )
                )

            self.db.add_all(event_models)
            await self.db.commit()

            logger.info(
                f"Processed {len(unique_events)} unique events for session {session_id[:8]}...",
                extra={
                    "session_id": session_id,
                    "user_id": user_id[:8] + "..." if user_id else None,
                    "total_events": len(events),
                    "unique_events": len(unique_events),
                    "duplicates_filtered": len(events) - len(unique_events),
                    "user_exists": user_exists,
                    "session_exists": session_exists,
                    "action": "events_processed",
                },
            )

            # Update aggregated metrics asynchronously
            await self._update_aggregated_metrics(user_id, session_id, unique_events)

        except Exception as e:
            await self.db.rollback()
            logger.error(
                f"Failed to process event batch for session {session_id[:8]}...",
                extra={
                    "session_id": session_id,
                    "user_id": user_id[:8] + "..." if user_id else None,
                    "event_count": len(events),
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "action": "process_event_batch",
                },
                exc_info=True,
            )
            raise

    async def track_post_interaction(self, user_id: str, post_id: str, interaction_type: str, metrics: Dict[str, Any]) -> UserPostAnalytics:
        """Track user interaction with a post."""
        logger.info(
            f"Tracking post interaction for user {user_id[:8]}...",
            extra={
                "user_id": user_id,
                "post_id": post_id,
                "interaction_type": interaction_type,
                "metrics_keys": list(metrics.keys()) if metrics else [],
                "action": "track_post_interaction",
            },
        )

        try:
            # Ensure user exists; create minimal placeholder if missing to avoid FK errors
            stmt_user = select(User).where(User.id == user_id)
            result_user = await self.db.execute(stmt_user)
            user = result_user.scalar_one_or_none()
            if not user:
                user = User(
                    id=user_id,  # Use provided ID (should be UUID from extension)
                    extension_user_id=user_id,
                    browser_info=None,
                    timezone=None,
                    locale=None,
                    experiment_groups=[],
                )
                self.db.add(user)
                # Flush so the user row exists for FK constraints in the same transaction
                await self.db.flush()
                logger.info(
                    "Created placeholder user for interaction",
                    extra={"user_id": user_id, "action": "create_placeholder_user"},
                )

            # Check for existing analytics record
            stmt = select(UserPostAnalytics).where(and_(UserPostAnalytics.user_id == user_id, UserPostAnalytics.post_id == post_id))
            result = await self.db.execute(stmt)
            analytics = result.scalar_one_or_none()

            current_time = datetime.utcnow()

            if analytics:
                # Update existing record
                analytics.interaction_type = interaction_type
                analytics.last_viewed_at = current_time
                analytics.times_viewed += 1

                # Update metrics if provided
                if metrics.get("backend_response_time_ms"):
                    analytics.backend_response_time_ms = metrics["backend_response_time_ms"]
                if metrics.get("time_to_interaction_ms"):
                    analytics.time_to_interaction_ms = metrics["time_to_interaction_ms"]
                    analytics.interaction_at = current_time
                if metrics.get("reading_time_ms"):
                    analytics.reading_time_ms = metrics["reading_time_ms"]
                if metrics.get("scroll_depth_percentage"):
                    analytics.scroll_depth_percentage = metrics["scroll_depth_percentage"]
                if metrics.get("viewport_time_ms"):
                    analytics.viewport_time_ms = metrics["viewport_time_ms"]

                logger.debug(f"Updated post analytics for user {user_id}, post {post_id}")
            else:
                # Create new record
                analytics = UserPostAnalytics(
                    user_id=user_id,
                    post_id=post_id,
                    interaction_type=interaction_type,
                    backend_response_time_ms=metrics.get("backend_response_time_ms"),
                    time_to_interaction_ms=metrics.get("time_to_interaction_ms"),
                    reading_time_ms=metrics.get("reading_time_ms"),
                    scroll_depth_percentage=metrics.get("scroll_depth_percentage"),
                    viewport_time_ms=metrics.get("viewport_time_ms"),
                    first_viewed_at=current_time,
                    last_viewed_at=current_time,
                )

                if metrics.get("time_to_interaction_ms"):
                    analytics.interaction_at = current_time

                self.db.add(analytics)
                logger.info(
                    f"Created post analytics for user {user_id[:8]}...",
                    extra={
                        "user_id": user_id,
                        "post_id": post_id,
                        "interaction_type": interaction_type,
                        "action": "created_post_analytics",
                    },
                )

            await self.db.commit()
            await self.db.refresh(analytics)
            return analytics

        except Exception as e:
            await self.db.rollback()
            logger.error(
                f"Failed to track post interaction for user {user_id[:8]}...",
                extra={
                    "user_id": user_id,
                    "post_id": post_id,
                    "interaction_type": interaction_type,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "action": "track_post_interaction",
                },
                exc_info=True,
            )
            raise

    async def get_user_dashboard(self, user_id: str, date_from: datetime, date_to: datetime) -> Dict[str, Any]:
        """Generate user analytics dashboard with caching."""
        try:
            # Fetch user data
            stmt = select(User).where(User.id == user_id)
            result = await self.db.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                raise ValueError(f"User {user_id} not found")

            # Parallel queries for performance
            tasks = [
                self._get_interaction_stats(user_id, date_from, date_to),
                self._get_session_stats(user_id, date_from, date_to),
                self._get_chat_stats(user_id, date_from, date_to),
                self._get_accuracy_feedback(user_id, date_from, date_to),
            ]

            results = await asyncio.gather(*tasks)

            dashboard_data = {
                "user_id": user_id,
                "period": {"from": date_from.isoformat(), "to": date_to.isoformat()},
                "interaction_stats": results[0],
                "session_stats": results[1],
                "chat_stats": results[2],
                "accuracy_feedback": results[3],
                "behavior_metrics": {
                    "avg_scroll_speed": user.avg_scroll_speed,
                    "avg_posts_per_minute": user.avg_posts_per_minute,
                    "total_posts_viewed": user.total_posts_viewed,
                    "total_interactions": user.total_interactions,
                },
            }

            logger.debug(f"Generated dashboard for user {user_id}")
            return dashboard_data

        except Exception as e:
            logger.error(f"Failed to generate dashboard for user {user_id}: {e}")
            raise

    async def record_performance_metric(self, metric_request: UserPerformanceAnalyticsRequest) -> UserPerformanceAnalytics:
        """Record a performance metric."""
        try:
            metric = UserPerformanceAnalytics(
                session_id=metric_request.session_id,
                metric_name=metric_request.metric_name,
                metric_value=metric_request.metric_value,
                metric_unit=metric_request.metric_unit,
                endpoint=metric_request.endpoint,
                metric_metadata=metric_request.metadata,
            )

            self.db.add(metric)
            await self.db.commit()
            await self.db.refresh(metric)

            logger.debug(f"Recorded performance metric: {metric_request.metric_name}")
            return metric

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to record performance metric {metric_request.metric_name}: {e}")
            raise

    async def _update_aggregated_metrics(self, user_id: str, session_id: str, events: List[EventSchema]) -> None:
        """Update user and session aggregated metrics."""
        try:
            # Calculate metrics from events
            metrics = self._calculate_metrics_from_events(events)

            # Update user metrics if we have scroll speed data
            if metrics.get("avg_scroll_speed"):
                stmt = select(User).where(User.id == user_id)
                result = await self.db.execute(stmt)
                user = result.scalar_one_or_none()

                if user:
                    current_avg = user.avg_scroll_speed or 0
                    total_posts = user.total_posts_viewed or 0

                    # Calculate weighted average
                    new_avg = (current_avg * total_posts + metrics["avg_scroll_speed"]) / (total_posts + 1)

                    user.avg_scroll_speed = new_avg
                    user.total_posts_viewed = total_posts + metrics.get("posts_viewed", 0)
                    user.total_interactions += metrics.get("interactions", 0)

            # Update session metrics
            if session_id and metrics:
                stmt = select(UserSessionAnalytics).where(UserSessionAnalytics.id == session_id)
                result = await self.db.execute(stmt)
                session = result.scalar_one_or_none()

                if session:
                    session.posts_viewed += metrics.get("posts_viewed", 0)
                    session.posts_analyzed += metrics.get("posts_analyzed", 0)
                    session.posts_interacted += metrics.get("posts_interacted", 0)
                    if metrics.get("avg_scroll_speed"):
                        session.avg_scroll_speed = metrics["avg_scroll_speed"]
                    session.updated_at = datetime.utcnow()

            await self.db.commit()

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to update aggregated metrics: {e}")
            raise

    async def _get_interaction_stats(self, user_id: str, date_from: datetime, date_to: datetime) -> Dict[str, Any]:
        """Get user interaction statistics."""
        try:
            stmt = select(
                func.count(UserPostAnalytics.id).label("total_posts_viewed"),
                func.count(UserPostAnalytics.id).filter(UserPostAnalytics.interaction_type != "viewed").label("total_interactions"),
                func.avg(UserPostAnalytics.reading_time_ms).label("avg_reading_time"),
                func.avg(UserPostAnalytics.time_to_interaction_ms).label("avg_time_to_interaction"),
            ).where(
                and_(
                    UserPostAnalytics.user_id == user_id,
                    UserPostAnalytics.first_viewed_at >= date_from,
                    UserPostAnalytics.first_viewed_at <= date_to,
                )
            )

            result = await self.db.execute(stmt)
            row = result.first()

            return {
                "total_posts_viewed": row.total_posts_viewed or 0,
                "total_interactions": row.total_interactions or 0,
                "avg_reading_time_ms": float(row.avg_reading_time) if row.avg_reading_time else 0,
                "avg_time_to_interaction_ms": float(row.avg_time_to_interaction) if row.avg_time_to_interaction else 0,
            }

        except Exception as e:
            logger.error(f"Failed to get interaction stats: {e}")
            return {}

    async def _get_session_stats(self, user_id: str, date_from: datetime, date_to: datetime) -> Dict[str, Any]:
        """Get user session statistics."""
        try:
            stmt = select(
                func.count(UserSessionAnalytics.id).label("total_sessions"),
                func.avg(UserSessionAnalytics.duration_seconds).label("avg_session_duration"),
                func.sum(UserSessionAnalytics.posts_viewed).label("total_posts_in_sessions"),
            ).where(
                and_(
                    UserSessionAnalytics.user_id == user_id,
                    UserSessionAnalytics.started_at >= date_from,
                    UserSessionAnalytics.started_at <= date_to,
                )
            )

            result = await self.db.execute(stmt)
            row = result.first()

            return {
                "total_sessions": row.total_sessions or 0,
                "avg_session_duration_seconds": float(row.avg_session_duration) if row.avg_session_duration else 0,
                "total_posts_in_sessions": row.total_posts_in_sessions or 0,
            }

        except Exception as e:
            logger.error(f"Failed to get session stats: {e}")
            return {}

    async def _get_chat_stats(self, user_id: str, date_from: datetime, date_to: datetime) -> Dict[str, Any]:
        """Get user chat statistics."""
        try:
            # Join through user_post_analytics to get to chat_session
            stmt = (
                select(
                    func.count(ChatSession.id).label("total_chat_sessions"),
                    func.avg(ChatSession.duration_ms).label("avg_chat_duration"),
                    func.sum(ChatSession.message_count).label("total_messages"),
                    func.avg(ChatSession.satisfaction_rating).label("avg_satisfaction"),
                )
                .select_from(
                    ChatSession.__table__.join(UserPostAnalytics.__table__, ChatSession.user_post_analytics_id == UserPostAnalytics.id)
                )
                .where(and_(UserPostAnalytics.user_id == user_id, ChatSession.started_at >= date_from, ChatSession.started_at <= date_to))
            )

            result = await self.db.execute(stmt)
            row = result.first()

            return {
                "total_chat_sessions": row.total_chat_sessions or 0,
                "avg_chat_duration_ms": float(row.avg_chat_duration) if row.avg_chat_duration else 0,
                "total_messages": row.total_messages or 0,
                "avg_satisfaction_rating": float(row.avg_satisfaction) if row.avg_satisfaction else 0,
            }

        except Exception as e:
            logger.error(f"Failed to get chat stats: {e}")
            return {}

    async def _get_accuracy_feedback(self, user_id: str, date_from: datetime, date_to: datetime) -> Dict[str, Any]:
        """Get accuracy feedback statistics."""
        try:
            stmt = (
                select(UserPostAnalytics.accuracy_feedback, func.count(UserPostAnalytics.id).label("count"))
                .where(
                    and_(
                        UserPostAnalytics.user_id == user_id,
                        UserPostAnalytics.first_viewed_at >= date_from,
                        UserPostAnalytics.first_viewed_at <= date_to,
                        UserPostAnalytics.accuracy_feedback.isnot(None),
                    )
                )
                .group_by(UserPostAnalytics.accuracy_feedback)
            )

            result = await self.db.execute(stmt)
            rows = result.all()

            feedback_stats = {}
            total_feedback = 0

            for row in rows:
                feedback_stats[row.accuracy_feedback] = row.count
                total_feedback += row.count

            return {"feedback_breakdown": feedback_stats, "total_feedback_given": total_feedback}

        except Exception as e:
            logger.error(f"Failed to get accuracy feedback: {e}")
            return {}

    def _hash_event(self, event: EventSchema) -> str:
        """Generate hash for event deduplication."""
        hash_input = f"{event.type}:{event.client_timestamp}:{event.value}:{event.metadata}"
        return hashlib.sha256(hash_input.encode()).hexdigest()[:16]

    def _assign_experiment_groups(self, user_id: str) -> List[str]:
        """Assign user to A/B test groups deterministically."""
        groups = []

        # Hash-based assignment for consistency
        user_hash = int(hashlib.md5(user_id.encode()).hexdigest(), 16)

        # 50/50 split for metrics collection detail level
        if user_hash % 2 == 0:
            groups.append("detailed_metrics")
        else:
            groups.append("basic_metrics")

        # 20% get experimental features
        if user_hash % 5 == 0:
            groups.append("experimental_features")

        return groups

    def _generate_session_token(self) -> str:
        """Generate unique session token."""
        import secrets

        return secrets.token_urlsafe(32)

    def _calculate_metrics_from_events(self, events: List[EventSchema]) -> Dict[str, Any]:
        """Calculate aggregated metrics from event list."""
        metrics = {"posts_viewed": 0, "posts_analyzed": 0, "posts_interacted": 0, "interactions": 0, "avg_scroll_speed": 0}

        scroll_speeds = []

        for event in events:
            if event.type == "post_view":
                metrics["posts_viewed"] += 1
            elif event.type == "post_processed":
                metrics["posts_analyzed"] += 1
            elif event.type in ["icon_click", "chat_start"]:
                metrics["posts_interacted"] += 1
                metrics["interactions"] += 1
            elif event.type == "scroll_behavior" and event.value:
                scroll_speeds.append(event.value)

        if scroll_speeds:
            metrics["avg_scroll_speed"] = sum(scroll_speeds) / len(scroll_speeds)

        return metrics

    # NOTE: The request-based method above is the canonical API. The older positional
    # variant has been removed to avoid signature conflicts with the endpoint code.
