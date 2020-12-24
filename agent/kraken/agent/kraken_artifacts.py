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
import glob
import logging

import minio

log = logging.getLogger(__name__)


def _upload_all(mc, minio_bucket, cwd, source, rundir, dest, report_artifact):
    for src in source:
        if cwd:
            cwd = os.path.abspath(cwd)
            src = os.path.abspath(os.path.join(cwd, src))

        if '*' not in src and os.path.isdir(src):
            src = os.path.join(src, '**')

        recursive = '**' in src

        files_num = 0
        for f in glob.iglob(src, recursive=recursive):
            if os.path.isdir(f):
                continue

            if cwd:
                f_path = os.path.relpath(f, cwd)
            else:
                f_path = f
            dest_f = os.path.join(rundir, dest, f_path)
            dest_f = os.path.normpath(dest_f)

            log.info('store %s -> %s / %s', f, minio_bucket, dest_f)
            mc.fput_object(minio_bucket, dest_f, f)

            pth = os.path.join(dest, f_path)
            pth = os.path.normpath(pth)
            artifact = dict(path=pth, size=os.path.getsize(f))
            report_artifact(artifact)
            files_num += 1

        # if no files were uploaded then raise error or just mention about that
        if files_num == 0:
            if '*' in src:
                log.warning('no files found for %s', src)
            else:
                msg = 'file %s not found for upload' % src
                log.error(msg)
                return 1, msg

    return 0, ''


def _download_dir(mc, minio_bucket, subdir, src_dir, dest):
    cnt = 0
    src = os.path.join(subdir, src_dir) + '/'
    objects = mc.list_objects(minio_bucket, src)
    log.info('objects in %s: %s', src, objects)
    for r in objects:
        log.info('obj %s', r.object_name)
        if r.is_dir:
            next_dir = os.path.join(src_dir, r.object_name)
            next_dest = os.path.join(dest, r.object_name)
            cnt += _download_dir(mc, minio_bucket, subdir, next_dir, next_dest)
        else:
            dest_file = os.path.join(src_dir, os.path.relpath(r.object_name, src))
            mc.fget_object(minio_bucket, r.object_name, dest_file)
            log.info('downloaded %s -> %s', r.object_name, dest_file)
            cnt += 1
    return cnt


def _download_file_or_dir(mc, minio_bucket, subdir, source, dest):
    cnt = 0
    dest_file = os.path.realpath(os.path.join(dest, source))
    src = '%s/%s' % (subdir, source)
    try:
        log.info('try download %s -> %s', src, dest_file)
        mc.fget_object(minio_bucket, src, dest_file)
        log.info('downloaded %s -> %s', src, dest_file)
        cnt = 1
    except Exception as e:
        log.exception('some problem with downloading')
        if hasattr(e, 'code') and e.code == 'NoSuchKey':  # pylint: disable=no-member
            cnt = _download_dir(mc, minio_bucket, subdir, source, dest_file)
        else:
            raise
    return cnt


def _download_all(mc, minio_bucket, flow_id, run_id, cwd, source, dest):
    if cwd:
        dest = os.path.join(cwd, dest)

    if not os.path.exists(dest):
        os.makedirs(dest)

    runs = []
    for r in mc.list_objects(minio_bucket, '%d/' % flow_id):
        if not r.is_dir:
            continue
        r_id = int(r.object_name.split('/')[1])
        if r_id == run_id:
            continue
        runs.append(r_id)
    runs.sort()

    log.info('runs for download: %s', runs)
    log.info('sources: %s', source)

    cnt = 0
    for r_id in reversed(runs):
        msg = None
        subdir = '%d/%d' % (flow_id, r_id)
        for src in source:
            cnt2 = 0
            try:
                cnt2 = _download_file_or_dir(mc, minio_bucket, subdir, src, dest)
            except Exception as e:
                msg = 'problem with downloading %s: %s' % (src, str(e))
                break
            if cnt2 == 0:
                msg = 'problem with downloading %s: not found' % src
                break
            cnt += cnt2
        # no error so stop looking for files in other runs
        if msg is None:
            break

    if msg:
        log.error(msg)
        return 1, msg

    if cnt == 0:
        return 2, "cannot find files to download"

    return 0, ''


def run_artifacts(step, report_artifact=None):

    minio_addr = step['minio_addr']
    minio_addr = os.environ.get('KRAKEN_MINIO_ADDR', minio_addr)
    minio_bucket = step['minio_bucket']
    minio_access_key = step['minio_access_key']
    minio_secret_key = step['minio_secret_key']
    action = step.get('action', 'upload')
    cwd = step.get('cwd', None)
    flow_id = step['flow_id']
    run_id = step['run_id']

    source = step['source']
    dest = step['destination']
    if action == 'upload':
        if dest == '/':
            dest = ''
        rundir = os.path.join(str(flow_id), str(run_id))
    dest = os.path.normpath(dest)

    log.info('%s: source: %s, dest: %s', action, source, dest)

    if not isinstance(source, list):
        source = [source]

    mc = minio.Minio(minio_addr, access_key=minio_access_key, secret_key=minio_secret_key, secure=False)

    if action == 'download':
        status, msg = _download_all(mc, minio_bucket, flow_id, run_id, cwd, source, dest)
    else:
        status, msg = _upload_all(mc, minio_bucket, cwd, source, rundir, dest, report_artifact)

    return status, msg
