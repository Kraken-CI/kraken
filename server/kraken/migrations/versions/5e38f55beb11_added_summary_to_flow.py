"""added summary to flow

Revision ID: 5e38f55beb11
Revises: 899dadc28f9c
Create Date: 2022-03-26 14:08:23.398591

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '5e38f55beb11'
down_revision = '899dadc28f9c'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('flows', sa.Column('summary', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade():
    op.drop_column('flows', 'summary')
