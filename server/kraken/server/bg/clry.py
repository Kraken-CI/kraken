import os
from celery import Celery

from .. import consts

REDIS_ADDR = os.environ.get('KRAKEN_REDIS_ADDR', consts.DEFAULT_REDIS_ADDR)

app = Celery('kraken', broker='redis://%s' % REDIS_ADDR, include=['kraken.server.bg.tasks'])
