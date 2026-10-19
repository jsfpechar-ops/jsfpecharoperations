# 0144: Settings, Archive, Privacy requests, Guide and the onboarding welcome on the v2 template

Status: todo
Depends on: 0143 | Base commit: c340b7f | Branch: claude/project-thread-5hw8cf
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

Part of [design-v2](../plans/design-v2.md). Commit once at the end (step 9). Never push, never open a PR. Page file: `docs/design/pages/settings.md`. The setup wizard (`setup_wizard/*`) is the follow-up brief 0144-b.

## 1. Objective

Move `settings.html` (settings kind), `settings_archived.html` (list kind with chips), `privacy_requests.html` (list kind), `guide.html` (detail kind) and `onboarding.html` (form kind, no header) onto `host_page.html`, replace legacy controls, badges, banners, fields and panels with v2 classes, and remove every inline style. Section ids (`settings-account` ... `settings-version`, `settings-technical`, `settings-audit`), the settings index grid (`host-property-grid`), the `settings_group` sections, the UbyPort PIN panel and all forms keep their ids, names and order.

## 2. Context

Rules: MASTER 5 (page kinds), 7.2, 7.5 (chips), 7.9, 4. Kinds follow `migration-map.md` (settings = settings, archive = list, privacy requests = list, guide = detail, onboarding = form). `app.js` and `host.js` key on ids, `data-copy`, `data-confirm`, `data-toggle-panel`, `.host-audit-filter`, never on `.btn`, `.pill`, `.chip` or `.field`.

How migrated pages do it (copy this, nothing else): `reservations.html`, `reservation_detail.html`, `dashboard.html` start with `{% extends "host_page.html" %}`, set `nav` and `body_kind`, fill `title`, `page_title`, `meta`, `back_url`, `back_label`, `primary_action`, `secondary_actions` and put the page in `{% block body %}`. An empty `page_title` block renders no header (dashboard does this for its welcome). `host_page.html` imports `ui_*` macros only for itself; a page that calls one imports it.

All anchors below were checked verbatim at c340b7f. No earlier brief (0138 to 0143) changes these five templates. `host2.css`, `catalog.json`, `base.html` and `test_host_wide_geometry_browser.py` are shared with earlier briefs, so this brief appends to `host2.css`, edits `catalog.json` with a json script keyed on names, bumps the `host2.css` key with a regex, and changes only one page-specific line in the geometry test.

Anchor A, `App/app/templates/settings.html` lines 1 to 6:

```
{% extends "base.html" %}
{% set nav = 'settings' %}
{% block title %}{{ t('nav.settings') }}{% endblock %}
{% block content %}
{% from "_components.html" import page_header, field_label, help_tip, settings_group, settings_heading with context %}
{{ page_header(t('nav.settings'), t('settings.lede')) }}
```

Anchor B, `App/app/templates/settings_archived.html` lines 1 to 11:

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

Anchor C, same file, two lines of the chip block:

```
<div class="chips archive-type-filters" role="group" aria-label="{{ t('archive.title') }}">
```
```
    <a class="chip {{ 'on' if item_type == value }}" href="/settings/archived?type={{ value }}">
```

Anchor D, `App/app/templates/privacy_requests.html` lines 1 to 6; Anchor E, `App/app/templates/guide.html` lines 1 to 6; Anchor F, `App/app/templates/onboarding.html` (whole file, 7 lines): quoted inside the step 1 script.

Pre-existing, fixed here: `App/tests/test_host_controls_browser.py` lines 201 to 206 measure `.action-group .btn` on the dashboard, which 0133 to 0137 removed, so the test fails at line 206 (`AssertionError: (360, [])`) before it reaches the archive chip check at line 242. Step 6 points it at the v2 header primary (40 px at 1280, 44 px on phone).

Browser: Chromium is at `/opt/pw-browsers/chromium`, but `tests/browser_support.py` only uses it when `UBYHOST_BROWSER_EXECUTABLE` is set. Every browser command below sets it.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/settings.html` | edit | head, classes, 9 styles |
| `App/app/templates/settings_archived.html` | edit | head, chips, classes, 1 style |
| `App/app/templates/privacy_requests.html` | edit | head, classes, 1 style |
| `App/app/templates/guide.html` | edit | head, classes, 1 style |
| `App/app/templates/onboarding.html` | edit | head |
| `App/app/static/host2.css` | edit | append three rules for the moved styles |
| `App/app/templates/base.html` | edit | `host2.css?v=` key only (step 8) |
| `App/tests/static_versions.json` | edit | regenerated (step 8) |
| `docs/design/catalog.json` | edit | enforce the five templates; legacy lists |
| `App/tests/test_settings_technical.py` | edit | two tag constants |
| `App/tests/test_host_controls_browser.py` | edit | chip selector; stale dashboard button check |
| `App/tests/test_host_wide_geometry_browser.py` | edit | archive selector |
| `App/tests/test_guide.py` | edit | one string |
| `App/tests/test_design_settings.py` | create | shells, no styles |

No other file may change.

## 4. Steps

Run every command from `App/` unless it says otherwise.

1. Heads and chips (Anchors A to F, C). Run:

```
.venv/bin/python - <<'EOF'
import pathlib
T = pathlib.Path("app/templates")
def rep(name, old, new):
    p = T / name; s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, (name, old[:70], s.count(old)); p.write_text(s.replace(old, new), encoding="utf-8")
