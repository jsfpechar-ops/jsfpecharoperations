# 0139: Guest edit page (host side) on the v2 template (form kind)

Status: todo
Depends on: 0138 | Base commit: c340b7f | Branch: claude/project-thread-5hw8cf
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

Part of [design-v2](../plans/design-v2.md). Commit once, at step 8, as `0139 step 8`. Never push, never open a PR. Page file: `docs/design/pages/stays.md` (guest edit).

## 1. Objective

Move `guest_form_admin.html` (the host's add/edit guest page under `/guests/{id}` and `/reservations/{id}/guests/new`) onto `host_page.html` as a form page: back link to the stay, guest title, stay dates as meta, one primary Save in `.ui-form-actions` (visible at every width once 0154 has run), v2 fields, banners and sections, no inline styles, no script tag in the page. Field names, validation, the identity reveal, the signature pad, the passport preview and the danger zone keep their markup and ids; only classes, the page shell and the actions row change. The guest-facing form pages are out of scope.

## 2. Context

Rules: MASTER 5 (form kind: narrow lane; actions row at the end, primary right), 7.2 (fields), 7.9, 4; design lint T1 (no `<script src>` in an enforced page), T4 (one `ui-btn-primary` per template).

Facts checked against the code at c340b7f (all scripts below were dry-run on a copy and pass):

- `host_page.html` blocks: `page_title`, `meta`, `back_url`, `back_label`, `primary_action`, `secondary_actions`, `body`; it reads `body_kind` and puts form pages in `ui-lane-narrow`. Same shape as `reservation_detail.html`.
- `host2.css`: brief 0154 (runs before 0138) deletes the phone rule `.host-workspace .ui-form-actions { display: none; }`, so `.ui-form-actions` stays visible on phone. No CSS change here. `.ui-form-actions` does not wrap, so only Save goes in it; Cancel, PDF, export, record and restrict move to a wrapping `ui-btn-group` below it. No sticky bar: `.ui-sticky-actions` would need a second `ui-btn-primary` (lint T4).
- Save must stay the first submit button of the main form: Enter in a field submits with the first one, and Restrict/Unrestrict are submit buttons with `formaction`. Step 2 asserts this; the new test checks it.
- `signature.js` sets `#sig-status` class to `err`/`hint` itself: that literal `class="err"` stays (legacy list). `app.js` keys on `.actions [type=submit]` only for forms with `data-unsaved-reset`; this form has none.
- The page's `<script src="/static/signature.js?v=20261004b">` moves into a new unenforced partial `_signature_script.html` (same pattern as `_dashboard_calendar.html` and `_cleaning_screen.html`).
- Inputs keep their bare `<input>`/`<select>`: app.css styles them globally. `class="grid"` (auto-fit columns, 3 to 5 fields) stays as a legacy class.
- Browser binary: Playwright 1.63 wants a newer headless shell than is installed, so browser runs need `UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome` (works, checked).

Anchor A, `App/app/templates/guest_form_admin.html` lines 1-2: `{% extends "base.html" %}` / `{% set nav = 'reservations' %}`.

Anchor B, same file, lines 28-40 (verbatim, in the step 1 script). Anchor C, same file, the actions row `  <div class="actions">` ... `</form>` (lines 268-282, verbatim in the step 2 script). Anchor D, same file, line 320: `<script src="/static/signature.js?v=20261004b"></script>`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/guest_form_admin.html` | edit | head, actions row, classes, style attributes, script include |
| `App/app/templates/_signature_script.html` | create | the signature.js script tag |
| `docs/design/catalog.json` | edit | enforce the template; legacy list |
| `App/tests/test_design_guest_admin.py` | create | shell, one primary in `.ui-form-actions`, Save first, no styles |

No other file may change. Existing tests that render this page and must stay green (no edits expected): `test_host_guest_form.py`, `test_admin_guest_data.py`, `test_restriction.py`, `test_passport_photos.py`, `test_remove_id_check.py`, `test_guest_visa_hidden.py`, `test_design_lint.py`.

## 4. Steps

1. Page shell. From `App/`:

````
.venv/bin/python - <<'EOF'
import pathlib
p = pathlib.Path("app/templates/guest_form_admin.html"); s = p.read_text(encoding="utf-8")
A_OLD = "{% extends \"base.html\" %}\n{% set nav = 'reservations' %}\n"
A_NEW = "{% extends \"host_page.html\" %}\n{% set nav = 'reservations' %}\n{% set body_kind = 'form' %}\n"
B_OLD = """{% block content %}
{% from "_components.html" import page_header, breadcrumb with context %}
{{ breadcrumb([
  {'label': t('nav.stays'), 'url': '/reservations'},
  {'label': reservation.internal_name ~ ' · ' ~ (reservation.date_from | date_cz), 'url': '/reservations/' ~ reservation.id},
  {'label': t('guest.admin.title_edit') if editing else t('guest.admin.title_add'), 'url': ''}
]) }}
{{ page_header(
  t('guest.admin.title_edit') if editing else t('guest.admin.title_add'),
  reservation.internal_name ~ ' · ' ~ (reservation.date_from | date_cz) ~ ' – ' ~ (reservation.date_to | date_cz),
  '/reservations/' ~ reservation.id,
  t('guest.admin.back_to_stay')
) }}
"""
B_NEW = """{% block page_title %}{{ t('guest.admin.title_edit') if editing else t('guest.admin.title_add') }}{% endblock %}
{% block meta %}{{ reservation.internal_name ~ ' · ' ~ (reservation.date_from | date_cz) ~ ' – ' ~ (reservation.date_to | date_cz) }}{% endblock %}
{% block back_url %}/reservations/{{ reservation.id }}{% endblock %}
{% block back_label %}{{ t('guest.admin.back_to_stay') }}{% endblock %}
{% block body %}
"""
for old, new in ((A_OLD, A_NEW), (B_OLD, B_NEW)):
    assert s.count(old) == 1, old[:60]
    s = s.replace(old, new)
assert s.count("{% block content %}") == 0 and s.rstrip().endswith("{% endblock %}")
p.write_text(s, encoding="utf-8"); print("ok")
EOF
.venv/bin/python -c "from app.templating import templates; templates.env.get_template('guest_form_admin.html'); print('compiled')"
````

   Expected: `ok`, then `compiled`. The file's final `{% endblock %}` now closes `body`.

2. Actions row, styles and classes. From `App/`:

````
.venv/bin/python - <<'EOF'
import pathlib, re
p = pathlib.Path("app/templates/guest_form_admin.html"); s = p.read_text(encoding="utf-8")
# a) the actions row: Save stays the first submit button in the form (Enter key),
#    alone in .ui-form-actions (no wrap); the other buttons go in a wrapping .ui-btn-group below it.
ACT_OLD = """  <div class="actions">
    <button class="btn primary" type="submit">{{ t('common.save_changes') if editing else t('guest.admin.submit_add') }}</button>
    <a class="btn" href="/reservations/{{ reservation.id }}">{{ t('confirm.cancel') }}</a>
    {% if editing and guest.id %}
      <a class="btn" href="/guests/{{ guest.id }}/form.pdf">{{ t('guest.admin.download_pdf') }}</a>
      <a class="btn" href="/guests/{{ guest.id }}/export.json">{{ t('guest.admin.export_dsr') }}</a>
      <a class="btn" href="/privacy-requests">{{ t('guest.admin.record_request') }}</a>
      {% if guest.restricted_at %}
        <button class="btn" type="submit" formaction="/guests/{{ guest.id }}/unrestrict">{{ t('guest.admin.unrestrict') }}</button>
      {% else %}
        <button class="btn" type="submit" formaction="/guests/{{ guest.id }}/restrict">{{ t('guest.admin.restrict') }}</button>
      {% endif %}
    {% endif %}
  </div>
</form>
"""
ACT_NEW = """  <div class="ui-form-actions">
    <button class="ui-btn ui-btn-primary" type="submit">{{ t('common.save_changes') if editing else t('guest.admin.submit_add') }}</button>
  </div>
  <div class="ui-btn-group">
    <a class="ui-btn ui-btn-secondary" href="/reservations/{{ reservation.id }}">{{ t('confirm.cancel') }}</a>
    {% if editing and guest.id %}
      <a class="ui-btn ui-btn-secondary" href="/guests/{{ guest.id }}/form.pdf">{{ t('guest.admin.download_pdf') }}</a>
      <a class="ui-btn ui-btn-secondary" href="/guests/{{ guest.id }}/export.json">{{ t('guest.admin.export_dsr') }}</a>
      <a class="ui-btn ui-btn-secondary" href="/privacy-requests">{{ t('guest.admin.record_request') }}</a>
      {% if guest.restricted_at %}
        <button class="ui-btn ui-btn-secondary" type="submit" formaction="/guests/{{ guest.id }}/unrestrict">{{ t('guest.admin.unrestrict') }}</button>
      {% else %}
        <button class="ui-btn ui-btn-secondary" type="submit" formaction="/guests/{{ guest.id }}/restrict">{{ t('guest.admin.restrict') }}</button>
      {% endif %}
    {% endif %}
  </div>
</form>
"""
assert s.count(ACT_OLD) == 1, "actions block not found"
s = s.replace(ACT_OLD, ACT_NEW)
# b) inline styles: all margins (the lane, .ui-field and .ui-section spacing replace them)
styles = re.findall(r' style="[^"]*"', s)
assert len(styles) == 12, (len(styles), styles)
assert all(re.fullmatch(r' style="margin[-a-z]*:[^"]*"', x) for x in styles), styles
s = re.sub(r' style="[^"]*"', "", s)
# c) classes
PAIRS = [
 ('class="btn small ghost"', 'class="ui-btn ui-btn-quiet ui-btn-compact"', 1),
 ('class="btn small"', 'class="ui-btn ui-btn-secondary ui-btn-compact"', 2),
 ('class="btn danger"', 'class="ui-btn ui-btn-danger"', 2),
 ('class="small muted"', 'class="ui-sub"', 4),
 ('class="banner critical"', 'class="ui-banner ui-banner-attention"', 1),
 ('class="banner warning"', 'class="ui-banner ui-banner-attention"', 1),
 ('class="banner info"', 'class="ui-banner ui-banner-neutral"', 1),
 ('class="field"', 'class="ui-field"', 15),
 ('class="hint"', 'class="ui-help"', 4),
 ('class="opt"', 'class="ui-opt"', 3),
 ("class=\"{{ 'err' if issue.is_error else 'hint' }}\"", "class=\"{{ 'ui-error' if issue.is_error else 'ui-help' }}\"", 1),
 ('class="panel danger-zone"', 'class="ui-section danger-zone"', 1),
 ('class="panel verify-panel tight"', 'class="ui-section verify-panel"', 1),
 ('class="panel"', 'class="ui-section"', 5),
 ('class="grid two"', 'class="ui-pair"', 1),
]
for old, new, n in PAIRS:
    assert s.count(old) == n, (old, s.count(old)); s = s.replace(old, new)
for bad in ('style="', 'class="btn', 'class="pill', 'class="panel', 'class="banner', 'class="field"', 'class="actions"', 'page_header', 'breadcrumb'):
    assert bad not in s, bad
assert s.count("ui-btn-primary") == 1
assert s.index('class="ui-btn ui-btn-primary" type="submit"') < s.index('formaction="/guests/')  # Save is the form's first submit
assert 'id="sig-status" class="err"' in s  # signature.js sets this class itself
p.write_text(s, encoding="utf-8"); print("ok")
EOF
````

   Expected: `ok`. If an assert fails, print what it shows and stop (section 8).

3. Script tag into a partial. From the repo root:

````
python3 - <<'EOF'
p = "App/app/templates/guest_form_admin.html"; s = open(p, encoding="utf-8").read()
old = '<script src="/static/signature.js?v=20261004b"></script>\n'
assert s.count(old) == 1, "Anchor D not found"
s = s.replace(old, '{% include "_signature_script.html" %}\n'); open(p, "w", encoding="utf-8").write(s)
open("App/app/templates/_signature_script.html", "w", encoding="utf-8").write(
    '{#- 0139: signature.js for the host guest page; a page on host_page may not carry a script tag (design lint T1). -#}\n'
    '<script src="/static/signature.js?v=20261004b"></script>\n')
print("ok")
EOF
````

   Expected: `ok`.

4. Catalog (text edits keyed on names, then a JSON check; works after 0138 changed the file). From the repo root:

````
python3 - <<'EOF'
import json, pathlib, re, subprocess
p = pathlib.Path("docs/design/catalog.json"); s = p.read_text(encoding="utf-8")
T = "App/app/templates/guest_form_admin.html"
assert T not in s
s = s.replace('"enforced_templates": [', '"enforced_templates": ["' + T + '", ', 1)
p.write_text(s, encoding="utf-8")
lint = subprocess.run(["python3", "scripts/design_lint.py"], capture_output=True, text=True).stdout
tokens = sorted({m for m in re.findall(r"guest_form_admin\.html: T3 class not in catalog: (\S+)", lint)})
other = [l for l in lint.splitlines() if "guest_form_admin" in l and "T3 class not in catalog" not in l]
assert not other, other
EXPECTED = "checkline compact danger-zone err grid identity-hidden muted passport-preview passport-preview-pdf-link signature-pad signature-pad-bar signature-saved signature-saved-note small verify-panel".split()
assert tokens == EXPECTED, tokens
s = s.replace('"legacy": {\n', '"legacy": {\n    "' + T + '": ' + json.dumps(tokens) + ',\n', 1)
d = json.loads(s)
assert T in d["enforced_templates"] and d["legacy"][T] == tokens
p.write_text(s, encoding="utf-8"); print("ok")
EOF
python3 scripts/design_lint.py 2>&1 | tail -5
````

   Expected: `ok`, then `design lint: OK`.

5. Create `App/tests/test_design_guest_admin.py` with exactly:

```python
"""0139: the host's guest add/edit page renders on host_page as a form page."""
from __future__ import annotations

from pathlib import Path

from tests.test_host_guest_form import _cleanup, _host_client, _host_guest, _host_stay

TEMPLATE = Path(__file__).resolve().parents[1] / "app" / "templates" / "guest_form_admin.html"


def _assert_v2_form_shell(page: str, stay_id: int) -> None:
    assert page.count("<h1") == 1 and 'data-body-kind="form"' in page
    assert f'class="ui-ph-back" href="/reservations/{stay_id}"' in page
    assert 'class="ui-ph-meta"' in page
    assert page.count('class="ui-btn ui-btn-primary"') == 1
    assert '<div class="ui-form-actions">\n    <button class="ui-btn ui-btn-primary" type="submit">' in page
    assert "page-header" not in page and "breadcrumbs" not in page
    assert '/static/signature.js?v=' in page


def test_add_guest_page_has_the_v2_form_shell():
    owner_id, stay_id = _host_stay()
    try:
        page = _host_client(owner_id).get(f"/reservations/{stay_id}/guests/new?lang=en").text
        _assert_v2_form_shell(page, stay_id)
    finally:
        _cleanup()


def test_edit_guest_page_keeps_save_as_the_first_submit_button():
    owner_id, stay_id = _host_stay()
    try:
        guest_id = _host_guest(stay_id)
        page = _host_client(owner_id).get(f"/guests/{guest_id}?lang=en").text
        _assert_v2_form_shell(page, stay_id)
        main = page[page.index(f'<form method="post" action="/guests/{guest_id}"'):]
        main = main[: main.index("</form>")]
        # Enter in a field submits with the first submit button: that must be Save, not Restrict.
        assert main.index('class="ui-btn ui-btn-primary" type="submit"') < main.index("formaction=")
    finally:
        _cleanup()


def test_no_raw_style_or_legacy_control_in_the_template():
    text = TEMPLATE.read_text(encoding="utf-8")
    assert 'style="' not in text and 'class="btn' not in text and "<script src" not in text
```

6. Tests. Command: `cd App && .venv/bin/python -m pytest tests/test_design_guest_admin.py tests/test_host_guest_form.py tests/test_admin_guest_data.py tests/test_restriction.py tests/test_passport_photos.py tests/test_remove_id_check.py tests/test_guest_visa_hidden.py tests/test_design_lint.py -q --tb=short -x 2>&1 | tail -30`. Expected: `78 passed` (or more), 0 failed.

7. Browser tests (no screenshots: the orchestrator takes them, so attach none). Command: `cd App && UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome .venv/bin/python -m pytest tests/test_host_geometry.py tests/test_host_unsaved_changes_browser.py tests/test_shell_lane_browser.py -q --tb=short -rs 2>&1 | tail -30`. Expected: `21 passed`, 0 skipped.

8. Commit: `git add App/app/templates/guest_form_admin.html App/app/templates/_signature_script.html docs/design/catalog.json App/tests/test_design_guest_admin.py && git commit -m "0139 step 8: host guest edit page on host_page (form kind)"`.

## 5. Do not touch

`routes/admin.py`, `signature.js`, `app.js`, the guest-facing templates, field names and validation, `_components.html`, `host2.css`, `base.html`; hard rules 1, 2, 3, 8.

## 6. Commands

- `python3 scripts/design_lint.py` expected: OK.
- Step 6 and 7 commands as written, 0 skipped.

## 7. Acceptance

- [ ] Back link, title, dates meta, one primary Save (first submit button of the form), alone in `.ui-form-actions`; other actions in the `ui-btn-group` below; signature pad and preview ids unchanged.
- [ ] No `style=`, `class="btn`, or `<script src` in `guest_form_admin.html`; lint passes with the template enforced.
- [ ] Step 6 and 7 outputs as expected. No screenshots needed from the executor.

## 8. Stop and ask

Stop, and write the report, if: an excerpt or assert fails; a count in step 2 differs; a test fails twice; you reach 25 tool calls or about 50k tokens (report as `blocked`); a file outside section 3 needs a change; section 5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0139-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

`App/app/templates/guest_form_admin.html` (guest data form; hard rule 1 adjacency; Enter-key submit order).

## Owner steps

None.
