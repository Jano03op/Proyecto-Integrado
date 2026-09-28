from django.contrib import admin
from django.utils import timezone

from .models import Commitment, CommitmentEvent


class CommitmentEventInline(admin.TabularInline):
    model = CommitmentEvent
    extra = 0
    can_delete = False
    readonly_fields = (
        "sequence",
        "previous_status",
        "next_status",
        "actor",
        "occurred_on",
        "occurred_at",
        "note",
    )

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Commitment)
class CommitmentAdmin(admin.ModelAdmin):
    actions = None
    list_display = (
        "id",
        "description",
        "delegation",
        "owner",
        "status",
        "due_on",
        "is_overdue_badge",
    )
    list_filter = ("status", "delegation")
    search_fields = (
        "description",
        "owner__display_name",
        "delegation__name",
        "territory_label",
        "requester",
    )
    autocomplete_fields = ("delegation", "owner")
    inlines = [CommitmentEventInline]

    @admin.display(description="Vencido", boolean=True)
    def is_overdue_badge(self, obj):
        return obj.is_overdue

    def get_inlines(self, request, obj):
        # Inlines are displayed on GET detail view for audit; they are not formset-editable.
        if obj is None or request.method == "POST":
            return []
        return super().get_inlines(request, obj)

    def get_form(self, request, obj=None, change=False, **kwargs):
        form_class = super().get_form(request, obj, change=change, **kwargs)

        class RequestAwareCommitmentForm(form_class):
            def clean(_self):
                cleaned_data = super().clean()
                if _self.instance:
                    _self.instance._current_actor = request.user
                    _self.instance._current_occurred_at = timezone.now()
                    _self.instance._current_note = cleaned_data.get("note", "")
                    if _self.instance.can_reopen_or_retrocede(request.user):
                        _self.instance._allow_backward = True
                return cleaned_data

        return RequestAwareCommitmentForm

    def save_model(self, request, obj, form, change):
        obj._current_actor = request.user
        obj._current_occurred_at = timezone.now()
        obj._current_note = form.cleaned_data.get("note", "")
        if obj.can_reopen_or_retrocede(request.user):
            obj._allow_backward = True
        super().save_model(request, obj, form, change)


@admin.register(CommitmentEvent)
class CommitmentEventAdmin(admin.ModelAdmin):
    actions = None
    list_display = (
        "id",
        "commitment",
        "sequence",
        "previous_status",
        "next_status",
        "actor",
        "occurred_on",
        "occurred_at",
    )
    list_filter = ("next_status", "previous_status")
    search_fields = ("commitment__description", "actor__username", "note")
    readonly_fields = (
        "commitment",
        "sequence",
        "previous_status",
        "next_status",
        "actor",
        "occurred_on",
        "occurred_at",
        "note",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
