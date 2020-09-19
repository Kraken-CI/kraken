#!/usr/bin/env python3

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

import os
import time
import logging
import datetime

from flask import Flask
from sqlalchemy.sql.expression import asc

from . import logs
from .models import db, Agent, Run, Job
from . import consts
from . import srvcheck
from .. import version

log = logging.getLogger('scheduler')


def assign_jobs_to_agents():
    counter = 0

    all_idle_agents = Agent.query.filter_by(job=None, authorized=True).all()
    agents_count = len(all_idle_agents)
    if agents_count == 0:
        return 0
    idle_agents_by_group = {}
    for e in all_idle_agents:
        # log.info('idle agent: %s', e)
        for asm in e.agents_groups:
            grp_id = asm.agents_group_id
            # log.info('  grp: %s', grp_id)
            if grp_id not in idle_agents_by_group:
                idle_agents_by_group[grp_id] = []
            idle_agents_by_group[grp_id].append(e)

    q = Job.query.filter_by(state=consts.JOB_STATE_QUEUED, agent_used=None)
    q = q.join('run')
    waiting_jobs = q.order_by(asc(Run.created), asc(Job.created)).all()  # FIFO
    if waiting_jobs:
        log.info('idle agents: %s, waiting jobs %s', agents_count, waiting_jobs)

    for j in waiting_jobs:
        log.info('job %s', j)
        # find idle agent from given agents group
        best_agent = None
        idle_agents = idle_agents_by_group.get(j.agents_group_id, [])
        while best_agent is None:
            if len(idle_agents) == 0:
                log.info('no avail agents for job %s', j)
                break
            best_agent = idle_agents.pop()
            if best_agent.job:
                log.info('agent busy %s', best_agent)
                best_agent = None

        if best_agent is None:
            log.info('no agents for job %s', j)
            continue

        # assign job to found agent
        best_agent.job = j
        best_agent.cancel = False
        j.agent_used = best_agent
        j.assigned = datetime.datetime.utcnow()
        db.session.commit()
        log.info("assigned job %s to agent %s", j, best_agent)

        counter += 1
        # if all idle agents used then stop assigning
        if counter == agents_count:
            break

    return counter


def create_app():
    # addresses
    db_url = os.environ.get('KRAKEN_DB_URL', consts.DEFAULT_DB_URL)
    planner_url = os.environ.get('KRAKEN_PLANNER_URL', consts.DEFAULT_PLANNER_URL)

    srvcheck.check_postgresql(db_url)
    srvcheck.check_url('planner', planner_url, 7997)

    logs.setup_logging('scheduler')
    log.info('Kraken Scheduler started, version %s', version.version)

    # Create  Flask app instance
    app = Flask('Kraken Scheduler')

    # Configure the SqlAlchemy part of the app instance
    app.config["SQLALCHEMY_ECHO"] = False
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # initialize SqlAlchemy
    db.init_app(app)

    return app


def main():
    app = create_app()

    with app.app_context():

        while True:
            t0 = time.time()
            jobs_cnt = assign_jobs_to_agents()
            t1 = time.time()

            dt = t1 - t0
            sleep_time = 5 - dt
            if sleep_time < 0:
                sleep_time = 0
            log.info("scheduled %d jobs in %.1fs, go sleep for %.1fs", jobs_cnt, dt, sleep_time)
            if sleep_time > 0:
                time.sleep(sleep_time)


if __name__ == "__main__":
    main()
