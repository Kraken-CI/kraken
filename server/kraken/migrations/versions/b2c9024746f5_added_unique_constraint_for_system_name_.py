"""added unique constraint for system name and executor

Revision ID: b2c9024746f5
Revises: 1f5039135dd8
Create Date: 2021-06-20 12:17:02.966101

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = 'b2c9024746f5'
down_revision = '1f5039135dd8'
branch_labels = None
depends_on = None


def upgrade():
    with op.get_context().autocommit_block():
        try:
            op.create_unique_constraint('uq_system_name_executor', 'systems', ['name', 'executor'])
        except Exception:
            pass


def downgrade():
    op.drop_constraint('uq_system_name_executor', 'systems', type_='unique')
