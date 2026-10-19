# 0139: Guest edit page (host side) on the v2 template (form kind)

Status: todo
Depends on: 0138 | Base commit: df8b842 | Branch: claude/project-thread-td6fpc
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

Part of [design-v2](../plans/design-v2.md). Commit each step as `0139 step k`. Never push, never open a PR. Page file: `docs/design/pages/stays.md` (guest edit).

## 1. Objective

Move `guest_form_admin.html` (the host's add/edit guest page under `/guests/{id}` and `/reservations/{id}/guests/new`) onto `host_page.html` as a form page: back link to the stay, guest title, stay dates as meta, one primary Save, v2 fields, banners and sections, no inline styles. Field names, validation, the identity reveal, the signature pad, the passport preview and the danger zone keep their markup and ids; only classes and the page shell change. The guest-facing form pages are out of scope.

## 2. Context

Rules: MASTER 5 (form kind, narrow lane), 7.2 (fields), 7.9, 4. `signature.js` and `app.js` key on ids and `data-*` attributes (`data-identity-hidden`, `data-copy`, `signature-pad` ids), never on `.btn` or `.field`. 0136 already removed the ID-check block from this file, so counts below are the post-0136 counts.

Anchor A, `App/app/templates/guest_form_admin.html` line 1: `{% extends "base.html" %}`; line 2: `{% set nav = 'reservations' %}`.

Anchor B, same file (twelve lines, verbatim):

```
{% block content %}
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
```

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/guest_form_admin.html` | edit | head, classes, style attributes |
| `docs/design/catalog.json` | edit | enforce the template; legacy list |
| `App/tests/test_design_guest_admin.py` | create | slots, one primary, no styles |

No other file may change.

## 4. Steps

1. Replace Anchor A line 1 with `{% extends "host_page.html" %}` and insert after line 2 a new line `{% set body_kind = 'form' %}`. Replace Anchor B with:

```
{% block page_title %}{{ t('guest.admin.title_edit') if editing else t('guest.admin.title_add') }}{% endblock %}
{% block meta %}{{ reservation.internal_name ~ ' · ' ~ (reservation.date_from | date_cz) ~ ' – ' ~ (reservation.date_to | date_cz) }}{% endblock %}
{% block back_url %}/reservations/{{ reservation.id }}{% endblock %}
{% block back_label %}{{ t('guest.admin.back_to_stay') }}{% endblock %}
{% block body %}
```

   The file's final `{% endblock %}` now closes `body`. Command: `cd App && .venv/bin/python -c "from app.templating import templates; templates.env.get_template('guest_form_admin.html'); print('compiled')"`. Expected: `compiled`.

2. Mechanical replacements, from `App/`:

```
.venv/bin/python - <<'EOF'
import pathlib, re
p = pathlib.Path("app/templates/guest_form_admin.html"); s = p.read_text(encoding="utf-8")
styles = re.findall(r' style="[^"]*"', s)
assert len(styles) == 12, (len(styles), styles)   # all margins or max-width: the lane and the field rhythm replace them
s = re.sub(r' style="[^"]*"', "", s)
PAIRS = [
 ('class="btn primary"', 'class="ui-btn ui-btn-primary"', 1),
 ('class="btn small ghost"', 'class="ui-btn ui-btn-quiet ui-btn-compact"', 1),
 ('class="btn small"', 'class="ui-btn ui-btn-secondary ui-btn-compact"', 2),
 ('class="btn danger"', 'class="ui-btn ui-btn-danger"', 2),
 ('class="btn"', 'class="ui-btn ui-btn-secondary"', 6),
 ('class="small muted"', 'class="ui-sub"', 4),
 ('class="banner critical"', 'class="ui-banner ui-banner-attention"', 1),
 ('class="banner warning"', 'class="ui-banner ui-banner-attention"', 1),
 ('class="banner info"', 'class="ui-banner ui-banner-neutral"', 1),
 ('class="field"', 'class="ui-field"', 15),
 ('class="actions"', 'class="ui-form-actions"', 1),
 ('class="panel danger-zone"', 'class="ui-section danger-zone"', 1),
 ('class="panel verify-panel tight"', 'class="ui-section verify-panel"', 1),
 ('class="panel"', 'class="ui-section"', 5),
 ('class="grid two"', 'class="ui-pair"', 1),
]
for old, new, n in PAIRS:
    assert s.count(old) == n, (old, s.count(old)); s = s.replace(old, new)
assert 'style="' not in s and 'class="btn' not in s and 'class="pill' not in s and s.count("ui-btn-primary") == 1
p.write_text(s, encoding="utf-8"); print("ok")
EOF
```

   Expected: `ok`. If the style count is not 12, print the list and stop: a style that is not a margin or max-width needs a named class and the reviewer's eye.

3. Catalog: add `App/app/templates/guest_form_admin.html` to `enforced_templates`; run `python3 scripts/design_lint.py 2>&1 | grep guest_form_admin.html | sed 's/.*catalog: //' | sort -u | tr '\n' ' '` and put the tokens into the template's `legacy` list (expected: `err hint opt grid tight compact quiet identity-hidden passport-preview passport-preview-pdf-link signature-pad signature-pad-bar signature-saved signature-saved-note verify-panel checkline danger-zone critical info warning bad`). Command: `python3 scripts/design_lint.py`. Expected: OK.

4. Create `App/tests/test_design_guest_admin.py`:

```python
"""0139: the host's guest edit page renders on host_page as a form page."""
from __future__ import annotations

import re

from tests.test_signed_in_chrome import host_with_property  # noqa: F401


def test_add_guest_page_has_the_v2_form_shell(host_with_property):
    stays = host_with_property.get("/reservations?range=all&lang=en").text
    match = re.search(r'data-href="(/reservations/\d+)"', stays)
    assert match, "no stay on the list"
    page = host_with_property.get(match.group(1) + "/guests/new?lang=en").text
    assert page.count("<h1") == 1 and 'data-body-kind="form"' in page
    assert 'class="ui-ph-back"' in page and 'class="ui-ph-meta"' in page
    assert page.count('class="ui-btn ui-btn-primary"') == 1
    assert "page-header" not in page and "breadcrumbs" not in page


def test_no_raw_style_or_legacy_control_in_the_template():
    text = open("app/templates/guest_form_admin.html", encoding="utf-8").read()
    assert 'style="' not in text and 'class="btn' not in text
```

   Command: `cd App && .venv/bin/python -m pytest tests/test_design_guest_admin.py tests/test_host_guest_form.py tests/test_admin_guest_data.py tests/test_identity*.py tests/test_signature*.py tests/test_design_lint.py -q --tb=short -x 2>&1 | tail -30`. Expected: passed.

5. Browser and screenshots: `cd App && UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-shots .venv/bin/python -m pytest tests/test_host_geometry.py tests/test_host_unsaved_changes_browser.py -q --tb=short 2>&1 | tail -30`. Expected: passed, 0 skipped. Attach the add-guest page at 390 and 1280 (`guest-add-390.png`, `guest-add-1280.png`).

6. Commit: `git add App/app/templates/guest_form_admin.html docs/design/catalog.json App/tests && git commit -m "0139 step 6: host guest edit page on host_page (form kind)"`.

## 5. Do not touch

`routes/admin.py`, `signature.js`, the guest-facing templates, field names and validation, `_components.html`; hard rules 1, 2, 3, 8.

## 6. Commands

- `python3 scripts/design_lint.py` expected: OK.
- Step 4 and step 5 commands, 0 skipped.

## 7. Acceptance

- [ ] Back link, title, dates meta, one primary Save; fields in the narrow lane; signature pad and preview unchanged.
- [ ] 390 px and 1280 px screenshots attached.
- [ ] Lint passes with the template enforced.

## 8. Stop and ask

Stop, and write the report, if: an excerpt is not found; a count in step 2 differs; a test fails twice; you reach 25 tool calls or about 50k tokens (report as `blocked`); a file outside section 3 needs a change; section 5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0139-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

`App/app/templates/guest_form_admin.html` (guest data form; hard rule 1 adjacency).

## Owner steps

None.
