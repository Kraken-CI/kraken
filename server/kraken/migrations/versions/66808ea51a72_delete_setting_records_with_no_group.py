"""delete Setting records with no group

Revision ID: 66808ea51a72
Revises: 8b4adeca953d
Create Date: 2020-02-09 06:35:05.418249

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = '66808ea51a72'
down_revision = '8b4adeca953d'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("DELETE FROM settings where settings.group = NULL;")

def downgrade():
    pass
