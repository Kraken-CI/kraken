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

from . import logs
from . import config
from . import server
from . import jobber
from . import update
from . import install

log = logging.getLogger('agent')


def parse_args():
    parser = argparse.ArgumentParser(description='Kraken Agent')
    parser.add_argument('-s', '--server', help='Server URL')
    parser.add_argument('-d', '--data-dir', help='Directory for presistent data')
    parser.add_argument('-t', '--tools-dirs', help='List of tools directories')
    parser.add_argument('--no-update', action='store_true', help='Do not update agent automatically (useful in agent development)')
    parser.add_argument('command', help="A command to execute")

    args = parser.parse_args()
    return parser, args


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
    except:
        log.exception('job interrupted by exception')
        exc = traceback.format_exc()
        srv.report_step_result(job['id'], 0, {'status': 'error', 'reason': 'exception', 'msg': exc})


def apply_cfg_changes(changes):
    if 'logstash_addr' in changes:
        logstash_addr = changes['logstash_addr']
        logs.setup_logging('agent', logstash_addr)
        os.environ['KRAKEN_LOGSTASH_ADDR'] = logstash_addr


def collect_sys_info():
    sys_info = {}
    s = platform.system().lower()
    sys_info['system'] = s
    # if s == 'linux':
    #     distr = platform.linux_distribution(full_distribution_name=False)  # pylint: disable=deprecated-method
    #     sys_info['distro_name'] = distr[0].lower()
    #     sys_info['distro_version'] = distr[1]

    return sys_info


def check_integrity():
    return True


def main():
    logs.setup_logging('agent')
    kraken_version = pkg_resources.get_distribution('kraken-agent').version
    log.info('Starting Kraken Agent, version %s', kraken_version)

    parser, args = parse_args()
    cfg = vars(args)
    config.set_config(cfg)

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

    if args.server is None:
        parser.print_usage()
        print('missing required --server option')
        sys.exit(1)

    if args.data_dir is None:
        parser.print_usage()
        print('missing required --data-dir option')
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

    sys_info = collect_sys_info()
    srv.report_sys_info(sys_info)

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
        except:
            log.exception('ignored exception in agent main loop')
            time.sleep(5)
        log.reset_ctx()


if __name__ == '__main__':
    main()
