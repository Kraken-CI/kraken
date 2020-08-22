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
from sqlalchemy import event
from sqlalchemy.orm import relationship, mapper
from sqlalchemy.dialects.postgresql import JSONB

from . import consts
from .schema import execute_schema_code

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
    executor_groups = relationship("ExecutorGroup", back_populates="project")
    webhooks = Column(JSONB)

    def get_json(self):
        return dict(id=self.id,
                    created=self.created.strftime("%Y-%m-%dT%H:%M:%SZ") if self.created else None,
                    deleted=self.deleted.strftime("%Y-%m-%dT%H:%M:%SZ") if self.deleted else None,
                    name=self.name,
                    description=self.description,
                    branches=[b.get_json(with_results=True) for b in self.branches],
                    secrets=[s.get_json() for s in self.secrets if s.deleted is None],
                    webhooks=self.webhooks if self.webhooks else {})


class Branch(db.Model, DatesMixin):
    __tablename__ = "branches"
    id = Column(Integer, primary_key=True)
    name = Column(Unicode(255))
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)
    project = relationship('Project', back_populates="branches")
    branch_name = Column(Unicode(255))
    ci_flows = relationship("Flow", order_by="desc(Flow.created)",
                            primaryjoin="and_(Branch.id==Flow.branch_id, Flow.kind==0)", viewonly=True)
    dev_flows = relationship("Flow", order_by="desc(Flow.created)",
                             primaryjoin="and_(Branch.id==Flow.branch_id, Flow.kind==1)", viewonly=True)
    stages = relationship("Stage", back_populates="branch", lazy="dynamic", order_by="Stage.name")

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
            data['stages'] = [s.get_json() for s in self.stages.filter_by(deleted=None)]
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
    schema_file = Column(UnicodeText)
    triggers = Column(JSONB)
    timeouts = Column(JSONB)
    runs = relationship('Run', back_populates="stage")
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
#     #executor_group
#     config_id = Column(Integer, ForeignKey('configs.id'), nullable=False)
#     config = relationship("Config", back_populates="environments")
#     job_plan_id = Column(Integer, ForeignKey('job_plans.id'), nullable=False)
#     job_plan = relationship("JobPlan", back_populates="environments")

# EXECUTION


class Flow(db.Model, DatesMixin):
    __tablename__ = "flows"
    id = Column(Integer, primary_key=True)
    finished = Column(DateTime)
    state = Column(Integer, default=consts.FLOW_STATE_IN_PROGRESS)
    kind = Column(Integer, default=0)  # 0 - CI, 1 - dev
    branch_name = Column(Unicode(255))
    branch_id = Column(Integer, ForeignKey('branches.id'), nullable=False)
    branch = relationship('Branch')
    runs = relationship('Run', back_populates="flow", order_by="Run.created")
    args = Column(JSONB, nullable=False, default={})
    trigger_data = Column(JSONB)
    artifacts = Column(JSONB, default={})
    artifacts_files = relationship('Artifact', back_populates="flow")

    def get_json(self):
        if self.state == consts.FLOW_STATE_COMPLETED:
            duration = self.finished - self.created
        else:
            duration = datetime.datetime.utcnow() - self.created

        return dict(id=self.id,
                    created=self.created.strftime("%Y-%m-%dT%H:%M:%SZ") if self.created else None,
                    finished=self.finished.strftime("%Y-%m-%dT%H:%M:%SZ") if self.finished else None,
                    deleted=self.deleted.strftime("%Y-%m-%dT%H:%M:%SZ") if self.deleted else None,
                    name=self.id,
                    state=consts.FLOW_STATES_NAME[self.state],
                    kind='ci' if self.kind == 0 else 'dev',
                    duration=duration_to_txt(duration),
                    branch_id=self.branch_id,
                    base_branch_name=self.branch.name,
                    branch_name=self.branch_name,
                    project_id=self.branch.project_id,
                    project_name=self.branch.project.name,
                    args=self.args,
                    stages=[s.get_json() for s in self.branch.stages.filter_by(deleted=None)],
                    runs=[r.get_json() for r in self.runs],
                    artifacts=self.artifacts)


