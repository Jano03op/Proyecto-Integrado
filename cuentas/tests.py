from django.contrib import admin
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.urls import reverse

from organizacion.models import Delegation, Position

from .models import StaffProfile


class StaffProfileModelTests(TestCase):
    def test_links_are_optional_and_user_link_is_unique(self):
        unassigned = StaffProfile.objects.create(display_name="Unassigned")
        self.assertIsNone(unassigned.user)
        self.assertIsNone(unassigned.delegation)
        self.assertIsNone(unassigned.position)
        self.assertEqual(StaffProfile.objects.create(display_name="Another").user, None)
        user = get_user_model().objects.create_user(username="staff")
        profile = StaffProfile.objects.create(display_name="Staff", user=user)
        self.assertEqual(user.staff_profile, profile)
        with self.assertRaises(IntegrityError), transaction.atomic():
            StaffProfile.objects.create(display_name="Duplicate", user=user)

    def test_linked_records_cannot_be_deleted_without_reassignment(self):
        user = get_user_model().objects.create_user(username="staff")
        delegation = Delegation.objects.create(name="North")
        position = Position.objects.create(name="Coordinator")
        StaffProfile.objects.create(
            display_name="Staff", user=user, delegation=delegation, position=position
        )
        for record in (user, delegation, position):
            with self.subTest(record=type(record).__name__):
                with self.assertRaises(ProtectedError):
                    record.delete()


class StaffProfileAdminTests(TestCase):
    def setUp(self):
        self.client.force_login(
            get_user_model().objects.create_superuser(
                username="admin", email="admin@example.test", password="test-password"
            )
        )

    def test_admin_search_and_crud_with_optional_links(self):
        model_admin = admin.site._registry[StaffProfile]
        self.assertIn("user__username", model_admin.search_fields)
        self.assertIn("delegation", model_admin.list_filter)
        self.assertIn("position", model_admin.autocomplete_fields)
        self.assertEqual(self.client.post(reverse("admin:cuentas_staffprofile_add"), {
            "display_name": "Alex Rivera", "legacy_role": "Historical label", "_save": "Save"
        }).status_code, 302)
        profile = StaffProfile.objects.get(display_name="Alex Rivera")
        StaffProfile.objects.create(display_name="Other Staff")
        result = self.client.get(reverse("admin:cuentas_staffprofile_changelist"), {"q": "Alex"})
        self.assertEqual(list(result.context["cl"].queryset), [profile])
        delegation = Delegation.objects.create(name="North")
        position = Position.objects.create(name="Coordinator")
        user = get_user_model().objects.create_user(username="alex")
        self.assertEqual(self.client.post(
            reverse("admin:cuentas_staffprofile_change", args=[profile.pk]), {
                "display_name": "Alex Rivera", "legacy_role": "Historical label",
                "user": user.pk, "delegation": delegation.pk, "position": position.pk,
                "_save": "Save",
            }
        ).status_code, 302)
        profile.refresh_from_db()
        self.assertEqual((profile.user, profile.delegation, profile.position), (user, delegation, position))
        result = self.client.get(reverse("admin:cuentas_staffprofile_changelist"), {"q": "alex"})
        self.assertEqual(list(result.context["cl"].queryset), [profile])
        self.assertEqual(self.client.post(
            reverse("admin:cuentas_staffprofile_delete", args=[profile.pk]), {"post": "yes"}
        ).status_code, 302)
        self.assertFalse(StaffProfile.objects.filter(pk=profile.pk).exists())
        self.assertTrue(get_user_model().objects.filter(pk=user.pk).exists())


class ReconciliationCommandTests(TestCase):
    def test_reconcile_command_dry_run_json_output(self):
        import io
        import json
        from django.core.management import call_command

        out = io.StringIO()
        call_command("reconcile_sgr_data", json=True, stdout=out)
        data = json.loads(out.getvalue())

        summary = data["summary"]
        self.assertEqual(summary["delegations"]["raw_count"], 6)
        self.assertEqual(summary["delegations"]["canonical_candidates"], 6)
        self.assertEqual(summary["persons"]["raw_count"], 10)
        self.assertEqual(summary["persons"]["accepted_with_delegation"], 8)
        self.assertEqual(summary["persons"]["held_delegation_exceptions"], 2)
        self.assertEqual(summary["persons"]["credential_hashes_detected"], 10)
        self.assertTrue(summary["period"]["valid"])
        self.assertEqual(summary["period"]["total_calendar_days"], 92)
        self.assertEqual(summary["staff_targets"]["persons_with_items"], 7)
        self.assertEqual(summary["staff_targets"]["weight_sets_100_percent"], 6)
        self.assertEqual(summary["commitments"]["raw_count"], 10)
        self.assertEqual(summary["commitments"]["with_owner_candidate"], 7)
        self.assertEqual(summary["commitments"]["held_owner_exceptions"], 3)
        self.assertEqual(summary["commitment_events"]["raw_count"], 25)
        self.assertEqual(summary["commitment_events"]["actor_candidates"], 21)
        self.assertEqual(summary["commitment_events"]["unresolved_historical_actors"], 4)

