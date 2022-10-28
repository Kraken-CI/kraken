"""user is session nullable

Revision ID: 2996b1b6e227
Revises: 87358b464400
Create Date: 2022-10-22 09:39:57.125878

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2996b1b6e227'
down_revision = '87358b464400'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('user_sessions', 'user_id',
               existing_type=sa.INTEGER(),
               nullable=True)


def downgrade():
    op.alter_column('user_sessions', 'user_id',
               existing_type=sa.INTEGER(),
               nullable=False)
