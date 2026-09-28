from datetime import date
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone


class Commitment(models.Model):
    class Status(models.TextChoices):
        INGRESADO = "Ingresado", "Ingresado"
        PENDIENTE = "Pendiente", "Pendiente"
        EN_PROCESO = "En proceso", "En proceso"
        REALIZADO = "Realizado", "Realizado"

    delegation = models.ForeignKey(
        "organizacion.Delegation",
        on_delete=models.PROTECT,
        related_name="commitments",
    )
    owner = models.ForeignKey(
        "cuentas.StaffProfile",
        on_delete=models.PROTECT,
        related_name="commitments",
    )
    origin = models.CharField(max_length=255, blank=True)
    requester = models.CharField(max_length=255, blank=True)
    territory_label = models.CharField(max_length=255, blank=True)
    support_area = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    registered_on = models.DateField(default=date.today)
    due_on = models.DateField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.INGRESADO,
    )
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["due_on", "id"]
        indexes = [
            models.Index(
                fields=["delegation", "status", "due_on"],
                name="agenda_com_del_st_due_idx",
            ),
        ]

    @property
    def is_overdue(self) -> bool:
        return self.check_overdue()

    def check_overdue(self, today: date | None = None) -> bool:
        if self.status == self.Status.REALIZADO or not self.due_on:
            return False
        check_day = today if today is not None else date.today()
        return self.due_on < check_day

    # Template compatibility properties
    @property
    def territorio(self):
        return self.territory_label or (self.delegation.name if self.delegation else "")

    @property
    def responsable(self):
        return self.owner.display_name if self.owner else ""

    @property
    def solicitante(self):
        return self.requester

    @property
    def area_apoyo(self):
        return self.support_area

    @property
    def fecha_registro(self):
        return self.registered_on

    @property
    def fecha_compromiso(self):
        return self.due_on

    @property
    def descripcion(self):
        return self.description

    @property
    def observacion(self):
        return self.note

    @property
    def estado(self):
        return self.status

    @property
    def vencido(self):
        return self.is_overdue

    @property
    def historial(self):
        return self.events.all()

    def can_reopen_or_retrocede(self, user) -> bool:
        if not user or not user.is_authenticated:
            return False
        if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
            return True
        profile = getattr(user, "staff_profile", None)
        if not profile:
            return False
        pos_name = (profile.position.name if profile.position else "").lower()
        legacy_role = (profile.legacy_role or "").lower()
        if "coordinad" in pos_name or "coordinad" in legacy_role:
            return True
        if profile.delegation_id == self.delegation_id:
            manager_terms = ("encargad", "delegad", "director", "jefe", "gerente", "manager")
            if any(term in pos_name for term in manager_terms):
                return True
            if any(term in legacy_role for term in manager_terms):
                return True
        return False

    def clean(self):
        super().clean()
        if self.pk:
            orig = type(self).objects.filter(pk=self.pk).first()
            if orig:
                if orig.owner_id != self.owner_id:
                    raise ValidationError({"owner": "Commitment owner cannot be reassigned in this release."})
                if orig.status != self.status:
                    status_order = list(self.Status.values)
                    if orig.status not in status_order or self.status not in status_order:
                        raise ValidationError({"status": "Invalid status transition."})
                    old_idx = status_order.index(orig.status)
                    new_idx = status_order.index(self.status)
                    if new_idx > old_idx + 1:
                        raise ValidationError({
                            "status": f"Status cannot advance more than one step (from {orig.status} to {self.status})."
                        })
                    if new_idx < old_idx:
                        is_authorized = getattr(self, "_allow_backward", False)
                        actor = getattr(self, "_current_actor", None)
                        if not is_authorized and actor:
                            is_authorized = self.can_reopen_or_retrocede(actor)
                        if not is_authorized:
                            raise ValidationError({
                                "status": f"Backward transition or reopening from '{orig.status}' to '{self.status}' is allowed only to the delegated manager of this delegation or a coordinator."
                            })
                        note = getattr(self, "_current_note", "") or self.note
                        if not note or not note.strip():
                            raise ValidationError({
                                "note": "A reason is required for backward transitions or reopening."
                            })

    def transition_to(self, next_status, actor=None, note="", allow_backward=False, occurred_at=None):
        orig_status = self.status
        self.status = next_status
        self._current_actor = actor
        self._current_note = note
        self._allow_backward = allow_backward
        self._current_occurred_at = occurred_at if occurred_at is not None else (timezone.now() if actor else None)
        try:
            self.save()
        except Exception:
            self.status = orig_status
            raise

    def save(self, *args, **kwargs):
        self.full_clean()
        is_new = self.pk is None
        old_status = None
        if not is_new:
            old_status = type(self).objects.filter(pk=self.pk).values_list("status", flat=True).first()

        with transaction.atomic():
            super().save(*args, **kwargs)
            if is_new:
                if not self.events.exists():
                    actor = getattr(self, "_current_actor", None)
                    occurred_at = getattr(self, "_current_occurred_at", None)
                    note = getattr(self, "_current_note", "") or self.note or "Compromiso registrado en la agenda colectiva."
                    CommitmentEvent.objects.create(
                        commitment=self,
                        sequence=1,
                        previous_status=None,
                        next_status=self.status,
                        actor=actor,
                        occurred_on=self.registered_on or date.today(),
                        occurred_at=occurred_at,
                        note=note,
                    )
            elif old_status is not None and old_status != self.status:
                last_seq = self.events.aggregate(m=models.Max("sequence"))["m"] or 0
                actor = getattr(self, "_current_actor", None)
                occurred_at = getattr(self, "_current_occurred_at", timezone.now() if actor else None)
                note = getattr(self, "_current_note", "") or self.note or ""
                CommitmentEvent.objects.create(
                    commitment=self,
                    sequence=last_seq + 1,
                    previous_status=old_status,
                    next_status=self.status,
                    actor=actor,
                    occurred_on=date.today(),
                    occurred_at=occurred_at,
                    note=note,
                )

    @classmethod
    def board_completion_rate(cls, queryset=None, start_date=None, end_date=None):
        qs = queryset if queryset is not None else cls.objects.all()
        if start_date:
            qs = qs.filter(due_on__gte=start_date)
        if end_date:
            qs = qs.filter(due_on__lte=end_date)
        total = qs.count()
        if total == 0:
            return None
        realizado_count = qs.filter(status=cls.Status.REALIZADO).count()
        return (Decimal(realizado_count) * Decimal("100")) / Decimal(total)

    def __str__(self):
        desc = (self.description[:37] + "...") if len(self.description) > 40 else self.description
        return f"#{self.pk or '?'} {desc or 'Sin descripción'} ({self.status})"


