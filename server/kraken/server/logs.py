import os
import json
import socket
import logging
import datetime
import traceback
from logging.handlers import DatagramHandler, SocketHandler

from . import consts


class StructLogger(logging.Logger):
    initial_context = {}
    context = {}

    def _log(self, level, msg, args, exc_info=None, extra=None, stack_info=False, **kwargs):
        if not extra:
            extra = {}
        extra.update(StructLogger.context)
        extra.update(kwargs)
        super()._log(level, msg, args, exc_info, extra, stack_info)

    def set_initial_ctx(self, **kwargs):
        if StructLogger.initial_context == {}:
            StructLogger.initial_context.update(kwargs)
            self.reset_ctx()

    def set_ctx(self, **kwargs):
        StructLogger.context.update(kwargs)

    def reset_ctx(self):
        StructLogger.context = StructLogger.initial_context.copy()


logging.setLoggerClass(StructLogger)
root_logger = StructLogger('root', logging.WARNING)
logging.root = root_logger
logging.Logger.root = root_logger
logging.Logger.manager.root = root_logger


class LogstashFormatter(logging.Formatter):
    def __init__(self, message_type='Logstash', tags=None, fqdn=False):
        self.message_type = message_type
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
            'tags': self.tags,
            'type': self.message_type,

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



class LogstashHandler(DatagramHandler, SocketHandler):
    """Python logging handler for Logstash. Sends events over TCP.
    :param host: The host of the logstash server.
    :param port: The port of the logstash server (default 5959).
    :param message_type: The type of the message (default logstash).
    :param fqdn; Indicates whether to show fully qualified domain name or not (default False).
    :param tags: list of tags for a logger (default is None).
    """

    def __init__(self, host, port=5959, message_type='logstash', tags=None, fqdn=False):
        super(LogstashHandler, self).__init__(host, port)
        self.formatter = LogstashFormatter(message_type, tags, fqdn)

    def makePickle(self, record):
        return self.formatter.format(record)


def setup_logging(service, logstash_server='logstash'):
    logging.basicConfig(format=consts.LOG_FMT, level=logging.INFO)

    logstash_server = os.environ.get('KRAKEN_LOGSTASH', 'localhost')
    g_logstash_handler = LogstashHandler(logstash_server, 5959, fqdn=True)
    l = logging.getLogger()
    l.set_initial_ctx(service=service)
    l.addHandler(g_logstash_handler)
