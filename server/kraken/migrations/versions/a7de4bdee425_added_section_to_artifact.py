"""added section to Artifact

Revision ID: a7de4bdee425
Revises: bb0d4908ba49
Create Date: 2020-02-16 13:50:35.889016

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a7de4bdee425'
down_revision = 'bb0d4908ba49'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('artifacts', sa.Column('section', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('artifacts', 'section')
