# Evaluation 2 technical report — evidence source

This Markdown document is a source for the required PDF or Word submission, **not** an exported PDF/Word or a completed evidence package. The current deployment is a private EC2 demonstration through an SSH tunnel, not a public production site. The older repository snapshot in `docs/sgr-system-specification.md` (lines 216–228) is a planning baseline, not a description of this deployment.

## Decision and rubric exception

The owner chose to retain `CommitmentEvent` as append-only audit history. Its `save()`/`delete()` reject changes to existing events (`agenda/models.py:289-301`); the Admin inline disallows adding, changing and deleting events, and the event Admin exposes read-only records and search (`agenda/admin.py:7-28,89-122`). Creating a `Commitment` creates its initial event automatically (`agenda/models.py:170-208`). Tests cover event immutability and Admin permissions (`agenda/tests.py:174-201,362-384`). This prevents routine Admin edits from rewriting or erasing an audit trail.

**Rubric mismatch:** `Eva Sumativa 2.pdf` p.5 requires create/edit/delete/view/search in Django Admin for **every modeled entity**. `CommitmentEvent` is modeled but does **not** offer direct Admin create/edit/delete; therefore literal all-entity Admin CRUD is **not met**. This is an owner-accepted exception with a grading risk, **not** instructor approval or a guarantee of credit. No soft-delete substitute or claim of full Event CRUD is proposed.

**Demonstration path:** In Django Admin, create a synthetic Commitment, then inspect its automatically created Event in the read-only inline or searchable Event list/detail. Show that the event cannot be added, edited or deleted there. Demonstrate permissible Commitment operations separately; they do not satisfy Event CRUD.

## Verified state and evidence to package

The following is the previously verified aggregate state recorded in `odd/tasks/eval2-ec2-no-docker.md`; it is not a fresh EC2 check by this documentation edit. Use screenshots and reproducible observations in the final submission (technical document and AI evidence: `Eva Sumativa 2.pdf` pp.8–9).

| Area | Verified state | Still needed for submission |
| --- | --- | --- |
| Cloud and GitHub | GitHub clone on EC2 checked out on `feature/eval2-ec2-deployment`; remote Git tree clean at last check. | Capture sanitized EC2/runtime and clone/branch/history screenshots; recheck branch and revision at capture time. |
| Relational database | 18 migrated tables, 19 foreign keys, 22 applied migration rows. Synthetic Admin records: 1 superuser, 1 Delegation, 1 Position, 2 StaffProfiles, 1 Period, 1 MetricItem, 1 StaffTarget, 1 Commitment and 1 automatically created Event. Nine Admin add-log entries; three checked orphan-FK counts are zero. | Capture sanitized schema/migration and phpMyAdmin table, relationship and synthetic-record screenshots. Do not infer all relationships were tested from three checks. |
| Private UI | App/Admin via localhost:8001 and phpMyAdmin via localhost:8080 using a private SSH tunnel; no public site claim. | Capture sanitized Admin creation, Commitment/Event read-only behavior and private app/phpMyAdmin views. Tunnel access is temporary. |
| Delivery and security | `manage.py check --deploy` does **not** pass: `mail.E001` for console mail backend and HTTPS/HSTS/secure-cookie warnings `W004/W008/W012/W016`. | Do not present this as production-ready or public HTTPS. Capture actual check output without secrets if relevant. |
| AI use and export | No AI prompt/response evidence or PDF/Word export captured for this report. | **Pending:** insert actual prompts, responses and applied changes with provenance; never invent a transcript. Remove credentials, personal data, private JSON and identifying records from all evidence. Export the completed report to PDF or Word and verify the export. |

The screenshots, AI transcript and final PDF/Word file remain pending. Keep synthetic data only, redact before sharing, and record capture dates/paths in the submitted artifact rather than treating this checklist as proof.
