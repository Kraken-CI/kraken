"""added authorized to Executor

Revision ID: 67d4f5a5ee98
Revises: 0ad7507aa6d0
Create Date: 2020-01-06 18:50:52.689999

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '67d4f5a5ee98'
down_revision = '0ad7507aa6d0'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('executors', sa.Column('authorized', sa.Boolean(), nullable=True))


def downgrade():
    op.drop_column('executors', 'authorized')
