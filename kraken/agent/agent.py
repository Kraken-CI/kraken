#!/usr/bin/env python3

import os
import time
import argparse
import logging
import traceback

import config
import server
import jobber

LOG_FMT = '%(asctime)s %(levelname)-4.4s p:%(process)5d %(module)8.8s:%(lineno)-5d %(message)s'


log = logging.getLogger('agent')


def parse_args():
    parser = argparse.ArgumentParser(description='Kraken Agent')
    parser.add_argument('-s', '--server', help='Server URL')
    parser.add_argument('-t', '--tools-dirs', help='List of tools directories')
    parser.add_argument('-d', '--data-dir', help='Directory for presistent data')

    args = parser.parse_args()
    return args


def dispatch_job(srv, job):
    try:
        jobber.run(srv, job)
    except KeyboardInterrupt:
        raise
    except:
        log.exception('job interrupted by exception')
        exc = traceback.format_exc()
        srv.report_step_result(job['id'], 0, {'status': 'error', 'reason': 'exception', 'msg': exc})


def main():
    logging.basicConfig(format=LOG_FMT, level=logging.INFO)

    args = parse_args()
    cfg = vars(args)
    config.set_config(cfg)

    data_dir = config.get('data_dir')
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    jobs_dir = os.path.join(data_dir, 'jobs')
    if not os.path.exists(jobs_dir):
        os.makedirs(jobs_dir)

    srv = server.Server()

    while True:
        try:
            job = srv.get_job()
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



if __name__ == '__main__':
    main()
