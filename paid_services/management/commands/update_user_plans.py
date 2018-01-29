# coding: utf-8

from django.core.management.base import BaseCommand
from django.db import transaction as db_transaction

from paid_services.models import UserPlan

import datetime

class Command(BaseCommand):
    def handle(self, *args, **options):
        now = datetime.datetime.now()
        print 'start', now

        for user_plan in UserPlan.objects.filter(end__lte=now, is_active=True).prefetch_related('user'):
            with db_transaction.atomic():
                print '  user #%d: ' % user_plan.user.id

                user_plan.is_active = False
                user_plan.save()

                next_user_plan = user_plan.user.user_plans.filter(start__lt=now, end__gt=now, is_active=False).order_by('start').first()
                if next_user_plan:
                    next_user_plan.is_active = True
                    next_user_plan.save()
                    next_user_plan.user.activate_ads()
                    print '    #%d activated' % next_user_plan.id
                else:
                    user_plan.user.deactivate_ads()
                    print '    #%d deactivated' % user_plan.id

        print 'end'
        print

