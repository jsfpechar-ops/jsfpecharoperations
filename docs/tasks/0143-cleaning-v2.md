# 0143: Cleaning pages (host side) on the v2 template

Status: done
Depends on: 0142 | Base commit: c340b7f | Branch: claude/project-thread-5hw8cf
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

Part of [design-v2](../plans/design-v2.md). One commit at the end (step 9). Never push, never open a PR. Page file: `docs/design/pages/cleaning.md`.

## 1. Objective

Move the five host cleaning pages (`cleaning.html`, `cleaning_edit.html`, `cleaning_properties.html`, `cleaning_settings.html`, `cleaning_shares.html`) onto `host_page.html`: v2 header with one primary, back links, v2 buttons and fields. `cleaning.css` stops being linked from inside each template and is loaded once by `base.html` for `nav == 'cleaning'`. The shared public page `cleaning_shared.html` (cleaner's link, no sign-in) and `cleaning.js` are untouched; the calendar cards, pins and date groups keep their `cleaning-*` classes.

## 2. Context

Rules: MASTER 5 (list, form kinds), 4 (one primary), 7.2. `cleaning.js` keys on `data-cleaning-labels`, `[data-calendar-add]`, `data-cal-create-type`, `.cleaning-card` and ids; `app.js` keys on `data-confirm`; neither keys on `.btn` or `.field`. The cleaning route already passes `nav: "cleaning"` and `ct` (the cleaning translator) in the context, so the templates do not set `nav`. Tests (`test_cleaning.py`, `test_cleaning_browser.py`) select `.cleaning-card`, `.cleaning-pin`, `.cleaning-date-group h3` and the sidebar link; none selects `.btn` or the heading block.

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

Anchor F, `App/app/templates/base.html`: the one line containing `href="/static/host2.css?v=`. Earlier briefs (0138 to 0142) may bump its `?v=` key, so step 1 finds the line by that prefix, not by the full line. At c340b7f it reads `  <link rel="stylesheet" href="/static/host2.css?v=20261019-v2a">` (inside the `{% if show_nav | default(true) %}` group).

Anchors A to E were re-checked verbatim at c340b7f, after cleaning management (PR #396) merged; no earlier brief touches these seven cleaning templates. `_dashboard_calendar.html` (included by `_cleaning_screen.html`) and `base.html` still carry old `class="btn` buttons; they are out of scope, so the new test checks the page header and the cleaning templates, not the whole page.

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
| `App/tests/static_versions.json` | regenerate | newest `cleaning.css` key becomes `20261019-0143` (step 8) |

Existing tests on this markup, which must pass unchanged (checked at c340b7f with every edit below applied): `App/tests/test_cleaning.py`, `App/tests/test_cleaning_browser.py`.

No other file may change. `cleaning_shared.html`, `cleaning.css`, `cleaning.js` stay as they are.

## 4. Steps

1. `base.html`: add the conditional `cleaning.css` link on its own line directly above Anchor F. From `App/`:

```
.venv/bin/python - <<'PY'
import pathlib
p = pathlib.Path("app/templates/base.html"); s = p.read_text(encoding="utf-8")
assert "cleaning.css" not in s, "cleaning.css already in base.html"
lines = s.split("\n")
hits = [i for i, l in enumerate(lines) if 'href="/static/host2.css?v=' in l]
assert len(hits) == 1, hits
lines.insert(hits[0], "  {% if nav | default('') == 'cleaning' %}<link rel=\"stylesheet\" href=\"/static/cleaning.css?v=20261019-0143\">{% endif %}")
p.write_text("\n".join(lines), encoding="utf-8")
print("ok")
PY
grep -c 'cleaning.css' app/templates/base.html
```

   Expected: `ok`, then `1`. `host2.css` stays after it so its control rules win over `cleaning.css` where both match.

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


4. Catalog: enforce the five page templates and give each its `legacy` list (the two partials stay unenforced: `_cleaning_screen.html` carries the `<script data-cleaning-labels>` and `<script src="/static/cleaning.js">` tags, which rule T1 forbids). Edit by name with this script, from the repo root (the lists were computed from the templates after step 3):

```
python3 - <<'PY'
import json, pathlib
p = pathlib.Path("docs/design/catalog.json"); c = json.loads(p.read_text(encoding="utf-8"))
T = "App/app/templates/"
LEGACY = {
 "cleaning.html": ["cleaning-page"],
 "cleaning_edit.html": ["cleaning-actions", "cleaning-form", "cleaning-form-page", "cleaning-page", "cleaning-panel", "cleaning-remove", "cleaning-timing-summary", "cleaning-warning"],
 "cleaning_properties.html": ["cleaning-page", "cleaning-panel", "cleaning-property-links"],
 "cleaning_settings.html": ["cleaning-form", "cleaning-form-page", "cleaning-page", "cleaning-panel", "cleaning-pin", "cleaning-remove", "cleaning-timing-summary", "cleaning-warning"],
 "cleaning_shares.html": ["cleaning-form", "cleaning-form-page", "cleaning-page", "cleaning-panel", "cleaning-share-option", "cleaning-share-row", "cleaning-share-url", "cleaning-warning"],
}
for name, tokens in LEGACY.items():
    if T + name not in c["enforced_templates"]:
        c["enforced_templates"].append(T + name)
    c["legacy"][T + name] = tokens
p.write_text(json.dumps(c, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("ok")
PY
python3 scripts/design_lint.py 2>&1 | tail -5
```

   Expected: `ok`, then `design lint: OK`. (The dump reflows the file's hand wrapping; that is expected.) If the lint names a `cleaning-*` token for one of these five files, add it to that file's list and rerun; anything else: stop.

5. Create `App/tests/test_design_cleaning.py`:

```python
"""0143: host cleaning pages render on host_page; cleaning.css loads once from base."""
from __future__ import annotations

from pathlib import Path

from tests.test_signed_in_chrome import host_with_property  # noqa: F401

TEMPLATES = Path(__file__).resolve().parent.parent / "app" / "templates"
# path -> ui-btn-primary count inside the page (properties is a plain link list)
PAGES = {"/cleaning": 1, "/cleaning/new": 1, "/cleaning/properties": 0, "/cleaning/shares": 1}
HOST_TEMPLATES = ("cleaning.html", "cleaning_edit.html", "cleaning_properties.html", "cleaning_settings.html",
                  "cleaning_shares.html", "_cleaning_list.html", "_cleaning_screen.html")


def test_cleaning_pages_have_the_v2_shell_and_one_stylesheet(host_with_property):
    for path, primaries in PAGES.items():
        response = host_with_property.get(f"{path}?lang=en")
        assert response.status_code == 200, path
        page = response.text
        assert page.count("<h1") == 1, path
        assert page.count("/static/cleaning.css") == 1, path
        assert page.index("/static/cleaning.css") < page.index("/static/host2.css"), path
        header = page[page.index('<header class="ui-ph"'):]
        header = header[: header.index("</header>")]
        assert 'class="btn' not in header and "cleaning-page-heading" not in page, path
        lane = page[page.index('<div class="ui-page"'): page.index("</main>")]
        assert lane.count("ui-btn-primary") == primaries, path


def test_host_cleaning_templates_use_only_v2_buttons_and_no_own_stylesheet():
    for name in HOST_TEMPLATES:
        text = (TEMPLATES / name).read_text(encoding="utf-8")
        assert 'class="btn' not in text and 'class="field"' not in text and "<link" not in text, name


def test_other_host_pages_do_not_load_cleaning_css(host_with_property):
    assert "/static/cleaning.css" not in host_with_property.get("/reservations?lang=en").text


def test_shared_cleaner_page_template_keeps_its_own_stylesheet():
    text = (TEMPLATES / "cleaning_shared.html").read_text(encoding="utf-8")
    assert 'href="/static/cleaning.css?v=20261016-0123b-0106b"' in text
    assert 'class="cleaning-page-heading"' in text
```

   Command: none (step 6 runs it).

6. Unit tests, from `App/`: `.venv/bin/python -m pytest tests/test_design_cleaning.py tests/test_cleaning.py tests/test_design_lint.py tests/test_design_page_template.py -q --tb=short -x 2>&1 | tail -30`. Expected: passed (about 50).

7. Browser, from `App/`: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium .venv/bin/python -m pytest tests/test_cleaning_browser.py tests/test_shell_lane_browser.py -q --tb=short -rs 2>&1 | tail -30`. Expected: `25 passed`, 0 skipped (about one minute; run it with a 10-minute timeout). Without `UBYHOST_BROWSER_EXECUTABLE` Playwright looks for a headless shell that is not installed and every test errors. No screenshots: the orchestrator takes them after review.

8. Static version manifest (no static file changes, but the newest `cleaning.css` key changes from `20261016a-0106b` to `20261019-0143`), from `App/`: `.venv/bin/python tests/test_static_versions.py --write && .venv/bin/python -m pytest tests/test_static_versions.py -q 2>&1 | tail -5`. Expected: `wrote ...`, then `2 passed`.

9. Commit: `git add App/app/templates docs/design/catalog.json App/tests && git commit -m "0143: host cleaning pages on host_page, cleaning.css from base"`. Then `git diff --stat HEAD~1 | tail -15`: only section 3 files.

## 5. Do not touch

`cleaning_shared.html`, `cleaning.css`, `cleaning.js`, `routes/cleaning.py`, `cleaning_i18n.py`; hard rules 2, 3, 8.

## 6. Commands

- `python3 scripts/design_lint.py` expected: OK.
- Step 6, 7 and 8 commands; step 7 with 0 skipped.

## 7. Acceptance

- [ ] Cleaning list: v2 header, one primary Add cleaning (still opens the calendar quick-create), three secondaries, calendar and cards unchanged.
- [ ] Edit, properties, property settings, shares: back link, title, v2 buttons and fields.
- [ ] `cleaning_shared.html` is not in `git diff --stat`.
- [ ] Lint OK with the five templates enforced; step 7 passed with 0 skipped.
- No screenshots from the executor: the orchestrator takes them after review.

## 8. Stop and ask

Stop, and write the report, if: an excerpt is not found; a count differs; a test fails twice; you reach 25 tool calls or about 50k tokens (report as `blocked`); a file outside section 3 needs a change; section 5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0143-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

`App/app/templates/base.html` (stylesheet order), the shared cleaner page (must keep its own stylesheet link).

## Owner steps

None.
