# coding: utf-8
from django.utils.encoding import filepath_to_uri
from django.core.files import storage
from django.core.files.storage import default_storage
from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage
from django.core.files.base import ContentFile

class StaticS3Boto3Storage(S3Boto3Storage):
    location = 'static'

def overwrite(name, content):
    default_storage.delete(name)
    default_storage.save(name, content)

