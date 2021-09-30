"""removed enabled from projects

Revision ID: 1f5039135dd8
Revises: ab9326d5fc02
Create Date: 2021-06-20 11:17:17.259316

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '1f5039135dd8'
down_revision = 'ab9326d5fc02'
branch_labels = None
depends_on = None


def upgrade():
    with op.get_context().autocommit_block():
        try:
            op.drop_column('projects', 'enabled')
        except Exception:
            pass

    with op.get_context().autocommit_block():
        try:
            op.drop_constraint("systems_executor_key", "systems", type_="unique")
        except Exception:
            pass

    with op.get_context().autocommit_block():
        try:
            op.drop_constraint("systems_name_key", "systems", type_="unique")
        except Exception:
            pass


    with op.get_context().autocommit_block():
        try:
            op.drop_column('flows', 'trigger_data')
        except Exception:
            pass

    with op.get_context().autocommit_block():
        try:
            op.drop_column('runs', 'repo_data')
        except Exception:
            pass

    with op.get_context().autocommit_block():
        try:
            op.alter_column('jobs', 'system_id',
                            nullable=False,
                            existing_nullable=True)
        except Exception:
            pass


def downgrade():
    op.add_column('projects', sa.Column('enabled', sa.Boolean))
