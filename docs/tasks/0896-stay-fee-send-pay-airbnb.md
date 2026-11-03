# 0896: Airbnb look for Stay fees step 2 "Send the PDF and pay"

Status: review
Depends on: none | Base commit: c6c53b35 | Branch: the current checkout (do not switch or create branches) | Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

On `/stay-fees`, step 2 of each property card (`section.card.fee-pay`, `data-fee-step="2"`) gets the Airbnb look: 16 px card padding, content at most 960 px wide, tasks 1 and 2 as list rows (number, 16 px bold label, quiet button right), ONE QR card as step 3, account and VS never wrapping, only "Open datová schránka" red. Visual only; every link, `download`, `data-copy` and `id` stays.

## 2. Context

- Owner override of executor.md: **do not commit, push or open a PR.** Leave changes in the working tree; the orchestrator commits. `copy_inline` (`_components.html:326`) takes no class; it renders `<input class="sr-only">` + `<button class="btn small" data-copy>`. Do NOT edit it; the CSS below styles it. `.btn.line` exists only in app2.css's phone block (~266), so step 4 adds it for desktop. Under 1023 px `body.v2 .btn` is full-width 50 px red with forced white text (~261, ~265): the Copy selector is deliberately more specific. Phone gutter is 20 px, so the QR card is flat under 1024 px.

## 3. Files

| Path | Action |
|---|---|
| `App/app/templates/stay_fees.html` | edit, step-2 block only (lines 96 to 126) |
| `App/app/static/app2.css` | edit, `/* 0794 stay fees v2 */` block only |
| `App/app/templates/base.html` | edit line 21, app2.css key |
| `App/tests/test_0896_fee_pay_geometry_browser.py` | create |
| `App/tests/static_versions.json` | regenerate with `--write`, never by hand |
| `App/tests/_scratch_fee.py` (delete), `docs/tasks/screenshots-0896/` (390 and 1280 PNGs) | other |

## 4. Steps

1. `rm App/tests/_scratch_fee.py`.
2. `stay_fees.html` (read lines 94 to 128 first; four Edits):
   a. `class="btn ghost" href="{{ pdf_url }}"` becomes `class="btn line" href="{{ pdf_url }}"`.
   b. Delete the empty third task: the 6 lines from `        {% if period.pay_total_czk != 0 %}` (line ~106) to the next `        {% endif %}`, which wrap `<strong>{{ t('stay_fees.pay.task_pay') }}</strong>`.
   c. Directly above `        <img src="{{ period.pay.qr }}"` insert:
      `        <h4 class="fee-qr-title"><span class="fee-qr-n" aria-hidden="true">3</span>{{ t('stay_fees.pay.task_pay') }}</h4>`
   d. In the two `<dd>` lines wrap the value only: `<dd>{{ period.pay.account or period.pay.iban_display }}{{ copy_inline(` becomes `<dd><span class="fee-qr-val">{{ period.pay.account or period.pay.iban_display }}</span>{{ copy_inline(`, and `<dd>{{ period.pay.vs }}{{ copy_inline(` becomes `<dd><span class="fee-qr-val">{{ period.pay.vs }}</span>{{ copy_inline(`.
   Command: `grep -c 'fee-qr-val\|class="btn line"\|fee-qr-title\|task_pay' App/app/templates/stay_fees.html | tail -3`. Expected: `4`.
