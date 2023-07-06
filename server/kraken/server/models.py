# Copyright 2020-2022 The Kraken Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Boolean, DateTime, ForeignKey, Integer, Unicode, UnicodeText, String
from sqlalchemy import event, UniqueConstraint, Index
from sqlalchemy.orm import relationship, mapper
from sqlalchemy.dialects.postgresql import JSONB, DOUBLE_PRECISION, BYTEA

from . import consts
from . import utils

log = logging.getLogger(__name__)

db = SQLAlchemy(engine_options=dict(connect_args={"options": "-c timezone=utc"}))


@event.listens_for(mapper, 'init')
def auto_add(target, args, kwargs):  # pylint: disable=unused-argument
    db.session.add(target)


def duration_to_txt(duration):
    duration_txt = ""
    if duration.days > 0:
        duration_txt = "%dd " % duration.days
    if duration.seconds > 3600:
        duration_txt += "%dh " % (duration.seconds // 3600)
    if duration.seconds > 60:
        seconds = duration.seconds % 3600
        duration_txt += "%dm " % (seconds // 60)
    duration_txt += "%ds" % (duration.seconds % 60)
    duration_txt = duration_txt.strip()
    return duration_txt


class AlembicVersion(db.Model):
    __tablename__ = "alembic_version"
    version_num = Column(Unicode(32), nullable=False, primary_key=True)


class DatesMixin():
    created = Column(DateTime(timezone=True), nullable=False, default=utils.utcnow)
    updated = Column(DateTime(timezone=True), nullable=False, default=utils.utcnow, onupdate=utils.utcnow)
    deleted = Column(DateTime(timezone=True))


class Project(db.Model, DatesMixin):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True)
    name = Column(UnicodeText)
    description = Column(UnicodeText)
    branches = relationship("Branch", back_populates="project", order_by="Branch.created")
    secrets = relationship("Secret", back_populates="project", order_by="Secret.name")
    agents_groups = relationship("AgentsGroup", back_populates="project")
    webhooks = Column(JSONB)
    user_data = Column(JSONB, default={})

    def get_json(self, with_branches=True, with_results=False, with_last_results=False, with_user_data=False):
        data = dict(id=self.id,
                    created=self.created.strftime("%Y-%m-%dT%H:%M:%SZ") if self.created else None,
                    deleted=self.deleted.strftime("%Y-%m-%dT%H:%M:%SZ") if self.deleted else None,
                    name=self.name,
                    description=self.description,
                    secrets=[s.get_json() for s in self.secrets if s.deleted is None],
                    webhooks=self.webhooks if self.webhooks else {})

        if with_branches:
            branches = [b.get_json(with_results=with_results, with_last_results=with_last_results) for b in self.branches if b.deleted is None]
            branches.sort(key=lambda b: b['name'])
            data['branches'] = branches

        if with_user_data:
            data['data'] = self.user_data

        return data

class Branch(db.Model, DatesMixin):
    __tablename__ = "branches"
    id = Column(Integer, primary_key=True)
    name = Column(UnicodeText)  # display name
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)
    project = relationship('Project', back_populates="branches")
    branch_name = Column(UnicodeText)                             # branch name in the repository, PR is matched agains this
    ci_flows = relationship("Flow", order_by="desc(Flow.created)",
                            primaryjoin="and_(Branch.id==Flow.branch_id, Flow.kind==0)", viewonly=True)
    dev_flows = relationship("Flow", order_by="desc(Flow.created)",
                             primaryjoin="and_(Branch.id==Flow.branch_id, Flow.kind==1)", viewonly=True)
    ci_last_completed_flow_id = Column(Integer, ForeignKey('flows.id'))
    ci_last_completed_flow = relationship('Flow', foreign_keys=[ci_last_completed_flow_id])
    ci_last_incomplete_flow_id = Column(Integer, ForeignKey('flows.id'))
    ci_last_incomplete_flow = relationship('Flow', foreign_keys=[ci_last_incomplete_flow_id])
    stages = relationship("Stage", back_populates="branch", order_by="Stage.name")
    sequences = relationship("BranchSequence", back_populates="branch")
    comments = relationship("TestCaseComment", back_populates="branch")
    retention_policy = Column(JSONB)
    user_data = Column(JSONB, default={})
    user_data_ci = Column(JSONB, default={})
    user_data_dev = Column(JSONB, default={})

    #base_branch = relationship('BaseBranch', uselist=False, primaryjoin="or_(Branch.id==BaseBranch.ci_branch_id, Branch.id==BaseBranch.dev_branch_id)")

    def get_json(self, with_results=False, with_cfg=False, with_last_results=False, with_user_data=False):
        if self.retention_policy:
            retention_policy = self.retention_policy
        else:
            retention_policy = dict(ci_logs=6,
                                    dev_logs=3,
                                    ci_artifacts=6,
                                    dev_artifacts=3)

        data = dict(id=self.id,
                    created=self.created.strftime("%Y-%m-%dT%H:%M:%SZ") if self.created else None,
                    deleted=self.deleted.strftime("%Y-%m-%dT%H:%M:%SZ") if self.deleted else None,
                    name=self.name,
                    project_id=self.project_id,
                    project_name=self.project.name,
                    branch_name=self.branch_name,
                    retention_policy=retention_policy)

        if with_results:
            data['ci_flows'] = [f.get_json() for f in self.ci_flows[:10]]
            data['dev_flows'] = [f.get_json() for f in self.dev_flows[:10]]

        if with_last_results:
            data['last_completed_flow'] = None
            data['last_incomplete_flow'] = None

            f = self.ci_last_completed_flow
            if f:
                f_json = dict(id=f.id,
                              label=f.label,
                              finished=f.finished.strftime("%Y-%m-%dT%H:%M:%SZ") if f.finished else None,
                              errors=any((r.jobs_error > 0 for r in f.runs)))
                data['last_completed_flow'] = f_json

            f = self.ci_last_incomplete_flow
            if f:
                f_json = dict(id=f.id,
                              label=f.label,
                              created=f.created.strftime("%Y-%m-%dT%H:%M:%SZ"),
                              errors=any((r.jobs_error > 0 for r in f.runs)))
                data['last_incomplete_flow'] = f_json

        if with_cfg:
            data['stages'] = [s.get_json() for s in self.stages if s.deleted is None]

        if with_user_data:
            data['data'] = self.user_data
            data['data_ci'] = self.user_data_ci
            data['data_dev'] = self.user_data_dev

        return data

