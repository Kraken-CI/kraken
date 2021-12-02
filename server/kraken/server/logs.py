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
import json
import socket
import logging
import datetime
import traceback
from logging.handlers import DatagramHandler, SocketHandler

# try to import sentry SDK
try:
    import sentry_sdk
except ImportError:
    sentry_sdk = None
try:
    from sentry_sdk.integrations.flask import FlaskIntegration
except ImportError:
    FlaskIntegration = None

from . import consts


class StructLogger(logging.Logger):
    initial_context = {}
    context = {}

    def _log(self, level, msg, args, exc_info=None, extra=None, stack_info=False, **kwargs):  # pylint: disable=arguments-differ
        if not extra:
            extra = {}
        extra.update(StructLogger.context)
        extra.update(kwargs)
        extra = {k: v for k, v in extra.items() if v is not None}
        super()._log(level, msg, args, exc_info, extra, stack_info)

    def set_initial_ctx(self, **kwargs):
        if not StructLogger.initial_context:
            StructLogger.initial_context.update(kwargs)
            self.reset_ctx()

    def set_ctx(self, **kwargs):
        StructLogger.context.update(kwargs)

    def reset_ctx(self):
        StructLogger.context = StructLogger.initial_context.copy()


logging.setLoggerClass(StructLogger)
root_logger = StructLogger('root', logging.WARNING)  # pylint: disable=invalid-name
logging.root = root_logger
logging.Logger.root = root_logger
logging.Logger.manager.root = root_logger


log = logging.getLogger(__name__)

g_clickhouse_handler = None
g_basic_logger_done = False


class ClickhouseFormatter(logging.Formatter):
    def __init__(self, tags=None, fqdn=False):
        super().__init__()
        self.tags = tags if tags is not None else []

        if fqdn:
            self.host = socket.getfqdn()
        else:
            self.host = socket.gethostname()

    def get_extra_fields(self, record):
        # The list contains all the attributes listed in
        # http://docs.python.org/library/logging.html#logrecord-attributes
        skip_list = (
            'args', 'asctime', 'created', 'exc_info', 'exc_text', 'filename',
            'funcName', 'id', 'levelname', 'levelno', 'lineno', 'module',
            'msecs', 'msecs', 'message', 'msg', 'name', 'pathname', 'process',
            'processName', 'relativeCreated', 'thread', 'threadName', 'extra')

        easy_types = (str, bool, dict, float, int, list, type(None))

        fields = {}

        for key, value in record.__dict__.items():
            if key not in skip_list:
                if isinstance(value, easy_types):
                    fields[key] = value
                else:
                    fields[key] = repr(value)

        if hasattr(record, 'extra'):
            for key, value in record.extra:
                if isinstance(value, easy_types):
                    fields[key] = value
                else:
                    fields[key] = repr(value)

        return fields

    def get_debug_fields(self, record):
        fields = {
            'stack_trace': self.format_exception(record.exc_info),
            'lineno': record.lineno,
            'process': record.process,
            'thread_name': record.threadName,
        }

        fields['funcName'] = record.funcName
        fields['processName'] = record.processName

        return fields

    @classmethod
    def format_source(cls, message_type, host, path):
        return "%s://%s/%s" % (message_type, host, path)

    @classmethod
    def format_timestamp(cls, time):
        tstamp = datetime.datetime.utcfromtimestamp(time)
        return tstamp.isoformat() + "Z"

    @classmethod
    def format_exception(cls, exc_info):
        return ''.join(traceback.format_exception(*exc_info)) if exc_info else ''

    @classmethod
    def serialize(cls, message):
        return bytes(json.dumps(message), 'utf-8')

    def format(self, record):
        msg = record.getMessage()
        if record.exc_info:
            for l in self.format_exception(record.exc_info).splitlines():
                msg += '\n' + l.rstrip()

        # Create message dict
        message = {
            '@timestamp': self.format_timestamp(record.created),
            '@version': '1',
            'message': msg,
            'host': self.host,
            'path': record.pathname,
            'lineno': record.lineno,
            'tags': self.tags,

            # Extra Fields
            'level': record.levelname,
            'logger_name': record.name,
        }

        # Add extra fields
        message.update(self.get_extra_fields(record))

        # If exception, add debug info
        if record.exc_info:
            message.update(self.get_debug_fields(record))

        return self.serialize(message)


class ClickhouseHandler(DatagramHandler, SocketHandler):
    """Python logging handler for Clickhouse. Sends events over TCP.
    :param host: The host of the Clickhouse server.
    :param port: The port of the Clickhouse server (default 9001).
    :param fqdn; Indicates whether to show fully qualified domain name or not (default False).
    :param tags: list of tags for a logger (default is None).
    """

    def __init__(self, host, port=9001, tags=None, fqdn=False):
        super().__init__(host, port)
        self.formatter = ClickhouseFormatter(tags, fqdn)

    def makePickle(self, record):
        return self.formatter.format(record)


def setup_logging(service, clickhouse_addr=None):
    global g_clickhouse_handler, g_basic_logger_done  # pylint: disable=global-statement

    if not g_basic_logger_done:
        logging.basicConfig(format=consts.LOG_FMT, level=logging.INFO)
        g_basic_logger_done = True

    l = logging.getLogger()

    if g_clickhouse_handler:
        l.removeHandler(g_clickhouse_handler)
        g_clickhouse_handler = None

    ch_addr = os.environ.get('KRAKEN_CLICKHOUSE_ADDR', None)
    if not ch_addr:
        ch_addr = clickhouse_addr
    if not ch_addr:
        ch_addr = consts.DEFAULT_CLICKHOUSE_ADDR
    host, port = ch_addr.split(':')
    g_clickhouse_handler = ClickhouseHandler(host, int(port), fqdn=True)
    l.set_initial_ctx(service=service)
    l.addHandler(g_clickhouse_handler)
    log.info('setup logging on %s to clickhouse: %s', service, ch_addr)


def setup_sentry(sentry_url):
    if not sentry_url or not sentry_sdk:
        return

    if FlaskIntegration:
        sentry_sdk.init(
            dsn=sentry_url,
            integrations=[FlaskIntegration()])
    else:
        sentry_sdk.init(
            dsn=sentry_url)

    log.info('sentry setup, DSN: %s...%s', sentry_url[:15], sentry_url[-5:])
