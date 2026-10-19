# 0142: Stay fees (list and period detail) on the v2 template

Status: todo
Depends on: 0141 | Base commit: c340b7f | Branch: claude/project-thread-5hw8cf
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

Part of [design-v2](../plans/design-v2.md). Commit each step as `0142 step k`. Never push, never open a PR. Page file: `docs/design/pages/stay-fees.md`.

## 1. Objective

Move `stay_fees.html` (list kind, no section tabs) and `stay_fee_detail.html` (detail kind, back link to the month) onto `host_page.html`, the way `reservations.html` and `reservation_detail.html` already are. The month filter partial `_list_filter.html` is made v2 by 0141 and goes into the `toolbar` block. Fee maths, the finalize form, CSV and PDF routes, QR payment block and the adjustment form keep their names and ids; only the shell and classes change. One primary per page: on the detail it is Save period (or Download PDF once the period is frozen); the scope save, the second PDF link and the adjustment save become secondary. The list has no header primary.

## 2. Context

Rules: MASTER 5 (list and detail kinds), 4 (one primary), 7.4, `docs/design/pages/stay-fees.md`. `host_page.html` blocks: `title`, `page_title`, `back_url`, `back_label`, `meta`, `primary_action`, `secondary_actions`, `tabs`, `toolbar`, `body`. Top-level `{% set nav %}`, `{% set body_kind %}`, `{% from ... import %}` and `{% macro %}` lines sit outside blocks (as in `reservation_detail.html`). `app.js` keys on `[data-filter-panel]`, `[data-month-picker]`, `[data-copy]`, `.clickable-row`, never on `.btn` or `.pill`. `stay-metrics detail-hero`, `copyrow`, `fee-*`, `mono` and `filters fee-scope-form` classes stay as legacy (they carry layout rules in `host.css`; `.fee-qr .mono` wraps the long QR string on phones). The fee list table keeps its legacy grammar (`panel tight scroll-x list-cards lc-fees fee-periods` wrapper, `table-cards`, `num`): the phone cards come from a `host.css` container query that needs `.panel.list-cards`, and `ui-table`'s own phone rules would fight it (a dry run with `ui-table ui-table-stack` broke `test_host_list_cards_browser.py`). Converting that table is a later brief. Badges follow the migrated pages: `class="ui-badge ui-badge-<kind>" data-tone="<colour>"`; the open-period badge (`waiting`) is `attention`, as the page file says.

