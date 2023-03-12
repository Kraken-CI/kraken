"""update Stage.enabled to true

Revision ID: ba436d491bf8
Revises: 0731897c862e
Create Date: 2019-12-22 19:00:15.365002

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'ba436d491bf8'
down_revision = '0731897c862e'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE stages SET enabled = TRUE")


def downgrade():
    pass
