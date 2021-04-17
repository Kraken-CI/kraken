"""added last flows to branch

Revision ID: 26c6d691e7ce
Revises: 5b13b262b132
Create Date: 2021-04-10 23:15:08.698459

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '26c6d691e7ce'
down_revision = '5b13b262b132'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('branches', sa.Column('ci_last_completed_flow_id', sa.Integer(), nullable=True))
    op.add_column('branches', sa.Column('ci_last_incomplete_flow_id', sa.Integer(), nullable=True))
    op.create_foreign_key('branches_ci_last_incomplete_flow_id_fkey', 'branches', 'flows', ['ci_last_incomplete_flow_id'], ['id'])
    op.create_foreign_key('branches_ci_last_completed_flow_id_fkey', 'branches', 'flows', ['ci_last_completed_flow_id'], ['id'])


def downgrade():
    op.drop_constraint('branches_ci_last_incomplete_flow_id_fkey', 'branches', type_='foreignkey')
    op.drop_constraint('branches_ci_last_completed_flow_id_fkey', 'branches', type_='foreignkey')
    op.drop_column('branches', 'ci_last_incomplete_flow_id')
    op.drop_column('branches', 'ci_last_completed_flow_id')
