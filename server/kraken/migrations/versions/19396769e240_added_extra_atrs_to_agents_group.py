"""added extra_atrs to agents group

Revision ID: 19396769e240
Revises: a26a02d0ac01
Create Date: 2021-05-05 06:47:10.502139

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '19396769e240'
down_revision = 'a26a02d0ac01'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('agents_groups', sa.Column('extra_attrs', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade():
    op.drop_column('agents_groups', 'extra_attrs')
