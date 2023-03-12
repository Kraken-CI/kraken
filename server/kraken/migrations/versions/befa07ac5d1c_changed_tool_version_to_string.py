"""changed tool version to string

Revision ID: befa07ac5d1c
Revises: af348b43d9d5
Create Date: 2022-05-26 07:18:25.697901

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'befa07ac5d1c'
down_revision = 'af348b43d9d5'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('tools', 'version',
               existing_type=sa.INTEGER(),
               type_=sa.UnicodeText(),
               existing_nullable=True)
    op.create_unique_constraint('uq_tool_name_version', 'tools', ['name', 'version'])

    op.execute("UPDATE tools SET version = '1'")


def downgrade():
    op.drop_constraint('uq_tool_name_version', 'tools', type_='unique')
    op.alter_column('tools', 'version',
               existing_type=sa.UnicodeText(),
               type_=sa.INTEGER(),
               existing_nullable=True)
