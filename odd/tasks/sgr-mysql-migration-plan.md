# T1 — Write a privacy-safe staged MySQL migration plan

**Status:** Stage 2 plan drafted and read back; review and commit remain with the parent. **Route:** delegated direct: reading the approved MER prepared one documentation write, with this task and the plan forming one reviewable work unit. **Delivery strategy:** ask-on-risk; 400 authored changed lines is a review advisory, not a cap. No commit, PR, or implementation is claimed.

## Objective and reason

Produce `docs/sgr-mysql-migration-plan.md`, a source-traceable plan for moving the four currently JSON-backed SGR modules to the approved first-delivery MySQL relational core. The plan must make data reconciliation, privacy, irreversible MySQL DDL, validation, cutover, and restoration gates explicit before anyone implements or runs a migration. This task authorizes documentation **only**.

## Scope and sources

- Stage 1 writes **only this task record**. Pause after readback so the parent can mirror the complete task before authorizing any plan-document write.
- Use `docs/sgr-backend-mysql-mer.md` as the approved nine-entity/ten-FK design and legacy mapping; consult only targeted requirements in `docs/sgr-system-specification.md` if necessary. Distinguish approved product policy, proposed implementation steps, observed aggregate audit findings, and unverified assumptions.
- The prior authorized, in-memory audit may be cited **only as aggregates**: 10 persons, 6 delegations, 10 commitments, 33 items, 25 history entries and one period; unresolved identity, owner, actor, territory, weight and transition issues need reconciliation. Do not copy record values. Refer to the approved MER's restricted exceptions workflow rather than exposing a mapping table.
- No Django code changes, migration generation/execution, DB connection, JSON writes, exports, remote/AWS operations, credential access, or inspection of `datosarray.json` or `credenciales_prueba.txt`. Use portable repository-relative paths only. Treat the dataset's synthetic status as **unverified**.

## Acceptance checklist for the future plan

- [x] Document prerequisites and gates: approved access and backup/restore location, MySQL/InnoDB/version/driver/config checks, identity and catalog reconciliation, privileges, private dry-run exceptions, and stakeholder decisions. Existing service/binary availability is not a successful Django database connection or migration. **Documented, not executed.**
- [x] Sequence schema preparation, read-only/restricted mapping, dry-run import, count/FK/date/weight/history validation, credential provisioning and server-side authorization, rehearsal, cutover, monitoring, and restore-based rollback. Explicitly separate proposed steps from completed work and require new authorization before executing any step. **Documented, not executed.**
- [x] Reconcile nullable historical actors without assigning them permissions; do not infer delegation FKs from territory labels, match names blindly, invent dates/timestamps, or copy existing password hashes. Require fresh securely provisioned credentials. Keep imported progress provisional and unresolved rows outside canonical required-FK tables. **Documented policy, not resolved records.**
- [x] Preserve all nine observed historical transitions (six forward jumps, two backward, one repeated) in ordered legacy history with explicit exception reporting; apply strict new-event transition policy only to **new** events. Verify parent status and append-only chronology without rewriting history. **Documented future check, not an import.**
- [x] Define safe pass/fail criteria and abort gates for totals, links, status, periods, duplicate catalog labels and weight sets, with restricted reporting; do not imply all links or weights already pass. MySQL DDL is not transactionally reversible: require a tested backup and restore rehearsal before cutover; do not promise a schema rollback by transaction alone. **Documented future gate; no restore performed.**
- [x] Cite the MER and targeted repository/official documentation for technical claims, avoid personal data and local absolute paths, and explicitly disclaim DB state changes, actual tests, imports, AWS deployment or implemented authorization. **Manual documentation readback only.**

## Verification and delivery boundary

**TDD mode/source/runner:** N/A, documentation-only. **Focused tests/runtime harness:** N/A; no executable behavior is changed. After each authorized write, read the whole artifact back; check citations against the approved design and authorized aggregate audit, inspect for personal data, secrets and absolute local paths, and have the parent inspect the exact staged paths and run `git diff --cached --check` **after staging**. An unstaged diff check cannot validate untracked files. Do not stage, commit or switch branches in this delegated stage. If the review slice approaches 400 authored changed lines, ask the parent before slicing; never compress necessary documentation just to meet an advisory.

**Rollback boundary:** remove this task record and the future `docs/sgr-mysql-migration-plan.md` documentation work unit without touching application code or data. The future operational plan must separately specify backup/restore checkpoints for irreversible MySQL schema operations; a documentation revert does not restore a database.

## Progress and handoff

- Stage 1: task record authored and read back; parent reports mirroring the complete task before authorizing this stage-2 plan write. No plan document was written in stage 1.
- Stage 2: wrote and read back `docs/sgr-mysql-migration-plan.md` (76 lines). Inspected approved MER and targeted specification, checked aggregate claims against the earlier authorized audit, and checked plan boundaries for private values/absolute paths. Only this plan and this task record were edited; no code, raw source, credentials, local database or remote target was accessed. Focused tests and runtime harness: **N/A**, documentation-only; no MySQL connection, migration, import or backup was performed. `git diff --check` and `git diff --stat` produced no output; because both documents remain **untracked**, these commands did not validate their contents. `git status --short` reports both documents untracked among pre-existing untracked paths; branch remains `feature/sgr-mysql-migration-plan`. Parent must inspect exact staged paths and run `git diff --cached --check` after staging. No staging or commit by this writer.
- Next: parent mirrors the full updated task and reviews the plan for privacy and policy accuracy before any documentation work-unit commit. Any operational step needs a separate authorization and its own evidence.