rep("settings.html", """{% extends "base.html" %}
{% set nav = 'settings' %}
{% block title %}{{ t('nav.settings') }}{% endblock %}
{% block content %}
{% from "_components.html" import page_header, field_label, help_tip, settings_group, settings_heading with context %}
{{ page_header(t('nav.settings'), t('settings.lede')) }}
""", """{% extends "host_page.html" %}
{% set nav = 'settings' %}
{% set body_kind = 'settings' %}
{% block title %}{{ t('nav.settings') }}{% endblock %}
{% block page_title %}{{ t('nav.settings') }}{% endblock %}
{% block meta %}{{ t('settings.lede') }}{% endblock %}
{% block body %}
{% from "_components.html" import field_label, help_tip, settings_group, settings_heading with context %}
""")
rep("settings_archived.html", """{% extends "base.html" %}
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
""", """{% extends "host_page.html" %}
{% set nav = 'settings' %}
{% set body_kind = 'list' %}
{% block title %}{{ t('archive.title') }}{% endblock %}
{% block page_title %}{{ t('archive.title') }}{% endblock %}
{% block meta %}{{ t('archive.page_lede') }}{% endblock %}
{% block back_url %}/settings{% endblock %}
{% block back_label %}{{ t('common.back') }}{% endblock %}
{% block body %}
{% from "_components.html" import help_tip, row_menu_begin, row_menu_end with context %}
""")
rep("settings_archived.html", """<div class="chips archive-type-filters" role="group" aria-label="{{ t('archive.title') }}">""",
    """<div class="ui-chips archive-type-filters" role="group" aria-label="{{ t('archive.title') }}">""")
rep("settings_archived.html", """    <a class="chip {{ 'on' if item_type == value }}" href="/settings/archived?type={{ value }}">""",
    """    <a class="ui-chip" href="/settings/archived?type={{ value }}"{% if item_type == value %} aria-current="true"{% endif %}>""")
rep("privacy_requests.html", """{% extends "base.html" %}
{% set nav = 'privacy_requests' %}
{% block title %}{{ t('privacy_requests.title') }}{% endblock %}
{% block content %}
{% from "_components.html" import page_header with context %}
{{ page_header(t('privacy_requests.title'), t('privacy_requests.lede')) }}
""", """{% extends "host_page.html" %}
{% set nav = 'privacy_requests' %}
{% set body_kind = 'list' %}
{% block title %}{{ t('privacy_requests.title') }}{% endblock %}
{% block page_title %}{{ t('privacy_requests.title') }}{% endblock %}
{% block meta %}{{ t('privacy_requests.lede') }}{% endblock %}
{% block body %}
""")
rep("guide.html", """{% extends "base.html" %}
{% set nav = 'guide' %}
{% block title %}{{ t('guide.title') }}{% endblock %}
{% block content %}
{% from "_components.html" import page_header with context %}
{{ page_header(t('guide.title'), t('guide.lede')) }}
""", """{% extends "host_page.html" %}
{% set nav = 'guide' %}
{% set body_kind = 'detail' %}
{% block title %}{{ t('guide.title') }}{% endblock %}
{% block page_title %}{{ t('guide.title') }}{% endblock %}
{% block meta %}{{ t('guide.lede') }}{% endblock %}
{% block body %}
""")
rep("onboarding.html", """{% extends "base.html" %}
{% set nav = 'dashboard' %}
{% block title %}{{ t('onboarding.welcome_title') }}{% endblock %}
{% block content %}
""", """{% extends "host_page.html" %}
{% set nav = 'dashboard' %}
{% set body_kind = 'form' %}
{% block title %}{{ t('onboarding.welcome_title') }}{% endblock %}
{% block page_title %}{% endblock %}
{% block body %}
""")
print("heads ok")
EOF
.venv/bin/python -c "from app.templating import templates; [templates.env.get_template(n) for n in ('settings.html','settings_archived.html','privacy_requests.html','guide.html','onboarding.html')]; print('compiled')"
```

   Expected: `heads ok` then `compiled`. (Each file's last line `{% endblock %}` now closes `body`. The empty `page_title` on onboarding renders no header; the welcome card has its own `h1`.)

2. Styles and classes. Run (dry-run checked at c340b7f after step 1: every count matches):

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

   Expected: `ok`. (No `host.css` rule combines `.panel` with `.guide-section`, `.guide-nav` or `.technical`, so nothing needs copying.)

3. Append to the END of `App/app/static/host2.css` (after whatever earlier briefs appended):

```
cat >> app/static/host2.css <<'EOF'

