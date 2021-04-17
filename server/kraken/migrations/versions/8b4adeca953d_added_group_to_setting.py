"""added group to Setting

Revision ID: 8b4adeca953d
Revises: 8200318b9e18
Create Date: 2020-02-08 12:44:36.855759

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '8b4adeca953d'
down_revision = '8200318b9e18'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('settings', sa.Column('group', sa.VARCHAR(length=50), autoincrement=False, nullable=True))


def downgrade():
    op.drop_column('settings', 'group')
