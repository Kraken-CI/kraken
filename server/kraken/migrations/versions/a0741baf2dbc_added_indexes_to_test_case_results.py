"""added indexes to test_case_results

Revision ID: a0741baf2dbc
Revises: f566580fd139
Create Date: 2022-01-20 06:50:44.181743

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'a0741baf2dbc'
down_revision = 'f566580fd139'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index('ix_test_case_results_comment_id', 'test_case_results', ['comment_id'], unique=False)
    op.create_index('ix_test_case_results_job_id', 'test_case_results', ['job_id'], unique=False)


def downgrade():
    op.drop_index('ix_test_case_results_job_id', table_name='test_case_results')
    op.drop_index('ix_test_case_results_comment_id', table_name='test_case_results')
