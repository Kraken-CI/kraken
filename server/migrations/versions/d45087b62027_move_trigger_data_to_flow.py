"""move trigger_data to Flow

Revision ID: d45087b62027
Revises: b5cc62f79980
Create Date: 2019-12-27 07:24:54.315303

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'd45087b62027'
down_revision = 'b5cc62f79980'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('flows', sa.Column('trigger_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.drop_column('runs', 'trigger_data')


def downgrade():
    op.add_column('runs', sa.Column('trigger_data', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=True))
    op.drop_column('flows', 'trigger_data')
