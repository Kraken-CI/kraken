"""added new repo fields to stage

Revision ID: 2dd5cf2d12dc
Revises: cb7654d57bca
Create Date: 2021-01-02 15:03:35.913920

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2dd5cf2d12dc'
down_revision = 'cb7654d57bca'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('stages', sa.Column('repo_error', sa.UnicodeText(), nullable=True))
    op.add_column('stages', sa.Column('repo_refresh_interval', sa.UnicodeText(), nullable=True))
    op.add_column('stages', sa.Column('repo_refresh_job_id', sa.UnicodeText(), nullable=True))
    op.add_column('stages', sa.Column('repo_state', sa.Integer(), nullable=True))
    op.add_column('stages', sa.Column('repo_version', sa.UnicodeText(), nullable=True))


def downgrade():
    op.drop_column('stages', 'repo_version')
    op.drop_column('stages', 'repo_state')
    op.drop_column('stages', 'repo_refresh_job_id')
    op.drop_column('stages', 'repo_refresh_interval')
    op.drop_column('stages', 'repo_error')
