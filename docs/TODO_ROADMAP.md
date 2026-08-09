# TODO_ROADMAP.md
# DayZTrader / DXEMB — Local Release Roadmap

This roadmap is the working implementation plan for a safe, testable final local release.

Source-of-truth priority:
1. `dxemb/shared/catalog/data/project_progress.json`
2. `docs/PROJECT_PROGRESS.md`
3. `docs/LOCAL_FINISH_RECOVERY_PLAN.md`
4. `docs/MASTER_HANDOFF.md`
5. `docs/PROJECT_CONTINUITY.md`
6. supporting audit/review docs under `docs/`

If this roadmap drifts from those sources, update this file to match verified repository evidence rather than planning assumptions.

---

## Current Baseline

- Active branch: `feature/local-finish-ui-recovery`
- Current head checkpoint: `70b0be2` — `Add blocked Truck_01 compatibility review mappings`
- Recent verified local-finish checkpoints:
  - `88768e4` — `assets: audit DayZ images and console vehicle variants`
  - `3678bc9` — `ui-sliceB: restore trader thumbnail catalog workflow`
  - `e43aa25` — `restore verified DayZ visual foundation`
  - `9b1b4f7` — `docs: add local finish UI recovery plan`
- Current progress source: `dxemb/shared/catalog/data/project_progress.json`
- Current overall local-finish progress: `41%` with `medium` confidence per `docs/PROJECT_PROGRESS.md`
- Immediate documentation priority after this roadmap update: Phase 1 local app health and runbook

---

## Roadmap Status Table

Allowed phase statuses:
- `not_started`
- `discovery`
- `planned`
- `in_progress`
- `implemented_unverified`
- `locally_tested`
- `owner_review_required`
- `complete`
- `intentionally_disabled`
- `blocked`

| Phase | Status | Evidence Anchor | Next Step |
|---|---|---|---|
| Phase 0 — Repository baseline | `locally_tested` | branch/history checks, continuity docs, clean baseline workflow in current local-finish branch | Keep baseline reproducible before each implementation slice |
| Phase 1 — Local app health | `locally_tested` | README, `.env.example`, `docker-compose.yml`, verified `docker compose up -d db web`, `/`, `/catalog`, `/vehicles`, Slice A/B route tests | Move to catalog-integrity validation with the current startup/runbook baseline |
| Phase 2 — Catalog integrity | `in_progress` | Slice B tests, catalog templates/routes already locally tested, thumbnail fallback workflow restored | Document/verify data-first catalog repair workflow and critical catalog validation steps |
| Phase 3 — Vehicle visuals | `implemented_unverified` | vehicle list/builder surfaces exist, fallback image behavior present, audit docs generated | Reconcile visual data sources and explicitly document fallback expectations |
| Phase 4 — Console compatibility review | `blocked` | fail-closed review JSON and owner queue docs exist; owner evidence still required | Continue family-by-family blocked review using exact evidence locators only |
| Phase 5 — Vehicle-builder integration | `blocked` | builder UI exists but compatibility must remain fail-closed | Trace reviewed compatibility into builder data without making blocked rows selectable |
| Phase 6 — Admin editing workflow | `planned` | owner-edit patterns partially documented across audit/progress docs | Consolidate data-only owner workflow for names, overrides, images, and compatibility reviews |
| Phase 7 — Local acceptance testing | `planned` | targeted suites exist, no concise final acceptance checklist yet | Create one local release acceptance checklist and runbook |
| Phase 8 — Final edits and release candidate | `not_started` | no owner-approved release candidate workflow yet | Prepare release checklist only after Phases 1–7 satisfy exit criteria |

---

## Phase 0 — Repository baseline

Status: `locally_tested`

Goals:
- Confirm active branch, recent commit checkpoint, worktree state, and source-of-truth docs.
- Keep one reproducible baseline before any implementation slice.
- Ensure there are no unexplained changes before claiming a new phase advance.

Required checks:
- `git branch --show-current`
- `git status --short`
- `git log --oneline -5`
- identify the primary planning/progress documents before editing anything

Exit criteria:
- reproducible baseline is documented
- current source-of-truth documents are identified
- no unexplained changes remain in the worktree for the intended slice

---

## Phase 1 — Local app health

Status: `locally_tested`

Goals:
- Identify app entry points, dependencies, environment variables, services, startup command, stop command, test commands, and core routes.
- Verify `/`, `/catalog`, and `/vehicles` load locally.
- Turn current verified commands into a single owner runbook.

Known anchors:
- `docker-compose.yml`
- `README.md`
- `.env.example`
- `requirements.txt`
- tests: `tests/test_web_visual_foundation_slice_a.py`, `tests/test_catalog_thumbnail_workflow_slice_b.py`

Verified local baseline:
- startup command: `docker compose up -d db web`
- stop command: `docker compose down`
- verified routes: `/`, `/catalog`, `/vehicles`
- verified local URL: `http://localhost:5000`
- verified tests: `python -m unittest tests.test_web_visual_foundation_slice_a tests.test_catalog_thumbnail_workflow_slice_b`

