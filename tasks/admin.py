from django.contrib import admin

from .models import Task


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'category', 'priority', 'complexity', 'status', 'created_at', 'completed_at')
    list_filter = ('category', 'priority', 'complexity', 'status')
    search_fields = ('title', 'description')
