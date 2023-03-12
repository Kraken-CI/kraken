"""added missing indexes

Revision ID: 899dadc28f9c
Revises: a0741baf2dbc
Create Date: 2022-01-20 07:45:48.954451

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '899dadc28f9c'
down_revision = 'a0741baf2dbc'
branch_labels = None
depends_on = None

INDEXES = [
    ('ix_artifacts_flow_id', 'artifacts', 'flow_id'),
    ('ix_artifacts_run_id', 'artifacts', 'run_id'),
    ('ix_flows_branch_id_kind', 'flows', 'branch_id, kind'),
    ('ix_flows_created', 'flows', 'created'),
    ('ix_runs_flow_id', 'runs', 'flow_id'),
    ('uq_system_name_executor', 'systems', 'name, executor'),
    ('ix_test_case_results_comment_id', 'test_case_results', 'comment_id'),
    ('ix_test_case_results_job_id', 'test_case_results', 'job_id')
]


def upgrade():
    for name, table, columns in INDEXES:
        if name.startswith('uq'):
            uq = ' UNIQUE '
            cmd = 'ALTER TABLE %s ADD CONSTRAINT %s UNIQUE (%s)' % (table, name, columns)
            with op.get_context().autocommit_block():
                try:
                    op.execute(cmd)
                except Exception:
                    pass
        else:
            uq = ''
        cmd = "CREATE %s INDEX IF NOT EXISTS %s ON public.%s USING btree (%s);" % (uq, name, table, columns)
        print(cmd)
        op.execute(cmd)
    print('migration completed')


def downgrade():
    for name, table, _ in INDEXES:
        if name.startswith('uq'):
            cmd = 'ALTER TABLE %s DROP CONSTRAINT %s' % (table, name)
            op.execute(cmd)
        print('dropping index %s' % name)
        cmd = "DROP INDEX IF EXISTS %s;" % name
        op.execute(cmd)
        #op.drop_index(name, table_name=table)
    print('migration completed')
