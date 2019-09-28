import json
import datetime
import logging

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Boolean, DateTime, ForeignKey, Index, Integer, Sequence, String, Text, Unicode, UnicodeText
from sqlalchemy import event
from sqlalchemy.types import TypeDecorator
from sqlalchemy.orm import relationship, mapper
from sqlalchemy.dialects.postgresql import JSONB, ARRAY

import consts

log = logging.getLogger(__name__)

db = SQLAlchemy()


@event.listens_for(mapper, 'init')
def auto_add(target, args, kwargs):
    db.session.add(target)


class DatesMixin():
    created = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)
    updated = Column(DateTime, nullable=False, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    deleted = Column(DateTime)


class Project(db.Model, DatesMixin):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True)
    name = Column(Unicode(50))
    description = Column(Unicode(200))
    branches = relationship("Branch", back_populates="project")
    executor_groups = relationship("ExecutorGroup", back_populates="project")


class Branch(db.Model, DatesMixin):
    __tablename__ = "branches"
    id = Column(Integer, primary_key=True)
    name = Column(Unicode(255))
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)
    project = relationship('Project', back_populates="branches")
    stages = relationship("Stage", back_populates="branch")


# PLANNING

class Stage(db.Model, DatesMixin):
    __tablename__ = "stages"
    id = Column(Integer, primary_key=True)
    name = Column(Unicode(50))
    description = Column(Unicode(1024))
    branch_id = Column(Integer, ForeignKey('branches.id'), nullable=False)
    branch = relationship('Branch', back_populates="stages")
    schema = Column(JSONB, nullable=False)
    runs = relationship('Run', back_populates="stage")
    #services

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

class Run(db.Model, DatesMixin):
    __tablename__ = "runs"
    id = Column(Integer, primary_key=True)
    started = Column(DateTime)    # time when the session got a first non-deleted job
    finished = Column(DateTime)    # time when all tasks finished first time
    finished_again = Column(DateTime)    # time when all tasks finished
    email_sent = Column(DateTime)
    note = Column(UnicodeText)
    stage_id = Column(Integer, ForeignKey('stages.id'), nullable=False)
    stage = relationship('Stage', back_populates="runs")
    jobs = relationship('Job', back_populates="run")
    hard_timeout_reached = Column(DateTime)
    soft_timeout_reached = Column(DateTime)

    def get_json(self):
        return dict(id=self.id,
                    created=str(self.created) if self.created else None,
                    deleted=str(self.deleted) if self.deleted else None,
                    started=str(self.started) if self.started else None,
                    finished=str(self.finished) if self.finished else None,
                    stage_id=self.stage_id,
                    jobs_id=[j.id for j in self.jobs])


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
    #services

    def get_json(self):
        data = dict(id=self.id,
                    index=self.index,
                    tool=self.tool.name,
                    tool_id=self.tool_id,
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
    run_id = Column(Integer, ForeignKey('runs.id'), nullable=False)
    run = relationship("Run", back_populates="jobs")
    steps = relationship("Step", back_populates="job", order_by="Step.index")
    state = Column(Integer, default=consts.JOB_STATE_QUEUED)
    completion_status = Column(Integer)
    notes = Column(Unicode(2048))
    executor = relationship('Executor', uselist=False, back_populates="job", foreign_keys="Executor.job_id", post_update=True)
    executor_group_id = Column(Integer, ForeignKey('executor_groups.id'), nullable=False)
    executor_group = relationship('ExecutorGroup', back_populates="jobs")
    executor_used_id = Column(Integer, ForeignKey('executors.id'))
    executor_used = relationship('Executor', foreign_keys=[executor_used_id], post_update=True)
    results = relationship('TestCaseResult', back_populates="job")

    def get_json(self):
        return dict(id=self.id,
                    created=str(self.created) if self.created else None,
                    deleted=str(self.deleted) if self.deleted else None,
                    state=self.state,
                    run_id=self.run_id,
                    steps=[s.get_json() for s in sorted(self.steps, key=lambda s: s.index)])

    def __repr__(self):
        txt = 'Job %s, state:%s' % (self.id, consts.JOB_STATES_NAME[self.state])
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
    cmd_line = Column(UnicodeText)


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


class ExecutorGroup(db.Model, DatesMixin):
    __tablename__ = "executor_groups"
    id = Column(Integer, primary_key=True)
    name = Column(Unicode(50))
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)
    project = relationship('Project', back_populates="executor_groups")
    executors = relationship("Executor", back_populates="executor_group")  # static assignments
    jobs = relationship("Job", back_populates="executor_group")


