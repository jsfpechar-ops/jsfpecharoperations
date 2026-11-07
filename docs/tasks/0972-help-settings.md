# 0972: Align help, headings and account status copy (batch B14: X03, X04, F02, F03)

Status: blocked (steps 2 to 4 run; group D regressions in the page-help layout and the brief size lint; see docs/tasks/0972-report.md)
Depends on: B13 (master plan; nothing in the repo to wait for) | Base commit: 7b0355c45ccdd2557a28edfcfe228aa1dc766e36 | Branch: codex/0972-b14-help-settings
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Settings help "?" buttons stay on the last line of their label and get a contextual accessible name ("Help with Passkeys"). The property H1 holds only the title (the "How does this work?" panel becomes its sibling), the Technical mail status reports the real runtime backend instead of staging/production prose, and the activity count, Passkeys and Help labels stop repeating or mis-pluralising.

## 2. Context

Rules that apply (full text in docs/context/rules.md; read-only here):
- Mail and secrets: **no mail configuration change, no authentication or security setting change.** You only change what Settings prints. Never print guest data, passwords or secrets; the repo is public.
- Copy: write "no tracking cookies", never "no cookies"; no em dashes (`test_no_em_dashes.py`).
- Host UI: light mode only; focus ring stays visible; Escape closes help and focus returns to the "?" (already done by `App/app/static/app.js`, around the line `if (e.key !== "Escape" || !helpTipState.current) return;`; **do not edit app.js or any CSS**, the tests prove it already works).

How it works today (read, do not change beyond §4):
- `help_tip(id, text, guide_href)` in `App/app/templates/_components.html` renders the "?" button with the generic name `t('help.tip.label')` ("Help"). `tip_label(text, id, help, tag)` keeps the "?" glued to the last word (`tip-nowrap`). In `settings.html` several rows used a bare `<strong>` plus a separate `help_tip`, so the "?" could wrap alone onto a new line.
- `partials/settings_back_header.html` puts its `help` argument **inside** the `<h1>`. `apartment_form.html` passes `help=page_help('property')`, a `<details>` with three steps, so the H1 text included that prose when open. `help_after` (already supported) renders a sibling after the H1 and `app2.css` already styles `.airbnb-header > .page-help`. This brief reuses that existing path.
- `settings.html` shows mail text from `settings.mail.help` (staging console prose plus production-disabled prose). The runtime value is `mail_backend` (from `mail.backend_name()` in `App/app/mail.py`, values `disabled`, `console`, `ses`, passed by `App/app/routes/admin.py`). Do not hard-code a message: the status line must be chosen from `mail_backend`.
- Plural keys: `tp('key', n)` looks up `key` (many), `key.one`, `key.few` (see `settings.retention.delete`). Languages: `en`, `cs` in `App/app/host_i18n.py`, `vi` in `App/app/host_vi_i18n.py`.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/templates/_components.html | edit | macro `help_tip` gets optional 4th arg `label` (contextual aria-label); macros `tip_label` and `settings_heading` pass their text to it |
| App/app/templates/partials/settings_back_header.html | edit | a `help` that is a `page-help` panel renders after the `</h1>`, not inside it |
| App/app/templates/partials/settings_value_card.html | edit | pass `label` to `help_tip` |
| App/app/templates/partials/settings_toggle_row.html | edit | pass `label` to `help_tip` |
| App/app/templates/settings.html | edit | rows use `tip_label`; heading helps get names; mail status line from `mail_backend`; `tp` for activity; Passkeys/Help label fixes |
| App/app/host_i18n.py | edit | en + cs keys |
| App/app/host_vi_i18n.py | edit | vi keys |
| App/tests/test_0786_settings_geometry_browser.py | append | new tests (§4 step 3) |
| App/tests/static_versions.json | do not edit | no static file changes in this brief; edit only if `test_static_versions.py` fails, then STOP (§8) |

