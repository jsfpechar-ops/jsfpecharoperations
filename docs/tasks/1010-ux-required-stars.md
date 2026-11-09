# 1010: Red required stars on every field the app cannot continue without

Status: todo
Depends on: 1000 (stars and legend on add-stay and guest forms, already in) | Base commit: HEAD of main when you start | Branch: task/1010-ux-required-stars
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Every control the app cannot continue without shows the red `*` in its label, and no star sits on a field the app does not need. One legend per form ("Fields marked * are required.", key `common.required_legend`, already exists). Template edits plus one static test. No route, validation, CSS, JS or copy change.

Owner's alternative (one note per section row instead of stars) is rejected: stars per field plus the single legend per form is the pattern the app already uses (rule 9: one explanation in one place).

## 2. Context (audit done by the orchestrator; do not re-audit)

Star = `<span class="req-star" aria-hidden="true">*</span>`, drawn by `field_label(for, text, help, optional, guide_href, required)` in `App/app/templates/_components.html` line 39 (6th positional argument, or `required=true`), or written inline. Stars are aria-hidden, so the input must carry `required` or `aria-required="true"`.

Server truth: `validation.validate_apartment` (App/app/validation.py ~1020-1060) requires `uby_idub`, `uby_mark`, `uby_name`, `addr_house_no`, `addr_zip`, `addr_obec`; `uby_ws_user` is required for automatic reporting. The street is NOT required (`addr_street` has no issue in `validate_apartment`; villages have no street) and `tests/test_wizard_old_look_0953.py` pins it, `addr_orient_no`, `addr_obec_cast` and `addr_okres` as unstarred. So the street stays unstarred; tell the owner in the report. If he wants the street required, that is a validation change and a separate brief.

Police fields in the property editor must NOT get the HTML `required` attribute (a host may save the address before the police data; the editor save must keep working). They get the star plus `aria-required="true"`. In the wizard police step they already carry `required`.

### Audit table

| file:line | field | why required | action |
|---|---|---|---|
| `_property_editor.html:298` | `uby_idub` | server rule: IDUB required to report (UBYPORT_CORE) | add star + aria-required |
| `_property_editor.html:301` | `uby_ws_user` | server rule: login required for automatic reporting; wizard has `required` | add star + aria-required |
| `_property_editor.html:303-305` | `uby_ws_password` | needed to file; wizard requires it when none is stored | add star + aria-required only when `not has_password` |
| `_property_editor.html:319` | `uby_mark` | server rule: zkratka required | add star + aria-required |
| `_property_editor.html:323` | `uby_name` | server rule: facility name required | add star + aria-required |
| `_property_calendars.html:77` | `label` (platform select) | `required` attribute | add star |
| `_property_calendars.html:92` | `url` | `required` attribute | add star |
| `setup_wizard/calendar.html:15` | `label` (platform select) | `required` attribute | add star |
| `setup_wizard/calendar.html:30` | `url` | `required` attribute | add star |
| `setup_wizard/property.html:18-19` | `wizard-ares-ico` | `required` attribute (register lookup) | add star |
| `setup_wizard/police.html:38-39` | `uby_ws_password` | `required` when none stored | add star when `not has_password` |
| `_stay_fee_fields.html:11` | `stay_fee_rate_czk` | `required` when `fee_required` | add star when `fee_required` |
| `_stay_fee_fields.html:26` | `stay_fee_vs` | `required` when `fee_required` | add star when `fee_required` |
| `_stay_fee_fields.html:36` | `stay_fee_council_account` | `required` when `fee_required` | add star when `fee_required` |
| `_stay_fee_fields.html:44` | `stay_fee_authority_name` | `required` when `fee_required` | add star when `fee_required` |
| `setup_wizard/_layout.html:43` | legend | the calendar step now has stars | show the legend on `calendar` too |
| `_property_address_fields.html:20-26` | `addr_house_no`, `addr_zip`, `addr_obec` | server rule + `required` | keep (already starred) |
| `_property_address_fields.html:19,21,25-27` | `addr_street`, `addr_orient_no`, `addr_obec_cast`, `addr_okres` | optional in `validate_apartment`; pinned by test 0953 | keep unstarred |
| `_property_identity_fields.html:10` | `internal_name` | `required` | keep |
| `_property_operator.html:16` | `legal_entity_id` | `required` | keep |
| `setup_wizard/property.html:34` | `checkin_hour`, `checkout_hour` | `required` | keep |
| `_property_editor.html:461` | `lock_checkin_hour`, `lock_checkout_hour` | `required` when door codes are on; star pinned by `test_ttlock_setup_0954_browser.py:85` | keep (owner question in report: star shows while codes are off) |
| `setup_wizard/police.html:30-47` | `uby_idub`, `uby_ws_user`, `uby_mark`, `uby_name` | server rule + `required` | keep |
| `_entity_business_fields.html:18,39,47,54` | `ico`, `name`, `seat`, `contact_email` | `required` (ico only outside lookup) | keep |
| `reservations.html:42-54`, `guest_form_admin.html:76,99` | add-stay and guest fields | `required` (brief 1000) | keep |

