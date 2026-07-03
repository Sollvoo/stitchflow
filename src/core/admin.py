from django.contrib import admin

from .models import WaitlistEmail


@admin.register(WaitlistEmail)
class WaitlistEmailAdmin(admin.ModelAdmin):
    list_display = ('email', 'created_at')
    search_fields = ('email',)
    readonly_fields = ('created_at',)