The scripts in steps 1, 2 and 4 contain every anchor verbatim and assert each one; a failed `assert` means an anchor is stale: STOP (section 8). Anchor A is the start of `App/app/templates/stay_fees.html` (lines 1 to 9); Anchors B, C, D are `App/app/templates/stay_fee_detail.html` lines 1 to 5, 27 to 29 and 49 to 50. All are quoted inside the scripts. No earlier brief (0138 to 0141) changes these two templates.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/stay_fees.html` | edit | host_page head, toolbar block, classes |
| `App/app/templates/stay_fee_detail.html` | edit | host_page head, header actions block, classes |
| `docs/design/catalog.json` | edit | enforce both templates; legacy lists (json script) |
| `App/tests/test_stay_fee_detail.py` | edit | two primary-button asserts |
| `App/tests/test_host_fee_navigation.py` | edit | button and header selectors |
| `App/tests/test_host_wide_geometry_browser.py` | edit | fee-detail selector, fee back-link selectors |
| `App/tests/test_host_button_contrast_browser.py` | edit | small button selector |
| `App/tests/test_host_list_cards_browser.py` | edit | row action selector |
| `App/tests/test_fee_setup_compatibility.py` | edit | Set up button selector |
| `App/tests/test_design_fees.py` | create | shells, one primary |

No other file may change. No static file changes, so no `?v=` bump.

## 4. Steps

1. `stay_fees.html`. From `App/` run:

```
.venv/bin/python - <<'EOF'
import pathlib
p = pathlib.Path("app/templates/stay_fees.html"); s = p.read_text(encoding="utf-8")
OLD_HEAD = """{% extends "base.html" %}
{% set nav = 'stay_fees' %}
{% block title %}{{ t('stay_fees.title') }}{% endblock %}
{% block content %}
{% from "_components.html" import row_menu_begin, row_menu_end, list_page_header, empty_state with context %}
{#- 0099: no sub-page tabs: fee settings live per property (Settings,
    Reporting & fees); there is no one fee-settings page to link. -#}
{{ list_page_header(t('stay_fees.title')) }}
{% include "_list_filter.html" %}
"""
NEW_HEAD = """{% extends "host_page.html" %}
{% set nav = 'stay_fees' %}
{% set body_kind = 'list' %}
{% from "_components.html" import row_menu_begin, row_menu_end, empty_state with context %}
{#- 0099: no sub-page tabs: fee settings live per property (Settings,
    Reporting & fees); there is no one fee-settings page to link. -#}
{% block title %}{{ t('stay_fees.title') }}{% endblock %}
{% block page_title %}{{ t('stay_fees.title') }}{% endblock %}
{% block toolbar %}{% include "_list_filter.html" %}{% endblock %}
{% block body %}
"""
assert s.count(OLD_HEAD) == 1 and s.startswith(OLD_HEAD), "Anchor A"
s = s.replace(OLD_HEAD, NEW_HEAD)
PAIRS = [
 ('class="btn small primary"', 'class="ui-btn ui-btn-secondary ui-btn-compact"', 2),
 ('class="pill grey no-dot"', 'class="ui-badge ui-badge-neutral" data-tone="grey"', 2),
 ('class="pill green"', 'class="ui-badge ui-badge-done" data-tone="green"', 2),
 ('class="pill teal"', 'class="ui-badge ui-badge-attention" data-tone="teal"', 1),
 ('class="pill amber"', 'class="ui-badge ui-badge-action" data-tone="amber"', 1),
 ('class="pill blue"', 'class="ui-badge ui-badge-action" data-tone="blue"', 2),
 ('class="fee-list-summary small muted"', 'class="fee-list-summary ui-sub"', 1),
 ('class="small muted"', 'class="ui-sub"', 2),
]
for old, new, n in PAIRS:
    assert s.count(old) == n, (old, s.count(old)); s = s.replace(old, new)
for bad in ('class="btn', 'class="pill', 'style="', "ui-btn-primary", "small muted", "list_page_header", "block content"):
    assert bad not in s, bad
assert s.count("{% block ") == s.count("{% endblock %}") == 4
p.write_text(s, encoding="utf-8"); print("ok")
EOF
```

   Expected: `ok`. Compile: `cd App && .venv/bin/python -c "from app.templating import templates; templates.env.get_template('stay_fees.html'); print('compiled')"`. Expected: `compiled`. Commit `0142 step 1`.

2. `stay_fee_detail.html`. The `decision_form` macro stays at top level (outside any block, like `stay_jump_nav` in `reservation_detail.html`), so the body can call it. From `App/` run:

```
.venv/bin/python - <<'EOF'
import pathlib
p = pathlib.Path("app/templates/stay_fee_detail.html"); s = p.read_text(encoding="utf-8")
EDITS = [
 ("""{% extends "base.html" %}
{% set nav = 'stay_fees' %}
{% block title %}{{ apartment.internal_name }} ({{ ui_period }}){% endblock %}
{% block content %}
{% from "_components.html" import page_header, copy_button, field_label with context %}
""", """{% extends "host_page.html" %}
{% set nav = 'stay_fees' %}
{% set body_kind = 'detail' %}
{% from "_components.html" import copy_button, field_label with context %}
{# The header branches below are exclusive: Download PDF (frozen) or Save period is the one coral button. #}
{% set cta = 'ui-btn ui-btn-primary' %}
{% block title %}{{ apartment.internal_name }} ({{ ui_period }}){% endblock %}
{% block page_title %}{{ apartment.internal_name }} ({{ ui_period }}){% endblock %}
{% block back_url %}/stay-fees?month={{ month_key }}{% endblock %}
{% block back_label %}{{ t('stay_fees.back') }}{% endblock %}
{% block toolbar %}{% include "_list_filter.html" %}{% endblock %}
"""),
 ("""<a class="back-link" href="/stay-fees?month={{ month_key }}"> {{ t('stay_fees.back') }}</a>
{% include "_list_filter.html" %}
{% set actions %}
""", "{% block primary_action %}\n"),
 ("""{% endset %}
{{ page_header(apartment.internal_name ~ ' (' ~ ui_period ~ ')', '', '', '', t('nav.stay_fees'), actions) }}
""", "{% endblock %}\n{% block body %}\n"),
]
for old, new in EDITS:
    assert s.count(old) == 1, old[:60]; s = s.replace(old, new)
