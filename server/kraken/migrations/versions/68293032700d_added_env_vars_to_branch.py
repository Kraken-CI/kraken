"""added env_vars to branch

Revision ID: 68293032700d
Revises: 9e57e0f30a5f
Create Date: 2023-07-24 07:41:57.915270

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '68293032700d'
down_revision = '9e57e0f30a5f'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('branches', sa.Column('env_vars', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('branches', 'env_vars')
    # ### end Alembic commands ###
