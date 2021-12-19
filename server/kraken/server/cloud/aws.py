# Copyright 2021 The Kraken Authors
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

import logging

# AWS
import boto3

from ..models import get_setting


log = logging.getLogger(__name__)


# AWS EC2 ###################################################################

def check_aws_settings():
    access_key = get_setting('cloud', 'aws_access_key')
    if not access_key:
        return 'AWS access key is empty'
    if len(access_key) < 16:
        return 'AWS access key is too short'
    if len(access_key) > 128:
        return 'AWS access key is too long'

    secret_access_key = get_setting('cloud', 'aws_secret_access_key')
    if not secret_access_key:
        return 'AWS secret access key is empty'
    if len(secret_access_key) < 36:
        return 'AWS secret access key is too short'

    try:
        ec2 = boto3.client('ec2', region_name='us-east-1', aws_access_key_id=access_key, aws_secret_access_key=secret_access_key)
        ec2.describe_regions()
    except Exception as ex:
        return str(ex)

    return 'ok'


def login_to_aws():
    access_key = get_setting('cloud', 'aws_access_key')
    secret_access_key = get_setting('cloud', 'aws_secret_access_key')
    settings = ['access_key', 'secret_access_key']
    for s in settings:
        val = locals()[s]
        if not val:
            log.error('AWS %s is empty, please set it in global cloud settings', s)
            return None

    return dict(aws_access_key_id=access_key, aws_secret_access_key=secret_access_key)