Index('ix_branches_name_project_id_not_deleted', Branch.name, Branch.project_id, postgresql_where=Branch.deleted.is_(None), unique=True)


# Sequence kinds:
# 0. KK_FLOW_SEQ
# 1. KK_CI_FLOW_SEQ
# 2. KK_DEV_FLOW_SEQ
# 3. KK_RUN_SEQ
# 4. KK_CI_RUN_SEQ
# 5. KK_DEV_RUN_SEQ
class BranchSequence(db.Model):
    __tablename__ = "branch_sequences"
    id = Column(Integer, primary_key=True)
    kind = Column(Integer, default=0)
    branch_id = Column(Integer, ForeignKey('branches.id'), nullable=False)
    branch = relationship('Branch', back_populates="sequences")
    stage_id = Column(Integer, ForeignKey('stages.id'), nullable=True)
    stage = relationship('Stage', back_populates="sequences")
    value = Column(Integer, default=0)

    def get_json(self):
        data = dict(id=self.id,
                    kind=self.kind,
                    branch_id=self.branch_id,
                    branch_name=self.branch.name,
                    stage_id=self.stage_id,
                    stage_name=self.stage.name if self.stage else None,
                    value=self.value)
        return data


class Secret(db.Model, DatesMixin):
    __tablename__ = "secrets"
    id = Column(Integer, primary_key=True)
    name = Column(UnicodeText)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)
    project = relationship('Project', back_populates="secrets")
    kind = Column(Integer, default=0)
    data = Column(JSONB)

    def get_json(self):
        data = dict(id=self.id,
                    created=self.created.strftime("%Y-%m-%dT%H:%M:%SZ") if self.created else None,
                    deleted=self.deleted.strftime("%Y-%m-%dT%H:%M:%SZ") if self.deleted else None,
                    name=self.name,
                    project_id=self.project_id,
                    project_name=self.project.name,
                    kind=consts.SECRET_KINDS_NAME[self.kind])
        data.update(self.data)
        if 'key' in data:
            data['key'] = '******'
        if 'secret' in data:
            data['secret'] = '******'
        return data


# PLANNING

class Stage(db.Model, DatesMixin):
    __tablename__ = "stages"
    id = Column(Integer, primary_key=True)
    name = Column(UnicodeText)
    description = Column(UnicodeText)
    branch_id = Column(Integer, ForeignKey('branches.id'), nullable=False)
    branch = relationship('Branch', back_populates="stages")
    enabled = Column(Boolean, default=True)
    schema = Column(JSONB, nullable=False)
    schema_code = Column(UnicodeText)
    triggers = Column(JSONB)
    timeouts = Column(JSONB)
    repo_access_token = Column(UnicodeText)
    repo_branch = Column(UnicodeText)
    repo_url = Column(UnicodeText)
    schema_file = Column(UnicodeText)
    schema_from_repo_enabled = Column(Boolean, default=False)
    repo_error = Column(UnicodeText)
    repo_refresh_interval = Column(UnicodeText)
    repo_refresh_job_id = Column(UnicodeText)
    repo_state = Column(Integer, default=consts.REPO_STATE_OK)
    repo_version = Column(UnicodeText)
    git_clone_params = Column(UnicodeText)
    runs = relationship('Run', back_populates="stage")
    sequences = relationship("BranchSequence", back_populates="stage")
    # services

    def get_json(self, with_schema=True):
        data = dict(id=self.id,
                    created=self.created.strftime("%Y-%m-%dT%H:%M:%SZ") if self.created else None,
                    deleted=self.deleted.strftime("%Y-%m-%dT%H:%M:%SZ") if self.deleted else None,
                    name=self.name,
                    description=self.description,
                    enabled=self.enabled,
                    schema_from_repo_enabled=self.schema_from_repo_enabled,
                    repo_url=self.repo_url,
                    repo_branch=self.repo_branch,
                    repo_access_token=self.repo_access_token,
                    repo_state=self.repo_state,
                    repo_error=self.repo_error,
                    repo_refresh_interval=self.repo_refresh_interval,
                    git_clone_params=self.git_clone_params,
                    repo_version=self.repo_version,
                    schema_file=self.schema_file)

        if with_schema:
            data['schema'] = self.schema
            data['schema_code'] = self.schema_code

        return data

    def __repr__(self):
        return "<Stage %s, '%s'>" % (self.id, self.name)

    def get_default_args(self):
        args = {}
        for param in self.schema['parameters']:
            args[param['name']] = param['default']
        return args

