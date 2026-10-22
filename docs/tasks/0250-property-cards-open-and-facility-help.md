# 0250: Open buttons on property cards, whole Guest links card, facility name example

Status: todo
Depends on: none | Base commit: c1ebb74 | Branch: claude/project-thread-cjz5cc
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Some hosts do not see that the property Overview cards open something, and the Guest links card only opens from its underlined title. Every card gets a bordered "Open ›" pill, the whole Guest links card opens its settings (Copy link stays its own button), and the cards are touch-safe on iPad. The "Facility name in UbyPort" help shows a full example line from a police letter with the part to type highlighted.

## 2. Context

- Owner rules: keep visible borders (no borderless look); no explanatory paragraphs on normal pages; light mode only; every changed CSS file gets a new `?v=` key (`tests/test_static_versions.py`).
- `tests/test_onboarding_wizard_browser.py` (around line 1360) requires every `.host-property-card` to have the same height (±1 px) at 360, 390 and 1280 px, and finds the guest card by `.host-property-card-static`. Keep that class name. That is why, below 640 px, the pill shows only the chevron (a 32 px bordered circle): with the word "Open" the Guest links card would wrap.
- The facility-name example is the same fictitious sample the example police letter uses (`app/ubyport_sample_pdf.py`, `SAMPLE_FACILITY_LINE1`/`LINE2`). The first line is what the host types (UBYPORT_CORE: max 35 characters).
- `test_reporting_help_0097.py` line 74 asserts `"Ubytovací zařízení:"` is in `apartment.form.ubyport.name_hint` in every language. The new wording keeps it.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/templates/_property_overview.html | edit | Open pill on 7 cards; Guest links title link stretches over the card |
| App/app/static/host.css | edit | card, pill, stretched link, touch, facility example styles |
| App/app/templates/base.html | edit | host.css `?v=` key |
| App/tests/static_versions.json | regenerate | `--write` |
| App/app/templates/_property_editor.html | edit | facility help with example |
| App/app/templates/setup_wizard/police.html | edit | facility help with example |
| App/app/host_i18n.py | edit | EN and CS name_hint, new name_example |
| App/app/host_vi_i18n.py | edit | VI name_hint, new name_example |
| App/tests/test_0250_property_cards.py | create | server-side checks |

No other file may change.

## 4. Steps

### Step 1: overview cards (`_property_overview.html`)

1a. In each of the six `<a class="host-property-card" ...>` cards (calendars, reporting, business, fee, property details, door code), insert this right before that card's closing `</a>`:

```
<span class="host-property-card-open" aria-hidden="true"><span class="host-property-card-open-text">{{ t('common.open') }}</span>{{ icon('chevron-right', 16) }}</span>
```

So for example `<small>...</small></div></a>` becomes `<small>...</small></div><span class="host-property-card-open" ...>...</span></a>`. The door-code card's `</div></a>` and the business card's `{% endif %}</div></a>` get it the same way.

1b. Replace the Guest links card (anchor: `grep -nF 'host-property-card host-property-card-static' App/app/templates/_property_overview.html`), these three lines:

```
  <div class="host-property-card host-property-card-static">{{ icon('external-link', 20) }}<div><strong><a href="{{ base_url }}?view=settings&amp;section=guests#communication">{{ t('nav.guest_links') }}</a></strong>
    <small>{{ t('wizard.guest_link.ready') }}</small></div>
    <div class="actions host-property-card-actions">{{ copy_inline('overview-guest-url', permalink, t('wizard.guest_link.copy_link')) }}</div></div>
```

with:

```
  <div class="host-property-card host-property-card-static">{{ icon('external-link', 20) }}<div><strong><a class="host-property-card-link" href="{{ base_url }}?view=settings&amp;section=guests#communication">{{ t('nav.guest_links') }}</a></strong>
    <small>{{ t('wizard.guest_link.ready') }}</small></div>
    <div class="actions host-property-card-actions">{{ copy_inline('overview-guest-url', permalink, t('wizard.guest_link.copy_link')) }}</div>
    <span class="host-property-card-open" aria-hidden="true"><span class="host-property-card-open-text">{{ t('common.open') }}</span>{{ icon('chevron-right', 16) }}</span></div>
```

