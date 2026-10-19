# 0144: Settings, Archive, Privacy requests, Guide and the onboarding welcome on the v2 template

Status: todo
Depends on: 0143 | Base commit: df8b842 | Branch: claude/project-thread-td6fpc
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

Part of [design-v2](../plans/design-v2.md). Commit each step as `0144 step k`. Never push, never open a PR. Page file: `docs/design/pages/settings.md`.

## 1. Objective

Move `settings.html` (settings kind), `settings_archived.html` (list kind with chips), `privacy_requests.html` (form kind), `guide.html` (settings kind) and `onboarding.html` (detail kind, no header) onto `host_page.html`, replace legacy controls, badges, banners, fields and panels with v2 classes, and remove every inline style. Section ids (`settings-account` ... `settings-version`, `settings-technical`, `settings-audit`), the settings index grid (`host-property-grid`), the `settings_group` sections, the UbyPort PIN panel and all forms keep their ids, names and order.

## 2. Context

Rules: MASTER 5 (settings kind), 7.2, 7.5 (chips), 7.9, 4. `app.js` and `host.js` key on ids, `data-copy`, `data-confirm`, `data-toggle-panel`, `.host-audit-filter`, never on `.btn`, `.pill`, `.chip` or `.field`. `test_settings_technical.py` slices the page between two exact tags (updated in step 6); `test_host_account_navigation.py` uses ids only.

Anchor A, `App/app/templates/settings.html` lines 1 to 6 (verbatim):

```
{% extends "base.html" %}
{% set nav = 'settings' %}
{% block title %}{{ t('nav.settings') }}{% endblock %}
{% block content %}
{% from "_components.html" import page_header, field_label, help_tip, settings_group, settings_heading with context %}
{{ page_header(t('nav.settings'), t('settings.lede')) }}
```

Anchor B, `App/app/templates/settings_archived.html` lines 1 to 11 (verbatim):

```
{% extends "base.html" %}
{% set nav = 'settings' %}
{% block title %}{{ t('archive.title') }}{% endblock %}
{% block content %}
{% from "_components.html" import page_header, help_tip, row_menu_begin, row_menu_end with context %}
{{ page_header(
  t('archive.title'),
  t('archive.page_lede'),
  '/settings',
  t('common.back')
) }}
```

Anchor C, same file, the chip block (verbatim):

```
<div class="chips archive-type-filters" role="group" aria-label="{{ t('archive.title') }}">
  {% for value, label_key in [
    ('all', 'archive.chip.all_count'),
    ('stays', 'archive.chip.stays_count'),
    ('properties', 'archive.chip.properties_count'),
    ('housebook', 'archive.chip.housebook_count'),
    ('entities', 'archive.chip.entities_count')
  ] %}
    <a class="chip {{ 'on' if item_type == value }}" href="/settings/archived?type={{ value }}">
      {{ t(label_key, count=counts[value]) }}
    </a>
```

Anchor D, `App/app/templates/privacy_requests.html` lines 1 to 6 (verbatim):

```
{% extends "base.html" %}
{% set nav = 'privacy_requests' %}
{% block title %}{{ t('privacy_requests.title') }}{% endblock %}
{% block content %}
{% from "_components.html" import page_header with context %}
{{ page_header(t('privacy_requests.title'), t('privacy_requests.lede')) }}
```

Anchor E, `App/app/templates/guide.html` lines 1 to 6 (verbatim):

```
{% extends "base.html" %}
{% set nav = 'guide' %}
{% block title %}{{ t('guide.title') }}{% endblock %}
{% block content %}
{% from "_components.html" import page_header with context %}
{{ page_header(t('guide.title'), t('guide.lede')) }}
```

Anchor F, `App/app/templates/onboarding.html` (whole file, 7 lines):

