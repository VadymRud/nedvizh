# coding: utf-8
from django.conf import settings
from django.db import connection

from huey import RedisHuey

from functools import wraps

# в huey.contrib.djhuey используется только одна очередь (переменная "HUEY"), а нам нужно несколько

HUEYS = {}

for queue in settings.MESTO_TASK_QUEUES:
    HUEYS[queue] = RedisHuey(
        queue,
        always_eager=settings.MESTO_TASK_QUEUES_SYNCRONOUS_EXECUTION,
        **settings.MESTO_TASK_QUEUES_REDIS_CONNECTION
    )

# пропатченный декоратор из huey.contrib.djhuey
# для декорирования функций задач, в которых используется Django ORM
def close_db(fn):
    """Decorator to be used with tasks that may operate on the database."""
    @wraps(fn)
    def inner(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        finally:
            # if not HUEY.always_eager:
            if not settings.MESTO_TASK_QUEUES_SYNCRONOUS_EXECUTION:
                connection.close()
    return inner

def task(*args, **kwargs):
    def decorator(fn):
        return HUEYS[kwargs.pop('queue')].task(*args, **kwargs)(fn)
    return decorator

