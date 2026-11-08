# 1031: first-run polish A, dashboard welcome, onboarding page and setup banner

Status: todo
Depends on: none | Base: `origin/main` | Branch: `claude/first-run-1031` | Open one PR (executor.md), never merge
Executor: Haiku 5.5, one run, 30 tool calls (checkpoint at 25: commit, report `Status: blocked`, list what is left). UI brief: rules 7 and 10 apply. Sibling briefs 1032 (setup done) and 1033 (small polish) touch other files; do not touch theirs.

## 1. Objective

An audit of first-run screens (before shots: `/mnt/project-files/first-run/before/{dash-new,onboarding-new,apartments-new,reservations-new,entities-new,dash-dismissed,apartments-dismissed,reservations-dismissed}/<en|cs>-<390|768|1280>.png`) found the welcome card noisy and repeated. Direction: one calm column, rounded, generous even spacing, less is more. Keep logic, copy meaning, a11y and focus behaviour. No new dependency. Light mode only. Auth/forms keep working without JavaScript.

Open each before shot once (390 and 1280, EN) to see the problem. Then:

1. Welcome card (`onboarding_welcome` macro, used on `/` with `compact=True` and on `/onboarding` with `v2=True`): show the current step ONCE. Remove: logo (`onboarding-logo` img), kicker (`onboarding-kicker`), the duplicate "0%" `<strong>` plus the empty progress bar (`<div aria-hidden><i>`) in `.onboarding-meter`, the whole "Do this now" block (`.onboarding-now`), and the "See all setup steps" link (`.onb-more`, the `compact_list` logic).
2. The steps are a plain numbered list. Only the CURRENT step has one primary button (its action, `btn primary`/`ui-btn ui-btn-primary`). Other steps: number + title only (done steps: check mark, keep the "Done" pill). Keep the `manual_url` link only on the current step, as a quiet text link. The per-step `<details>` "learn" disclosure stays only on `/onboarding` (v2), not on `/` (compact).
3. "Skip setup guidance" becomes a quiet text link (`onboarding-skip-link`) at the card foot, left aligned or centred under the list, WITHOUT its `help_tip` "?" (remove the `help_tip('onboarding-skip-help', ...)` call; the string `onboarding.skip_hint` becomes unused: leave the key in the i18n files). The Resume form (dismissed state) stays as the same quiet link.
4. The demo button (`demo_available` block, `.onboarding-demo`): put 24px of space above it, make the button secondary (`btn` without `primary`; it must not look like the step button) and keep its `help_tip`.
5. Alignment: at 1280 the welcome card lane must have the same left edge and width as the page heading (`.head`/h1) above it on `/`. Remove any extra max-width or margin on `.onboarding-welcome` that breaks this (see "Files", CSS).
6. `onboarding_banner` (shown on /apartments, /reservations, /entities, and `/` when apartments exist): becomes ONE quiet line, no button styling: text "Setup 2 of 5 · Continue" where the whole text is one link to `onboarding.setup_url` (class `onboarding-banner-setup-link`, no `ui-btn`), then the quiet "Skip setup guidance" button on the same line, right aligned. Min touch target 44px height under 1024px. No border box heavier than a hairline; keep `aria-label`.
7. `/apartments` empty state (no rows): give the page a proper `<h1>` title "Properties" (`apartments.title`) with the same `.head` markup as the `{% if rows %}` branch (without the add button), above the `empty_state(...)`. Look at `apartments.html` line ~15-90.
8. `/entities` empty (no operators): the page already shows the add-operator form/card. Remove the duplicate `<div class="card ui-empty">{{ t('entities.empty') }}</div>` in the `{% else %}` branch ONLY IF the add form is rendered right above it in that state (check the CS/EN `entities-new` before shot and the template around line 112-117). If the form is not shown in that state, STOP and ask.

New copy: none expected. If you need a string, add EN and CS (and VI, parity) in `App/app/host_i18n.py` and `App/app/host_vi_i18n.py`, find neighbours with `grep -nF "onboarding.skip" App/app/host_i18n.py`.

