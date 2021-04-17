"""added system to Job

Revision ID: 1982be95e79f
Revises: 3c1af14e0370
Create Date: 2020-01-18 08:09:39.372105

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '1982be95e79f'
down_revision = '3c1af14e0370'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('jobs', sa.Column('system', sa.Unicode(length=200), nullable=True))


def downgrade():
    op.drop_column('jobs', 'system')
