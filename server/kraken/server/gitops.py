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

import furl

from . import minioops

log = logging.getLogger(__name__)


def _run(cmd, check=True, cwd=None, capture_output=False, text=None, secret=None):
    if secret:
        cmd2 = cmd.replace(secret, '******')
    else:
        cmd2 = cmd
    log.info("execute '%s' in '%s'", cmd2, cwd)
    p = subprocess.run(cmd, shell=True, check=check, cwd=cwd, capture_output=capture_output, text=text)
    return p


def _retrieve_git_repo(tmpdir, repo_url, git_cfg, mc, minio_bucket, minio_repo_bundle_path):
    # retrieve git repo bundle from minio
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

    # prepare git config
    cfg_params = []
    for k, v in git_cfg.items():
        cfg_params.append('-c %s=%s' % (k, v))
    cfg_params = ' '.join(cfg_params)

    repo_dir = os.path.join(tmpdir, 'repo')
    restore_ok = False
    if bundle_present:
        try:
            # restore git repo bundle
            _run('git clone %s %s repo' % (cfg_params, repo_bundle_path), check=True, cwd=tmpdir)

            # restore original remote URL
            _run('git remote set-url origin %s' % repo_url, check=True, cwd=repo_dir)

            # pull latest stuff from remote
            _run('git pull', check=True, cwd=repo_dir)

            restore_ok = True
        except Exception:
            log.exception('cloning repo from bundle failed, skipping it')
            if os.path.exists(repo_dir):
                shutil.rmtree(repo_dir)

        # delete old bundle
        os.unlink(repo_bundle_path)

    # if restoring repo from bundle failed then do normal clone repo
    if not restore_ok:
        # clone repo
        #cmd = "git clone --single-branch --branch %s '%s' repo" % (repo_branch, repo_url)
        cmd = "git clone %s '%s' repo" % (cfg_params, repo_url)
        p = _run(cmd, check=False, cwd=tmpdir, capture_output=True, text=True)
        if p.returncode != 0:
            err = "command '%s' returned non-zero exit status %d\n" % (cmd, p.returncode)
            err += p.stdout.strip()[:140] + '\n'
            err += p.stderr.strip()[:140]
            err = err.strip()
            raise Exception(err)

    return repo_dir


def _collect_commits_from_git_log(text):
    commits = []
    commit = {'author': {}, 'added': [], 'modified': [], 'removed': []}
    record_lines = 0
    for line in text.splitlines():
        line = line.strip()
        # if empty line ie. record finished
        if not line:
            log.info('  %s', commit)
            commits.append(commit)
            commit = {'author': {}, 'added': [], 'modified': [], 'removed': []}
            record_lines = 0
            continue

        record_lines += 1
        if record_lines <= 5:
            field, val = line.split(':', 1)
            if field == 'commit':
                commit['id'] = val
            elif field == 'author':
                commit['author']['name'] = val
            elif field == 'email':
                commit['author']['email'] = val
            elif field == 'date':
                commit['timestamp'] = val
            elif field == 'subject':
                commit['message'] = val
            else:
                raise Exception('unrecognized field %s' % field)
        else:
            flag = line[0]
            fpath = line[1:].strip()
            if flag == 'A':
                commit['added'].append(fpath)
            elif flag == 'D':
                commit['removed'].append(fpath)
            else:
                commit['modified'].append(fpath)

    # add last non-empty entry
    if 'id' in commit:
        log.info('  %s', commit)
        commits.append(commit)

    return commits


