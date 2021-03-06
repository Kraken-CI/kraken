# Copyright 2020 The Kraken Authors
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

import datetime
import logging

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Boolean, DateTime, ForeignKey, Integer, String, Text, Unicode, UnicodeText
from sqlalchemy import event, UniqueConstraint
from sqlalchemy.orm import relationship, mapper
from sqlalchemy.dialects.postgresql import JSONB, DOUBLE_PRECISION, BYTEA

from . import consts

log = logging.getLogger(__name__)

db = SQLAlchemy()


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
    created = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)
    updated = Column(DateTime, nullable=False, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    deleted = Column(DateTime)


class Project(db.Model, DatesMixin):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True)
    name = Column(Unicode(50))
    description = Column(Unicode(200))
    branches = relationship("Branch", back_populates="project", order_by="Branch.created")
    secrets = relationship("Secret", back_populates="project", order_by="Secret.name")
    agents_groups = relationship("AgentsGroup", back_populates="project")
    webhooks = Column(JSONB)

    def get_json(self, with_results=False):
        branches = [b.get_json(with_results=with_results) for b in self.branches if b.deleted is None]
        branches.sort(key=lambda b: b['name'])
        return dict(id=self.id,
                    created=self.created.strftime("%Y-%m-%dT%H:%M:%SZ") if self.created else None,
                    deleted=self.deleted.strftime("%Y-%m-%dT%H:%M:%SZ") if self.deleted else None,
                    name=self.name,
                    description=self.description,
                    branches=branches,
                    secrets=[s.get_json() for s in self.secrets if s.deleted is None],
                    webhooks=self.webhooks if self.webhooks else {})


class Branch(db.Model, DatesMixin):
    __tablename__ = "branches"
    id = Column(Integer, primary_key=True)
    name = Column(Unicode(255))
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)
    project = relationship('Project', back_populates="branches")
    branch_name = Column(Unicode(255))  # TODO: it seems that it is not used
    ci_flows = relationship("Flow", order_by="desc(Flow.created)",
                            primaryjoin="and_(Branch.id==Flow.branch_id, Flow.kind==0)", viewonly=True)
    dev_flows = relationship("Flow", order_by="desc(Flow.created)",
                             primaryjoin="and_(Branch.id==Flow.branch_id, Flow.kind==1)", viewonly=True)
    stages = relationship("Stage", back_populates="branch", order_by="Stage.name")
    sequences = relationship("BranchSequence", back_populates="branch")

    #base_branch = relationship('BaseBranch', uselist=False, primaryjoin="or_(Branch.id==BaseBranch.ci_branch_id, Branch.id==BaseBranch.dev_branch_id)")
    #flows = relationship("Flow", back_populates="branch", order_by="desc(Flow.created)")

    def get_json(self, with_results=False, with_cfg=False):
        data = dict(id=self.id,
                    created=self.created.strftime("%Y-%m-%dT%H:%M:%SZ") if self.created else None,
                    deleted=self.deleted.strftime("%Y-%m-%dT%H:%M:%SZ") if self.deleted else None,
                    name=self.name,
                    project_id=self.project_id,
                    project_name=self.project.name,
                    branch_name=self.branch_name)
        if with_results:
            data['ci_flows'] = [f.get_json() for f in self.ci_flows[:10]]
            data['dev_flows'] = [f.get_json() for f in self.dev_flows[:10]]
        if with_cfg:
            data['stages'] = [s.get_json() for s in self.stages if s.deleted is None]
        return data


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
    name = Column(Unicode(255))
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
    name = Column(Unicode(50))
    description = Column(Unicode(1024))
    branch_id = Column(Integer, ForeignKey('branches.id'), nullable=False)
    branch = relationship('Branch', back_populates="stages")
    enabled = Column(Boolean, default=True)
    schema = Column(JSONB, nullable=False)
    schema_code = Column(UnicodeText)
    schema_from_repo_enabled = Column(Boolean, default=False)
    repo_url = Column(UnicodeText)
    repo_branch = Column(UnicodeText)
    repo_access_token = Column(UnicodeText)
    repo_state = Column(Integer, default=consts.REPO_STATE_OK)
    repo_error = Column(UnicodeText)
    repo_version = Column(UnicodeText)
    repo_refresh_interval = Column(UnicodeText)
    repo_refresh_job_id = Column(UnicodeText)
    schema_file = Column(UnicodeText)
    triggers = Column(JSONB)
    timeouts = Column(JSONB)
    runs = relationship('Run', back_populates="stage")
    sequences = relationship("BranchSequence", back_populates="stage")
    # services

    def get_json(self):
        return dict(id=self.id,
                    created=self.created.strftime("%Y-%m-%dT%H:%M:%SZ") if self.created else None,
                    deleted=self.deleted.strftime("%Y-%m-%dT%H:%M:%SZ") if self.deleted else None,
                    name=self.name,
                    description=self.description,
                    enabled=self.enabled,
                    schema=self.schema,
                    schema_code=self.schema_code,
                    schema_from_repo_enabled=self.schema_from_repo_enabled,
                    repo_url=self.repo_url,
                    repo_branch=self.repo_branch,
                    repo_access_token=self.repo_access_token,
                    repo_state=self.repo_state,
                    repo_error=self.repo_error,
                    repo_refresh_interval=self.repo_refresh_interval,
                    repo_version=self.repo_version,
                    schema_file=self.schema_file)

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
#     name = Column(Unicode(50))
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


