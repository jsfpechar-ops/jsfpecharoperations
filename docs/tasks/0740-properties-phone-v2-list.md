# 0740 brief: phone v2 properties list (Airbnb listings style)

Status: review (test follow-ups moved to 0741 step 0)
Executor: Haiku 5.5, alone, on branch `claude/project-thread-b9cg54` in `/home/claude/jsfpecharoperations` (already checked out; do not switch branches, do not push).

## 1. Objective

Below 1024 px, `/apartments` looks like screen `nemovitosti` of `docs/design/mockup/ubyhost-phone-v2.html`:
title "Properties" left with a round soft "+" button right (same row), then one compact card per property:
64 px coloured initials tile, name, address, ONE status line ("Ready for guests" in green, or "Missing: Police, Calendar"
in coral, listing the chips whose state is `bad`), chevron. No 132 px cover, no four chips, no subtitle line on phone.
Desktop (>= 1024 px) must not change at all.

## 2. Context

- Design: `docs/design/mockup/ubyhost-phone-v2.html` (read its `/* properties list (0740)` CSS block and the `data-s="nemovitosti"` section; do not edit it).
- Template: `App/app/templates/apartments.html` (`.props-top`, `.props-head`, `.props-phone`). CSS: `App/app/static/app2.css` lines ~306-313 (`0533` phone card rules and `.cover.c0-2`).
- `.ph-hide` hides below 1024 px; `.ph-only` (app2.css ~line 408) shows only below 1024 px. Check both with grep before use.
- Standing rule for tests: you may change assertions that only check the phone property cards below 1024 px (cover height, chips inside `.props-phone`, `.props-top`) in `App/tests/test_0281_card_borders_browser.py`, `test_host_list_cards_browser.py`, `test_design_guardrails_browser.py`, `test_host_wide_geometry_browser.py` and the `properties` entry of `App/tests/v2_mockup.py`. Change no desktop assertion and no other test; if another test fails, stop and write it in the report.

## 3. Files

`App/app/templates/apartments.html`, i18n files, `App/app/static/app2.css`, `base.html`, `static_versions.json`, `v2_mockup.py`, `catalog.json`, the tests in section 2.

## 4. Steps

1. `apartments.html`:
   a. Delete the line `<div class="top props-top">…</div>`.
   b. In `.head.props-head`: add `ph-hide` to the `<p class="sub">`; after the existing desktop `<a class="btn" href="/apartments/new">` add
      `<a class="round props-add ph-only" href="/apartments/new" aria-label="{{ t('apartments.add') }}">{{ icon('plus', 22) }}</a>`.
   c. Replace the body of the `.props-phone` loop card with:
      ```jinja
  {% set missing = row.chips | selectattr('state', 'equalto', 'bad') | list %}
  <a class="card prop" href="/apartments/{{ apartment.id }}">
    <span class="cover c{{ apartment.id % 3 }}"><span class="ini">{{ initials }}</span></span>
    <span class="in"><b>{{ apartment.internal_name }}</b>{% if address_text %}<small>{{ address_text }}</small>{% endif %}
      {% if missing %}<span class="st r">{{ t('apartments.phone.missing', items=missing | map(attribute='key') | map('prefix_chip') | join(', ')) }}</span>{% else %}<span class="st g">{{ t('apartments.phone.ready') }}</span>{% endif %}</span>
    {{ icon('chevron-right', 20, 'chev') }}
  </a>
      ```
      There is no `prefix_chip` filter: build the list with a small loop instead, e.g.
      `{% set names = [] %}{% for c in missing %}{% set _ = names.append(t('apartments.chip.' ~ c.key)) %}{% endfor %}` and pass `items=names | join(', ')`.
      Check `sed -n 1,8p App/app/templates/_icons.html` for the icon macro argument order and how `t()` passes keyword values (`grep -n "def t\b\|def t(" -r App/app | head`).
2. i18n (keep key order next to `apartments.chip.*`):
   - `App/app/host_i18n.py` English: `"apartments.phone.ready": "Ready for guests",` `"apartments.phone.missing": "Missing: {items}",`
   - Czech: `"apartments.phone.ready": "Připraveno pro hosty",` `"apartments.phone.missing": "Chybí: {items}",`
   - `App/app/host_vi_i18n.py`: `"apartments.phone.ready": "Sẵn sàng đón khách",` `"apartments.phone.missing": "Thiếu: {items}",`
   Use the placeholder syntax the file already uses for other keys (grep one key with a placeholder first).
