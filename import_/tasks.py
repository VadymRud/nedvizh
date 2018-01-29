# coding: utf-8

from task_queues import close_db, task
from models import ImportTask, ImportAdTask

import logging
import traceback

task_logger = logging.getLogger('task_queues')

@task(queue='import_')
@close_db
def perform_importtask(importtask_id):
    message = ''
    try:
        message = 'importtask #%d ' % importtask_id
        task = ImportTask.objects.get(id=importtask_id)
        task.perform()
    except:
        task_logger.debug(message + 'exception ' + traceback.format_exc(8).encode('utf-8'))
    else:
        task_logger.debug(message + 'ok')

@task(queue='import_')
@close_db
def perform_importadtask(importadtask_id):
    message = ''
    try:
        message = 'importadtask #%d ' % importadtask_id
        task = ImportAdTask.objects.get(id=importadtask_id)
        task.perform()
    except:
        task_logger.debug(message + 'exception ' + traceback.format_exc(8).encode('utf-8'))
    else:
        task_logger.debug(message + 'ok')

