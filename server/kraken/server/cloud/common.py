# Copyright 2021 The Kraken Authors
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

from sqlalchemy.exc import IntegrityError
from psycopg2.errors import UniqueViolation  # pylint: disable=no-name-in-module

from .. import utils
from ..models import db
from ..models import Agent, AgentAssignment


log = logging.getLogger(__name__)


def _create_agent(params, ag):
    now = utils.utcnow()
    params['last_seen'] = now
    params['authorized'] = True
    params['disabled'] = False

    try:
        a = Agent(**params)
        db.session.commit()
        log.info('created new agent %s', a)
    except Exception:
        db.session.rollback()
        a = Agent.query.filter_by(address=params['address']).one_or_none()
        log.info('using existing agent %s', a)
        if a:
            a.created = now
            if a.deleted:
                log.info('undeleting agent %s', a)
                a.deleted = None
            for f, val in params.items():
                setattr(a, f, val)
            db.session.commit()
        else:
            log.info('agent %s duplicated but cannot find it', params['address'])
            raise

    try:
        AgentAssignment(agent=a, agents_group=ag)
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        if not isinstance(e.orig, UniqueViolation):
            raise

    return a
