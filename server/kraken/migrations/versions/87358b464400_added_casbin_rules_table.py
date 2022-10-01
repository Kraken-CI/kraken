"""added casbin_rules table

Revision ID: 87358b464400
Revises: 411094f6b709
Create Date: 2022-09-30 22:52:45.199722

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '87358b464400'
down_revision = '411094f6b709'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('casbin_rules',
                    sa.Column('created', sa.DateTime(timezone=True), nullable=False),
                    sa.Column('updated', sa.DateTime(timezone=True), nullable=False),
                    sa.Column('deleted', sa.DateTime(timezone=True), nullable=True),
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('ptype', sa.String(length=255), nullable=True),
                    sa.Column('v0', sa.String(length=255), nullable=True),
                    sa.Column('v1', sa.String(length=255), nullable=True),
                    sa.Column('v2', sa.String(length=255), nullable=True),
                    sa.Column('v3', sa.String(length=255), nullable=True),
                    sa.Column('v4', sa.String(length=255), nullable=True),
                    sa.Column('v5', sa.String(length=255), nullable=True),
                    sa.PrimaryKeyConstraint('id'))


def downgrade():
    op.drop_table('casbin_rules')
