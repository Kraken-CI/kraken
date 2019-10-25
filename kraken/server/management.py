import logging
import datetime

from flask import make_response, abort
from sqlalchemy.sql.expression import asc, desc
from sqlalchemy.orm import joinedload

import consts
from models import db, Branch, Flow, Run, Stage, Job, Step, ExecutorGroup, Tool, TestCaseResult
from models import Project

log = logging.getLogger(__name__)


def create_branch(project_id, branch):
    """
    This function creates a new person in the people structure
    based on the passed in person data

    :param person:  person to create in people structure
    :return:        201 on success, 406 on person exists
    """
    project = Project.query.filter_by(id=project_id).one_or_none()
    if project is None:
        abort(404, "Project not found")

    new_branch = Branch(project=project, name=branch['name'])
    db.session.commit()

    return new_branch.get_json(), 201


def get_branch(branch_id):
    branch = Branch.query.filter_by(id=branch_id).one_or_none()
    if branch is None:
        abort(404, "Branch not found")
    return branch.get_json(with_cfg=True), 200


def create_stage(branch_id, stage):
    """
    This function creates a new person in the people structure
    based on the passed in person data

    :param person:  person to create in people structure
    :return:        201 on success, 406 on person exists
    """
    branch = Branch.query.filter_by(id=branch_id).one_or_none()
    if branch is None:
        abort(404, "Branch not found")

    if 'schema' in stage:
        schema = stage['schema']
    else:
        schema = {'jobs': [], 'configs': [], 'trigger': 'manual'}

    new_stage = Stage(branch=branch, name=stage['name'], schema=schema)
    db.session.commit()

    return new_stage.get_json(), 201


def update_stage(stage_id, stage):
    stage_rec = Stage.query.filter_by(id=stage_id).one_or_none()
    if stage_rec is None:
        abort(404, "Stage not found")

    stage_rec.schema = stage['schema']
    db.session.commit()

    return stage_rec.get_json(), 200
