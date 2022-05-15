"""extended tool

Revision ID: af348b43d9d5
Revises: 5e38f55beb11
Create Date: 2022-05-14 19:48:36.262751

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'af348b43d9d5'
down_revision = '5e38f55beb11'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('tools', sa.Column('location', sa.UnicodeText(), nullable=True))
    op.add_column('tools', sa.Column('entry', sa.UnicodeText(), nullable=True))
    op.add_column('tools', sa.Column('version', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('tools', 'version')
    op.drop_column('tools', 'entry')
    op.drop_column('tools', 'location')
