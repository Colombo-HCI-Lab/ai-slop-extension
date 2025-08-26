"""Add missing updated_at columns to analytics tables

Revision ID: 003
Revises: 002_add_metrics_tables
Create Date: 2025-08-26

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002_add_metrics_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add missing updated_at columns to analytics tables."""
    
    # Add updated_at column to analytics_event table
    op.add_column('analytics_event', sa.Column('updated_at', sa.DateTime(timezone=True), 
                                                server_default=sa.func.now(), 
                                                nullable=False))
    
    # Add updated_at column to performance_metric table  
    op.add_column('performance_metric', sa.Column('updated_at', sa.DateTime(timezone=True),
                                                   server_default=sa.func.now(),
                                                   nullable=False))


def downgrade() -> None:
    """Remove updated_at columns from analytics tables."""
    op.drop_column('analytics_event', 'updated_at')
    op.drop_column('performance_metric', 'updated_at')