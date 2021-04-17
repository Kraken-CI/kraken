"""added results change stats to Run

Revision ID: 98af95844f27
Revises: 818e190ca142
Create Date: 2020-01-04 18:32:23.969038

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '98af95844f27'
down_revision = '818e190ca142'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('runs', sa.Column('fix_cnt', sa.Integer(), nullable=True))
    op.add_column('runs', sa.Column('new_cnt', sa.Integer(), nullable=True))
    op.add_column('runs', sa.Column('no_change_cnt', sa.Integer(), nullable=True))
    op.add_column('runs', sa.Column('regr_cnt', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('runs', 'regr_cnt')
    op.drop_column('runs', 'no_change_cnt')
    op.drop_column('runs', 'new_cnt')
    op.drop_column('runs', 'fix_cnt')
