"""Database models for AI Slop Detection backend."""

import uuid
from datetime import datetime
from typing import Any, List, Optional

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base model class with common fields."""

    __abstract__ = True

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def dict(self) -> dict[str, Any]:
        """Convert model to dictionary."""
        return {column.name: getattr(self, column.name) for column in self.__table__.columns}


class Post(Base):
    """Post model for storing Facebook posts and their AI detection results."""

    __tablename__ = "post"

    # Facebook post ID (numeric string from URL) - now primary key
    post_id: Mapped[str] = mapped_column(String(255), primary_key=True, index=True)

    # Post content
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Post author
    author: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # AI detection verdict: 'ai_slop', 'human_content', 'uncertain'
    verdict: Mapped[str] = mapped_column(String(50), nullable=False)

    # Confidence score (0.0 to 1.0) - legacy field for backward compatibility
    confidence: Mapped[float] = mapped_column(Float, nullable=False)

    # Explanation of the verdict
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Text analysis results
    text_ai_probability: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    text_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Image analysis results
    image_ai_probability: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    image_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Video analysis results
    video_ai_probability: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    video_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Additional metadata as JSON
    post_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Metrics fields added by migration
    content_length: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    post_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    has_media: Mapped[Optional[bool]] = mapped_column(Boolean, default=False)
    facebook_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    detected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    group_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    group_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Relationship to chat conversations
    chats: Mapped[list["Chat"]] = relationship(
        "Chat",
        back_populates="post",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # Relationship to post media
    media: Mapped[list["PostMedia"]] = relationship(
        "PostMedia",
        back_populates="post",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<Post(post_id={self.post_id}, verdict={self.verdict}, confidence={self.confidence})>"


class Chat(Base):
    """Chat model for storing conversations about analyzed posts."""

    __tablename__ = "chat"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Reference to the post table's post_id
    post_id: Mapped[str] = mapped_column(
        ForeignKey("post.post_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Reference to user directly for persistent conversations
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Role: 'user' or 'assistant'
    role: Mapped[str] = mapped_column(String(20), nullable=False)

    # Chat message content
    message: Mapped[str] = mapped_column(Text, nullable=False)

    # Gemini file URIs for uploaded images (JSON array)
    file_uris: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)

    # Relationship to post
    post: Mapped["Post"] = relationship(
        "Post",
        back_populates="chats",
        lazy="selectin",
    )

    # Relationship to user
    user: Mapped["User"] = relationship(
        "User",
        back_populates="chats",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<Chat(id={self.id}, post_id={self.post_id}, role={self.role})>"


class UserSession(Base):
    """User session model for tracking individual extension users."""

    __tablename__ = "user_session"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Unique identifier from browser (UUID)
    user_identifier: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)

    # Last activity timestamp
    last_active: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<UserSession(id={self.id}, user_identifier={self.user_identifier})>"


class PostMedia(Base):
    """Post media model for storing image and video URLs from Facebook posts."""

    __tablename__ = "post_media"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Reference to the post table's post_id
    post_id: Mapped[str] = mapped_column(
        ForeignKey("post.post_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Media type: 'image' or 'video'
    media_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    # Original media URL from Facebook
    media_url: Mapped[str] = mapped_column(Text, nullable=False)

    # Thumbnail URL (optional)
    thumbnail_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Media dimensions
    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # File metadata
    file_size: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Gemini File API URI for pre-uploaded media
    gemini_file_uri: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Storage path for downloaded media (local file path)
    storage_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Storage type: reserved for future use (currently 'local')
    storage_type: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    # Content hash for deduplication
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    # Normalized URL for Facebook URL deduplication
    normalized_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True, index=True)

    # Relationship to post
    post: Mapped["Post"] = relationship(
        "Post",
        back_populates="media",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<PostMedia(id={self.id}, post_id={self.post_id}, media_type={self.media_type})>"


class User(Base):
    """User model for storing extension users with behavioral metrics."""

    __tablename__ = "user"

    # Primary key is the user_id from browser extension (UUID)
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Browser and environment information
    browser_info: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    timezone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    locale: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    # A/B testing groups
    experiment_groups: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)

    # Activity tracking
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    last_active_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships

    chats: Mapped[list["Chat"]] = relationship(
        "Chat",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    events: Mapped[list["AnalyticsEvent"]] = relationship(
        "AnalyticsEvent",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<User(id={self.id})>"

    # Legacy analytics models removed (consolidated into analytics_event)


class AnalyticsEvent(Base):
    """Analytics event model for granular event tracking."""

    __tablename__ = "analytics_event"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Foreign keys (all optional to support various event types)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Single session identifier (generated via /users/session/initialize)
    session_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)

    post_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("post.post_id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Event data
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    event_category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)  # 'interaction', 'performance', 'error'
    event_priority: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)  # 'critical', 'high', 'medium', 'low'
    event_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    event_label: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # New: unified event data payload (JSONB for GIN indexing)
    event_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Timestamps
    client_timestamp: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    server_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # Relationships
    user: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="events",
        lazy="selectin",
    )

    # Legacy session relationship removed in consolidated analytics

    post: Mapped[Optional["Post"]] = relationship(
        "Post",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<AnalyticsEvent(id={self.id}, event_type={self.event_type})>"
