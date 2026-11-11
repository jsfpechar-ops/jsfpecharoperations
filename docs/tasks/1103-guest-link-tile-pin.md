# 1103: property page "Guest link" tile, calm look and PIN next to the link

Status: review
Depends on: none | Base commit: origin/main | Branch: task/1103-guest-link-tile-pin
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (3 steps of at most 6 calls)
Brief by Sonnet 5.5, 2026-11-11. Owner Josef reported both points from a screenshot.

## 1. Objective

(a) The "Guest link" status tile on the property page looks like an alert (red tile, red pill inside) although the link is only unused. (b) The host copies the link in the tile but the PIN lives elsewhere; show the PIN in the tile and copy link and PIN together.

## 2. Context

Rules: AGENTS rule 6 (light mode), 7 (browser and geometry tests, 0 skipped, one 390 px screenshot per changed page), 9 (copy), 10 (UX gate). No new dependency. Say "property", never "apartment", in copy. Never print a real PIN; tests use fake data.

Causes in `App/app/static/app2.css` (all inside `body.v2`):
- line 3165, inside `@media (min-width:768px)`: `body.v2 nav.prop-strip .sc.is-current{background:var(--accs);border-color:var(--acc)}`. `is-current` is a scroll-spy class (`app.js` 2769-2780), not a state, yet it paints the brand red.
- line 2642: `a.sc:focus, a.sc:focus-visible, a.sc-main:focus, a.sc-main:focus-visible{outline:2px solid var(--acc)!important;outline-offset:2px;border-radius:12px;box-shadow:none}`. Plain `:focus` shows after a mouse click and, on `.sc-main` inside the tile, draws a red pill.
- line 2649: `body.v2 .prop-strip .sc small.is-problem{color:var(--bad);font-weight:600}`.

Template, `App/app/templates/_property_editor.html` line ~75 (the `{%- if permalink %}` branch of `nav.prop-strip`):
```
<div class="sc sc-link" data-strip="guest" data-state="{{ g_state }}"><a class="sc-main" href="#sec-messages"><i class="sd" aria-hidden="true"></i><b>{{ t('property_page.guest_link.title') }}</b><small{% if g_bad %} class="is-problem"{% endif %}>{% if g_bad %}{{ t(hc['guest_link'].text_key) }}{% else %}{{ t('wizard.guest_link.ready') }}{% endif %}</small></a><div class="sc-actions">{{ copy_inline('overview-guest-url', permalink, t('wizard.guest_link.copy_link')) }}</div></div>
```
The template var `pin` (string, may be empty) is already used further down in the same file (`value="{{ pin }}"`, ~line 260). `copy_inline` is in `_components.html` line 337 (hidden `<input>` plus a `data-copy` button; a newline cannot live in an input, so the combined text needs a hidden `<textarea>`, as `setup_wizard/guest_link.html` does with `wizard-guest-message`).
Message format to mirror exactly (from `wizard.guest_link.message_template`): the link, a newline, then `PIN: <pin>` (the literal `PIN:` is not translated in en or cs).

## 3. Files

| Path | Action |
|---|---|
| `App/app/static/app2.css` | edit lines 2642, 2649, 3165, add rules after 2654 |
| `App/app/templates/_property_editor.html` | edit the tile (line ~75) |
| `App/app/templates/base.html` | bump `app2.css?v=` (line 23, now `20261111-1100a`) to `20261111-1103a` |
| `App/app/host_i18n.py` | add 1 key, en and cs blocks |
| `App/app/host_vi_i18n.py` | add the same key in vi |
| `App/tests/test_0534_property_page_v2.py` | add one test |
| `App/tests/test_host_property_controls_browser.py` | add one browser test |

No other file. Find the i18n spots with `grep -n '"property_page.guest_link.copy_pin"' App/app/host_i18n.py App/app/host_vi_i18n.py` (hits at 8077 en, 8124 cs, vi 3263). Add right after each hit, same indentation:
- en: `"property_page.guest_link.copy_both": "Copy link and PIN",`
- cs: `"property_page.guest_link.copy_both": "Kopírovat odkaz a PIN",`
- vi: `"property_page.guest_link.copy_both": "Sao chép liên kết và PIN",`
Link-only button reuses the existing `wizard.guest_link.copy_link` ("Copy link"). The PIN line is `PIN <digits>`, no new key. Rule 9: no helper sentence.

