"""added last_seen to Executor

Revision ID: ff4a425a6070
Revises: 735e81eedae4
Create Date: 2020-01-13 07:24:56.514075

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'ff4a425a6070'
down_revision = '735e81eedae4'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('executors', sa.Column('last_seen', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('executors', 'last_seen')