3. `app2.css`: in the line `body.v2 .stay-fees-page .fee-stepper-item[data-state="current"] .fee-stepper-dot{...}` replace `color:var(--acc-text)}` with `color:#fff;font-size:14px;font-weight:700}` (the current dot was red on red).
4. `app2.css`: read lines 1110 to 1140. Replace the 20 lines from `body.v2 .stay-fees-page .fee-send-pay{display:grid;grid-template-columns:minmax(0,1fr) 260px;` through the `}` that closes `@media (max-width:1023px){` (right after the line `  body.v2 .stay-fees-page .fee-tasks .btn,body.v2 .stay-fees-page .fee-step-actions .btn{display:flex;justify-content:center;width:100%}`) with exactly:
```css
body.v2 .stay-fees-page .card.fee-pay{padding:16px}
body.v2 .stay-fees-page .fee-send-pay{display:grid;grid-template-columns:minmax(0,1fr) 320px;gap:24px;align-items:start;max-width:960px}
body.v2 .stay-fees-page .fee-tasks{margin:0;padding:0;list-style:none;counter-reset:fee-task;display:grid;gap:12px}
body.v2 .stay-fees-page .fee-tasks li{counter-increment:fee-task;display:grid;grid-template-columns:28px minmax(0,1fr) auto;align-items:center;gap:12px;min-width:0;min-height:44px;padding-top:12px;border-top:1px solid var(--line)}
body.v2 .stay-fees-page .fee-tasks li:first-child{padding-top:0;border-top:0}
body.v2 .stay-fees-page .fee-tasks li::before{content:counter(fee-task);width:28px;height:28px;border-radius:50%;background:var(--accs);color:var(--acc-text);display:grid;place-items:center;font-weight:700;font-size:14px}
body.v2 .stay-fees-page .fee-qr-n{flex:none;width:28px;height:28px;border-radius:50%;background:var(--accs);color:var(--acc-text);display:inline-grid;place-items:center;font-weight:700;font-size:14px}
body.v2 .stay-fees-page .fee-tasks strong{min-width:0;font-size:16px;font-weight:700;line-height:1.35}
body.v2 .stay-fees-page .fee-send-pay .btn{display:inline-flex;align-items:center;justify-content:center;min-height:44px;padding:0 18px;border-radius:12px;font-size:15px;font-weight:600;box-sizing:border-box;white-space:nowrap}
body.v2 .stay-fees-page .fee-send-pay .btn.line{background:#fff;color:var(--ink);border:1px solid var(--ink)}
body.v2 .stay-fees-page .fee-qr-panel{min-width:0;display:grid;gap:12px;justify-items:center;padding:16px;border:1px solid var(--line);border-radius:16px;background:#fff}
body.v2 .stay-fees-page .fee-qr-panel p,body.v2 .stay-fees-page .fee-qr-panel p.sub{margin:0;font-size:14px}
body.v2 .stay-fees-page .fee-qr-title{justify-self:stretch;display:flex;align-items:center;gap:12px;margin:0;font-size:16px;font-weight:700}
body.v2 .stay-fees-page .fee-qr-panel img{display:block;width:176px;max-width:100%;height:auto;border-radius:12px}
body.v2 .stay-fees-page .fee-qr-panel .fee-qr-amount{font-size:22px;font-weight:700;font-variant-numeric:tabular-nums}
body.v2 .stay-fees-page .fee-qr-meta{justify-self:stretch;margin:0;display:grid;gap:12px}
body.v2 .stay-fees-page .fee-qr-meta div{display:grid;grid-template-columns:minmax(0,1fr) auto;column-gap:12px;row-gap:4px;align-items:center;min-width:0;padding-top:12px;border-top:1px solid var(--line)}
body.v2 .stay-fees-page .fee-qr-meta dt{grid-column:1;grid-row:1;color:var(--ink3);font-size:14px}
body.v2 .stay-fees-page .fee-qr-meta dd{display:contents}
body.v2 .stay-fees-page .fee-qr-val{grid-column:1;grid-row:2;min-width:0;font-size:16px;font-weight:600;white-space:nowrap;font-variant-numeric:tabular-nums}
body.v2 .stay-fees-page .fee-qr-meta .btn.small[data-copy]{grid-column:2;grid-row:1 / span 2;width:auto;min-width:44px;min-height:44px;padding:0 14px;border-radius:12px;background:#fff;color:var(--ink);border:1px solid var(--ink3);font-size:14px;font-weight:600}
@media (min-width:1024px) and (max-width:1279px){body.v2 .stay-fees-page .fee-tasks li{grid-template-columns:28px minmax(0,1fr)}body.v2 .stay-fees-page .fee-tasks li .btn{grid-column:2;justify-self:start}}
@media (max-width:1023px){
  body.v2 .stay-fees-page .fee-send-pay{grid-template-columns:minmax(0,1fr)}body.v2 .stay-fees-page .fee-qr-panel{order:-1;padding:0;border:0;border-radius:0}body.v2 .stay-fees-page .fee-qr-n{display:none}
  body.v2 .stay-fees-page .fee-tasks li{grid-template-columns:28px minmax(0,1fr)}body.v2 .stay-fees-page .fee-tasks li .btn{grid-column:1 / -1;min-height:50px;font-size:16px}
  body.v2 .stay-fees-page .fee-tasks .btn,body.v2 .stay-fees-page .fee-step-actions .btn{display:flex;justify-content:center;width:100%}
}
@media (max-width:400px){body.v2 .stay-fees-page .fee-qr-val{font-size:15px}}
```
   Command: `grep -c "fee-qr-val\|fee-qr-n\|card.fee-pay{padding:16px}" App/app/static/app2.css | tail -3`. Expected: `5`.
