"""added retention_policy to branch

Revision ID: cea0e48abb5a
Revises: 5c16623f4d55
Create Date: 2023-02-16 08:06:50.864851

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'cea0e48abb5a'
down_revision = '5c16623f4d55'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('branches', sa.Column('retention_policy', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade():
    op.drop_column('branches', 'retention_policy')
