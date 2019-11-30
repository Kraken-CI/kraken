import os
from celery import Celery

REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')

app = Celery('kraken', broker='redis://%s//' % REDIS_HOST, include=['kraken.server.bg.tasks'])
