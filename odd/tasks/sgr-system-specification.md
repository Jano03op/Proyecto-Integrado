# T1 — Specify the SGR system from primary evidence

**Status:** Specification authored and documentation checks performed; closure/commit pending. **Route:** delegated direct. **Delivery strategy:** ask-on-risk. **Commit evidence:** pending; no branch or commit created in this stage.

## Objective and reason

Produce a detailed, usable SGR system specification that lets a reader recreate the intended system and identify defensible improvements. The original presentation conveys workflows and screens visually; the project guide and backend evaluation add requirements and assessment context. A source-traceable document is needed so visual intent, stated requirements, and current implementation are not conflated.

## Scope and boundaries

- This task's deliverable is a documentation-only specification; stage 1 created **only this task record**. After the parent mirrored the task to Engram, stage 2 authored `docs/sgr-system-specification.md`.
- Describe intended roles, capabilities, entities, workflows, reporting/indicators, permissions, validation, and prioritized improvements where supported by evidence. Distinguish explicit source requirements, screenshot-based interpretation, current repository behavior, and proposals.
- Do not implement or modify application source, run remote operations, publish credentials, or expose secrets. Do not reproduce personal names, phone numbers, or identification numbers visible in slide screenshots.
- Avoid promising behavior unsupported by the PDFs; mark unclear or conflicting details as open questions with provenance.

## Primary evidence and provenance plan

| Source | Location | Required use |
| --- | --- | --- |
| Original presentation, 20 pages including images | `PRESENTACIÓN  MATRIZ  REGIMIENTO RESULTADO.pdf` | Inspect text **and images**; cite PDF page numbers for each sourced screen, process, matrix, and visual inference. |
| SGR student project guide, 30 pages | `Guia_Proyecto_Software_SGR_Alumnos.pdf` | Cite PDF page numbers beside requirements and constraints; reconcile with presentation. |
| Backend evaluation | `Eva Sumativa 2.pdf` | Cite PDF page numbers for relevant evaluation criteria; do not present assessment criteria as implemented features. |
| Local repository | `.` | Compare intended system against observed Django code, labeling existing behavior separately; cite paths/symbols, not speculative functionality. |

Page provenance here identifies each primary source; the external, user-supplied PDF paths are available in the conversation rather than embedded in this repository. Feature-to-page citations were filled from inspected PDFs in the specification. The backend evaluation has 10 PDF pages as verified in stage 2.

## Acceptance criteria

- [x] The document provides an executive summary, domain glossary, actor/permission matrix, workflows, conceptual data model, functional and nonfunctional requirements, indicator/reporting rules, gaps, improvements, and open questions in a navigable structure.
- [x] Screenshots were inspected directly across all 20 original pages; visual observations are attributed to exact PDF page numbers and distinguished from text or inference.
- [x] Substantive external-source claims carry page citations; repository-state claims identify inspected paths. Conflicts and unresolved decisions are explicitly called out.
- [x] Examples omit real personal contact details, identification numbers, credentials, and other sensitive data.
- [x] Improvements are labeled proposals, prioritized by value/risk, with acceptance-oriented descriptions; no invented requirement is silently treated as fact.
- [x] Documentation changes alone were made; no app code, remote operation, or secret-bearing artifact was written as part of this work unit.

## Verification and delivery evidence

**TDD mode:** not applicable to documentation-only task. **TDD source/runner:** not applicable. This says nothing about project-wide TDD settings.

Documentation-only checks in stage 2: read back all 266 numbered document lines after the baseline clarification; inspected heading coherence, citations and privacy against PDF text/images. `git diff --check`: exit 0, no output; `git diff --stat`: exit 0, no output because the files are untracked and this repository has no tracked baseline; `git status --short`: exit 0 and includes `?? docs/`, `?? odd/` plus pre-existing untracked project paths. The Git checks were repeated after the document clarification, with the same results. Because these files are untracked, `git diff --check` does **not** validate their whitespace; visual readback is the documentation-only check here. No configured Markdown linter was found (`.markdownlint*`, `package.json`, `pyproject.toml`, `.pre-commit-config.yaml` checked); skipped. Focused automated tests and runtime harness: N/A because no executable behavior changed.

Forecast: approximately **300–400 authored lines** for the substantive specification, plus this task record. Track authored additions/deletions before review; under **ask-on-risk**, ask the parent/user for a review-slicing decision if the work exceeds the review budget rather than compressing essential evidence. Route is **delegated direct** because the visual-source research is long and the full work unit comprises two nontrivial files (task record and detailed document). Keep task and specification as one coherent documentation work unit if reviewable. Rollback boundary: remove only the task record and later specification; no application behavior should change. Branch and conventional work-unit commit are future closure steps, not authorized in this stage; commit identity remains pending.

## Progress and next step

Stage 1: task record created and read back; parent mirrored it to Engram. Stage 2: 20-page presentation, 30-page guide and 10-page evaluation read; `docs/sgr-system-specification.md` authored, clarified and read back end-to-end, with checks recorded above. Stage 2b: replaced machine-local source paths in this task with portable basenames and `.`; documented delegation scoping for commitments in the specification and its conceptual MER (O p.13; G pp.6–8). Checks after the edits: `git diff --check` exit 0/no output; `git diff --stat` exit 0/no output; `git status --short` exit 0 with `?? docs/` and `?? odd/` among existing untracked paths. Both files remain untracked, so Git diff does not cover their contents. **Next:** parent updates the task mirror and decides review/closure. Commit identity remains pending; no branch or commit was made in this stage.
