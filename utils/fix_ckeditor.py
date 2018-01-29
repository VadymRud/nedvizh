# coding: utf-8

# подмена оригинальных имен файлов на случайные - ранее использовалось для обхода ошибок
# при сохранении файлов с кириллическими символами в именах, в версии 5.0.3 используется
# slugify из django, вырезающий не-ASCII символы - не самое надежное и полноценное
# решение, поэтому патч оставлен

from ckeditor_uploader.views import ImageUploadView, csrf_exempt

import uuid
import os

class FixedFileNamesImageUploadView(ImageUploadView):
    def post(self, request, **kwargs):
        uploaded_file = request.FILES['upload']
        uploaded_file.name = '%s%s' % (uuid.uuid4().hex[:8], os.path.splitext(uploaded_file.name)[-1])
        return super(FixedFileNamesImageUploadView, self).post(request, **kwargs)

upload = csrf_exempt(FixedFileNamesImageUploadView.as_view())