5. `base.html` line 21: `app2.css?v=20261103-0898` becomes `app2.css?v=20261103-0896`. From `App/`: `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5`.
6. Create `App/tests/test_0896_fee_pay_geometry_browser.py` with exactly the code below, then run §6 command 1. On failure fix only step 4's values (never below the numbers in §1 or the test), once; fails again: STOP.
```python
"""0896: Stay fees step 2 (send the PDF and pay): geometry at seven widths."""
from __future__ import annotations
import os
from pathlib import Path
import pytest
from tests.test_stay_fee_send_panel import (  # noqa: F401  (fixtures and helpers)
    _finalize, _property, _stay, auth, browser_base, chromium_launch_kwargs, host, sync_api,
)
SHOTS = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0896"
CHECK_JS = """(id) => {
  const f = [], doc = document.documentElement, card = document.getElementById(id), r = e => e.getBoundingClientRect();
  if (doc.scrollWidth > doc.clientWidth + 1) f.push('page scrolls sideways');
  if (!card || card.dataset.feeStep !== '2') return f.concat('no step-2 card');
  const box = card.querySelector('.fee-send-pay'), vis = e => { const b = r(e); return b.width > 1 && b.height > 1 && !e.closest('.sr-only'); };
  if (r(box).width > 1000) f.push('content wider than 1000px: ' + r(box).width);
  const img = box.querySelector('.fee-qr-panel img'); if (!img) f.push('no QR'); else if (r(img).left < 0 || r(img).right > doc.clientWidth) f.push('QR outside viewport');
  [...box.querySelectorAll('.btn')].filter(vis).forEach(b => { if (r(b).height < 43.5) f.push('button under 44px: ' + b.textContent.trim()); });
  const red = [...card.querySelectorAll('.btn')].filter(vis).filter(b => getComputedStyle(b).backgroundColor === 'rgb(208, 69, 45)');
  if (red.length !== 1 || !(red[0].href || '').includes('mojedatovaschranka')) f.push('red buttons: ' + red.length);
  box.querySelectorAll('*').forEach(e => {
    if (!vis(e) || ![...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())) return;
    if (parseFloat(getComputedStyle(e).fontSize) < 14) f.push('text under 14px: ' + e.textContent.trim().slice(0, 30));
  });
  box.querySelectorAll('.fee-qr-val').forEach(e => { const cs = getComputedStyle(e), lh = parseFloat(cs.lineHeight) || parseFloat(cs.fontSize) * 1.2;
    if (r(e).height >= 1.6 * lh) f.push('value wraps: ' + e.textContent.trim()); });
  const items = [...box.querySelectorAll('.fee-tasks > li, .fee-tasks strong, .btn, .fee-qr-panel > *, .fee-qr-meta > div, .fee-qr-meta dt, .fee-qr-val')].filter(vis);
  for (let i = 0; i < items.length; i++) for (let j = i + 1; j < items.length; j++) {
    const a = items[i], b = items[j]; if (a.contains(b) || b.contains(a)) continue;
    if (a.matches('dt') && b.matches('.fee-qr-val') && a.parentElement === b.closest('div')) continue;  // label + value = one row
    const p = r(a), q = r(b), gap = Math.max(q.left - p.right, p.left - q.right, q.top - p.bottom, p.top - q.bottom);
    if (gap < 11.5) f.push('gap ' + gap.toFixed(1) + 'px: ' + (a.className || a.tagName) + ' / ' + (b.className || b.tagName));
  }
  return f;
}"""

@pytest.mark.parametrize("width", [320, 390, 768, 1024, 1280, 1440, 1920], ids=lambda w: f"w{w}")
def test_fee_pay_step2_geometry(host, browser_base, width):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id)
    _stay(apartment_id); _finalize(client, apartment_id)
    cookie = client.cookies.get(auth.SESSION_COOKIE)
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        context = browser.new_context(viewport={"width": width, "height": 900})
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": browser_base}])
        page = context.new_page()
        page.goto(f"{browser_base}/stay-fees?month=2026-08&lang=en", wait_until="networkidle")
        failures = page.evaluate(CHECK_JS, f"fee-pay-{apartment_id}")
        if os.environ.get("UBYHOST_SHOTS_0896") == "1" and width in (390, 1280):
            SHOTS.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(SHOTS / f"0896-stay-fees-pay-{width}.png"), full_page=True)
        browser.close()
    assert failures == [], failures
```
7. Run §6 commands 2 and 3, then command 4; look at each PNG once.

