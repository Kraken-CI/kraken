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

LOG_FMT = '%(asctime)s %(levelname)-4.4s p:%(process)5d %(module)8.8s:%(lineno)-5d %(message)s'

JOB_STATE_PREQUEUED = 1
JOB_STATE_QUEUED = 2
JOB_STATE_ASSIGNED = 3
JOB_STATE_EXECUTING_FINISHED = 4
JOB_STATE_COMPLETED = 5

JOB_STATES_NAME = {
    JOB_STATE_PREQUEUED: "prequeued",
    JOB_STATE_QUEUED: "queued",
    JOB_STATE_ASSIGNED: "assigned",
    JOB_STATE_EXECUTING_FINISHED: "executing-finished",
    JOB_STATE_COMPLETED: "completed",
}

JOB_CMPLT_ALL_OK = 0
JOB_CMPLT_JOB_TIMEOUT = 1
JOB_CMPLT_AGENT_ERROR_RETURNED = 2
JOB_CMPLT_AGENT_EXCEPTION = 3
JOB_CMPLT_MISSING_TOOL_IN_DB = 4
JOB_CMPLT_MISSING_TOOL_FILES = 5
JOB_CMPLT_STEP_TIMEOUT = 6
JOB_CMPLT_SERVER_TIMEOUT = 7
JOB_CMPLT_USER_CANCEL = 8
JOB_CMPLT_MISSING_AGENTS_GROUP = 9
JOB_CMPLT_NO_AGENTS = 10

STEP_STATUS_NOT_STARTED = 0
STEP_STATUS_IN_PROGRES = 1
STEP_STATUS_DONE = 2
STEP_STATUS_ERROR = 3

STEP_STATUS_TO_INT = {
    'not-started': STEP_STATUS_NOT_STARTED,
    'in-progress': STEP_STATUS_IN_PROGRES,
    'done': STEP_STATUS_DONE,
    'error': STEP_STATUS_ERROR
}
STEP_STATUS_NAME = {
    STEP_STATUS_NOT_STARTED: 'not-started',
    STEP_STATUS_IN_PROGRES: 'in-progress',
    STEP_STATUS_DONE: 'done',
    STEP_STATUS_ERROR: 'error'
}

TC_RESULT_NOT_RUN = 0
TC_RESULT_PASSED = 1
TC_RESULT_FAILED = 2
TC_RESULT_ERROR = 3
TC_RESULT_DISABLED = 4
TC_RESULT_UNSUPPORTED = 5
TC_RESULTS_NAME = {
    TC_RESULT_NOT_RUN: 'Not Run',
    TC_RESULT_PASSED: 'Passed',
    TC_RESULT_FAILED: 'Failed',
    TC_RESULT_ERROR: 'Error',
    TC_RESULT_DISABLED: 'Disabled',
    TC_RESULT_UNSUPPORTED: 'Unsupported',
}

RUN_STATE_IN_PROGRESS = 1
RUN_STATE_COMPLETED = 2
RUN_STATE_PROCESSED = 3
RUN_STATE_MANUAL = 4

RUN_STATES_NAME = {
    RUN_STATE_IN_PROGRESS: 'in-progress',
    RUN_STATE_COMPLETED: 'completed',
    RUN_STATE_PROCESSED: 'processed',
    RUN_STATE_MANUAL: 'manual',
}

FLOW_STATE_IN_PROGRESS = 1
FLOW_STATE_COMPLETED = 2

FLOW_STATES_NAME = {
    FLOW_STATE_IN_PROGRESS: 'in-progress',
    FLOW_STATE_COMPLETED: 'completed'
}

TC_RESULT_CHANGE_NO = 0
TC_RESULT_CHANGE_FIX = 1
TC_RESULT_CHANGE_REGR = 2
TC_RESULT_CHANGE_NEW = 3

NETWORK_TIMEOUT = 2  # minutes


DEFAULT_DB_URL = 'postgresql://kraken:kk123@localhost:5433/kraken'
DEFAULT_REDIS_ADDR = 'localhost'
DEFAULT_ELASTICSEARCH_URL = 'http://elastic:changeme@localhost:9200'
DEFAULT_LOGSTASH_PORT = '5959'
DEFAULT_LOGSTASH_ADDR = 'localhost:%s' % DEFAULT_LOGSTASH_PORT
DEFAULT_PLANNER_URL = 'http://localhost:7997/'
DEFAULT_SERVER_ADDR = 'localhost:8080'
DEFAULT_STORAGE_ADDR = 'localhost:2121'

ISSUE_TYPE_ERROR = 0
ISSUE_TYPE_WARNING = 1
ISSUE_TYPE_CONVENTION = 2
ISSUE_TYPE_REFACTOR = 3
ISSUE_TYPES_NAME = {
    ISSUE_TYPE_ERROR: 'error',
    ISSUE_TYPE_WARNING: 'warning',
    ISSUE_TYPE_CONVENTION: 'convention',
    ISSUE_TYPE_REFACTOR: 'refactor',
}
ISSUE_TYPES_CODE = {n: c for c, n in ISSUE_TYPES_NAME.items()}

SECRET_KIND_SSH_KEY = 0
SECRET_KIND_SIMPLE = 1
SECRET_KINDS_NAME = {
    SECRET_KIND_SSH_KEY: 'ssh-key',
    SECRET_KIND_SIMPLE: 'simple',
}


DEFAULT_RUN_TIMEOUT = 3 * 60 * 60  # 3 hours (in seconds)
DEFAULT_JOB_TIMEOUT = 5 * 60  # 5 minutes (in seconds)
AGENT_TIMEOUT = 5 * 60  # 5 minutes (in seconds)

DEFAULT_STORAGE_DIR = '/tmp/kraken_storage'


ARTIFACTS_SECTION_PRIVATE = 0
ARTIFACTS_SECTION_PUBLIC = 1
ARTIFACTS_SECTION_REPORT = 2


AGENT_DIR = '/opt/kraken'


AGENT_MSG_GET_JOB = 'get-job'
AGENT_MSG_STEP_RESULT = 'step-result'
AGENT_MSG_DISPATCH_TESTS = 'dispatch-tests'
AGENT_MSG_SYS_INFO = 'sys-info'
AGENT_MSG_KEEP_ALIVE = 'keep-alive'


BRANCH_SEQ_FLOW = 0
BRANCH_SEQ_CI_FLOW = 1
BRANCH_SEQ_DEV_FLOW = 2
BRANCH_SEQ_RUN = 3
BRANCH_SEQ_CI_RUN = 4
BRANCH_SEQ_DEV_RUN = 5
