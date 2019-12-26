"""add extra to Issue

Revision ID: b5cc62f79980
Revises: 1cf31ab18f84
Create Date: 2019-12-26 11:17:33.681018

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'b5cc62f79980'
down_revision = '1cf31ab18f84'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('issues', sa.Column('extra', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade():
    op.drop_column('issues', 'extra')