/* 0144 settings: moved inline styles */
.host-workspace .ui-prewrap { white-space: pre-wrap; }
.host-workspace .ui-center { justify-content: center; }
.host-workspace .settings-mail-preview { width: 100%; min-height: 26rem; margin-top: var(--space-2); border: 1px solid var(--line); border-radius: var(--radius-2); background: var(--surface); }
EOF
tail -4 app/static/host2.css
```

   Expected: the four lines just added. (`--surface`, `--space-2`, `--radius-2` exist in `tokens.css`.)

4. Catalog: from the repo root, run:

```
python3 - <<'EOF'
import json, sys
sys.path.insert(0, "scripts")
import design_lint as L
names = ["settings.html", "settings_archived.html", "privacy_requests.html", "guide.html", "onboarding.html"]
cat = json.loads(L.CATALOG.read_text(encoding="utf-8"))
for n in names:
    rel = f"App/app/templates/{n}"
    if rel not in cat["enforced_templates"]:
        cat["enforced_templates"].append(rel)
    cat.setdefault("legacy", {}).pop(rel, None)
    found = L._findings_template(L.ROOT / rel, (L.ROOT / rel).read_text(encoding="utf-8"), cat)
    other = [f for f in found if " T3 " not in f]
    assert not other, other
    tokens = sorted({f.rsplit(": ", 1)[1] for f in found})
    if tokens:
        cat["legacy"][rel] = tokens
    print(n, len(tokens))
