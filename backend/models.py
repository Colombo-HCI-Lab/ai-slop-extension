"""Database models for AI Slop Detection backend."""

import uuid
from datetime import datetime
from typing import Any, List, Optional

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, JSON, String, Text, func
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

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    # Reference to the post table's post_id
    post_id: Mapped[str] = mapped_column(
        ForeignKey("post.post_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Reference to user session (optional for backward compatibility)
    user_session_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("user_session.id", ondelete="SET NULL"),
        nullable=True,
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

    # Relationship to user session
    user_session: Mapped[Optional["UserSession"]] = relationship(
        "UserSession",
        back_populates="chats",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<Chat(id={self.id}, post_id={self.post_id}, role={self.role})>"


class UserSession(Base):
    """User session model for tracking individual extension users."""

    __tablename__ = "user_session"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    # Unique identifier from browser (UUID)
    user_identifier: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)

    # Last activity timestamp
    last_active: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationship to chat conversations
    chats: Mapped[list["Chat"]] = relationship(
        "Chat",
        back_populates="user_session",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<UserSession(id={self.id}, user_identifier={self.user_identifier})>"


class PostMedia(Base):
    """Post media model for storing image and video URLs from Facebook posts."""

    __tablename__ = "post_media"

    id: Mapped[str] = mapped_column(
        String(64),  # Increased length to accommodate Facebook IDs (fb_xxxxx format)
        primary_key=True,
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

    # Storage path for downloaded media (GCS URI or local file path)
    storage_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Storage type: 'gcs' or 'local'
    storage_type: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    # Relationship to post
    post: Mapped["Post"] = relationship(
        "Post",
        back_populates="media",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<PostMedia(id={self.id}, post_id={self.post_id}, media_type={self.media_type})>"