class Run(db.Model, DatesMixin):
    __tablename__ = "runs"
    id = Column(Integer, primary_key=True)
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

    def get_json(self):
        jobs_processing = 0
        jobs_executing = 0
        jobs_waiting = 0
        jobs_error = 0
        jobs_total = 0

        if self.state == consts.RUN_STATE_COMPLETED:
            jobs_total = self.jobs_total
            jobs_error = self.jobs_error
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
                    created=self.created.strftime("%Y-%m-%dT%H:%M:%SZ") if self.created else None,
                    deleted=self.deleted.strftime("%Y-%m-%dT%H:%M:%SZ") if self.deleted else None,
                    started=self.started.strftime("%Y-%m-%dT%H:%M:%SZ") if self.started else None,
                    finished=self.finished.strftime("%Y-%m-%dT%H:%M:%SZ") if self.finished else None,
                    name=self.stage.name,
                    state=consts.RUN_STATES_NAME[self.state],
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
                    new_cnt=self.new_cnt,
                    no_change_cnt=self.no_change_cnt,
                    regr_cnt=self.regr_cnt,
                    fix_cnt=self.fix_cnt,
                    duration=duration_to_txt(duration))

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
    processing_started = Column(DateTime)
    completed = Column(DateTime)
    run_id = Column(Integer, ForeignKey('runs.id'), nullable=False)
    run = relationship("Run", back_populates="jobs")
    steps = relationship("Step", back_populates="job", order_by="Step.index")
    state = Column(Integer, default=consts.JOB_STATE_QUEUED)
    completion_status = Column(Integer)
    timeout = Column(Integer)
    covered = Column(Boolean, default=False)
    notes = Column(Unicode(2048))
    system = Column(Unicode(200))
    executor = relationship('Executor', uselist=False, back_populates="job",
                            foreign_keys="Executor.job_id", post_update=True)
    executor_group_id = Column(Integer, ForeignKey('executor_groups.id'), nullable=False)
    executor_group = relationship('ExecutorGroup', back_populates="jobs")
    executor_used_id = Column(Integer, ForeignKey('executors.id'))
    executor_used = relationship('Executor', foreign_keys=[executor_used_id], post_update=True)
    results = relationship('TestCaseResult', back_populates="job")
    issues = relationship('Issue', back_populates="job")

    def get_json(self):
        return dict(id=self.id,
                    created=self.created.strftime("%Y-%m-%dT%H:%M:%SZ") if self.created else None,
                    deleted=self.deleted.strftime("%Y-%m-%dT%H:%M:%SZ") if self.deleted else None,
                    started=self.started.strftime("%Y-%m-%dT%H:%M:%SZ") if self.started else None,
                    finished=self.finished.strftime("%Y-%m-%dT%H:%M:%SZ") if self.finished else None,
                    completed=self.completed.strftime("%Y-%m-%dT%H:%M:%SZ") if self.completed else None,
                    processing_started=self.processing_started.strftime(
                        "%Y-%m-%dT%H:%M:%SZ") if self.processing_started else None,
                    name=self.name,
                    state=self.state,
                    completion_status=self.completion_status,
                    timeout=self.timeout,
                    covered=self.covered,
                    notes=self.notes,
                    system=self.system,
                    run_id=self.run_id,
                    executor_group_id=self.executor_group_id,
                    executor_group_name=self.executor_group.name,
                    executor_id=self.executor_used_id if self.executor_used else 0,
                    executor_name=self.executor_used.name if self.executor_used else '',
                    steps=[s.get_json() for s in sorted(self.steps, key=lambda s: s.index)])

    def __repr__(self):
        txt = 'Job %s, state:%s' % (self.id, consts.JOB_STATES_NAME[self.state])
        txt += ', g:%s' % self.executor_group_id
        if self.executor_used_id:
            txt += ', ex:%s' % self.executor_used_id
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
                    job_id=self.job_id,
                    job_name=self.job.name,
                    executor_group_name=self.job.executor_group.name,
                    executor_group_id=self.job.executor_group_id,
                    executor_name=self.job.executor_used.name if self.job.executor_used else '',
                    executor_id=self.job.executor_used_id if self.job.executor_used else 0)

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
                    executor_group_name=self.job.executor_group.name,
                    executor_group_id=self.job.executor_group_id,
                    executor_name=self.job.executor_used.name,
                    executor_id=self.job.executor_used_id)
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