# class Config(db.Model, DatesMixin):
#     __tablename__ = "configs"
#     id = Column(Integer, primary_key=True)
#     name = Column(UnicodeText)
#     #vector =
#     environments = relationship("Environment", back_populates="config")
#     stage_id = Column(Integer, ForeignKey('stages.id'), nullable=False)
#     stage = relationship("Stage", back_populates="configs")

# class Environment(db.Model, DatesMixin):
#     __tablename__ = "environments"
#     id = Column(Integer, primary_key=True)
#     #system
#     #agents_group
#     config_id = Column(Integer, ForeignKey('configs.id'), nullable=False)
#     config = relationship("Config", back_populates="environments")
#     job_plan_id = Column(Integer, ForeignKey('job_plans.id'), nullable=False)
#     job_plan = relationship("JobPlan", back_populates="environments")

# EXECUTION



class RepoChanges(db.Model, DatesMixin):
    __tablename__ = "repo_changes"
    id = Column(Integer, primary_key=True)
    data = Column(JSONB, nullable=False)
    flow = relationship("Flow", back_populates="trigger_data")
    runs = relationship("Run", back_populates="repo_data")


def _get_report_entries(artifacts, infix):
    report_entries = []
    if (isinstance(artifacts, dict) and 'public' in artifacts and 'entries' in artifacts['public']):
        for rep_ent in artifacts['public']['entries']:
            url = '/bk/artifacts/public/%s/%s' % (infix, rep_ent)
            name = rep_ent.rsplit('/', 1)[-1].split('.', 1)[0].capitalize()
            rep = dict(name=name,
                       url=url)
            report_entries.append(rep)
    return report_entries


class Flow(db.Model, DatesMixin):
    __tablename__ = "flows"
    id = Column(Integer, primary_key=True)
    finished = Column(DateTime(timezone=True))
    state = Column(Integer, default=consts.FLOW_STATE_IN_PROGRESS)
    kind = Column(Integer, default=consts.FLOW_KIND_CI)  # 0 - CI, 1 - dev
    branch_name = Column(UnicodeText)
    branch_id = Column(Integer, ForeignKey('branches.id'), nullable=False)
    branch = relationship('Branch', foreign_keys=[branch_id])
    runs = relationship('Run', back_populates="flow", order_by="Run.created")
    args = Column(JSONB, nullable=False, default={})
    artifacts = Column(JSONB, default={})
    label = Column(UnicodeText)
    trigger_data_id = Column(Integer, ForeignKey('repo_changes.id'))
    trigger_data = relationship('RepoChanges')
    artifacts_files = relationship('Artifact', back_populates="flow")
    comments = relationship("TestCaseComment", back_populates="last_flow")
    summary = Column(JSONB, default={})
    user_data = Column(JSONB, default={})
    seq = Column(JSONB, default={})

    Index('ix_flows_branch_id_kind', branch_id, kind)

    def __repr__(self):
        return "<Flow %s, label %s, kind %s, state %s>" % (self.id,
                                                           self.get_label(),
                                                           consts.FLOW_KINDS_NAME.get(self.kind, 'unknown %d' % self.kind),
                                                           consts.FLOW_STATES_NAME.get(self.state, 'unknown %d' % self.state))

    def get_label(self):
        return self.label if self.label else ("%d." % self.id)

    def get_json(self, with_project=True, with_branch=True, with_schema=True, with_user_data=False, with_stages=True, with_runs=True):
        if self.state == consts.FLOW_STATE_COMPLETED:
            duration = self.finished - self.created
        else:
            duration = utils.utcnow() - self.created

        trigger = None
        if self.trigger_data:
            trigger = self.trigger_data.data[0]

        data = dict(id=self.id,
                    label=self.get_label(),
                    created=self.created.strftime("%Y-%m-%dT%H:%M:%SZ") if self.created else None,
                    finished=self.finished.strftime("%Y-%m-%dT%H:%M:%SZ") if self.finished else None,
                    deleted=self.deleted.strftime("%Y-%m-%dT%H:%M:%SZ") if self.deleted else None,
                    state=consts.FLOW_STATES_NAME[self.state],
                    kind='ci' if self.kind == consts.FLOW_KIND_CI else 'dev',
                    duration=duration_to_txt(duration),
                    branch_name=self.branch_name,
                    args=self.args,
                    trigger=trigger,
                    artifacts=self.artifacts,
                    seq=self.seq)

        infix = 'f/%d' % self.id
        data['report_entries'] = _get_report_entries(self.artifacts, infix)

        if with_stages:
            stages = [s.get_json(with_schema=with_schema) for s in self.branch.stages if s.deleted is None]
            data['stages'] = stages

        if with_runs:
            runs = [r.get_json(with_project=False, with_branch=False, with_artifacts=False) for r in self.runs]
            data['runs'] = runs

        if with_project:
            data['project_id'] = self.branch.project_id
            data['project_name'] = self.branch.project.name

        if with_branch:
            data['branch_id'] = self.branch_id
            data['base_branch_name'] = self.branch.name

        if with_user_data:
            data['data'] = self.user_data

        return data


Index('ix_flows_created', Flow.created)