No other file may change. The patch in step 2 touches exactly the first seven rows.

## 4. Steps

Work in the worktree `/tmp/ubyhost-b14-worktree` (already created on branch `codex/0972-b14-help-settings`; do not create another). If `git rev-parse HEAD` is not a descendant of `7b0355c4`, STOP. Commands run from `/tmp/ubyhost-b14-worktree/App` unless stated.

### Step 1: anchors and venv

```
cd /tmp/ubyhost-b14-worktree/App
ln -s /tmp/ubyhost-0958-worktree/App/.venv .venv 2>&1 | tail -3
.venv/bin/python --version 2>&1 | tail -3
mkdir -p /tmp/ubyhost-b14
git status --short | tail -5
```
`.venv` is git-ignored; it must not appear in `git status`. Then confirm each anchor with `grep -nF` (any missing: STOP):

| File | Anchor |
|---|---|
| app/templates/_components.html | `{%- macro help_tip(id, text, guide_href='') -%}` |
| app/templates/_components.html | `aria-label="{{ t('help.tip.label') }}" aria-expanded="false"` |
| app/templates/_components.html | `{{ help_tip(id, help) }}</span></{{ tag }}>` |
| app/templates/_components.html | `{{ help_tip('settings-' ~ key ~ '-help', help_text, guide_href) }}` |
| app/templates/partials/settings_back_header.html | `<h1 class="airbnb-title">{% if help %}` |
| app/templates/settings.html | `{{ t('settings.audit.recent', count=audit_count) }}` |
| app/templates/settings.html | `{% with label=t('passkeys.title'), value=(passkeys or []) \| length %}` |
| app/templates/settings.html | `aria-label="{{ t('settings.help.guide_action') }} {{ t('help.tip.label') \| lower }}"` |
| app/host_i18n.py | `"settings.mail.help": "Staging uses the console backend` |
| app/host_i18n.py | `"settings.help.guide_action": "Open",` |
| app/host_vi_i18n.py | `"settings.help.guide_action": "Mở Trợ giúp",` |

(In the grep, the `\|` above is a literal `|`.)

Commit nothing yet.

### Step 2: apply the patch

The unified diff is large: it lives in this repo at `docs/tasks/inc/0972-b14-step2.patch` (byte-identical to the old inline heredoc in prior revisions of this brief).

From the worktree repo root:

```
cd /tmp/ubyhost-b14-worktree
cp docs/tasks/inc/0972-b14-step2.patch /tmp/ubyhost-b14/b14.patch
git apply --check /tmp/ubyhost-b14/b14.patch 2>&1 | tail -30
git apply /tmp/ubyhost-b14/b14.patch 2>&1 | tail -30
git diff --stat | tail -12
```
`--check` fails: STOP, do not hand-edit. The stat must list exactly the seven files in §3 rows 1 to 7. Then `git add` those seven paths by name and commit `0972 step 2`.

What the patch does, so you can review it: `help_tip` gets `label=''`; the aria-label is `t('help.tip.label_for', topic=label)` when a label is given, else the old generic name. `tip_label`, `settings_heading`, the value card, the toggle row and the heading helps in settings.html pass their label. Account/Security/Push rows move from a bare `<strong>` plus separate `help_tip` to `tip_label`. The header partial computes `help_is_page = help and 'page-help' in help`; a page-help is printed after `</h1>`, any other `help` (a `help_tip`) stays inside as before. `<p id="settings-mail-status" data-mail-backend="...">` prints `settings.mail.status.<backend>` (`disabled`, `console`, `ses`, else `unknown`). `settings.mail.help` loses the staging/production prose. Activity heading uses `tp` (keys `.one`, `.few`). The Passkeys value card is labelled "Registered" (key `passkeys.count_label`). Help row: label "User guide" (key `settings.help.guide_label`), button "Open user guide", and the extra `aria-label` is removed because the visible text already names the button.

