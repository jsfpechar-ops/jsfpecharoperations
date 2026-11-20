# 1866: billing banner unstyled on v2 host pages (big red block under the text)

Status: review
Depends on: none | Base commit: 216a087779fceb0839db64440fd338c5dfbd72b6 | Branch: task/1866-billing-banner-v2
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

On v2 host pages (`{% set v2 = true %}`) the billing banner (`_billing_banner.html`, included from
`base.html:85`) renders with no box at all: the text floats on the page background and the
"Pay the invoice" link renders as a large red `.btn` block below the text, overlapping the
preview bar (screenshot from the owner, admin previewing a workspace with an overdue invoice,
1232 px wide). v2 pages do not load `app.css`, where `.banner` is styled; only `app2.css` loads.
Fix: give the top-of-page `.banner` family v2 styles in `app2.css`, mirroring the 0993
impersonation-bar precedent, and bump the `app2.css` cache key.

## 2. Context

Rules that apply: AGENTS.md rules 7 (template/CSS change: browser + geometry tests for the
changed pages, 0 skipped, one 390 px screenshot per changed page in the report) and 10 (UX
gate: `test_layout_lint_browser.py` green, 390/768/1280 screenshots of each touched page opened
and described in the PR, design-system checklist ticked). Design: `docs/design/MASTER.md:90`
("banners use attention amber or neutral grey", coral never a full-width banner) and
`MASTER.md:256` (`banner(kind, text, action)`: attention or neutral only, full lane, radius 12,
one secondary action).

Verbatim excerpts (if any is not found verbatim, STOP, §8):

`App/app/templates/base.html:21-24`:
```
  {% if v2 | default(false) %}
  <link rel="stylesheet" data-turbo-track="reload" href="/static/tokens.css?v=20261120-host-palette-1865bb">
  <link rel="stylesheet" data-turbo-track="reload" href="/static/app2.css?v=20261120-host-palette-1865b">
  {% if show_nav | default(true) %}<link rel="stylesheet" data-turbo-track="reload" href="/static/command.css?v=20261103-0935">{% endif %}
```
(`app.css` is loaded only in the `{% else %}` branch, so on v2 pages `.banner` has no styles.)

`App/app/templates/base.html:85`:
```
    {% include "_billing_banner.html" %}
```

`App/app/templates/_billing_banner.html` (whole file):
```
{% set billing_line = billing_banner(workspace_user.id if workspace_user else None) %}
{% if billing_line %}
<aside class="banner {{ 'warning' if billing_line.warning }} billing-banner" role="status" data-billing-banner="{{ billing_line.kind }}">
  <div class="grow"><strong>{{ t('billing.banner.' ~ billing_line.kind, date=billing_line.date) }}</strong></div>
  <a class="btn small" href="/predplatne">{{ t('billing.banner.action_' ~ billing_line.kind) }}</a>
</aside>
{% endif %}
```

`App/app/static/app.css:458-468` (the styles v2 pages never get):
```
.banner {
  border-radius: var(--radius);
  padding: 14px 16px;
  margin-bottom: 14px;
  border: 1px solid transparent;
  display: flex;
  gap: 14px;
  align-items: flex-start;
  font-size: 14.5px;
}
.banner .grow { flex: 1; min-width: 0; }
```
and `app.css:489`: `.banner.warning { background: var(--warn-soft); border-color: color-mix(in srgb, var(--warn) 25%, transparent); color: var(--warn); }`

`App/app/static/app2.css:2984-2990` (the 0993 precedent — v2 rules for a base.html banner, since
"v2 pages do not load app.css"):
```
/* 0993: preview banner, v2 pages do not load app.css */
body.v2 .impersonation-bar{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:12px 16px;margin:0 0 20px;padding:12px 16px;border:1px solid var(--line);border-radius:12px;background:var(--s)}
body.v2 .impersonation-copy{flex:1 1 240px;min-width:0;display:flex;flex-wrap:wrap;align-items:baseline;gap:2px 10px;font-size:14px}
body.v2 .impersonation-eyebrow{font-size:12px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:var(--acc-text)}
body.v2 .impersonation-handle{font-size:13px;color:var(--ink3)}
body.v2 .impersonation-bar form{margin:0;flex:0 0 auto}
body.v2 .impersonation-bar .btn{white-space:nowrap}
```

