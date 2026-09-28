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


class OrganizationViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="test_admin", email="admin@example.test", password="test-password"
        )
        self.client.force_login(self.user)
        session = self.client.session
        session["persona_actual"] = {"nombre": "Admin Test", "rol": "administrador"}
        session["rol"] = "administrador"
        session.save()
        self.delegation = Delegation.objects.create(
            name="Delegación Norte", scope="Sector Norte", status=Delegation.Status.ACTIVE
        )

    def test_list_view_renders_delegations_and_filters(self):
        d_south = Delegation.objects.create(
            name="Delegación Sur", scope="Sector Sur", status=Delegation.Status.INACTIVE
        )
        url = reverse("organizacion:delegaciones_list")
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Delegación Norte")
        self.assertContains(res, "Delegación Sur")

        # Search filter
        res_search = self.client.get(url, {"q": "Norte"})
        self.assertEqual(res_search.status_code, 200)
        self.assertContains(res_search, "Delegación Norte")
        self.assertNotContains(res_search, "Delegación Sur")

        # Status filter
        res_status = self.client.get(url, {"estado": "Activa"})
        self.assertEqual(res_status.status_code, 200)
        self.assertContains(res_status, "Delegación Norte")
        self.assertNotContains(res_status, "Delegación Sur")

    def test_detail_view_renders_staff_members(self):
        pos = Position.objects.create(name="Especialista")
        StaffProfile.objects.create(
            display_name="Juan Pérez", delegation=self.delegation, position=pos, legacy_role="funcionario"
        )
        url = reverse("organizacion:delegacion_detail", args=[self.delegation.pk])
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Delegación Norte")
        self.assertContains(res, "Juan Pérez")
        self.assertContains(res, "Especialista")

    def test_detail_view_not_found_redirects(self):
        url = reverse("organizacion:delegacion_detail", args=[9999])
        res = self.client.get(url)
        self.assertRedirects(res, reverse("organizacion:delegaciones_list"))

    def test_create_view_and_duplicate_validation(self):
        url = reverse("organizacion:delegacion_create")
        res_get = self.client.get(url)
        self.assertEqual(res_get.status_code, 200)

        # Successful creation
        res_post = self.client.post(url, {
            "nombre": "Delegación Este", "ambito": "Sector Este", "estado": "Activa"
        })
        self.assertRedirects(res_post, reverse("organizacion:delegaciones_list"))
        self.assertTrue(Delegation.objects.filter(name="Delegación Este").exists())

        # Duplicate name rejected
        res_dup = self.client.post(url, {
            "nombre": "Delegación Este", "ambito": "Duplicado", "estado": "Activa"
        })
        self.assertEqual(res_dup.status_code, 200)
        self.assertContains(res_dup, "Ya existe una delegación con ese nombre")

    def test_edit_view_updates_delegation(self):
        url = reverse("organizacion:delegacion_edit", args=[self.delegation.pk])
        res_get = self.client.get(url)
        self.assertEqual(res_get.status_code, 200)
        self.assertContains(res_get, "Delegación Norte")

        res_post = self.client.post(url, {
            "nombre": "Delegación Norte Modificada",
            "ambito": "Nuevo ámbito",
            "estado": "Inactiva",
        })
        self.assertRedirects(res_post, reverse("organizacion:delegaciones_list"))
        self.delegation.refresh_from_db()
        self.assertEqual(self.delegation.name, "Delegación Norte Modificada")
        self.assertEqual(self.delegation.status, Delegation.Status.INACTIVE)

    def test_toggle_estado_view(self):
        url = reverse("organizacion:delegacion_toggle_estado", args=[self.delegation.pk])
        res = self.client.post(url)
        self.assertRedirects(res, reverse("organizacion:delegaciones_list"))
        self.delegation.refresh_from_db()
        self.assertEqual(self.delegation.status, Delegation.Status.INACTIVE)

        res2 = self.client.post(url)
        self.assertRedirects(res2, reverse("organizacion:delegaciones_list"))
        self.delegation.refresh_from_db()
        self.assertEqual(self.delegation.status, Delegation.Status.ACTIVE)

    def test_unauthorized_role_cannot_modify(self):
        regular_user = get_user_model().objects.create_user(username="regular")
        self.client.force_login(regular_user)
        session = self.client.session
        session["persona_actual"] = {"nombre": "Consulta Test", "rol": "consulta"}
        session["rol"] = "consulta"
        session.save()

        url_create = reverse("organizacion:delegacion_create")
        res = self.client.get(url_create)
        self.assertRedirects(res, reverse("organizacion:delegaciones_list"))

