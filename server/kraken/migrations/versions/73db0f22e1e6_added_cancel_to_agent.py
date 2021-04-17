"""added cancel to agent

Revision ID: 73db0f22e1e6
Revises: 89ffd52f1f00
Create Date: 2020-09-19 07:28:37.769815

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '73db0f22e1e6'
down_revision = '89ffd52f1f00'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('agents', sa.Column('cancel', sa.Boolean(), nullable=True))


def downgrade():
    op.drop_column('agents', 'cancel')