class Flow(db.Model, DatesMixin):
    __tablename__ = "flows"
    id = Column(Integer, primary_key=True)
    label = Column(Unicode(200))
    finished = Column(DateTime)
    state = Column(Integer, default=consts.FLOW_STATE_IN_PROGRESS)
    kind = Column(Integer, default=consts.FLOW_KIND_CI)  # 0 - CI, 1 - dev
    branch_name = Column(Unicode(255))
    branch_id = Column(Integer, ForeignKey('branches.id'), nullable=False)
    branch = relationship('Branch')
    runs = relationship('Run', back_populates="flow", order_by="Run.created")
    args = Column(JSONB, nullable=False, default={})
    trigger_data = Column(JSONB)
    artifacts = Column(JSONB, default={})
    artifacts_files = relationship('Artifact', back_populates="flow")

    def get_label(self):
        return self.label if self.label else ("%d." % self.id)

    def get_json(self):
        if self.state == consts.FLOW_STATE_COMPLETED:
            duration = self.finished - self.created
        else:
            duration = datetime.datetime.utcnow() - self.created

        trigger = None
        if self.trigger_data:
            trigger = self.trigger_data

        return dict(id=self.id,
                    label=self.get_label(),
                    created=self.created.strftime("%Y-%m-%dT%H:%M:%SZ") if self.created else None,
                    finished=self.finished.strftime("%Y-%m-%dT%H:%M:%SZ") if self.finished else None,
                    deleted=self.deleted.strftime("%Y-%m-%dT%H:%M:%SZ") if self.deleted else None,
                    state=consts.FLOW_STATES_NAME[self.state],
                    kind='ci' if self.kind == 0 else 'dev',
                    duration=duration_to_txt(duration),
                    branch_id=self.branch_id,
                    base_branch_name=self.branch.name,
                    branch_name=self.branch_name,
                    project_id=self.branch.project_id,
                    project_name=self.branch.project.name,
                    args=self.args,
                    stages=[s.get_json() for s in self.branch.stages if s.deleted is None],
                    runs=[r.get_json() for r in self.runs],
                    trigger=trigger,
                    artifacts=self.artifacts)