3. `app2.css`: replace the 0533 phone rule line (`@media (max-width:1023px){body.v2 .props-card{display:none}body.v2 .props-phone .prop{…}…}`) with the following, and in the `@media (min-width:1024px)` line after it delete `body.v2 .props-top{display:none}`:
   ```css
/* 0740: phone v2 properties list; values from docs/design/mockup/ubyhost-phone-v2.html, screen nemovitosti */
@media (max-width:1023px){
  body.v2 .props-card{display:none}
  body.v2 .props-head{display:flex;align-items:center;justify-content:space-between;margin:6px 0 24px}
  body.v2 .props-head h1{font-size:30px;font-weight:800;letter-spacing:-.02em;line-height:1.15;margin:0}
  body.v2 .props-add{width:44px;height:44px;border-radius:50%;background:#f4f3ef;color:var(--ink);display:grid;place-items:center;flex:none}
  body.v2 .props-phone .card.prop{display:flex;align-items:center;gap:16px;padding:16px;margin:0 0 14px;color:inherit;text-decoration:none}
  body.v2 .props-phone .cover{width:64px;height:64px;border-radius:16px;display:grid;place-items:center;color:#fff;flex:none}
  body.v2 .props-phone .cover .ini{font-size:22px;font-weight:800;letter-spacing:-.02em;line-height:1}
  body.v2 .props-phone .in{flex:1;min-width:0;display:flex;flex-direction:column;align-items:flex-start}
  body.v2 .props-phone .in b{font-size:17px;font-weight:700;line-height:1.3;max-width:100%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  body.v2 .props-phone .in small{color:var(--ink3);font-size:14px;max-width:100%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  body.v2 .props-phone .st{display:inline-flex;align-items:center;gap:6px;font-size:13px;font-weight:700;margin-top:6px;line-height:1.3;padding:0;background:none;min-height:0}
  body.v2 .props-phone .st:before{content:"";width:7px;height:7px;border-radius:50%;background:currentColor;flex:none}
  body.v2 .props-phone .st.g{color:var(--ok)}
  body.v2 .props-phone .st.r{color:var(--acc-text)}
  body.v2 .props-phone .chev{width:20px;height:20px;color:var(--ink3);flex:none}
}
   ```
   Keep the `.cover.c0/.c1/.c2` gradient lines. Then `grep -n "props-top\|props-phone .setup" App/app App/tests -r` must print nothing (except a test you update under the standing rule).
   If a shared `.st` / `.card` rule elsewhere wins over these (check computed styles in the 0710 failure output), raise specificity with `body.v2 .props-phone .card.prop .st…`, never `!important`.
4. New classes (`props-add`, `chev` if absent) go in `docs/design/catalog.json` like existing entries; run `python3 scripts/design_lint.py 2>&1 | tail -5` from the repo root.
5. Cache key: set the app2.css `?v=` in `App/app/templates/base.html` to `20261102-0740`, then from `App/`: `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5`.
6. `App/tests/v2_mockup.py`, `properties` entry: add `"phone_mockup": PHONE_MOCKUP_V2,`; set `"phone_selectors"` to
   `[".tabs", ".tab.on", ".big, .head h1", ".props-add", ".card.prop", ".cover", ".cover .ini", ".prop .in b", ".prop .in small", ".card.prop .st.g", ".card.prop .st.r", ".card.prop .chev"]`;
   `"missing_ok"`: keep `.prop .in small`, add `".card.prop .st.g": "tone depends on the demo property's setup"` and the same for `.st.r`; `"phone_box_skip"`: keep `.st.g`/`.st.r` width and `.cover .ini` width; drop the `.card.prop` height skip unless the test needs it.
7. Tests (from `App/`; do NOT reinstall playwright, the venv pins 1.63.0 to match /opt/pw-browsers):
   `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -k "properties" -q --tb=short -x 2>&1 | tail -30`
   Box failures that follow text length get a `"selector@width"` BOX_OVERRIDES entry with the app value under `# text-dependent: app copy vs phone v2 mockup demo copy (0740)`. Style failures mean the CSS is wrong: fix the CSS, never override a style.
   Then: `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0530_properties_chips.py tests/test_properties_table_chips.py tests/test_0250_property_cards.py tests/test_0281_card_borders_browser.py tests/test_host_list_cards_browser.py tests/test_design_guardrails_browser.py tests/test_host_wide_geometry_browser.py tests/test_static_versions.py tests/test_privacy_first.py -q --tb=short 2>&1 | tail -30` (0 skipped).
   And from the repo root: `python3 scripts/context_lint.py 2>&1 | tail -5`.
8. Commit (do not push): message `0740: phone v2 properties list (Airbnb style)` ending with
   ```
   Co-Authored-By: Claude Haiku 5.5 <noreply@anthropic.com>
   ```

## 5. Do not touch

Desktop (>= 1024 px) rules and markup, `docs/design/mockup/`.

## 6. Commands

The test commands in step 7, from `App/`.

## 7. Acceptance

Step 7 commands pass with 0 skipped.

## 8. Stop and ask

A test outside the standing rule fails.

## 9. Report

`docs/tasks/0740-report.md`: changed files, command tails, overrides added, deviations. Commit it with the work.
