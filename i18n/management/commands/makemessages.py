# coding: utf-8

# для обновления po-файлов используется собственная команда update_po (см. комментарии в ее исходнике),
# поэтому команды makemessages из django и django-jinja нужно "заблокировать", чтобы случайно не испортить po-файлы

from django.core.management.commands.makemessages import Command as MakemessagesOriginalCommand

class Command(MakemessagesOriginalCommand):
    help = '''"makemessages" command is blocked in this project.
Use "update_po" command instead.
See comments in code of "update_po" command for details'''

    def handle(self, **options):
        print self.help

