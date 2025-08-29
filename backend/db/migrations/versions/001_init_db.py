"""Initialize database

Revision ID: 001_init_db
Revises:
Create Date: 2025-08-23 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001_init_db"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create user table with behavioral metrics
    op.create_table(
        "user",
        sa.Column("id", sa.String(36), primary_key=True),  # This will be the user_id from browser extension
        sa.Column("avg_scroll_speed", sa.Float()),
        sa.Column("avg_posts_per_minute", sa.Float()),
        sa.Column("total_posts_viewed", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_interactions", sa.Integer(), server_default="0", nullable=False),
        sa.Column("browser_info", sa.JSON()),
        sa.Column("timezone", sa.String(50)),
        sa.Column("locale", sa.String(10)),
        sa.Column("experiment_groups", sa.JSON()),  # For A/B testing
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_active_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # Create enhanced post table
    op.create_table(
        "post",
        sa.Column("post_id", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("author", sa.String(length=255), nullable=True),
        sa.Column("verdict", sa.String(length=50), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("text_ai_probability", sa.Float(), nullable=True),
        sa.Column("text_confidence", sa.Float(), nullable=True),
        sa.Column("image_ai_probability", sa.Float(), nullable=True),
        sa.Column("image_confidence", sa.Float(), nullable=True),
        sa.Column("video_ai_probability", sa.Float(), nullable=True),
        sa.Column("video_confidence", sa.Float(), nullable=True),
        sa.Column("post_metadata", sa.JSON(), nullable=True),
        # Enhanced post fields
        sa.Column("content_length", sa.Integer()),
        sa.Column("post_type", sa.String(50)),
        sa.Column("has_media", sa.Boolean(), default=False),
        sa.Column("facebook_url", sa.Text()),
        sa.Column("content_hash", sa.String(64)),
        sa.Column("detected_at", sa.DateTime(timezone=True)),
        sa.Column("group_id", sa.String(255)),
        sa.Column("group_name", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("post_id"),
    )
    op.create_index(op.f("ix_post_post_id"), "post", ["post_id"], unique=False)
    op.create_index("ix_post_content_hash", "post", ["content_hash"])
    op.create_index("ix_post_detected_at", "post", ["detected_at"])
    op.create_index("ix_post_group_id", "post", ["group_id"])

    op.create_table(
        "user_session",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_identifier", sa.String(length=255), nullable=False),
        sa.Column("last_active", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_user_session_user_identifier"), "user_session", ["user_identifier"], unique=True)

    # Create chat table with user_id reference (not user_session_id)
    op.create_table(
        "chat",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("post_id", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),  # Direct user reference
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("file_uris", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["post_id"], ["post.post_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_chat_post_id"), "chat", ["post_id"], unique=False)
    op.create_index("ix_chat_user_id", "chat", ["user_id"], unique=False)

    # User post analytics table
    op.create_table(
        "user_post_analytics",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("post_id", sa.String(255), sa.ForeignKey("post.post_id", ondelete="CASCADE"), nullable=False),
        sa.Column("interaction_type", sa.String(20), default="viewed"),
        sa.Column("backend_response_time_ms", sa.Integer()),
        sa.Column("time_to_interaction_ms", sa.Integer()),
        sa.Column("icon_visibility_duration_ms", sa.Integer()),
        sa.Column("reading_time_ms", sa.Integer()),
        sa.Column("scroll_depth_percentage", sa.Float()),
        sa.Column("viewport_time_ms", sa.Integer()),
        sa.Column("chat_session_count", sa.Integer(), default=0),
        sa.Column("total_chat_duration_ms", sa.Integer(), default=0),
        sa.Column("total_messages_sent", sa.Integer(), default=0),
        sa.Column("suggested_questions_used", sa.Integer(), default=0),
        sa.Column("accuracy_feedback", sa.String(20)),  # 'correct', 'incorrect', 'unsure'
        sa.Column("times_viewed", sa.Integer(), default=1),
        sa.Column("first_viewed_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("last_viewed_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("interaction_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("user_id", "post_id", name="uq_user_post"),
    )
    op.create_index("ix_user_post_analytics_user_id", "user_post_analytics", ["user_id"])
    op.create_index("ix_user_post_analytics_post_id", "user_post_analytics", ["post_id"])
    op.create_index("ix_user_post_analytics_interaction", "user_post_analytics", ["interaction_type"])
    op.create_index("ix_user_post_analytics_viewed_at", "user_post_analytics", ["first_viewed_at"])

    # Enhanced user session analytics table
    op.create_table(
        "user_session_analytics",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_token", sa.String(255), unique=True),
        sa.Column("ip_hash", sa.String(64)),  # Hashed IP for geographic analytics
        sa.Column("user_agent", sa.Text()),
        sa.Column("duration_seconds", sa.Integer()),
        sa.Column("posts_viewed", sa.Integer(), default=0),
        sa.Column("posts_analyzed", sa.Integer(), default=0),
        sa.Column("posts_interacted", sa.Integer(), default=0),
        sa.Column("avg_scroll_speed", sa.Float()),
        sa.Column("avg_posts_per_minute", sa.Float()),
        sa.Column("total_scroll_distance", sa.Integer()),
        sa.Column("active_time_seconds", sa.Integer()),
        sa.Column("idle_time_seconds", sa.Integer()),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("end_reason", sa.String(50)),  # 'user_logout', 'timeout', 'browser_close'
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_user_session_analytics_user_id", "user_session_analytics", ["user_id"])
    op.create_index("ix_user_session_analytics_started_at", "user_session_analytics", ["started_at"])
    op.create_index("ix_user_session_analytics_token", "user_session_analytics", ["session_token"])

    # User post chat analytics table
    op.create_table(
        "user_post_chat_analytics",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_post_analytics_id", sa.String(36), sa.ForeignKey("user_post_analytics.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_token", sa.String(255), unique=True),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("message_count", sa.Integer(), default=0),
        sa.Column("user_message_count", sa.Integer(), default=0),
        sa.Column("assistant_message_count", sa.Integer(), default=0),
        sa.Column("suggested_question_clicks", sa.Integer(), default=0),
        sa.Column("average_response_time_ms", sa.Integer()),
        sa.Column("max_response_time_ms", sa.Integer()),
        sa.Column("ended_by", sa.String(20), default="close"),
        sa.Column("satisfaction_rating", sa.Integer()),  # 1-5 scale
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_user_post_chat_analytics_id", "user_post_chat_analytics", ["user_post_analytics_id"])
    op.create_index("ix_user_post_chat_analytics_started_at", "user_post_chat_analytics", ["started_at"])

    # Analytics event table for granular tracking
    op.create_table(
        "analytics_event",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("user.id", ondelete="CASCADE")),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("user_session_analytics.id", ondelete="CASCADE")),
        sa.Column("post_id", sa.String(255), sa.ForeignKey("post.post_id", ondelete="CASCADE")),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("event_category", sa.String(50)),  # 'interaction', 'performance', 'error'
        sa.Column("event_value", sa.Float()),
        sa.Column("event_label", sa.String(255)),
        sa.Column("event_metadata", sa.JSON()),
        sa.Column("client_timestamp", sa.DateTime(timezone=True)),
        sa.Column("server_timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_analytics_event_user_type", "analytics_event", ["user_id", "event_type"])
    op.create_index("ix_analytics_event_created", "analytics_event", ["created_at"])
    op.create_index("ix_analytics_event_post", "analytics_event", ["post_id"])
    op.create_index("ix_analytics_event_session", "analytics_event", ["session_id"])
    op.create_index("ix_analytics_event_category", "analytics_event", ["event_category"])

    op.create_table(
        "post_media",
        sa.Column("id", sa.String(length=64), nullable=False),  # Combined: length=64 from second migration
        sa.Column("post_id", sa.String(length=255), nullable=False),
        sa.Column("media_type", sa.String(length=20), nullable=False),
        sa.Column("media_url", sa.Text(), nullable=False),
        sa.Column("thumbnail_url", sa.Text(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("mime_type", sa.String(length=100), nullable=True),
        sa.Column("gemini_file_uri", sa.Text(), nullable=True),
        sa.Column("storage_path", sa.Text(), nullable=True),  # Combined: renamed from local_file_path
        sa.Column("storage_type", sa.String(length=10), nullable=True),  # Combined: added from GCS migration
        # Merged from 002_add_content_dedup_fields
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("normalized_url", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["post_id"], ["post.post_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_post_media_media_type"), "post_media", ["media_type"], unique=False)
    op.create_index(op.f("ix_post_media_post_id"), "post_media", ["post_id"], unique=False)
    # Composite indexes to speed common queries
    op.create_index("ix_post_media_post_type", "post_media", ["post_id", "media_type"], unique=False)
    op.create_index("ix_post_media_post_gemini_uri", "post_media", ["post_id", "gemini_file_uri"], unique=False)
    # Single-column indexes for deduplication fields (merged from 002)
    op.create_index("ix_post_media_content_hash", "post_media", ["content_hash"], unique=False)
    op.create_index("ix_post_media_normalized_url", "post_media", ["normalized_url"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop all tables in reverse dependency order
    op.drop_table("post_media")
    op.drop_table("analytics_event")
    op.drop_table("user_post_chat_analytics")
    op.drop_table("user_session_analytics")
    op.drop_table("user_post_analytics")
    op.drop_table("chat")
    op.drop_table("user_session")
    op.drop_table("post")
    op.drop_table("user")
