"""added label to run

Revision ID: 466de256799e
Revises: d2b23f410d02
Create Date: 2020-09-26 20:36:07.063973

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '466de256799e'
down_revision = 'd2b23f410d02'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('runs', sa.Column('label', sa.Unicode(length=200), nullable=True))


def downgrade():
    op.drop_column('runs', 'label')