class CommitmentEvent(models.Model):
    commitment = models.ForeignKey(
        Commitment,
        on_delete=models.CASCADE,
        related_name="events",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="commitment_events",
    )
    sequence = models.PositiveIntegerField()
    previous_status = models.CharField(
        max_length=20,
        choices=Commitment.Status.choices,
        null=True,
        blank=True,
    )
    next_status = models.CharField(
        max_length=20,
        choices=Commitment.Status.choices,
    )
    occurred_on = models.DateField(default=date.today)
    occurred_at = models.DateTimeField(null=True, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["sequence"]
        constraints = [
            models.UniqueConstraint(
                fields=["commitment", "sequence"],
                name="unique_commitment_event_sequence",
            ),
        ]

    # Template compatibility properties
    @property
    def estado_anterior(self):
        return self.previous_status

    @property
    def estado_nuevo(self):
        return self.next_status

    @property
    def fecha(self):
        return self.occurred_on

    @property
    def observacion(self):
        return self.note

    @property
    def autor(self):
        if not self.actor:
            return "Sistema"
        profile = getattr(self.actor, "staff_profile", None)
        return profile.display_name if profile else self.actor.username

    def clean(self):
        super().clean()
        if self.pk:
            raise ValidationError("Commitment events are append-only and cannot be modified.")
        if self.occurred_at is not None and not self.actor_id:
            raise ValidationError({"actor": "An authenticated actor is required on new events."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Commitment events are append-only and cannot be deleted.")

    def __str__(self):
        return f"Event {self.sequence} on Commitment #{self.commitment_id}: {self.previous_status} -> {self.next_status}"
