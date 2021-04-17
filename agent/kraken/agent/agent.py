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
import sys
import time
import logging
import argparse
import platform
import traceback

import pkg_resources
import distro

from . import logs
from . import utils
from . import config
from . import server
from . import jobber
from . import update
from . import install
from . import local_run
from . import docker_run
from . import lxd_run

log = logging.getLogger('agent')


def parse_args():
    parser = argparse.ArgumentParser(description='Kraken Agent')
    subparsers = parser.add_subparsers(title='Kraken Agent commands', dest='command')

    parser_run = subparsers.add_parser('run',
                                       help='Start Kraken Agent service',
                                       description='Start Kraken Agent service.')
    parser_run.add_argument('-s', '--server', help='Server URL')
    parser_run.add_argument('-d', '--data-dir', help='Directory for presistent data')
    parser_run.add_argument('-t', '--tools-dirs', help='List of tools directories')
    parser_run.add_argument('--no-update', action='store_true', help='Do not update agent automatically (useful in agent development)')

    pi = subparsers.add_parser('install',
                               help='Install Kraken Agent in the system as a systemd service',
                               description='Install Kraken Agent in the system as a systemd service.')

    pci = subparsers.add_parser('check-integrity',
                                help='Check if current installation of Kraken Agent is integral ie. is complete and should work ok',
                                description="Check if current installation of Kraken Agent is integral ie. is complete and should work ok.")

    args = parser.parse_args()
    return parser, parser_run, pi, pci, args


def dispatch_job(srv, job):
    try:
        now = time.time()
        deadline = now + job['timeout']
        job['deadline'] = deadline
        t0 = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(now))
        t1 = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(deadline))
        log.info('job now: %s, deadline: %s, time: %ss', t0, t1, job['timeout'])
        jobber.run(srv, job)
    except KeyboardInterrupt:
        raise
    except Exception:
        log.exception('job interrupted by exception')
        exc = traceback.format_exc()
        srv.report_step_result(job['id'], 0, {'status': 'error', 'reason': 'exception', 'msg': exc})


def apply_cfg_changes(changes):
    if 'clickhouse_addr' in changes:
        clickhouse_addr = changes['clickhouse_addr']
        logs.setup_logging('agent', clickhouse_addr)


def collect_host_info():
    host_info = {}

    # collect basic host and its system information
    s = platform.system().lower()
    host_info['system_type'] = s
    if s == 'linux':
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
    print('All is ok')
    return True


def main():
    logs.setup_logging('agent')
    kraken_version = pkg_resources.get_distribution('kraken-agent').version
    log.info('Starting Kraken Agent, version %s', kraken_version)

    parser, pr, _, _, args = parse_args()
    cfg = vars(args)
    config.set_config(cfg)

    if args.command is None:
        parser.print_usage()
        print('missing command - please, provide one of commands: run, install, check-integrity')
        sys.exit(1)

    # check integrity (used during update)
    if args.command == 'check-integrity':
        if check_integrity():
            sys.exit(0)
        else:
            sys.exit(1)
    # install agent
    elif args.command == 'install':
        install.install()
        sys.exit(0)

    # no specific command so start agent main loop

    if not args.server:
        pr.print_usage()
        print('missing required -s/--server option')
        sys.exit(1)

    if not args.data_dir:
        pr.print_usage()
        print('missing required -d/--data-dir option')
        sys.exit(1)

    # allow running kktool from current dir in container
    os.environ["PATH"] += os.pathsep + os.getcwd()
    os.environ["PATH"] += os.pathsep + os.path.abspath(__file__)

    data_dir = config.get('data_dir')
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    jobs_dir = os.path.join(data_dir, 'jobs')
    if not os.path.exists(jobs_dir):
        os.makedirs(jobs_dir)

    srv = server.Server()
    if not srv.srv_addr:
        print('There is missing server address.')
        print('Run agent with -s parameter or start agent container')
        print('with KRAKEN_SERVER_ADDR env variable set properly.')
        sys.exit(1)

    host_info = collect_host_info()
    while True:
        resp = srv.report_host_info(host_info)
        log.info('RESP %s', resp)
        if 'unauthorized' not in resp:
            break
        log.warning('agent is not authorized, sleeping for 10s')
        time.sleep(10)

    while True:
        try:
            job, cfg_changes, version = srv.get_job()

            if cfg_changes:
                apply_cfg_changes(cfg_changes)

            if not args.no_update and version and version != kraken_version:
                log.info('new version: %s, was: %s, updating agent', version, kraken_version)
                update.update_agent(version)

            if job:
                log.set_ctx(job=job['id'], run=job['run_id'])
            log.info('received job: %s', str(job)[:200])

            if job:
                dispatch_job(srv, job)
            else:
                time.sleep(5)
        except KeyboardInterrupt:
            log.exception('exiting due to ctrl-c')
            break
        except Exception:
            log.exception('ignored exception in agent main loop')
            time.sleep(5)
        log.reset_ctx()


if __name__ == '__main__':
    main()
