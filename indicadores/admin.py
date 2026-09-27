from django.contrib import admin

from .models import MetricItem, Period, StaffTarget


@admin.register(Period)
class PeriodAdmin(admin.ModelAdmin):
    actions = None  # Bulk deletion bypasses instance-level closed-period checks.
    list_display = ("starts_on", "ends_on", "status")
    list_filter = ("status",)
    search_fields = ("starts_on", "ends_on")

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj) and (
            obj is None or obj.status != Period.Status.CLOSED
        )

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and (
            obj is None or obj.status != Period.Status.CLOSED
        )


@admin.register(MetricItem)
class MetricItemAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(StaffTarget)
class StaffTargetAdmin(admin.ModelAdmin):
    actions = None  # Bulk deletion bypasses instance-level closed-period checks.
    list_display = ("staff", "period", "item", "goal", "weight_percent", "legacy_progress")
    list_filter = ("period", "item")
    search_fields = ("staff__display_name", "item__name")

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj) and (
            obj is None or obj.period.status != Period.Status.CLOSED
        )

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and (
            obj is None or obj.period.status != Period.Status.CLOSED
        )
