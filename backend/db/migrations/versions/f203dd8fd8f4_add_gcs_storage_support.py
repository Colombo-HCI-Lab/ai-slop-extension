"""Add GCS storage support

Revision ID: f203dd8fd8f4
Revises: 2449353db8c6
Create Date: 2025-08-24 00:52:28.834821

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f203dd8fd8f4'
down_revision: Union[str, Sequence[str], None] = '2449353db8c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Rename local_file_path to storage_path to support both GCS and local storage
    op.alter_column('post_media', 'local_file_path', new_column_name='storage_path')
    
    # Add storage_type column to distinguish between 'gcs' and 'local' storage
    op.add_column('post_media', sa.Column('storage_type', sa.String(10), nullable=True))
    
    # Set default values for existing records (local storage)
    op.execute("UPDATE post_media SET storage_type = 'local' WHERE storage_path IS NOT NULL")


def downgrade() -> None:
    """Downgrade schema."""
    # Remove storage_type column
    op.drop_column('post_media', 'storage_type')
    
    # Rename storage_path back to local_file_path
    op.alter_column('post_media', 'storage_path', new_column_name='local_file_path')
