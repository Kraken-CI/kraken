"""added deployment to agents group

Revision ID: 050fbc3d126c
Revises: 26c6d691e7ce
Create Date: 2021-05-03 11:31:59.682708

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '050fbc3d126c'
down_revision = '26c6d691e7ce'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('agents_groups', sa.Column('deployment', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade():
    op.drop_column('agents_groups', 'deployment')
