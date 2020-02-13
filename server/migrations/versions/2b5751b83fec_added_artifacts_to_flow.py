"""added artifacts to Flow

Revision ID: 2b5751b83fec
Revises: 66808ea51a72
Create Date: 2020-02-12 08:30:28.025708

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '2b5751b83fec'
down_revision = '66808ea51a72'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('flows', sa.Column('artifacts', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade():
    op.drop_column('flows', 'artifacts')
