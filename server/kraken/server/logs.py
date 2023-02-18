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
from logging.handlers import DatagramHandler

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
    secrets_multi = []
    secrets_single = []

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

    def set_secrets(self, secrets):
        secrets_single = []
        secrets_multi = []
        for s in secrets:
            s = s.splitlines()
            if len(s) == 1:
                secrets_single.append(s[0])
            else:
                secrets_multi.append(s)
        secrets_single.sort(key=len, reverse=True)
        secrets_multi.sort(key=len, reverse=True)
        StructLogger.secrets_single = secrets_single
        StructLogger.secrets_multi = secrets_multi


logging.setLoggerClass(StructLogger)
root_logger = StructLogger('root', logging.WARNING)  # pylint: disable=invalid-name
logging.root = root_logger
logging.Logger.root = root_logger
logging.Logger.manager.root = root_logger


log = logging.getLogger(__name__)

g_clickhouse_handler = None
g_basic_logger_done = False
g_masking_handler = None


class MaskingLogRecord(logging.LogRecord):
    def __init__(self, *args, **kwargs):
        logging.LogRecord.__init__(self, *args, **kwargs)
        self._msg = None
        self._secrets = []

    def add_mask_secret(self, secret, where):
        self._secrets.append((secret, where))
        self._msg = None

    def _mask_secrets(self, msg):
        if not self._secrets:
            return msg

        for s, where in self._secrets:
            if where == 'start':
                msg2 = '******' + msg[len(s):]
            elif where == 'end':
                msg2 = msg[:-len(s)] + '******'
            else:  # middle
                msg2 = msg.replace(s, '******')

            msg = msg2

        return msg

    def getMessage(self):
        if self._msg:
            return self._msg
        msg = logging.LogRecord.getMessage(self)
        msg = self._mask_secrets(msg)
        self._msg = msg
        return self._msg


class MaskingHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self._buffer = []
        self._hanlders = {}

    def add_handler(self, name, handler):
        self._hanlders[name] = handler
        handler.setLevel(self.level)

    def remove_handler(self, name):
        if name in self._hanlders:
            del self._hanlders[name]

    def setLevel(self, level):
        super().setLevel(level)
        for handler in self._hanlders.values():
            handler.setLevel(level)

    def setFormatter(self, fmt):
        super().setFormatter(fmt)
        for handler in self._hanlders.values():
            handler.setFormatter(fmt)

    def flush(self):
        super().flush()
        for handler in self._hanlders.values():
            handler.flush()

    def close(self):
        super().close()
        for handler in self._hanlders.values():
            handler.close()

    def true_emit(self, record):
        for handler in self._hanlders.values():
            handler.emit(record)

    def emit(self, record):
        # if there are no secrets them emit the record now
        if not StructLogger.secrets_single and not StructLogger.secrets_multi:
            # if there are some buffered records then flush them now
            if self._buffer:
                for rec in self._buffer:
                    self.true_emit(rec)
                self._buffer = []
            self.true_emit(record)
            return

        # if there are multi line secrets then buffer records
        # and process them when the number of buffered records
        # is equal or greater then min number of lines of all secrets
        if StructLogger.secrets_multi:
            max_secrets_lines = len(StructLogger.secrets_multi[0])
            min_secrets_lines = len(StructLogger.secrets_multi[-1])

            self._buffer.append(record)

            if len(self._buffer) < min_secrets_lines:
                return

            matched = False
            s = None
            for s in StructLogger.secrets_multi:
                if len(s) > len(self._buffer):
                    continue

                # moving window over buffer if it is longer than secret
                for w in range(0, len(self._buffer) - len(s) + 1):

                    # match lines in secret and buffer window
                    for idx, line in enumerate(s):
                        rec = self._buffer[w + idx]
                        msg = rec.getMessage()

                        if idx == 0:
                            if not msg.endswith(line):
                                break
                        elif idx == len(s) - 1:
                            if not msg.startswith(line):
                                break
                            # matched whole secret, so perform masking
                            matched = True
                        elif msg != line:
                            #continue
                            break

                    if matched:
                        break

                if matched:
                    break

            if s and matched:
                # flush any lines before window
                for _ in range(0, w):
                    rec = self._buffer[0]
                    del self._buffer[0]
                    for ss in StructLogger.secrets_single:
                        rec.add_mask_secret(ss, 'middle')
                    self.true_emit(rec)

                # replace secret in affected lines
                for idx, line in enumerate(s):
                    rec = self._buffer[0]
                    del self._buffer[0]

                    if idx == 0:
                        rec.add_mask_secret(line, 'end')
                    elif idx == len(s) - 1:
                        rec.add_mask_secret(line, 'start')

                    # drop lines between first and last lines
                    if idx in [0, len(s) - 1]:
                        for ss in StructLogger.secrets_single:
                            rec.add_mask_secret(ss, 'middle')
                        self.true_emit(rec)

            elif len(self._buffer) == max_secrets_lines:
                # if number of buffered lines is equal to the number of the longest secret
                # then make a space for new line in a buffer
                rec = self._buffer[0]
                del self._buffer[0]
                for ss in StructLogger.secrets_single:
                    rec.add_mask_secret(ss, 'middle')
                self.true_emit(rec)

        # if there are only single line secrets then process them now
        if StructLogger.secrets_single and not StructLogger.secrets_multi:
            for ss in StructLogger.secrets_single:
                record.add_mask_secret(ss, 'middle')
            self.true_emit(record)

    def flush_log_entries(self):
        for rec in self._buffer:
            for ss in StructLogger.secrets_single:
                rec.add_mask_secret(ss, 'middle')
            self.true_emit(rec)

        self._buffer = []


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
            'processName', 'relativeCreated', 'thread', 'threadName', 'extra',
            # new to skip, not needed
            '_msg', '_secrets', 'stack_info')

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
            # '@version': '1',
            'message': msg,
            'host': self.host,
            'path': record.pathname,
            'lineno': record.lineno,
            # 'tags': self.tags,

            # Extra Fields
            'level': record.levelname,
            'logger_name': record.name,
        }

        # Add extra fields
        message.update(self.get_extra_fields(record))

        # If exception, add debug info
        # TODO: for now skipped
        # if record.exc_info:
        #     message.update(self.get_debug_fields(record))

        return self.serialize(message)


class ClickhouseHandler(DatagramHandler):
    """Python logging handler for Clickhouse. Sends events over UDP.
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
    global g_clickhouse_handler, g_basic_logger_done, g_masking_handler  # pylint: disable=global-statement

    logging.setLogRecordFactory(MaskingLogRecord)

    if not g_basic_logger_done:
        g_masking_handler = MaskingHandler()
        sh = logging.StreamHandler()
        g_masking_handler.add_handler('stream', sh)
        logging.basicConfig(format=consts.LOG_FMT, level=logging.INFO, handlers=[g_masking_handler])
        g_basic_logger_done = True

    l = logging.getLogger()

    if g_clickhouse_handler:
        g_masking_handler.remove_handler('clickhouse')
        g_clickhouse_handler = None

    ch_addr = os.environ.get('KRAKEN_CLICKHOUSE_ADDR', None)
    if not ch_addr:
        ch_addr = clickhouse_addr
    if not ch_addr:
        ch_addr = consts.DEFAULT_CLICKHOUSE_ADDR
    host, port = ch_addr.split(':')
    g_clickhouse_handler = ClickhouseHandler(host, int(port), fqdn=True)
    l.set_initial_ctx(service=service)
    g_masking_handler.add_handler('clickhouse', g_clickhouse_handler)
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
