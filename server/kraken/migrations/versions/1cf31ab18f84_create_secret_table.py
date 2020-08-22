"""create Secret table

Revision ID: 1cf31ab18f84
Revises: ba436d491bf8
Create Date: 2019-12-24 07:56:00.751309

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '1cf31ab18f84'
down_revision = 'ba436d491bf8'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('secrets',
                    sa.Column('created', sa.DateTime(), nullable=False),
                    sa.Column('updated', sa.DateTime(), nullable=False),
                    sa.Column('deleted', sa.DateTime(), nullable=True),
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('name', sa.Unicode(length=255), nullable=True),
                    sa.Column('project_id', sa.Integer(), nullable=False),
                    sa.Column('kind', sa.Integer(), nullable=True),
                    sa.Column('data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
                    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
                    sa.PrimaryKeyConstraint('id'))


def downgrade():
    op.drop_table('secrets')
