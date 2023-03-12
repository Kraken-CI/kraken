"""added reason to run

Revision ID: 29b96da53f09
Revises: dae910bd9587
Create Date: 2021-01-10 13:41:43.387949

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '29b96da53f09'
down_revision = 'dae910bd9587'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('runs', sa.Column('reason', postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    op.execute("""UPDATE runs SET reason = '{"reason": "manual"}'::jsonb""")

    op.alter_column('runs', 'reason', nullable=False)


def downgrade():
    op.drop_column('runs', 'reason')
