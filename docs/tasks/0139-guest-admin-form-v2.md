# 0139: Guest edit page (host side) on the v2 template (form kind)

Status: todo
Depends on: 0138 | Base commit: 79252fd (refreshed 2026-10-19 against 0130-0137 and 0147-0152; every anchor count below was asserted on a scratch copy of this head and the result compiled and tested) | Branch: claude/project-thread-td6fpc
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

Part of [design-v2](../plans/design-v2.md). Commit each step as `0139 step k`. Never push, never open a PR. Page file: `docs/design/pages/stays.md` (guest edit).

**How to run this brief.** Every step is one command, run from `App/` (`cd App` first; the scripts use paths relative to `App/`). Each script asserts the count of every anchor before it writes anything and prints `ok` at the end; if it prints an `AssertionError` tuple instead (the anchor text and the count it found), nothing was written: stop and put the tuple in the report. Do not retype the scripts and do not edit the files by hand. Known-failing tests are named per step; a failure not named there is yours to report, not to fix by weakening the test.

## 1. Objective

Move `guest_form_admin.html` (the host's add/edit guest page under `/guests/{id}` and `/reservations/{id}/guests/new`) onto `host_page.html` as a form page: back link to the stay, guest title, stay dates as meta, one primary Save, v2 fields, banners and sections, no inline styles. Field names, validation, the identity reveal, the signature pad, the passport preview and the danger zone keep their markup and ids; only classes and the page shell change. The guest-facing form pages are out of scope.

## 2. Context

Rules: MASTER 4, 5 (form kind, narrow lane), 7.2 (fields), 7.9. `signature.js` and `app.js` key on ids and `data-*` attributes, never on `.btn` or `.field`. Settled since the first version:

- The page loads `signature.js` with its own `<script src>` tag at the end of the template. An enforced template may carry no script tag (lint T1), so script 1 adds a `page_script` slot to `host_page.html` (rendered after the body, only when a child sets `{% set page_script = '...' %}`) and the guest page sets it. This is the one change outside the page.
- `.ui-form-actions` is hidden below 1024 px; the Save row is `ui-btn-group`. `.panel` boxes that must keep their frame (danger zone, delete form) are `ui-section ui-card`; plain panels are `ui-section`.
- The design test uses the `stay` fixture from `tests/test_stay_missing_guest_rows.py` (`host_with_property` seeds no stay).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/guest_form_admin.html` | edit | head, page_script, classes, style attributes |
| `App/app/templates/host_page.html` | edit | `page_script` slot after the body (script 1) |
| `docs/design/catalog.json` | edit | enforce the template; legacy list (script 3) |
| `App/tests/test_design_guest_admin.py` | create | slots, one primary, no styles |

No other file may change.

## 4. Steps

1. Head, script slot:

```
.venv/bin/python - <<'EOF'
import pathlib
p = pathlib.Path("app/templates/guest_form_admin.html"); s = p.read_text(encoding="utf-8")
PAIRS = [
 ("""{% extends "base.html" %}
{% set nav = 'reservations' %}
""", """{% extends "host_page.html" %}
{% set nav = 'reservations' %}
{% set body_kind = 'form' %}
{# signature.js loads through host_page's page_script slot: an enforced template carries no script tag of its own (lint T1). #}
{% set page_script = 'signature.js?v=20261004b' %}
"""),
 ("""<script src="/static/signature.js?v=20261004b"></script>
{% endblock %}
""", """{% endblock %}
"""),
 ("""{% block content %}
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
""", """{% block page_title %}{{ t('guest.admin.title_edit') if editing else t('guest.admin.title_add') }}{% endblock %}
{% block meta %}{{ reservation.internal_name ~ ' · ' ~ (reservation.date_from | date_cz) ~ ' – ' ~ (reservation.date_to | date_cz) }}{% endblock %}
{% block back_url %}/reservations/{{ reservation.id }}{% endblock %}
{% block back_label %}{{ t('guest.admin.back_to_stay') }}{% endblock %}
{% block body %}
"""),
]
for old, new in PAIRS:
    assert s.count(old) == 1, (old[:60], s.count(old)); s = s.replace(old, new)
p.write_text(s, encoding="utf-8")
# host_page.html: a page names its one script file in page_script; the layout renders the tag after the body.
p = pathlib.Path("app/templates/host_page.html"); s = p.read_text(encoding="utf-8")
old = """  <div class="ui-body ui-body-{{ body_kind }}">{% block body %}{% endblock %}</div>
</div>
"""
assert s.count(old) == 1, s.count(old)
s = s.replace(old, old + """{% if page_script | default('') %}<script src="/static/{{ page_script }}"></script>{% endif %}
""")
p.write_text(s, encoding="utf-8"); print("ok")
EOF
```

   Expected: `ok`. Then `.venv/bin/python -c "from app.templating import templates; templates.env.get_template('guest_form_admin.html'); templates.env.get_template('host_page.html'); print('compiled')"`. Expected: `compiled`. Commit `0139 step 1`.

2. Styles out, classes:

```
.venv/bin/python - <<'EOF'
import pathlib, re
p = pathlib.Path("app/templates/guest_form_admin.html"); s = p.read_text(encoding="utf-8")
styles = re.findall(r' style="[^"]*"', s)
assert len(styles) == 12, (len(styles), styles)   # all margins: the lane and the field rhythm replace them
s = re.sub(r' style="[^"]*"', "", s)
PAIRS = [
 ('class="btn primary"', 'class="ui-btn ui-btn-primary"', 1),
 ('class="btn small ghost"', 'class="ui-btn ui-btn-quiet ui-btn-compact"', 1),
 ('class="btn small"', 'class="ui-btn ui-btn-secondary ui-btn-compact"', 2),
 ('class="btn danger"', 'class="ui-btn ui-btn-danger"', 2),
 ('class="btn"', 'class="ui-btn ui-btn-secondary"', 6),
 ('<p class="small muted">', '<p class="ui-sub">', 4),
 ('<p class="small muted signature-saved-note">', '<p class="ui-sub signature-saved-note">', 1),
 ('class="banner critical"', 'class="ui-banner ui-banner-attention"', 1),
 ('class="banner warning"', 'class="ui-banner ui-banner-attention"', 1),
 ('class="banner info"', 'class="ui-banner ui-banner-neutral"', 1),
 ('class="field"', 'class="ui-field"', 15),
 # ui-form-actions is hidden below 1024 px (sticky-bar pattern, no twin here): action rows are ui-btn-group
 ('<div class="actions">', '<div class="ui-btn-group">', 1),
 # the danger zone and the delete form keep a box (0135-fix-1: ui-section alone has no padding)
 ('<details class="panel danger-zone">', '<details class="ui-section ui-card danger-zone">', 1),
 ('/delete" class="panel"', '/delete" class="ui-section ui-card"', 1),
 ('<div class="panel verify-panel tight">', '<div class="ui-section verify-panel">', 1),
 ('<div class="panel">', '<div class="ui-section">', 4),
 ('<div class="grid two">', '<div class="ui-pair">', 1),
]
for old, new, n in PAIRS:
    assert s.count(old) == n, (old, s.count(old)); s = s.replace(old, new)
for f in ('style="', 'class="btn', 'class="pill', 'class="panel', 'class="small', 'class="actions"'):
    assert f not in s, f
assert s.count("ui-btn-primary") == 1
p.write_text(s, encoding="utf-8"); print("ok")
EOF
```

   Expected: `ok`. Commit `0139 step 2`.

3. Catalog:

```
.venv/bin/python - <<'EOF'
import json, pathlib
p = pathlib.Path("../docs/design/catalog.json"); s = p.read_text(encoding="utf-8")
TOKENS = ["checkline", "compact", "danger-zone", "err", "grid", "hint", "identity-hidden", "opt", "passport-preview", "passport-preview-pdf-link", "signature-pad", "signature-pad-bar", "signature-saved", "signature-saved-note", "verify-panel"]
old = '"App/app/templates/housebook.html"],\n  "legacy": {\n'
assert s.count(old) == 1, s.count(old)
new = '"App/app/templates/housebook.html", "App/app/templates/guest_form_admin.html"],\n  "legacy": {\n    "App/app/templates/guest_form_admin.html": ' + json.dumps(TOKENS) + ',\n'
s = s.replace(old, new); json.loads(s); p.write_text(s, encoding="utf-8"); print("ok")
EOF
```

   Expected: `ok`. Then `cd .. && python3 scripts/design_lint.py && cd App`. Expected: `design lint: OK`. Commit `0139 step 3`.

4. Tests:

```
.venv/bin/python - <<'EOF'
import pathlib
pathlib.Path("tests/test_design_guest_admin.py").write_text('''"""0139: the host's guest edit page renders on host_page as a form page."""
from __future__ import annotations

from tests.test_stay_missing_guest_rows import stay  # noqa: F401  (a host with one stay)


def test_add_guest_page_has_the_v2_form_shell(stay):
    client, reservation = stay
    page = client.get(f"/reservations/{reservation['id']}/guests/new?lang=en").text
    assert page.count("<h1") == 1 and 'data-body-kind="form"' in page
    assert 'class="ui-ph-back"' in page and 'class="ui-ph-meta"' in page
    assert page.count('class="ui-btn ui-btn-primary"') == 1
    assert 'class="page-header' not in page and 'class="breadcrumb' not in page


def test_no_raw_style_or_legacy_control_in_the_template():
    text = open("app/templates/guest_form_admin.html", encoding="utf-8").read()
    assert 'style="' not in text and 'class="btn' not in text and 'class="panel' not in text
    assert text.count("ui-btn-primary") == 1
''', encoding="utf-8")
print("ok")
EOF
```

   Expected: `ok`. Then `.venv/bin/python -m pytest tests/test_design_guest_admin.py tests/test_host_guest_form.py tests/test_admin_guest_data.py tests/test_stay_missing_guest_rows.py tests/test_design_page_template.py tests/test_design_lint.py -q --tb=short 2>&1 | tail -30`. Expected: all passed. Commit `0139 step 4`.

5. Browser: `UBYHOST_REQUIRE_BROWSER=1 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers .venv/bin/python -m pytest tests/test_host_geometry.py tests/test_host_unsaved_changes_browser.py -q --tb=short 2>&1 | tail -30`. Expected: passed, 0 skipped.

6. Screenshots: `UBYHOST_REQUIRE_BROWSER=1 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers SHOT_TASK=0139 SHOT_PAGES="guest-add" .venv/bin/python -m pytest -p tests.conftest /tmp/claude-0/-home-user-jsfpecharoperations/3c6f1ec6-a025-553c-863a-9c0748d5832e/scratchpad/shoot_pages.py -q -s 2>&1 | tail -8`. Files: `.../scratchpad/shots/0139/guest-add-390.png` and `guest-add-1280.png` (full path printed by the helper). Check in the 390 shot that the Save button is visible under the last field and the signature pad keeps its width. Then `git status --short | head -20`: the only changes must be the files in section 3. If a tracked evidence folder changed (for example `docs/tasks/0087-evidence/`), `git checkout -- <that folder>` before committing.

7. Commit: `git add App/app/templates/guest_form_admin.html App/app/templates/host_page.html docs/design/catalog.json App/tests && git commit -m "0139 step 7: host guest edit page on host_page (form kind)"`.

## 5. Do not touch

`routes/admin.py`, `signature.js`, the guest-facing templates, field names and validation, `_components.html`; hard rules 1, 2, 3, 8.

## 6. Commands

- `python3 scripts/design_lint.py` expected: OK.
- Step 4 and step 5 commands, 0 skipped.

## 7. Acceptance

- [ ] Back link, title, dates meta, one primary Save; fields in the narrow lane; signature pad and preview unchanged and `signature.js` still loaded (view source: one `<script src="/static/signature.js` after the body).
- [ ] 390 px and 1280 px screenshots attached.
- [ ] Lint passes with the template enforced.

## 8. Stop and ask

Stop, and write the report, if: a script prints an `AssertionError` instead of `ok`; a test not named as known-failing fails twice; you reach 25 tool calls or about 50k tokens (report as `blocked`); a file outside section 3 needs a change; section 5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0139-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, section 7 ticked, the known failures seen (one line each, with the message), deviations, questions, owner steps left.

## Risk list (for the reviewer)

`App/app/templates/guest_form_admin.html` (guest data form; hard rule 1 adjacency); `App/app/templates/host_page.html` (new slot, shared by every v2 page).

## Owner steps

None.
