"""removed cancel from agent

Revision ID: 38088514157a
Revises: 73db0f22e1e6
Create Date: 2020-09-20 06:56:12.245924

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '38088514157a'
down_revision = '73db0f22e1e6'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column('agents', 'cancel')


def downgrade():
    op.add_column('agents', sa.Column('cancel', sa.BOOLEAN(), autoincrement=False, nullable=True))
