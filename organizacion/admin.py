from django.contrib import admin

from .models import Delegation, Position


@admin.register(Delegation)
class DelegationAdmin(admin.ModelAdmin):
    list_display = ("name", "scope", "status")
    list_filter = ("status",)
    search_fields = ("name", "scope")


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)