head, body = s.split("{% block body %}", 1)
assert head.count('class="btn accent primary"') == 2 and body.count('class="btn accent primary"') == 2
head = head.replace('class="btn accent primary"', 'class="{{ cta }}"')
body = body.replace('class="btn accent primary"', 'class="ui-btn ui-btn-secondary"')
s = head + "{% block body %}" + body
PAIRS = [
 ('class="btn primary"', 'class="ui-btn ui-btn-secondary"', 1),
 ('class="btn small"', 'class="ui-btn ui-btn-secondary ui-btn-compact"', 6),
 ('class="btn"', 'class="ui-btn ui-btn-secondary"', 5),
 ('class="pill green"', 'class="ui-badge ui-badge-done" data-tone="green"', 2),
 ('class="pill grey no-dot"', 'class="ui-badge ui-badge-neutral" data-tone="grey"', 1),
 ('class="pill amber"', 'class="ui-badge ui-badge-action" data-tone="amber"', 1),
 ('class="section-heading"', 'class="ui-section-h"', 2),
 ('class="panel tight"', 'class="ui-section"', 1),
 ('class="panel fee-blockers"', 'class="ui-section fee-blockers"', 1),
 ('class="panel"', 'class="ui-section"', 4),
 ('class="field fee-adjust-reason"', 'class="ui-field fee-adjust-reason"', 1),
 ('class="field"', 'class="ui-field"', 15),
 ('class="small muted mono"', 'class="ui-sub ui-mono mono"', 1),
 ('class="small muted fee-qr-help"', 'class="ui-sub fee-qr-help"', 1),
 ('class="small muted fee-hint"', 'class="ui-sub fee-hint"', 1),
 ('class="small muted"', 'class="ui-sub"', 3),
 ('class="warn-text small"', 'class="ui-sub warn-text"', 1),
 ('class="small warn-text"', 'class="ui-sub warn-text"', 1),
 ('class="small"', 'class="ui-sub"', 3),
 ('class="muted"', 'class="ui-sub"', 1),
]
for old, new, n in PAIRS:
    assert s.count(old) == n, (old, s.count(old)); s = s.replace(old, new)
for bad in ('class="btn', 'class="pill', 'style="', "back-link", "page_header", "block content", "{% set actions", "{{ actions"):
    assert bad not in s, bad
assert s.count("ui-btn-primary") == 1 and s.count('class="{{ cta }}"') == 2
assert s.count("{% block ") == s.count("{% endblock %}") == 7
p.write_text(s, encoding="utf-8"); print("ok")
EOF
```

   Expected: `ok`. The two `class="{{ cta }}"` sit in exclusive branches of the header (frozen: Download PDF; otherwise: Save period), so one primary renders at a time; the hidden `collected_*` inputs stay inside the finalize form. Compile: `cd App && .venv/bin/python -c "from app.templating import templates; templates.env.get_template('stay_fees.html'); templates.env.get_template('stay_fee_detail.html'); print('compiled')"`. Expected: `compiled`. Commit `0142 step 2`.

3. Catalog: json load/modify/dump keyed on names (earlier briefs edit this file too, so never edit it by line or text anchor). From the repo root run:

```
python3 - <<'EOF'
import json, pathlib, re, subprocess
cat_path = pathlib.Path("docs/design/catalog.json")
NAMES = ["App/app/templates/stay_fees.html", "App/app/templates/stay_fee_detail.html"]
data = json.loads(cat_path.read_text(encoding="utf-8"))
for name in NAMES:
    if name not in data["enforced_templates"]:
        data["enforced_templates"].append(name)