class Run(db.Model, DatesMixin):
    __tablename__ = "runs"
    id = Column(Integer, primary_key=True)
    started = Column(DateTime(timezone=True))    # time when the run got a first non-deleted job
    finished = Column(DateTime(timezone=True))    # time when all jobs finished first time
    finished_again = Column(DateTime(timezone=True))    # time when all jobs finished
    state = Column(Integer, default=consts.RUN_STATE_IN_PROGRESS)
    email_sent = Column(DateTime(timezone=True))
    note = Column(UnicodeText)
    stage_id = Column(Integer, ForeignKey('stages.id'), nullable=False)
    stage = relationship('Stage', back_populates="runs")
    flow_id = Column(Integer, ForeignKey('flows.id'), nullable=False, index=True)
    flow = relationship('Flow', back_populates="runs")
    jobs = relationship('Job', back_populates="run")
    artifacts_files = relationship('Artifact', back_populates="run")
    hard_timeout_reached = Column(DateTime(timezone=True))
    soft_timeout_reached = Column(DateTime(timezone=True))
    args = Column(JSONB, nullable=False, default={})
    # stats - result changes
    fix_cnt = Column(Integer, default=0)
    new_cnt = Column(Integer, default=0)
    no_change_cnt = Column(Integer, default=0)
    regr_cnt = Column(Integer, default=0)
    issues_new = Column(Integer, default=0)
    issues_total = Column(Integer, default=0)
    jobs_error = Column(Integer, default=0)
    jobs_total = Column(Integer, default=0)
    tests_not_run = Column(Integer, default=0)
    tests_passed = Column(Integer, default=0)
    tests_total = Column(Integer, default=0)
    artifacts = Column(JSONB, default={})
    label = Column(UnicodeText)
    reason = Column(JSONB, nullable=False)
    repo_data_id = Column(Integer, ForeignKey('repo_changes.id'))
    repo_data = relationship('RepoChanges')
    processed_at = Column(DateTime(timezone=True))    # time when results analysis completed
    seq = Column(JSONB, default={})

    def __repr__(self):
        return "<Run %s, state %s>" % (self.id, consts.RUN_STATES_NAME.get(self.state, 'unknown %d' % self.state))

    def get_json(self, with_project=True, with_branch=True, with_artifacts=True, with_counts=True):
        jobs_processing = 0
        jobs_executing = 0
        jobs_waiting = 0
        jobs_error = 0
        jobs_total = 0
        duration = ''

        if self.state == consts.RUN_STATE_PROCESSED:
            jobs_total = self.jobs_total
            jobs_error = self.jobs_error
            if self.started:
                begin = self.started
            else:
                begin = self.created
            if self.finished is None:
                log.error('PROBLEM WITH NONE TIMESTAMP in run %s', self)
                duration = utils.utcnow() - begin
            else:
                duration = self.finished - begin

            duration = duration_to_txt(duration)

        elif with_counts:
            non_covered_jobs = Job.query.filter_by(run=self).filter_by(covered=False).all()
            jobs_total = len(non_covered_jobs)
            jobs_completed = 0
            last_time = None
            for job in non_covered_jobs:
                if job.state == consts.JOB_STATE_EXECUTING_FINISHED:
                    jobs_processing += 1
                elif job.state == consts.JOB_STATE_ASSIGNED:
                    jobs_executing += 1
                elif job.state != consts.JOB_STATE_COMPLETED:
                    jobs_waiting += 1
                elif job.state == consts.JOB_STATE_COMPLETED:
                    jobs_completed += 1
                    if last_time is None or (job.completed and job.completed > last_time):
                        last_time = job.completed

                if job.completion_status not in [consts.JOB_CMPLT_ALL_OK, None]:
                    jobs_error += 1

            if jobs_total == jobs_completed and last_time:
                duration = last_time - self.created
            else:
                duration = utils.utcnow() - self.created

            duration = duration_to_txt(duration)

        data = dict(id=self.id,
                    label=self.label,
                    created=self.created.strftime("%Y-%m-%dT%H:%M:%SZ") if self.created else None,
                    deleted=self.deleted.strftime("%Y-%m-%dT%H:%M:%SZ") if self.deleted else None,
                    started=self.started.strftime("%Y-%m-%dT%H:%M:%SZ") if self.started else None,
                    finished=self.finished.strftime("%Y-%m-%dT%H:%M:%SZ") if self.finished else None,
                    processed_at=self.processed_at.strftime("%Y-%m-%dT%H:%M:%SZ") if self.processed_at else None,
                    duration=duration,
                    state=consts.RUN_STATES_NAME[self.state],
                    stage_name=self.stage.name,
                    stage_id=self.stage_id,
                    flow_id=self.flow_id,
                    flow_kind='ci' if self.flow.kind == consts.FLOW_KIND_CI else 'dev',
                    flow_label=self.flow.get_label(),
                    args=self.args,
                    jobs_total=jobs_total,
                    jobs_waiting=jobs_waiting,
                    jobs_executing=jobs_executing,
                    jobs_processing=jobs_processing,
                    jobs_error=jobs_error,
                    tests_total=self.tests_total,
                    tests_passed=self.tests_passed,
                    tests_not_run=self.tests_not_run,
                    issues_total=self.issues_total,
                    issues_new=self.issues_new,
                    new_cnt=self.new_cnt,
                    no_change_cnt=self.no_change_cnt,
                    regr_cnt=self.regr_cnt,
                    fix_cnt=self.fix_cnt,
                    repo_data=self.repo_data.data if self.repo_data else None,
                    reason=self.reason['reason'],
                    note=self.note,
                    seq=self.seq)

        if with_project:
            data['project_id'] = self.flow.branch.project_id
            data['project_name'] = self.flow.branch.project.name

        if with_branch:
            data['branch_id'] = self.flow.branch_id
            data['branch_name'] = self.flow.branch.name

        if with_artifacts:
            data['artifacts_total'] = len(self.artifacts_files)
            infix = 'r/%d' % self.id
            data['report_entries'] = _get_report_entries(self.artifacts, infix)

        return data


