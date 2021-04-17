"""longer message in Issue

Revision ID: b908e219f07f
Revises: 1982be95e79f
Create Date: 2020-01-26 07:59:37.454201

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'b908e219f07f'
down_revision = '1982be95e79f'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('issues', 'message',
               existing_type=sa.VARCHAR(length=256),
               type_=sa.Unicode(length=512),
               existing_nullable=True)


def downgrade():
    op.alter_column('issues', 'message',
               existing_type=sa.Unicode(length=512),
               type_=sa.VARCHAR(length=256),
               existing_nullable=True)
