"""change project_id in ExecutorGroup to nullable

Revision ID: 735e81eedae4
Revises: 67d4f5a5ee98
Create Date: 2020-01-11 07:16:41.259814

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '735e81eedae4'
down_revision = '67d4f5a5ee98'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('executor_groups', 'project_id',
                    existing_type=sa.INTEGER(),
                    nullable=True)


def downgrade():
    op.alter_column('executor_groups', 'project_id',
                    existing_type=sa.INTEGER(),
                    nullable=False)