## 2. Context

- `welcome_back` looked like dead UI (the route in `App/app/routes/onboarding.py` and the strings exist, no template renders it). Do NOT change it, do not delete its route, strings or module.
- Do NOT touch the "Add a second way in" dialog in `base.html`.
- Existing strings used: `onboarding.welcome_title`, `onboarding.progress`, `onboarding.<step>.title/.action/.manual`, `onboarding.skip`, `onboarding.resume`, `setup.banner.line` (EN "Setup: step %(step)s of %(total)s · Continue"; change EN to "Setup %(step)s of %(total)s · Continue" and CS to "Nastavení %(step)s z %(total)s · Pokračovat"; there are two more `setup.banner.line` entries around host_i18n.py lines 7964/7988 that read "Continue setup"; run `grep -nF '"setup.banner.line"' App/app/host_i18n.py` and edit only the two whose value contains `%(step)s`).
- Banner and welcome tests assert some of these strings and classes; update an assertion only when it names a string or element this brief removes, and say so in the report.

## 3. Files (grep to confirm each anchor first; not found: STOP)

| Path | Action |
|---|---|
| App/app/templates/_components.html | edit macros `onboarding_welcome` (starts `{% macro onboarding_welcome`) and `onboarding_banner` (starts `{% macro onboarding_banner`). Do NOT edit `onboarding_finish` (brief 1033) |
| App/app/templates/dashboard.html | edit lines ~36-37 only if the compact call needs changing (expected: no change; the `ph-hide` wrapper on line ~64 stays) |
| App/app/templates/onboarding.html | no change expected (calls `onboarding_welcome(onboarding, v2=true)`) |
| App/app/templates/apartments.html | edit the empty branch (step 7) |
| App/app/templates/entities.html | edit the `{% else %}` empty branch (step 8) |
| App/app/templates/reservations.html | no change expected (banner call only) |
| App/app/static/app2.css | edit the `body.v2 .onboarding-welcome...` rules (lines ~1453-1491 for v2, ~2706-2764 for the non-v2 card, ~2744 for the banner, ~143 for the link, ~1846 and ~2243 lane rules) |
| App/app/static/host.css, host2.css, host-controls.css, components.css, app.css | edit only to delete or override a rule that would still apply to a removed element or to the banner (`grep -n "onboarding-banner-setup" App/app/static/*.css`, `grep -n "onboarding-now\|onboarding-logo\|onboarding-meter" App/app/static/*.css`). Prefer deleting dead rules for removed elements over adding overrides |
| App/app/host_i18n.py, App/app/host_vi_i18n.py | edit `setup.banner.line` per section 2 (EN, CS, VI parity) |
| App/app/templates/base.html, App/tests/static_versions.json | when a static CSS file changed, bump the `?v=` for that file in base.html and update `static_versions.json` (find with `grep -n "app2.css" App/app/templates/base.html App/tests/static_versions.json`) |
| docs/tasks/1031-report.md | create |

## 4. Steps

