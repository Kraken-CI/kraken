"""added seq to flow and run

Revision ID: b510fae321ba
Revises: bdcdbb4b5b3f
Create Date: 2023-03-19 13:45:12.691045

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'b510fae321ba'
down_revision = 'bdcdbb4b5b3f'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('flows', sa.Column('seq', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('runs', sa.Column('seq', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('runs', 'seq')
    op.drop_column('flows', 'seq')
    # ### end Alembic commands ###
