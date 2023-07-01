"""added fields_raw to step

Revision ID: 9e57e0f30a5f
Revises: b510fae321ba
Create Date: 2023-06-30 14:28:08.251557

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '9e57e0f30a5f'
down_revision = 'b510fae321ba'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('steps', sa.Column('fields_raw', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade():
    op.drop_column('steps', 'fields_raw')
