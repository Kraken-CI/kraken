"""added index to flows

Revision ID: ab9326d5fc02
Revises: 9d8d8713c1ad
Create Date: 2021-05-28 07:44:40.012276

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'ab9326d5fc02'
down_revision = '9d8d8713c1ad'
branch_labels = None
depends_on = None


INDEXES = [
    # create INDEX ix_flows_branch_id_kind on flows(branch_id, kind);
    ['ix_flows_branch_id_kind', 'flows', ['branch_id', 'kind']],
    # create INDEX ix_flows_created on flows(created);
    ['ix_flows_created', 'flows', ['created']],
    # create INDEX ix_runs_flow_id on runs(flow_id);
    ['ix_runs_flow_id', 'runs', ['flow_id']],
    # create INDEX ix_artifacts_run_id on artifacts(run_id);
    ['ix_artifacts_run_id', 'artifacts', ['run_id']],
    # create INDEX ix_artifacts_flow_id on artifacts(flow_id);
    ['ix_artifacts_flow_id', 'artifacts', ['flow_id']],
]


def upgrade():
    for name, table, columns in INDEXES:
        try:
            print('creating index %s' % name)
            op.create_index(name, table, columns)
        except Exception:
            pass


def downgrade():
    for name, table, _ in INDEXES:
        try:
            print('dropping index %s' % name)
            op.drop_index(name, table_name=table)
        except Exception:
            pass
