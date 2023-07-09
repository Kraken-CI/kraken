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

from flask import Flask
from sqlalchemy.sql.expression import asc

from . import logs
from .models import db, Agent, Run, Job, get_setting
from . import consts
from . import srvcheck
from .. import version
from . import utils

log = logging.getLogger('scheduler')


def _get_idle_agents():
    all_idle_agents = Agent.query.filter_by(job=None, authorized=True, disabled=False, deleted=None).all()
    agents_count = len(all_idle_agents)
    if agents_count == 0:
        return 0, {}, {}

    idle_agents_by_group = {}
    idle_agents_by_sys_group = {}
    for ag in all_idle_agents:
        log.info('idle agent: %s', ag)
        for asm in ag.agents_groups:
            grp_id = asm.agents_group_id
            log.info('  grp: %s', grp_id)
            if grp_id not in idle_agents_by_group:
                idle_agents_by_group[grp_id] = []
            idle_agents_by_group[grp_id].append(ag)

            sys_grp_key = (asm.agents_group_id,
                           ag.host_info['system'] if ag.host_info and 'system' in ag.host_info else 'fake')
            if sys_grp_key not in idle_agents_by_sys_group:
                idle_agents_by_sys_group[sys_grp_key] = []
            idle_agents_by_sys_group[sys_grp_key].append(ag)

    return agents_count, idle_agents_by_group, idle_agents_by_sys_group


def _get_waiting_jobs():
    q = Job.query.filter_by(state=consts.JOB_STATE_QUEUED, agent_used=None)
    q = q.join('run')
    waiting_jobs = q.order_by(asc(Run.created), asc(Job.created)).all()  # FIFO

    return waiting_jobs


def _assign_jobs(agents_count, idle_agents_by_group, idle_agents_by_sys_group,
                 waiting_jobs):
    counter = 0

    for j in waiting_jobs:
        log.set_ctx(branch=j.run.flow.branch_id, flow_kind=j.run.flow.kind, flow=j.run.flow_id, run=j.run.id, job=j.id)
        log.info('job %s, executor %s', j, j.system.executor)

        # system does not have to be taken into account when user selects ANY system
        # or when executor is not local eg. it is a docker container
        if j.system.name == 'any' or j.system.executor != 'local':
            idle_agents = idle_agents_by_group.get(j.agents_group_id, [])
        else:
            key = (j.agents_group_id, j.system.name)
            idle_agents = idle_agents_by_sys_group.get(key, [])

        # find idle agent from given agents groups
        best_agent = None
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
        j.agent_used = best_agent
        j.assigned = utils.utcnow()
        db.session.commit()
        log.info("assigned job %s to agent %s", j, best_agent)

        counter += 1
        # if all idle agents used then stop assigning
        if counter == agents_count:
            break

    log.reset_ctx()

    return counter


def assign_jobs_to_agents():

    agents_count, idle_agents_by_group, idle_agents_by_sys_group = _get_idle_agents()
    if agents_count == 0:
        log.info('no idle agents')
        return 0

    waiting_jobs = _get_waiting_jobs()

    if len(waiting_jobs) > 0:
        log.info('idle agents: %s, waiting jobs %s', agents_count, waiting_jobs)

    counter = _assign_jobs(agents_count, idle_agents_by_group, idle_agents_by_sys_group, waiting_jobs)

    return counter


def create_app():
    # addresses
    db_url = os.environ.get('KRAKEN_DB_URL', consts.DEFAULT_DB_URL)
    planner_url = os.environ.get('KRAKEN_PLANNER_URL', consts.DEFAULT_PLANNER_URL)

    srvcheck.check_postgresql(db_url)
    srvcheck.wait_for_service('planner', planner_url, 7997)

    logs.setup_logging('scheduler')
    log.info('Kraken Scheduler started, version %s', version.version)

    # Create  Flask app instance
    app = Flask('Kraken Scheduler')

    # Configure the SqlAlchemy part of the app instance
    app.config["SQLALCHEMY_ECHO"] = False
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url + '?application_name=scheduler'
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # initialize SqlAlchemy
    db.init_app(app)

    # setup sentry
    with app.app_context():
        sentry_url = get_setting('monitoring', 'sentry_dsn')
        logs.setup_sentry(sentry_url)

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
            sleep_time = max(sleep_time, 0)
            log.info("scheduled %d jobs in %.1fs, go sleep for %.1fs", jobs_cnt, dt, sleep_time)
            if sleep_time > 0:
                time.sleep(sleep_time)


if __name__ == "__main__":
    main()
