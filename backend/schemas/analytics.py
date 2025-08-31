"""Analytics schemas (consolidated)."""

from typing import Dict, List, Optional, Any, Literal, Union
from datetime import datetime
from pydantic import BaseModel, Field


class UserInitRequest(BaseModel):
    """Request to initialize a user (server generates ID)."""

    browser_info: Dict[str, Any] = Field(..., description="Browser and environment information")
    timezone: str = Field(..., description="User timezone")
    locale: str = Field(..., description="User locale")
    client_ip: Optional[str] = Field(None, description="Client IP address for geolocation")


class UserInitResponse(BaseModel):
    """Response from user initialization."""

    user_id: str = Field(..., description="Internal user ID")
    experiment_groups: List[str] = Field(default_factory=list, description="A/B test groups")


# Enhanced Analytics Event Types
EventCategory = Literal["session", "post", "chat", "interaction", "performance", "behavior", "trust", "ui", "content", "learning", "error"]

EventPriority = Literal["critical", "high", "medium", "low"]

# Comprehensive event type definitions
BehaviorEventType = Literal[
    "mouse_hover_pattern",
    "rage_click_detected",
    "attention_focus",
    "attention_blur",
    "content_engagement_depth",
    "copy_action",
    "text_selection",
    "mouse_movement_pattern",
    "reading_behavior_pattern",
    "idle_detection",
    "typing_speed_analysis",
    "multi_selection",
]

TrustEventType = Literal[
    "detection_confidence_interaction",
    "detection_icon_interaction",
    "detection_icon_hover",
    "false_positive_report",
    "trust_score_change",
    "detection_fatigue",
    "ai_vs_human_behavior",
    "false_positive_pattern_detected",
    "trust_calibration",
    "confidence_threshold_adjustment",
]

UIEventType = Literal[
    "icon_render_performance",
    "tooltip_interaction_depth",
    "chat_resize_behavior",
    "visual_hierarchy_effectiveness",
    "error_recovery_flow",
    "layout_shift_detected",
    "paint_timing",
    "memory_usage_tracking",
    "ui_error_detected",
    "accessibility_interaction",
    "theme_change",
    "font_size_adjustment",
    "keyboard_navigation",
    "responsive_breakpoint",
    "animation_performance",
]

ContentEventType = Literal[
    "post_characteristics",
    "content_velocity",
    "temporal_patterns",
    "content_similarity_clusters",
    "network_effects",
    "content_anomaly_detected",
    "ai_farming_detection",
    "engagement_correlation",
    "viral_pattern_detection",
    "content_freshness_analysis",
    "duplicate_content_detection",
    "language_detection",
]

LearningEventType = Literal[
    "learning_accuracy_update",
    "interaction_speed_tracking",
    "feature_discovery",
    "sophistication_level_change",
    "multi_tab_usage",
    "session_recovery",
    "idle_session_start",
    "tab_visibility_change",
    "cross_session_learning",
    "user_onboarding_progress",
    "help_system_usage",
    "tutorial_completion",
    "skill_assessment",
    "adaptation_response",
    "personalization_update",
    "retention_milestone",
    "habit_formation",
    "proficiency_test",
]

ChatEventType = Literal[
    "chat_conversation_start",
    "chat_conversation_end",
    "chat_user_message",
    "chat_assistant_message",
    "chat_satisfaction_signal",
    "suggested_question_performance",
    "chat_typing_activity",
    "question_classification_factual",
    "question_classification_clarification",
    "question_classification_opinion",
    "question_classification_comparison",
    "question_classification_explanation",
    "question_classification_hypothetical",
    "conversation_flow_analysis",
    "response_quality_rating",
    "context_switch_detected",
]

# Combined event type union
ComprehensiveEventType = Union[BehaviorEventType, TrustEventType, UIEventType, ContentEventType, LearningEventType, ChatEventType]


class EnhancedEventTrackingRequest(BaseModel):
    """Enhanced event tracking request with priority and comprehensive types."""

    event_type: Union[str, ComprehensiveEventType] = Field(..., description="Event type identifier")
    event_category: EventCategory = Field(..., description="Event category for grouping")
    priority: EventPriority = Field(default="medium", description="Event processing priority")

    # Identifiers
    user_id: Optional[str] = Field(None, description="User identifier")
    session_id: Optional[str] = Field(None, description="Session identifier (from /analytics/users/initialize)")
    post_id: Optional[str] = Field(None, description="Post identifier")

    # Event data
    event_data: Dict[str, Any] = Field(default_factory=dict, description="Event payload")
    event_value: Optional[float] = Field(None, description="Numeric event value")
    event_label: Optional[str] = Field(None, description="Event label")

    # Timestamps
    client_timestamp: Optional[datetime] = Field(None, description="Client-side timestamp")

    # Metadata
    user_agent: Optional[str] = Field(None, description="User agent string")
    page_url: Optional[str] = Field(None, description="Page URL where event occurred")
    referrer: Optional[str] = Field(None, description="Referrer URL")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class EnhancedEventBatchRequest(BaseModel):
    """Enhanced batch event tracking request."""

    events: List[EnhancedEventTrackingRequest] = Field(..., description="List of events to track")
    batch_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Batch-level metadata")


class EventTrackingResponse(BaseModel):
    """Response for event tracking."""

    event_id: str = Field(..., description="Generated event ID")
    status: Literal["tracked", "queued", "failed"] = Field(..., description="Processing status")
    priority: EventPriority = Field(..., description="Assigned priority")
    processed_at: datetime = Field(..., description="Server processing timestamp")


class EventBatchTrackingResponse(BaseModel):
    """Response for batch event tracking."""

    events_accepted: int = Field(..., description="Number of events accepted")
    events_rejected: int = Field(default=0, description="Number of events rejected")
    status: Literal["accepted", "partial", "rejected"] = Field(..., description="Batch processing status")
    batch_id: Optional[str] = Field(None, description="Batch identifier for tracking")
    errors: Optional[List[str]] = Field(default_factory=list, description="Processing errors")


# Mouse tracking data structures
class MouseState(BaseModel):
    x: int
    y: int
    timestamp: datetime


class HoverZone(BaseModel):
    element_selector: str
    dwell_time: float
    entry_count: int


# Trust tracking data structures
class DetectionInteraction(BaseModel):
    post_id: str
    confidence: float
    detection_result: Literal["ai", "human", "uncertain"]
    user_response: Optional[str] = None
    response_time: Optional[float] = None


# Content intelligence data structures
class PostCharacteristics(BaseModel):
    text_length: int
    media_count: int
    hashtag_count: int
    mention_count: int
    link_count: int
    emoji_count: int
    readability_score: Optional[float] = None
    sentiment_score: Optional[float] = None


# Learning analytics data structures
class LearningProgress(BaseModel):
    user_id: str
    session_id: str
    accuracy_score: float
    interaction_speed: float
    feature_adoption: List[str]
    sophistication_level: int


# Chat analytics data structures
class ConversationContext(BaseModel):
    session_id: str
    post_id: Optional[str] = None
    message_count: int
    conversation_duration: float
    user_satisfaction_signals: List[str]


class QuestionClassification(BaseModel):
    question_type: str
    complexity_score: float
    context_requirements: List[str]
    response_expectations: List[str]
