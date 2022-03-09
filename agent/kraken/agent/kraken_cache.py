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
import io
import time
import json
import shutil
import logging
import tarfile

import minio

log = logging.getLogger(__name__)

def _upload():
    pass


class Pumper:
    def __init__(self, path):
        self.path = path
        self.blocks = []
        self.tar = None

        self.files = self._walk_files()
        self.files_cnt = 0

        self.t0 = time.time()

    def _walk_files(self):
        for dirpath, _, fnames in os.walk(self.path):
            for f in fnames:
                fp = os.path.join(dirpath, f)
                yield fp

    def _get_buf_size(self, size):
        if len(self.blocks) == 0:
            return b''

        bufs = []
        cur_size = 0
        while cur_size < size:
            if len(self.blocks) == 0:
                break
            b = self.blocks.pop(0)
            rest_size = size - cur_size

            b0 = b[:rest_size]
            bufs.append(b0)
            cur_size += len(b0)

            b1 = b[rest_size:]
            if b1:
                self.blocks.insert(0, b1)
        buf = b''.join(bufs)
        return buf

    def read(self, size):
        # read is used by minio to get next block and send it to minio server

        avail_size = sum([len(b) for b in self.blocks])
        while avail_size < size:
            try:
                fpath = next(self.files)
            except StopIteration:
                log.info('no more files, packed %d files', self.files_cnt)
                self.tar.close()
                break

            self.tar.add(fpath)
            self.files_cnt += 1

            t1 = time.time()
            if t1 - self.t0 > 10:
                self.t0 = t1
                log.info('added %d files', self.files_cnt)

            avail_size = sum([len(b) for b in self.blocks])

        return self._get_buf_size(size)

    def write(self, b):
        # write is used by tarfile to output next block of tarred and compressed content
        self.blocks.append(b)


def _save_to_cache(mc, cache_key, minio_bucket, dest_folder, paths):
    log.info('cache save: key: %s, paths: %s, bucket: %s, dest: %s', cache_key, paths, minio_bucket, dest_folder)

    meta = {}

    size = 5 * 1024 * 1024

    for pth in paths:
        pth = os.path.expandvars(pth)
        pth = os.path.expanduser(pth)
        if not os.path.exists(pth):
            log.error("path '%s' does not exists", pth)
            return 1, "path '%s' does not exists" % pth
        pumper = Pumper(pth)
        tar_name = '%s.tar.gz' % pth.strip('/').replace('/', '_')
        tar = tarfile.open(tar_name, 'w|gz', pumper, bufsize=size)
        pumper.tar = tar

        object_name = '%s/%s' % (dest_folder, tar_name)
        log.info('saving %s to %s', pth, object_name)

        meta[tar_name] = pth

        mc.put_object(minio_bucket, object_name, pumper, length=-1, part_size=size)

    data = json.dumps(meta)
    object_name = '%s/meta.json' % dest_folder
    mc.put_object(minio_bucket, object_name, io.BytesIO(bytes(data, 'utf-8')), len(data))
    log.info('saved meta %s', object_name)

    return 0, ''


def _restore_from_cache(mc, minio_bucket, minio_folders):
    for cache_key, folder in minio_folders.items():
        log.info('cache restore: key: %s, source: %s', cache_key, folder)
        objects = mc.list_objects(minio_bucket, folder + '/')
        runs = []
        for o in objects:
            run_id = o.object_name.strip('/').rsplit('/', 1)[1]
            runs.append(int(run_id))
        if len(runs) == 0:
            log.info('no cache for %s', cache_key)
            continue
        runs.sort()
        run_id = runs[-1]
        path = '%s/%d/meta.json' % (folder, run_id)
        resp = mc.get_object(minio_bucket, path)
        meta = json.loads(resp.data)
        log.info('meta %s', meta)
        for tgz, path in meta.items():
            src_pth = '%s/%d/%s' % (folder, run_id, tgz)
            log.info('restoring %s / %s -> %s', src_pth, tgz, path)
            resp = mc.get_object(minio_bucket, src_pth)
            tar = tarfile.open('a.tgz', 'r|gz', resp)
            if path[0] == '/':
                dest = '/'
            else:
                dest = '.'
            try:
                tar.extractall(dest)
            except Exception as e:
                log.error('problem with cache extraction: %s', str(e))
                # remove not fully extracted folder
                shutil.rmtree(path)
            finally:
                resp.close()
                resp.release_conn()

    return 0, ''

def run(step):
    minio_addr = step['minio_addr']
    minio_bucket = step['minio_bucket']
    minio_access_key = step['minio_access_key']
    minio_secret_key = step['minio_secret_key']
    job_id = step['job_id']
    action = step['action']

    mc = minio.Minio(minio_addr, access_key=minio_access_key, secret_key=minio_secret_key, secure=False)

    # check connection
    try:
        mc.bucket_exists(minio_bucket)
    except Exception as e:
        log.exception('problem with connecting to minio %s', minio_addr)
        msg = 'problem with connecting to minio %s: %s' % (minio_addr, str(e))
        return 1, msg

    if action == 'save':
        paths = step['paths']
        cache_key, minio_folder = step['minio_folder'].popitem()
        dest_folder = '%s/%s' % (minio_folder, job_id)
        status, msg = _save_to_cache(mc, cache_key, minio_bucket, dest_folder, paths)
    else:
        minio_folders = step['minio_folders']
        status, msg = _restore_from_cache(mc, minio_bucket, minio_folders)

    return status, msg