L.CATALOG.write_text(json.dumps(cat, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
EOF
python3 scripts/design_lint.py 2>&1 | tail -3
```

   Expected: `settings.html 24`, `settings_archived.html 7`, `privacy_requests.html 1`, `guide.html 16`, `onboarding.html 0` (a count of plus or minus 2 is fine), then `design lint: OK`. The file is rewritten as plain indented json; that is expected.

5. Test edits. Run:

```
.venv/bin/python - <<'EOF'
import pathlib
def rep(p, old, new):
    p = pathlib.Path(p); s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, (str(p), old, s.count(old)); p.write_text(s.replace(old, new), encoding="utf-8")
rep("tests/test_settings_technical.py", """OPEN_TAG = '<details class="panel technical" id="settings-technical">'""",
    """OPEN_TAG = '<details class="ui-section technical" id="settings-technical">'""")
rep("tests/test_settings_technical.py", """PIN_PANEL = '<div class="panel" id="settings-ubyport">'""",
    """PIN_PANEL = '<div class="ui-section" id="settings-ubyport">'""")
rep("tests/test_host_controls_browser.py", """page.locator(".archive-type-filters .chip").count() == 5""",
    """page.locator(".archive-type-filters .ui-chip").count() == 5""")
rep("tests/test_host_controls_browser.py", """        for width, expected_height in ((360, 44), (390, 44), (1280, 42)):""",
    """        for width, expected_height in ((360, 44), (390, 44), (1280, 40)):""")
rep("tests/test_host_controls_browser.py", """            heights = page.locator(".action-group .btn").evaluate_all(""",
    """            heights = page.locator(".ui-ph-acts .ui-btn-primary").evaluate_all(""")
rep("tests/test_host_wide_geometry_browser.py", """    "archive": ("/settings/archived", ".panel"),""",
    """    "archive": ("/settings/archived", ".ui-section, .ui-empty"),""")
rep("tests/test_guide.py", """'<span class="pill red">'""", """'<span class="ui-badge ui-badge-action" data-tone="red">'""")
print("tests ok")
EOF
```

   Expected: `tests ok`.

6. Create `App/tests/test_design_settings.py`:

```python
"""0144: settings group pages render on host_page without inline styles."""
from __future__ import annotations

from tests.test_signed_in_chrome import host_with_property  # noqa: F401

PAGES = {"/settings": "settings", "/settings/archived": "list", "/privacy-requests": "list", "/guide": "detail"}
TEMPLATES = ("settings.html", "settings_archived.html", "privacy_requests.html", "guide.html", "onboarding.html")


def test_settings_pages_have_the_v2_shell(host_with_property):
    for path, kind in PAGES.items():
        response = host_with_property.get(f"{path}?lang=en")
        assert response.status_code == 200, path
        page = response.text
        assert page.count("<h1") == 1 and f'data-body-kind="{kind}"' in page, path
        # Scoped to <main>: base.html's shared confirm dialogs sit after </main>.
        main = page[page.index('id="main-content"'):page.index('</main>')]
        assert 'style="' not in main, path
        assert page.count('class="ui-btn ui-btn-primary') <= 1, path


def test_archive_chips_mark_the_current_type(host_with_property):
    page = host_with_property.get("/settings/archived?type=stays&lang=en").text
    assert page.count('class="ui-chip"') == 5 and page.count('aria-current="true"') >= 1


def test_templates_have_no_raw_style_or_legacy_control():
    for name in TEMPLATES:
        text = open(f"app/templates/{name}", encoding="utf-8").read()
        assert 'style="' not in text and 'class="btn' not in text and 'class="pill' not in text, name
```

   Command: `.venv/bin/python -m pytest tests/test_design_settings.py tests/test_settings_technical.py tests/test_settings_data_panel.py tests/test_guide.py tests/test_privacy_requests.py tests/test_onboarding.py tests/test_archive_stays_on_page.py tests/test_design_lint.py -q --tb=short -x 2>&1 | tail -5`. Expected: `passed`, 0 failed.

7. Browser (verified at c340b7f with steps 1 to 6 applied: all pass). Command:

```
UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_host_account_navigation.py tests/test_host_controls_browser.py tests/test_shell_lane_browser.py -q --tb=short -rs 2>&1 | tail -8
UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_host_help_browser.py tests/test_host_wide_geometry_browser.py -q --tb=short -rs 2>&1 | tail -8
```

   Run the two lines as two separate calls, each with a 600 s timeout (together about 6 to 10 minutes). Expected: 28 passed in total, 0 failed, 0 skipped. No screenshots: the orchestrator takes them.

8. Static key (last change before the commit; `host2.css` changed in step 3). Run:

```
.venv/bin/python - <<'EOF'
import pathlib, re
for p in pathlib.Path("app/templates").rglob("*.html"):
    if "archive" in p.relative_to("app/templates").parts:
        continue
    s = p.read_text(encoding="utf-8")
    n = re.sub(r'/static/host2\.css\?v=[^"]+', '/static/host2.css?v=20261019-0144', s)
    if n != s:
        p.write_text(n, encoding="utf-8"); print("bumped", p)
EOF
grep -rn "/static/host2.css?v=" app/templates | grep -v archive
.venv/bin/python tests/test_static_versions.py --write && .venv/bin/python -m pytest tests/test_static_versions.py -q 2>&1 | tail -5
```

   Expected: `bumped app/templates/base.html`, the grep shows only `?v=20261019-0144`, then `passed`.

9. Commit: from the repo root, `python3 scripts/context_lint.py 2>&1 | tail -3` (expected: OK), then `git add App/app/templates App/app/static/host2.css App/tests docs/design/catalog.json && git commit -m "0144: settings, archive, privacy requests, guide and welcome on host_page" 2>&1 | tail -3`.

## 5. Do not touch

`routes/admin.py`, `routes/settings*.py`, `_components.html` (`settings_group`, `settings_heading`, `onboarding_welcome` stay), the UbyPort PIN form fields, `host.css`, `setup_wizard/*` (0144-b); hard rules 1, 2, 3, 8.

## 6. Commands

- `python3 scripts/design_lint.py` expected: OK.
- Steps 6, 7 and 8 commands: passed, 0 failed, 0 skipped.

## 7. Acceptance

- [ ] Settings: header from `host_page`, index grid, groups and ids unchanged; technical details still fold; mail preview iframe has the same size.
- [ ] Archive: back link, v2 chips with the current type marked (`aria-current`), v2 tables.
- [ ] Privacy requests, Guide, welcome page: v2 shells, one primary at most.
- [ ] Lint OK with the five templates enforced; step 7 browser run 0 failed, 0 skipped; `host2.css` key is `20261019-0144`.

## 8. Stop and ask

Stop, and write the report, if: an excerpt is not found; a count differs; a test fails twice; you reach 25 tool calls or about 50k tokens (report as `blocked`); a file outside section 3 needs a change; section 5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0144-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps left. No screenshots needed.

## Risk list (for the reviewer)

`App/app/templates/settings.html` (UbyPort PIN panel and retention actions sit here; hard rule 1 adjacency, classes only).

## Owner steps

None.
