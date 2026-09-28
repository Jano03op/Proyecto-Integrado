from datetime import date, timedelta
from decimal import Decimal

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from cuentas.models import StaffProfile
from organizacion.models import Delegation, Position

from .models import Commitment, CommitmentEvent


class CommitmentModelTests(TestCase):
    def setUp(self):
        self.delegation = Delegation.objects.create(name="Delegación Metropolitana")
        self.position = Position.objects.create(name="Analista")
        self.coord_position = Position.objects.create(name="Coordinador Territorial")
        self.owner = StaffProfile.objects.create(
            display_name="Funcionario Responsable",
            delegation=self.delegation,
            position=self.position,
        )
        self.actor_user = get_user_model().objects.create_user(username="actor_user")
        self.coord_user = get_user_model().objects.create_user(username="coord_user")
        self.coord_profile = StaffProfile.objects.create(
            user=self.coord_user,
            display_name="Coordinador Principal",
            delegation=self.delegation,
            position=self.coord_position,
        )

    def create_commitment(self, **kwargs):
        defaults = {
            "delegation": self.delegation,
            "owner": self.owner,
            "description": "Compromiso de prueba",
            "due_on": date.today() + timedelta(days=7),
            "status": Commitment.Status.INGRESADO,
        }
        defaults.update(kwargs)
        return Commitment.objects.create(**defaults)

    def test_commitment_creation_creates_initial_event_atomically(self):
        commitment = self.create_commitment()
        self.assertEqual(commitment.events.count(), 1)
        event = commitment.events.first()
        self.assertEqual(event.sequence, 1)
        self.assertIsNone(event.previous_status)
        self.assertEqual(event.next_status, Commitment.Status.INGRESADO)
        self.assertEqual(event.occurred_on, date.today())
        self.assertIn("Compromiso registrado", event.note)

    def test_normal_status_progression_advances_one_step(self):
        commitment = self.create_commitment()
        steps = [
            Commitment.Status.PENDIENTE,
            Commitment.Status.EN_PROCESO,
            Commitment.Status.REALIZADO,
        ]
        for idx, next_step in enumerate(steps, start=2):
            commitment.transition_to(
                next_step,
                actor=self.actor_user,
                note=f"Paso a {next_step}",
            )
            self.assertEqual(commitment.status, next_step)
            self.assertEqual(commitment.events.count(), idx)
            latest_event = commitment.events.order_by("sequence").last()
            self.assertEqual(latest_event.sequence, idx)
            self.assertEqual(latest_event.next_status, next_step)
            self.assertEqual(latest_event.actor, self.actor_user)
            self.assertIsNotNone(latest_event.occurred_at)

    def test_forward_jump_is_rejected(self):
        commitment = self.create_commitment()
        with self.assertRaises(ValidationError):
            commitment.transition_to(Commitment.Status.EN_PROCESO, actor=self.actor_user)
        with self.assertRaises(ValidationError):
            commitment.transition_to(Commitment.Status.REALIZADO, actor=self.actor_user)
        self.assertEqual(commitment.status, Commitment.Status.INGRESADO)
        self.assertEqual(commitment.events.count(), 1)

    def test_backward_transition_requires_authorized_actor_and_reason(self):
        commitment = self.create_commitment()
        commitment.transition_to(Commitment.Status.PENDIENTE, actor=self.actor_user)

        # Non-coordinator user without note
        with self.assertRaises(ValidationError):
            commitment.transition_to(
                Commitment.Status.INGRESADO,
                actor=self.actor_user,
                note="",
            )

        # Non-coordinator user with note
        with self.assertRaises(ValidationError):
            commitment.transition_to(
                Commitment.Status.INGRESADO,
                actor=self.actor_user,
                note="Reabriendo por error",
            )

        # Coordinator without note
        with self.assertRaises(ValidationError):
            commitment.transition_to(
                Commitment.Status.INGRESADO,
                actor=self.coord_user,
                note="",
            )

        # Coordinator with note
        commitment.transition_to(
            Commitment.Status.INGRESADO,
            actor=self.coord_user,
            note="Reapertura autorizada por coordinación",
        )
        self.assertEqual(commitment.status, Commitment.Status.INGRESADO)
        latest_event = commitment.events.order_by("sequence").last()
        self.assertEqual(latest_event.sequence, 3)
        self.assertEqual(latest_event.previous_status, Commitment.Status.PENDIENTE)
        self.assertEqual(latest_event.next_status, Commitment.Status.INGRESADO)
        self.assertEqual(latest_event.actor, self.coord_user)

    def test_owner_is_fixed_after_creation(self):
        commitment = self.create_commitment()
        other_owner = StaffProfile.objects.create(display_name="Otro Funcionario")
        commitment.owner = other_owner
        with self.assertRaises(ValidationError):
            commitment.save()

    def test_overdue_derivation(self):
        yesterday = date.today() - timedelta(days=1)
        tomorrow = date.today() + timedelta(days=1)

        c_overdue = self.create_commitment(due_on=yesterday)
        self.assertTrue(c_overdue.is_overdue)

        c_pending = self.create_commitment(due_on=tomorrow)
        self.assertFalse(c_pending.is_overdue)

        c_done = self.create_commitment(due_on=yesterday, status=Commitment.Status.REALIZADO)
        self.assertFalse(c_done.is_overdue)

        # Custom date check
        self.assertTrue(c_pending.check_overdue(today=date.today() + timedelta(days=5)))
        self.assertFalse(c_pending.check_overdue(today=date.today() - timedelta(days=5)))

    def test_board_completion_rate(self):
        # Empty set returns None (N/A)
        self.assertIsNone(Commitment.board_completion_rate())

        d1 = date(2026, 4, 1)
        d2 = date(2026, 4, 15)
        d3 = date(2026, 4, 30)

        self.create_commitment(due_on=d1, status=Commitment.Status.REALIZADO)
        self.create_commitment(due_on=d2, status=Commitment.Status.EN_PROCESO)
        self.create_commitment(due_on=d3, status=Commitment.Status.REALIZADO)
        self.create_commitment(due_on=date(2026, 5, 10), status=Commitment.Status.PENDIENTE)

        # Filter April range: 3 commitments, 2 Realizado -> 2/3 * 100
        rate = Commitment.board_completion_rate(start_date=date(2026, 4, 1), end_date=date(2026, 4, 30))
        self.assertAlmostEqual(float(rate), (2 / 3) * 100, places=2)

        # Filter empty range -> None
        empty_rate = Commitment.board_completion_rate(start_date=date(2026, 6, 1), end_date=date(2026, 6, 30))
        self.assertIsNone(empty_rate)

    def test_commitment_event_immutability_and_sequence_uniqueness(self):
        commitment = self.create_commitment()
        event = commitment.events.first()
        event.note = "Modificación no permitida"
        with self.assertRaises(ValidationError):
            event.save()
        with self.assertRaises(ValidationError):
            event.delete()

        # Duplicate sequence rejected by model validation
        with self.assertRaises(ValidationError):
            CommitmentEvent.objects.create(
                commitment=commitment,
                sequence=1,
                next_status=Commitment.Status.PENDIENTE,
                occurred_on=date.today(),
            )

        # Database constraint applies to queryset update
        event2 = CommitmentEvent(
            commitment=commitment,
            sequence=2,
            next_status=Commitment.Status.PENDIENTE,
            occurred_on=date.today(),
        )
        super(CommitmentEvent, event2).save()
        with self.assertRaises(IntegrityError), transaction.atomic():
            CommitmentEvent.objects.filter(pk=event2.pk).update(sequence=1)

    def test_new_event_requires_authenticated_actor_when_occurred_at_present(self):
        commitment = self.create_commitment()
        # With occurred_at but no actor -> ValidationError
        with self.assertRaises(ValidationError):
            CommitmentEvent.objects.create(
                commitment=commitment,
                sequence=2,
                next_status=Commitment.Status.PENDIENTE,
                occurred_on=date.today(),
                occurred_at=timezone.now(),
                actor=None,
            )

        # Historical event (occurred_at is None, actor is None) is permitted
        legacy_event = CommitmentEvent.objects.create(
            commitment=commitment,
            sequence=2,
            next_status=Commitment.Status.PENDIENTE,
            occurred_on=date(2025, 6, 1),
            occurred_at=None,
            actor=None,
            note="Legacy import event",
        )
        self.assertEqual(legacy_event.sequence, 2)