Commit `0250 step 1`.

### Step 2: card CSS (`host.css`)

2a. Replace these two existing lines (anchors around line 123 and 127):

```
.host-property-card:hover { border-color: var(--border-strong); background: #fdf6f2; }
```
```
.host-property-card > span:last-child { margin-left: auto; color: var(--muted); }
```

with (put the block where the first line was; delete the second line):

```
/* 0250: every card shows a bordered Open pill; the whole card is the tap target (iPad). */
.host-property-card { position: relative; cursor: pointer; touch-action: manipulation; -webkit-tap-highlight-color: transparent; }
.host-property-card > div:not(.host-property-card-actions) { flex: 1 1 auto; min-width: 0; }
.host-property-card-open { margin-left: auto; flex: 0 0 auto; display: inline-flex; align-items: center; gap: 4px; min-height: 32px; padding: 0 10px 0 12px; border: 1px solid var(--border-strong); border-radius: 999px; font-size: 13px; font-weight: 600; color: var(--ink); background: white; }
.host-property-card-link { color: inherit; text-decoration: none; }
.host-property-card-link::after { content: ""; position: absolute; inset: 0; border-radius: inherit; }
.host-property-card-link:focus-visible { outline: none; }
.host-property-card-static:has(.host-property-card-link:focus-visible) { outline: 3px solid var(--focus-ring); outline-offset: 2px; }
@media (hover: hover) {
  .host-property-card:hover { border-color: var(--border-strong); background: #fdf6f2; }
  .host-property-card:hover .host-property-card-open { border-color: var(--ink); }
}
@media (max-width: 639px) {
  .host-property-card-open { width: 32px; padding: 0; justify-content: center; }
  .host-property-card-open-text { display: none; }
}
```

2b. Replace the line `.host-property-card-static { cursor: default; text-decoration: none; color: inherit; }` with:

```
.host-property-card-static { text-decoration: none; color: inherit; }
```

and the line `.host-property-card-static > .host-property-card-actions { margin: 0 0 0 auto; flex: 0 0 auto; }` with:

```
.host-property-card-static > .host-property-card-actions { position: relative; z-index: 1; margin: 0 0 0 auto; flex: 0 0 auto; }
.host-property-card-static > .host-property-card-open { margin-left: 0; }
```

2c. After the line `.help-tip-body a { color: var(--brand-ink); font-weight: 650; }` add:

```
.help-tip-body .facility-example { display: block; margin-top: 8px; padding: 8px; border: 1px solid var(--line); border-radius: 8px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; overflow-wrap: anywhere; }
.help-tip-body .facility-example-label { display: block; margin-bottom: 4px; font-family: inherit; font-weight: 650; }
.help-tip-body mark { background: var(--brand-soft); color: inherit; padding: 0 2px; border-radius: 3px; outline: 1px solid var(--brand); }
```

2d. In `App/app/templates/base.html` change `/static/host.css?v=20261021-0206f` to `/static/host.css?v=20261022-0250`. If `grep -rn "host.css?v=" App/app/templates` shows another template with the old key, change it there too (that file is allowed). Then from `App/`: `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5`.

Commit `0250 step 2`.

### Step 3: facility name help

3a. `_property_editor.html`: replace the line

```
        {{ text_field('uby_name', t('automation.facility_name'), apartment.uby_name, t('apartment.form.ubyport.name_hint'), false, 35) }}
```

with

```
        {%- set facility_help -%}{{ t('apartment.form.ubyport.name_hint') }} <span class="facility-example"><span class="facility-example-label">{{ t('apartment.form.ubyport.name_example') }}</span>Ubytovací zařízení: <mark>BYT Č. [2] FIKTVNÍ 1234/56 (PRAHA,</mark> PRAHA 2, FIKTVNÍ, 1234/56)</span>{%- endset %}
        {{ text_field('uby_name', t('automation.facility_name'), apartment.uby_name, facility_help, false, 35) }}
```

3b. `setup_wizard/police.html`: same change for the line

