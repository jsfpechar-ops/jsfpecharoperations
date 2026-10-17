# 0022: Restore the production look of the Dashboard stay rows in PR 397

Status: todo
Depends on: none | Base commit: 34b7933 (head of `feature/host-design0123-20261016`) | Branch: `feature/host-design0123-20261016` (PR 397, keep committing there)
Executor: Cursor local agent (composer, Kimi or GLM) | Fits one session

## 1. Objective

On the Dashboard, the "Needs action now" / "Current" stay rows must look exactly like production (`main`): one bordered rounded card per stay, property badge and name, no "Open" button, only the "⋯" menu. PR 397 turned them into flat hairline rows with an "Open" button and a repeated name line, and the owner does not like that.

## 2. Context

Owner feedback (2026-10-17): the new stay rows are worse than the ones in production. Rule: [DESIGN](../DESIGN.md#action-geometry), and production tests already assert there is **no** `.dashboard-open` on Dashboard rows (a deliberate "quiet dashboard" choice, `origin/main:App/tests/test_host_quiet_dashboard_browser.py:208,350` and `test_onboarding_followup_browser.py:103`). PR 397 reversed that; this task puts it back.

Everything else in PR 397 stays: the compact stat row, calendar controls, Stays-page list, filter panels, stay detail, cleaning pages. Only `.dashboard-row*` on the Dashboard changes. The `stay_label` logic on `reservations.html` is out of scope.

Excerpt A, `App/app/templates/dashboard.html` on the PR branch, lines 9 to 34 (the row macro). Confirm it matches before editing:

```
  {% set stay_label = reservation.summary if reservation.source == 'manual' and reservation.summary and reservation.summary.strip() else reservation.internal_name %}
  ...
           aria-label="{{ stay_label }} · {{ reservation.date_from | date_cz }} – {{ reservation.date_to | date_cz }}">
  ...
      <a class="dashboard-row-property" href="/reservations/{{ reservation.id }}?return_to=/">{{ stay_label }}</a>
      <p class="dashboard-row-property-context">{{ property_identity(...) }} · {{ source_label(reservation) }}</p>
  ...
      <a class="btn dashboard-row-open dashboard-open" href="/reservations/{{ reservation.id }}?return_to=/">{{ t('common.open') }}</a>
```

Excerpt B, production markup for the same lines (`git show origin/main:App/app/templates/dashboard.html`, the `dashboard_rows` macro). Restore it byte for byte:

```
  {% set reservation = row.reservation %}{% set progress = row.progress %}{% set cell = row.deadline_cell %}
           aria-label="{{ reservation.date_from | date_cz }} – {{ reservation.date_to | date_cz }} · {{ reservation.internal_name }}">
      <a class="dashboard-row-property" href="/reservations/{{ reservation.id }}?return_to=/">{{ property_identity(reservation.apartment_id, reservation.internal_name, true) }}</a>
```

(no `stay_label` line, no `dashboard-row-property-context` paragraph, no `dashboard-open` link.)

Excerpt C, production CSS (in `origin/main:App/app/templates/dashboard.html`, inside its `<style>` block, lines 15 to 39 of that block). Re-add these rules verbatim to `App/app/static/host-design0123.css`, prefixed `body.host-workspace` instead of `.host-workspace`, replacing the PR's `.dashboard-row-list`, `.dashboard-row*` rules (PR lines 67 to 78) and the PR's mobile `.dashboard-row*` / `.dashboard-open` lines (PR lines 122 to 127). Take the exact text from `git show origin/main:App/app/templates/dashboard.html`; the key values:

```
.dashboard-row-list { display:grid; gap:8px; }
.dashboard-row { display:grid; grid-template-columns:minmax(0,1fr) 184px; align-items:center; gap:18px; padding:12px 14px; border:1px solid var(--line); border-radius:11px; background:#fff; }
.dashboard-row.is-overdue { border-left:3px solid var(--status-critical-border); }
.dashboard-row-property { display:inline-block; margin-top:3px; color:var(--ink); font-size:15px; font-weight:700; text-decoration:none; border-radius:3px; }
.dashboard-row-actions { display:grid; grid-template-columns:42px; justify-content:end; gap:8px; align-items:center; }
@media (max-width:760px) { .dashboard-row { grid-template-columns:minmax(0,1fr); gap:10px; padding:12px; } .dashboard-row-actions { grid-template-columns:44px; justify-content:end; } ... }
@media (max-width:380px) { .dashboard-row-actions { grid-template-columns:44px; } .dashboard-row-dates { gap:5px; } }
```

If any excerpt is not found as shown, STOP (§8).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/dashboard.html` | edit | Restore Excerpt B in the `dashboard_rows` macro. Leave the rest of the PR changes (stat row, `data-dashboard-refresh`, cleaning button) |
| `App/app/static/host-design0123.css` | edit | Replace the `.dashboard-row*` rules with Excerpt C. Keep `.dashboard-stats` and everything else |
| `App/tests/test_host_quiet_dashboard_browser.py` | edit | Revert only the hunks about `.dashboard-open` / `dashboard-row-property-context` to `origin/main` |
| `App/tests/test_host_list_layouts_browser.py` | edit | Same: only dashboard-row hunks |
| `App/tests/test_onboarding_followup_browser.py` | edit | Same: only dashboard-row hunks |
| `docs/tasks/0022-report.md` | new | §9 |
| `docs/tasks/0022-screenshots/*.png` | new | §7 |

No other file may change.

## 4. Steps

1. `git fetch origin main feature/host-design0123-20261016`. Check out `feature/host-design0123-20261016`.
2. Edit `dashboard.html` per Excerpt B. Remove the now-unused `.dashboard-row-property-context` and `.dashboard-open` rules from the CSS.
3. Edit `host-design0123.css` per Excerpt C.
4. For each of the three test files run `git diff origin/main...HEAD -- <file>` and revert only the hunks tied to the Open button or the context line. Keep hunks for the calendar or other PR features.
5. Run the commands in §6. Take the screenshots.
6. Commit on the same branch (do not push; the owner pushes). Write the report.

## 5. Do not touch

`App/app/static/dashboard-calendar.*`, `reservations.html`, the Stays page, stay detail, cleaning pages, `.github/workflows/ci.yml`, any route or Python file, any `host_i18n` key. Hard rules 5, 6 and 7 from AGENTS.md apply (light mode only; browser and geometry tests 0 skipped; screenshots in the report). No new dependency.

## 6. Commands

From `App/`:

```
.venv/bin/python -m pytest tests/test_host_quiet_dashboard_browser.py tests/test_host_list_layouts_browser.py tests/test_onboarding_followup_browser.py -q
UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=../docs/tasks/0022-screenshots .venv/bin/python -m pytest tests -q -k "dashboard or host_geometry or filter_panel or wide_geometry"
.venv/bin/python -m pytest tests -q
```

From the repo root: `python3 scripts/context_lint.py`. Expected: all pass, 0 skipped.

## 7. Acceptance

- [ ] Dashboard rows are bordered rounded cards, with no "Open" button and no second name line (compare against production, screenshot side by side with `origin/main`).
- [ ] `.dashboard-open` count is 0 on every Dashboard row (the production tests pass unchanged).
- [ ] The compact stat row, calendar and Stays page are unchanged from the PR head.
- [ ] No horizontal overflow at 360, 390, 1024 and 1280 px; Czech and English labels fit.
- [ ] Screenshots at 360, 390 and 1280 px in `docs/tasks/0022-screenshots/`.
- [ ] Browser and geometry tests: 0 skipped.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- a test fails twice;
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/0022-report.md` (1,500 tokens at most) and set `Status: review`. The report has: the files changed (`git diff --stat`), each command with the last 5 lines of output, §7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

`App/app/static/host-design0123.css` (the dashboard-row block and its mobile media query) and the three test files (make sure only the Open-button hunks were reverted).

## Owner steps

1. Push the branch: `git push origin feature/host-design0123-20261016`.
2. Open PR 397, wait for CI, and look at the Dashboard screenshots at 360 and 1280 px.
3. If the rows look right, take the PR out of draft and merge it with `scripts/merge-pr-on-green.sh`. Deploy to production is yours.
