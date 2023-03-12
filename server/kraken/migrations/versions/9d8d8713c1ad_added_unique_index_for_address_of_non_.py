"""added unique index for address of non-deleted agents

Revision ID: 9d8d8713c1ad
Revises: 19396769e240
Create Date: 2021-05-22 07:04:18.171520

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = '9d8d8713c1ad'
down_revision = '19396769e240'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE UNIQUE INDEX ix_agents_address_not_deleted ON agents (address) WHERE deleted is NULL;")


def downgrade():
    op.drop_index('ix_agents_address_not_deleted')
