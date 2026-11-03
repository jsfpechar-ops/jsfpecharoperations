# 0884: Setup wizard in 4 steps, ARES fill, geometry tests

Status: todo
Depends on: none (the RÚIAN include in step 8 needs PR #725; see step 8) | Base commit: 98913fd3 | Branch: claude/project-thread-v21yd0 (already checked out; do not create another)
Executor: Haiku 5.5 | Three sessions: part 1 = steps 0-8, part 2 = steps 9-12, part 3 = steps 13-16. Each session stops at its part's end and hands over (executor.md); the next one continues.

## 1. Objective

The setup wizard goes from 8 steps to 4 required steps (property, calendar, police, guest link). The automation choice moves into the police step. Stay fee, door lock and the demo become "Do next" cards on the done page. The property step gets a no-JS "Fill from register" (ARES) form. New browser tests check the geometry at 6 widths. UbyPort filing correctness beats speed: no legal value is saved without the host pressing a button, and the automation cards show the stored mode (manual for a new property).

## 2. Context

- Hard rules (AGENTS.md): 1 filing correctness first; 2 privacy (no new outbound request in this brief); 6 light mode, forms work without JS; 7 template/CSS change = browser and geometry tests pass with **0 skipped** plus screenshots; 8 never push to `main`; 9 one explanation in one place.
- Already done on this branch (old 0884 part, keep as is): `App/app/ruian.py`, `GET /apartments/ruian-suggest` in `App/app/routes/admin.py`, `App/tests/test_ruian.py`, `App/tests/wizard_taps.py` (baseline script).
- **The old brief was wrong in these points; do not follow it:** (a) there is no `ares.lookup` route. ARES on Entities is a no-JS POST to `/entities` with `fill_from_register=1` and `ico`, handled by `_entities_ares_rerender` (rate limit and cache in `invoices.register_lookup`). (b) No wizard JS is written. (c) The address widget `_ruian_suggest.html` + `static/ruian_suggest.js` is **not** on this branch or on main (it is in open PR #725, commit c5118d0d); step 8 handles that.
- `property_setup.load()` drops marks for steps not in `STEPS`. That is why step 2 adds `KNOWN_STEPS`: old saved marks (stay_fee, door_lock, try_it, automation) must survive a later save.
- The DB default of `apartment.automation_mode` is `'scheduled'`; a property created through the form gets `'manual'` (`_automation_timing_values`). The cards show the stored mode and fall back to manual.
- Browser tests skip unless `UBYHOST_REQUIRE_BROWSER=1` is set. Always set it. Playwright is not in `.venv` here; CI pins `playwright==1.63.0` (`.github/workflows/ci.yml`). Installing it into `.venv` for local runs is allowed. Do **not** add it to any requirements file.
- Executor rules: anchor with `grep -nF`, apply exactly, commit each step as `0884 step k` with `git add <named files>` (never `git add -A`; never stage `docs/tasks/0102-evidence/`).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/property_setup.py` | edit | 4 STEPS, RETIRED_STEPS, KNOWN_STEPS |
| `App/app/routes/onboarding_wizard.py` | edit | retired URLs → done; demo from done page; Wait saves automation |
| `App/app/routes/admin.py` | edit | automation on police save; stale-post guard; lock return; entity `next` |
| `App/app/templates/setup_wizard/police.html` | edit | automation cards; Wait button |
| `App/app/templates/setup_wizard/done.html` | edit | Do next cards |
| `App/app/templates/setup_wizard/property.html` | edit | ARES form; RÚIAN include (step 8) |
| `App/app/templates/entities.html` | edit | hidden `next` on the add form |
| `App/app/host_i18n.py`, `App/app/host_vi_i18n.py` | edit | one key `wizard.done.next_title` |
| `App/app/static/app2.css`, `App/app/templates/base.html`, `App/tests/static_versions.json` | edit | wizard-only CSS, cache key |
| `App/tests/wizard_taps.py`, `App/tests/wizard_walk.py` | edit | counter scope, BEFORE numbers, after-asserts; 4-step walk |
| `App/tests/test_wizard_four_steps_0884.py` | new | server tests |
| `App/tests/test_0884_wizard_geometry_browser.py` | new | geometry at 6 widths + screenshots |
| Old tests in step 12 | edit | follow the 4 steps |
| `docs/tasks/screenshots-0884/` | new | PNGs |
| `docs/tasks/0884-report.md` | rewrite | report |

No other file may change. Do **not** delete the templates `automation.html`, `stay_fee.html`, `door_lock.html`, `try_it.html` (refusal paths in admin.py still name them; a later brief removes them).

## 4. Steps

### Part 1 (session 1): steps 0-8

**Step 0. Check.** From the repo root: `git status --short | tail -5 && git log --oneline -1 | tail -1`. The tree must be clean. HEAD must be 98913fd3, a later commit that changes only docs/tasks/0884-*, or a later `0884 step` commit (check with `git diff --stat 98913fd3 -- App | tail -3`: empty or only 0884 step changes). Otherwise STOP.

**Step 1. Baseline (before any app change).** In `App/tests/wizard_taps.py`, in `_measure_page`, replace
```python
    counter.feed(response.text)
```
with
```python
    # Only the wizard body; the app shell's own controls are not wizard work.
    body = response.text.split("data-setup-wizard", 1)[-1].split('class="setup-wizard-foot"', 1)[0]
    counter.feed(body)
```
Run command C1 (§6). Copy the printed `WIZARD_TAPS` numbers into a constant placed just above `class _FieldCounter`:
```python
# 0884: measured on the eight-step wizard before the change (brief step 1).
BEFORE = {"steps_defined": 8, "steps_visited": N, "posts": N, "fields_total": N, "required_or_empty_total": N}
```
(each N = the printed value). If `steps_defined` is not 8, STOP. Commit.

**Step 2. `App/app/property_setup.py`.**
(a) Replace the whole tuple from `STEPS = (` to its closing `)` (8 names) with:
```python
STEPS = (
    "property",
    "calendar",
    "police",
    "guest_link",
)
# 0884: former steps. Their saved marks stay readable; their URLs go to the done page.
RETIRED_STEPS = ("automation", "stay_fee", "door_lock", "try_it")
KNOWN_STEPS = STEPS + RETIRED_STEPS
```
Keep the comment above it and `TOTAL_STEPS = len(STEPS)`.
(b) In `load()`: `            if step not in STEPS or value not in MARKS:` → `            if step not in KNOWN_STEPS or value not in MARKS:`
(c) In `mark()`: `    if state["finished"] or step not in STEPS or value not in MARKS:` → `    if state["finished"] or step not in KNOWN_STEPS or value not in MARKS:`
Nothing else in this file. Run `cd App && .venv/bin/python -c "from app import property_setup as p; print(p.STEPS, p.TOTAL_STEPS)" 2>&1 | tail -3`. Commit.

**Step 3. `App/app/routes/onboarding_wizard.py`.**
(a) In `setup_step`, replace
```python
    if step != "done" and step not in property_setup.STEPS:
        return _back(f"/apartments/{apartment_id}/setup")
```
with
```python
    if step in property_setup.RETIRED_STEPS:
        # 0884: automation, stay fee, door lock and the demo left the wizard.
        return _back(wizard_return_to(apartment_id, "done"))
    if step != "done" and step not in property_setup.STEPS:
        return _back(f"/apartments/{apartment_id}/setup")
```
(b) In `setup_action`, after the line `    overview = f"/apartments/{apartment_id}?view=overview"` insert:
```python
    if step == "try_it" and action == "demo":
        # 0884: "Try it yourself" is a Do next card on the done page, so the demo
        # starts without a current wizard step. Demo stays are never reported.
        stay_id = demo.create_demo_stay(apartment_id)
        db.audit("property_setup_step", f"apartment={apartment_id} step=try_it action=demo")
        lang = host_i18n.lang_from_request(request)
        return _back(f"/l/{guest_slug.link_key(apartment)}/demo/{stay_id}?lang={lang}")
```
(c) Replace
```python
    if action == "wait" and step == "police":
        property_setup.mark(apartment_id, step, "waiting")
```
with
```python
    if action == "wait" and step == "police":
        if "automation_mode" in form:
            # 0884: the police step carries the automation choice; Wait keeps it too.
            admin_routes = _admin_helpers()
            timing_error = admin_routes.automation_choice_error(form)
            if timing_error:
                refused = refuse_setup_save(request, apartment, form, operator_error=timing_error)
                if refused:
                    return refused
                return _back(guide["url"])
            db.update("apartment", apartment_id, admin_routes._automation_timing_values(form))
            db.audit("apartment_updated", f"id={apartment_id}")
            property_setup.mark(apartment_id, "automation", "done")
        property_setup.mark(apartment_id, step, "waiting")
```
(d) In `refuse_setup_save`, replace `    if step == "automation":` with `    if step == "police" and "automation_mode" in form:` (the two lines under it stay).
Run C2 with only `tests/test_onboarding.py`. Commit.

**Step 4. `App/app/routes/admin.py`** (five edits; grep each anchor).
(a) Insert directly above `def _apartment_payload(form) -> Dict[str, Any]:`:
```python
def automation_choice_error(form) -> Optional[str]:
    """0884: the timing save's own checks, for the police step's cards. A flash key or None."""
    mode = _form_str(form, "automation_mode")
    if mode not in reporting.AUTOMATION_MODES:
        return "flash.properties.timing_invalid"
    if mode == "scheduled":
        hours = _form_int(form, "submit_after_hours")
        if hours is None or not 1 <= hours <= 48:
            return "flash.properties.timing_hours"
    return None


```
(b) In `_wizard_step_payload`, replace
```python
        payload["uby_mark"] = payload["uby_mark"].upper()
    elif step == "stay_fee":
```
with
```python
        payload["uby_mark"] = payload["uby_mark"].upper()
        if "automation_mode" in form:
            # 0884: the automation choice cards live on the police step.
            payload.update(_automation_timing_values(form))
    elif step == "stay_fee":
```
(c) In `_save_apartment_form`, replace `    form = _with_lock_tab_hours(form, apartment)` with
```python
    form = _with_lock_tab_hours(form, apartment)
    if _form_str(form, "setup_step") in property_setup.RETIRED_STEPS:
        # 0884: a page left open from the old eight-step wizard saves nothing.
        from .onboarding_wizard import wizard_return_to

        return _back(wizard_return_to(apartment_id, "done")), False
```
then replace
```python
    password = _form_str(form, "uby_ws_password")
    if setup_step == "police":
        police_errors = _wizard_police_format_errors(apartment, payload, password)
```
with
```python
    if setup_step == "police" and "automation_mode" in form:
        timing_error = automation_choice_error(form)
        if timing_error:
            from .onboarding_wizard import refuse_setup_save

            refused = refuse_setup_save(request, apartment, form, operator_error=timing_error)
            if refused:
                return refused, False
    password = _form_str(form, "uby_ws_password")
    if setup_step == "police":
        police_errors = _wizard_police_format_errors(apartment, payload, password)
```
(d) In `_setup_after_save`, insert directly above `    if step == "property" and property_setup.property_details_complete(apartment):`:
```python
    if step == "police" and "automation_mode" in form:
        # 0884: saving the police step answers the automation question too.
        property_setup.mark(apartment_id, "automation", "done")
```
(e) In `_lock_property_return`, delete these three lines:
```python
    if match.group(2):
        # 0203: the setup wizard's lock step; every lock answer returns to it.
        return f"/apartments/{apartment_id}/setup/door_lock"
```
and put this comment line in their place: `    # 0884: the wizard has no lock step; an old wizard return_to lands on the lock settings.`
(f) In `create_entity`, replace
```python
    entity_id = db.insert("legal_entity", payload)
    _resolve_controller_alerts(entity_id)
```
with
```python
    entity_id = db.insert("legal_entity", payload)
    _resolve_controller_alerts(entity_id)
    next_path = _entity_next(_form_str(form, "next"))
    if next_path:
        # 0884: "Fill from register" on the wizard's property step returns there.
        return _back(next_path, msg=_flash(request, "flash.entities.added", name=payload["name"]))
```
Run `cd App && .venv/bin/python -c "import app.main" 2>&1 | tail -3` (no output = OK). Commit.

**Step 5. `App/app/templates/setup_wizard/police.html`.**
(a) `{% from "_components.html" import field_label, help_tip with context %}` → `{% from "_components.html" import field_label, help_tip, choice_card with context %}`
(b) After the line `  <input type="hidden" name="default_purpose" value="{{ values.default_purpose or '10' }}">` add `  <input type="hidden" name="step" value="police">`.
(c) Replace
```
    {{ text_field('uby_contact', t('automation.contact'), values.uby_contact, t('apartment.form.ubyport.contact_hint'), true, 50) }}
  </div>
</form>
```
with
```
    {{ text_field('uby_contact', t('automation.contact'), values.uby_contact, t('apartment.form.ubyport.contact_hint'), true, 50) }}
  </div>
  {#- 0884: the former automation step. The stored mode is shown; a new property stores manual. -#}
  {% set auto_mode = values.automation_mode if values.automation_mode in ('manual', 'scheduled', 'immediate') else 'manual' %}
  <h3 class="property-section-title">{{ t('wizard.question.automation') }}{{ help_tip('wiz-why-automation', t('why.automation')) }}</h3>
  <div class="ui-choice-cards">
    {{ choice_card('automation_mode', 'manual', t('automation.mode.manual'), auto_mode == 'manual', 'wizard-manual-help', t('wizard.automation.manual_detail')) }}
    {% call choice_card('automation_mode', 'scheduled', t('automation.mode.scheduled'), auto_mode == 'scheduled', 'wizard-scheduled-help', t('wizard.automation.scheduled_detail')) %}
      <div class="field inline-hours">
        <label for="submit_after_hours">{{ t('automation.hours') }}</label>
        <input type="number" id="submit_after_hours" name="submit_after_hours" min="1" max="48" value="{{ values.submit_after_hours if values.submit_after_hours is not none else 2 }}">
      </div>
    {% endcall %}
    {{ choice_card('automation_mode', 'immediate', t('automation.mode.immediate'), auto_mode == 'immediate', 'wizard-immediate-help', t('wizard.automation.immediate_detail')) }}
  </div>
</form>
```
(d) Replace the whole Wait form (5 lines, from `  <form method="post" action="/apartments/{{ apartment.id }}/setup" class="inline" id="police-wait-form">` to its `  </form>`) with one line:
```
  <button class="ui-btn ui-btn-secondary setup-wizard-wait" type="submit" form="police-form" formaction="/apartments/{{ apartment.id }}/setup" name="action" value="wait" formnovalidate>{{ t('setup_guide.reporting.wait') }}</button>
```
Commit.

**Step 6. `App/app/templates/setup_wizard/done.html`.** Replace
```
  {% endfor %}
</ul>
{% if not missing_row %}
```
with
```
  {% endfor %}
</ul>
<h2 class="setup-wizard-section-title">{{ t('wizard.done.next_title') }}</h2>
<ul class="setup-wizard-checklist host-property-grid setup-wizard-next" data-setup-next>
  <li data-setup-next-step="stay_fee">
    <a class="host-property-card setup-summary-card setup-next-card" href="/apartments/{{ apartment.id }}?view=settings&amp;section=reporting#stay-fee-settings">
      <span class="setup-summary-icon">{{ nav_icon('coins') }}</span>
      <span class="setup-summary-copy"><strong>{{ t('wizard.step.stay_fee') }}</strong></span>
    </a>
  </li>
  {% if lock_available %}
  <li data-setup-next-step="door_lock">
    <a class="host-property-card setup-summary-card setup-next-card" href="/apartments/{{ apartment.id }}?view=settings&amp;section=lock#door-code">
      <span class="setup-summary-icon">{{ nav_icon('lock') }}</span>
      <span class="setup-summary-copy"><strong>{{ t('wizard.step.door_lock') }}</strong></span>
    </a>
  </li>
  {% endif %}
  <li data-setup-next-step="try_it">
    <form method="post" action="/apartments/{{ apartment.id }}/setup" class="host-property-card setup-summary-card setup-next-card">
      <input type="hidden" name="_csrf" value="{{ csrf_token }}">
      <input type="hidden" name="step" value="try_it">
      <span class="setup-summary-icon">{{ nav_icon('users') }}</span>
      <span class="setup-summary-copy"><strong>{{ t('wizard.step.try_it') }}</strong></span>
      <button class="ui-btn ui-btn-secondary" type="submit" name="action" value="demo">{{ t('setup_guide.try.create') }}</button>
    </form>
  </li>
</ul>
{% if not missing_row %}
```
Commit.

**Step 7. i18n.** First `grep -rnF '"wizard.done.next_title"' App/app | tail -3` must print nothing (else STOP). Then add one line after each anchor:
- `App/app/host_i18n.py` after `        "wizard.done.title": "Setup summary",` → `        "wizard.done.next_title": "Do next",`
- `App/app/host_i18n.py` after `        "wizard.done.title": "Shrnutí nastavení",` → `        "wizard.done.next_title": "Co dál",`
- `App/app/host_vi_i18n.py` after `    "wizard.done.title": "Tóm tắt thiết lập",` → `    "wizard.done.next_title": "Việc tiếp theo",`
Commit.

**Step 8. `App/app/templates/setup_wizard/property.html`.**
(a) ARES form. Replace `{{ workflow_strip(none) }}` with
```
{{ workflow_strip(none) }}
{% if not entities %}
{#- 0884: no business yet. The register lookup prefills the business form on /entities; the host checks it and saves it there, then comes back here. -#}
<form method="post" action="/entities" class="wizard-ares" id="wizard-ares-form">
  <input type="hidden" name="_csrf" value="{{ csrf_token }}">
  <input type="hidden" name="next" value="/apartments/{{ apartment.id }}/setup/property">
  <div class="field">
    <label for="wizard-ares-ico">{{ t('entities.ico') }}</label>
    <input type="text" id="wizard-ares-ico" name="ico" inputmode="numeric" maxlength="8" autocomplete="off" required>
  </div>
  <button class="ui-btn ui-btn-secondary" type="submit" name="fill_from_register" value="1">{{ t('ares.fill') }}</button>
</form>
{% endif %}
```
(b) In `App/app/templates/entities.html` replace
```
  <form method="post" action="/entities" enctype="multipart/form-data">
    <input type="hidden" name="_csrf" value="{{ csrf_token }}">
    {{ business_form_body('new_', new_entity or none, '', ares_error, ares_note) }}
```
with the same three lines plus, after the `_csrf` line: `    {% if next_path %}<input type="hidden" name="next" value="{{ next_path }}">{% endif %}`
(c) RÚIAN include. Run `test -f App/app/templates/_ruian_suggest.html && grep -c data-ruian-suggest App/app/templates/_property_address_fields.html | tail -1`. Only if the file exists **and** the count is 1 or more: replace `  {% include "_property_address_fields.html" %}` with that line plus a next line `  {% include "_ruian_suggest.html" %}`. Otherwise skip (c), do not create either file, and write "RÚIAN include skipped: waits for PR #725" under Deviations.
Commit.

**Step 8b. CSS** (still part 1). In `App/app/static/app2.css` make these exact replacements (each old text occurs once):
- `.wiz-count{margin:0 0 8px;font-size:13px;` → `.wiz-count{margin:0 0 8px;font-size:14px;`
- `.setup-wizard-done-count{margin:0;font-size:13px;` → `.setup-wizard-done-count{margin:0;font-size:14px;`
- `.required-legend{margin:0 0 12px;font-size:12px;` → `.required-legend{margin:0 0 12px;font-size:14px;`
- `padding:10px 12px;font-size:13px;line-height:1.5}` → `padding:10px 12px;font-size:14px;line-height:1.5}`
- `min-height:72px;padding:14px 16px;` → `min-height:72px;padding:16px;`
- `box-sizing:border-box;white-space:nowrap}` (the `.setup-summary-copy .ui-badge` rule) → `box-sizing:border-box;white-space:nowrap;font-size:14px}`
- `.setup-summary-action{font-size:13px;` → `.setup-summary-action{font-size:14px;`
- `.setup-wizard-note-box{margin:16px 0 0;padding:14px 16px;` → `.setup-wizard-note-box{margin:16px 0 0;padding:16px;`
Then insert after the line that starts `body.v2 .wiz-page .setup-summary-action{`:
```
body.v2 .wiz-page .setup-next-card{text-decoration:none;color:inherit;flex-wrap:wrap;row-gap:12px}
body.v2 .wiz-page .setup-next-card .ui-btn{margin-left:auto}
body.v2 .wiz-page .wizard-ares{display:flex;flex-wrap:wrap;align-items:flex-end;gap:12px;padding:16px;margin:0 0 20px;border:1px solid var(--line);border-radius:16px}
body.v2 .wiz-page .wizard-ares .field{flex:1 1 180px;margin:0}
```
In `App/app/templates/base.html`: `/static/app2.css?v=20261103-0852` → `/static/app2.css?v=20261103-0884`. Run C5. Commit. **End of part 1:** write the report as `blocked` with `Done: steps 0 to 8b. Left: steps 9 to 16.` and stop.

### Part 2 (session 2): steps 9-12

**Step 9. `App/tests/wizard_walk.py`.** Replace `_ACTIONS` with `{"calendar": "skip", "police": "wait", "guest_link": "done"}`. In `walk_to`, delete the whole `if step == "automation":` branch so the loop body is: the return check, then `response = client.post(base, data={"step": step, "action": _ACTIONS[step]}, follow_redirects=False)`, then the assert. Docstring: `"""Answer each step (police: wait) until ``target`` is current.`. Commit.

**Step 10. `App/tests/wizard_taps.py` after-numbers.** Change the module docstring's second line to `Before/after measurement: the wizard needs at most half the steps and POSTs.` At the end of `test_wizard_baseline_numbers` add:
```python
    # 0884: after-numbers. Steps and POSTs at most half of the eight-step wizard.
    assert report["steps_defined"] * 2 <= BEFORE["steps_defined"], report
    assert report["steps_visited"] * 2 <= BEFORE["steps_visited"], report
    assert report["posts"] * 2 <= BEFORE["posts"], report
    assert report["required_or_empty_total"] <= BEFORE["required_or_empty_total"], report
```
Run C1. If an assert fails, STOP (do not change BEFORE). Copy the printed after-numbers into the report. Commit.

**Step 11. New `App/tests/test_wizard_four_steps_0884.py`** (write exactly; fix only an obvious typo):
```python
"""0884: four required wizard steps; the rest are Do next cards on the done page."""
from __future__ import annotations

import json
from urllib.parse import urlparse

from app import auth, db, property_setup
from app.routes import invoices as invoice_routes
from tests.test_onboarding_wizard_survival import POLICE, _full_apartment, host  # noqa: F401
from tests.wizard_walk import walk_to

RETIRED = ("automation", "stay_fee", "door_lock", "try_it")


def _path(response) -> str:
    return urlparse(response.headers.get("location", "")).path


def _police_form(flat, host, **extra):
    data = {**POLICE, "setup_step": "police", "internal_name": flat["internal_name"],
            "legal_entity_id": str(host["entity"]), "default_purpose": "10",
            "return_to": f"/apartments/{flat['id']}/setup/guest_link"}
    data.update(extra)
    return data


def test_four_required_steps():
    assert property_setup.STEPS == ("property", "calendar", "police", "guest_link")
    assert property_setup.TOTAL_STEPS == 4
    assert set(property_setup.RETIRED_STEPS) == set(RETIRED)


def test_retired_step_urls_go_to_done(host):  # noqa: F811
    flat = _full_apartment(host)
    for step in RETIRED:
        response = host["client"].get(f"/apartments/{flat['id']}/setup/{step}", follow_redirects=False)
        assert response.status_code == 303, step
        assert _path(response) == f"/apartments/{flat['id']}/setup/done", step


def test_saved_marks_of_retired_steps_stay_valid(host):  # noqa: F811
    flat = _full_apartment(host)
    old = {"stay_fee": "skipped", "door_lock": "not_needed", "try_it": "done", "automation": "done", "police": "waiting"}
    db.set_setting(f"property_setup:{flat['id']}", json.dumps(
        {"steps": old, "finished": False, "hidden": False, "legacy": False}))
    property_setup.mark(flat["id"], "calendar", "skipped")
    assert property_setup.load(flat["id"])["steps"] == {**old, "calendar": "skipped"}
    assert host["client"].get(f"/apartments/{flat['id']}/setup/done?lang=en").status_code == 200


def test_done_page_shows_four_rows_and_do_next_cards(host):  # noqa: F811
    flat = _full_apartment(host)
    page = host["client"].get(f"/apartments/{flat['id']}/setup/done?lang=en").text
    assert page.count('data-setup-summary-step="') == 4
    assert 'data-setup-next-step="stay_fee"' in page
    assert 'data-setup-next-step="try_it"' in page


def test_police_save_stores_the_automation_choice(host):  # noqa: F811
    flat = _full_apartment(host)
    data = _police_form(flat, host, automation_mode="immediate", submit_after_hours="6")
    response = host["client"].post(f"/apartments/{flat['id']}", data=data, follow_redirects=False)
    assert response.status_code == 303, response.text[:300]
    row = db.query_one("SELECT automation_mode FROM apartment WHERE id = ?", (flat["id"],))
    assert row["automation_mode"] == "immediate"
    assert property_setup.load(flat["id"])["steps"].get("automation") == "done"


def test_police_save_with_bad_hours_saves_nothing(host):  # noqa: F811
    flat = _full_apartment(host)
    data = _police_form(flat, host, automation_mode="scheduled", submit_after_hours="0", uby_name="Changed name")
    response = host["client"].post(f"/apartments/{flat['id']}", data=data, follow_redirects=False)
    assert response.status_code == 400
    row = db.query_one("SELECT automation_mode, submit_after_hours, uby_name FROM apartment WHERE id = ?", (flat["id"],))
    assert (row["automation_mode"], row["submit_after_hours"], row["uby_name"]) == ("scheduled", 6, POLICE["uby_name"])


def test_police_wait_keeps_the_automation_choice(host):  # noqa: F811
    flat = _full_apartment(host)
    db.update("apartment", flat["id"], {"uby_idub": ""})
    client = host["client"]
    assert walk_to(client, flat["id"], "police") == "police"
    response = client.post(f"/apartments/{flat['id']}/setup", data={
        "step": "police", "action": "wait", "setup_step": "police",
        "automation_mode": "manual", "submit_after_hours": "24"}, follow_redirects=False)
    assert response.status_code == 303
    assert db.query_one("SELECT automation_mode FROM apartment WHERE id = ?", (flat["id"],))["automation_mode"] == "manual"
    steps = property_setup.load(flat["id"])["steps"]
    assert steps["police"] == "waiting" and steps["automation"] == "done"


def test_stale_post_from_a_retired_step_saves_nothing(host):  # noqa: F811
    flat = _full_apartment(host)
    response = host["client"].post(f"/apartments/{flat['id']}", data={
        "setup_step": "stay_fee", "stay_fee_rate_czk": "99", "uby_idub": "",
        "return_to": f"/apartments/{flat['id']}/setup/door_lock"}, follow_redirects=False)
    assert response.status_code == 303
    assert _path(response) == f"/apartments/{flat['id']}/setup/done"
    row = db.query_one("SELECT stay_fee_rate_czk, uby_idub FROM apartment WHERE id = ?", (flat["id"],))
    assert row["stay_fee_rate_czk"] == 50 and row["uby_idub"] == POLICE["uby_idub"]


def test_try_it_card_starts_the_demo_after_setup_is_finished(host):  # noqa: F811
    flat = _full_apartment(host)
    property_setup.finish(flat["id"])
    response = host["client"].post(f"/apartments/{flat['id']}/setup",
                                   data={"step": "try_it", "action": "demo"}, follow_redirects=False)
    assert response.status_code == 303
    assert _path(response).startswith("/l/") and "/demo/" in _path(response)


def test_register_fill_from_the_property_step(host, monkeypatch):  # noqa: F811
    db.update("legal_entity", host["entity"], {"archived_at": db.utcnow()})
    apt = db.insert("apartment", {"internal_name": "No business yet", "owner_user_id": host["owner"],
                                  "permalink_token": auth.new_permalink_token(), "active": 1, "created_at": db.utcnow()})
    client = host["client"]
    page = client.get(f"/apartments/{apt}/setup/property?lang=en").text
    assert 'id="wizard-ares-form"' in page and 'name="fill_from_register"' in page
    monkeypatch.setattr(invoice_routes, "register_lookup",
                        lambda owner, lang, ico: ({"name": "Register s.r.o.", "seat": "Brno", "dic": "CZ12345678"}, None))
    back = f"/apartments/{apt}/setup/property"
    filled = client.post("/entities", data={"fill_from_register": "1", "ico": "12345678", "next": back})
    assert filled.status_code == 200
    assert "Register s.r.o." in filled.text and f'name="next" value="{back}"' in filled.text
    saved = client.post("/entities", data={"name": "Register s.r.o.", "seat": "Brno", "ico": "12345678",
                                           "contact_email": "wizard@example.test", "next": back},
                        follow_redirects=False)
    assert saved.status_code == 303 and _path(saved) == back
```
If the last POST is refused, read the flash in its `location` and add the one missing business field to that dict, once. Run C1. Commit.

**Step 12. Old tests that hard-code 8 steps.** Rules, in this order of preference:
- R1 count or list: `of 8` → `of 4`; page lists in guardrail/v2 tests: delete the entries for `setup/stay_fee`, `setup/door_lock`, `setup/automation`, `setup/try_it`.
- R2 a walk or click-through: police save now goes straight to `/setup/guest_link`; `guest_link` done goes to `/setup/done`. Drop waits/clicks/screenshots for automation, stay_fee, door_lock, try_it. A post to `/automation-timing` with `setup_step=automation` becomes `automation_mode`/`submit_after_hours` added to the police save data (or to the police `wait` post data together with `setup_step=police`).
- R3 a `return_to` or `walk_to` target of a retired step that is not the test's subject → use `guest_link` (or `done` when it was the last step).
- R4 a test whose **subject** is a retired wizard page (its HTML, its refusal, its skip): delete the test function and list its name and one reason in the report.
- Never delete or weaken an assertion about `uby_*` fields, the password, `report_complete`, police `waiting`, or demo-stay exclusion. If one fails and only weakening would pass it, STOP.

Known places (line numbers are approximate; grep the text):
| File | What |
|---|---|
| `App/tests/test_wizard_friendly_0273.py` | R1 (`of 8` twice) |
| `App/tests/test_design_guardrails_browser.py` | R1 (4 entries near line 43, 1 near line 478) |
| `App/tests/test_0800_v2_remaining_pages_browser.py` | R1 (`setup-stay-fee` entry) |
| `App/tests/test_door_code_window_browser.py` | R1 (`wizard-lock` entry) |
| `App/tests/test_onboarding_followup_browser.py` | delete the try_it block (from `page.goto(f"{base}/setup/try_it` through its `_shot(...)` line); marks on retired steps may stay |
| `App/tests/test_smart_locks_page.py` | `test_the_setup_wizard_lock_step_gets_every_lock_answer_back`: rename to `..._goes_to_the_lock_settings`; both `startswith(wizard)` asserts become `startswith(f"/apartments/{flats[0]}?view=settings&section=lock")`; drop the `#smart-locks-share` endswith; keep the foreign assert |
| `App/tests/test_wizard_second_lock_0400.py` | R4 for the four wizard-lock tests; keep `test_the_door_lock_tab_still_shows_its_sharing_steps` |
| `App/tests/test_fee_setup_compatibility.py` | R4 `test_the_wizard_asks_four_fee_boxes` |
| `App/tests/test_onboarding_wizard_survival.py` | `test_cross_step_guarded_fields_survive_each_wizard_post`: remove the try_it, stay_fee, door_lock, automation entries and fix the `if step in (...)` line; R4 `test_stay_fee_save_skips_door_lock_when_unavailable`, `test_try_it_skip_deletes_demo_stay`, `test_missing_property_hours_from_lock_step_keep_saved_property_draft`; `test_demo_action_teaches_pin...`: replace `walk_to(..., "try_it")` with posting `{"step": "try_it", "action": "demo"}` directly; R2/R3 for the rest; `try_it` out of the `missing_step` parametrize list |
| `App/tests/test_onboarding_wizard_browser.py` | journey test: after the police click `page.wait_for_url("**/setup/guest_link**")`, then guest_link `done` → `**/setup/done**`; assert `page.locator("[data-setup-next-step=try_it]").is_visible()` on done; R4 `test_fee_refusal_shows_error_on_wizard`, `test_rejected_fee_save_stays_on_stay_fee_with_typed_values`, `test_try_it_open_skip_moves_on`, `test_door_lock_saved_without_a_lock_stays_on_door_lock`, `test_done_count_includes_skipped_door_lock_when_unavailable`; `test_automation_invalid_hours_rerenders_the_step` → post the bad hours with the police save and expect 400 on the police page; R2/R3 for the rest |

Triage with C3 (lists every failure at once), fix by the rules, rerun C3, then C2. If more than 12 test functions would need deleting in total, STOP. Commit after each file. **End of part 2:** report `blocked`, `Done: steps 0 to 12. Left: steps 13 to 16.`

### Part 3 (session 3): steps 13-16

**Step 13. Browser setup.** Run C0. If Chromium cannot launch after the install, STOP for the browser steps: write the report as `blocked` (CI runs them) and still do step 16.

**Step 14. New `App/tests/test_0884_wizard_geometry_browser.py`** (write exactly):
```python
"""0884: the wizard pages at six widths: text inset, button gaps, overlap, text size, no sideways scroll."""
import json
import os
import secrets
from pathlib import Path

import pytest

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

from app import auth, db
from tests.browser_support import chromium_launch_kwargs
from tests.test_host_geometry import _browser_session_cookie, base  # noqa: F401

SHOTS = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0884"
WIDTHS = (320, 390, 768, 1024, 1280, 1440)
PAGES = ("property", "property-no-business", "calendar", "police", "guest_link", "done")
SHOT_PAGES = ("property", "property-no-business", "police", "done")
SUGGEST = [{"label": "Synthetická 12/3, Brno", "fields": {
    "addr_street": "Synthetická", "addr_house_no": "12", "addr_orient_no": "3", "addr_zip": "60200",
    "addr_obec": "Brno", "addr_obec_cast": "Černá Pole", "addr_okres": "Brno-město"}}]
CHECK = r"""() => {
  const root = document.querySelector('.setup-wizard');
  const CARD = '.setup-summary-card, .ui-choice-card, .setup-wizard-note-box, .setup-wizard-celebrate, .wizard-ares';
  const BTN = 'button, a.ui-btn, input[type=submit]';
  const CTRL = 'button, a.ui-btn, input:not([type=hidden]), select, textarea';
  const shown = el => {
    for (let n = el; n && n !== document.body; n = n.parentElement) {
      const s = getComputedStyle(n);
      if (s.display === 'none' || s.visibility === 'hidden' || s.opacity === '0') return false;
    }
    const r = el.getBoundingClientRect();
    return r.width > 1 && r.height > 1;
  };
  const texts = [];
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const node = walker.currentNode, el = node.parentElement;
    if (!node.textContent.trim() || !el || el.closest('.help-tip-body, .visually-hidden, .sr-only, script, style, noscript, option, textarea') || !shown(el)) continue;
    const range = document.createRange();
    range.selectNodeContents(node);
    for (const r of range.getClientRects()) if (r.width > 0 && r.height > 0) texts.push({el, r, text: node.textContent.trim().slice(0, 40)});
  }
  const bad = {small: [], inset: [], gap: [], overlap: [], scroll: []};
  for (const t of texts) {
    const size = parseFloat(getComputedStyle(t.el).fontSize);
    if (size < 14) bad.small.push([t.text, size]);
    const card = t.el.closest(CARD);
    if (card) {
      const c = card.getBoundingClientRect();
      const inset = Math.min(t.r.left - c.left, c.right - t.r.right, t.r.top - c.top, c.bottom - t.r.bottom);
      if (inset < 15.5) bad.inset.push([t.text, Math.round(inset)]);
    }
  }
  const buttons = [...root.querySelectorAll(BTN)].filter(b => !b.matches('.help-tip-btn') && shown(b));
  for (const b of buttons) {
    const br = b.getBoundingClientRect();
    for (const t of texts) {
      if (b.contains(t.el)) continue;
      const dx = Math.max(0, br.left - t.r.right, t.r.left - br.right);
      const dy = Math.max(0, br.top - t.r.bottom, t.r.top - br.bottom);
      if (Math.max(dx, dy) < 11.5) bad.gap.push([(b.textContent || b.value || '').trim().slice(0, 30), t.text, Math.round(Math.max(dx, dy))]);
    }
  }
  const controls = [...root.querySelectorAll(CTRL)].filter(shown);
  for (let i = 0; i < controls.length; i++) for (let j = i + 1; j < controls.length; j++) {
    if (controls[i].contains(controls[j]) || controls[j].contains(controls[i])) continue;
    const a = controls[i].getBoundingClientRect(), c = controls[j].getBoundingClientRect();
    const w = Math.min(a.right, c.right) - Math.max(a.left, c.left), h = Math.min(a.bottom, c.bottom) - Math.max(a.top, c.top);
    if (w > 1 && h > 1) bad.overlap.push([controls[i].outerHTML.slice(0, 60), controls[j].outerHTML.slice(0, 60)]);
  }
  if (document.documentElement.scrollWidth > innerWidth) bad.scroll.push(document.documentElement.scrollWidth);
  return bad;
}"""


def _flat(with_business: bool):
    username = f"g884{secrets.token_hex(3)}"
    owner = auth.create_account(f"{username}@example.test", "Geometry", role="host", username=username)
    entity = None
    if with_business:
        entity = db.insert("legal_entity", {"name": "Geometry s.r.o.", "owner_user_id": owner, "created_at": db.utcnow()})
    apartment = db.insert("apartment", {"internal_name": "Geometry flat", "owner_user_id": owner, "legal_entity_id": entity,
                                        "permalink_token": f"g8{secrets.token_hex(4)}", "active": 1, "created_at": db.utcnow()})
    return username, apartment


@pytest.mark.parametrize("lang", ["en", "cs"])
@pytest.mark.parametrize("width", WIDTHS)
def test_wizard_pages_keep_their_geometry(base, width, lang):
    failures = {}
    with sync_api.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(**chromium_launch_kwargs())
        except Exception as exc:
            if REQUIRE_BROWSER:
                raise
            pytest.skip(f"Chromium is not available: {exc}")
        for with_business in (True, False):
            username, apartment = _flat(with_business)
            context = browser.new_context(viewport={"width": width, "height": 900})
            context.add_cookies([{"name": auth.SESSION_COOKIE, "value": _browser_session_cookie(username), "url": base + "/"}])
            page = context.new_page()
            for name in PAGES:
                if (name == "property-no-business") == with_business:
                    continue
                step = "property" if name == "property-no-business" else name
                page.goto(f"{base}/apartments/{apartment}/setup/{step}?lang={lang}")
                page.wait_for_selector(".setup-wizard", timeout=30000)
                bad = {key: value for key, value in page.evaluate(CHECK).items() if value}
                if bad:
                    failures[name] = bad
                if lang == "en" and width in (390, 1280) and name in SHOT_PAGES:
                    SHOTS.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(SHOTS / f"{name}-{width}.png"), full_page=True)
                if name == "property" and lang == "en" and width == 390 and page.locator("input[data-ruian-suggest]").count():
                    page.route("**/apartments/ruian-suggest*", lambda route: route.fulfill(
                        status=200, content_type="application/json", body=json.dumps(SUGGEST)))
                    page.fill("input[data-ruian-suggest]", "Synt")
                    page.wait_for_selector(".ruian-suggest li", timeout=5000)
                    page.screenshot(path=str(SHOTS / "property-suggest-390.png"), full_page=True)
            context.close()
        browser.close()
    assert not failures, failures
```
Run C4. **CSS fix rounds (at most 2).** Each failure names the page, the rule and the text. Fix only in `App/app/static/app2.css`, only with selectors that start with `body.v2 .wiz-page`, by changing padding, gap, margin, font-size (to 14px or more) or `flex-wrap`. Typical fixes: `gap:12px` on a head row that holds a button beside a title (`.setup-wizard-head`, `.police-section-head`); padding `16px` on a card. Never move a button over text, never hide text, never change a template for this. After round 2, if failures remain, STOP and paste them into the report. After each CSS change run C5 again (static versions). Commit each round.

**Step 15. Regression.** Run C2, C4, C6, C7, C5, C8. All pass, `0 skipped` in each browser run. Look at each screenshot once (`property-390`, `property-no-business-390`, `police-390`, `done-390`, and the 1280 ones): no text on a card edge, no button on text. Commit the PNGs: `git add docs/tasks/screenshots-0884/*.png`.

**Step 16. Report and PR.** Rewrite `docs/tasks/0884-report.md` (§9), keep its old "TODO-verify" and "Privacy and limits" sections word for word. Set this brief to `Status: review`. Run C8. Commit `0884 report`. Push the branch (`git push origin claude/project-thread-v21yd0 2>&1 | tail -5`) and open one PR to `main` titled `0884: setup wizard in 4 steps, ARES fill, wizard geometry tests`, body = the report's summary plus the attribution lines from the session.

## 5. Do not touch

- Signup, default check-in/check-out times (`checkin_hour`/`checkout_hour` defaults), guest-link send: other threads own them.
- `App/app/ruian.py`, its route, `App/tests/test_ruian.py`, any `.js` file, `_property_address_fields.html`, `_property_operator.html`, `_property_editor.html`.
- The four retired templates (keep them, do not edit them). `App/app/reporting.py`, `App/app/claim.py`, UbyPort code. `docs/context/*`.
- No migration, no new setting key, no new dependency, no requirements change.

## 6. Commands

All from `App/`. Expected: `passed`, no `failed`, browser runs `0 skipped`.
- C0 `.venv/bin/python -c "import playwright" 2>&1 | tail -1 || (.venv/bin/pip install playwright==1.63.0 2>&1 | tail -3; .venv/bin/python -m playwright install chromium 2>&1 | tail -3)`
- C1 `.venv/bin/python -m pytest tests/wizard_taps.py tests/test_wizard_four_steps_0884.py -q -s --tb=short -x 2>&1 | tail -30` (in step 1 only `tests/wizard_taps.py`)
- C2 `.venv/bin/python -m pytest tests/test_onboarding.py tests/test_onboarding_wizard_survival.py tests/test_wizard_friendly_0273.py tests/test_wizard_second_lock_0400.py tests/test_test_run_0272.py tests/test_fee_setup_compatibility.py tests/test_smart_locks_page.py tests/test_setup_banner.py tests/test_ares.py tests/test_ruian.py tests/test_demo_stay_exclusion.py tests/test_privacy_first.py -q --tb=short -x 2>&1 | tail -30`
- C3 (server parts; browser parts run in C6) `.venv/bin/python -m pytest tests/test_onboarding_wizard_survival.py tests/test_onboarding_wizard_browser.py tests/test_wizard_friendly_0273.py tests/test_wizard_second_lock_0400.py tests/test_fee_setup_compatibility.py tests/test_smart_locks_page.py -q --tb=line 2>&1 | grep -E "FAILED|ERROR|passed|failed" | tail -30`
- C4 `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0884_wizard_geometry_browser.py -q -rs --tb=short -x 2>&1 | tail -30`
- C5 `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5 && .venv/bin/python -m pytest tests/test_static_versions.py -q --tb=short 2>&1 | tail -30`
- C6 `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_onboarding_wizard_browser.py tests/test_onboarding_followup_browser.py tests/test_design_setup_wizard_browser.py tests/test_door_code_window_browser.py -q -rs --tb=short 2>&1 | tail -30`
- C7 `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_design_guardrails_browser.py tests/test_0800_v2_remaining_pages_browser.py tests/test_0710_v2_mockup_match_browser.py tests/test_host_geometry.py -q -rs --tb=short 2>&1 | tail -30`
- C8 from the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30` → `context lint: OK`

## 7. Acceptance

- [ ] `property_setup.STEPS` has 4 names; `/setup/automation|stay_fee|door_lock|try_it` answer 303 to `/setup/done`; old marks survive a save (C1).
- [ ] Police page shows the 3 automation cards; Save and Wait both store the chosen mode and mark `automation` done; bad hours save nothing (C1).
- [ ] Done page: 4 summary rows and Do next cards (stay fee, door lock when available, try it); the try-it card opens the guest demo after setup is finished (C1).
- [ ] Property step without a business shows the register form; it prefills /entities and saving returns to the property step (C1).
- [ ] `wizard_taps.py`: BEFORE numbers recorded; steps defined, steps visited and POSTs at most half (C1).
- [ ] C2, C3, C5, C6, C7, C8 pass; browser runs 0 skipped.
- [ ] C4 passes at 320/390/768/1024/1280/1440 in en and cs: no text under 14 px, no text within 16 px of a card edge, 12 px between buttons and text, no overlapping controls, no sideways scroll.
- [ ] Screenshots in `docs/tasks/screenshots-0884/`: property, property-no-business, police, done at 390 and 1280.

## 8. Stop and ask

Stop, and write the report, if:

- an anchor is not found, or occurs more than once;
- step 1 prints `steps_defined` other than 8, or a step 10 after-assert fails;
- a test about `uby_*`, the password, `report_complete`, police waiting or demo exclusion fails and only weakening it would pass;
- more than 12 test functions would need deleting;
- geometry failures remain after 2 CSS rounds, or a fix needs a template or a selector outside `body.v2 .wiz-page`;
- Chromium cannot launch after C0 (finish the rest, report `blocked`);
- a test fails twice after one fix;
- you reach 25 tool calls or about 50k tokens (hand over, executor.md);
- a file outside §3 needs a change, or a new dependency seems needed;
- a step is unclear.

Not a stop: `_ruian_suggest.html` missing (skip step 8c and note it).

## 9. Report

Report: docs/tasks/0884-report.md

Rewrite it (600 tokens at most, plus the two kept old sections): files changed (`git diff --stat 98913fd3 | tail -30`); each command with its last 5 lines; the BEFORE and after `WIZARD_TAPS` numbers side by side; §7 ticked; every deleted test with one reason; CSS fixes made in step 14; screenshot list; Deviations (RÚIAN include done or skipped); Questions; Owner steps left. Then set `Status: review`.

## Risk list (for the reviewer)

- `App/app/routes/admin.py` stale-post guard and police automation save (a full-payload save from an old page would blank fields; the guard must come before `_wizard_setup_step`).
- `App/app/routes/onboarding_wizard.py` demo start before the guide check (owner check is `access.apartment` above it).
- `App/app/property_setup.py` `KNOWN_STEPS` in `load`/`mark` (old marks kept).
- Deleted tests list in the report.
- After #725 merges, both #725 and this branch define `GET /apartments/ruian-suggest` (#731): check there is one route.

## Owner steps

1. Open the PR link from the report and read the "Deleted tests" list.
2. Wait for CI to be green, then merge with `scripts/merge-pr-on-green.sh <PR number>`.
3. If the report says "RÚIAN include skipped": after PR #725 is merged, ask the orchestrator for the one-line follow-up (include `_ruian_suggest.html` on the wizard property step).
4. Still open from the old 0884 part: confirm the ČÚZK address URL and terms (see the report's TODO-verify).