class Run(db.Model, DatesMixin):
    __tablename__ = "runs"
    id = Column(Integer, primary_key=True)
    label = Column(Unicode(200))
    started = Column(DateTime)    # time when the session got a first non-deleted job
    finished = Column(DateTime)    # time when all tasks finished first time
    finished_again = Column(DateTime)    # time when all tasks finished
    state = Column(Integer, default=consts.RUN_STATE_IN_PROGRESS)
    email_sent = Column(DateTime)
    note = Column(UnicodeText)
    stage_id = Column(Integer, ForeignKey('stages.id'), nullable=False)
    stage = relationship('Stage', back_populates="runs")
    flow_id = Column(Integer, ForeignKey('flows.id'), nullable=False)
    flow = relationship('Flow', back_populates="runs")
    jobs = relationship('Job', back_populates="run")
    artifacts = Column(JSONB, default={})
    artifacts_files = relationship('Artifact', back_populates="run")
    hard_timeout_reached = Column(DateTime)
    soft_timeout_reached = Column(DateTime)
    args = Column(JSONB, nullable=False, default={})
    # stats - result changes
    new_cnt = Column(Integer, default=0)
    no_change_cnt = Column(Integer, default=0)
    regr_cnt = Column(Integer, default=0)
    fix_cnt = Column(Integer, default=0)
    tests_total = Column(Integer, default=0)
    tests_passed = Column(Integer, default=0)
    tests_not_run = Column(Integer, default=0)
    jobs_error = Column(Integer, default=0)
    jobs_total = Column(Integer, default=0)
    issues_total = Column(Integer, default=0)
    issues_new = Column(Integer, default=0)
    repo_data = Column(JSONB)
    reason = Column(JSONB, nullable=False)

    def get_json(self):
        jobs_processing = 0
        jobs_executing = 0
        jobs_waiting = 0
        jobs_error = 0
        jobs_total = 0

        if self.state == consts.RUN_STATE_PROCESSED:
            jobs_total = self.jobs_total
            jobs_error = self.jobs_error
            if self.finished is None:
                log.error('PROBLEM WITH NONE TIMESTAMP in run %s', self)
                duration = datetime.datetime.utcnow() - self.created
            else:
                duration = self.finished - self.created
        else:
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
                duration = datetime.datetime.utcnow() - self.created

        data = dict(id=self.id,
                    label=self.label,
                    created=self.created.strftime("%Y-%m-%dT%H:%M:%SZ") if self.created else None,
                    deleted=self.deleted.strftime("%Y-%m-%dT%H:%M:%SZ") if self.deleted else None,
                    started=self.started.strftime("%Y-%m-%dT%H:%M:%SZ") if self.started else None,
                    finished=self.finished.strftime("%Y-%m-%dT%H:%M:%SZ") if self.finished else None,
                    duration=duration_to_txt(duration),
                    state=consts.RUN_STATES_NAME[self.state],
                    stage_name=self.stage.name,
                    stage_id=self.stage_id,
                    flow_id=self.flow_id,
                    flow_kind='ci' if self.flow.kind == 0 else 'dev',
                    branch_id=self.flow.branch_id,
                    branch_name=self.flow.branch.name,
                    project_id=self.flow.branch.project_id,
                    project_name=self.flow.branch.project.name,
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
                    artifacts_total=len(self.artifacts_files),
                    new_cnt=self.new_cnt,
                    no_change_cnt=self.no_change_cnt,
                    regr_cnt=self.regr_cnt,
                    fix_cnt=self.fix_cnt,
                    repo_data=self.repo_data,
                    reason=self.reason['reason'])

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
    # services

    def get_json(self):
        data = dict(id=self.id,
                    index=self.index,
                    tool=self.tool.name,
                    tool_id=self.tool_id,
                    job_id=self.job_id,
                    status=self.status,
                    result=self.result)
        for f, v in self.fields.items():
            data[f] = v
        return data


