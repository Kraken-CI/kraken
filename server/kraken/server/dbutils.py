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

from sqlalchemy.sql.expression import desc

from .models import Run, Flow, db
from . import utils
from . import consts


def get_prev_run(stage_id, flow_kind):
    q = Run.query
    q = q.filter_by(deleted=None)
    q = q.filter_by(stage_id=stage_id)
    q = q.join('flow')
    q = q.filter(Flow.kind == flow_kind)
    q = q.order_by(desc(Flow.created))
    prev_run = q.first()
    return prev_run


def find_cloud_assignment_group(agent):
    for aa in agent.agents_groups:
        ag = aa.agents_group
        if ag.deployment:
            return ag
    return None


def delete_agent(agent):
    agent.deleted = utils.utcnow()
    agent.disabled = True
    agent.authorized = False
    for aa in agent.agents_groups:
        db.session.delete(aa)
    db.session.commit()


def get_secret_values(project):
    secrets = []
    for s in project.secrets:
        if s.deleted:
            continue
        if s.kind == consts.SECRET_KIND_SSH_KEY:
            secrets.append(s.data['key'])
        elif s.kind == consts.SECRET_KIND_SIMPLE:
            secrets.append(s.data['secret'])
    return secrets
