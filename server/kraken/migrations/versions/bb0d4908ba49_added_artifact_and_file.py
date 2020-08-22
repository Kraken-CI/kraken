"""added Artifact and File

Revision ID: bb0d4908ba49
Revises: 2b5751b83fec
Create Date: 2020-02-16 07:42:24.358297

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'bb0d4908ba49'
down_revision = '2b5751b83fec'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('files',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('path', sa.Unicode(length=512), nullable=True),
                    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('artifacts',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('file_id', sa.Integer(), nullable=False),
                    sa.Column('flow_id', sa.Integer(), nullable=False),
                    sa.Column('run_id', sa.Integer(), nullable=False),
                    sa.Column('size', sa.Integer(), nullable=True),
                    sa.ForeignKeyConstraint(['file_id'], ['files.id'], ),
                    sa.ForeignKeyConstraint(['flow_id'], ['flows.id'], ),
                    sa.ForeignKeyConstraint(['run_id'], ['runs.id'], ),
                    sa.PrimaryKeyConstraint('id')
    )
    op.add_column('runs', sa.Column('artifacts', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade():
    op.drop_column('runs', 'artifacts')
    op.drop_table('artifacts')
    op.drop_table('files')
