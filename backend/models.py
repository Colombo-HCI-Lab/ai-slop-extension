"""Database models for AI Slop Detection backend."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import DateTime, Float, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base model class with common fields."""

    __abstract__ = True

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
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

    # Facebook post ID (numeric string from URL)
    post_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)

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

    def __repr__(self) -> str:
        """String representation."""
        return f"<Post(id={self.id}, post_id={self.post_id}, verdict={self.verdict}, confidence={self.confidence})>"


class Chat(Base):
    """Chat model for storing conversations about analyzed posts."""

    __tablename__ = "chat"

    # Reference to the post table's internal id
    post_db_id: Mapped[str] = mapped_column(
        ForeignKey("post.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Role: 'user' or 'assistant'
    role: Mapped[str] = mapped_column(String(20), nullable=False)

    # Chat message content
    message: Mapped[str] = mapped_column(Text, nullable=False)

    # Relationship to post
    post: Mapped["Post"] = relationship(
        "Post",
        back_populates="chats",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<Chat(id={self.id}, post_db_id={self.post_db_id}, role={self.role})>"
