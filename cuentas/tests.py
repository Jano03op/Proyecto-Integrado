from django.contrib import admin
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.urls import reverse

from agenda.models import Commitment, CommitmentEvent
from indicadores.models import MetricItem, Period, StaffTarget
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


class CuentasViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="carlos.valenzuela",
            email="carlos@laserena.cl",
            password="secure-password-123",
            first_name="Carlos",
            last_name="Valenzuela",
        )
        self.delegation = Delegation.objects.create(name="La Antena", scope="Territorial")
        self.profile = StaffProfile.objects.create(
            user=self.user,
            delegation=self.delegation,
            display_name="Carlos Valenzuela",
            legacy_role="funcionario",
        )

    def set_session(self, user=None, persona_actual=None, rol=None):
        from django.conf import settings

        if user:
            self.client.force_login(user)
        session = self.client.session
        if persona_actual:
            session["persona_actual"] = persona_actual
        if rol:
            session["rol"] = rol
        session.save()
        self.client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key

    def test_login_view_get_and_post_valid(self):
        url = reverse("cuentas:login")
        res_get = self.client.get(url)
        self.assertEqual(res_get.status_code, 200)
        self.assertTemplateUsed(res_get, "cuentas/login.html")

        res_fail = self.client.post(url, {"username": "carlos.valenzuela", "password": "wrong"})
        self.assertEqual(res_fail.status_code, 200)
        self.assertContains(res_fail, "Usuario o contraseña incorrectos")

        res_success = self.client.post(url, {"username": "carlos.valenzuela", "password": "secure-password-123"})
        self.assertEqual(res_success.status_code, 302)
        self.assertEqual(res_success.url, reverse("cuentas:home"))
        self.assertEqual(self.client.session.get("persona_actual"), "Carlos Valenzuela")

    def test_logout_view(self):
        self.set_session(user=self.user, persona_actual="Carlos Valenzuela", rol="funcionario")
        res = self.client.get(reverse("cuentas:logout"))
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, reverse("landing_page"))
        self.assertNotIn("persona_actual", self.client.session)

    def test_registro_view_creates_user_and_profile(self):
        url = reverse("cuentas:registro")
        res_get = self.client.get(url)
        self.assertEqual(res_get.status_code, 200)
        self.assertTemplateUsed(res_get, "cuentas/registro.html")

        payload = {
            "first_name": "Ana",
            "last_name": "Gómez",
            "username": "ana.gomez",
            "email": "ana@laserena.cl",
            "password1": "password1234",
            "password2": "password1234",
        }
        res_post = self.client.post(url, payload)
        self.assertEqual(res_post.status_code, 302)
        self.assertEqual(res_post.url, reverse("cuentas:home"))

        new_user = get_user_model().objects.get(username="ana.gomez")
        self.assertEqual(new_user.email, "ana@laserena.cl")
        self.assertTrue(new_user.check_password("password1234"))
        profile = StaffProfile.objects.get(user=new_user)
        self.assertEqual(profile.display_name, "Ana Gómez")
        self.assertEqual(profile.legacy_role, "funcionario")

    def test_recuperar_view_two_steps(self):
        from django.conf import settings

        url = reverse("cuentas:recuperar")
        res_step1 = self.client.post(url, {"identificador": "carlos.valenzuela"})
        self.assertEqual(res_step1.status_code, 302)
        self.assertEqual(res_step1.url, url)

        session = self.client.session
        session["recuperar_usuario"] = "carlos.valenzuela"
        session.save()
        self.client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key

        res_step2_get = self.client.get(url)
        self.assertEqual(res_step2_get.status_code, 200)
        self.assertContains(res_step2_get, "Define tu nueva contraseña")

        res_step2_post = self.client.post(url, {
            "password1": "new-password-5678",
            "password2": "new-password-5678",
        })
        self.assertEqual(res_step2_post.status_code, 302)
        self.assertEqual(res_step2_post.url, reverse("cuentas:login"))

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("new-password-5678"))

    def test_home_view_renders_commitment_counters(self):
        from agenda.models import Commitment
        from datetime import date, timedelta

        Commitment.objects.create(
            delegation=self.delegation,
            owner=self.profile,
            description="Reparar veredas",
            origin="Solicitud ciudadana",
            requester="Vecinos",
            territory_label="La Antena",
            due_on=date.today() + timedelta(days=10),
            status=Commitment.Status.INGRESADO,
        )

        self.set_session(user=self.user, persona_actual="Carlos Valenzuela", rol="funcionario")
        res = self.client.get(reverse("cuentas:home"))
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, "cuentas/home.html")
        self.assertContains(res, "Carlos Valenzuela")
        self.assertContains(res, "Reparar veredas")
        self.assertEqual(res.context["total_compromisos"], 1)
        self.assertEqual(res.context["pendientes"], 1)


class ImportDataCommandTests(TestCase):
    def test_import_data_command_dry_run(self):
        import io
        import json
        from django.core.management import call_command

        out = io.StringIO()
        call_command("import_sgr_data", dry_run=True, json=True, stdout=out)
        data = json.loads(out.getvalue())
        self.assertTrue(data["dry_run"])
        self.assertEqual(data["delegations"]["total"], 6)
        self.assertEqual(data["commitments"]["imported"], 7)
        self.assertEqual(data["commitments"]["held_exceptions"], 3)
        self.assertEqual(data["staff_targets"]["created"], 33)
        # Database remains empty because of dry-run rollback
        self.assertEqual(Delegation.objects.count(), 0)
        self.assertEqual(Commitment.objects.count(), 0)

    def test_import_data_command_execution(self):
        import io
        import json
        from django.core.management import call_command

        out = io.StringIO()
        call_command("import_sgr_data", json=True, stdout=out)
        data = json.loads(out.getvalue())
        self.assertFalse(data["dry_run"])
        self.assertEqual(data["delegations"]["total"], 6)
        self.assertEqual(data["commitments"]["imported"], 7)
        self.assertEqual(data["commitments"]["held_exceptions"], 3)
        self.assertEqual(data["staff_targets"]["created"], 33)
        self.assertEqual(data["users"]["password_hashes_blocked"], 10)

        # Verify records exist in database
        self.assertEqual(Delegation.objects.count(), 6)
        self.assertEqual(Position.objects.count(), 7)
        self.assertEqual(StaffProfile.objects.count(), 10)
        self.assertEqual(Period.objects.count(), 1)
        self.assertEqual(MetricItem.objects.count(), 30)
        self.assertEqual(StaffTarget.objects.count(), 33)
        self.assertEqual(Commitment.objects.count(), 7)
        self.assertGreater(CommitmentEvent.objects.count(), 15)

        # Verify no passwords were imported
        User = get_user_model()
        for u in User.objects.all():
            self.assertFalse(u.has_usable_password())

        # Verify idempotency (re-running produces no duplicates)
        out2 = io.StringIO()
        call_command("import_sgr_data", json=True, stdout=out2)
        self.assertEqual(Delegation.objects.count(), 6)
        self.assertEqual(Commitment.objects.count(), 7)
        self.assertEqual(StaffTarget.objects.count(), 33)

