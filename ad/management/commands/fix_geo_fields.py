from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import connection

fix_geodjango_sql = '''
    UPDATE ad_region SET centroid = ST_SetSRID(ST_Point(coords_x, coords_y), 4326) WHERE coords_x IS NOT NULL AND coords_y IS NOT NULL AND centroid IS NULL;
    UPDATE ad_region SET boundary = ST_SetSRID(
        ST_Envelope(
            ST_GeomFromText(
                'LINESTRING(' || replace(bounded_by_coords, ';', ',') || ')'
            )
        ),
        4326
    ) WHERE bounded_by_coords > '' AND boundary IS NULL;
    UPDATE ad_ad SET point = ST_SetSRID(ST_Point(coords_x, coords_y), 4326) WHERE coords_x IS NOT NULL AND coords_y IS NOT NULL AND point IS NULL;
    UPDATE ad_subwaystation SET point = ST_SetSRID(ST_Point(coords_x, coords_y), 4326) WHERE coords_x IS NOT NULL AND coords_y IS NOT NULL AND point IS NULL;
'''

fix_coords_sql = '''
    UPDATE ad_region SET coords_x = ST_X(centroid), coords_y = ST_Y(centroid) WHERE centroid IS NOT NULL AND coords_x IS NULL AND coords_y IS NULL;
    UPDATE ad_region SET bounded_by_coords =
        ST_XMin(boundary)::text || ' ' || ST_YMin(boundary)::text || ';' || ST_XMax(boundary)::text || ' ' || ST_YMax(boundary)::text
    WHERE boundary IS NOT NULL AND (bounded_by_coords IS NULL OR bounded_by_coords = '');
    UPDATE ad_ad SET coords_x = ST_X(point), coords_y = ST_Y(point) WHERE point IS NOT NULL AND coords_x IS NULL AND coords_y IS NULL;
    UPDATE ad_subwaystation SET coords_x = ST_X(point), coords_y = ST_Y(point) WHERE point IS NOT NULL AND coords_x IS NULL AND coords_y IS NULL;
'''

class Command(BaseCommand):
    help = 'Fixes geo fields regarding settings.MESTO_USE_GEODJANGO'

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            if settings.MESTO_USE_GEODJANGO:
                cursor.execute(fix_geodjango_sql)
            else:
                cursor.execute(fix_coords_sql)

