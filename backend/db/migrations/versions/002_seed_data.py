"""Seed database with sample data

Revision ID: 002_seed_data
Revises: 001_init_db
Create Date: 2025-08-30 00:00:00.000000

"""

import os
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002_seed_data"
down_revision: Union[str, Sequence[str], None] = "001_init_db"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _get_seed_data_path() -> str:
    """Get the path to the seed_data directory."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
    return os.path.join(backend_dir, "seed_data")


def _load_sql_file(filename: str) -> str:
    """Load SQL content from a file."""
    seed_data_path = _get_seed_data_path()
    file_path = os.path.join(seed_data_path, filename)
    with open(file_path, "r") as f:
        return f.read()


def upgrade() -> None:
    """Upgrade schema."""
    # # Load and execute post data
    # post_sql = _load_sql_file("post.sql")
    # op.execute(post_sql)
    #
    # # Load and execute post_media data
    # post_media_sql = _load_sql_file("post_media.sql")
    # op.execute(post_media_sql)
    pass


def downgrade() -> None:
    """Downgrade schema."""
    # Delete all seed data (post_media first due to foreign key constraint)
    op.execute("DELETE FROM post_media")
    op.execute("DELETE FROM post")
