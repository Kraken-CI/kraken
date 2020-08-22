"""added timeouts to Stage and Job

Revision ID: 3c1af14e0370
Revises: ff4a425a6070
Create Date: 2020-01-14 07:26:17.893236

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '3c1af14e0370'
down_revision = 'ff4a425a6070'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('jobs', sa.Column('timeout', sa.Integer(), nullable=True))
    op.add_column('stages', sa.Column('timeouts', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade():
    op.drop_column('stages', 'timeouts')
    op.drop_column('jobs', 'timeout')
