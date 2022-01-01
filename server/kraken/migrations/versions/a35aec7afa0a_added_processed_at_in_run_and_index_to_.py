"""added processed_at in run and index to tcr

Revision ID: a35aec7afa0a
Revises: 54efe873f88f
Create Date: 2022-01-01 09:29:44.529228

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a35aec7afa0a'
down_revision = '54efe873f88f'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('runs', sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index('ix_test_case_results_test_case_id', 'test_case_results', ['test_case_id'], unique=False)


def downgrade():
    op.drop_index('ix_test_case_results_test_case_id', table_name='test_case_results')
    op.drop_column('runs', 'processed_at')
