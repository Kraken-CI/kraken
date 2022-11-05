"""added fields_masked to step

Revision ID: 5c16623f4d55
Revises: 9666bf8c1bb0
Create Date: 2022-11-05 18:50:29.258670

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '5c16623f4d55'
down_revision = '9666bf8c1bb0'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('steps', sa.Column('fields_masked', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade():
    op.drop_column('steps', 'fields_masked')
