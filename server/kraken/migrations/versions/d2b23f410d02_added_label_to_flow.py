"""added label to flow

Revision ID: d2b23f410d02
Revises: 4a7ac9143bb1
Create Date: 2020-09-26 17:17:27.078419

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'd2b23f410d02'
down_revision = '4a7ac9143bb1'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('flows', sa.Column('label', sa.Unicode(length=200), nullable=True))


def downgrade():
    op.drop_column('flows', 'label')