`App/app/static/app2.css:2` tokens: `--s:#fff;--line:#ebebe7;--warns:#fff4d6;--warn:#8a5200;--bads:#fdecea;--bad:#b42318;--oks:#e6f5ec;--ok:#167044;--info:#eaf3fb`
`App/app/static/app2.css:1813-1814`: `body.v2 .ui-banner{padding:12px 16px;border-radius:10px;border:1px solid var(--line);background:var(--s);color:var(--ink);font-size:15px;line-height:1.5}` and `body.v2 .ui-banner-attention{background:var(--warns);border-color:var(--warn)}`

`App/app/static/app2.css:2820` (why the new rules must exclude it):
`body.v2 .section-notice{margin:0 0 var(--space-4);padding:14px 16px;min-height:44px;...display:flex;align-items:flex-start;gap:10px;border-left-width:4px}`
— `.section-notice` also carries the `.banner` class (`_section_notice.html`, `_property_editor.html:512-513`) and already has its own v2 styling (0955), so the new generic rule uses `:not(.section-notice)`.

The only other v2 `.banner` use is `base.html:75`: `<aside class="banner warning workspace-deletion-banner" ...>` — same bug, same fix.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/static/app2.css` | edit | add the v2 `.banner` block after line 2990 (exact diff in §4) |
| `App/app/templates/base.html` | edit | bump the `app2.css` `?v=` key on line 23 (exact diff in §4) |
| `App/tests/static_versions.json` | regenerate | `tests/test_static_versions.py --write` after the two edits above |
| `App/tests/test_0414_billing_banner_browser.py` | edit | add layout assertions to the existing test (exact diff in §4) |
| `docs/tasks/screenshots-1866/` | new | 390/768/1280 px screenshots of the dashboard banner |

No other file may change.

## 4. Steps

1. In `App/app/static/app2.css`, insert immediately after the line
   `body.v2 .impersonation-bar .btn{white-space:nowrap}` (line 2990) and before the
   `/* 0993: dashboard calendar legend and bar tooltips */` comment:

```css
/* 1866: top-of-page banners on v2 pages; v2 pages do not load app.css, where .banner is styled (same 0993 gap as the preview bar). .section-notice keeps its own 0955 styling. */
body.v2 .banner:not(.section-notice){display:flex;flex-wrap:wrap;align-items:center;gap:12px 16px;margin:0 0 20px;padding:12px 16px;border:1px solid var(--line);border-radius:12px;background:var(--s);color:var(--ink);font-size:15px;line-height:1.5}
body.v2 .banner:not(.section-notice) .grow{flex:1 1 240px;min-width:0}
body.v2 .banner:not(.section-notice) .btn{white-space:nowrap}
body.v2 .banner.warning:not(.section-notice){background:var(--warns);border-color:var(--warn)}
body.v2 .banner.err:not(.section-notice),body.v2 .banner.critical:not(.section-notice){background:var(--bads);border-color:var(--bad)}
body.v2 .banner.ok:not(.section-notice){background:var(--oks);border-color:var(--ok)}
body.v2 .banner.info:not(.section-notice){background:var(--info);border-color:var(--line)}
```

2. In `App/app/templates/base.html` line 23, change
   `href="/static/app2.css?v=20261120-host-palette-1865b"` to
   `href="/static/app2.css?v=20261120-host-palette-1866a"` (that string appears exactly once).

3. From `App/`: `.venv/bin/python tests/test_static_versions.py --write` and verify
   `git diff App/tests/static_versions.json` shows only the `app2.css` entry changed.

4. In `App/tests/test_0414_billing_banner_browser.py`, inside the `for width in (390, 1280):`
   loop, right after the line
   `assert line.locator('a[href="/predplatne"]').count() == 1, width` add:

```python
                bb = line.bounding_box()
                btnb = line.locator('a[href="/predplatne"]').bounding_box()
                assert bb and btnb, width
                assert btnb["x"] >= bb["x"] - 1 and btnb["y"] >= bb["y"] - 1, width
                assert btnb["x"] + btnb["width"] <= bb["x"] + bb["width"] + 1, width
                assert btnb["y"] + btnb["height"] <= bb["y"] + bb["height"] + 1, width
                cs = page.evaluate("getComputedStyle(document.querySelector('[data-billing-banner]'))")
                assert cs["display"] == "flex", width
                assert cs["backgroundColor"] not in ("rgba(0, 0, 0, 0)", "transparent"), width
