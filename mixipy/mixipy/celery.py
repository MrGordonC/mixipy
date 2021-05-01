from __future__ import absolute_import, unicode_literals
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mixipy.settings')

# app = Celery('mixipyapp',
#              broker='amqp://',
#              backend='rpc://',
#              include=['mixipyapp.tasks'])
app = Celery('mixipy')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()
# lambda: settings.INSTALLED_APPS

# Optional configuration, see the application user guide.
app.conf.update(
    result_expires=3600,
)


@app.task(bind=True)
def debug_task(self):
    print('Request: {0!r}'.format(self.request))


if __name__ == '__main__':
    app.start()
