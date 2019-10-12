from celery import Celery

app = Celery('kraken', broker='redis://localhost//', include=['bg.tasks'])
