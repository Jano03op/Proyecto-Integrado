"""
Management command for Stage 3 real data migration of legacy SGR JSON data.
Implements the audit, security, and integrity boundaries specified in:
- docs/sgr-backend-mysql-mer.md
- docs/sgr-mysql-migration-plan.md

Integrity and security guarantees:
- Passwords: Hashes in JSON are NEVER imported into auth_user. Users receive unusable passwords.
- FK Integrity: Only commitments with confirmed owner and delegation are imported into canonical tables.
- Quarantine: Unresolved commitments and delegation-less persons are reported as exceptions without corrupting DB.
- Events: Historical events preserved in original sequence with NULL actor for unresolved actors.
- Atomicity: Wrapped in atomic transaction; rollback on --dry-run or any unexpected error.
"""
from datetime import date, datetime
from decimal import Decimal
import json
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from agenda.models import Commitment, CommitmentEvent
from cuentas.models import StaffProfile
from indicadores.models import MetricItem, Period, StaffTarget
from organizacion.models import Delegation, Position


class Command(BaseCommand):
    help = "Import legacy JSON data (datosarray.json) into the relational Django ORM models."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=str,
            default=str(settings.BASE_DIR / "datosarray.json"),
            help="Path to source JSON file (default: BASE_DIR/datosarray.json)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Execute reconciliation and validation without committing changes to the database.",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="Output migration summary in JSON format.",
        )

    def handle(self, *args, **options):
        file_path = Path(options["file"])
        if not file_path.exists():
            raise CommandError(f"Source file not found: {file_path}")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            raise CommandError(f"Error reading JSON file {file_path}: {e}")

        dry_run = options.get("dry_run", False)

        try:
            with transaction.atomic():
                summary = self.import_data(data, dry_run=dry_run)
                if dry_run:
                    transaction.set_rollback(True)
        except Exception as e:
            raise CommandError(f"Data migration aborted: {e}")

        if options.get("json"):
            self.stdout.write(json.dumps(summary, indent=2, default=str))
        else:
            self.print_summary(summary, dry_run=dry_run)

    def import_data(self, data, dry_run=False):
        User = get_user_model()
        summary = {
            "dry_run": dry_run,
            "delegations": {"created": 0, "total": 0},
            "positions": {"created": 0, "total": 0},
            "users": {"created": 0, "password_hashes_blocked": 0},
            "staff_profiles": {"accepted": 0, "delegation_exceptions": 0},
            "period": {"created": False, "starts_on": None, "ends_on": None},
            "metric_items": {"created": 0, "total": 0},
            "staff_targets": {"created": 0, "staff_count": 0},
            "commitments": {"imported": 0, "held_exceptions": 0},
            "commitment_events": {"imported": 0, "with_actor": 0, "unresolved_actors": 0},
        }

        # 1. Delegations
        raw_delegaciones = data.get("delegaciones", [])
        delegation_map = {}
        for d in raw_delegaciones:
            name = (d.get("nombre") or "").strip()
            if not name:
                continue
            scope = (d.get("ambito") or "").strip()
            status = Delegation.Status.ACTIVE if d.get("estado") == "Activa" else Delegation.Status.INACTIVE
            del_obj, created = Delegation.objects.update_or_create(
                name=name,
                defaults={"scope": scope, "status": status},
            )
            delegation_map[name.lower()] = del_obj
            if created:
                summary["delegations"]["created"] += 1
            summary["delegations"]["total"] += 1

        # 2. Positions & Staff Profiles
        raw_personas = data.get("personas", [])
        position_map = {}
        staff_map = {}

        for p in raw_personas:
            cargo = (p.get("cargo") or "").strip()
            if cargo and cargo.lower() not in position_map:
                pos_obj, created = Position.objects.get_or_create(name=cargo)
                position_map[cargo.lower()] = pos_obj
                if created:
                    summary["positions"]["created"] += 1
                summary["positions"]["total"] += 1

        for p in raw_personas:
            nombre = (p.get("nombre") or "").strip()
            cargo = (p.get("cargo") or "").strip()
            del_name = (p.get("delegacion") or "").strip()
            username = (p.get("usuario") or "").strip()
            correo = (p.get("correo") or "").strip().lower()

            if p.get("password"):
                summary["users"]["password_hashes_blocked"] += 1

            user_obj = None
            if username:
                user_obj, u_created = User.objects.get_or_create(
                    username=username,
                    defaults={
                        "email": correo,
                        "is_active": True,
                        "first_name": nombre.split()[0] if nombre else "",
                        "last_name": " ".join(nombre.split()[1:]) if len(nombre.split()) > 1 else "",
                    },
                )
                user_obj.set_unusable_password()
                user_obj.save()
                if u_created:
                    summary["users"]["created"] += 1

            pos_obj = position_map.get(cargo.lower()) if cargo else None
            del_obj = delegation_map.get(del_name.lower()) if del_name else None

            if not del_obj:
                summary["staff_profiles"]["delegation_exceptions"] += 1
            else:
                summary["staff_profiles"]["accepted"] += 1

            profile, _ = StaffProfile.objects.update_or_create(
                display_name=nombre,
                defaults={
                    "user": user_obj,
                    "delegation": del_obj,
                    "position": pos_obj,
                    "legacy_role": p.get("rol", "funcionario"),
                },
            )
            staff_map[nombre.lower()] = profile

        # 3. Period
        raw_periodo = data.get("periodo", {})
        if raw_periodo.get("inicio") and raw_periodo.get("termino"):
            p_start = datetime.strptime(raw_periodo["inicio"], "%Y-%m-%d").date()
            p_end = datetime.strptime(raw_periodo["termino"], "%Y-%m-%d").date()
            period_obj, p_created = Period.objects.get_or_create(
                starts_on=p_start,
                ends_on=p_end,
                defaults={"status": Period.Status.ACTIVE},
            )
            summary["period"]["created"] = p_created
            summary["period"]["starts_on"] = p_start.isoformat()
            summary["period"]["ends_on"] = p_end.isoformat()
        else:
            period_obj = None

        # 4. Metric Items & Staff Targets
        item_map = {}
        for p in raw_personas:
            for it in p.get("items", []):
                item_name = (it.get("nombre") or "").strip()
                if item_name and item_name.lower() not in item_map:
                    it_obj, created = MetricItem.objects.get_or_create(name=item_name)
                    item_map[item_name.lower()] = it_obj
                    if created:
                        summary["metric_items"]["created"] += 1
                    summary["metric_items"]["total"] += 1

        if period_obj:
            for p in raw_personas:
                items = p.get("items", [])
                if not items:
                    continue
                nombre = (p.get("nombre") or "").strip()
                profile = staff_map.get(nombre.lower())
                if not profile:
                    continue
                summary["staff_targets"]["staff_count"] += 1
                for it in items:
                    item_name = (it.get("nombre") or "").strip()
                    it_obj = item_map.get(item_name.lower())
                    if not it_obj:
                        continue
                    goal = Decimal(str(it.get("meta", 1)))
                    weight = Decimal(str(it.get("ponderador", 0)))
                    avance = Decimal(str(it["avance"])) if it.get("avance") is not None else None
                    StaffTarget.objects.update_or_create(
                        staff=profile,
                        period=period_obj,
                        item=it_obj,
                        defaults={
                            "goal": goal,
                            "weight_percent": weight,
                            "legacy_progress": avance,
                        },
                    )
                    summary["staff_targets"]["created"] += 1

        # 5. Commitments & Events
        raw_compromisos = data.get("compromisos", [])
        for c in raw_compromisos:
            resp = (c.get("responsable") or "").strip()
            terr = (c.get("territorio") or "").strip()

            owner_profile = staff_map.get(resp.lower()) if resp else None
            del_candidate = delegation_map.get(terr.lower()) if terr else None

            # Quarantine rule: must have confirmed owner and delegation
            if not owner_profile or not del_candidate:
                summary["commitments"]["held_exceptions"] += 1
                continue

            reg_date = date.today()
            if c.get("fecha_registro"):
                try:
                    reg_date = datetime.strptime(c["fecha_registro"], "%Y-%m-%d").date()
                except ValueError:
                    pass

            due_date = reg_date
            if c.get("fecha_compromiso"):
                try:
                    due_date = datetime.strptime(c["fecha_compromiso"], "%Y-%m-%d").date()
                except ValueError:
                    pass

            status_val = c.get("estado", Commitment.Status.INGRESADO)
            if status_val not in Commitment.Status.values:
                status_val = Commitment.Status.INGRESADO

            com_obj = Commitment.objects.filter(id=c.get("id")).first()
            if not com_obj:
                com_obj = Commitment(id=c.get("id"))
                summary["commitments"]["imported"] += 1

            com_obj.delegation = del_candidate
            com_obj.owner = owner_profile
            com_obj.origin = c.get("origen", "")
            com_obj.requester = c.get("solicitante", "")
            com_obj.territory_label = terr
            com_obj.support_area = c.get("area_apoyo", "")
            com_obj.description = c.get("descripcion", "")
            com_obj.registered_on = reg_date
            com_obj.due_on = due_date
            com_obj.status = status_val
            com_obj.note = c.get("observacion", "")
            com_obj._skip_auto_event = True
            com_obj.save()

            historial = c.get("historial", [])
            for idx, ev in enumerate(historial):
                autor_name = (ev.get("autor") or "").strip()
                actor_user = None
                if autor_name:
                    actor_profile = staff_map.get(autor_name.lower())
                    if actor_profile and actor_profile.user:
                        actor_user = actor_profile.user

                if actor_user:
                    summary["commitment_events"]["with_actor"] += 1
                else:
                    summary["commitment_events"]["unresolved_actors"] += 1

                ev_date = reg_date
                if ev.get("fecha"):
                    try:
                        ev_date = datetime.strptime(ev["fecha"], "%Y-%m-%d").date()
                    except ValueError:
                        pass

                seq = idx + 1
                if not CommitmentEvent.objects.filter(commitment=com_obj, sequence=seq).exists():
                    CommitmentEvent.objects.create(
                        commitment=com_obj,
                        sequence=seq,
                        previous_status=ev.get("estado_anterior"),
                        next_status=ev.get("estado_nuevo", com_obj.status),
                        occurred_on=ev_date,
                        occurred_at=None,
                        actor=actor_user,
                        note=ev.get("observacion", ""),
                    )
                summary["commitment_events"]["imported"] += 1

        return summary

    def print_summary(self, summary, dry_run=False):
        prefix = "[DRY-RUN] " if dry_run else ""
        self.stdout.write(self.style.SUCCESS(f"\n{prefix}SGR Relational Data Migration Complete"))
        self.stdout.write("=" * 60)
        self.stdout.write(f"Delegations:      {summary['delegations']['total']} loaded ({summary['delegations']['created']} created)")
        self.stdout.write(f"Positions:        {summary['positions']['total']} loaded ({summary['positions']['created']} created)")
        self.stdout.write(f"Staff Profiles:   {summary['staff_profiles']['accepted']} matched, {summary['staff_profiles']['delegation_exceptions']} delegation exceptions held")
        self.stdout.write(f"Auth Users:       {summary['users']['created']} created without passwords ({summary['users']['password_hashes_blocked']} raw hashes blocked)")
        self.stdout.write(f"Period:           {summary['period']['starts_on']} -> {summary['period']['ends_on']}")
        self.stdout.write(f"Metric Items:     {summary['metric_items']['total']} loaded ({summary['metric_items']['created']} created)")
        self.stdout.write(f"Staff Targets:    {summary['staff_targets']['created']} loaded for {summary['staff_targets']['staff_count']} staff")
        self.stdout.write(f"Commitments:      {summary['commitments']['imported']} canonical imported, {summary['commitments']['held_exceptions']} held outside canonical FKs")
        self.stdout.write(f"Commitment Events:{summary['commitment_events']['imported']} events ({summary['commitment_events']['with_actor']} with actor, {summary['commitment_events']['unresolved_actors']} unresolved historical)")
        self.stdout.write("=" * 60 + "\n")
