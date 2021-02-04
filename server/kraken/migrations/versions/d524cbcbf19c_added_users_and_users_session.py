"""added users and users_session

Revision ID: d524cbcbf19c
Revises: 29b96da53f09
Create Date: 2021-02-03 07:34:18.936536

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd524cbcbf19c'
down_revision = '29b96da53f09'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('users',
                    sa.Column('created', sa.DateTime(), nullable=False),
                    sa.Column('updated', sa.DateTime(), nullable=False),
                    sa.Column('deleted', sa.DateTime(), nullable=True),
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('name', sa.Unicode(length=50), nullable=True),
                    sa.Column('password', sa.Unicode(length=150), nullable=True),
                    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('user_sessions',
                    sa.Column('created', sa.DateTime(), nullable=False),
                    sa.Column('updated', sa.DateTime(), nullable=False),
                    sa.Column('deleted', sa.DateTime(), nullable=True),
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('token', sa.Unicode(length=32), nullable=True),
                    sa.Column('user_id', sa.Integer(), nullable=False),
                    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
                    sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('user_sessions')
    op.drop_table('users')
