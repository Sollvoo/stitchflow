from django.contrib import admin
from .models import ConversionJob


@admin.register(ConversionJob)
class ConversionJobAdmin(admin.ModelAdmin):
    list_display = ['id', 'source_format', 'status', 'created_at', 'updated_at']
    list_filter = ['status', 'source_format']
    readonly_fields = ['id', 'created_at', 'updated_at']
    search_fields = ['id']
    ordering = ['-created_at']
