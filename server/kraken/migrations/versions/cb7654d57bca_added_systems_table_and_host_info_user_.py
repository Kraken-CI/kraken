"""added systems table and host_info, user_attrs column to agent table

Revision ID: cb7654d57bca
Revises: 466de256799e
Create Date: 2020-10-11 20:07:55.477525

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql.expression import bindparam

# revision identifiers, used by Alembic.
revision = 'cb7654d57bca'
down_revision = '466de256799e'
branch_labels = None
depends_on = None


def upgrade():
    sys_tbl = op.create_table('systems',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('name', sa.Unicode(length=150), nullable=True),
                    sa.Column('executor', sa.Unicode(length=20), nullable=True),
                    sa.PrimaryKeyConstraint('id'),
                    sa.UniqueConstraint('name', 'executor', name='uq_system_name_executor'),
    )
    op.add_column('agents', sa.Column('host_info', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('agents', sa.Column('user_attrs', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('jobs', sa.Column('system_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_systems_jobs', 'jobs', 'systems', ['system_id'], ['id'])

    conn = op.get_bind()

    # prepare system records for insertion
    jobs = conn.execute("SELECT id,system FROM jobs")
    systems = []
    jobs_map = {}
    for j_id, j_system in jobs.fetchall():
        print(j_id, j_system)
        if not j_system:
            j_system = 'local^fake'

        if j_system in jobs_map:
            jobs_map[j_system].append({'_id': j_id})
        else:
            parts = j_system.split('^')
            if len(parts) == 2:
                executor, name = parts
            elif len(parts) == 1:
                executor = 'local'
                name = parts[0]
                j_system = '%s^%s' % (executor, name)
                if j_system in jobs_map:
                    jobs_map[j_system].append({'_id': j_id})
                    continue
            else:
                raise Exception('not enough parts: %s' % str(parts))
            systems.append({'name': name, 'executor': executor})
            jobs_map[j_system] = [{'_id': j_id}]

    # insert all system records
    op.bulk_insert(sys_tbl, systems)

    # get all systems id and prepare list of job updates
    systems = conn.execute("SELECT id,name,executor FROM systems")
    sys_map = {}
    jobs_updts = []
    for s_id, s_name, s_executor in systems.fetchall():
        key = '%s^%s' % (s_executor, s_name)
        sys_map[key] = s_id

        for upd in jobs_map[key]:
            upd['system_id'] = s_id
            jobs_updts.append(upd)

    if jobs_updts:
        # update all jobs
        jobs_tbl = sa.sql.table(
            'jobs',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('system_id', sa.Integer(), nullable=True),
            # Other columns not needed for the data migration
        )
        stmt = jobs_tbl.update()
        stmt = stmt.where(jobs_tbl.c.id == bindparam('_id'))
        stmt = stmt.values({
            'system_id': bindparam('system_id')
        })
        conn.execute(stmt, jobs_updts)

    op.drop_column('jobs', 'system')


def downgrade():
    #op.add_column('jobs', sa.Column('system', sa.VARCHAR(length=200), autoincrement=False, nullable=True))
    op.drop_constraint('fk_systems_jobs', 'jobs', type_='foreignkey')
    op.drop_column('jobs', 'system_id')
    op.drop_column('agents', 'user_attrs')
    op.drop_column('agents', 'host_info')
    op.drop_table('systems')
