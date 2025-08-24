"""Add content deduplication fields

Revision ID: 002_add_content_dedup_fields
Revises: 001_init_db
Create Date: 2025-08-24 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002_add_content_dedup_fields"
down_revision: Union[str, Sequence[str], None] = "001_init_db"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add content deduplication fields to post_media table."""
    # Add content_hash field for deduplication
    op.add_column('post_media', sa.Column('content_hash', sa.String(length=64), nullable=True))
    op.create_index('ix_post_media_content_hash', 'post_media', ['content_hash'])
    
    # Add normalized_url field for Facebook URL deduplication
    op.add_column('post_media', sa.Column('normalized_url', sa.Text(), nullable=True))
    op.create_index('ix_post_media_normalized_url', 'post_media', ['normalized_url'])


def downgrade() -> None:
    """Remove content deduplication fields from post_media table."""
    op.drop_index('ix_post_media_normalized_url', 'post_media')
    op.drop_column('post_media', 'normalized_url')
    op.drop_index('ix_post_media_content_hash', 'post_media')
    op.drop_column('post_media', 'content_hash')