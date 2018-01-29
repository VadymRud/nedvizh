# coding: utf-8
from django.core.files.storage import default_storage

# данный сигнал не срабатывает когда используется метод <object>.image.save()
# надо с этим что-то сделать
def post_save_clean_image_file(sender, instance, created, **kwargs):
    dirty_fields = instance.get_dirty_fields()
    if 'image' in dirty_fields:
        if dirty_fields['image']:
            default_storage.delete(dirty_fields['image'].name)

def post_delete_clean_image_file(sender, instance, **kwargs):
    if instance.image:
        default_storage.delete(instance.image.name)