class Executor(db.Model, DatesMixin):
    __tablename__ = "executors"
    id = Column(Integer, primary_key=True)
    name = Column(Unicode(50), nullable=False)
    address = Column(Unicode(25), index=True, nullable=False)
    ip_address = Column(Unicode(50))
    state = Column(Integer, default=0)
    disabled = Column(Boolean, default=False)
    comment = Column(Text)
    status_line = Column(Text)
    executor_group_id = Column(Integer, ForeignKey('executor_groups.id'))  # static assignment to exactly one machines group, if NULL then not authorized
    executor_group = relationship('ExecutorGroup', back_populates="executors")
    job_id = Column(Integer, ForeignKey('jobs.id'))
    job = relationship('Job', back_populates="executor", foreign_keys=[job_id])

    def __repr__(self):
        return "<Executor %s, job:%s>" % (self.id, self.job_id)


class Preference(db.Model):
    __tablename__ = "preferences"
    id = Column(Integer, primary_key=True)
    name = Column(Unicode(50))
    value = Column(Text)
    val_type = Column(String(8))  # integer, text, boolean, password

    def get_json(self):
        if self.val_type == "integer":
            val = long(self.value)
        elif self.val_type == "boolean":
            val = (self.value == 'True')
        else:
            val = self.value

        return {
            "id": self.id,
            "name": self.name,
            "value": val,
            "type": self.val_type}

    def set_value(self, value):
        if self.val_type == "integer":
            self.value = str(value)
        elif self.val_type == "boolean":
            self.value = str(value)
        else:
            self.value = value


INITIAL_PREFERENCES = {
    "smtp_server": ""
}

def _prepare_initial_preferences():
    for name, val in INITIAL_PREFERENCES.items():
        p = Preference.query.filter_by(name=name).one_or_none()
        if p is not None:
            continue
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
        Preference(name=name, value=val, val_type=val_type)
    db.session.commit()


def prepare_initial_data():
    log.info("Preparing initial DB data")

    tool_fields = {
        'git': {'checkout': 'text', 'branch': 'text'},
        'shell': {'cmd': 'text'},
        'pytest': {'params': 'text', 'directory': 'text'},
        'artifacts': {'type': 'choice:file', 'upload': 'text'}
    }
    tools = {}
    for name, fields in tool_fields.items():
        tool = Tool.query.filter_by(name=name).one_or_none()
        if tool is None:
            tool = Tool(name=name, description="This is a %s tool." % name, fields=fields)
            db.session.commit()
            log.info("   created Tool record '%s'", name)
        tools[name] = tool

    project = Project.query.filter_by(name="demo").one_or_none()
    if project is None:
        project = Project(name='demo', description="This is a demo project.")
        db.session.commit()
        log.info("   created Project record 'demo'")

    branch = Branch.query.filter_by(name="master", project=project).one_or_none()
    if branch is None:
        branch = Branch(name='master', project=project)
        db.session.commit()
        log.info("   created Branch record 'master'")

    stage = Stage.query.filter_by(name="hello-world", branch=branch).one_or_none()
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
        #         "trigger": "on_new_run",
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
        #     }]
        # }
        schema = {
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
                "trigger": "on_new_run",
                "steps": [{
                    "tool": "git",
                    "checkout": "git@github.com:godfryd/kraken.git",
                    "branch": "master"
                }, {
                    "tool": "pytest",
                    "params": "tests",
                    "cwd": "kraken"
                }],
                "environments": [{
                    "system": "ubuntu-18.04",
                    "executor_group": "server",
                    "config": "c1"
                }]
            }]
        }
        stage = Stage(name='hello-world', description="This is a hello-world stage.", branch=branch,
                      schema=schema)
        db.session.commit()
        log.info("   created Stage record 'hello-world'")

    executor_group = ExecutorGroup.query.filter_by(name="server", project=project).one_or_none()
    if executor_group is None:
        executor_group = ExecutorGroup(name='server', project=project)
        db.session.commit()
        log.info("   created ExecutorGroup record 'server'")

    executor = Executor.query.filter_by(name="server", executor_group=executor_group).one_or_none()
    if executor is None:
        executor = Executor(name='server', executor_group=executor_group, address="server")
        db.session.commit()
        log.info("   created Executor record 'server'")


    _prepare_initial_preferences()