Counts: add 15 stars (5 editor police, 4 calendar, 1 ICO, 1 wizard password, 4 stay fee) plus 1 legend line, remove 0, keep 20 (+ 5 optional address/contact fields kept unstarred).

Out of scope (follow-up briefs, do not touch): `_account_parts.html` (account number and bank when `account_required`), `payments*.html`, `cleaning_*.html`, `booking_site_setup.html` (`nightly_price_czk`), `invoice_*.html`, `settings.html`, `stay_fee_detail.html`, `setup_wizard/door_lock.html` (retired step), login and signup pages.

## 3. Files

| Path | Action |
|---|---|
| App/app/templates/_property_editor.html | edit (step 1) |
| App/app/templates/_property_calendars.html | edit (step 2) |
| App/app/templates/setup_wizard/calendar.html | edit (step 2) |
| App/app/templates/setup_wizard/property.html | edit (step 2) |
| App/app/templates/setup_wizard/police.html | edit (step 2) |
| App/app/templates/setup_wizard/_layout.html | edit (step 2) |
| App/app/templates/_stay_fee_fields.html | edit (step 2) |
| App/tests/test_required_stars.py | create (step 3) |
| docs/tasks/1010-report.md | create |
| docs/tasks/1010-ux-required-stars.md | Status line only |

Cache keys: none. Only templates change, so no `app2.css` or `app.js` bump and `static_versions.json` stays. No i18n change (the legend key exists), so no `host_i18n.py` edit.

## 4. Steps

For each anchor use `grep -nF "<text>" <file>`. Not found: STOP (§8). Commit after each step with `1010 step k`.

1. **Property editor police fields** (`App/app/templates/_property_editor.html`).
   a. Macro `text_field` (line 15): replace the signature and body so it becomes:
```
{% macro text_field(name, label, value, help='', optional=false, maxlength=none, required=false) %}
  <div class="field">
    {{ field_label(name, label, help, optional, '', required) }}
    <input type="text" id="{{ name }}" name="{{ name }}" value="{{ value or '' }}"
           {%- if maxlength %} maxlength="{{ maxlength }}"{% endif %}
           {%- if required %} aria-required="true"{% endif %}
           {%- if help %} aria-describedby="{{ name }}-help"{% endif %}>
  </div>
{% endmacro %}
```
   b. Four calls, add `required=true` as the last argument (each anchor appears once):
      - `false, 14) }}` becomes `false, 14, required=true) }}` (the `uby_idub` call, line 298)
      - `t('apartment.form.ubyport.login_hint'))` becomes `t('apartment.form.ubyport.login_hint'), required=true)` (`uby_ws_user`, line 301)
      - `false, 6) }}` becomes `false, 6, required=true) }}` (`uby_mark`, line 319)
      - `false, 35) }}` becomes `false, 35, required=true) }}` (`uby_name`, line 323)
      Check each with `grep -nF` that the match is on the named `text_field('uby_...` line; if an anchor matches another line, STOP.
   c. Password (line 303-305): change `t('apartment.form.ubyport.password_help')) }}` to `t('apartment.form.ubyport.password_help'), false, '', not has_password) }}`, and in the `<input type="password" id="uby_ws_password" ...>` tag add `{% if not has_password %}aria-required="true" {% endif %}` directly before `aria-describedby="uby_ws_password-help uby_ws_password-hint"`.
   Run: from `App/`, `.venv/bin/python -m pytest tests/test_0952_lock_section.py tests/test_property_address_required.py -q --tb=short -x 2>&1 | tail -30`.