```
{% extends "base.html" %}
{% set nav = 'dashboard' %}
{% block title %}{{ t('onboarding.welcome_title') }}{% endblock %}
{% block content %}
{% from "_components.html" import onboarding_welcome with context %}
{{ onboarding_welcome(onboarding) }}
{% endblock %}
```

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/settings.html` | edit | head, classes, 9 styles |
| `App/app/templates/settings_archived.html` | edit | head, chips, classes, 1 style |
| `App/app/templates/privacy_requests.html` | edit | head, classes, 1 style |
| `App/app/templates/guide.html` | edit | head, classes, 1 style |
| `App/app/templates/onboarding.html` | edit | head |
| `App/app/static/host2.css` | edit | two named classes for the moved styles |
| `docs/design/catalog.json` | edit | enforce the five templates; legacy lists |
| `App/tests/test_settings_technical.py` | edit | two tag constants |
| `App/tests/test_host_controls_browser.py` | edit | one selector |
| `App/tests/test_guide.py` | edit | one string |
| `App/tests/test_design_settings.py` | create | shells, no styles |

No other file may change.

## 4. Steps

1. Heads. Replace Anchor A with:

```
{% extends "host_page.html" %}
{% set nav = 'settings' %}
{% set body_kind = 'settings' %}
{% block title %}{{ t('nav.settings') }}{% endblock %}
{% block page_title %}{{ t('nav.settings') }}{% endblock %}
{% block meta %}{{ t('settings.lede') }}{% endblock %}
{% block body %}
{% from "_components.html" import field_label, help_tip, settings_group, settings_heading with context %}
```

   Replace Anchor B with:

```
{% extends "host_page.html" %}
{% set nav = 'settings' %}
{% set body_kind = 'list' %}
{% block title %}{{ t('archive.title') }}{% endblock %}
{% block page_title %}{{ t('archive.title') }}{% endblock %}
{% block meta %}{{ t('archive.page_lede') }}{% endblock %}
{% block back_url %}/settings{% endblock %}
{% block back_label %}{{ t('common.back') }}{% endblock %}
{% block body %}
{% from "_components.html" import help_tip, row_menu_begin, row_menu_end with context %}
```

   Replace Anchor D with:

```
{% extends "host_page.html" %}
{% set nav = 'privacy_requests' %}
{% set body_kind = 'form' %}
{% block title %}{{ t('privacy_requests.title') }}{% endblock %}
{% block page_title %}{{ t('privacy_requests.title') }}{% endblock %}
{% block meta %}{{ t('privacy_requests.lede') }}{% endblock %}
{% block body %}
```

   Replace Anchor E with:

```
{% extends "host_page.html" %}
{% set nav = 'guide' %}
{% set body_kind = 'settings' %}
{% block title %}{{ t('guide.title') }}{% endblock %}
{% block page_title %}{{ t('guide.title') }}{% endblock %}
{% block meta %}{{ t('guide.lede') }}{% endblock %}
{% block body %}
```

   Replace Anchor F (whole file) with:

```
{% extends "host_page.html" %}
{% set nav = 'dashboard' %}
{% set body_kind = 'detail' %}
{% block title %}{{ t('onboarding.welcome_title') }}{% endblock %}
{% block page_title %}{% endblock %}
{% block body %}
{% from "_components.html" import onboarding_welcome with context %}
{{ onboarding_welcome(onboarding) }}
{% endblock %}
```

   (an empty `page_title` renders no header; the welcome card has its own heading). Compile: `cd App && .venv/bin/python -c "from app.templating import templates; [templates.env.get_template(n) for n in ('settings.html','settings_archived.html','privacy_requests.html','guide.html','onboarding.html')]; print('compiled')"`. Expected: `compiled`.

2. Chips: replace Anchor C with:

```
<div class="ui-chips archive-type-filters" role="group" aria-label="{{ t('archive.title') }}">
  {% for value, label_key in [
    ('all', 'archive.chip.all_count'),
    ('stays', 'archive.chip.stays_count'),
    ('properties', 'archive.chip.properties_count'),
    ('housebook', 'archive.chip.housebook_count'),
    ('entities', 'archive.chip.entities_count')
  ] %}
    <a class="ui-chip" href="/settings/archived?type={{ value }}"{% if item_type == value %} aria-current="true"{% endif %}>
      {{ t(label_key, count=counts[value]) }}
    </a>
