"""Initial migration: Migrate from Prisma to SQLAlchemy

This migration transforms the database schema from Prisma ORM format
to SQLAlchemy format with the following changes:

1. Removes Prisma migration tracking table
2. Updates Post table:
   - Renames postId -> post_id with proper indexing
   - Renames metadata -> post_metadata (JSON type)
   - Updates timestamp columns (createdAt/updatedAt -> created_at/updated_at)
   - Adds proper string length constraints for performance
3. Updates Chat table:
   - Renames postDbId -> post_db_id with proper foreign key
   - Updates timestamp columns and string constraints
   - Adds proper CASCADE delete behavior

Revision ID: b870b7a7fd72
Revises:
Create Date: 2025-08-18 13:45:34.376003
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Revision identifiers, used by Alembic
revision: str = "b870b7a7fd72"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema from Prisma to SQLAlchemy format."""

    # ========================================
    # Remove Prisma migration tracking table
    # ========================================
    op.drop_table("_prisma_migrations")

    # ========================================
    # Update POST table schema
    # ========================================

    # Add new SQLAlchemy-style columns
    op.add_column("post", sa.Column("post_id", sa.String(length=255), nullable=False))
    op.add_column("post", sa.Column("post_metadata", sa.JSON(), nullable=True))
    op.add_column("post", sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False))
    op.add_column("post", sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False))

    # Update existing columns with proper constraints
    op.alter_column("post", "id", existing_type=sa.TEXT(), type_=sa.String(length=36), existing_nullable=False)
    op.alter_column("post", "author", existing_type=sa.TEXT(), type_=sa.String(length=255), existing_nullable=True)
    op.alter_column("post", "verdict", existing_type=sa.TEXT(), type_=sa.String(length=50), existing_nullable=False)

    # Update indexes
    op.drop_index(op.f("post_postId_key"), table_name="post")
    op.create_index(op.f("ix_post_post_id"), "post", ["post_id"], unique=True)

    # Remove old Prisma columns
    op.drop_column("post", "postId")
    op.drop_column("post", "metadata")
    op.drop_column("post", "createdAt")
    op.drop_column("post", "updatedAt")

    # ========================================
    # Update CHAT table schema
    # ========================================

    # Add new SQLAlchemy-style columns
    op.add_column("chat", sa.Column("post_db_id", sa.String(length=36), nullable=False))
    op.add_column("chat", sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False))
    op.add_column("chat", sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False))

    # Update existing columns with proper constraints
    op.alter_column("chat", "id", existing_type=sa.TEXT(), type_=sa.String(length=36), existing_nullable=False)
    op.alter_column("chat", "role", existing_type=sa.TEXT(), type_=sa.String(length=20), existing_nullable=False)

    # Update foreign key relationship with CASCADE delete
    op.drop_constraint(op.f("chat_postDbId_fkey"), "chat", type_="foreignkey")
    op.create_foreign_key(None, "chat", "post", ["post_db_id"], ["id"], ondelete="CASCADE")

    # Add index for foreign key performance
    op.create_index(op.f("ix_chat_post_db_id"), "chat", ["post_db_id"], unique=False)

    # Remove old Prisma columns
    op.drop_column("chat", "postDbId")
    op.drop_column("chat", "createdAt")


def downgrade() -> None:
    """Downgrade schema back to Prisma format.

    WARNING: This will revert to the original Prisma schema format.
    This should only be used in development environments.
    """

    # ========================================
    # Restore CHAT table to Prisma format
    # ========================================

    # Add back Prisma-style columns
    op.add_column("chat", sa.Column("postDbId", sa.TEXT(), autoincrement=False, nullable=False))
    op.add_column(
        "chat",
        sa.Column(
            "createdAt", postgresql.TIMESTAMP(precision=3), server_default=sa.text("CURRENT_TIMESTAMP"), autoincrement=False, nullable=False
        ),
    )

    # Revert column constraints
    op.alter_column("chat", "id", existing_type=sa.String(length=36), type_=sa.TEXT(), existing_nullable=False)
    op.alter_column("chat", "role", existing_type=sa.String(length=20), type_=sa.TEXT(), existing_nullable=False)

    # Restore original foreign key
    op.drop_constraint(None, "chat", type_="foreignkey")
    op.create_foreign_key(op.f("chat_postDbId_fkey"), "chat", "post", ["postDbId"], ["id"], onupdate="CASCADE", ondelete="CASCADE")

    # Remove SQLAlchemy-style elements
    op.drop_index(op.f("ix_chat_post_db_id"), table_name="chat")
    op.drop_column("chat", "post_db_id")
    op.drop_column("chat", "created_at")
    op.drop_column("chat", "updated_at")

    # ========================================
    # Restore POST table to Prisma format
    # ========================================

    # Add back Prisma-style columns
    op.add_column("post", sa.Column("postId", sa.TEXT(), autoincrement=False, nullable=False))
    op.add_column("post", sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=True))
    op.add_column("post", sa.Column("updatedAt", postgresql.TIMESTAMP(precision=3), autoincrement=False, nullable=False))
    op.add_column(
        "post",
        sa.Column(
            "createdAt", postgresql.TIMESTAMP(precision=3), server_default=sa.text("CURRENT_TIMESTAMP"), autoincrement=False, nullable=False
        ),
    )

    # Revert column constraints
    op.alter_column("post", "id", existing_type=sa.String(length=36), type_=sa.TEXT(), existing_nullable=False)
    op.alter_column("post", "verdict", existing_type=sa.String(length=50), type_=sa.TEXT(), existing_nullable=False)
    op.alter_column("post", "author", existing_type=sa.String(length=255), type_=sa.TEXT(), existing_nullable=True)

    # Restore original indexes
    op.drop_index(op.f("ix_post_post_id"), table_name="post")
    op.create_index(op.f("post_postId_key"), "post", ["postId"], unique=True)

    # Remove SQLAlchemy-style columns
    op.drop_column("post", "post_id")
    op.drop_column("post", "post_metadata")
    op.drop_column("post", "created_at")
    op.drop_column("post", "updated_at")

    # ========================================
    # Restore Prisma migration tracking table
    # ========================================
    op.create_table(
        "_prisma_migrations",
        sa.Column("id", sa.VARCHAR(length=36), autoincrement=False, nullable=False),
        sa.Column("checksum", sa.VARCHAR(length=64), autoincrement=False, nullable=False),
        sa.Column("finished_at", postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
        sa.Column("migration_name", sa.VARCHAR(length=255), autoincrement=False, nullable=False),
        sa.Column("logs", sa.TEXT(), autoincrement=False, nullable=True),
        sa.Column("rolled_back_at", postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
        sa.Column("started_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), autoincrement=False, nullable=False),
        sa.Column("applied_steps_count", sa.INTEGER(), server_default=sa.text("0"), autoincrement=False, nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("_prisma_migrations_pkey")),
    )