2. **Calendars, ICO, wizard password, legend, stay fee.**
   a. `_property_calendars.html` line 77 and `setup_wizard/calendar.html` line 14: `<label for="label">{{ t('calendar.platform_label') }}</label>` becomes `<label for="label">{{ t('calendar.platform_label') }}<span class="req-star" aria-hidden="true">*</span></label>`. In both files the `url` call `field_label('url', t('apartment.form.calendars.url_label'), t('apartment.form.calendars.url_hint'), false, '/guide#stays')` gets `, true` before the final `)` : `..., false, '/guide#stays', true)`.
   b. `setup_wizard/property.html` line 18: `<label for="wizard-ares-ico">{{ t('entities.ico') }}</label>` becomes `<label for="wizard-ares-ico">{{ t('entities.ico') }}<span class="req-star" aria-hidden="true">*</span></label>`.
   c. `setup_wizard/police.html` line 38: `t('apartment.form.ubyport.password_help')) }}` becomes `t('apartment.form.ubyport.password_help'), false, '', not has_password) }}`. The input already has `required` when no password is stored.
   d. `setup_wizard/_layout.html` line 43: `wizard_step in ('property', 'police', 'stay_fee')` becomes `wizard_step in ('property', 'calendar', 'police', 'stay_fee')`.
   e. `_stay_fee_fields.html`: in the four `field_label(` calls for `stay_fee_rate_czk`, `stay_fee_vs`, `stay_fee_council_account`, `stay_fee_authority_name`, change the closing `')) }}` after the `*_help'` argument to `'), false, '', fee_required) }}`, e.g. `t('apartment.form.stay_fee.rate_help'), false, '', fee_required) }}`. Do not touch the other three `field_label` calls in that file.
   Run: `.venv/bin/python -m pytest tests/test_wizard_old_look_0953.py tests/test_calendar_platform_required.py tests/test_stay_fee.py -q --tb=short -x 2>&1 | tail -30`.