## 4. Steps

### Step 1: CSS (at most 6 calls)
1. Line 2642: replace the selector list with `body.v2 nav.prop-strip a.sc:focus-visible,body.v2 nav.prop-strip a.sc-main:focus-visible` (drop both plain `:focus`), keep `outline:2px solid var(--acc)!important`, change `outline-offset:2px` to `outline-offset:-2px` (ring sits inside the tile, no nested pill). Keyboard focus stays visible.
2. Line 3165: change to `body.v2 nav.prop-strip .sc.is-current{background:var(--s);border-color:var(--ink3)}` (neutral, never the accent). If `--s` or `--ink3` is not defined (`grep -n -e '--ink3:' -e '--s:' App/app/static/app2.css | head -4`), use `#fff` and `var(--line)`.
3. After line 2649 add: `body.v2 .prop-strip .sc[data-strip="guest"] small.is-problem{color:var(--warn);font-weight:600}` (an unused link is waiting, not broken; check `--warn` exists with grep, else use `#8a5a00`).
4. After line 2654 add:
```
body.v2 .prop-strip .sc-main .sc-pin{grid-column:2;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:13px;letter-spacing:.06em;color:var(--ink2)}
body.v2 .prop-strip .sc-actions{display:flex;flex-wrap:wrap;gap:8px}
```
(`.sc-link` already has `flex-wrap:wrap`, so the actions wrap under the text on narrow tiles.) Bump `base.html` `?v=`.

### Step 2: template and i18n (at most 5 calls)
Replace the whole `<div class="sc sc-link" ...>...</div>` line (Context excerpt) with the block below (one line in the file is fine; keep the `{%- if permalink %}` and `{%- else %}` lines untouched):
```
<div class="sc sc-link" data-strip="guest" data-state="{{ g_state }}"><a class="sc-main" href="#sec-messages"><i class="sd" aria-hidden="true"></i><b>{{ t('property_page.guest_link.title') }}</b><small{% if g_bad %} class="is-problem"{% endif %}>{% if g_bad %}{{ t(hc['guest_link'].text_key) }}{% else %}{{ t('wizard.guest_link.ready') }}{% endif %}</small>{% if pin %}<small class="sc-pin" data-guest-pin>PIN {{ pin }}</small>{% endif %}</a><div class="sc-actions">
  {%- if pin %}<textarea class="sr-only" id="overview-guest-both" readonly rows="2" tabindex="-1" aria-hidden="true">{{ permalink }}
PIN: {{ pin }}</textarea><button class="btn small" type="button" data-copy="overview-guest-both" data-copy-label="{{ t('property_page.guest_link.copy_both') }}" data-copied-label="{{ t('common.copied') }}" data-guest-copy-both>{{ t('property_page.guest_link.copy_both') }}</button>{% endif -%}
  {% if pin %}<input class="sr-only" type="text" id="overview-guest-url" readonly value="{{ permalink }}" tabindex="-1" aria-hidden="true"><button class="ui-btn ui-btn-quiet ui-btn-compact" type="button" data-copy="overview-guest-url" data-copy-label="{{ t('wizard.guest_link.copy_link') }}" data-copied-label="{{ t('common.copied') }}" data-guest-copy-link>{{ t('wizard.guest_link.copy_link') }}</button>{% else %}{{ copy_inline('overview-guest-url', permalink, t('wizard.guest_link.copy_link')) }}{% endif %}</div></div>
```
Then add the three i18n keys from section 3. Check with `python3 -c "import ast,sys;[ast.parse(open(f).read()) for f in ('App/app/host_i18n.py','App/app/host_vi_i18n.py')]"`.

