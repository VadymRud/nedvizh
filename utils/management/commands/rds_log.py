from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

import boto.rds2
import sqlparse

from collections import defaultdict
import re
import os

log_entry_prefix_re = re.compile(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} .*?:.*?:.*?@.*?:.*?:LOG: ')
log_entry_extract_re = re.compile(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} .*?:.*?:.*?@.*?:.*?:LOG:  duration: (?P<duration>.*?) ms  statement: (?P<statement>.*?)$')

sort_functions = ('avg', 'min', 'max', 'count')
cache_dir = os.path.join(settings.VAR_ROOT, 'rds_log_cache')

def conver_to_pattern(token):
    token_type = str(token.ttype)
    if token_type in ('Token.Literal.Number.Integer', 'Token.Literal.String.Single'):
        token.value = '?'
    if isinstance(token, sqlparse.sql.IdentifierList):
        if len(token.tokens) > 1:
            token.tokens = [sqlparse.sql.Token('Token.Literal', '?')]
    if token.is_group():
        for child_token in token.tokens:
            conver_to_pattern(child_token)

command_actions = ['clear', 'download', 'collect_stats']

class Command(BaseCommand):
    help = 'Shows RDS slow log stats'

    def add_arguments(self, parser):
        parser.add_argument('--actions', dest='actions', nargs='+', type=str, choices=command_actions)
        parser.add_argument('--files', dest='files', type=int, default=1, help='Number of files to download (default = 1)')
        parser.add_argument('--sort', dest='sort', choices=sort_functions, default=sort_functions[0], help='Sorting function')
        parser.add_argument('--show-source-data', dest='show_source_data', action='store_true', help='Show source data in output')

    def handle(self, *args, **options):
        actions = options['actions'] or command_actions

        if 'clear' in actions:
            for name in os.listdir(cache_dir):
                path = os.path.join(cache_dir, name)
                os.remove(path)

        if 'download' in actions:
            conn = boto.rds2.connect_to_region(
                'eu-west-1',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
            )

            db_instance_id = 'mestoua-postgresql'

            response = conn.describe_db_log_files(db_instance_id)
            logs = response['DescribeDBLogFilesResponse']['DescribeDBLogFilesResult']['DescribeDBLogFiles']

            for log in logs[-options['files']:]:
                print log['LogFileName']

                marker = None
                data = ''

                while True:
                    response = conn.download_db_log_file_portion(db_instance_id, log['LogFileName'], marker)
                    result = response['DownloadDBLogFilePortionResponse']['DownloadDBLogFilePortionResult']
                    data += result['LogFileData']
                    if result['AdditionalDataPending']:
                        marker = result['Marker']
                    else:
                        break

                cached_file_path = os.path.join(cache_dir, log['LogFileName'].replace('/', '_'))

                with open(cached_file_path, 'w') as f:
                    f.write(data)

        if 'collect_stats' in actions:
            source_groupped_by_template = defaultdict(list)

            for name in os.listdir(cache_dir):
                path = os.path.join(cache_dir, name)
                if os.path.isfile(path):
                    print path

                    with open(path, 'r') as f:
                        data = f.read()

                    original_lines = data.split('\n')
                    fixed_lines = []

                    while original_lines:
                        line = original_lines.pop(0)
                        if log_entry_prefix_re.match(line) is None:
                            fixed_lines[-1] = u'%s\\n%s' % (fixed_lines[-1], line)
                        else:
                            fixed_lines.append(line)

                    errors = []
                    for line in fixed_lines:
                        match = log_entry_extract_re.match(line)
                        if match is None:
                            errors.append(line)
                        else:
                            statement = match.group('statement')
                            duration = float(match.group('duration'))

                            parsed_statement = sqlparse.parse(statement)
                            if len(parsed_statement) != 1:
                                errors.append(line)
                            else:
                                for token in parsed_statement:
                                    conver_to_pattern(token)
                                template = unicode(parsed_statement[0])
                                source_groupped_by_template[template].append((statement, duration))

                    for error in errors:
                        print '  bad line: "%s"' % error

            stats = []

            for template, source in source_groupped_by_template.iteritems():
                durations = [duration for statement, duration in source]
                stat_item = {
                    'statement': template,
                    'count': len(durations),
                    'min': min(durations),
                    'max': max(durations),
                    'avg': sum(durations) / float(len(durations)),
                }
                if options['show_source_data']:
                    stat_item['source'] = source

                stats.append(stat_item)

            stats.sort(key=lambda obj: obj[options['sort']], reverse=True)

            if stats:
                print
                print 'stats:'

                format_string = []

                functions = list(sort_functions)
                functions.remove(options['sort'])
                functions.insert(0, options['sort'])

                for func in functions:
                    if func == 'count':
                        type_letter = 'd'
                    else:
                        type_letter = '.3f'
                    format_string.append(u'%s=%%(%s)%s' % (func, func, type_letter))
                format_string.append(u' %(statement)s')

                for stat_item in stats:
                    print u' '.join(format_string) % stat_item

                    if options['show_source_data']:
                        stat_item['source'].sort(key=lambda obj: obj[1], reverse=True)
                        for statement, duration in stat_item['source']:
                            print '  %.3f  %s' % (duration, statement)

