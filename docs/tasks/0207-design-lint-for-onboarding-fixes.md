# 0207: Design lint and test follow-ups for the onboarding fixes

Status: todo
Depends on: 0205 | Base commit: b7c817a | Branch: claude/project-thread-cf47ju
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

CI's design lint (`scripts/design_lint.py`) fails on PR #418: five new classes are not in the catalog, and two values in `host2.css` are bare px. Register the classes and use tokens. Also close the four test follow-ups 0205 reported.

## 2. Context

CI output (2026-10-21):

```
DESIGN App/app/templates/setup_wizard/_layout.html: T3 class not in catalog: required-legend
DESIGN App/app/templates/setup_wizard/done.html: T3 class not in catalog: setup-wizard-celebrate
DESIGN App/app/templates/setup_wizard/done.html: T3 class not in catalog: setup-wizard-confetti
DESIGN App/app/templates/setup_wizard/door_lock.html: T3 class not in catalog: setup-wizard-lock-panel
DESIGN App/app/templates/setup_wizard/guest_link.html: T3 class not in catalog: setup-wizard-message-steps
DESIGN App/app/static/host2.css: S2 bare 2px in border-radius
DESIGN App/app/static/host2.css: S2 bare 14px in font-size
```

Tokens that exist in `tokens.css`: `--radius-xs` (4px) and `--text-sm`.

## 3. Files

| Path | Action | What |
|---|---|---|
| docs/design/catalog.json | edit | five classes plus a note each |
| App/app/static/host2.css | edit | two tokens |
| App/app/templates/base.html | edit | new `host2.css` key |
| App/tests/static_versions.json | regenerate | `--write` |
| App/app/host_i18n.py | edit | Czech abbreviation hint keeps the letter's exact line |
| App/tests/test_smart_locks_page.py | edit | new TTLock essentials text |
| App/tests/test_onboarding_wizard_browser.py | edit | the police step now needs a password |
| App/tests/test_host_ux_acceptance.py | edit | follow-up: city_en is no longer an editable setting |

## 4. Steps

### Step 1. `docs/design/catalog.json`

With a short Python script (`python3 -I`, `json.load` then `json.dump(..., ensure_ascii=False, indent=2)` plus a trailing newline; first check with `git diff` that the file's existing formatting is kept, and if the whole file reformats, STOP and report):

- append to `"classes"`: `"required-legend"`, `"setup-wizard-celebrate"`, `"setup-wizard-confetti"`, `"setup-wizard-lock-panel"`, `"setup-wizard-message-steps"`;
- add to `"class_notes"`:
  - `"required-legend"`: `"One line above a form: fields marked * are required (0204; the star comes from the required attribute in host2.css)."`
  - `"setup-wizard-celebrate"`: `"Setup wizard finish banner, green, holds the one-time confetti (0203)."`
  - `"setup-wizard-confetti"`: `"Decorative confetti pieces inside setup-wizard-celebrate; aria-hidden, off for reduced motion (0203)."`
  - `"setup-wizard-lock-panel"`: `"Setup wizard lock step: wraps the smart locks panel so connecting a lock stays in the wizard (0203)."`
  - `"setup-wizard-message-steps"`: `"Setup wizard guest message: the numbered steps that say how to use the template (0204)."`

### Step 2. `App/app/static/host2.css`

a) In the line starting `.host-workspace .setup-wizard-confetti i { position: absolute;` replace `border-radius: 2px;` with `border-radius: var(--radius-xs);`
b) In the line starting `.host-workspace .required-legend {` replace `font-size: 14px;` with `font-size: var(--text-sm);`

### Step 3. `App/app/templates/base.html`

Replace the current `host2.css?v=` value (it is `20261021-0204`; check with grep) with `20261021-0207`.

### Step 4. Cache keys

`cd App && .venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5`

### Step 5. `App/app/host_i18n.py` (0205 block)

Anchor: `        "apartment.form.ubyport.mark_hint": "Vyplní se samo z přihlašovacího jména: je to část za UBY-WS_. Změňte ji, jen když dopis od policie uvádí jinou „Zkratku ubytovacího zařízení“.",`
Replace with:
`        "apartment.form.ubyport.mark_hint": "Vyplní se samo z přihlašovacího jména: je to část za UBY-WS_. Změňte ji, jen když dopis od policie uvádí na řádku „Zkratka ubytovacího zařízení“ něco jiného.",`

