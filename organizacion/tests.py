from django.contrib import admin
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from cuentas.models import StaffProfile

from .models import Delegation, Position


class OrganizationModelTests(TestCase):
    def test_delegation_defaults_active_and_names_are_unique(self):
        delegation = Delegation.objects.create(name="North", scope="District")
        self.assertEqual(delegation.status, Delegation.Status.ACTIVE)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Delegation.objects.create(name="North")

    def test_position_is_globally_unique_and_shared(self):
        position = Position.objects.create(name="Coordinator")
        first = StaffProfile.objects.create(display_name="Person One", position=position)
        second = StaffProfile.objects.create(display_name="Person Two", position=position)
        self.assertEqual(first.position, second.position)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Position.objects.create(name="Coordinator")

    def test_user_admin_remains_registered(self):
        self.assertIn(get_user_model(), admin.site._registry)


class OrganizationAdminTests(TestCase):
    def setUp(self):
        self.client.force_login(
            get_user_model().objects.create_superuser(
                username="admin", email="admin@example.test", password="test-password"
            )
        )

    def test_delegation_admin_search_and_crud(self):
        model_admin = admin.site._registry[Delegation]
        self.assertIn("name", model_admin.search_fields)
        self.assertIn("status", model_admin.list_filter)
        self.assertEqual(
            self.client.post(reverse("admin:organizacion_delegation_add"), {
                "name": "North", "scope": "District", "status": "active", "_save": "Save"
            }).status_code, 302
        )
        delegation = Delegation.objects.get(name="North")
        other = Delegation.objects.create(name="South")
        result = self.client.get(reverse("admin:organizacion_delegation_changelist"), {"q": "North"})
        self.assertEqual(list(result.context["cl"].queryset), [delegation])
        self.assertNotIn(other, result.context["cl"].queryset)
        change_url = reverse("admin:organizacion_delegation_change", args=[delegation.pk])
        self.assertEqual(self.client.post(change_url, {
            "name": "North", "scope": "New district", "status": "inactive", "_save": "Save"
        }).status_code, 302)
        delegation.refresh_from_db()
        self.assertEqual((delegation.scope, delegation.status), ("New district", "inactive"))
        delete_url = reverse("admin:organizacion_delegation_delete", args=[delegation.pk])
        self.assertEqual(self.client.post(delete_url, {"post": "yes"}).status_code, 302)
        self.assertFalse(Delegation.objects.filter(pk=delegation.pk).exists())

    def test_position_admin_search_and_crud(self):
        model_admin = admin.site._registry[Position]
        self.assertIn("name", model_admin.search_fields)
        self.assertEqual(self.client.post(reverse("admin:organizacion_position_add"), {
            "name": "Coordinator", "_save": "Save"
        }).status_code, 302)
        position = Position.objects.get(name="Coordinator")
        Position.objects.create(name="Analyst")
        result = self.client.get(reverse("admin:organizacion_position_changelist"), {"q": "Coordinator"})
        self.assertEqual(list(result.context["cl"].queryset), [position])
        self.assertEqual(self.client.post(
            reverse("admin:organizacion_position_change", args=[position.pk]),
            {"name": "Lead Coordinator", "_save": "Save"},
        ).status_code, 302)
        position.refresh_from_db()
        self.assertEqual(position.name, "Lead Coordinator")
        self.assertEqual(self.client.post(
            reverse("admin:organizacion_position_delete", args=[position.pk]), {"post": "yes"}
        ).status_code, 302)
        self.assertFalse(Position.objects.filter(pk=position.pk).exists())
