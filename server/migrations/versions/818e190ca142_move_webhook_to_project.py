"""move webhook to Project

Revision ID: 818e190ca142
Revises: d45087b62027
Create Date: 2019-12-27 07:38:17.002835

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '818e190ca142'
down_revision = 'd45087b62027'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('projects', sa.Column('webhooks', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.drop_column('stages', 'webhooks')


def downgrade():
    op.add_column('stages', sa.Column('webhooks', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=True))
    op.drop_column('projects', 'webhooks')
