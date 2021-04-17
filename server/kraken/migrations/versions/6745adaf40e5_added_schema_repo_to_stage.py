"""added schema repo to Stage

Revision ID: 6745adaf40e5
Revises: a7de4bdee425
Create Date: 2020-02-16 19:29:56.547139

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '6745adaf40e5'
down_revision = 'a7de4bdee425'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('stages', sa.Column('repo_access_token', sa.UnicodeText(), nullable=True))
    op.add_column('stages', sa.Column('repo_branch', sa.UnicodeText(), nullable=True))
    op.add_column('stages', sa.Column('repo_url', sa.UnicodeText(), nullable=True))
    op.add_column('stages', sa.Column('schema_file', sa.UnicodeText(), nullable=True))
    op.add_column('stages', sa.Column('schema_from_repo_enabled', sa.Boolean(), nullable=True))


def downgrade():
    op.drop_column('stages', 'schema_from_repo_enabled')
    op.drop_column('stages', 'schema_file')
    op.drop_column('stages', 'repo_url')
    op.drop_column('stages', 'repo_branch')
    op.drop_column('stages', 'repo_access_token')