### Step 3: append the tests

Append the fragment at `docs/tasks/inc/0972-b14-step3-tests.fragment` to the end of `App/tests/test_0786_settings_geometry_browser.py` (do not change anything above it). From the worktree `App` directory:

```
cd /tmp/ubyhost-b14-worktree/App
cat ../docs/tasks/inc/0972-b14-step3-tests.fragment >> tests/test_0786_settings_geometry_browser.py
.venv/bin/python -m py_compile tests/test_0786_settings_geometry_browser.py 2>&1 | tail -5
git add tests/test_0786_settings_geometry_browser.py && git commit -q -m "0972 step 3" 2>&1 | tail -3
```

### Step 4: run the tests (section 6), fix once, view screenshots, write the report (section 9)

## 5. Do not touch

- `App/app/static/*` (CSS and JS), `App/app/mail.py`, `App/app/config.py`, `App/app/routes/*`, `App/app/auth.py`, any env or secret file, `docs/` other than your report and the status line of this brief.
- Mail backend, SES, login, 2FA, passkey and session behaviour: you change text and markup only.
- No new dependency. No push, no PR, no merge, no deploy (hand back to the orchestrator in the report).
- Never use `git add -A`. Before each commit run `git status` and `git diff --staged | grep -iE 'secret|token|api[_-]?key|password|AKIA|ghp_'`; nothing may match.

## 6. Commands

All from `/tmp/ubyhost-b14-worktree/App`, each ending `2>&1 | tail -30`. Browser rows need `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-b14`, `-rs`, and **0 skipped** (a skip is a failure).

```
# A. new tests plus the settings geometry file (browser, 0 skipped)
UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-b14 .venv/bin/python -m pytest tests/test_0786_settings_geometry_browser.py -q -rs --tb=short -x 2>&1 | tail -30

# B. settings and status-rendering tests
.venv/bin/python -m pytest tests/test_settings_technical.py tests/test_0789_settings_subpages.py tests/test_0789b_settings_toggles.py tests/test_design_settings.py tests/test_settings_data_panel.py tests/test_copy_property_settings.py tests/test_passkeys.py -q --tb=short -x 2>&1 | tail -30

# C. copy tests
.venv/bin/python -m pytest tests/test_*_i18n.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py tests/test_flash_literals.py -q --tb=short -x 2>&1 | tail -30

# D. host pages, geometry, guardrails, layout lint (browser, 0 skipped)
UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-b14 .venv/bin/python -m pytest tests/test_host_*.py tests/test_host_geometry.py tests/test_design_guardrails_browser.py tests/test_layout_lint_browser.py -q -rs --tb=short -x 2>&1 | tail -30

# E. static cache keys (no static file changed; must pass untouched)
.venv/bin/python -m pytest tests/test_static_versions.py -q --tb=short -x 2>&1 | tail -30

# F. context lint, from the repo root
cd /tmp/ubyhost-b14-worktree && python3 scripts/context_lint.py 2>&1 | tail -30
```
Expected: every command ends `N passed` with no failed, no error, no skipped. Run A first; if A fails read the last 30 lines, fix **once** (only within §3 files), rerun; a second failure: STOP.

Screenshots land in `/tmp/ubyhost-b14/` as `settings-<group>-<lang>-<width>.png` (groups account, security, technical, help; en and cs; 390, 768, 1280), `help-open-pointer-security-390.png`, `property-help-open-<lang>-<width>.png`, `technical-mail-disabled-<lang>-<width>.png`. View exactly these 8 (one Read each) and describe each in one line in the report: `settings-account-en-390`, `settings-security-en-390`, `help-open-pointer-security-390`, `settings-technical-en-390`, `technical-mail-disabled-en-390`, `settings-help-en-390`, `property-help-open-en-390`, `settings-security-cs-768`. The other shots exist for the orchestrator; say "not viewed" for them. Never save screenshots anywhere else, never commit them.

