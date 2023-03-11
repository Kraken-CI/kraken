# Copyright 2020-2021 The Kraken Authors
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
import platform
import traceback

import distro
import pkg_resources

from . import logs
from . import utils
from . import config
from . import server
from . import jobber
from . import update
from . import local_run
from . import docker_run
from . import lxd_run

log = logging.getLogger(__name__)


def _dispatch_job(srv, job):
    try:
        now = time.time()
        deadline = now + job['timeout']
        job['deadline'] = deadline
        t0, t1, _ = utils.get_times(deadline)
        log.info('job now: %s, deadline: %s, time: %ss', t0, t1, job['timeout'])
        jobber.run(srv, job)
    except Exception:
        log.exception('job interrupted by exception')
        exc = traceback.format_exc()
        srv.report_step_result(job['id'], 0, {'status': 'error', 'reason': 'exception', 'msg': exc})


def _apply_cfg_changes(changes):
    if 'clickhouse_addr' in changes:
        clickhouse_addr = changes['clickhouse_addr']
        logs.setup_logging('agent', clickhouse_addr)


def _collect_host_info():
    host_info = {}

    sys = config.get('system_id', '')
    host_info['system'] = sys

    # collect basic host and its system information
    s = platform.system().lower()
    host_info['system_type'] = s
    if s == 'linux':
        if not host_info['system']:
            host_info['system'] = '%s-%s' % (distro.id(), distro.version())
        host_info['distro_name'] = distro.id()
        host_info['distro_version'] = distro.version()

    # detect isolation
    host_info['isolation_type'] = 'bare-metal'
    host_info['isolation'] = 'bare-metal'
    if utils.is_in_docker():
        host_info['isolation_type'] = 'container'
        host_info['isolation'] = 'docker'
    elif utils.is_in_lxc():
        host_info['isolation_type'] = 'container'
        host_info['isolation'] = 'lxc'

    # check executors capabilities
    for mod in [local_run, docker_run, lxd_run]:
        caps = mod.detect_capabilities()
        host_info.update(caps)

    return host_info


def check_integrity():
    # check integrity (used during update)
    print('All is ok')
    return True


def _enable_masking_secrets_in_logs(job):
    secrets = []
    if 'secrets' in job:
        secrets = job['secrets']
    log.set_secrets(secrets)


def _disable_masking_secrets_in_logs():
    if logs.g_masking_handler:
        logs.g_masking_handler.flush_log_entries()
    log.set_secrets([])


def run():
    kraken_version = pkg_resources.get_distribution('kraken-agent').version

    # allow running kktool from current dir in container
    os.environ["PATH"] += os.pathsep + os.getcwd()
    os.environ["PATH"] += os.pathsep + os.path.abspath(__file__)

    # check server address
    srv_addr = config.get('server')
    if not srv_addr:
        raise Exception('missing server address')
    if not srv_addr.startswith('http'):
        raise Exception('incorrect server URL (no http/https schema): %s' % srv_addr)
    log.info('server address: %s', srv_addr)

    data_dir = config.get('data_dir')
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    log.info('data dir: %s', data_dir)
    jobs_dir = os.path.join(data_dir, 'jobs')
    if not os.path.exists(jobs_dir):
        os.makedirs(jobs_dir)

    srv = server.Server()

    host_info = _collect_host_info()
    while True:
        resp = srv.report_host_info(host_info)
        log.info('RESP %s', resp)
        if 'unauthorized' not in resp:
            break
        log.warning('agent is not authorized, sleeping for 10s')
        time.sleep(10)
    agent_id = resp.get('agent_id', None)
    log.set_ctx(agent=agent_id)

    one_job = config.get('one_job', False)
    if one_job:
        log.info("this is one job agent")

    while True:
        try:
            job, cfg_changes, version = srv.get_job()

            if cfg_changes:
                _apply_cfg_changes(cfg_changes)

            if not config.get('no_update') and version and version != kraken_version:
                log.info('new version: %s, was: %s, updating agent', version, kraken_version)
                update.update_agent(version)

            if job:
                log.set_ctx(job=job['id'], run=job['run_id'], flow=job['flow_id'],
                            flow_kind=job['flow_kind'], branch=job['branch_id'])

                _enable_masking_secrets_in_logs(job)

            log.info('>>>>>> received job: %s', str(job)[:200])

            if job:
                _dispatch_job(srv, job)

                # disable masking secrets in logs
                _disable_masking_secrets_in_logs()

                if one_job:
                    log.info("one job so terminating")
                    break
            else:
                time.sleep(5)
        except KeyboardInterrupt:
            log.exception('exiting due to ctrl-c')
            break
        except Exception:
            log.exception('ignored exception in agent main loop')
            time.sleep(5)
        log.reset_ctx()
        log.set_ctx(agent=agent_id)
