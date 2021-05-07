"""added extra_atrs to agents

Revision ID: a26a02d0ac01
Revises: 050fbc3d126c
Create Date: 2021-05-05 06:32:20.203580

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'a26a02d0ac01'
down_revision = '050fbc3d126c'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('agents', sa.Column('extra_attrs', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade():
    op.drop_column('agents', 'extra_attrs')