class Step(db.Model, DatesMixin):
    __tablename__ = "steps"
    id = Column(Integer, primary_key=True)
    index = Column(Integer, nullable=False)
    job_id = Column(Integer, ForeignKey('jobs.id'), nullable=False)
    job = relationship("Job", back_populates="steps")
    tool_id = Column(Integer, ForeignKey('tools.id'), nullable=False)
    tool = relationship("Tool", back_populates="steps")
    fields = Column(JSONB, nullable=False)
    result = Column(JSONB)
    status = Column(Integer)
    fields_masked = Column(JSONB, nullable=True)
    fields_raw = Column(JSONB, nullable=True)
    # services

    def get_json(self, with_fields=True, mask_secrets=False):
        data = dict(id=self.id,
                    index=self.index,
                    tool=self.tool.name,
                    tool_id=self.tool_id,
                    tool_location=self.tool.location,
                    tool_entry=self.tool.entry,
                    tool_version=self.tool.version,
                    job_id=self.job_id,
                    status=self.status,
                    result=self.result)

        if with_fields:
            if mask_secrets and self.fields_masked:
                fields = self.fields_masked
            elif self.fields:
                fields = self.fields
            else:
                fields = self.fields_raw

            name = self.tool.name
            if 'name' in fields:
                name = fields['name']
            elif self.tool.name == 'shell':
                if 'script' in fields and fields['script']:
                    name = fields['script'].strip().splitlines()[0] + '...'
                elif 'cmd' in fields and fields['cmd']:
                    name = fields['cmd']
            elif self.tool.name == 'git':
                name = 'checkout: ' + fields['checkout']

            data['name'] = name

            for f, v in fields.items():
                data[f] = v

        return data


class Job(db.Model, DatesMixin):
    __tablename__ = "jobs"
    id = Column(Integer, primary_key=True)
    name = Column(UnicodeText)
    assigned = Column(DateTime(timezone=True))
    started = Column(DateTime(timezone=True))
    finished = Column(DateTime(timezone=True))            # time when agent reported that job is finished
    processing_started = Column(DateTime(timezone=True))  # TODO: this is never used
    completed = Column(DateTime(timezone=True))
    run_id = Column(Integer, ForeignKey('runs.id'), nullable=False)
    run = relationship("Run", back_populates="jobs")
    steps = relationship("Step", back_populates="job", order_by="Step.index")
    state = Column(Integer, default=consts.JOB_STATE_QUEUED)
    completion_status = Column(Integer)
    covered = Column(Boolean, default=False)
    notes = Column(UnicodeText)
    agent = relationship('Agent', uselist=False, back_populates="job",
                            foreign_keys="Agent.job_id", post_update=True)
    agent_used_id = Column(Integer, ForeignKey('agents.id'))
    agent_used = relationship('Agent', foreign_keys=[agent_used_id], post_update=True)
    agents_group_id = Column(Integer, ForeignKey('agents_groups.id'), nullable=False)
    agents_group = relationship('AgentsGroup', back_populates="jobs")
    timeout = Column(Integer)
    system_id = Column(Integer, ForeignKey('systems.id', name='fk_systems_jobs'), nullable=False) # match name fk_systems_jobs with name in alembic migration
    system = relationship('System', back_populates="jobs")
    results = relationship('TestCaseResult', back_populates="job")
    issues = relationship('Issue', back_populates="job")

    def get_json(self, with_steps=True, mask_secrets=False):
        if self.started:
            if self.finished:
                duration = self.finished - self.started
            else:
                duration = utils.utcnow() - self.started
            duration = duration_to_txt(duration)
        else:
            duration = ''

        data = dict(id=self.id,
                    created=self.created.strftime("%Y-%m-%dT%H:%M:%SZ") if self.created else None,
                    deleted=self.deleted.strftime("%Y-%m-%dT%H:%M:%SZ") if self.deleted else None,
                    started=self.started.strftime("%Y-%m-%dT%H:%M:%SZ") if self.started else None,
                    finished=self.finished.strftime("%Y-%m-%dT%H:%M:%SZ") if self.finished else None,
                    completed=self.completed.strftime("%Y-%m-%dT%H:%M:%SZ") if self.completed else None,
                    # processing_started=self.processing_started.strftime(
                    #     "%Y-%m-%dT%H:%M:%SZ") if self.processing_started else None,
                    duration=duration,
                    name=self.name,
                    state=self.state,
                    completion_status=self.completion_status,
                    timeout=self.timeout,
                    covered=self.covered,
                    notes=self.notes,
                    system_id=self.system_id,
                    system=self.system.name,
                    executor=self.system.executor,
                    run_id=self.run_id,
                    agents_group_id=self.agents_group_id,
                    agents_group_name=self.agents_group.name,
                    agent_id=self.agent_used_id if self.agent_used else 0,
                    agent_name=self.agent_used.name if self.agent_used else '')

        if with_steps:
            steps = []
            for s in sorted(self.steps, key=lambda s: s.index):
                s = s.get_json(mask_secrets=mask_secrets)
                steps.append(s)
            data['steps'] = steps

        return data


    def __repr__(self):
        txt = 'Job %s, state:%s' % (self.id, consts.JOB_STATES_NAME[self.state])
        txt += ', g:%s' % self.agents_group_id
        if self.agent_used_id:
            txt += ', ag:%s' % self.agent_used_id
        return "<%s>" % txt