Exit criteria:
- local startup command is documented
- local stop command is documented
- smoke routes `/`, `/catalog`, and `/vehicles` are documented and passing
- relevant test commands are documented and passing

---

## Phase 2 — Catalog integrity

Status: `in_progress`

Goals:
- Validate catalog source data, display names, categories, enabled state, prices, thumbnail fallback behavior, duplicates, and missing mappings.
- Prefer data fixes and existing overrides over UI rewrites.

Working rules:
- repair data and overrides first
- preserve current routes/templates unless a narrow bug fix is required
- treat fallback thumbnails as honest placeholders, not errors to hide

Exit criteria:
- no obvious broken catalog cards in current local app
- no unresolved critical catalog-data issue blocking local use
- critical fallback and thumbnail behavior are documented and validated

---

## Phase 3 — Vehicle visuals

Status: `implemented_unverified`

Goals:
- Reconcile vehicle manifest, body thumbnails, color variants, part thumbnails, resolver outputs, and overrides.
- Keep missing or unverified images visible as fallbacks.
- Do not invent thumbnail-to-part matches.

Working rules:
- compare manifest, resolver final, overrides, and review JSON before changing vehicle data
- prefer truthful missing-image states over guessed visual completeness

Exit criteria:
- vehicle list and builder both show honest, usable visual fallback behavior
- manifest/resolver/override differences are documented
- no guessed part-to-image pairing is introduced

---

## Phase 4 — Console compatibility review

Status: `blocked`

Goals:
- Build the authoritative fail-closed compatibility data family by family.
- Never infer compatibility from image names, generic aliases, archive JavaScript, family assumptions, or color suffixes.
- Keep all uncertain records blocked.

Required review state for uncertain records:
- `approved_status: owner_review_required`
- `selection_state: blocked`

Working rules:
- use truthful evidence source paths and exact locators
- exclude cargo/loadout items from repair-part mappings
- do not promote evidence to live approval without owner review and verified source records

Exit criteria:
- every builder-relevant vehicle, variant, and slot is explicitly approved or explicitly blocked
- every blocked row has an evidence or review reason
- no uncertain compatibility row becomes selectable or purchasable

---

## Phase 5 — Vehicle-builder integration

Status: `blocked`

Goals:
- Trace how compatibility and resolver data become builder data.
- Confirm blocked records cannot become selectable, purchasable, or silently approved.
- Preserve existing templates and routes unless a narrowly justified change is required.

Working rules:
- prefer data-only enforcement when possible
- if builder display cannot surface a blocked state without code changes, document that limitation before changing templates

Exit criteria:
- builder clearly reflects approved, blocked, missing-image, and unknown states
- blocked rows remain non-selectable and non-purchasable
- any required code change is narrow, justified, and validated

---

## Phase 6 — Admin editing workflow

Status: `planned`

Goals:
- Document safe owner workflows for display names, images, variants, overrides, compatibility evidence, review approval, validation, commit, and rollback.
- Prefer data-only maintenance wherever possible.

Exit criteria:
- owner can perform routine data maintenance without editing application code
- validation and rollback steps are documented
- commit hygiene and JSON validation steps are explicit

---

## Phase 7 — Local acceptance testing

Status: `planned`

Goals:
- Run relevant automated tests, JSON validation, startup checks, route smoke tests, error and empty-state checks, and a visual walkthrough.
- Create a concise acceptance checklist.

Exit criteria:
- a concise local acceptance checklist exists
- relevant automated and manual local checks are documented and passing
- release-candidate blockers are explicit

---

## Phase 8 — Final edits and release candidate

Status: `not_started`

Goals:
- Review final changes, confirm clean Git state, prepare changelog/runbook/rollback instructions, and create a stable final commit or release branch only with explicit owner approval.

Exit criteria:
- reproducible local release candidate is ready for owner testing
- rollback and changelog notes exist
- final commit or release branch is prepared only with owner approval

---

## Implementation Rules

- Preserve existing IDs, classes, routes, data models, schemas, and templates unless explicitly asked to redesign.
- Prefer the biggest cohesive safe slice, not tiny busywork and not broad uncontrolled changes.
- Before each implementation, report target files, intended outcome, validation plan, and what will not change.
- After each implementation, run applicable validation and report changed files, test results, blockers, and the next recommended phase/task.
- Always run `git diff --check` for edits.
- Validate JSON files after JSON edits.
- Never introduce UTF-8 BOMs, broad formatting churn, or unrelated line-ending changes.
- Never commit unless explicitly instructed.
- If a task needs live-server testing, implement only the safe review-required/blocked state and list the remaining live verification as a later owner task.
- Keep this roadmap updated with the allowed phase statuses listed above.

---

## Immediate Next Recommended Task

Current repository evidence supports this next task:
- Phase 2 catalog integrity

Target outcome:
- validate catalog data integrity and fallback behavior without redesigning routes or templates

What will not change in that phase:
- no route redesign
- no schema rewrite
- no live-service changes
- no compatibility approvals

---

*End of TODO_ROADMAP.md*