# RESOURCES

# class System(db.Model):
#     __tablename__ = "systems"
#     id = Column(Integer, primary_key=True)
#     name = Column(Unicode(150))


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


class ExecutorAssignment(db.Model):
    __tablename__ = "executor_assignments"
    executor_id = Column(Integer, ForeignKey('executors.id'), primary_key=True)
    executor = relationship('Executor', back_populates="executor_groups")
    executor_group_id = Column(Integer, ForeignKey('executor_groups.id'), primary_key=True)
    executor_group = relationship('ExecutorGroup', back_populates="executors")


class ExecutorGroup(db.Model, DatesMixin):
    __tablename__ = "executor_groups"
    id = Column(Integer, primary_key=True)
    name = Column(Unicode(50))
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=True)
    project = relationship('Project', back_populates="executor_groups")
    # executors = relationship("Executor", back_populates="executor_group")  # static assignments
    executors = relationship('ExecutorAssignment', back_populates="executor_group")
    jobs = relationship("Job", back_populates="executor_group")

    def get_json(self):
        return dict(id=self.id,
                    created=self.created.strftime("%Y-%m-%dT%H:%M:%SZ") if self.created else None,
                    deleted=self.deleted.strftime("%Y-%m-%dT%H:%M:%SZ") if self.deleted else None,
                    name=self.name,
                    project_id=self.project_id,
                    project_name=self.project.name if self.project else None,
                    executors_count=len(self.executors))


class Executor(db.Model, DatesMixin):
    __tablename__ = "executors"
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
    # executor_group_id = Column(Integer, ForeignKey('executor_groups.id'))  # static assignment to exactly one machines group, if NULL then not authorized
    executor_groups = relationship('ExecutorAssignment', back_populates="executor")
    job_id = Column(Integer, ForeignKey('jobs.id'))
    job = relationship('Job', back_populates="executor", foreign_keys=[job_id])

    def __repr__(self):
        return "<Executor %s, job:%s>" % (self.id, self.job_id)

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
                    groups=[dict(id=a.executor_group.id, name=a.executor_group.name) for a in self.executor_groups],
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


INITIAL_SETTINGS = {
    'general': {
        'server_url': ''
    },
    'notification': {
        'smtp_server': '',
        'smtp_tls': False,
        'smtp_from': '',
        'smtp_user': '',
        'smtp_password': None,  # password
        'slack_token': None  # password
    }
}


def _prepare_initial_preferences():
    for group_name, group_fields in INITIAL_SETTINGS.items():
        for name, val in group_fields.items():
            s = Setting.query.filter_by(group=group_name, name=name).one_or_none()
            if s is not None:
                # correct type if necessary
                if isinstance(val, bool):
                    s.val_type = 'boolean'
                elif isinstance(val, int):
                    s.val_type = 'integer'
                elif val is None:
                    s.val_type = 'password'
                else:
                    s.val_type = 'text'
                continue

            # set value and type
            if isinstance(val, bool):
                val_type = 'boolean'
                val = str(val)
            elif isinstance(val, int):
                val_type = 'integer'
                val = str(val)
            elif val is None:
                val_type = 'password'
                val = ''
            else:
                val_type = 'text'
            Setting(group=group_name, name=name, value=val, val_type=val_type)
    db.session.commit()