class TestCase(db.Model, DatesMixin):
    __tablename__ = "test_cases"
    __test__ = False  # do not treat this class as a test by pytest
    id = Column(Integer, primary_key=True)
    name = Column(UnicodeText, unique=True)
    tool_id = Column(Integer, ForeignKey('tools.id'), nullable=False)
    tool = relationship('Tool', back_populates="test_cases")
    results = relationship("TestCaseResult", back_populates="test_case")
    comments = relationship("TestCaseComment", back_populates="test_case")


class TestCaseResult(db.Model):
    __tablename__ = "test_case_results"
    __test__ = False  # do not treat this class as a test by pytest
    id = Column(Integer, primary_key=True)
    test_case_id = Column(Integer, ForeignKey('test_cases.id'), nullable=False)
    test_case = relationship('TestCase', back_populates="results")
    job_id = Column(Integer, ForeignKey('jobs.id'), nullable=False)
    job = relationship('Job', back_populates="results")
    result = Column(Integer, default=0)
    values = Column(JSONB)
    cmd_line = Column(UnicodeText)
    instability = Column(Integer, default=0)
    age = Column(Integer, default=0)
    change = Column(Integer, default=consts.TC_RESULT_CHANGE_NO)
    relevancy = Column(Integer, default=0)
    comment_id = Column(Integer,
                        ForeignKey('test_case_comments.id',
                                   # this is WA, remember to set correct fk name in migration
                                   name='fk_test_case_comments_test_case_results'),
                        nullable=True)
    comment = relationship('TestCaseComment', back_populates="test_case_results")

    Index('ix_test_case_results_test_case_id', test_case_id)
    Index('ix_test_case_results_job_id', job_id)
    Index('ix_test_case_results_comment_id', comment_id)

    def __repr__(self):
        txt = 'TCR %s, result:%s' % (self.id, consts.TC_RESULTS_NAME[self.result])
        return "<%s>" % txt

    def get_json(self, with_extra=False, with_comment=False):
        data = dict(id=self.id,
                    test_case_id=self.test_case_id,
                    test_case_name=self.test_case.name,
                    result=self.result,
                    values=self.values,
                    cmd_line=self.cmd_line,
                    instability=self.instability,
                    age=self.age,
                    change=self.change,
                    relevancy=self.relevancy if self.relevancy is not None else 0,
                    job_id=self.job_id,
                    job_name=self.job.name,
                    agents_group_name=self.job.agents_group.name,
                    agents_group_id=self.job.agents_group_id,
                    system_name=self.job.system.name,
                    system_id=self.job.system_id,
                    agent_name=self.job.agent_used.name if self.job.agent_used else '',
                    agent_id=self.job.agent_used_id if self.job.agent_used else 0)

        if with_extra:
            data['project_id'] = self.job.run.flow.branch.project_id
            data['project_name'] = self.job.run.flow.branch.project.name
            data['branch_id'] = self.job.run.flow.branch_id
            data['branch_name'] = self.job.run.flow.branch.name
            data['flow_id'] = self.job.run.flow_id
            data['flow_kind'] = 'ci' if self.job.run.flow.kind == consts.FLOW_KIND_CI else 'dev'
            data['flow_label'] = self.job.run.flow.get_label()
            created_at = self.job.run.flow.created
            data['flow_created_at'] = created_at.strftime("%Y-%m-%dT%H:%M:%SZ") if created_at else None
            data['run_id'] = self.job.run_id
            data['stage_id'] = self.job.run.stage_id
            data['stage_name'] = self.job.run.stage.name

        if with_comment and self.comment and self.comment.data:
            data['comment'] = dict(state=self.comment.state,
                                   data=list(reversed(self.comment.data)))

        return data


class TestCaseComment(db.Model):
    __tablename__ = "test_case_comments"
    id = Column(Integer, primary_key=True)
    test_case_id = Column(Integer, ForeignKey('test_cases.id'), nullable=True)
    test_case = relationship('TestCase', back_populates="comments")
    branch_id = Column(Integer, ForeignKey('branches.id'), nullable=True)
    branch = relationship('Branch', back_populates="comments")
    last_flow_id = Column(Integer, ForeignKey('flows.id'), nullable=True)
    last_flow = relationship('Flow', back_populates="comments")
    test_case_results = relationship('TestCaseResult', back_populates="comment")
    state = Column(Integer, default=consts.TC_COMMENT_NEW)
    data = Column(JSONB)

    def get_json(self):
        return dict(id=self.id,
                    state=self.state,
                    data=self.data)


class Issue(db.Model):
    __tablename__ = "issues"
    id = Column(Integer, primary_key=True)
    issue_type = Column(Integer, default=consts.ISSUE_TYPE_ERROR)
    line = Column(Integer)
    column = Column(Integer)
    path = Column(UnicodeText)
    symbol = Column(UnicodeText)
    message = Column(UnicodeText)
    job_id = Column(Integer, ForeignKey('jobs.id'), nullable=False)
    job = relationship('Job', back_populates="issues")
    extra = Column(JSONB)
    age = Column(Integer, default=0)

    def get_json(self):
        data = dict(id=self.id,
                    issue_type=self.issue_type,
                    line=self.line,
                    column=self.column,
                    path=self.path,
                    symbol=self.symbol,
                    message=self.message,
                    age=self.age,
                    job_id=self.job_id,
                    job_name=self.job.name,
                    agents_group_name=self.job.agents_group.name,
                    agents_group_id=self.job.agents_group_id,
                    agent_name=self.job.agent_used.name,
                    agent_id=self.job.agent_used_id)
        if self.extra:
            data.update(self.extra)
        return data


