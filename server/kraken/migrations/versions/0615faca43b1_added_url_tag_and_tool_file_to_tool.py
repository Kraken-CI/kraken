"""added url, tag and tool_file to tool

Revision ID: 0615faca43b1
Revises: befa07ac5d1c
Create Date: 2022-05-30 20:34:29.878224

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0615faca43b1'
down_revision = 'befa07ac5d1c'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('tools', sa.Column('url', sa.UnicodeText(), nullable=True))
    op.add_column('tools', sa.Column('tag', sa.UnicodeText(), nullable=True))
    op.add_column('tools', sa.Column('tool_file', sa.UnicodeText(), nullable=True))


def downgrade():
    op.drop_column('tools', 'tool_file')
    op.drop_column('tools', 'tag')
    op.drop_column('tools', 'url')
