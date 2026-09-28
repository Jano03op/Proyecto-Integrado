from django.contrib import admin

from .models import StaffProfile


@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):
    list_display = ("display_name", "user", "delegation", "position")
    list_filter = ("delegation", "position")
    search_fields = ("display_name", "user__username", "legacy_role")
    autocomplete_fields = ("delegation", "position", "user")