class File(db.Model):
    __tablename__ = "files"
    id = Column(Integer, primary_key=True)
    path = Column(UnicodeText)
    artifacts = relationship('Artifact', back_populates="file")


class Artifact(db.Model):
    __tablename__ = "artifacts"
    id = Column(Integer, primary_key=True)
    file_id = Column(Integer, ForeignKey('files.id'), nullable=False)
    file = relationship('File', back_populates="artifacts")
    flow_id = Column(Integer, ForeignKey('flows.id'), nullable=False, index=True)
    flow = relationship('Flow', back_populates="artifacts_files")
    run_id = Column(Integer, ForeignKey('runs.id'), nullable=False, index=True)
    run = relationship('Run', back_populates="artifacts_files")
    size = Column(Integer, default=0)
    section = Column(Integer, default=0)

    def get_json(self):
        return dict(id=self.id,
                    path=self.file.path,
                    size=self.size,
                    flow_id=self.flow_id,
                    run_id=self.run_id,
                    stage=self.run.stage.name)


class APSchedulerJob(db.Model):
    __tablename__ = 'apscheduler_jobs'
    id = Column(Unicode(191), autoincrement=False, nullable=False, primary_key=True)
    next_run_time = Column(DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=True, index=True, unique=False)
    job_state = Column(BYTEA, autoincrement=False, nullable=False)


# RESOURCES

class System(db.Model):
    __tablename__ = "systems"
    id = Column(Integer, primary_key=True)
    name = Column(UnicodeText)
    executor = Column(UnicodeText)
    jobs = relationship('Job', back_populates="system")
    UniqueConstraint(name, executor, name='uq_system_name_executor')

    def get_json(self):
        return dict(id=self.id,
                    name=self.name,
                    executor=self.executor)


class Tool(db.Model, DatesMixin):
    __tablename__ = "tools"
    id = Column(Integer, primary_key=True)
    name = Column(UnicodeText)
    description = Column(UnicodeText)
    configuration = Column(UnicodeText)
    steps = relationship("Step", back_populates="tool")
    fields = Column(JSONB, nullable=False)
    # TODO should it have optional reference to project so that there are local and global tools?
    test_cases = relationship("TestCase", back_populates="tool")
    location = Column(UnicodeText)
    entry = Column(UnicodeText)
    version = Column(UnicodeText)
    url = Column(UnicodeText)
    tag = Column(UnicodeText)
    tool_file = Column(UnicodeText)
    UniqueConstraint(name, version, name='uq_tool_name_version')

    def __repr__(self):
        return "<Tool %s, '%s'>" % (self.id, self.name)

    def get_json(self, with_details=False):
        data = dict(id=self.id,
                    name=self.name)
        if with_details:
            data['location'] = self.location
            data['entry'] = self.entry
            data['version'] = self.version
            data['description'] = self.description
            data['fields'] = self.fields
            data['url'] = self.url
            data['tag'] = self.tag
            data['tool_file'] = self.tool_file
        return data


class AgentAssignment(db.Model):
    __tablename__ = "agent_assignments"
    agent_id = Column(Integer, ForeignKey('agents.id'), primary_key=True)
    agent = relationship('Agent', back_populates="agents_groups")
    agents_group_id = Column(Integer, ForeignKey('agents_groups.id'), primary_key=True)
    agents_group = relationship('AgentsGroup', back_populates="agents")


class AgentsGroup(db.Model, DatesMixin):
    __tablename__ = "agents_groups"
    id = Column(Integer, primary_key=True)
    name = Column(UnicodeText)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=True)
    project = relationship('Project', back_populates="agents_groups")
    # agents = relationship("Agent", back_populates="agents_group")  # static assignments
    agents = relationship('AgentAssignment', back_populates="agents_group")
    jobs = relationship("Job", back_populates="agents_group")
    deployment = Column(JSONB)
    extra_attrs = Column(JSONB)

    def get_json(self):
        deployment = self.deployment
        if not deployment:
            deployment = dict(method=0)

        if 'aws' not in deployment:
            deployment['aws'] = dict(region='', instances_limit=5, default_image='', instance_type='', disk_size=0,
                                     destruction_after_jobs=1, destruction_after_time=30)
        else:
            if 'destruction_after_jobs' not in deployment['aws']:
                deployment['aws']['destruction_after_jobs'] = 1
            if 'destruction_after_time' not in deployment['aws']:
                deployment['aws']['destruction_after_time'] = 30
            if 'disk_size' not in deployment['aws']:
                deployment['aws']['disk_size'] = 0

        if 'aws_ecs_fargate' not in deployment:
            deployment['aws_ecs_fargate'] = dict(region='', instances_limit=5, cluster='', subnets='', security_groups='')

        if 'azure_vm' not in deployment:
            deployment['azure_vm'] = dict(location='', instances_limit=5, default_image='', vm_size='',
                                          destruction_after_jobs=1, destruction_after_time=30)

        if 'kubernetes' not in deployment:
            deployment['kubernetes'] = dict(instances_limit=5)

        return dict(id=self.id,
                    created=self.created.strftime("%Y-%m-%dT%H:%M:%SZ") if self.created else None,
                    deleted=self.deleted.strftime("%Y-%m-%dT%H:%M:%SZ") if self.deleted else None,
                    name=self.name,
                    project_id=self.project_id,
                    project_name=self.project.name if self.project else None,
                    agents_count=len([a for a in self.agents if not a.agent.deleted]),
                    deployment=deployment)

    def get_deployment(self):
        method = self.deployment['method']
        if method == consts.AGENT_DEPLOYMENT_METHOD_AWS_EC2:
            depl = self.deployment['aws']
        elif method == consts.AGENT_DEPLOYMENT_METHOD_AWS_ECS_FARGATE:
            depl = self.deployment['aws_ecs_fargate']
        elif method == consts.AGENT_DEPLOYMENT_METHOD_AZURE_VM:
            depl = self.deployment['azure_vm']
        elif method == consts.AGENT_DEPLOYMENT_METHOD_K8S:
            depl = self.deployment['kubernetes']
        else:
            msg = 'deployment method %d in agents group id:%d not implemented' % (self.deployment['method'], self.id)
            raise Exception(msg)
        return method, depl




