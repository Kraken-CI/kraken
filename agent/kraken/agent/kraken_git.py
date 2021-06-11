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
import shutil
import logging

import minio

from . import utils
from . import tool
from . import sshkey

log = logging.getLogger(__name__)


def run(step, **kwargs):  # pylint: disable=unused-argument
    timeout = int(step.get('timeout', 60))
    url = step['checkout']
    dest = ''
    if 'destination' in step:
        dest = step['destination']

    # determine repo dir
    if dest:
        repo_dir = dest
    else:
        repo_dir = url.split('/')[-1]
        if repo_dir.endswith('.git'):
            repo_dir = repo_dir[:-4]

    # prepare accessing git repo
    ssh_agent = None
    access_token = None
    if 'ssh-key' in step:
        # username = step['ssh-key']['username']
        # url = '%s@%s' % (username, url)
        key = step['ssh-key']['key']
        ssh_agent = sshkey.SshAgent()
        ssh_agent.add_key(key)
    elif 'access-token' in step:
        access_token = step['access-token']
        if url.startswith('git@'):
            url = url[4:]
        url = 'https://%s@%s' % (access_token, url.replace(':', '/'))

    # setup connection to minio
    minio_addr = step['minio_addr']
    minio_addr = os.environ.get('KRAKEN_MINIO_ADDR', minio_addr)
    minio_access_key = step['minio_access_key']
    minio_secret_key = step['minio_secret_key']
    minio_bucket = step['minio_bucket']
    minio_folder = step['minio_folder']
    minio_repo_bundle_path = '%s/repo.bundle' % minio_folder
    mc = minio.Minio(minio_addr, access_key=minio_access_key, secret_key=minio_secret_key, secure=False)
    try:
        mc.bucket_exists(minio_bucket)
    except Exception as e:
        log.exception('problem with connecting to minio %s', minio_addr)
        msg = 'problem with connecting to minio %s: %s' % (minio_addr, str(e))
        return 1, msg

    # retrieve git repo bundle
    repo_bundle_path = 'repo.bundle'
    log.info('try to retrieve repo bundle %s / %s -> %s', minio_bucket, minio_repo_bundle_path, repo_bundle_path)
    try:
        mc.fget_object(minio_bucket, minio_repo_bundle_path, repo_bundle_path)
        bundle_present = True
    except Exception as e:
        if 'Object does not exist' in str(e):
            log.info('repo bundled not archived yet')
        else:
            log.exception('retriving repo from bundle failed, skipping it')
        bundle_present = False

    restore_ok = False
    if bundle_present:
        try:
            # restore git repo bundle
            utils.execute('git clone %s %s' % (repo_bundle_path, repo_dir), out_prefix='', timeout=timeout, raise_on_error=True)

            # restore original remote URL
            utils.execute('git remote set-url origin %s' % url, cwd=repo_dir, out_prefix='', timeout=timeout, raise_on_error=True)

            # pull latest stuff from remote
            utils.execute('git pull --ff-only', cwd=repo_dir, out_prefix='', timeout=timeout, raise_on_error=True)

            restore_ok = True
        except Exception:
            log.exception('cloning repo from bundle failed, skipping it')
            if os.path.exists(repo_dir):
                shutil.rmtree(repo_dir)

        # delete old bundle
        os.unlink(repo_bundle_path)

    # if restoring repo from bundle failed then do normal clone repo
    if not restore_ok:
        try:
            ret, _ = utils.execute('git clone %s %s' % (url, dest), mask=access_token, out_prefix='', timeout=timeout)
            if ret != 0:
                return ret, 'git clone exited with non-zero retcode'
        finally:
            if ssh_agent is not None:
                ssh_agent.shutdown()

    # bundle repo and cache it
    repo_bundle_path = os.path.abspath(os.path.join(repo_dir, '..', 'repo.bundle'))
    ret, _ = utils.execute('git bundle create %s --all' % repo_bundle_path, cwd=repo_dir, out_prefix='', timeout=300)
    if ret != 0:
        log.warning('repo bundle failed, skipping it')
    else:
        minio_bucket = step['minio_bucket']
        log.info('store repo bundle %s -> %s / %s', repo_bundle_path, minio_bucket, minio_repo_bundle_path)
        try:
            mc.fput_object(minio_bucket, minio_repo_bundle_path, repo_bundle_path)
        except Exception:
            log.exception('problem with storing repo bundle, skipping it')

    # checkout commit that comes from trigger, otherwise checkout master/main
    if 'trigger_data' in step and step['trigger_data'][0]['repo'] == step['http_url']:
        branch_or_commit = step['trigger_data'][0]['after']
    else:
        branch_or_commit = step.get('branch', 'master')  # TODO: detect if there is master, if not then checkout main

    # do checkout
    ret, _ = utils.execute('git checkout %s' % branch_or_commit, cwd=repo_dir, out_prefix='')
    if ret != 0:
        return ret, 'git checkout exited with non-zero retcode'

    return 0, ''


if __name__ == '__main__':
    tool.main()
