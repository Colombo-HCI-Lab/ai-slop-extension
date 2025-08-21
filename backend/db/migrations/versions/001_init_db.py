"""init_db

Revision ID: 001_init_db
Revises:
Create Date: 2025-08-21 08:35:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "001_init_db"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create post table
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
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_post_post_id"), "post", ["post_id"], unique=True)

    # Create user_session table
    op.create_table(
        "user_session",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_identifier", sa.String(255), unique=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("last_active", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_user_session_user_identifier", "user_session", ["user_identifier"], unique=True)

    # Create post_media table
    op.create_table(
        "post_media",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("post_db_id", sa.String(36), sa.ForeignKey("post.id", ondelete="CASCADE"), nullable=False),
        sa.Column("media_type", sa.String(20), nullable=False),
        sa.Column("media_url", sa.Text, nullable=False),
        sa.Column("thumbnail_url", sa.Text, nullable=True),
        sa.Column("width", sa.Integer, nullable=True),
        sa.Column("height", sa.Integer, nullable=True),
        sa.Column("file_size", sa.BigInteger, nullable=True),
        sa.Column("mime_type", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index("ix_post_media_post_db_id", "post_media", ["post_db_id"])
    op.create_index("ix_post_media_media_type", "post_media", ["media_type"])

    # Create chat table
    op.create_table(
        "chat",
        sa.Column("post_db_id", sa.String(length=36), nullable=False),
        sa.Column("user_session_id", sa.String(36), sa.ForeignKey("user_session.id", ondelete="SET NULL"), nullable=True),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("file_uris", sa.JSON, nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["post_db_id"], ["post.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_chat_post_db_id"), "chat", ["post_db_id"], unique=False)
    op.create_index("ix_chat_user_session_id", "chat", ["user_session_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop tables in reverse order
    op.drop_index("ix_chat_user_session_id", table_name="chat")
    op.drop_index(op.f("ix_chat_post_db_id"), table_name="chat")
    op.drop_table("chat")

    op.drop_index("ix_post_media_media_type", table_name="post_media")
    op.drop_index("ix_post_media_post_db_id", table_name="post_media")
    op.drop_table("post_media")

    op.drop_index("ix_user_session_user_identifier", table_name="user_session")
    op.drop_table("user_session")

    op.drop_index(op.f("ix_post_post_id"), table_name="post")
    op.drop_table("post")
