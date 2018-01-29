from django.core.management.base import BaseCommand, CommandError
from custom_user.models import User, update_region

class Command(BaseCommand):
    help = 'Updates denormalized field "User.region"'

    def add_arguments(self, parser):
        parser.add_argument('user_id', nargs='*', type=int, help='ID of user. Updates all users if empty')

    def handle(self, *args, **options):
        if options['user_id']:
            updated = 0
            for user_id in options['user_id']:
                updated += update_region(User.objects.get(id=user_id))
        else:
            updated = update_region()
        print 'updated: %d' % updated