```

3. Styles and classes, from `App/`:

```
.venv/bin/python - <<'EOF'
import pathlib, re
T = pathlib.Path("app/templates")
def run(name, exact, pairs, primaries):
    p = T / name; s = p.read_text(encoding="utf-8")
    for old, new in exact:
        assert s.count(old) == 1, (name, old, s.count(old)); s = s.replace(old, new)
    for old, new, n in pairs:
        assert s.count(old) == n, (name, old, s.count(old)); s = s.replace(old, new)
    assert 'style="' not in s, (name, re.findall(r' style="[^"]*"', s))
    assert 'class="btn' not in s and 'class="pill' not in s and 'class="chip' not in s, name
    assert s.count("ui-btn-primary") == primaries, (name, s.count("ui-btn-primary"))
    p.write_text(s, encoding="utf-8")
run("settings.html", [
 ('<div class="panel" id="settings-data" style="margin-top:14px">', '<div class="ui-section" id="settings-data">'),
 ('<h2 id="settings-overview" style="margin-top:0">', '<h2 id="settings-overview">'),
 ('<div class="banner warning" style="margin-top:14px">', '<div class="ui-banner ui-banner-attention">'),
 ('<table class="data" style="margin-top:12px">', '<table class="ui-table">'),
 ('<pre class="small" style="white-space:pre-wrap">', '<pre class="ui-sub ui-prewrap">'),
 ('style="width:100%;min-height:420px;margin-top:8px;border:1px solid var(--line);border-radius:10px;background:#fff"', 'class="settings-mail-preview"'),
 ('<details class="panel technical" id="settings-technical">', '<details class="ui-section technical" id="settings-technical">'),
 ('<details class="panel technical" open id="settings-audit">', '<details class="ui-section technical" open id="settings-audit">'),
 ('class="btn {{ \'danger\' if expired_records else \'\' }}"', 'class="ui-btn ui-btn-{{ \'danger\' if expired_records else \'secondary\' }}"'),
], [
 ('<h3 style="margin-top:0">', '<h3>', 2),
 ('<h2 style="margin-top:0">', '<h2>', 1),
 ('class="btn small primary"', 'class="ui-btn ui-btn-primary ui-btn-compact"', 1),
 ('class="btn small"', 'class="ui-btn ui-btn-secondary ui-btn-compact"', 13),
 ('class="btn"', 'class="ui-btn ui-btn-secondary"', 1),
 ('class="pill grey"', 'class="ui-badge ui-badge-neutral" data-tone="grey"', 1),
 ('class="pill green"', 'class="ui-badge ui-badge-done" data-tone="green"', 1),
 ('class="banner warning"', 'class="ui-banner ui-banner-attention"', 1),
 ('class="panel"', 'class="ui-section"', 10),
 ('class="table-cards"', 'class="ui-table ui-table-stack"', 1),
 ('class="field"', 'class="ui-field"', 4),
 ('class="small muted"', 'class="ui-sub"', 14),
 ('class="muted small"', 'class="ui-sub"', 1),
 ('class="mono small"', 'class="ui-mono ui-sub"', 2),
 ('class="nowrap small"', 'class="ui-sub nowrap"', 1),
 ('class="small err-text"', 'class="ui-sub err-text"', 1),
 ('class="kv small"', 'class="kv ui-sub"', 1),
 ('class="small"', 'class="ui-sub"', 4),
 ('class="muted"', 'class="ui-sub"', 2),
 ('class="mono"', 'class="ui-mono"', 3),
], 1)
run("settings_archived.html", [
 ('<div class="actions" style="justify-content:center">', '<div class="ui-form-actions ui-center">'),
], [
 ('class="btn small"', 'class="ui-btn ui-btn-secondary ui-btn-compact"', 1),
 ('class="btn"', 'class="ui-btn ui-btn-secondary"', 4),
 ('class="table-cards"', 'class="ui-table ui-table-stack"', 4),
 ('class="panel tight scroll-x"', 'class="ui-section scroll-x"', 4),
 ('class="panel empty"', 'class="ui-empty"', 5),
 ('class="small muted"', 'class="ui-sub"', 5),
 ('class="nowrap small"', 'class="ui-sub nowrap"', 1),
 ('class="num"', 'class="ui-num"', 1),
 ('class="mono"', 'class="ui-mono"', 1),
], 0)
run("privacy_requests.html", [
 ('<h2 style="margin-top:0">', '<h2>'),
], [
 ('class="btn primary"', 'class="ui-btn ui-btn-primary"', 1),
 ('class="btn"', 'class="ui-btn ui-btn-secondary"', 1),
 ('class="field"', 'class="ui-field"', 8),
 ('class="actions"', 'class="ui-form-actions"', 2),
 ('class="grid"', 'class="ui-pair"', 2),
 ('class="panel"', 'class="ui-section"', 2),
 ('class="small muted"', 'class="ui-sub"', 1),
 ('class="muted"', 'class="ui-sub"', 1),
], 1)
run("guide.html", [
 ('<p class="small" style="margin:12px 0">', '<p class="ui-sub">'),
 ('class="pill {{ tone }}"', 'class="ui-badge ui-badge-{{ \'done\' if tone == \'green\' else \'action\' }}" data-tone="{{ tone }}"'),
], [
 ('class="btn primary"', 'class="ui-btn ui-btn-primary"', 1),
 ('class="btn small"', 'class="ui-btn ui-btn-secondary ui-btn-compact"', 1),
 ('class="guide-section panel guide-legal"', 'class="guide-section ui-section guide-legal"', 1),
 ('class="guide-section panel"', 'class="guide-section ui-section"', 15),
 ('class="guide-nav panel"', 'class="guide-nav ui-section"', 1),
 ('class="legal-disclaimer panel quiet"', 'class="legal-disclaimer ui-section quiet"', 1),
 ('class="small muted legal-fineprint"', 'class="ui-sub legal-fineprint"', 1),
 ('class="small muted"', 'class="ui-sub"', 11),
 ('class="legal-list small"', 'class="legal-list ui-sub"', 1),
 ('class="muted"', 'class="ui-sub"', 1),
], 1)
print("ok")
EOF
```

   Expected: `ok`. If the `<details ... technical>` lines have `class="panel technical"` with another attribute order, copy the actual line into the exact pair. Append to `App/app/static/host2.css`:

```
/* 0144 settings: moved inline styles */
.ui-prewrap { white-space: pre-wrap; }
.ui-center { justify-content: center; }
.settings-mail-preview { width: 100%; min-height: 26rem; margin-top: var(--space-2); border: 1px solid var(--line); border-radius: var(--radius-2); background: var(--surface); }
```

   If `--surface` is not defined in the 0125 token layer, use `var(--surface-1)` and name it in the report.

4. `grep -n 'panel\b' App/app/static/host.css | grep -c 'guide-section\|guide-nav\|settings'`: if any rule in `host.css` selects `.guide-section.panel`, `.guide-nav.panel` or `.panel.technical`, copy that rule to the end of `host2.css` with `.panel` replaced by `.ui-section` (under the `/* 0144 */` comment) so the guide layout keeps its spacing. Expected: at most three short rules copied; list them in the report.

5. Catalog: add the five templates to `enforced_templates`; for each run `python3 scripts/design_lint.py 2>&1 | grep <name> | sed 's/.*catalog: //' | sort -u | tr '\n' ' '` and put the tokens into its `legacy` list. Command: `python3 scripts/design_lint.py`. Expected: OK.

6. Tests. `App/tests/test_settings_technical.py` line 22: `OPEN_TAG = '<details class="panel technical" id="settings-technical">'` → `OPEN_TAG = '<details class="ui-section technical" id="settings-technical">'`; line 23: `PIN_PANEL = '<div class="panel" id="settings-ubyport">'` → `PIN_PANEL = '<div class="ui-section" id="settings-ubyport">'`. `App/tests/test_host_controls_browser.py` line 242: `page.locator(".archive-type-filters .chip").count() == 5` → `page.locator(".archive-type-filters .ui-chip").count() == 5`. `App/tests/test_guide.py` line 15: `'<span class="pill red">'` → `'<span class="ui-badge ui-badge-action" data-tone="red">'`. Create `App/tests/test_design_settings.py`:

```python
"""0144: settings group pages render on host_page without inline styles."""
from __future__ import annotations

