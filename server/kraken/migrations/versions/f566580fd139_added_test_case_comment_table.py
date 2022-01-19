"""added test case comment table

Revision ID: f566580fd139
Revises: a35aec7afa0a
Create Date: 2022-01-15 21:02:31.961891

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'f566580fd139'
down_revision = 'a35aec7afa0a'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('test_case_comments',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('test_case_id', sa.Integer(), nullable=True),
                    sa.Column('branch_id', sa.Integer(), nullable=True),
                    sa.Column('last_flow_id', sa.Integer(), nullable=True),
                    sa.Column('state', sa.Integer(), nullable=True),
                    sa.Column('data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
                    sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], ),
                    sa.ForeignKeyConstraint(['last_flow_id'], ['flows.id'], ),
                    sa.ForeignKeyConstraint(['test_case_id'], ['test_cases.id'], ),
                    sa.PrimaryKeyConstraint('id'))
    op.add_column('test_case_results', sa.Column('comment_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_test_case_comments_test_case_results',
                          'test_case_results', 'test_case_comments', ['comment_id'], ['id'])


def downgrade():
    op.drop_constraint('fk_test_case_comments_test_case_results', 'test_case_results', type_='foreignkey')
    op.drop_column('test_case_results', 'comment_id')
    op.drop_table('test_case_comments')
