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

import minio

from . import consts


def get_minio_addr():
    minio_addr = os.environ.get('KRAKEN_MINIO_ADDR', consts.DEFAULT_MINIO_ADDR)
    access_key = os.environ['MINIO_ACCESS_KEY']
    secret_key = os.environ['MINIO_SECRET_KEY']
    return minio_addr, access_key, secret_key


def get_minio():
    minio_addr, access_key, secret_key = get_minio_addr()
    mc = minio.Minio(minio_addr, access_key=access_key, secret_key=secret_key, secure=False)
    return mc


def get_or_create_minio_bucket_for_artifacts(branch_id):
    bucket_name = '%08d' % branch_id

    mc = get_minio()
    found = mc.bucket_exists(bucket_name)
    if not found:
        mc.make_bucket(bucket_name)

    return bucket_name


def get_or_create_minio_bucket_for_cache(job, step):
    bucket_name = '%08d-cache' % job.run.flow.branch_id

    if 'key' in step:
        cache_keys = [step['key']]
    else:
        cache_keys = step['keys']
    folders = {}
    for key in cache_keys:
        fldr = '%d-%s/%s' % (job.run.stage_id,
                             job.name.replace(' ', '_'),
                             key)
        folders[key] = fldr

    mc = get_minio()
    found = mc.bucket_exists(bucket_name)
    if not found:
        mc.make_bucket(bucket_name)

    return bucket_name, folders


def get_or_create_minio_bucket_for_git(branch_id, repo_url):
    bucket_name = '%08d-git' % branch_id

    folder = repo_url.replace('/', '_').replace(':', '_').replace('.', '_')

    mc = get_minio()
    found = mc.bucket_exists(bucket_name)
    if not found:
        mc.make_bucket(bucket_name)

    return bucket_name, folder