### Step 3: tests (at most 6 calls)
1. In `test_0534_property_page_v2.py` (imports `host` fixture; read lines 1-15 only) add:
```python
def test_guest_link_tile_shows_pin_and_both_copy_buttons(host):
    client, apartment_id = host
    db.update("apartment", apartment_id, {"permalink_pin": "123456"})
    html = _page(client, apartment_id)
    tile = html[html.index('class="sc sc-link"'):]
    tile = tile[: tile.index("</nav>")]
    assert 'data-guest-pin>PIN 123456<' in tile
    assert "data-guest-copy-both" in tile and "data-guest-copy-link" in tile
    assert 'id="overview-guest-both"' in tile and "\nPIN: 123456</textarea>" in tile
    db.update("apartment", apartment_id, {"permalink_pin": ""})
    html = _page(client, apartment_id)
    tile = html[html.index('class="sc sc-link"'):]
    tile = tile[: tile.index("</nav>")]
    assert "data-guest-pin" not in tile and "data-guest-copy-both" not in tile
    assert 'id="overview-guest-url"' in tile
```
(If the empty PIN makes the page auto-create one, `admin.py` line 155 does that on GET; then in the second half assert only the first half and delete the second half; report which you did.)
2. In `test_host_property_controls_browser.py` follow its existing server fixture (grep `^def test_` and read one test, at most 60 lines) and add one test: at widths 390, 768, 1280 open the property page with a PIN set to the fake `123456`, then assert (a) `document.documentElement.scrollWidth <= innerWidth`; (b) every `.sc-link` child's `getBoundingClientRect().right <= .sc-link right + 1`; (c) after `locator('.sc-link .sc-main').click()` the computed `outlineStyle` of `.sc-main` is `none` (no red ring after a mouse click); (d) `.sc-link` computed `backgroundColor` is not the accent tint: add class `is-current` through `evaluate`, then assert `getComputedStyle(...).borderTopColor` differs from `getComputedStyle(document.documentElement).getPropertyValue('--acc')`-resolved colour (resolve via a temporary element, or simply assert it equals the border of a sibling `.sc` without the class).
3. Existing tests mentioning `prop-strip` or `sc` (`test_0251_tablet_browser.py`, `test_0284_states_browser.py`, `test_0534_property_page_v2.py`) assert on `a.sc` only; none asserts `is-current` colours or `sc-main` focus (grep found no hit), so no update is expected. If one fails, report it, do not weaken it.

## 5. Tests (run from `App/`, each ends with `| tail -30`)

```
.venv/bin/python -m pytest tests/test_0534_property_page_v2.py -q --tb=short -x 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_host_property_controls_browser.py tests/test_host_geometry.py tests/test_layout_lint_browser.py tests/test_design_guardrails_browser.py tests/test_0251_tablet_browser.py tests/test_0284_states_browser.py -q --tb=short -x -rs 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_host_i18n*.py tests/test_privacy_first.py -q --tb=short -x 2>&1 | tail -30
```
Browser files must report 0 skipped (`-rs` lists skips; any skip means fail, report it). Do not run the full suite (test-map: host pages, host templates and host CSS rows).

## 6. UX gate (AGENTS rule 10, you do it, never ask the owner)

For `/apartments/<id>` (one property with a PIN) take screenshots at 390, 768 and 1280 px and open them. In the PR write per width what you saw: tile neutral (white, grey border, no red), no nested pill after a click, `PIN` line readable, buttons wrap under the text without overflow, three-column strip intact. Also one screenshot with the tile scrolled to the current section (`is-current`). Tick the [design-system checklist](../design/design-system.md) in the PR body. Never silence a finding; if `test_layout_lint_browser.py` flags the new buttons (44 px target), fix it, then rerun.

## 7. Done when

- Tests in section 5 green, 0 skipped; screenshots attached; PR is a draft until the UX notes are written; merge only with `scripts/merge-pr-on-green.sh`, never push to `main`.
- Report: files changed, test tail lines, the three screenshot descriptions. Add nothing to status, decisions or known-issues (the orchestrator does that).
- Out of scope: the Guest links section, the setup wizard, stay-level copy buttons.
