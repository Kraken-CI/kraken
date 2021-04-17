"""rename executor to agent

Revision ID: 89ffd52f1f00
Revises: 6745adaf40e5
Create Date: 2020-09-05 08:19:47.642453

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '89ffd52f1f00'
down_revision = '6745adaf40e5'
branch_labels = None
depends_on = None


def upgrade():

    op.rename_table("executors", "agents")
    op.rename_table("executor_assignments", "agent_assignments")
    op.rename_table("executor_groups", "agents_groups")

    op.drop_constraint("executor_assignments_executor_id_fkey", "agent_assignments", type_="foreignkey")
    op.drop_constraint("executor_assignments_executor_group_id_fkey", "agent_assignments", type_="foreignkey")
    op.drop_constraint("executor_assignments_pkey", "agent_assignments", type_="primary")
    op.drop_constraint("jobs_executor_used_id_fkey", "jobs", type_="foreignkey")
    op.drop_constraint("jobs_executor_group_id_fkey", "jobs", type_="foreignkey")
    op.drop_constraint("executors_pkey", "agents", type_="primary")
    op.drop_constraint("executors_job_id_fkey", "agents", type_="foreignkey")
    op.drop_constraint("executor_groups_pkey", "agents_groups", type_="primary")
    op.drop_constraint("executor_groups_project_id_fkey", "agents_groups", type_="primary")

    op.alter_column("agent_assignments", "executor_id", new_column_name="agent_id")
    op.alter_column("agent_assignments", "executor_group_id", new_column_name="agents_group_id")
    op.alter_column("jobs", "executor_group_id", new_column_name="agents_group_id")
    op.alter_column("jobs", "executor_used_id", new_column_name="agent_used_id")

    op.create_primary_key("agents_pkey", "agents", ["id"])
    op.create_primary_key("agent_assignments_pkey", "agent_assignments", ["agent_id", "agents_group_id"])
    op.create_primary_key("agents_groups_pkey", "agents_groups", ["id"])
    op.create_foreign_key("jobs_agent_used_id_fkey", "jobs",
                          "agents", ["agent_used_id"], ["id"])
    op.create_foreign_key("jobs_agents_group_id_fkey", "jobs",
                          "agents_groups", ["agents_group_id"], ["id"])
    op.create_foreign_key("agent_assignments_agent_id_fkey", "agent_assignments",
                          "agents", ["agent_id"], ["id"])
    op.create_foreign_key("agent_assignments_agents_group_id_fkey", "agent_assignments",
                          "agents_groups", ["agents_group_id"], ["id"])
    op.create_foreign_key("agents_groups_project_id_fkey", "agents_groups",
                          "projects", ["project_id"], ["id"])
    op.create_foreign_key("agents_job_id_fkey", "agents",
                          "jobs", ["job_id"], ["id"])

    op.drop_index("ix_executors_address")
    op.create_index('ix_agents_address', 'agents', ['address'])

    op.execute('ALTER SEQUENCE executor_groups_id_seq RENAME TO agents_groups_id_seq')
    op.execute('ALTER SEQUENCE executors_id_seq RENAME TO agents_id_seq')


def downgrade():
    op.rename_table("agent_assignments", "executor_assignments")
    op.rename_table("agents", "executors")
    op.rename_table("agents_groups", "executor_groups")

    op.drop_constraint("agent_assignments_agent_id_fkey", "executor_assignments", type_="foreignkey")
    op.drop_constraint("agent_assignments_agents_group_id_fkey", "executor_assignments", type_="foreignkey")
    op.drop_constraint("agent_assignments_pkey", "executor_assignments", type_="primary")
    op.drop_constraint("jobs_agent_used_id_fkey", "jobs", type_="foreignkey")
    op.drop_constraint("jobs_agents_group_id_fkey", "jobs", type_="foreignkey")
    op.drop_constraint("agents_pkey", "executors", type_="primary")
    op.drop_constraint("agents_job_id_fkey", "executors", type_="foreignkey")
    op.drop_constraint("agents_groups_pkey", "executor_groups", type_="primary")
    op.drop_constraint("agents_groups_project_id_fkey", "executor_groups", type_="primary")

    op.alter_column("executor_assignments", "agents_group_id", new_column_name="executor_group_id")
    op.alter_column("executor_assignments", "agent_id", new_column_name="executor_id")
    op.alter_column("jobs", "agent_used_id", new_column_name="executor_used_id")
    op.alter_column("jobs", "agents_group_id", new_column_name="executor_group_id")

    op.create_primary_key("executors_pkey", "executors", ["id"])
    op.create_primary_key("executor_assignments_pkey", "executor_assignments", ["executor_id", "executor_group_id"])
    op.create_primary_key("executor_groups_pkey", "executor_groups", ["id"])
    op.create_foreign_key("jobs_executor_used_id_fkey", "jobs",
                          "executors", ["executor_used_id"], ["id"])
    op.create_foreign_key("jobs_executor_group_id_fkey", "jobs",
                          "executor_groups", ["executor_group_id"], ["id"])
    op.create_foreign_key("executor_assignments_executor_id_fkey", "executor_assignments",
                          "executors", ["executor_id"], ["id"])
    op.create_foreign_key("executor_assignments_executor_group_id_fkey", "executor_assignments",
                          "executor_groups", ["executor_group_id"], ["id"])
    op.create_foreign_key("executor_groups_project_id_fkey", "executor_groups",
                          "projects", ["project_id"], ["id"])
    op.create_foreign_key("executors_job_id_fkey", "executors",
                          "jobs", ["job_id"], ["id"])

    op.drop_index("ix_agents_address")
    op.create_index('ix_executors_address', 'executors', ['address'])

    op.execute('ALTER SEQUENCE agents_groups_id_seq RENAME TO executor_groups_id_seq')
    op.execute('ALTER SEQUENCE agents_id_seq RENAME TO executors_id_seq')