class Agent(db.Model, DatesMixin):
    __tablename__ = "agents"
    id = Column(Integer, primary_key=True)
    name = Column(UnicodeText, nullable=False)
    address = Column(UnicodeText, index=True, nullable=False, unique=True)
    ip_address = Column(UnicodeText)
    state = Column(Integer, default=0)
    disabled = Column(Boolean, default=False)
    comment = Column(UnicodeText)
    status_line = Column(UnicodeText)
    job_id = Column(Integer, ForeignKey('jobs.id'))
    job = relationship('Job', back_populates="agent", foreign_keys=[job_id])
    authorized = Column(Boolean, default=False)
    last_seen = Column(DateTime(timezone=True))
    host_info = Column(JSONB)
    user_attrs = Column(JSONB)
    extra_attrs = Column(JSONB)
    agents_groups = relationship('AgentAssignment', back_populates="agent")

    def __repr__(self):
        return "<Agent %s, job:%s>" % (self.id, self.job_id)

    def get_json(self):
        return dict(id=self.id,
                    created=self.created.strftime("%Y-%m-%dT%H:%M:%SZ") if self.created else None,
                    deleted=self.deleted.strftime("%Y-%m-%dT%H:%M:%SZ") if self.deleted else None,
                    last_seen=self.last_seen.strftime("%Y-%m-%dT%H:%M:%SZ") if self.last_seen else None,
                    name=self.name,
                    address=self.address,
                    authorized=self.authorized,
                    ip_address=self.ip_address,
                    state=self.state,
                    disabled=self.disabled,
                    comment=self.comment,
                    status_line=self.status_line,
                    host_info=self.host_info,
                    user_attrs=self.user_attrs,
                    extra_attrs=self.extra_attrs,
                    groups=[dict(id=a.agents_group.id, name=a.agents_group.name) for a in self.agents_groups],
                    job=self.job.get_json() if self.job else None)


class Setting(db.Model):
    __tablename__ = "settings"
    id = Column(Integer, primary_key=True)
    name = Column(UnicodeText)
    value = Column(UnicodeText)
    val_type = Column(UnicodeText)  # integer, text, boolean, password
    group = Column(UnicodeText)

    def get_json(self):
        return {
            "id": self.id,
            "name": self.name,
            "value": self.get_value(),
            "type": self.val_type}

    def get_value(self, password_blank=True):
        if self.val_type == "integer":
            return int(self.value)
        if self.val_type == "boolean":
            return self.value == 'True'
        if self.val_type == "password" and password_blank:
            return ''
        if self.value is None:
            return ''
        return self.value

    def set_value(self, value):
        if self.val_type == "integer":
            self.value = str(value)
        elif self.val_type == "boolean":
            self.value = str(value)
        else:
            self.value = value


def get_setting(group, name):
    s = Setting.query.filter_by(group=group, name=name).one_or_none()
    if s is None:
        raise Exception('cannot find setting %s:%s' % (group, name))

    return s.get_value(password_blank=False)


def get_settings_group(group):
    ss = Setting.query.filter_by(group=group).all()
    if not ss:
        raise Exception('cannot find settings in %s group' % group)

    resp = {}
    for s in ss:
        resp[s.name] = s.get_value(password_blank=False)
    return resp


def set_setting(group, name, val):
    s = Setting.query.filter_by(group=group, name=name).one_or_none()
    if s is None:
        raise Exception('cannot find setting %s:%s' % (group, name))

    s.value = val
    db.session.commit()


class User(db.Model, DatesMixin):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(UnicodeText)
    password = Column(UnicodeText)
    sessions = relationship("UserSession", back_populates="user")
    details = Column(JSONB)

    def get_json(self):
        if self.details:
            details = self.details
        else:
            details = {}

        return dict(id=self.id,
                    name=self.name,
                    enabled=details.get('enabled', True),
                    email=details.get('email', ''),
                    superadmin=self.name == 'admin')


class UserSession(db.Model, DatesMixin):
    __tablename__ = "user_sessions"
    id = Column(Integer, primary_key=True)
    token = Column(UnicodeText)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    user = relationship('User', back_populates="sessions")
    details = Column(JSONB)

    def get_json(self):
        return dict(id=self.id,
                    token=self.token,
                    user=self.user.get_json() if self.user else None)


class CasbinRule(db.Model, DatesMixin):
    __tablename__ = "casbin_rules"

    id = Column(Integer, primary_key=True)
    ptype = Column(String(255))
    v0 = Column(String(255))
    v1 = Column(String(255))
    v2 = Column(String(255))
    v3 = Column(String(255))
    v4 = Column(String(255))
    v5 = Column(String(255))

    def __str__(self):
        arr = [self.ptype]
        for v in (self.v0, self.v1, self.v2, self.v3, self.v4, self.v5):
            if v is None:
                break
            arr.append(v)
        return ", ".join(arr)

    def __repr__(self):
        return '<CasbinRule {}: "{}">'.format(self.id, str(self))