### Step 6. `App/tests/test_smart_locks_page.py`

Anchor (exact, 3 lines):

```
        "Open your lock in TTLock.",
        "Share administrator access with the account above.",
        "Return here and check for locks.",
```

Replace with:

```
        "In the TTLock app, open your lock and tap Authorized Admin (eAdmin in some app versions).",
        "In the Recipient field, where TTLock expects an e-mail or phone number, paste your UbyHost name from above.",
        "Come back here and tap Check connection.",
```

### Step 7. `App/tests/test_onboarding_wizard_browser.py`

0205 made the police password required when none is stored, so the browser now blocks this save before the server can show its IDUB error.

Anchor (exact, 2 lines):

```
        page.fill("#uby_name", "Typed Facility")
        page.locator('button[form="police-form"]').click()
```

Replace with:

```
        page.fill("#uby_name", "Typed Facility")
        page.fill("#uby_ws_password", "typed-password")  # 0205: required until one is stored
        page.locator('button[form="police-form"]').click()
```

If this anchor occurs more than once, apply it only to the occurrence followed within 4 lines by `assert page.locator(".err-text").first.is_visible()` and say so in the report.

### Step 9 (follow-up). Two test pins

a) `App/tests/test_smart_locks_page.py`: in the line `    for words in ("Authorized Admin", "Create Admin", "Manage their own users only", "Tap Recipient and paste the name"):` replace `"Tap Recipient and paste the name"` with `"paste your UbyHost name"` (the new `smart_locks.s6`).

b) `App/tests/test_host_ux_acceptance.py`: replace the line `    "internal_name", "city_en", "legal_entity_id", "data_controller_entity_id",` with `    "internal_name", "legal_entity_id", "data_controller_entity_id",  # 0204: city_en follows the address town`. Only the PROPERTY_SETTINGS line (the first match, line about 59); leave CREATE_FIELDS alone.

### Step 8. Is the 360 px tab overflow this PR's?

`tests/test_property_navigation_browser.py::test_property_views_fit_every_width_and_sidebar` failed in the 0205 run (360 px settings tabs: Reporting & fees, Door lock, Automation). Check whether it fails on main too:

```
git worktree add /tmp/ubyhost-main 2f043c8 2>&1 | tail -2
cd /tmp/ubyhost-main/App && UBYHOST_REQUIRE_BROWSER=1 /home/user/jsfpecharoperations/App/.venv/bin/python -m pytest tests/test_property_navigation_browser.py -k fit_every_width -q --tb=line -rs 2>&1 | tail -8
cd /home/user/jsfpecharoperations && git worktree remove --force /tmp/ubyhost-main
```

Then run the same test on the branch. Report both results. Do not try to fix it here: if it passes on main and fails on the branch, report the assertion message (the `fit` dict) and stop.

## 5. Do not touch

Guest templates, filing code, every file not in §3. AGENTS hard rules 1, 3, 5, 8.

## 6. Commands

1. `python3 scripts/design_lint.py 2>&1 | tail -10` → `OK`
2. From `App/`: `.venv/bin/python -m pytest tests/test_design_lint.py tests/test_dev_ui.py tests/test_design_ui_macros.py tests/test_static_versions.py -q --tb=short -x 2>&1 | tail -30`
3. From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -10`
4. From `App/`: `.venv/bin/python -m pytest tests/test_reporting_help_0097.py tests/test_smart_locks_page.py -q --tb=short -x 2>&1 | tail -30`
5. From `App/`: `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_onboarding_wizard_browser.py tests/test_host_ux_acceptance.py -q --tb=line -rs 2>&1 | tail -30` (0 skipped; list every failure by name)

## 7. Acceptance

- [ ] design lint prints OK; §6 tests pass.

## 8. Stop and ask

As in TEMPLATE.md §8. If design lint reports a finding not listed in §2 (for example from 0205), fix it only if it is the same kind (a new class to register, or a bare px with an obvious token); otherwise STOP and report it.

## 9. Report

`docs/tasks/0207-report.md`, as in TEMPLATE.md §9.
