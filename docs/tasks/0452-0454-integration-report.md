# 0452 + 0454 integration report — remaining handoff plan

Status: review. One pull request for the remaining handoff content; no merge, deploy or production access.

## Scope and base

Applies the remaining manifest content from
`docs/plans/postgresql/ubyhost-handoff/current-files/` on top of current `main`
(`1f31d41a`). Bundle recorded base `8b5317d0` was verified present and all 48
manifest SHA-256 hashes matched at source. The bundle was not applied wholesale:
its guest changes are superseded by merged PR #583, and 0455/0456 PostgreSQL
drafts remain blocked.

- **0452 read-only billing extract** — `App/app/db.py` gains
  `readonly_cursor()` (SQLite URI `mode=ro`, one deferred transaction, no
  `_open()`/chmod/journal-mode changes); `App/scripts/export_billing_analytics.py`
  is new; new tests `test_db_readonly_cursor.py` and
  `test_billing_analytics_export.py`.
- **0454 host UX** — `.entities-page td.row-actions` wraps instead of
  overflowing; the secondary-nav landmark follows its visible links (Guide for
  host, Guide / Admin for admin); `host.css` cache key bumped; new host-nav test
  and an entities-lane geometry test at 390/820/1024/1180/1280 in en/cs/vi.
- Revised plans and the bundle's context updates: `docs/context/decisions.md`,
  `known-issues.md`, `prompts.md`, `rules.md`, `status.md` (rewritten for the
  current merge state), `workflow.md`.
- Task briefs/reports/screenshots for 0451, 0452, 0453, 0454, 0455 and 0456,
  including the 0453 evidence screenshots. 0455/0456 documents stay marked
  blocked; their runtime/operations draft patches are **not** applied.
- **Superseded, not overwritten:** the bundle's guest templates/routes/i18n and
  `_email_purpose_help.html` describe the pre-merge implementation; merged PR
  #583 already ships save-and-continue, visible acknowledgement and its own
  contextual help, so those files stay at the merged version. The bundle's
  0451 screenshots are replaced by the merged #583 evidence.
- **Not included:** the unreviewed PostgreSQL 0455/0456 runtime and operations
  patches (`handoff/UNREVIEWED-*.patch`); they are explicitly blocked and are
  not manifest files.

## Source verification for 0452

The extract contract was checked against the current source, not the bundle
claims: `platform_invoice.total_haler` is an integer, `voided` and `paid_on` are
the source status/paid-date columns, the invoice table has no currency column,
and portfolio amounts come from `billing.quote()` with per-account monthly
rounding. The extract opens one read-only transaction, bounds the month range,
writes one JSON file atomically, and refuses to run over an existing
database/sidecar. No production database, credentials or guest contact data.

## Commands and results

```
.venv/bin/python -m pytest tests/test_db_readonly_cursor.py tests/test_db_upgrade.py \
  tests/test_db_update_if.py tests/test_billing_analytics_export.py \
  tests/test_billing_analytics.py -q --tb=short -x
50 passed in 2.23s

UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest \
  tests/test_host_account_navigation.py tests/test_design_shell.py \
  tests/test_design_guardrails_browser.py tests/test_host_geometry.py \
  tests/test_static_versions.py -q -rs --tb=short -x
36 passed in 26.16s (0 skipped)

UBYHOST_SHOTS_DIR=/tmp/ubyhost-shots UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python \
  -m pytest tests/test_host_wide_geometry_browser.py -q -rs --tb=short -x
10 passed in 81.60s

ruff check app tests tools --select E9,F63,F7,F82,F401,F841
All checks passed!

python3 scripts/context_lint.py
context lint: OK

python tools/smoke.py http://127.0.0.1:18081
44 pages checked / no dead pages, no server errors
```

`git diff --check` clean. The 0454 evidence screenshots are
`docs/tasks/0454-admin-settings-390.png` (390×5681) and
`docs/tasks/0454-entities-390.png` (390×1969), both inspected.

## Known pre-existing failure

`tests/test_host_filter_panels_browser.py::test_filter_draft_calendar_and_month_grid_commit_once`
fails on unmodified `origin/main` (`1f31d41a`) as well — reproduced in a clean
worktree before this branch. The host wide-geometry files also expect
`UBYHOST_SHOTS_DIR` or `/workspace`; they pass with a writable shots dir. Neither
is caused by this change.

## Remaining gates

0455/0456 PostgreSQL runtime/operations remain blocked and unreviewed; no
scheduler, driver, migration, deployment or production query was added. Owner
merges; production deploy is manual.
