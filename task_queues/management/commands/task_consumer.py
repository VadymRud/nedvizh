# coding: utf-8

from django.conf import settings
from django.core.management.base import CommandError

from huey.consumer import Consumer
from huey.consumer_options import ConsumerConfig
from huey.contrib.djhuey.management.commands import run_huey

from task_queues import HUEYS

# пропатченная команда run_huey из huey.contrib.djhuey,
# расширенная для работы с несколькими очередями (huey.contrib.djhuey умеет только с одной)
class Command(run_huey.Command):
    help = 'runs consumer for task queue'

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)
        parser.add_argument('queue', choices=HUEYS.keys(), help='name of queue')

    # скопировано из run_huey.Command.handle() и изменено
    def handle(self, *args, **options):
        # добавлено
        if settings.MESTO_TASK_QUEUES_SYNCRONOUS_EXECUTION:
            raise CommandError('If you want to use queues, set MESTO_TASK_QUEUES_SYNCRONOUS_EXECUTION setting to False')

        # from huey.contrib.djhuey import HUEY

        # добавлено
        queue = options.pop('queue')

        consumer_options = {}
        # if isinstance(settings.HUEY, dict):
            # consumer_options.update(settings.HUEY.get('consumer', {}))

        for key, value in options.items():
            if value is not None:
                consumer_options[key] = value

        consumer_options.setdefault('verbose',
                                    consumer_options.pop('huey_verbose', None))
        self.autodiscover()

        config = ConsumerConfig(**consumer_options)
        config.validate()
        config.setup_logger()

        # consumer = Consumer(HUEY, **config.values)
        consumer = Consumer(HUEYS[queue], **config.values)
        consumer.run()

