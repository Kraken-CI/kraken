"""add enabled to Stage

Revision ID: 0731897c862e
Revises:
Create Date: 2019-12-22 17:39:27.154403

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0731897c862e'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('stages', sa.Column('enabled', sa.Boolean, default=True))


def downgrade():
    op.drop_column('stages', 'enabled')