class Job(db.Model, DatesMixin):
    __tablename__ = "jobs"
    id = Column(Integer, primary_key=True)
    name = Column(Unicode(200))
    assigned = Column(DateTime)
    started = Column(DateTime)
    finished = Column(DateTime)
    processing_started = Column(DateTime)  # TODO: this is never used
    completed = Column(DateTime)
    run_id = Column(Integer, ForeignKey('runs.id'), nullable=False)
    run = relationship("Run", back_populates="jobs")
    steps = relationship("Step", back_populates="job", order_by="Step.index")
    state = Column(Integer, default=consts.JOB_STATE_QUEUED)
    completion_status = Column(Integer)
    timeout = Column(Integer)
    covered = Column(Boolean, default=False)
    notes = Column(Unicode(2048))
    system_id = Column(Integer, ForeignKey('systems.id'), nullable=False)
    system = relationship('System', back_populates="jobs")
    agent = relationship('Agent', uselist=False, back_populates="job",
                            foreign_keys="Agent.job_id", post_update=True)
    agents_group_id = Column(Integer, ForeignKey('agents_groups.id'), nullable=False)
    agents_group = relationship('AgentsGroup', back_populates="jobs")
    agent_used_id = Column(Integer, ForeignKey('agents.id'))
    agent_used = relationship('Agent', foreign_keys=[agent_used_id], post_update=True)
    results = relationship('TestCaseResult', back_populates="job")
    issues = relationship('Issue', back_populates="job")

    def get_json(self):
        if self.started:
            if self.finished:
                duration = self.finished - self.started
            else:
                duration = datetime.datetime.utcnow() - self.started
            duration = duration_to_txt(duration)
        else:
            duration = ''

        return dict(id=self.id,
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
                    agent_name=self.agent_used.name if self.agent_used else '',
                    steps=[s.get_json() for s in sorted(self.steps, key=lambda s: s.index)])

    def __repr__(self):
        txt = 'Job %s, state:%s' % (self.id, consts.JOB_STATES_NAME[self.state])
        txt += ', g:%s' % self.agents_group_id
        if self.agent_used_id:
            txt += ', ag:%s' % self.agent_used_id
        return "<%s>" % txt


class TestCase(db.Model, DatesMixin):
    __tablename__ = "test_cases"
    id = Column(Integer, primary_key=True)
    name = Column(Unicode(255), unique=True)
    tool_id = Column(Integer, ForeignKey('tools.id'), nullable=False)
    tool = relationship('Tool', back_populates="test_cases")
    results = relationship("TestCaseResult", back_populates="test_case")


class TestCaseResult(db.Model):
    __tablename__ = "test_case_results"
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

    def __repr__(self):
        txt = 'TCR %s, result:%s' % (self.id, consts.TC_RESULTS_NAME[self.result])
        return "<%s>" % txt

    def get_json(self, with_extra=False):
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
                    agent_name=self.job.agent_used.name if self.job.agent_used else '',
                    agent_id=self.job.agent_used_id if self.job.agent_used else 0)

        if with_extra:
            data['project_id'] = self.job.run.flow.branch.project_id
            data['project_name'] = self.job.run.flow.branch.project.name
            data['branch_id'] = self.job.run.flow.branch_id
            data['branch_name'] = self.job.run.flow.branch.name
            data['flow_id'] = self.job.run.flow_id
            data['flow_kind'] = 'ci' if self.job.run.flow.kind == 0 else 'dev'
            data['run_id'] = self.job.run_id
            data['stage_id'] = self.job.run.stage_id
            data['stage_name'] = self.job.run.stage.name

        return data


class Issue(db.Model):
    __tablename__ = "issues"
    id = Column(Integer, primary_key=True)
    issue_type = Column(Integer, default=consts.ISSUE_TYPE_ERROR)
    line = Column(Integer)
    column = Column(Integer)
    path = Column(Unicode(512))
    symbol = Column(Unicode(64))
    message = Column(Unicode(512))
    extra = Column(JSONB)
    age = Column(Integer, default=0)
    job_id = Column(Integer, ForeignKey('jobs.id'), nullable=False)
    job = relationship('Job', back_populates="issues")

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
    path = Column(Unicode(512))
    artifacts = relationship('Artifact', back_populates="file")