def get_repo_commits_since(branch_id, prev_run, repo_url, repo_branch, git_cfg):
    log.info('checking commits in %s %s', repo_url, repo_branch)

    with tempfile.TemporaryDirectory(prefix='kraken-git-') as tmpdir:
        # prepare minio
        minio_bucket, minio_folder = minioops.get_or_create_minio_bucket_for_git(repo_url, branch_id=branch_id)
        mc = minioops.get_minio()
        minio_repo_bundle_path = '%s/repo.bundle' % minio_folder

        # retrieve repo from minio in bundle form or from remote git repository
        repo_dir = _retrieve_git_repo(tmpdir, repo_url, git_cfg, mc, minio_bucket, minio_repo_bundle_path)

        # get commits history
        cmd = "git log --no-merges --since='2 weeks ago' -n 20 --pretty=format:'commit:%H%nauthor:%an%nemail:%ae%ndate:%aI%nsubject:%s' --name-status"
        if prev_run and prev_run.repo_data_id and prev_run.repo_data.data:
            base_commit = None
            for rd in prev_run.repo_data.data:
                if rd['repo'] == repo_url:
                    base_commit = rd['commits'][0]['id']
                    break
            log.info('base commit: %s', base_commit)
            if base_commit:
                cmd += ' %s..' % base_commit
        else:
            base_commit = None
            log.info('no base commit %s', repo_url)
        p = _run(cmd, check=True, cwd=repo_dir, capture_output=True, text=True)
        text = p.stdout.strip()

        # bundle repo and cache it
        repo_bundle_path = os.path.join(tmpdir, 'repo.bundle')
        p = _run('git bundle create %s --all' % repo_bundle_path, check=False, cwd=repo_dir)
        if p.returncode != 0:
            log.warning('repo bundle failed, skipping it')
        else:
            log.info('store repo bundle %s -> %s / %s', repo_bundle_path, minio_bucket, minio_repo_bundle_path)
            try:
                mc.fput_object(minio_bucket, minio_repo_bundle_path, repo_bundle_path)
            except Exception:
                log.exception('problem with storing repo bundle, skipping it')

    # collect commits from git log
    commits = _collect_commits_from_git_log(text)

    return commits, base_commit


def get_schema_from_repo(repo_url, repo_branch, repo_access_token, schema_file, git_clone_params):  # pylint: disable=unused-argument
    with  tempfile.TemporaryDirectory(prefix='kraken-git-') as tmpdir:
        # clone repo
        if not git_clone_params:
            git_clone_params = ''

        if repo_access_token:
            url = furl.furl(repo_url)
            url.username = repo_access_token
            repo_url = url.tostr()

        cmd = "git clone --depth 1 --single-branch --branch %s %s '%s' repo" % (repo_branch, git_clone_params, repo_url)
        p = _run(cmd, check=False, cwd=tmpdir, capture_output=True, text=True, secret=repo_access_token)
        if p.returncode != 0:
            if repo_access_token:
                cmd = cmd.replace(repo_access_token, '******')
            err = "command '%s' returned non-zero exit status %d\n" % (cmd, p.returncode)
            err += p.stdout.strip()[:140] + '\n'
            err += p.stderr.strip()[:140]
            err = err.strip()
            raise Exception(err)

        repo_dir = os.path.join(tmpdir, 'repo')

        # get last commit SHA
        cmd = 'git rev-parse --verify HEAD'
        p = _run(cmd, check=True, cwd=repo_dir, capture_output=True, text=True)
        version = p.stdout.strip()

        # read schema code
        schema_path = os.path.join(repo_dir, schema_file)
        with open(schema_path, 'r') as f:
            schema_code = f.read()

    return schema_code, version


def clone_tool_repo(repo_url, repo_tag, tool_id):
    log.info('clone repo %s %s', repo_url, repo_tag)

    tmpdir = tempfile.TemporaryDirectory(prefix='kraken-git-')

    try:
        # prepare minio
        minio_bucket, minio_folder = minioops.get_or_create_minio_bucket_for_git(repo_url, tool_id=tool_id)
        mc = minioops.get_minio()
        minio_repo_bundle_path = '%s/repo.bundle' % minio_folder

        # retrieve repo from minio in bundle form or from remote git repository
        repo_dir = _retrieve_git_repo(tmpdir.name, repo_url, {}, mc, minio_bucket, minio_repo_bundle_path)

        # get last commit SHA
        cmd = 'git rev-parse --verify --short HEAD'
        p = _run(cmd, check=True, cwd=repo_dir, capture_output=True, text=True)
        version = p.stdout.strip()

        # bundle repo and cache it
        repo_bundle_path = os.path.join(tmpdir.name, 'repo.bundle')
        p = _run('git bundle create %s --all' % repo_bundle_path, check=False, cwd=repo_dir)
        if p.returncode != 0:
            log.warning('repo bundle failed, skipping it')
        else:
            log.info('store repo bundle %s -> %s / %s', repo_bundle_path, minio_bucket, minio_repo_bundle_path)
            try:
                mc.fput_object(minio_bucket, minio_repo_bundle_path, repo_bundle_path)
            except Exception:
                log.exception('problem with storing repo bundle, skipping it')
    except:
        tmpdir.cleanup()
        raise

    return tmpdir, os.path.join(tmpdir.name, 'repo'), version
