"""added repo_data to run

Revision ID: dae910bd9587
Revises: 2dd5cf2d12dc
Create Date: 2021-01-06 08:48:41.813706

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'dae910bd9587'
down_revision = '2dd5cf2d12dc'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('runs', sa.Column('repo_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade():
    op.drop_column('runs', 'repo_data')
