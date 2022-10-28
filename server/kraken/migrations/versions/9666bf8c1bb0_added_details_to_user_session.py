"""added details to user session

Revision ID: 9666bf8c1bb0
Revises: 2996b1b6e227
Create Date: 2022-10-23 08:20:15.282445

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '9666bf8c1bb0'
down_revision = '2996b1b6e227'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('user_sessions', sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade():
    op.drop_column('user_sessions', 'details')