cat_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
out = subprocess.run(["python3", "scripts/design_lint.py"], capture_output=True, text=True).stdout
data = json.loads(cat_path.read_text(encoding="utf-8"))
for name in NAMES:
    short = name.rsplit("/", 1)[1]
    tokens = sorted({line.split("catalog: ", 1)[1].strip() for line in out.splitlines() if short in line and "catalog: " in line})
    data["legacy"][name] = sorted(set(data["legacy"].get(name, [])) | set(tokens))
    print(short, len(tokens), " ".join(tokens))
cat_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
EOF
```

   Expected: two lines, `stay_fees.html 14 ...` and `stay_fee_detail.html 30 ...` (a count off by one or two is fine). Then `python3 scripts/design_lint.py 2>&1 | tail -5`. Expected: `design lint: OK`. Commit `0142 step 3`.

4. Existing tests that assert on the old markup. From `App/` run:

```
.venv/bin/python - <<'EOF'
import pathlib
EDITS = {
 "tests/test_stay_fee_detail.py": [
  ('assert response.text.count("btn accent primary") == 1', """assert response.text.count('class="ui-btn ui-btn-primary"') == 1"""),
  ('assert "btn accent primary" not in response.text', """assert 'class="ui-btn ui-btn-primary"' not in response.text"""),
 ],
 "tests/test_host_fee_navigation.py": [
  ('page.locator(".host-workspace main a.btn, .host-workspace main button.btn").all()', 'page.locator(".host-workspace main a.btn, .host-workspace main button.btn, .host-workspace main a.ui-btn, .host-workspace main button.ui-btn").all()'),
  ('left = page.locator(".page-header").bounding_box()', 'left = page.locator(".ui-ph").bounding_box()'),
 ],
 "tests/test_host_wide_geometry_browser.py": [
  ('"fee-detail": ("/stay-fees/{configured_apartment}", ".stay-fee-detail, .panel"),', '"fee-detail": ("/stay-fees/{configured_apartment}", ".ui-body-detail, .ui-section"),'),
  ('header = page.locator(".page-header").bounding_box()\n                    back = page.locator("main.wrap.with-sidebar > a.back-link").bounding_box()', 'header = page.locator(".ui-ph").bounding_box()\n                    back = page.locator(".ui-ph-back").bounding_box()'),
  ('header = page.locator(".page-header").first.bounding_box()', 'header = page.locator(".page-header, .ui-ph").first.bounding_box()'),
 ],
 "tests/test_host_button_contrast_browser.py": [
  ("document.querySelectorAll('a.btn.small.primary')", "document.querySelectorAll('a.ui-btn.ui-btn-compact')"),
 ],
 "tests/test_host_list_cards_browser.py": [
  ("tbody td.row-actions a.btn, tbody td.row-actions .row-menu-trigger", "tbody td.row-actions a.btn, tbody td.row-actions a.ui-btn, tbody td.row-actions .row-menu-trigger"),
 ],
 "tests/test_fee_setup_compatibility.py": [
  ("""page.locator(f'a.btn[href^="/apartments/{unset}?view=settings"]').click()""", """page.locator(f'a.ui-btn[href^="/apartments/{unset}?view=settings"]').click()"""),
 ],
}
for name, pairs in EDITS.items():
    p = pathlib.Path(name); s = p.read_text(encoding="utf-8")
    for old, new in pairs:
        if s.count(old) == 1:
            s = s.replace(old, new)
        else:
            print("SKIPPED (not found once, already changed?):", name, old[:70])
    p.write_text(s, encoding="utf-8")
print("ok")
EOF
```

   Expected: `ok` and no `SKIPPED` line. The only allowed `SKIPPED` line is the `test_host_wide_geometry_browser.py` one for `.page-header").first` (0140 may already have changed that property settings line): then `grep -n 'ui-ph' tests/test_host_wide_geometry_browser.py | tail -3` must show line 733 using `.ui-ph`; say so in the report. Any other `SKIPPED`: STOP.

   Then create `App/tests/test_design_fees.py` with exactly:

