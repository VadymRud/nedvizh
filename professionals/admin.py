from django.contrib import admin
from professionals.models import Review, Reply

class ReplyInline(admin.TabularInline):
    model = Reply
    raw_id_fields = ('review', 'user')
    extra = 0

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('id', 'created', 'user', 'agency', 'rating')
    raw_id_fields = ('user', 'agency')
    inlines = [ReplyInline]
