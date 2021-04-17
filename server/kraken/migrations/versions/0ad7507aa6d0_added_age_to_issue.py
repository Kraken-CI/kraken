"""added age to Issue

Revision ID: 0ad7507aa6d0
Revises: 98af95844f27
Create Date: 2020-01-05 13:30:13.930171

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0ad7507aa6d0'
down_revision = '98af95844f27'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('issues', sa.Column('age', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('issues', 'age')