```python
"""0142: stay fee pages render on host_page; one primary on the period detail."""
from __future__ import annotations

from tests.test_stay_fee_detail import _property, _stay, host  # noqa: F401


def test_fee_list_and_detail_have_the_v2_shells(host):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id, "Design Demo")
    _stay(apartment_id, "2026-08-10", "2026-08-14", [{}])
    listing = client.get("/stay-fees?month=2026-08&lang=en").text
    assert listing.count("<h1") == 1 and 'data-body-kind="list"' in listing
    assert 'class="ui-toolbar"' in listing and "ui-btn-primary filter-apply" in listing
    assert 'class="ui-btn ui-btn-primary"' not in listing
    detail = client.get(f"/stay-fees/{apartment_id}?month=2026-08&lang=en").text
    assert 'data-body-kind="detail"' in detail and 'class="ui-ph-back"' in detail
    assert detail.count('class="ui-btn ui-btn-primary"') == 1
    assert detail.index('class="ui-ph"') < detail.index('class="stay-metrics')


def test_templates_have_no_raw_style_or_legacy_control():
    for name in ("stay_fees.html", "stay_fee_detail.html"):
        text = open(f"app/templates/{name}", encoding="utf-8").read()
        assert 'style="' not in text and 'class="btn' not in text and 'class="pill' not in text, name
```

   Command: `cd App && .venv/bin/python -m pytest tests/test_design_fees.py tests/test_stay_fee*.py tests/test_design_lint.py -q --tb=short -x 2>&1 | tail -30`. Expected: passed (one browser test in `test_stay_fee_send_panel.py` may skip here; step 5 runs it). Commit `0142 step 4`.

5. Browser tests. The orchestrator takes the screenshots, so you attach none. From `App/`:

```
UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_host_fee_navigation.py tests/test_stay_fee_send_panel.py tests/test_host_button_contrast_browser.py tests/test_host_list_cards_browser.py tests/test_fee_setup_compatibility.py tests/test_host_filter_panels_browser.py tests/test_host_wide_geometry_browser.py tests/test_shell_lane_browser.py -q --tb=short -rs 2>&1 | tail -30
```

   Expected: passed, 0 skipped. `UBYHOST_BROWSER_EXECUTABLE` is required: the venv's Playwright expects a newer bundled browser than `/opt/pw-browsers` has, and without it every browser test errors. It takes about 11 minutes; run it in the background and wait for it (it passed 0 skipped in the reconcile dry run). Commit `0142 step 5` only if a fix was needed.

6. Commit anything left (skip if nothing is staged; never `git add` a whole folder): `git add App/app/templates/stay_fees.html App/app/templates/stay_fee_detail.html docs/design/catalog.json App/tests/test_design_fees.py App/tests/test_stay_fee_detail.py App/tests/test_host_fee_navigation.py App/tests/test_host_wide_geometry_browser.py App/tests/test_host_button_contrast_browser.py App/tests/test_host_list_cards_browser.py App/tests/test_fee_setup_compatibility.py && git commit -m "0142 step 6: stay fees list and period detail on host_page"`.

## 5. Do not touch

`routes/stay_fees.py`, fee maths, `_list_filter.html` (done in 0141), `host.css`, `host2.css`; hard rules 1, 2, 3, 8.

## 6. Commands

- `python3 scripts/design_lint.py` expected: `design lint: OK`.
- Step 4 and step 5 commands; step 5 with 0 skipped.

## 7. Acceptance

- [ ] Fees list: `data-body-kind="list"`, one `<h1>`, month toolbar (`ui-toolbar`), fee table and phone cards as before, no header primary (Apply in the collapsed filter is the only coral button).
- [ ] Period detail: `ui-ph-back` link to the month, header with Save period or Download PDF as the one primary, metrics and sections unchanged in content.
- [ ] Design lint OK with both templates enforced; step 4 and step 5 tests pass, 0 skipped. No screenshots from the executor.

## 8. Stop and ask

Stop, and write the report, if: an `assert` in a step script fails (stale anchor or count); a `SKIPPED` line other than the one allowed in step 4; a test fails twice; you reach 25 tool calls or about 50k tokens (report as `blocked`); a file outside section 3 needs a change; section 5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0142-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

`App/app/templates/stay_fee_detail.html` (finalize form inputs must stay inside the header form; the hidden `collected_*` inputs still post; `decision_form` stays top level). `App/tests/test_host_wide_geometry_browser.py` line 733 (property settings header, shared with 0140).

## Owner steps

None.
