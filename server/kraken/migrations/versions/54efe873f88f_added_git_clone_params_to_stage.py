"""added git_clone_params to stage

Revision ID: 54efe873f88f
Revises: e0d8421619c2
Create Date: 2021-09-15 06:40:12.583695

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '54efe873f88f'
down_revision = 'e0d8421619c2'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('stages', sa.Column('git_clone_params', sa.UnicodeText(), nullable=True))


def downgrade():
    op.drop_column('stages', 'git_clone_params')
