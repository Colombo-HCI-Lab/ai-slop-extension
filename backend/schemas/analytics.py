"""Analytics schemas for metrics collection system."""

from typing import Dict, List, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class AnalyticsEvent(BaseModel):
    """Individual analytics event."""

    type: str = Field(..., description="Event type identifier")
    category: str = Field(..., description="Event category (interaction, performance, error)")
    value: Optional[float] = Field(None, description="Numeric event value")
    label: Optional[str] = Field(None, description="Human-readable event label")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional event metadata")
    client_timestamp: datetime = Field(..., description="Client-side timestamp", alias="clientTimestamp")

    model_config = {"populate_by_name": True}  # Allow both field name and alias

    # Timestamp validation moved to background task for performance
    # This allows the endpoint to return immediately


class UserInitRequest(BaseModel):
    """Request to initialize a user."""

    user_id: str = Field(..., description="Unique user identifier from browser extension")
    session_id: str = Field(..., description="Session identifier from browser extension")
    browser_info: Dict[str, Any] = Field(..., description="Browser and environment information")
    timezone: str = Field(..., description="User timezone")
    locale: str = Field(..., description="User locale")
    client_ip: Optional[str] = Field(None, description="Client IP address for geolocation")


class UserInitResponse(BaseModel):
    """Response from user initialization."""

    user_id: str = Field(..., description="Internal user ID")
    session_id: str = Field(..., description="Current session ID")
    experiment_groups: List[str] = Field(default_factory=list, description="A/B test groups")


class SessionStartRequest(BaseModel):
    """Request to start a new session."""

    user_id: str = Field(..., description="User ID")
    browser_info: Dict[str, Any] = Field(..., description="Browser information")
    ip_hash: Optional[str] = Field(None, description="Hashed IP address")


class SessionEndRequest(BaseModel):
    """Request to end a session."""

    session_id: str = Field(..., description="Session ID")
    end_reason: str = Field(..., description="Reason for ending session")
    duration_seconds: int = Field(..., description="Session duration in seconds")


class EventBatchRequest(BaseModel):
    """Batch of analytics events."""

    session_id: str = Field(..., description="Session ID")
    user_id: Optional[str] = Field(None, description="User ID (optional)")
    events: List[AnalyticsEvent] = Field(..., description="List of events")

    @field_validator("events")
    @classmethod
    def validate_batch_size(cls, v):
        """Ensure batch size is within limits."""
        if len(v) > 1000:
            raise ValueError("Batch size cannot exceed 1000 events")
        return v


class PostInteractionRequest(BaseModel):
    """Request to track post interaction."""

    user_id: str = Field(..., description="User ID")
    interaction_type: str = Field(..., description="Type of interaction")
    backend_response_time_ms: Optional[int] = Field(None, description="Backend response time")
    time_to_interaction_ms: Optional[int] = Field(None, description="Time from view to interaction")
    reading_time_ms: Optional[int] = Field(None, description="Estimated reading time")
    scroll_depth_percentage: Optional[float] = Field(None, description="Scroll depth percentage")
    viewport_time_ms: Optional[int] = Field(None, description="Time in viewport")


class UserPostChatAnalyticsMetrics(BaseModel):
    """User post chat analytics metrics."""

    session_id: str = Field(..., description="Chat session ID")
    user_post_analytics_id: str = Field(..., description="Related user post analytics ID")
    duration_ms: int = Field(..., description="Session duration in milliseconds")
    message_count: int = Field(..., description="Total messages")
    user_message_count: int = Field(..., description="User messages")
    assistant_message_count: int = Field(..., description="Assistant messages")
    suggested_question_clicks: int = Field(default=0, description="Suggested questions used")
    satisfaction_rating: Optional[int] = Field(None, description="1-5 satisfaction rating")
    ended_by: str = Field(default="close", description="How session ended")


class UserDashboardResponse(BaseModel):
    """User analytics dashboard data."""

    user_id: str = Field(..., description="User ID")
    period: Dict[str, str] = Field(..., description="Time period for data")
    interaction_stats: Dict[str, Any] = Field(..., description="Interaction statistics")
    session_stats: Dict[str, Any] = Field(..., description="Session statistics")
    chat_stats: Dict[str, Any] = Field(..., description="Chat statistics")
    accuracy_feedback: Dict[str, Any] = Field(..., description="Accuracy feedback stats")
    behavior_metrics: Dict[str, Any] = Field(..., description="Behavioral metrics")


class AnalyticsEventCreate(BaseModel):
    """Create analytics event in database."""

    user_id: Optional[str] = None
    session_id: Optional[str] = None
    post_id: Optional[str] = None
    event_type: str
    event_category: Optional[str] = None
    event_value: Optional[float] = None
    event_label: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    client_timestamp: datetime
    server_timestamp: Optional[datetime] = None


class UserPostAnalyticsCreate(BaseModel):
    """Create user post analytics entry."""

    user_id: str
    post_id: str
    interaction_type: str = "viewed"
    backend_response_time_ms: Optional[int] = None
    time_to_interaction_ms: Optional[int] = None
    icon_visibility_duration_ms: Optional[int] = None
    reading_time_ms: Optional[int] = None
    scroll_depth_percentage: Optional[float] = None
    viewport_time_ms: Optional[int] = None
    accuracy_feedback: Optional[str] = None


class UserCreate(BaseModel):
    """Create user entry."""

    user_id: str
    browser_info: Optional[Dict[str, Any]] = None
    timezone: Optional[str] = None
    locale: Optional[str] = None
    experiment_groups: Optional[List[str]] = None


class UserSessionAnalyticsCreate(BaseModel):
    """Create enhanced user session."""

    user_id: str
    session_token: str
    ip_hash: Optional[str] = None
    user_agent: Optional[str] = None
    duration_seconds: Optional[int] = None
    posts_viewed: int = 0
    posts_analyzed: int = 0
    posts_interacted: int = 0
    avg_scroll_speed: Optional[float] = None
    avg_posts_per_minute: Optional[float] = None
    total_scroll_distance: Optional[int] = None
    active_time_seconds: Optional[int] = None
    idle_time_seconds: Optional[int] = None
    end_reason: Optional[str] = None


class UserPostChatAnalyticsCreate(BaseModel):
    """Create user post chat analytics entry."""

    user_post_analytics_id: str
    session_token: str
    duration_ms: Optional[int] = None
    message_count: int = 0
    user_message_count: int = 0
    assistant_message_count: int = 0
    suggested_question_clicks: int = 0
    average_response_time_ms: Optional[int] = None
    max_response_time_ms: Optional[int] = None
    ended_by: str = "close"
    satisfaction_rating: Optional[int] = None