## 7. Acceptance

Each line: PASS or FAIL in the report, with the test or screenshot that proves it.
- [ ] Account, Security, Technical, Help: H1 is exactly the short title (test `test_0972_h1_is_the_short_title_only`).
- [ ] Property heading: H1 is exactly the property name, also with the help open; the help panel is a sibling after `</h1>` (tests `test_0972_property_help_is_a_sibling_of_the_h1`, `test_0972_property_h1_stays_short_while_its_help_is_open`).
- [ ] Help "?" is on the last line of its label on all four pages, EN and CS, 390/768/1280, no sideways scroll (`test_0972_help_stays_beside_its_label_with_a_contextual_name`).
- [ ] Every settings help button has a contextual, unique name ("Help with ...", "Nápověda: ...") (`test_0972_every_settings_help_button_has_its_own_name`).
- [ ] Help opens by pointer and by keyboard (Tab then Enter); Escape closes and returns focus to the "?"; Tab moves on and closes; focus ring visible; the popover stays inside the viewport at 390, 768 and 1280 (`test_0972_help_opens_by_pointer_and_keyboard_and_stays_in_the_viewport`).
- [ ] Activity heading: zero ("0 events"), one ("1 event"), many; Czech one/few/many (`test_0972_activity_copy_is_plural_aware`, `test_0972_technical_page_uses_the_plural_form_for_its_count`).
- [ ] Mail status shows the runtime backend for `disabled`, `console`, `ses` in EN and CS, with no staging/production prose; with mail disabled it says sending is off (`test_0972_mail_status_reports_the_runtime_backend`, `test_0972_mail_status_with_mail_disabled_in_the_browser`).
- [ ] Passkeys appears once as a label; the Help page row says "User guide" / "Open user guide" (`test_0972_passkeys_and_help_labels_are_not_repeated`).
- [ ] Commands A to F green, 0 skipped. `git diff --stat` shows only the files in §3. No file under `App/app/static`, `App/app/mail.py`, `App/app/config.py`, `App/app/routes` changed.
- [ ] The 8 screenshots viewed and described (sections cut, overlapping text, a "?" alone on a line, a popover beyond the screen edge are FAIL).

## 8. Stop and ask

Stop, and write the report (`Status: blocked`), if:
- an anchor or excerpt is not found, or `git apply --check` fails;
- a test fails twice, or any browser test is skipped;
- test A finds a "?" that is not on the last line of its label, or a popover outside the viewport, and one fix inside §3 files does not cure it (a CSS or app.js change would be needed: that is a new brief, do not do it);
- a test in B to E that you did not write fails because of your patch and the fix is outside §3;
- `test_static_versions.py` fails (do not edit `static_versions.json`);
- you reach 25 tool calls or about 50k tokens (see executor.md, write `Done: steps 1 to k. Left: steps k+1 to n.`);
- you would need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0972-report.md` (600 tokens at most): `git diff --stat`; each command with the last 5 lines of output; the §7 list with PASS or FAIL per line; one line per viewed screenshot (file name plus what you saw); Deviations; Questions; owner steps left. Set `Status: review` in this brief, commit `0972 report` (report and brief only). Do **not** push and do **not** open a PR: the orchestrator does that after reading the report.

## Risk list (for the reviewer)

- `App/app/templates/partials/settings_back_header.html` (shared by about 18 pages: the `help_is_page` branch must not change pages that pass a `help_tip` or no help).
- `App/app/templates/_components.html` (`tip_label` and `settings_heading` now name their "?" buttons site-wide; `help_tip` default is unchanged).
- `App/app/templates/settings.html` (rows moved from `<strong>` plus `help_tip` to `tip_label`; mail status line).

## Owner steps

None for this brief. After review the orchestrator pushes `codex/0972-b14-help-settings` and merges with `scripts/merge-pr-on-green.sh`; the production deploy stays manual.
