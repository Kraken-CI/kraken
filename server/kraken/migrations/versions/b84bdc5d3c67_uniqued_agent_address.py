"""uniqued agent address

Revision ID: b84bdc5d3c67
Revises: b2c9024746f5
Create Date: 2021-06-21 22:03:17.503080

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'b84bdc5d3c67'
down_revision = 'b2c9024746f5'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_index('ix_agents_address', table_name='agents')
    op.create_index(op.f('ix_agents_address'), 'agents', ['address'], unique=True)


def downgrade():
    op.drop_index(op.f('ix_agents_address'), table_name='agents')
    op.create_index('ix_agents_address', 'agents', ['address'], unique=False)
