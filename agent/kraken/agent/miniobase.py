# Copyright 2022 The Kraken Authors
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
from minio.lifecycleconfig import LifecycleConfig, Expiration, Rule
from minio.commonconfig import ENABLED, Filter
import urllib3
from urllib3.exceptions import MaxRetryError


from . import config


def get_minio(step):
    minio_addr = step['minio_addr']
    access_key = step['minio_access_key']
    secret_key = step['minio_secret_key']

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
    mc = minio.Minio(minio_addr, access_key=access_key, secret_key=secret_key, secure=False, http_client=http_client)

    # check connection
    mc.list_buckets()

    return mc


def download_tool(step, minio_path):
    m_bucket, m_path = minio_path[6:].split('/', 1)
    data_dir = config.get('data_dir')
    tools_dir = os.path.join(data_dir, 'tools')
    tool_zip = os.path.join(tools_dir, m_bucket, m_path, 'tool.zip')
    mc = get_minio(step)
    mc.fget_object(m_bucket, m_path, tool_zip)
    ver = m_path.split('/')[0]
    return tool_zip, m_bucket, ver
