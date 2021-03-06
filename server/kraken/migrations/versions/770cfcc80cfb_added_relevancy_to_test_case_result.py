"""added relevancy to test case result

Revision ID: 770cfcc80cfb
Revises: d524cbcbf19c
Create Date: 2021-03-06 08:50:49.401290

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '770cfcc80cfb'
down_revision = 'd524cbcbf19c'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('test_case_results', sa.Column('relevancy', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('test_case_results', 'relevancy')