3. **Static test.** Create `App/tests/test_required_stars.py` with exactly:
```python
"""1010: every control the app cannot continue without has a red star, and every star has a required control."""
import re
from pathlib import Path

T = Path(__file__).resolve().parent.parent / "app" / "templates"
AUDITED = [
    "_property_editor.html", "_property_address_fields.html", "_property_identity_fields.html",
    "_property_operator.html", "_property_calendars.html", "_stay_fee_fields.html",
    "_entity_business_fields.html", "setup_wizard/property.html", "setup_wizard/calendar.html",
    "setup_wizard/police.html", "reservations.html", "guest_form_admin.html",
]
LEGEND_ONCE = ["_property_editor.html", "reservations.html", "guest_form_admin.html", "_entity_business_fields.html"]
# control id -> reason it may be required without a star. Empty on purpose: add nothing without an owner decision.
ALLOW: dict = {}

CTRL = re.compile(r"<(?:input|select|textarea)\b.*?>", re.S)
REQ = re.compile(r"(?<![-\w])required\b")
ID = re.compile(r'\bid="([^"]+)"')
LABEL_STAR = re.compile(r'<label\b[^>]*\bfor="([^"]+)"[^>]*>[^<]*<span class="req-star"')
TAIL = r"(?:true|required|fee_required|not has_password)"


def _text(name):
    return (T / name).read_text(encoding="utf-8")


def _controls(text):
    return [(m.group(1), tag) for tag in CTRL.findall(text) for m in [ID.search(tag)] if m]


def _starred_ids(text):
    ids = set(LABEL_STAR.findall(text))
    for line in text.splitlines():
        m = re.search(r"field_label\('([^']+)'", line)
        if m and (re.search(r"required=(?!false)\w", line) or re.search(rf",\s*{TAIL}\s*\)\s*\}}\}}", line)):
            ids.add(m.group(1))
    return ids


def _macro_labelled(text):
    return re.search(r"field_label\(name,[^\n]*,\s*required\)", text) is not None


def test_every_required_control_has_a_star():
    bad = []
    for name in AUDITED:
        text = _text(name)
        stars = _starred_ids(text)
        for cid, tag in _controls(text):
            if not REQ.search(tag) or cid in stars or cid in ALLOW:
                continue
            if cid == "{{ name }}" and _macro_labelled(text):
                continue
            bad.append(f"{name}: {cid}")
    assert not bad, bad


def test_every_star_has_a_required_control():
    bad = []
    for name in AUDITED:
        text = _text(name)
        controls = _controls(text)
        for sid in _starred_ids(text):
            tags = [tag for cid, tag in controls if cid == sid]
            if tags and not any(REQ.search(t) or "aria-required" in t for t in tags) and sid not in ALLOW:
                bad.append(f"{name}: {sid}")
    assert not bad, bad


def test_editor_police_fields_are_starred_and_aria_required():
    text = _text("_property_editor.html")
    for fid in ("uby_idub", "uby_ws_user", "uby_mark", "uby_name"):
        line = next(ln for ln in text.splitlines() if f"text_field('{fid}'" in ln)
        assert "required=true" in line, fid
    macro = text[text.index("{% macro text_field"):text.index("{% endmacro %}")]
    assert "field_label(name, label, help, optional, '', required)" in macro
    assert 'aria-required="true"' in macro
    assert "uby_ws_password', t('automation.password')" in text and "not has_password" in text


def test_street_and_other_optional_address_fields_stay_unstarred():
    text = _text("_property_address_fields.html")
    for fid in ("addr_street", "addr_orient_no", "addr_obec_cast", "addr_okres"):
        line = next(ln for ln in text.splitlines() if f"address_input('{fid}'" in ln)
        assert "required" not in line and not line.rstrip().endswith("true) }}"), fid


def test_one_legend_per_form_and_wizard_calendar_step_shows_it():
    for name in LEGEND_ONCE:
        assert _text(name).count("required_legend") == 1, name
    layout = _text("setup_wizard/_layout.html")
    assert re.search(r"wizard_step in \([^)]*'calendar'[^)]*\).*required_legend", layout)
```
   Run: `.venv/bin/python -m pytest tests/test_required_stars.py -q --tb=short -x 2>&1 | tail -30`. If it flags a field that is not in the §2 table, do NOT add it to ALLOW: STOP and report the file and id (§8). One fix of the test's own regex is allowed.

4. **Tests and UX gate** (from `App/`; the rows are from `docs/context/test-map.md`: Onboarding/properties, Invoices/stay fee, Calendar, Host pages, Any host template). Each ends in `| tail -30`:
```
.venv/bin/python -m pytest tests/test_required_stars.py tests/test_wizard_old_look_0953.py tests/test_0952_lock_section.py tests/test_property_address_required.py tests/test_calendar_platform_required.py tests/test_times_required_0210.py tests/test_stay_fee.py tests/test_onboarding*.py -q --tb=short -x 2>&1 | tail -30
UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest -rs tests/test_property_navigation_browser.py tests/test_0833_property_editor_browser.py tests/test_ttlock_setup_0954_browser.py tests/test_wizard_old_look_0953_browser.py tests/test_0884_wizard_geometry_browser.py tests/test_design_setup_wizard_browser.py tests/test_onboarding_wizard_browser.py tests/test_host_geometry.py tests/test_design_guardrails_browser.py -q --tb=short -x 2>&1 | tail -30
UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest -rs tests/test_layout_lint_browser.py -q -x 2>&1 | tail -30
```
   If `test_wizard_old_look_0953_browser.py` does not exist, drop it from the list (do not search). Expected: all pass, `0 skipped`, zero host layout findings. A failing test that pins an old star: STOP, report (§8).