from tests.test_signed_in_chrome import host_with_property  # noqa: F401

PAGES = {"/settings": "settings", "/settings/archived": "list", "/privacy-requests": "form", "/guide": "settings"}
TEMPLATES = ("settings.html", "settings_archived.html", "privacy_requests.html", "guide.html", "onboarding.html")


def test_settings_pages_have_the_v2_shell(host_with_property):
    for path, kind in PAGES.items():
        response = host_with_property.get(f"{path}?lang=en")
        assert response.status_code == 200, path
        page = response.text
        assert page.count("<h1") == 1 and f'data-body-kind="{kind}"' in page, path
        assert 'style="' not in page.split('<main', 1)[1], path
        assert page.count('class="ui-btn ui-btn-primary') <= 1, path


def test_archive_chips_mark_the_current_type(host_with_property):
    page = host_with_property.get("/settings/archived?type=stays&lang=en").text
    assert page.count('class="ui-chip"') == 5 and page.count('aria-current="true"') >= 1


def test_templates_have_no_raw_style_or_legacy_control():
    for name in TEMPLATES:
        text = open(f"app/templates/{name}", encoding="utf-8").read()
        assert 'style="' not in text and 'class="btn' not in text and 'class="pill' not in text, name
```

   If `/privacy-requests` is not the route path, read it from `grep -n '"/privacy' App/app/routes/*.py | head -3` and fix the dict. Command: `cd App && .venv/bin/python -m pytest tests/test_design_settings.py tests/test_settings*.py tests/test_host_account_navigation.py tests/test_guide.py tests/test_privacy_requests*.py tests/test_design_lint.py -q --tb=short -x 2>&1 | tail -30`. Expected: passed.

7. Browser and screenshots: `cd App && UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-shots .venv/bin/python -m pytest tests/test_host_controls_browser.py tests/test_host_wide_geometry_browser.py tests/test_onboarding_followup_browser.py -q --tb=short 2>&1 | tail -30`. Expected: passed, 0 skipped. Attach `settings-390.png`, `settings-1280.png`, `archive-390.png`, `guide-390.png`.

8. Commit: `git add App/app/templates App/app/static/host2.css docs/design/catalog.json App/tests && git commit -m "0144 step 8: settings, archive, privacy requests, guide and welcome on host_page"`.

## 5. Do not touch

`routes/admin.py`, `routes/settings*.py`, `_components.html` (`settings_group`, `settings_heading`, `onboarding_welcome` stay), the UbyPort PIN form fields, `host.css`; hard rules 1, 2, 3, 8.

## 6. Commands

- `python3 scripts/design_lint.py` expected: OK.
- Step 6 and step 7 commands, 0 skipped.

## 7. Acceptance

- [ ] Settings: header, index grid, groups and ids unchanged; technical details still fold; mail preview iframe has the same size.
- [ ] Archive: back link, v2 chips with the current type marked, v2 tables.
- [ ] Privacy requests, Guide, welcome page: v2 shells, one primary at most.
- [ ] Screenshots attached; lint OK with the five templates enforced.

## 8. Stop and ask

Stop, and write the report, if: an excerpt is not found; a count differs; a test fails twice; you reach 25 tool calls or about 50k tokens (report as `blocked`); a file outside section 3 needs a change; section 5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0144-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

`App/app/templates/settings.html` (UbyPort PIN panel and retention actions sit here; hard rule 1 adjacency, classes only).

## Owner steps

None.
