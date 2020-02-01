#!/usr/bin/env python3

import os
import time
import logging
import argparse
import platform
import traceback

from . import logs
from . import config
from . import server
from . import jobber

log = logging.getLogger('agent')


def parse_args():
    parser = argparse.ArgumentParser(description='Kraken Agent')
    parser.add_argument('-s', '--server', help='Server URL', required=True)
    parser.add_argument('-d', '--data-dir', help='Directory for presistent data', required=True)
    parser.add_argument('-t', '--tools-dirs', help='List of tools directories')

    args = parser.parse_args()
    return args


def dispatch_job(srv, job):
    try:
        now = time.time()
        deadline = now + job['timeout']
        job['deadline'] = deadline
        log.info('job deadline: %s', deadline)
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
    if s == 'linux':
        distr = platform.linux_distribution(full_distribution_name=False)  # pylint: disable=deprecated-method
        sys_info['distro_name'] = distr[0].lower()
        sys_info['distro_version'] = distr[1]

    return sys_info


def main():
    logs.setup_logging('agent')

    args = parse_args()
    cfg = vars(args)
    config.set_config(cfg)

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
            job, cfg_changes = srv.get_job()

            if cfg_changes:
                apply_cfg_changes(cfg_changes)

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
