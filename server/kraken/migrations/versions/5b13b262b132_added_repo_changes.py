"""added repo changes

Revision ID: 5b13b262b132
Revises: 770cfcc80cfb
Create Date: 2021-04-07 06:02:59.604892

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import orm
from sqlalchemy.sql import insert
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '5b13b262b132'
down_revision = '770cfcc80cfb'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    orm.Session(bind=conn)

    rc_tbl = op.create_table('repo_changes',
                             sa.Column('created', sa.DateTime(), nullable=False),
                             sa.Column('updated', sa.DateTime(), nullable=False),
                             sa.Column('deleted', sa.DateTime(), nullable=True),
                             sa.Column('id', sa.Integer(), nullable=False),
                             sa.Column('data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
                             sa.PrimaryKeyConstraint('id')
    )

    op.add_column('flows', sa.Column('trigger_data_id', sa.Integer()))
    op.create_foreign_key('flows_trigger_data_id_fkey', 'flows', 'repo_changes', ['trigger_data_id'], ['id'])

    op.add_column('runs', sa.Column('repo_data_id', sa.Integer()))
    op.create_foreign_key('runs_repo_data_id_fkey', 'runs', 'repo_changes', ['repo_data_id'], ['id'])

    print('updating flows')
    res = conn.execute("SELECT id, created, trigger_data FROM flows WHERE trigger_data IS NOT NULL AND trigger_data::text != 'null'")
    for flow_id, created, d in res.fetchall():
        if isinstance(d, dict):
            d = [d]
        rc = {'created': created, 'updated': created, 'data': d}
        ret = conn.execute(insert(rc_tbl).values(rc).returning(rc_tbl.c.id))
        d_id = ret.fetchone()[0]
        print('flow: %d  repo_changes %d' % (flow_id, d_id))
        conn.execute("UPDATE flows SET trigger_data_id = %d WHERE id = %d" % (d_id, flow_id))

    print('updating runs')
    res = conn.execute("SELECT id, created, repo_data FROM runs WHERE repo_data IS NOT NULL AND repo_data::text != 'null'")
    for run_id, created, d in res.fetchall():
        if isinstance(d, dict):
            new_ds = []
            for url, commits in d.items():
                new_d = {}
                new_d['repo'] = url
                new_d['trigger'] = 'git-push'

                new_commits = []
                for c in commits:
                    nc = dict(id=c['commit'],
                              author=dict(name=c['author'], email=c['email']),
                              timestamp=c['date'],
                              message=c['subject'])
                    new_commits.append(nc)

                new_d['commits'] = new_commits
                new_d['before'] = new_commits[-1]['id']
                new_d['after'] = new_commits[0]['id']

                new_ds.append(new_d)

            d = new_ds

        rc = {'created': created, 'updated': created, 'data': d}
        ret = conn.execute(insert(rc_tbl).values(rc).returning(rc_tbl.c.id))
        d_id = ret.fetchone()[0]
        print('run: %d  repo_changes %d' % (run_id, d_id))
        conn.execute("UPDATE runs SET repo_data_id = %d WHERE id = %d" % (d_id, run_id))

    #op.drop_column('flows', 'trigger_data')
    #op.drop_column('runs', 'repo_data')


def downgrade():
    # op.add_column('runs', sa.Column('repo_data', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=True))
    op.drop_constraint('runs_repo_data_id_fkey', 'runs', type_='foreignkey')
    op.drop_column('runs', 'repo_data_id')

    # op.add_column('flows', sa.Column('trigger_data', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=True))
    op.drop_constraint('flows_trigger_data_id_fkey', 'flows', type_='foreignkey')
    op.drop_column('flows', 'trigger_data_id')

    op.drop_table('repo_changes')
