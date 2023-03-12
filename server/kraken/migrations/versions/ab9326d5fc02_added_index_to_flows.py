"""added index to flows

Revision ID: ab9326d5fc02
Revises: 9d8d8713c1ad
Create Date: 2021-05-28 07:44:40.012276

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = 'ab9326d5fc02'
down_revision = '9d8d8713c1ad'
branch_labels = None
depends_on = None


INDEXES = [
    # create INDEX ix_flows_branch_id_kind on flows(branch_id, kind);
    ['ix_flows_branch_id_kind', 'flows', 'branch_id, kind'],
    # create INDEX ix_flows_created on flows(created);
    ['ix_flows_created', 'flows', 'created'],
    # create INDEX ix_runs_flow_id on runs(flow_id);
    ['ix_runs_flow_id', 'runs', 'flow_id'],
    # create INDEX ix_artifacts_run_id on artifacts(run_id);
    ['ix_artifacts_run_id', 'artifacts', 'run_id'],
    # create INDEX ix_artifacts_flow_id on artifacts(flow_id);
    ['ix_artifacts_flow_id', 'artifacts', 'flow_id'],
]


def upgrade():
    for name, table, columns in INDEXES:
        print('creating index %s' % name)
        cmd = "CREATE INDEX IF NOT EXISTS %s ON %s (%s);" % (name, table, columns)
        op.execute(cmd)
        #op.create_index(name, table, columns)
    print('migration completed')


def downgrade():
    for name, _, _ in INDEXES:
        print('dropping index %s' % name)
        cmd = "DROP INDEX IF EXISTS %s;" % name
        op.execute(cmd)
        #op.drop_index(name, table_name=table)
    print('migration completed')
