"""added branch sequences

Revision ID: 4a7ac9143bb1
Revises: 38088514157a
Create Date: 2020-09-26 11:18:26.316516

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '4a7ac9143bb1'
down_revision = '38088514157a'
branch_labels = None
depends_on = None


def upgrade():
    bs_tbl = op.create_table('branch_sequences',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('kind', sa.Integer(), nullable=True),
                    sa.Column('branch_id', sa.Integer(), nullable=False),
                    sa.Column('stage_id', sa.Integer(), nullable=True),
                    sa.Column('value', sa.Integer(), nullable=True),
                    sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], ),
                    sa.ForeignKeyConstraint(['stage_id'], ['stages.id'], ),
                    sa.PrimaryKeyConstraint('id')
    )
    conn = op.get_bind()
    br_res = conn.execute("SELECT id FROM branches WHERE deleted IS NULL")
    seqs = []
    for br_id in br_res.fetchall():
        seqs.append({'kind': 0, 'branch_id': br_id[0], 'stage_id': None, 'value': 0})
        seqs.append({'kind': 1, 'branch_id': br_id[0], 'stage_id': None, 'value': 0})
        seqs.append({'kind': 2, 'branch_id': br_id[0], 'stage_id': None, 'value': 0})

        stg_res = conn.execute("SELECT id FROM stages WHERE deleted IS NULL AND branch_id = %d" % br_id[0])
        for stg_id in stg_res.fetchall():
            seqs.append({'kind': 3, 'branch_id': br_id[0], 'stage_id': stg_id[0], 'value': 0})
            seqs.append({'kind': 4, 'branch_id': br_id[0], 'stage_id': stg_id[0], 'value': 0})
            seqs.append({'kind': 5, 'branch_id': br_id[0], 'stage_id': stg_id[0], 'value': 0})

    op.bulk_insert(bs_tbl, seqs)


def downgrade():
    op.drop_table('branch_sequences')
