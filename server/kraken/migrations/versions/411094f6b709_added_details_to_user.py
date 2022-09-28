"""added details to user

Revision ID: 411094f6b709
Revises: 0615faca43b1
Create Date: 2022-09-27 20:55:12.280567

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '411094f6b709'
down_revision = '0615faca43b1'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade():
    op.drop_column('users', 'details')
