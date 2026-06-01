import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'stitchflow.settings')

app = Celery('stitchflow')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
