# T1 — Establish agenda commitment and history ORM foundations

**Status:** T1 implemented and functionally verified locally; delivery pending. **Branch:** `feature/sgr-indicator-orm`. **Route:** direct; work-unit verification completed. **Delivery strategy:** ask-on-risk. Work-unit commit and staging are pending; no staging or commit performed.

## Problem, purpose, and scope

The `agenda` module currently relies on JSON persistence (`datosarray.json` under the `compromisos` key) and in-memory list operations. According to the approved first-delivery MER (`docs/sgr-backend-mysql-mer.md`) and migration plan (`docs/sgr-mysql-migration-plan.md`), Agenda requires a relational foundation consisting of two core entities:
1. `Commitment`: scoped to a mandatory `Delegation` and owned by a mandatory `StaffProfile`, tracking origin, requester, territory label, support area, description, registered/due dates, sequential status progression (`Ingresado -> Pendiente -> En proceso -> Realizado`), and notes. The owner is immutable after creation in this release. No period FK: due dates and agenda calculations remain independent of period closure. Overdue state is derived dynamically from `due_on`, `status`, and reference date.
2. `CommitmentEvent`: ordered history maintained with sequence numbers per commitment (`UNIQUE(commitment, sequence)`), tracking previous and next statuses, nullable actor (auth User, allowed null only for unresolved legacy imports; required on new events), date/datetime timestamps (`occurred_on` as date, `occurred_at` as timestamp reserved for new events), and notes. Events are append-only; modification and deletion are disallowed.

**Authorized scope:** `agenda/models.py`, `agenda/admin.py`, `agenda/migrations/0001_initial.py`, `agenda/tests.py`, and this task. No JSON import, no MySQL/AWS connections, no modification of existing SQLite database outside the isolated test runner.

## T1 acceptance criteria (local implementation)

- [x] `Commitment` models mandatory protected FKs to `Delegation` and `StaffProfile`, source text/date fields, status choices matching canonical order, dynamic overdue check, fixed-owner enforcement on update, single-step forward progression enforcement, and authorized backward transition/reopening guard requiring reason and coordinator/manager role.
- [x] Initial `CommitmentEvent` is created atomically on new commitment creation. Status changes record atomic append-only `CommitmentEvent` rows with incremented sequence numbers.
- [x] `CommitmentEvent` models `commitment`, nullable `actor` (`settings.AUTH_USER_MODEL`), `sequence`, `previous_status`, `next_status`, `occurred_on`, `occurred_at`, and `note`. Enforces `UNIQUE(commitment, sequence)`. Rejects edits and direct deletions. Rejects new events with `occurred_at` but no authenticated actor.
- [x] Board completion rate calculation method implements the approved display rule: `100 * (Realizado / total)` for commitments due within the inclusive range; returns `None` (representing N/A) when denominator is zero.
- [x] Django Admin registers `Commitment` with search, filters, autocomplete fields, overdue badge, and read-only inline event history. Admin registers `CommitmentEvent` as read-only audit log with disabled add/change/delete permissions. Bulk actions are disabled on both admins to protect transition and audit invariants.
- [x] Initial migration `0001_initial.py` generated with dependencies on `cuentas`, `organizacion`, and `auth.User`. `makemigrations --check --dry-run` confirms clean state with no drift.
- [x] Isolated test suite in `agenda/tests.py` passes 15 focused tests covering creation, transitions, invalid jumps, backward guard, owner immutability, overdue derivation, board completion rate, event immutability, sequence uniqueness, actor validation, and Admin operations/permissions.

## Stage verification receipt

Environment variables: temporary process-only `SECRET_KEY=check-only-not-a-secret`, `DB_BACKEND=sqlite`, `DEBUG=False`, `ALLOWED_HOSTS=localhost`.
- `python -B manage.py check`: exit 0, `System check identified no issues (0 silenced).`
- `python -B manage.py makemigrations agenda`: exit 0, generated `agenda/migrations/0001_initial.py`.
- `python -B manage.py makemigrations --check --dry-run`: exit 0, `No changes detected`.
- `python -B manage.py test agenda`: exit 0, `Ran 15 tests in 13.185s`, `OK`.
- Full suite `python -B manage.py test organizacion cuentas indicadores agenda`: exit 0, `Ran 32 tests in 24.825s`, `OK`.

## Explicit path inventory

- `agenda/models.py`
- `agenda/admin.py`
- `agenda/migrations/0001_initial.py`
- `agenda/migrations/__init__.py`
- `agenda/tests.py`
- `odd/tasks/sgr-agenda-orm.md`