## 5. Do not touch

Step-1 content (`{% if period.step == 1 %}` branch), stepper markup, `.fee-bulk`, `.fee-copy`, notifications, help button, sidebar, `_components.html`, `app.css`, `host2.css`, `app.js`, any Python or i18n file, any other test. No new class beyond `fee-qr-title`, `fee-qr-n`, `fee-qr-val`. AGENTS.md rules 6, 7, 9.

## 6. Commands

From `App/`:
1. `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0896_fee_pay_geometry_browser.py -q -rs --tb=short -x -p no:cacheprovider 2>&1 | tail -30`. Expected: 7 passed, 0 skipped.
2. `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_stay_fee_pay_steps.py tests/test_stay_fee_pay_steps_browser.py tests/test_stay_fee_send_panel.py tests/test_static_versions.py -q -rs --tb=short -x -p no:cacheprovider 2>&1 | tail -30`. Expected: passed, 0 skipped.
3. `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -k stay -q -rs --tb=short -x -p no:cacheprovider 2>&1 | tail -30`. Expected: passed, 0 skipped.
4. `UBYHOST_SHOTS_0896=1 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0896_fee_pay_geometry_browser.py -k "w390 or w1280" -q -p no:cacheprovider 2>&1 | tail -5`.
From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance

- [ ] `App/tests/_scratch_fee.py` gone; `git status --short` shows only §3 paths; nothing committed. Commands 1 to 3 passed, 0 skipped; lint OK; `screenshots-0896/0896-stay-fees-pay-390.png` and `-1280.png` exist.

## 8. Stop and ask

Stop and write the report if: an anchor is not found verbatim; a test fails twice; a fix needs a file outside §3 or a value below §1 or the test; an existing test asserts removed markup (`btn ghost` on the PDF link, the third task row); you reach 25 tool calls or about 50k tokens (report `blocked`); a step is unclear.

## 9. Report

Write `docs/tasks/0896-report.md` (300 tokens at most) and set this brief's `Status: review`: `git status --short`, each §6 command with its last 5 lines, §7 ticked, Deviations, Questions. Do not commit.
