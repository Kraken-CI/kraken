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
import logging

import minio
from minio.lifecycleconfig import LifecycleConfig, Expiration, Rule
from minio.commonconfig import ENABLED, Filter
from minio.error import S3Error
import urllib3
from urllib3.exceptions import MaxRetryError

from . import consts
from .models import get_setting


log = logging.getLogger(__name__)


def get_minio_addr():
    minio_addr = get_setting('general', 'minio_addr')
    if not minio_addr:
        minio_addr = os.environ.get('KRAKEN_MINIO_ADDR', consts.DEFAULT_MINIO_ADDR)
    root_user = os.environ['MINIO_ROOT_USER']
    root_password = os.environ['MINIO_ROOT_PASSWORD']
    return minio_addr, root_user, root_password


def get_minio():
    minio_addr, root_user, root_password = get_minio_addr()
    http_client = urllib3.PoolManager(
        timeout=5,
        maxsize=10,
        cert_reqs='CERT_REQUIRED',
        retries=urllib3.Retry(
            total=3,
            backoff_factor=0.2,
            status_forcelist=[500, 502, 503, 504]
        )
    )
    mc = minio.Minio(minio_addr, access_key=root_user, secret_key=root_password, secure=False, http_client=http_client)
    return mc


def check_connection():
    minio_addr, root_user, root_password = get_minio_addr()
    http_client = urllib3.PoolManager(
        timeout=1,
        maxsize=10,
        cert_reqs='CERT_REQUIRED',
        retries=urllib3.Retry(
            total=2,
            backoff_factor=0.2,
            status_forcelist=[500, 502, 503, 504]
        )
    )
    mc = minio.Minio(minio_addr, access_key=root_user, secret_key=root_password, secure=False, http_client=http_client)
    try:
        mc.list_buckets()
    except MaxRetryError as ex:
        log.error('minio connection error: %s', ex)
        return False
    except S3Error as ex:
        log.error('minio connection error: %s', ex)
        return False

    return True


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
        # create bucket
        mc.make_bucket(bucket_name)

        # set retention policy - delete files after 10 days
        cfg = LifecycleConfig(
            [
                Rule(
                    ENABLED,
                    rule_filter=Filter(prefix=""),
                    rule_id="rule-10-days",
                    expiration=Expiration(days=10),
                ),
            ],
        )
        mc.set_bucket_lifecycle(bucket_name, cfg)

    return bucket_name, folders


def get_or_create_minio_bucket_for_git(repo_url, branch_id=None, tool_id=None):
    if branch_id:
        bucket_name = '%08d-git' % branch_id
    elif tool_id:
        bucket_name = 'tool-%08d-git' % tool_id
    else:
        raise Exception('Branch or Tool id should not be None')

    folder = repo_url.replace('/', '_').replace(':', '_').replace('.', '_')

    mc = get_minio()
    found = mc.bucket_exists(bucket_name)
    if not found:
        mc.make_bucket(bucket_name)

    return bucket_name, folder


def get_or_create_minio_bucket_for_tool(tool_id):
    bucket_name = 'tool-%d' % tool_id

    mc = get_minio()
    found = mc.bucket_exists(bucket_name)
    if not found:
        mc.make_bucket(bucket_name)

    return bucket_name, mc
