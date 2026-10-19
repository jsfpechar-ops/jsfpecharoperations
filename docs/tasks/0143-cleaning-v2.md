# 0143: Cleaning pages (host side) on the v2 template

Status: todo
Depends on: 0142 | Base commit: df8b842 | Branch: claude/project-thread-td6fpc
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

Part of [design-v2](../plans/design-v2.md). Commit each step as `0143 step k`. Never push, never open a PR. Page file: `docs/design/pages/cleaning.md`.

## 1. Objective

Move the five host cleaning pages (`cleaning.html`, `cleaning_edit.html`, `cleaning_properties.html`, `cleaning_settings.html`, `cleaning_shares.html`) onto `host_page.html`: v2 header with one primary, back links, v2 buttons and fields. `cleaning.css` stops being linked from inside each template and is loaded once by `base.html` for `nav == 'cleaning'`. The shared public page `cleaning_shared.html` (cleaner's link, no sign-in) and `cleaning.js` are untouched; the calendar cards, pins and date groups keep their `cleaning-*` classes.

## 2. Context

Rules: MASTER 5 (list, form kinds), 4 (one primary), 7.2. `cleaning.js` keys on `data-cleaning-labels`, `[data-calendar-add]`, `data-cal-create-type`, `.cleaning-card` and ids; `app.js` keys on `data-confirm`; neither keys on `.btn` or `.field`. The cleaning route already passes `nav: "cleaning"` and `ct` (the cleaning translator) in the context, so the templates do not set `nav`. Tests (`test_cleaning_browser.py`) select `.cleaning-card`, `.cleaning-pin`, `.cleaning-date-group h3` and the sidebar link; none selects `.btn` or the heading block.

Anchor A, `App/app/templates/cleaning.html` lines 1 to 9 (verbatim):

```
{% extends "base.html" %}
{% block title %}{{ ct('title') }} · UbyHost{% endblock %}
{% block content %}
<link rel="stylesheet" href="/static/cleaning.css?v=20261016-0123d-0106b">
<div class="cleaning-page">
  <header class="cleaning-page-heading"><div><h1>{{ ct('title') }}</h1><p>{{ ct('subtitle') }}</p></div>
    <div class="cleaning-actions"><a class="btn primary" href="/cleaning/new" data-calendar-add data-cal-create-type="cleaning">{{ ct('add') }}</a><a class="btn" href="/reservations?new=1" data-calendar-add data-cal-create-type="stay">{{ t('calendar.add_stay') }}</a><a class="btn" href="/cleaning/properties">{{ ct('settings') }}</a><a class="btn" href="/cleaning/shares">{{ ct('share') }}</a></div>
  </header>
  {% include "_cleaning_screen.html" %}
```

Anchor B, `App/app/templates/cleaning_edit.html` lines 1 to 6 (verbatim):

```
{% extends "base.html" %}
{% block title %}{{ ct('edit') if event else ct('add') }} · UbyHost{% endblock %}
{% block content %}
<link rel="stylesheet" href="/static/cleaning.css?v=20261016-0123a-0106b">
<div class="cleaning-page cleaning-form-page"><a href="/cleaning">{{ ct('back') }}</a>
<h1>{{ ct('edit') if event else ct('add') }}</h1>
```

Anchor C, `App/app/templates/cleaning_properties.html` lines 1 to 5 (verbatim):

```
{% extends "base.html" %}
{% block title %}{{ ct('settings') }} · UbyHost{% endblock %}
{% block content %}
<link rel="stylesheet" href="/static/cleaning.css?v=20261016a-0106b">
<div class="cleaning-page"><a href="/cleaning">{{ ct('back') }}</a><h1>{{ ct('settings') }}</h1>
```

Anchor D, `App/app/templates/cleaning_settings.html` lines 1 to 5 (verbatim):

```
{% extends "base.html" %}
{% block title %}{{ home.internal_name }} · {{ ct('title') }}{% endblock %}
{% block content %}
<link rel="stylesheet" href="/static/cleaning.css?v=20261016-0123b-0106b">
<div class="cleaning-page cleaning-form-page"><a href="/cleaning/properties">{{ ct('settings') }}</a><h1>{{ home.internal_name }}</h1>
```

Anchor E, `App/app/templates/cleaning_shares.html` lines 1 to 5 (verbatim):

```
{% extends "base.html" %}
{% block title %}{{ ct('share') }} · UbyHost{% endblock %}
{% block content %}
<link rel="stylesheet" href="/static/cleaning.css?v=20261016a-0106b">
<div class="cleaning-page cleaning-form-page"><a href="/cleaning">{{ ct('back') }}</a><h1>{{ ct('share') }}</h1><p>{{ ct('share_intro') }}</p>
```

Anchor F, `App/app/templates/base.html`, one line (added by 0128): `  <link rel="stylesheet" href="/static/host2.css?v=20261019-v2a">`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/cleaning.html` | edit | head |
| `App/app/templates/cleaning_edit.html` | edit | head, classes |
| `App/app/templates/cleaning_properties.html` | edit | head |
| `App/app/templates/cleaning_settings.html` | edit | head, classes |
| `App/app/templates/cleaning_shares.html` | edit | head, classes |
| `App/app/templates/_cleaning_list.html` | edit | one button class |
| `App/app/templates/_cleaning_screen.html` | edit | two fields, one button |
| `App/app/templates/base.html` | edit | conditional `cleaning.css` link |
| `docs/design/catalog.json` | edit | enforce the five pages; legacy lists |
| `App/tests/test_design_cleaning.py` | create | shells, stylesheet once, one primary |

No other file may change. `cleaning_shared.html`, `cleaning.css`, `cleaning.js` stay as they are.

## 4. Steps

1. `base.html`: replace Anchor F with:

```
  {% if nav | default('') == 'cleaning' %}<link rel="stylesheet" href="/static/cleaning.css?v=20261019-v2a">{% endif %}
  <link rel="stylesheet" href="/static/host2.css?v=20261019-v2a">
```

   `host2.css` stays last so its control rules win over `cleaning.css` where both match. Command: `grep -c 'cleaning.css' App/app/templates/base.html`. Expected: `1`.

2. `cleaning.html`: replace Anchor A with:

```
{% extends "host_page.html" %}
{% set body_kind = 'list' %}
{% from "_ui.html" import ui_button with context %}
{% block title %}{{ ct('title') }} · UbyHost{% endblock %}
{% block page_title %}{{ ct('title') }}{% endblock %}
{% block meta %}{{ ct('subtitle') }}{% endblock %}
{% block primary_action %}{{ ui_button(ct('add'), 'primary', href='/cleaning/new', icon_name='plus', attrs='data-calendar-add data-cal-create-type="cleaning"') }}{% endblock %}
{% block secondary_actions %}{{ ui_button(t('calendar.add_stay'), 'secondary', href='/reservations?new=1', attrs='data-calendar-add data-cal-create-type="stay"') }}{{ ui_button(ct('settings'), 'secondary', href='/cleaning/properties') }}{{ ui_button(ct('share'), 'secondary', href='/cleaning/shares') }}{% endblock %}
{% block body %}
<div class="cleaning-page">
  {% include "_cleaning_screen.html" %}
```

   The import sits at top level (not inside a block) so that the `primary_action`, `secondary_actions` and `body` blocks all see it; blocks do not inherit a sibling block's imports. Compile: `cd App && .venv/bin/python -c "from app.templating import templates; [templates.env.get_template(n) for n in ('cleaning.html','cleaning_edit.html','cleaning_properties.html','cleaning_settings.html','cleaning_shares.html')]; print('compiled')"` (run after step 3 too). Expected: `compiled`.

3. The four sub-pages. Replace Anchor B with:

```
{% extends "host_page.html" %}
{% set body_kind = 'form' %}
{% block title %}{{ ct('edit') if event else ct('add') }} · UbyHost{% endblock %}
{% block page_title %}{{ ct('edit') if event else ct('add') }}{% endblock %}
{% block back_url %}/cleaning{% endblock %}
{% block back_label %}{{ ct('back') }}{% endblock %}
{% block body %}
<div class="cleaning-page cleaning-form-page">
```

   Replace Anchor C with:

```
{% extends "host_page.html" %}
{% set body_kind = 'list' %}
{% block title %}{{ ct('settings') }} · UbyHost{% endblock %}
{% block page_title %}{{ ct('settings') }}{% endblock %}
{% block back_url %}/cleaning{% endblock %}
{% block back_label %}{{ ct('back') }}{% endblock %}
{% block body %}
<div class="cleaning-page">
```

   Replace Anchor D with:

```
{% extends "host_page.html" %}
{% set body_kind = 'form' %}
{% block title %}{{ home.internal_name }} · {{ ct('title') }}{% endblock %}
{% block page_title %}{{ home.internal_name }}{% endblock %}
{% block back_url %}/cleaning/properties{% endblock %}
{% block back_label %}{{ ct('settings') }}{% endblock %}
{% block body %}
<div class="cleaning-page cleaning-form-page">
```

   Replace Anchor E with:

```
{% extends "host_page.html" %}
{% set body_kind = 'form' %}
{% block title %}{{ ct('share') }} · UbyHost{% endblock %}
{% block page_title %}{{ ct('share') }}{% endblock %}
{% block meta %}{{ ct('share_intro') }}{% endblock %}
{% block back_url %}/cleaning{% endblock %}
{% block back_label %}{{ ct('back') }}{% endblock %}
{% block body %}
<div class="cleaning-page cleaning-form-page">
```

   Then, from `App/`:

```
.venv/bin/python - <<'EOF'
import pathlib
PLAN = {
 "cleaning_edit.html": [('class="btn primary"', 'class="ui-btn ui-btn-primary"', 1), ('class="btn danger"', 'class="ui-btn ui-btn-danger"', 1), ('class="btn"', 'class="ui-btn ui-btn-secondary"', 1), ('class="field"', 'class="ui-field"', 3)],
 "cleaning_settings.html": [('class="btn primary"', 'class="ui-btn ui-btn-primary"', 1), ('class="btn danger"', 'class="ui-btn ui-btn-danger"', 1), ('class="btn"', 'class="ui-btn ui-btn-secondary"', 2), ('class="field"', 'class="ui-field"', 2)],
 "cleaning_shares.html": [('class="btn primary"', 'class="ui-btn ui-btn-primary"', 1), ('class="btn"', 'class="ui-btn ui-btn-secondary"', 1)],
 "_cleaning_list.html": [('class="btn"', 'class="ui-btn ui-btn-secondary ui-btn-compact"', 1)],
 "_cleaning_screen.html": [('class="btn"', 'class="ui-btn ui-btn-secondary"', 1), ('class="field"', 'class="ui-field"', 2)],
}
for name, pairs in PLAN.items():
    p = pathlib.Path("app/templates") / name; s = p.read_text(encoding="utf-8")
    for old, new, n in pairs:
        assert s.count(old) == n, (name, old, s.count(old)); s = s.replace(old, new)
    assert 'class="btn' not in s and "<link" not in s and 'style="' not in s, name
    p.write_text(s, encoding="utf-8")
print("ok")
EOF
```

   Expected: `ok`. `cleaning_edit.html` and `cleaning_settings.html` have `class="field"` on one line with other attributes; the substring match still finds them.

4. Catalog: add the five page templates to `enforced_templates` (the two partials stay unenforced: `_cleaning_screen.html` carries the `<script data-cleaning-labels>` and `<script src="/static/cleaning.js">` tags, which rule T1 forbids in pages). For each page run `python3 scripts/design_lint.py 2>&1 | grep <name> | sed 's/.*catalog: //' | sort -u | tr '\n' ' '` and put the tokens into its `legacy` list (the `cleaning-*` classes). Command: `python3 scripts/design_lint.py`. Expected: OK.

5. Create `App/tests/test_design_cleaning.py`:

```python
"""0143: host cleaning pages render on host_page; cleaning.css loads once from base."""
from __future__ import annotations

from tests.test_signed_in_chrome import host_with_property  # noqa: F401

PAGES = ("/cleaning", "/cleaning/new", "/cleaning/properties", "/cleaning/shares")


def test_cleaning_pages_have_the_v2_shell_and_one_stylesheet(host_with_property):
    for path in PAGES:
        page = host_with_property.get(f"{path}?lang=en").text
        assert page.count("<h1") == 1, path
        assert page.count("/static/cleaning.css") == 1, path
        assert page.index("/static/cleaning.css") < page.index("/static/host2.css"), path
        assert page.count('class="ui-btn ui-btn-primary"') == 1, path
        assert "cleaning-page-heading" not in page and 'class="btn' not in page, path


def test_other_host_pages_do_not_load_cleaning_css(host_with_property):
    assert "/static/cleaning.css" not in host_with_property.get("/reservations?lang=en").text


def test_shared_cleaner_page_template_is_untouched():
    text = open("app/templates/cleaning_shared.html", encoding="utf-8").read()
    assert 'href="/static/cleaning.css' in text
```

   If the shared template links its stylesheet with another attribute order, adjust the last assertion to the exact substring and say so in the report. Command: `cd App && .venv/bin/python -m pytest tests/test_design_cleaning.py tests/test_cleaning*.py tests/test_design_lint.py -q --tb=short -x 2>&1 | tail -30`. Expected: passed.

6. Browser and screenshots: `cd App && UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-shots .venv/bin/python -m pytest tests/test_cleaning_browser.py -q --tb=short 2>&1 | tail -30`. Expected: passed, 0 skipped. Attach `cleaning-390.png`, `cleaning-1280.png`, `cleaning-edit-390.png`.

7. Commit: `git add App/app/templates docs/design/catalog.json App/tests && git commit -m "0143 step 7: host cleaning pages on host_page, cleaning.css from base"`.

## 5. Do not touch

`cleaning_shared.html`, `cleaning.css`, `cleaning.js`, `routes/cleaning.py`, `cleaning_i18n.py`; hard rules 2, 3, 8.

## 6. Commands

- `python3 scripts/design_lint.py` expected: OK.
- Step 5 and step 6 commands, 0 skipped.

## 7. Acceptance

- [ ] Cleaning list: v2 header, one primary Add cleaning (still opens the calendar quick-create), three secondaries, calendar and cards unchanged.
- [ ] Edit, properties, property settings, shares: back link, title, v2 buttons and fields.
- [ ] The shared cleaner page looks exactly as before (open one share link at 390 px: `cleaning-shared-390.png`).
- [ ] Screenshots attached; lint OK with the five templates enforced.

## 8. Stop and ask

Stop, and write the report, if: an excerpt is not found; a count differs; a test fails twice; you reach 25 tool calls or about 50k tokens (report as `blocked`); a file outside section 3 needs a change; section 5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0143-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

`App/app/templates/base.html` (stylesheet order), the shared cleaner page (must keep its own stylesheet link).

## Owner steps

None.
