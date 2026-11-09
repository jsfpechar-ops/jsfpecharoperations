# 1033: first-run polish C, celebration toast, accept screen, first guest link card

Status: todo
Depends on: none | Base: `origin/main`. If 1031 is not merged yet it also edits `_components.html`; this brief only touches the `onboarding_finish` macro there, so rebasing is trivial. | Branch: `claude/first-run-1033` | Open one PR (executor.md), never merge
Executor: Haiku 5.5, one run, 30 tool calls (checkpoint at 25: commit, report `Status: blocked`, list what is left). UI brief: rules 7 and 10 apply.

## 1. Objective

Before shots: `/mnt/project-files/first-run/before/{dash-celebration,accept,dash-ready,guest-link}/<en|cs>-<390|768|1280>.png` (the onboarding finish card shows on `dash-ready` and `dash-fin`; open `dash-fin` too). Direction: calm, rounded, generous even spacing, less is more. Keep logic, copy meaning, a11y and focus behaviour. No new dependency. Light mode only. Three small fixes:

A. Celebration toast (`App/app/templates/base.html`, the `{% if celebration_milestone %}` block only, around lines 114-125): the "Thanks!" button (`class="toast-undo"`, string `celebration.dismiss`) is an underlined text link. Restyle it as the rounded pill used elsewhere: replace its class with `toast-pill` and add CSS: `min-height:44px; padding:8px 18px; border-radius:999px; background:var(--canvas); color:var(--ink); font-weight:700; font-size:14px; text-decoration:none; border:0` with a visible focus ring identical to other buttons (`:focus-visible`, reuse the ring token other `.btn`/`.ui-btn` use; find with `grep -n "focus-visible" App/app/static/app.css | head -5`). Other toasts (Undo) keep `.toast-undo`. Form, hidden inputs, `id="celebration-toast"` and data attributes unchanged. Add the CSS next to `.toast button.toast-undo` in `App/app/static/app.css` (~line 592) and a host override only if `.host-workspace .toast-stack .toast .toast-undo` (host.css ~368) needs a matching `.toast-pill` rule (it sets min-height 44px; mirror it so the pill keeps its padding).

B. Accept screen (`App/app/templates/account_accept.html`, route `/account/accept`): two log-out controls render, the in-card `<form class="auth-secondary">` (string `account.accept.sign_out`) and the footer `auth-not-you` form from `App/app/templates/auth_base.html` (line ~50, shown whenever `current_user`; string `auth.not_you`). Keep ONE: delete the in-card `auth-secondary` form from `account_accept.html` and keep the `auth_base.html` footer one (it is shared; do not edit `auth_base.html`). Before deleting, confirm in the `accept` before shots that both are visible; if only one shows, STOP. `account.accept.sign_out` becomes unused: leave the key. Check no test asserts the removed form (`grep -rn "account.accept.sign_out\|auth-secondary" App/tests | head`); update only such an assertion and say so.

C. First guest link card (`onboarding_finish` macro in `App/app/templates/_components.html`, starts `{% macro onboarding_finish`; CSS `.onboarding-finish*` in `App/app/static/app.css` lines ~2011-2096 plus any `body.v2 .onboarding-finish` / `.host-workspace .onboarding-finish` overrides: `grep -n "onboarding-finish" App/app/static/*.css`):
 - No nested boxes: the card is one rounded container; `.onboarding-finish-field` rows lose their own border/background and become simple label + value + copy rows separated by a hairline or 16px gap.
 - Buttons consistent: "Open communication" (primary) and "Preview" (secondary) and the quiet skip/resume share the same height (44px), radius and padding class family; on <640px they stack full width with centred labels (`justify-content:center; text-align:center`), at >=640px they sit in one centred row.
 - The URL `code#onboarding-finish-link` wraps safely: `overflow-wrap:anywhere; word-break:break-word; min-width:0` and no horizontal scroll at 390 (also on the grid child that contains it: `min-width:0`).
 - Copy buttons keep `copy_button(...)` macro and ids unchanged (tests/JS use `onboarding-finish-link` and `onboarding-finish-pin`).
 - Do not change strings; do not remove the `help_tip`.

## 2. Context

- `welcome_back` looked like dead UI (the route in `App/app/routes/onboarding.py` and the strings exist, no template renders it). Do NOT change it.
- Do NOT touch the "Add a second way in" dialog in `base.html`; change only the celebrations block.
- Relevant tests: `tests/test_celebrations.py`, `tests/test_legal_acceptance.py`, `tests/test_login_acceptance.py`, `tests/test_onboarding.py`, `tests/test_onboarding_followup_browser.py`.