def prepare_initial_data():
    log.info("Preparing initial DB data")

    tool_fields = {
        'git': {'checkout': 'text', 'branch': 'text', 'destination': 'text'},
        'shell': {'cmd': 'text'},
        'pytest': {'params': 'text', 'directory': 'text'},
        'rndtest': {'count': 'text'},
        'artifacts': {'type': 'choice:file', 'upload': 'text'},
        'pylint': {'rcfile': 'text', 'modules_or_packages': 'text'},
        'cloc': {'not-match-f': 'text', 'exclude-dir': 'text'},
        'nglint': {},
    }
    tools = {}
    for name, fields in tool_fields.items():
        tool = Tool.query.filter_by(name=name).one_or_none()
        if tool is None:
            tool = Tool(name=name, description="This is a %s tool." % name, fields=fields)
            db.session.commit()
            log.info("   created Tool record '%s'", name)
        tools[name] = tool

    executor = Executor.query.filter_by(name="agent.7").one_or_none()
    if executor is None:
        executor = Executor(name='agent.7', address="agent.7", authorized=False)
        db.session.commit()
        log.info("   created Executor record 'agent.7'")
    else:
        executor.authorized = False
        db.session.commit()
        log.info("   Executor 'agent.7' unauthorized")

    executor_group = ExecutorGroup.query.filter_by(name="all").one_or_none()
    if executor_group is None:
        executor_group = ExecutorGroup(name='all')
        db.session.commit()
        log.info("   created ExecutorGroup record 'all'")

        # ExecutorAssignment(executor=executor, executor_group=executor_group)
        # db.session.commit()
        # log.info("   created ExecutorAssignment for record 'all'")

    # Project DEMO
    project = Project.query.filter_by(name="Demo").one_or_none()
    if project is None:
        project = Project(name='Demo', description="This is a demo project.")
        db.session.commit()
        log.info("   created Project record 'Demo'")

    branch = Branch.query.filter_by(name="Master", project=project).one_or_none()
    if branch is None:
        branch = Branch(name='Master', branch_name='master', project=project)
        db.session.commit()
        log.info("   created Branch record 'master'")

    stage = Stage.query.filter_by(name="System Tests", branch=branch).one_or_none()
    if stage is None:
        # schema = {
        #     "configs": [{
        #         "name": "c1",
        #         "p1": "1",
        #         "p2": "3"
        #     }, {
        #         "name": "c2",
        #         "n3": "33",
        #         "t2": "asdf"
        #     }],
        #     "jobs": [{
        #         "name": "make dist",
        #         "steps": [{
        #             "tool": "git",
        #             "checkout": "git@gitlab.isc.org:isc-projects/kea.git",
        #             "branch": "master"
        #         }, {
        #             "tool": "shell",
        #             "cmd": "make dist",
        #             "cwd": "kea"
        #         }, {
        #             "tool": "artifacts",
        #             "type": "file",
        #             "upload": "aaa-{ver}.tar.gz"
        #         }],
        #         "environments": [{
        #             "system": "ubuntu-18.04",
        #             "executor_group": "server",
        #             "config": "c1"
        #         }]
        #     }],
        #     "notification": {
        #         "changes": {
        #             "slack": {"channel": "abc"},
        #             "email": "godfryd@abc.pl"
        #         }
        #     }
        # }
        #
        # TRIGGER:
        # kind: parent | interval | date | cron | repository | webhook
        # interval: duration e.g. '1d' or '3h 30m'
        # cron: cron rule e.g. '* * 10 * *'
        # repository: url with branch
        # webhook: from GitHub or GitLab or Bitbucket
        schema_code = '''def stage(ctx):
    return {
        "parent": "Unit Tests",
        "triggers": {
            "parent": True,
            "cron": "1 * * * *",
            "interval": "10m",
            "repository": True,
            "webhook": True
        },
        "parameters": [],
        "configs": [{
            "name": "c1",
            "p1": "1",
            "p2": "3"
        }, {
            "name": "c2",
            "n3": "33",
            "t2": "asdf"
        }],
        "jobs": [{
            "name": "make dist",
            "steps": [{
                "tool": "git",
                "checkout": "https://github.com/frankhjung/python-helloworld.git",
                "branch": "master"
            }, {
                "tool": "pytest",
                "params": "tests/testhelloworld.py",
                "cwd": "python-helloworld"
            }],
            "environments": [{
                "system": "ubuntu-18.04",
                "executor_group": "all",
                "config": "c1"
            }]
        }]
    }'''
        stage = Stage(name='System Tests', description="This is a stage of system tests.", branch=branch,
                      schema_code=schema_code, schema=execute_schema_code(branch, schema_code))
        db.session.commit()
        log.info("   created Stage record 'System Tests'")

    stage = Stage.query.filter_by(name="Unit Tests", branch=branch).one_or_none()
    if stage is None:
        schema_code = '''def stage(ctx):
    return {
        "parent": "root",
        "triggers": {
            "parent": True
        },
        "parameters": [{
            "name": "COUNT",
            "type": "string",
            "default": "10",
            "description": "Number of tests to generate"
        }],
        "jobs": [{
            "name": "random tests",
            "steps": [{
                "tool": "rndtest",
                "count": "#{COUNT}"
            }],
            "environments": [{
                "system": "centos-7",
                "executor_group": "all",
                "config": "default"
            }]
        }]
    }'''
        stage = Stage(name='Unit Tests', description="This is a stage of unit tests.", branch=branch,
                      schema_code=schema_code, schema=execute_schema_code(branch, schema_code))
        db.session.commit()
        log.info("   created Stage record 'Unit Tests'")

    # Project KRAKEN
    project = Project.query.filter_by(name="Kraken").one_or_none()
    if project is None:
        project = Project(name='Kraken', description="This is a Kraken project.")
        db.session.commit()
        log.info("   created Project record 'Kraken'")

    branch = Branch.query.filter_by(name="Master", project=project).one_or_none()
    if branch is None:
        branch = Branch(name='Master', branch_name='master', project=project)
        db.session.commit()
        log.info("   created Branch record 'master'")

    stage = Stage.query.filter_by(name="Static Analysis", branch=branch).one_or_none()
    if stage is None:
        # TODO: pylint
        # }, {
        #     "tool": "pylint",
        #     "rcfile": "../pylint.rc",
        #     "modules_or_packages": "kraken.agent",
        #     "cwd": "kraken/agent"
        schema_code = '''def stage(ctx):
    return {
        "parent": "root",
        "triggers": {
            "parent": True
        },
        "parameters": [],
        "configs": [],
        "jobs": [{
            "name": "pylint",
            "steps": [{
                "tool": "git",
                "checkout": "git@github.com:godfryd/kraken.git",
                "branch": "master"
            }, {
                "tool": "pylint",
                "rcfile": "pylint.rc",
                "modules_or_packages": "agent/kraken/agent",
                "cwd": "kraken"
            }],
            "environments": [{
                "system": "ubuntu-18.04",
                "executor_group": "all",
                "config": "c1"
            }]
        }]
    }'''
        stage = Stage(name='Static Analysis', description="This is a stage of Static Analysis.", branch=branch,
                      schema_code=schema_code, schema=execute_schema_code(branch, schema_code))
        db.session.commit()
        log.info("   created Stage record 'System Tests'")

    stage = Stage.query.filter_by(name="Unit Tests", branch=branch).one_or_none()
    if stage is None:
        schema_code = '''def stage(ctx):
    return {
        "parent": "root",
        "triggers": {
            "parent": True
        },
        "parameters": [],
        "configs": [],
        "jobs": [{
            "name": "pytest",
            "steps": [{
                "tool": "git",
                "checkout": "git@github.com:godfryd/kraken.git",
                "branch": "master"
            }, {
                "tool": "pytest",
                "params": "-vv",
                "cwd": "kraken/agent"
            }],
            "environments": [{
                "system": "centos-7",
                "executor_group": "all",
                "config": "default"
            }]
        }]
    }'''
        stage = Stage(name='Unit Tests', description="This is a stage of unit tests.", branch=branch,
                      schema_code=schema_code, schema=execute_schema_code(branch, schema_code))
        db.session.commit()
        log.info("   created Stage record 'Unit Tests'")

    _prepare_initial_preferences()
