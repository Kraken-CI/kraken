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
import shutil
import logging
import tempfile
import subprocess

from . import minioops

log = logging.getLogger(__name__)


def _run(cmd, check=True, cwd=None):
    log.info("execute '%s' in '%s'", cmd, cwd)
    p = subprocess.run(cmd, shell=True, check=check, cwd=cwd)
    return p


def get_repo_commits_since(branch_id, prev_run, repo_url, repo_branch):
    commits = []
    log.info('checking commits in %s %s', repo_url, repo_branch)

    with tempfile.TemporaryDirectory(prefix='kraken-git-') as tmpdir:
        # retrieve git repo bundle from minio
        minio_bucket, minio_folder = minioops.get_or_create_minio_bucket_for_git(branch_id, repo_url)
        mc = minioops.get_minio()
        minio_repo_bundle_path = '%s/repo.bundle' % minio_folder
        repo_bundle_path = os.path.join(tmpdir, 'repo.bundle')
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

        repo_dir = os.path.join(tmpdir, 'repo')
        restore_ok = False
        if bundle_present:
            try:
                # restore git repo bundle
                _run('git clone %s repo' % repo_bundle_path, check=True, cwd=tmpdir)

                # restore original remote URL
                _run('git remote set-url origin %s' % repo_url, check=True, cwd=repo_dir)

                # pull latest stuff from remote
                _run('git pull', check=True, cwd=repo_dir)

                restore_ok = True
            except:
                log.exception('cloning repo from bundle failed, skipping it')
                if os.path.exists(repo_dir):
                    shutil.rmtree(repo_dir)

            # delete old bundle
            os.unlink(repo_bundle_path)

        # if restoring repo from bundle failed then do normal clone repo
        if not restore_ok:
            # clone repo
            #cmd = "git clone --single-branch --branch %s '%s' repo" % (repo_branch, repo_url)
            cmd = "git clone '%s' repo" % repo_url
            p = subprocess.run(cmd, shell=True, check=False, cwd=tmpdir, capture_output=True, text=True)
            if p.returncode != 0:
                err = "command '%s' returned non-zero exit status %d\n" % (cmd, p.returncode)
                err += p.stdout.strip()[:140] + '\n'
                err += p.stderr.strip()[:140]
                err = err.strip()
                raise Exception(err)

        # get commits history
        cmd = "git log --no-merges --since='2 weeks ago' -n 20 --pretty=format:'commit:%H%nauthor:%an%nemail:%ae%ndate:%aI%nsubject:%s'"
        if prev_run and prev_run.repo_data and repo_url in prev_run.repo_data:
            base_commit = prev_run.repo_data[repo_url][0]['commit']
            log.info('base commit: %s', base_commit)
            cmd += ' %s..' % base_commit
        else:
            log.info('no base commit %s %s', repo_url, prev_run.repo_data)
        p = subprocess.run(cmd, shell=True, check=True, cwd=repo_dir, capture_output=True, text=True)
        text = p.stdout.strip()

        # bundle repo and cache it
        p = _run('git bundle create %s --all' % repo_bundle_path, check=False, cwd=repo_dir)
        if p.returncode != 0:
            log.warning('repo bundle failed, skipping it')
        else:
            log.info('store repo bundle %s -> %s / %s', repo_bundle_path, minio_bucket, minio_repo_bundle_path)
            try:
                mc.fput_object(minio_bucket, minio_repo_bundle_path, repo_bundle_path)
            except:
                log.exception('problem with storing repo bundle, skipping it')


    # collect commits info
    commit = {}
    for line in text.splitlines():
        field, val = line.split(':', 1)
        commit[field] = val
        if len(commit) == 5:
            commits.append(commit)
            log.info('  %s', commit)
            commit = {}

    return commits


def get_schema_from_repo(repo_url, repo_branch, repo_access_token, schema_file):  # pylint: disable=unused-argument
    with  tempfile.TemporaryDirectory(prefix='kraken-git-') as tmpdir:
        # clone repo
        cmd = "git clone --depth 1 --single-branch --branch %s '%s' repo" % (repo_branch, repo_url)
        p = subprocess.run(cmd, shell=True, check=False, cwd=tmpdir, capture_output=True, text=True)
        if p.returncode != 0:
            err = "command '%s' returned non-zero exit status %d\n" % (cmd, p.returncode)
            err += p.stdout.strip()[:140] + '\n'
            err += p.stderr.strip()[:140]
            err = err.strip()
            raise Exception(err)

        repo_dir = os.path.join(tmpdir, 'repo')

        # get last commit SHA
        cmd = 'git rev-parse --verify HEAD'
        p = subprocess.run(cmd, shell=True, check=True, cwd=repo_dir, capture_output=True, text=True)
        version = p.stdout.strip()

        # read schema code
        schema_path = os.path.join(repo_dir, schema_file)
        with open(schema_path, 'r') as f:
            schema_code = f.read()

    return schema_code, version