## 3. Files (grep to confirm anchors; not found: STOP)

| Path | Action |
|---|---|
| App/app/templates/base.html | edit: the celebration `<button class="toast-undo" ...>` only; bump the `?v=` of app.css / host.css if changed |
| App/app/static/app.css | edit: add `.toast button.toast-pill` after `.toast button.toast-undo`; edit `.onboarding-finish*` rules |
| App/app/static/host.css, app2.css, host2.css, host-controls.css | edit only the `.onboarding-finish*` or `.toast .toast-undo` overrides that would still fight the result |
| App/app/templates/account_accept.html | edit: delete the `auth-secondary` logout form (B) |
| App/app/templates/_components.html | edit only inside `onboarding_finish` (C), markup tweaks only if CSS alone cannot do it |
| App/tests/static_versions.json | update for each bumped static file (`grep -n "app.css" App/app/templates/base.html App/tests/static_versions.json`) |
| docs/tasks/1033-report.md | create |

## 4. Steps

0. Clean tree. `git checkout -B claude/first-run-1033 origin/main`. Read design-system checklist headings only (`grep -n '^## \|^- \[' docs/design/design-system.md | head -40`).
1. A: base.html + CSS. Run `cd App && .venv/bin/python -m pytest tests/test_celebrations.py -q --tb=short -x 2>&1 | tail -30`.
2. B: account_accept.html. Run `cd App && .venv/bin/python -m pytest tests/test_legal_acceptance.py tests/test_login_acceptance.py -q --tb=short -x 2>&1 | tail -30`.
3. C: macro + CSS. Run `cd App && .venv/bin/python -m pytest tests/test_onboarding.py -q --tb=short -x 2>&1 | tail -30`.
4. Static `?v=` bumps.
5. Tests (test-map "Host pages, host templates, host CSS" plus guest/auth pages are untouched): `cd App && .venv/bin/python -m pytest tests/test_host_*.py tests/test_host_geometry.py tests/test_onboarding_followup_browser.py tests/test_design_guardrails_browser.py -q -rs --tb=short -x 2>&1 | tail -30`. 0 skipped.
6. UX gate: `cd App && UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -rs -x 2>&1 | tail -30`: green, 0 skipped, zero host findings (accept is a public/auth page: report-only findings go in the report, never silenced).
7. Screenshots EN at 390, 768, 1280 into `/mnt/project-files/first-run/after/<surface>/en-<w>.png` for `dash-celebration`, `accept`, `dash-ready`, `dash-fin`, `guest-link` (same fixtures as the before shots), plus CS 390 for `dash-celebration` and `accept`. Look at each once. Write per page in the report and PR body: "390: ...; 768: ...; 1280: ..." (pill visible and focus ring; exactly one log-out link; no nested boxes, buttons equal height with centred labels, URL wraps with no horizontal scroll). Tick the design-system checklist in the PR.
8. Report (600 tokens max), `Status: review`, one PR. Commit each step as `1033 step k`.

## 5. Do not touch

The "Add a second way in" dialog and any other part of base.html, `auth_base.html`, `welcome_back*`, `onboarding_welcome` / `onboarding_banner` (brief 1031), `setup_wizard/*` (brief 1032), i18n files (no copy change), the onboarding logic.

## 6. Commands

From `App/`, as in steps 1, 2, 3, 5, 6. Browser tests: 0 skipped.

## 7. Acceptance

- [ ] "Thanks!" is a rounded pill, 44px high, with a visible focus ring; Undo toast unchanged.
- [ ] `/account/accept` shows exactly one log-out control.
- [ ] Finish card: one container, no nested boxes, equal-height buttons with centred labels, long URL wraps at 390 with no horizontal scroll.
- [ ] Layout lint and browser tests green, 0 skipped; 390/768/1280 shots in `/mnt/project-files/first-run/after/<surface>/`; per-page notes in the PR.

## 8. Stop and ask

- Anchor not found; only one log-out control visible on accept.
- A layout-lint finding or skipped browser test (report text, never silence).
- A test fails twice. 25 tool calls reached: commit, report `Status: blocked`.

## 9. Report

Per `docs/context/executor.md` plus the UX-gate notes. Owner steps: none.
