from datetime import date
from decimal import Decimal

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.urls import reverse

from cuentas.models import StaffProfile
from .models import MetricItem, Period, StaffTarget


class IndicatorModelTests(TestCase):
    def setUp(self):
        self.period = Period.objects.create(
            starts_on=date(2026, 1, 1), ends_on=date(2026, 1, 3)
        )
        self.staff = StaffProfile.objects.create(display_name="Synthetic Staff")
        self.item = MetricItem.objects.create(name="Synthetic metric")

    def target(self, **changes):
        fields = dict(
            staff=self.staff, period=self.period, item=self.item,
            goal=Decimal("10.00"), weight_percent=Decimal("40.00"),
        )
        fields.update(changes)
        return StaffTarget.objects.create(**fields)

    def test_inclusive_days_clamp_before_and_after_period(self):
        self.assertEqual(self.period.total_days, 3)
        for day, expected in [
            (date(2025, 12, 31), 0), (date(2026, 1, 1), 1),
            (date(2026, 1, 3), 3), (date(2026, 1, 4), 3),
        ]:
            with self.subTest(day=day):
                self.assertEqual(self.period.elapsed_days(day), expected)
        single = Period(starts_on=date(2027, 1, 1), ends_on=date(2027, 1, 1))
        self.assertEqual(single.total_days, 1)
        self.assertEqual(single.elapsed_days(date(2027, 1, 1)), 1)

    def test_invalid_dates_overlap_inclusive_endpoint_and_single_active(self):
        with self.assertRaises(ValidationError):
            Period.objects.create(starts_on=date(2026, 2, 2), ends_on=date(2026, 2, 1))
        with self.assertRaises(ValidationError):
            Period.objects.create(starts_on=date(2026, 1, 3), ends_on=date(2026, 1, 9))
        self.period.status = Period.Status.ACTIVE
        self.period.save()
        with self.assertRaises(ValidationError):
            Period.objects.create(
                starts_on=date(2026, 2, 1), ends_on=date(2026, 2, 2),
                status=Period.Status.ACTIVE,
            )

    def test_closed_period_and_its_targets_are_read_only_on_instance_paths(self):
        target = self.target()
        self.period.status = Period.Status.CLOSED
        self.period.save()
        self.period.status = Period.Status.ACTIVE
        with self.assertRaises(ValidationError):
            self.period.save()
        with self.assertRaises(ValidationError):
            self.period.delete()
        target.goal = Decimal("12")
        with self.assertRaises(ValidationError):
            target.save()
        with self.assertRaises(ValidationError):
            target.delete()
        with self.assertRaises(ValidationError):
            self.target(item=MetricItem.objects.create(name="Second metric"))
        later = Period.objects.create(
            starts_on=date(2026, 2, 1), ends_on=date(2026, 2, 3)
        )
        target.period = later
        with self.assertRaises(ValidationError):
            target.save()

    def test_required_links_and_uniqueness(self):
        self.target()
        with self.assertRaises(ValidationError):
            self.target()
        with self.assertRaises(ValidationError):
            self.target(staff=None)
        with self.assertRaises(ValidationError):
            MetricItem(name=self.item.name).full_clean()
        with self.assertRaises(ProtectedError):
            self.staff.delete()

    def test_decimal_constraints_and_optional_provisional_progress(self):
        for changes in [
            {"goal": Decimal("0")}, {"weight_percent": Decimal("-1")},
            {"weight_percent": Decimal("101")}, {"legacy_progress": Decimal("-1")},
        ]:
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.target(**changes)
        target = self.target(weight_percent=Decimal("0"))
        self.assertIsNone(target.legacy_progress)
        target.legacy_progress = Decimal("8.50")
        target.save()
        self.assertEqual(StaffTarget.objects.get(pk=target.pk).legacy_progress, Decimal("8.50"))

    def test_db_constraints_apply_even_to_queryset_update_on_sqlite(self):
        target = self.target()
        with self.assertRaises(IntegrityError), transaction.atomic():
            StaffTarget.objects.filter(pk=target.pk).update(goal=Decimal("0"))
        with self.assertRaises(IntegrityError), transaction.atomic():
            Period.objects.filter(pk=self.period.pk).update(ends_on=date(2025, 1, 1))

    def test_draft_weights_require_exactly_one_hundred_for_readiness(self):
        self.assertFalse(StaffTarget.weights_ready(self.staff, self.period))
        self.target()
        self.assertFalse(StaffTarget.weights_ready(self.staff, self.period))
        self.target(item=MetricItem.objects.create(name="Other metric"), weight_percent=Decimal("60"))
        self.assertTrue(StaffTarget.weights_ready(self.staff, self.period))
        self.target(item=MetricItem.objects.create(name="Third metric"), weight_percent=Decimal("1"))
        self.assertFalse(StaffTarget.weights_ready(self.staff, self.period))


class IndicatorAdminTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="synthetic-admin", password="test-password", email="admin@example.test"
        )
        self.client.force_login(self.user)
        self.staff = StaffProfile.objects.create(display_name="Synthetic Staff")
        self.period = Period.objects.create(
            starts_on=date(2026, 1, 1), ends_on=date(2026, 1, 3)
        )
        self.item = MetricItem.objects.create(name="Synthetic metric")

    def test_admin_registration_search_and_create(self):
        for model in (Period, MetricItem, StaffTarget):
            self.assertIn(model, admin.site._registry)
        item_list = reverse("admin:indicadores_metricitem_changelist")
        self.assertContains(self.client.get(item_list + "?q=Synthetic"), "Synthetic metric")
        self.assertEqual(self.client.post(reverse("admin:indicadores_metricitem_add"), {
            "name": "Second metric", "_save": "Save",
        }).status_code, 302)
        target_add = reverse("admin:indicadores_stafftarget_add")
        payload = {
            "staff": self.staff.pk, "period": self.period.pk, "item": self.item.pk,
            "goal": "10.00", "weight_percent": "40.00", "legacy_progress": "",
            "_save": "Save",
        }
        self.assertEqual(self.client.post(target_add, payload).status_code, 302)
        self.assertEqual(StaffTarget.objects.count(), 1)
        self.assertContains(self.client.get(
            reverse("admin:indicadores_stafftarget_changelist") + "?q=Synthetic"
        ), "Synthetic Staff")
        change = reverse("admin:indicadores_stafftarget_change", args=[StaffTarget.objects.get().pk])
        self.assertEqual(self.client.post(change, {**payload, "goal": "12.00"}).status_code, 302)
        self.assertEqual(StaffTarget.objects.get().goal, Decimal("12.00"))

    def test_admin_invalid_input_renders_form_errors_and_closed_rows_cannot_be_edited(self):
        target_add = reverse("admin:indicadores_stafftarget_add")
        payload = {
            "staff": self.staff.pk, "period": self.period.pk, "item": self.item.pk,
            "goal": "0", "weight_percent": "101", "legacy_progress": "",
            "_save": "Save",
        }
        response = self.client.post(target_add, payload)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Constraint")
        self.assertFalse(StaffTarget.objects.exists())
        payload.update(goal="10", weight_percent="40")
        self.client.post(target_add, payload)
        target = StaffTarget.objects.get()
        self.period.status = Period.Status.CLOSED
        self.period.save()
        self.assertEqual(self.client.post(target_add, payload).status_code, 200)
        self.assertEqual(StaffTarget.objects.count(), 1)
        period_change = reverse("admin:indicadores_period_change", args=[self.period.pk])
        target_change = reverse("admin:indicadores_stafftarget_change", args=[target.pk])
        self.assertEqual(self.client.get(period_change).status_code, 200)  # Read-only detail.
        self.assertEqual(self.client.get(target_change).status_code, 200)
        self.assertEqual(self.client.post(period_change, {
            "starts_on": "2026-01-01", "ends_on": "2026-01-03", "status": "active",
        }).status_code, 403)
        self.assertEqual(self.client.post(target_change, payload).status_code, 403)
        self.assertEqual(self.client.get(reverse(
            "admin:indicadores_stafftarget_delete", args=[target.pk]
        )).status_code, 403)
