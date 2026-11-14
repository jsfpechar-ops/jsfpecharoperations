# 1525: Property settings pages that wait for the host layout shell (alert stack in v2 pages, housebook CSV menu)

Status: blocked — the read-only layout `go/internal/hostweb/layout` cannot render what these pages need
Depends on: see §2 | Base commit: current branch (One big PR mode) | Branch: current branch
Executor: none until unblocked | Tier B (A where §2 says)

> **One big PR mode.** The owner wants one big pull request. You work on the current branch: commit `1525 step k` after each step that changes a file, never create a branch, never push, never open a PR. The orchestrator merges. Acceptance below does not depend on a base commit: it uses `git log --oneline --grep='^1525 step'` and `git show --stat` on those commits.

## 1. Objective

Serve `GET /housebook`, `GET /settings`, the six `GET /settings/<group>` routes and the "host has an open alert" branch of `GET /entities` on Go. None can be ported inside the rules: each needs a change in `go/internal/hostweb/layout/`, which is read-only for this thread.

## 2. Context

Gaps found by reading the layout (not worked around):

1. **Alert stack in v2 pages.** `entities.html` (line 16), `settings.html` (line 11), `settings_archived.html`, `reservations.html` include `_host_alerts.html` in their own body, because `base.html` line 86 skips it for v2 pages. Go's `layout.go` (around line 625) builds `v.Alerts` only when `!(HideAlertStack || V2)`, and a page template cannot reach it: the page data is its own struct, `layout.host_alerts` reads `.Alerts` of the shell data. Needed from the layout owner: a `Page` flag (for example `AlertsInBody`) that builds the stack for a v2 page, plus a way for the page template to include `layout.host_alerts` (for example the stack passed in the page data or a func `host_alerts`). Today `GET /entities` answers 501 for a host with an open alert (`go/internal/web/properties/lists.go`, `notPorted`), and that branch must stay until this is done.
2. **`housebook_csv_menu` macro.** `housebook.html` (line 6) imports it; `go/internal/hostweb/layout/macros_components.go` lists it as "not ported yet". Also `date_range` (`_date_range.html`) is not a layout func. Needed: both macros in the layout.
3. **Data for `/housebook`** (not a layout gap): `housebook.housebook_rows` decrypts guest data; Go has the row builder only inside `go/internal/web/exports` (CSV, private functions). A new file in `exports` exporting the rows would be needed (new file only; the exports thread owns the package). Guest personal data: hard rule 2 review.

Python for the later brief: `housebook_view` admin.py 5181-5213, `housebook.py` 76-235, `templates/housebook.html` (216 lines); `settings_view` and `_settings_page` admin.py 5287-5392 (about 100 lines), `templates/settings.html` (514 lines), `settings_archived.html` (188 lines).

**Paths.** `/entities` (exact) cannot be switched to Go until gap 1 is closed: a host with an open alert would get 501. `/settings`, `/settings/*`, `/housebook` stay on Python.

## 3. Files

None until unblocked.

## 4. Steps

None. Unblock by: (a) a layout brief that closes gaps 1 and 2, (b) a decision on gap 3. Then the orchestrator writes the port briefs (settings page and its six groups: about 700 lines of Go and template; housebook page: about 500).

## 5. Do not touch

Everything. `go/internal/hostweb/` is read-only.

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

1. Decide who changes the layout (gaps 1 and 2) and when.
