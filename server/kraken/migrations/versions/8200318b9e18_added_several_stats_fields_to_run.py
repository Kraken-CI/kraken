"""added several stats fields to Run

Revision ID: 8200318b9e18
Revises: b908e219f07f
Create Date: 2020-02-08 11:50:24.255977

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '8200318b9e18'
down_revision = 'b908e219f07f'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table('preferences')
    op.add_column('runs', sa.Column('issues_new', sa.Integer(), nullable=True))
    op.add_column('runs', sa.Column('issues_total', sa.Integer(), nullable=True))
    op.add_column('runs', sa.Column('jobs_error', sa.Integer(), nullable=True))
    op.add_column('runs', sa.Column('jobs_total', sa.Integer(), nullable=True))
    op.add_column('runs', sa.Column('tests_not_run', sa.Integer(), nullable=True))
    op.add_column('runs', sa.Column('tests_passed', sa.Integer(), nullable=True))
    op.add_column('runs', sa.Column('tests_total', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('runs', 'tests_total')
    op.drop_column('runs', 'tests_passed')
    op.drop_column('runs', 'tests_not_run')
    op.drop_column('runs', 'jobs_total')
    op.drop_column('runs', 'jobs_error')
    op.drop_column('runs', 'issues_total')
    op.drop_column('runs', 'issues_new')
    op.create_table('preferences',
                    sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
                    sa.Column('name', sa.VARCHAR(length=50), autoincrement=False, nullable=True),
                    sa.Column('value', sa.TEXT(), autoincrement=False, nullable=True),
                    sa.Column('val_type', sa.VARCHAR(length=8), autoincrement=False, nullable=True),
                    sa.PrimaryKeyConstraint('id', name='preferences_pkey'))