5. **Screenshots (rule 7 and 10).** Open once each: `/tmp/shots/layout-lint/property-detail-configured+open-390.png` (editor with Reporting & fees open: look at the five police stars, legend on top), the wizard police page and the wizard calendar page at 390 px (take them from the layout-lint set; names via `ls /tmp/shots/layout-lint | grep -E 'wizard|setup' | head -20`). Write per page in the report what you saw: stars visible and red, label not wrapped onto a second line, legend present once, no star on street, orient no, district, contact. Do not retake.

6. **Report and commit.** Write `docs/tasks/1010-report.md` (600 tokens at most): files changed, last 5 lines of each command in step 4, per page 390 observation, deviations, and these owner questions: (1) the street has no star because the server and test 0953 treat it as optional; (2) the door-code time stars show while door codes are off (kept, pinned by a browser test). Set `Status: review`. Commit with the attribution trailer:
```
Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Cjmb7NmwKqNNoY1XVAeQbg
```
   Open one PR (rule 8: never push to main, no merge). The PR text lists the audit table counts and the per-page UX notes, and ticks the design-system checklist (`docs/design/design-system.md`).

## 5. Do not touch

`_components.html` (the macro is already right), `app2.css`, `app.js`, routes, `validation.py`, i18n files, any template not in §3, any existing test, `static_versions.json`. Do not make the street required. Do not add the HTML `required` attribute to the editor police fields.

## 6. Commands

Steps 1, 2, 3 and 4, each ending in `| tail -30`. Plus from the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`. No full suite.

## 7. Acceptance

- [ ] `tests/test_required_stars.py` green; every other command in step 4 green, browser runs and layout lint `0 skipped`, zero host layout findings.
- [ ] `git diff HEAD~3 --stat | tail -12` shows only the §3 files.
- [ ] Editor police section shows stars on IDUB, login, password (only when none stored), facility abbreviation, facility name; saving the editor with them blank still works (no HTML `required` there).
- [ ] Calendar platform and URL, ICO lookup and the stay-fee wizard fields carry stars; legend shows once on the wizard calendar step.
- [ ] 390 px screenshots of the property editor, wizard police and wizard calendar opened and described in the report.
- [ ] `python3 scripts/context_lint.py` OK.

## 8. Stop and ask

Stop, write the report as `blocked` with `Done: steps 1 to k. Left: steps k+1 to n.`, if: an anchor is not found or matches the wrong line; the new test flags a field outside §2; a test fails twice; a test pins the old look; a file outside §3 seems needed; you reach 25 tool calls or about 50k tokens; you would need push, merge, secrets or deploy.

## 9. Report

`docs/tasks/1010-report.md` as in step 6.

## Risk list (for the reviewer)

`_property_editor.html` `text_field` macro (also used by non-police fields, whose `required` defaults to false); `_stay_fee_fields.html` (`fee_required` is undefined in the editor, so no star there); the regexes in `test_required_stars.py` (multi-line tags, Jinja inside tags).

## Owner steps

1. Open the PR's three 390 px screenshots and confirm the stars are where you expect them.
2. Decide whether the street should become required (a separate validation brief) and whether the door-code time stars should hide while door codes are off.
3. Merge with `scripts/merge-pr-on-green.sh` when the checks are green.