```
    {{ text_field('uby_name', t('automation.facility_name'), values.uby_name, t('apartment.form.ubyport.name_hint'), false, 35, true) }}
```

(keep `values.uby_name` and `, false, 35, true`).

3c. Strings. `host_i18n.py` EN (line ~3394) replace the value of `"apartment.form.ubyport.name_hint"` and add the next key right after it:

```
        "apartment.form.ubyport.name_hint": "From your police letter, line “Ubytovací zařízení:”. Type only the highlighted first line (max 35 characters). Never your property or listing name: the police reject reports with a different name.",
        "apartment.form.ubyport.name_example": "Example from a police letter:",
```

CS (line ~4211):

```
        "apartment.form.ubyport.name_hint": "Z dopisu od policie, řádek „Ubytovací zařízení:“. Zadejte jen zvýrazněný první řádek (nejvýše 35 znaků). Nikdy název ubytování ani inzerátu: hlášení s jiným názvem policie odmítne.",
        "apartment.form.ubyport.name_example": "Příklad z dopisu od policie:",
```

`host_vi_i18n.py` (line ~1732, 4-space indent there):

```
    "apartment.form.ubyport.name_hint": "Lấy từ thư của cảnh sát, dòng “Ubytovací zařízení:”. Chỉ nhập dòng đầu được tô sáng (tối đa 35 ký tự). Không bao giờ dùng tên chỗ ở hay tên tin đăng: cảnh sát từ chối khai báo có tên khác.",
    "apartment.form.ubyport.name_example": "Ví dụ từ thư của cảnh sát:",
```

Commit `0250 step 3`.

### Step 4: test `App/tests/test_0250_property_cards.py`

Copy the `host` fixture pattern from `tests/test_property_navigation_browser.py` lines 124-160 (imports it needs: `json, secrets, pytest, TestClient, auth, config, db, property_setup, app, login_as`; you may instead `from tests.test_property_navigation_browser import host  # noqa: F401`, which is simpler: do that). Tests:

1. `GET /apartments/{id}?view=overview&lang=en`: the overview grid has 7 `host-property-card-open` spans (door code is enabled in that fixture), each containing `Open`; the guest card contains `class="host-property-card-link"`.
2. Same with `lang=cs` contains `Otevřít`, `lang=vi` contains `Mở`.
3. `GET /apartments/{id}?view=settings&section=reporting&lang=en` contains `<mark>BYT Č. [2] FIKTVNÍ 1234/56 (PRAHA,</mark>` and `Example from a police letter:` and no `&lt;mark&gt;` (the markup is not escaped).

Commit `0250 step 4`.

## 5. Do not touch

`_host_alerts.html`, `alerts.py`, the "Setup checklist" section of `_property_overview.html` (another branch is rebuilding it), `app.js`, `host2.css`. AGENTS.md hard rules 2, 3, 6, 7, 8.

## 6. Commands

From `App/` (set the browser once: `export UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome UBYHOST_REQUIRE_BROWSER=1`):

```
.venv/bin/python -m pytest tests/test_0250_property_cards.py tests/test_reporting_help_0097.py tests/test_static_versions.py -q --tb=short -x 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_property_navigation_browser.py tests/test_onboarding_wizard_browser.py -q --tb=short -x -rs 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_design_guardrails_browser.py tests/test_host_wide_geometry_browser.py -q --tb=short -x -rs 2>&1 | tail -30
```

Expected: all pass, 0 skipped. If the guardrail test refuses the raw colours `white`/`#fdf6f2`, they were already on these lines before; report it and stop.

## 7. Acceptance

- [ ] 7 cards show an Open pill (text at ≥640 px, chevron circle below).
- [ ] Guest links card opens settings from anywhere on it; Copy link still copies.
- [ ] Facility help shows the example with the highlighted first line, EN/CS/VI.
- [ ] host.css key bumped, manifest regenerated.
- [ ] All §6 commands green, 0 skipped. (Screenshots are taken by the orchestrator.)

## 8. Stop and ask

As in TEMPLATE.md §8.

## 9. Report

`docs/tasks/0250-report.md`, as in TEMPLATE.md §9. Do not push; do not open a PR (the orchestrator does).