class CommitmentAdminTests(TestCase):
    def setUp(self):
        self.admin_user = get_user_model().objects.create_superuser(
            username="admin_user",
            email="admin@example.test",
            password="test-password",
        )
        self.client.force_login(self.admin_user)
        self.delegation = Delegation.objects.create(name="Delegación Regional")
        self.position = Position.objects.create(name="Especialista")
        self.owner = StaffProfile.objects.create(
            display_name="Funcionario Asignado",
            delegation=self.delegation,
            position=self.position,
        )

    def test_admin_registration_and_search(self):
        self.assertIn(Commitment, admin.site._registry)
        self.assertIn(CommitmentEvent, admin.site._registry)

        Commitment.objects.create(
            delegation=self.delegation,
            owner=self.owner,
            description="Compromiso Búsqueda",
            territory_label="Territorio Norte",
            due_on=date.today() + timedelta(days=5),
        )

        changelist_url = reverse("admin:agenda_commitment_changelist")
        response = self.client.get(changelist_url + "?q=Búsqueda")
        self.assertContains(response, "Compromiso Búsqueda")
        response_owner = self.client.get(changelist_url + "?q=Asignado")
        self.assertContains(response_owner, "Funcionario Asignado")

    def test_admin_create_commitment_creates_initial_event_with_actor(self):
        add_url = reverse("admin:agenda_commitment_add")
        payload = {
            "delegation": self.delegation.pk,
            "owner": self.owner.pk,
            "description": "Nuevo compromiso vía Admin",
            "registered_on": "2026-09-27",
            "due_on": "2026-10-15",
            "status": Commitment.Status.INGRESADO,
            "note": "Registro inicial",
            "_save": "Save",
        }
        response = self.client.post(add_url, payload)
        self.assertEqual(response.status_code, 302)
        commitment = Commitment.objects.get(description="Nuevo compromiso vía Admin")
        self.assertEqual(commitment.events.count(), 1)
        event = commitment.events.first()
        self.assertEqual(event.actor, self.admin_user)
        self.assertIsNotNone(event.occurred_at)

    def test_admin_change_advances_status_and_appends_event(self):
        commitment = Commitment.objects.create(
            delegation=self.delegation,
            owner=self.owner,
            description="Compromiso Admin Avance",
            due_on=date.today() + timedelta(days=5),
            status=Commitment.Status.INGRESADO,
        )
        change_url = reverse("admin:agenda_commitment_change", args=[commitment.pk])
        payload = {
            "delegation": self.delegation.pk,
            "owner": self.owner.pk,
            "description": "Compromiso Admin Avance",
            "registered_on": str(commitment.registered_on),
            "due_on": str(commitment.due_on),
            "status": Commitment.Status.PENDIENTE,
            "note": "Avanzando a pendiente desde Admin",
            "_save": "Save",
        }
        response = self.client.post(change_url, payload)
        self.assertEqual(response.status_code, 302)
        commitment.refresh_from_db()
        self.assertEqual(commitment.status, Commitment.Status.PENDIENTE)
        self.assertEqual(commitment.events.count(), 2)
        latest_event = commitment.events.order_by("sequence").last()
        self.assertEqual(latest_event.previous_status, Commitment.Status.INGRESADO)
        self.assertEqual(latest_event.next_status, Commitment.Status.PENDIENTE)
        self.assertEqual(latest_event.actor, self.admin_user)

    def test_admin_invalid_jump_renders_form_error(self):
        commitment = Commitment.objects.create(
            delegation=self.delegation,
            owner=self.owner,
            description="Compromiso Salto Inválido",
            due_on=date.today() + timedelta(days=5),
            status=Commitment.Status.INGRESADO,
        )
        change_url = reverse("admin:agenda_commitment_change", args=[commitment.pk])
        payload = {
            "delegation": self.delegation.pk,
            "owner": self.owner.pk,
            "description": "Compromiso Salto Inválido",
            "registered_on": str(commitment.registered_on),
            "due_on": str(commitment.due_on),
            "status": Commitment.Status.REALIZADO,
            "note": "Salto no permitido",
            "_save": "Save",
        }
        response = self.client.post(change_url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Status cannot advance more than one step")
        commitment.refresh_from_db()
        self.assertEqual(commitment.status, Commitment.Status.INGRESADO)

    def test_admin_owner_change_renders_form_error(self):
        commitment = Commitment.objects.create(
            delegation=self.delegation,
            owner=self.owner,
            description="Compromiso Bloqueo Dueño",
            due_on=date.today() + timedelta(days=5),
        )
        other_owner = StaffProfile.objects.create(display_name="Otro Funcionario 2")
        change_url = reverse("admin:agenda_commitment_change", args=[commitment.pk])
        payload = {
            "delegation": self.delegation.pk,
            "owner": other_owner.pk,
            "description": "Compromiso Bloqueo Dueño",
            "registered_on": str(commitment.registered_on),
            "due_on": str(commitment.due_on),
            "status": Commitment.Status.INGRESADO,
            "note": "",
            "_save": "Save",
        }
        response = self.client.post(change_url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Commitment owner cannot be reassigned")
        commitment.refresh_from_db()
        self.assertEqual(commitment.owner, self.owner)

    def test_commitment_event_admin_permissions(self):
        commitment = Commitment.objects.create(
            delegation=self.delegation,
            owner=self.owner,
            description="Compromiso para Eventos",
            due_on=date.today() + timedelta(days=5),
        )
        event = commitment.events.first()

        changelist_url = reverse("admin:agenda_commitmentevent_changelist")
        self.assertEqual(self.client.get(changelist_url).status_code, 200)

        add_url = reverse("admin:agenda_commitmentevent_add")
        self.assertEqual(self.client.get(add_url).status_code, 403)
        self.assertEqual(self.client.post(add_url, {}).status_code, 403)

        change_url = reverse("admin:agenda_commitmentevent_change", args=[event.pk])
        self.assertEqual(self.client.get(change_url).status_code, 200)  # Read-only detail view
        self.assertEqual(self.client.post(change_url, {}).status_code, 403)

        delete_url = reverse("admin:agenda_commitmentevent_delete", args=[event.pk])
        self.assertEqual(self.client.get(delete_url).status_code, 403)
        self.assertEqual(self.client.post(delete_url, {}).status_code, 403)