class Artifact(db.Model):
    __tablename__ = "artifacts"
    id = Column(Integer, primary_key=True)
    file_id = Column(Integer, ForeignKey('files.id'), nullable=False)
    file = relationship('File', back_populates="artifacts")
    flow_id = Column(Integer, ForeignKey('flows.id'), nullable=False)
    flow = relationship('Flow', back_populates="artifacts_files")
    run_id = Column(Integer, ForeignKey('runs.id'), nullable=False)
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
    name = Column(Unicode(150), unique=True)
    executor = Column(Unicode(20), unique=True)
    jobs = relationship('Job', back_populates="system")
    UniqueConstraint('name', 'executor', name='uq_system_name_executor')


class Tool(db.Model, DatesMixin):
    __tablename__ = "tools"
    id = Column(Integer, primary_key=True)
    name = Column(Unicode(50))
    description = Column(Unicode(200))
    configuration = Column(Text)
    steps = relationship("Step", back_populates="tool")
    fields = Column(JSONB, nullable=False)
    # TODO should it have optional reference to project so that there are local and global tools?
    test_cases = relationship("TestCase", back_populates="tool")


class AgentAssignment(db.Model):
    __tablename__ = "agent_assignments"
    agent_id = Column(Integer, ForeignKey('agents.id'), primary_key=True)
    agent = relationship('Agent', back_populates="agents_groups")
    agents_group_id = Column(Integer, ForeignKey('agents_groups.id'), primary_key=True)
    agents_group = relationship('AgentsGroup', back_populates="agents")


class AgentsGroup(db.Model, DatesMixin):
    __tablename__ = "agents_groups"
    id = Column(Integer, primary_key=True)
    name = Column(Unicode(50))
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=True)
    project = relationship('Project', back_populates="agents_groups")
    # agents = relationship("Agent", back_populates="agents_group")  # static assignments
    agents = relationship('AgentAssignment', back_populates="agents_group")
    jobs = relationship("Job", back_populates="agents_group")

    def get_json(self):
        return dict(id=self.id,
                    created=self.created.strftime("%Y-%m-%dT%H:%M:%SZ") if self.created else None,
                    deleted=self.deleted.strftime("%Y-%m-%dT%H:%M:%SZ") if self.deleted else None,
                    name=self.name,
                    project_id=self.project_id,
                    project_name=self.project.name if self.project else None,
                    agents_count=len(self.agents))


class Agent(db.Model, DatesMixin):
    __tablename__ = "agents"
    id = Column(Integer, primary_key=True)
    name = Column(Unicode(50), nullable=False)
    address = Column(Unicode(25), index=True, nullable=False)
    authorized = Column(Boolean, default=False)
    ip_address = Column(Unicode(50))
    state = Column(Integer, default=0)
    disabled = Column(Boolean, default=False)
    comment = Column(Text)
    status_line = Column(Text)
    last_seen = Column(DateTime)
    host_info = Column(JSONB)
    user_attrs = Column(JSONB)
    agents_groups = relationship('AgentAssignment', back_populates="agent")
    job_id = Column(Integer, ForeignKey('jobs.id'))
    job = relationship('Job', back_populates="agent", foreign_keys=[job_id])

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
                    groups=[dict(id=a.agents_group.id, name=a.agents_group.name) for a in self.agents_groups],
                    job=self.job.get_json() if self.job else None)


class Setting(db.Model):
    __tablename__ = "settings"
    id = Column(Integer, primary_key=True)
    group = Column(Unicode(50))
    name = Column(Unicode(50))
    value = Column(Text)
    val_type = Column(String(8))  # integer, text, boolean, password

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

    return s.value


class User(db.Model, DatesMixin):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(Unicode(50))
    password = Column(Unicode(150))
    sessions = relationship("UserSession", back_populates="user")

    def get_json(self):
        return dict(id=self.id,
                    user=self.name)


class UserSession(db.Model, DatesMixin):
    __tablename__ = "user_sessions"
    id = Column(Integer, primary_key=True)
    token = Column(Unicode(32))
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    user = relationship('User', back_populates="sessions")

    def get_json(self):
        return dict(id=self.id,
                    token=self.token,
                    user=self.user.get_json())
