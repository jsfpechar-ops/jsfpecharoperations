# 1527: Property pages (list with properties, new, create, detail, update and the small property POSTs)

Status: blocked — the property page is one large view built on the setup guide, filing readiness and the lock; it needs a plan and a layout check first
Depends on: see §2 | Base commit: current branch (One big PR mode) | Branch: current branch
Executor: none until unblocked | Tier B (A where §2 says)

> **One big PR mode.** The owner wants one big pull request. You work on the current branch: commit `1527 step k` after each step that changes a file, never create a branch, never push, never open a PR. The orchestrator merges. Acceptance below does not depend on a base commit: it uses `git log --oneline --grep='^1527 step'` and `git show --stat` on those commits.

## 1. Objective

Serve on Go: `GET /apartments` for a host with a live property, `GET /apartments/new`, `POST /apartments`, `GET /apartments/{id}`, `POST /apartments/{id}`, `POST /apartments/{id}/door-codes`, `POST /apartments/{id}/automation-timing`, `POST /apartments/{id}/feeds`, `POST /apartments/{id}/test-connection`, `POST /apartments/{id}/police-letter`, `POST /apartments/{id}/refresh-codelists`, `GET /apartments/ruian-suggest`.

## 2. Context

Why blocked (checked against the Python and the Go code, nothing was ported):

- **One page behind everything.** `apartment_detail` (admin.py 1857-2160), `_render_apartment_detail`, `_property_view_state`, `_setup_guide_bundle`, `_setup_progress`, `_property_copy_form_context` and the templates `_property_editor.html` (519 lines), `_property_calendars.html`, `_property_create.html`, `_setup_ready_card.html`, `_copy_settings_dialog.html`, `_police_fields.html`, `_stay_fee_fields.html` (149), `_smart_locks_panel.html` and more render the whole property: setup guide state (`property_setup.py`, 494 lines), filing readiness and validation issues (`_apartment_issues`, `_readiness`), UbyPort credentials and codelists, the TTLock panel, stay-fee rates and the guest-link state. Every failing POST (`add_feed` 400, `apartment_update`, `automation_timing_save`, `door-codes`, `apartment_create` refusal) re-renders this page or the onboarding wizard. A port of any of them needs the page.
- **Filing-adjacent.** `apartment_create` and `apartment_update` store the UbyPort web-service password (encrypted) and police defaults; `test_connection`, `police_letter_read` and `refresh_codelists` call UbyPort or an AI reader. Anything that files to the police is out of this thread.
- **Outbound clients missing in Go:** RUIAN lookup (`ruian_lookup.py`) for `ruian-suggest`; the TTLock client (brief 1526).
- **Go today.** `GET /apartments` answers 501 for any workspace with a live property (`lists.go` `notPorted("the property list")`). **If `/apartments` is routed to Go on the server, every host with a property gets 501: report this to the owner.** `POST /apartments` is Python only.
- The layout gap of brief 1525 (alert stack in v2 pages) also applies if the property list page includes the alert stack.

**Paths.** `/apartments` (exact) cannot be switched until both methods and the live-property list are ported; `/apartments/*` stays on Python; the exact paths `/apartments/{id}/archive`, `.../unarchive`, `.../regenerate-pin`, `.../regenerate-link` (brief 1300) are Go-ready only as exact paths, so do not switch a `/apartments/*` prefix.

Python for the later plan: admin.py 1333-1857 (list, new, create), 1857-2500 (detail), 2496-2640 (door codes, update), 3075-3137 (automation timing), 3324-3441 (feeds), 3444-3686 (test-connection, police-letter, refresh-codelists).

## 3. Files

None until unblocked.

## 4. Steps

None. Unblock by a tier A plan (docs/plans) that splits the property page: first the read-only detail view with its readiness and setup-guide inputs, then each POST with its re-render, then the list. The plan decides who owns the filing-adjacent parts (the filing lane, not this thread).

## 5. Do not touch

Everything.

## 6. Commands

None.

## 7. Acceptance

None.

## 8. Stop and ask

Do not run this brief.

## 9. Report

None.

## Risk list (for the reviewer)

Not applicable.

## Owner steps

1. Check on the server whether `/apartments` is in `UBYHOST_GO_PATHS`; if it is, remove it (hosts with a property get 501 from Go).
2. Ask for the plan brief when the filing lane is done.
