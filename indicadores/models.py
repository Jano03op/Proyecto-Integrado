from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class Period(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        CLOSED = "closed", "Closed"

    starts_on = models.DateField()
    ends_on = models.DateField()
    status = models.CharField(max_length=6, choices=Status.choices, default=Status.DRAFT)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(starts_on__lte=models.F("ends_on")),
                name="indicator_period_dates_ordered",
            ),
        ]
        ordering = ["starts_on"]

    @property
    def total_days(self):
        return (self.ends_on - self.starts_on).days + 1

    def elapsed_days(self, today: date):
        return min(max((today - self.starts_on).days + 1, 0), self.total_days)

    def clean(self):
        super().clean()
        if self.pk and type(self).objects.filter(pk=self.pk, status=self.Status.CLOSED).exists():
            raise ValidationError("Closed periods cannot be changed or reopened.")
        if isinstance(self.starts_on, date) and isinstance(self.ends_on, date):
            if self.starts_on > self.ends_on:
                raise ValidationError({"ends_on": "End must not precede start."})
            if type(self).objects.exclude(pk=self.pk).filter(
                starts_on__lte=self.ends_on, ends_on__gte=self.starts_on
            ).exists():
                raise ValidationError("Periods cannot overlap, including their endpoints.")
        if self.status == self.Status.ACTIVE and type(self).objects.exclude(pk=self.pk).filter(
            status=self.Status.ACTIVE
        ).exists():
            raise ValidationError("Only one period may be active.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk, status=self.Status.CLOSED).exists():
            raise ValidationError("Closed periods cannot be deleted.")
        return super().delete(*args, **kwargs)

    def __str__(self):
        return f"{self.starts_on} – {self.ends_on} ({self.get_status_display()})"


class MetricItem(models.Model):
    name = models.CharField(max_length=150, unique=True)

    def __str__(self):
        return self.name


class StaffTarget(models.Model):
    staff = models.ForeignKey(
        "cuentas.StaffProfile", on_delete=models.PROTECT, related_name="targets"
    )
    period = models.ForeignKey(Period, on_delete=models.PROTECT, related_name="targets")
    item = models.ForeignKey(MetricItem, on_delete=models.PROTECT, related_name="targets")
    goal = models.DecimalField(max_digits=12, decimal_places=2)
    weight_percent = models.DecimalField(max_digits=5, decimal_places=2)
    legacy_progress = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Provisional imported progress; not evidence-verified.",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["staff", "period", "item"], name="unique_staff_period_item"),
            models.CheckConstraint(condition=Q(goal__gt=0), name="target_goal_positive"),
            models.CheckConstraint(
                condition=Q(weight_percent__gte=0) & Q(weight_percent__lte=100),
                name="target_weight_range",
            ),
            models.CheckConstraint(
                condition=Q(legacy_progress__isnull=True) | Q(legacy_progress__gte=0),
                name="target_legacy_progress_nonnegative",
            ),
        ]

    @classmethod
    def weights_ready(cls, staff, period):
        """Eligibility only; this does not calculate or verify a score."""
        weights = cls.objects.filter(staff=staff, period=period).values_list(
            "weight_percent", flat=True
        )
        return bool(weights) and sum(weights, Decimal("0")) == Decimal("100")

    @property
    def nombre(self):
        return self.item.name

    @property
    def meta(self):
        return self.goal

    @property
    def avance(self):
        return self.legacy_progress or Decimal("0")

    @property
    def ponderador(self):
        return self.weight_percent

    @property
    def porcentaje(self):
        if self.goal and self.goal > 0:
            return (self.avance / self.goal) * Decimal("100")
        return Decimal("0")

    @property
    def semaforo(self):
        return getattr(self, "_semaforo", "verde")

    @semaforo.setter
    def semaforo(self, value):
        self._semaforo = value

    @property
    def ponderado_cumplimiento(self):
        if hasattr(self, "_ponderado_cumplimiento"):
            return self._ponderado_cumplimiento
        return (self.weight_percent * self.porcentaje) / Decimal("100")

    @ponderado_cumplimiento.setter
    def ponderado_cumplimiento(self, value):
        self._ponderado_cumplimiento = value

    def clean(self):
        super().clean()
        if self.pk and type(self).objects.filter(pk=self.pk, period__status=Period.Status.CLOSED).exists():
            raise ValidationError("Targets in closed periods cannot be changed.")
        if self.period_id and Period.objects.filter(pk=self.period_id, status=Period.Status.CLOSED).exists():
            raise ValidationError("Targets cannot be saved to closed periods.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.period_id and Period.objects.filter(pk=self.period_id, status=Period.Status.CLOSED).exists():
            raise ValidationError("Targets in closed periods cannot be deleted.")
        return super().delete(*args, **kwargs)

    def __str__(self):
        return f"{self.staff} / {self.period} / {self.item}"