0. Clean tree. `git checkout -B claude/first-run-1031 origin/main`. Before editing, read the checklist headings only: `grep -n '^## \|^- \[' docs/design/design-system.md | head -40`; you tick relevant items in the report.
1. `_components.html` `onboarding_welcome`: apply items 1-4 of the Objective. Keep the `help_tip` for the demo. Keep `{{ onboarding_finish(onboarding, show_toggle=False) }}` when `onboarding.finished`. Keep header `<h1>` on `/onboarding` and `<h2>` when `compact`. Under the title keep one line `onboarding.progress` ("2 of 5 ready") as the ONLY progress indicator (a `<p class="sub">`, for both v2 and compact).
2. Same file `onboarding_banner`: apply item 6. Run `cd App && .venv/bin/python -m pytest tests/test_onboarding.py -q --tb=short -x 2>&1 | tail -30` (fix an assertion only per section 2).
3. CSS (files in section 3): delete dead rules for removed elements; style the steps as a plain numbered list in one rounded card (radius token already used by `.onboarding-welcome`, 24px padding at 1280, 16px at 390, 12px gap between rows, hairline dividers, no per-row boxes except a soft tint on the current row); primary button on the current row right aligned at >=640px and full width below the title at <640px; the quiet skip link under the list with 16px top margin; the welcome card `margin-inline:0; max-width:none` so its edges equal the heading edges at 1280 (check with the screenshot, compare left edges).
4. Items 7 and 8 in `apartments.html` and `entities.html`.
5. i18n edit for `setup.banner.line`. Then `cd App && .venv/bin/python -m pytest tests/test_host_i18n.py tests/test_no_em_dashes.py -q --tb=short -x 2>&1 | tail -30`.
6. Bump static versions (section 3 last static row).
7. Tests from the test-map row "Host pages, host templates, host CSS": `cd App && .venv/bin/python -m pytest tests/test_host_*.py tests/test_host_geometry.py tests/test_onboarding.py tests/test_onboarding_why_0206.py tests/test_onboarding_wizard_browser.py tests/test_onboarding_followup_browser.py tests/test_design_guardrails_browser.py -q -rs --tb=short -x 2>&1 | tail -30`. 0 skipped.
8. UX gate (rule 10): `cd App && UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -rs -x 2>&1 | tail -30`: green, 0 skipped, zero host findings (never silence one).
9. Screenshots: for each surface `dash-new`, `onboarding-new`, `apartments-new`, `reservations-new`, `entities-new`, `dash-dismissed`, `apartments-dismissed`, `reservations-dismissed` take EN at 390, 768, 1280 (same method and fixtures as the before shots; if you cannot find how they were taken, use the browser test helpers in `tests/test_onboarding_wizard_browser.py` and the layout-lint shots in `/tmp/shots/layout-lint/`). Save to `/mnt/project-files/first-run/after/<surface>/en-<width>.png`. Also CS 390 for `dash-new` and `onboarding-new`. Open each once. Write per page in the report AND the PR body: "390: ...; 768: ...; 1280: ..." (what you saw: step shown once, one primary button, lane alignment, no overflow). Tick the design-system checklist in the PR.
10. Report (`docs/tasks/1031-report.md`, 600 tokens max, per executor.md), set `Status: review`, open one PR. Commit each step as `1031 step k`.

## 5. Do not touch

`onboarding_finish` and `onboarding_finish_strip` macros, `setup_wizard/*`, `account_accept.html`, base.html except the static `?v=` bump, the "Add a second way in" dialog, `welcome_back*` (route, module, strings), the onboarding logic in `App/app/onboarding.py`, any other page.

## 6. Commands

All from `App/`, as in steps 2, 5, 7, 8. Browser tests: 0 skipped (`-rs`).

## 7. Acceptance

- [ ] On `/` (new account) the current step appears once, one primary step button, no logo/kicker/duplicate 0%/empty bar/"Do this now"/"See all setup steps"; skip is a quiet text link without "?".
- [ ] `/onboarding` has the same list; details disclosure kept there.
- [ ] Banner on other pages is one quiet line "Setup N of M · Continue" plus the skip link; 44px target under 1024px.
- [ ] `/apartments` empty has an h1; `/entities` empty has no duplicate card.
- [ ] Welcome card left edge equals the heading edge at 1280.
- [ ] i18n parity EN/CS/VI; layout lint and browser tests green, 0 skipped; 390/768/1280 shots in `/mnt/project-files/first-run/after/<surface>/`; per-page notes in the PR.

## 8. Stop and ask

- An anchor in section 3 is not found verbatim.
- Item 8: the add form is not rendered above the empty card.
- A layout-lint finding or a skipped browser test appears (report the finding text, never silence it).
- A test fails twice. 25 tool calls reached: commit, report `Status: blocked`.

## 9. Report

Per `docs/context/executor.md` plus the UX-gate notes from step 9. Owner steps: none (merge is done by the orchestrator with `scripts/merge-pr-on-green.sh`).