```

   (Before the fix, on the v2 dashboard, `display` is `block` and `backgroundColor` is
   transparent and the button sits outside/below the text — this is the regression test.)

5. Run the §6 commands; capture screenshots: with `UBYHOST_CAPTURE_0414=1` the existing test
   already writes `docs/tasks/screenshots-0414/dashboard-390.png`; copy the run into
   `docs/tasks/screenshots-1866/` and additionally capture 768 and 1280 px shots of the
   dashboard with `data-billing-banner="trial"` visible (same harness, `open_page(..., width=w)`).

## 5. Do not touch

- Anything under `App/app/static/app.css`, `host2.css`, `tokens.css` (non-v2 pages are fine).
- `_section_notice.html`, `_property_editor.html`, `_billing_banner.html` markup, i18n.
- AGENTS.md hard rules: never push to `main`; no new dependency; SQL untouched; light mode only.

## 6. Commands

From `App/`, each ending `2>&1 | tail -30`:

- `.venv/bin/python -m pytest tests/test_0414_billing_banner_browser.py tests/test_static_versions.py -q --tb=short -x`
- `.venv/bin/python -m pytest tests/test_billing_*.py -q --tb=short -x`
- `.venv/bin/python -m pytest tests/test_host_geometry.py -q --tb=short` (0 skipped)
- `.venv/bin/python -m pytest tests/test_design_guardrails_browser.py tests/test_0710_v2_mockup_match_browser.py -q --tb=short` (0 skipped; browser tests need playwright, as in CI)
- UX gate: `.venv/bin/python -m pytest tests/test_layout_lint_browser.py -q --tb=short` (0 skipped)
- From repo root: `python3 scripts/context_lint.py`

## 7. Acceptance

- [ ] `test_0414_billing_banner_browser.py` passes at 390 and 1280 with the new assertions (button inside the banner box, `display:flex`, non-transparent background).
- [ ] `test_static_versions.py` green; `static_versions.json` committed.
- [ ] 390 px screenshot per changed page in `docs/tasks/screenshots-1866/` (dashboard with the banner), plus 768/1280; open them and describe what you see in the PR.
- [ ] No horizontal scroll at 390 (already asserted in the test).
- [ ] `test_layout_lint_browser.py` green; design-system checklist (`docs/design/design-system.md`) ticked in the PR description.

## 8. Stop and ask

Stop and write the report if: an excerpt is not found verbatim; a §6 test fails twice; the
`:not(.section-notice)` selector misbehaves in any tested browser; a file outside §3 needs a
change; you need push/merge/deploy (hand to the owner).

## 9. Report

Write `docs/tasks/1866-report.md` (≤600 tokens), set `Status: review` in this file, open one PR
from `task/1866-billing-banner-v2`. Report: `git diff --stat`, last 5 lines of each §6 command,
§7 ticked, deviations, and the screenshot observations per width.

## Risk list (for the reviewer)

- `App/app/static/app2.css` (new selector block — check it does not leak into `.section-notice`)
- `App/app/templates/base.html` (one cache-key string)
- `App/tests/test_0414_billing_banner_browser.py` (new assertions)

## Owner steps

1. Wait for the PR from `task/1866-billing-banner-v2` to go green.
2. Merge with `scripts/merge-pr-on-green.sh` (green merges auto-deploy).
3. In a staging admin session, preview a workspace with an overdue invoice at 1280 and 390 px
   and confirm the amber banner with the pill button on the right (or full-width row on phone).
