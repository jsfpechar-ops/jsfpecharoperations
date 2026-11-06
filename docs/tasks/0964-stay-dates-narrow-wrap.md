# 0964: Stay dates card: keep each date on one line at 320 px

Status: todo
Depends on: none | Base commit: a2fa3a8 | Branch: claude/zealous-planck-raxu4v (already checked out, rides on PR #791, no new PR)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

On a 320 px phone the stay detail "Arrival / Departure" card wraps dates such as "Mon 9. 11." onto two lines (56 px instead of 28 px). Fix the card so each date stays on one line at 320 px, without changing any value the 0710 mockup test compares.

CI failure this fixes (PR #791, browser shard 4): `tests/test_0710_v2_mockup_match_browser.py` -> `stay at 320 px: .stay-dates b height at 320 px: app=56px mockup=28px`. The test seeds its "ready" stay at `today+1 .. today+3`, so it fails on the days when a date is wide. It fails locally today (2026-11-06: "Sat 7. 11." and "Mon 9. 11."). The PR does not touch this page; the flaw is in the product.

## 2. Context

Measured in Chromium with the app's Manrope font (20 px, weight 800, letter-spacing -.01em):

| Text | Width |
|---|---|
| Mon 9. 11. | 91.1 px |
| Sat 28. 12. | 98.3 px |
| Wed 28. 11. | 103.8 px |
| Wed 28. 12. | 107.5 px |
| Mon 31. 12. 2027 | 153.8 px |

At 320 px: the card is 280 px wide with 20 px card padding, 1 px borders, so the grid has 238 px. Today the columns are `1fr 1fr` with intrinsic sizing, so they come out unequal (114.9 and 123.1 px, and the split depends on the date text). Each cell has 20 px side padding and a 1 px border, so the text gets only 73.9 px (first cell) and 82.1 px. "Fri 6. 11." (about 76 px) fitted by luck; "Mon 9. 11." (91 px) wraps.

Why "one line with the weekday" is impossible at 320 px: 238 px / 2 = 119 px per cell. The widest realistic text with weekday is 107.5 px, so the cell would need at most 5 px of side padding. The font-size, letter-spacing and the `.stay-dates` card padding (16/20) are all compared by the 0710 test against the mockup (STYLE_PROPS), so none of them may change. Therefore at 320 px the weekday is dropped visually (kept for screen readers) and the cell side padding goes from 20 to 12 px:

- cell content = 119 - 12 - 12 - 1 (border) = about 94 px (measure, do not trust this number);
- the widest date without weekday is "28. 12." (about 65 px) and "28. 12. 2027" (about 120 px) is the only one that still wraps, and only for dates in another year, where wrapping the year to a second line is acceptable. Dates in the current year always fit.

What the 0710 test compares for this card at 320 px (`tests/v2_mockup.py`, `phone_selectors` of the `stay` page): for `.stay-dates`, `.stay-dates small`, `.stay-dates b`, `.stay-dates .tot` the STYLE_PROPS (font-size, font-weight, color, background, radius, padding-top/right/bottom/left, border-top-width, border-bottom-color, letter-spacing) against the phone mockup `docs/design/mockup/ubyhost-phone-v2.html`, and the box metrics width (+-2 px), height (+-1 px) and margins (+-1 px) against the mockup or against `BOX_OVERRIDES` in `tests/v2_mockup.py`. The `stay:` overrides at lines 155 to 163 are "the app's measured fixture sizes" (text-dependent), not mockup values:

```
    "stay:.stay-dates small@320": {"width": "73.8906px"},
    ...
    "stay:.stay-dates b@320": {"width": "73.8906px", "height": "28px"},
```

The padding compared for `.stay-dates` is the card's (16/20), not the cell's, so changing the cell padding (`.stay-dates>div`) is not a style difference. The widths in the two override lines above DO change with the cell padding and the equal columns (they become date-independent, which is the point), so they are re-pinned to the new measured value. The height 28 px stays. This is the 0957 precedent (the same line was re-pinned there). No assertion is removed or loosened, the tolerance stays +-2 px, and the seed dates stay.

Current code (anchors, each must be found verbatim or STOP):

`App/app/templates/reservation_detail.html` lines 32-33:
```
  <div><small>{{ t('stays.table.arrival') }}</small><b>{{ reservation.date_from | weekday }} {{ reservation.date_from | date_short }}</b></div>
  <div><small>{{ t('stays.table.departure') }}</small><b>{{ reservation.date_to | weekday }} {{ reservation.date_to | date_short }}</b></div>
```
`App/app/static/app2.css` lines 655 and 658:
```
body.v2 .host-stay-detail .stay-dates>div{padding:18px 20px}
body.v2 .host-stay-detail .stay-dates b{display:block;font-size:20px;font-weight:800;letter-spacing:-.01em;line-height:1.4;margin-top:4px}
```
`App/app/templates/base.html` line 22: `href="/static/app2.css?v=20261105-guestpay8"`.

Weekday comes from `strftime("%a")` (`App/app/templating.py` `_weekday`), not localised; `date_short` gives `d. m.` plus the year only when it is not the current year (`App/app/validation.py` `fmt_date_short`).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/reservation_detail.html` | edit | wrap the weekday in `<span class="wd">` (2 lines) |
| `App/app/static/app2.css` | edit | one `@media (max-width:359px)` block after line 658 |
| `App/app/templates/base.html` | edit | bump the `app2.css` cache-buster |
| `App/tests/static_versions.json` | regenerate | by the script, never by hand |
| `App/tests/v2_mockup.py` | edit | re-pin the two 320 px widths (lines 157 and 160) to the measured value |
| `docs/tasks/screenshots-0964/` | create | screenshots (step 7) |
| `docs/tasks/0964-stay-dates-narrow-wrap.md` | edit | Status line only |
| `docs/tasks/0964-report.md` | create | the report |

No other file may change. The scratch test in step 4 is created and deleted before the commit.

## 4. Steps

1. Set `Status: in-progress` in this brief. Confirm the branch: `git branch --show-current | tail -30` prints `claude/zealous-planck-raxu4v`. Confirm the anchors from section 2 with `grep -nF` (each file, each line). Any anchor missing: STOP.

2. Template. In `App/app/templates/reservation_detail.html` replace the two `<b>` contents so the weekday sits in a span (the space after the span stays):
```
  <div><small>{{ t('stays.table.arrival') }}</small><b><span class="wd">{{ reservation.date_from | weekday }}</span> {{ reservation.date_from | date_short }}</b></div>
  <div><small>{{ t('stays.table.departure') }}</small><b><span class="wd">{{ reservation.date_to | weekday }}</span> {{ reservation.date_to | date_short }}</b></div>
```
Before this, `grep -rn "stay-dates\|| weekday" tests | tail -30`: if a test reads the exact text of these `<b>` elements via the HTML string (not inner_text), report it and STOP.

3. CSS. In `App/app/static/app2.css`, directly after line 658 (the `.stay-dates b{...}` rule), insert exactly:
```
/* 0964: at 320 px the two date cells are 119 px wide; "Mon 9. 11." (91 px at 20 px) wraps in a 74 px text column. Equal columns, 12 px cell padding, and the weekday read by screen readers only keep each date on one line. */
@media (max-width:359px){
body.v2 .host-stay-detail .stay-dates{grid-template-columns:minmax(0,1fr) minmax(0,1fr)}
body.v2 .host-stay-detail .stay-dates>div{padding:18px 12px}
body.v2 .host-stay-detail .stay-dates b .wd{position:absolute;width:1px;height:1px;margin:-1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
}
```
Do not touch the `.tot` rule (line 659), `font-size`, `letter-spacing` or the card padding.

4. Measure and check the worst case (scratch test, deleted afterwards). Create `App/tests/test_zz_0964_scratch.py` with exactly:
```
from app import auth
from tests.test_0710_v2_mockup_match_browser import _launch, _open_app, _path
from tests.test_host_quiet_dashboard_browser import base, dashboard_host, dashboard_rich_host, sync_api  # noqa: F401
from tests.v2_mockup import PAGES

JS = """(worst) => {
  const c = document.querySelector('.host-stay-detail .stay-dates');
  const bs = [...c.querySelectorAll('b')];
  if (worst) bs.forEach(b => { b.innerHTML = '<span class="wd">Wed</span> 28. 12.'; });
  const r = e => { const x = e.getBoundingClientRect(); return Math.round(x.width * 100) / 100 + 'x' + Math.round(x.height * 100) / 100; };
  return {card: r(c), small: [...c.querySelectorAll('small')].map(r), b: bs.map(r), scrollW: document.documentElement.scrollWidth};
}"""


def test_scratch(base, dashboard_rich_host):
    spec = [s for s in PAGES if s["name"] == "stay"][0]
    cookie = dashboard_rich_host["client"].cookies.get(auth.SESSION_COOKIE)
    out = "/tmp/shots0964"
    import os
    os.makedirs(out, exist_ok=True)
    with sync_api.sync_playwright() as p:
        br = _launch(p)
        for w in (320, 390, 768, 1280):
            ctx, pg = _open_app(br, base, cookie, _path(spec, dashboard_rich_host), w)
            print("MEAS", w, "real", pg.evaluate(JS, False))
            pg.screenshot(path=f"{out}/stay-{w}.png", full_page=True)
            print("MEAS", w, "worst", pg.evaluate(JS, True))
            ctx.close()
        br.close()
```
Run (needs Playwright, see section 6 first):
`cd App && PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers .venv/bin/python -m pytest tests/test_zz_0964_scratch.py -q -s -rs 2>&1 | grep -E "MEAS|passed|failed|Error|skipped" | tail -30`
Expected at 320: both `b` heights `28`, `scrollW` `320`, "worst" `b` heights `28` too (real and worst), `small` and `b` widths about 94 (write the exact first-cell value down as W320). At 390: `b` `113x28` and `small` `113x...` as before the change (unchanged). Heights 56 at 320 or scrollW above 320: STOP and report the numbers.
Then delete the file: `rm -f tests/test_zz_0964_scratch.py` (its screenshots stay in /tmp/shots0964 for step 8).

5. Re-pin the widths in `App/tests/v2_mockup.py`: replace the two 320 px values `73.8906px` (lines 157 and 160, in `"stay:.stay-dates small@320"` and `"stay:.stay-dates b@320"`) with `<W320>px` (the first-cell width measured in step 4, for example `94px`; the `b` line keeps `"height": "28px"`). Extend the existing 0957 comment above line 160 with: `0964: 320 px has equal columns, 12 px cell padding and a screen-reader-only weekday, so the width no longer depends on the date text`. Check: `grep -n "stay:.stay-dates" tests/v2_mockup.py | tail -30`. Do not change the 390 px lines.

6. Cache-buster. In `App/app/templates/base.html` change `?v=20261105-guestpay8` to `?v=20261106-0964` (only on the `app2.css` link). Check no other template pins app2.css: `grep -rn "app2.css" app --include=*.html --include=*.py --include=*.js | tail -30` (only base.html expected; others: report and STOP). Then `cd App && .venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -30`, then `cd App && .venv/bin/python -m pytest tests/test_static_versions.py -q --tb=short 2>&1 | tail -30` (green). `git diff --stat | tail -30` must show `static_versions.json` changed only for `app2.css` (sha256 and `v`).

7. Tests (section 6), then screenshots: copy `/tmp/shots0964/stay-320.png`, `stay-390.png`, `stay-768.png`, `stay-1280.png` to `docs/tasks/screenshots-0964/` (`mkdir -p` first). Open each with the Read tool once. Note per width what you see: 320 px: the two dates on one line each, no weekday, no sideways scroll, text at least 16 px from the card edge; 390 px: weekday and date on one line as before; 768 px and 1280 px: unchanged desktop or tablet layout.

8. Commit and push. `git add App/app/templates/reservation_detail.html App/app/static/app2.css App/app/templates/base.html App/tests/static_versions.json App/tests/v2_mockup.py docs/tasks/0964-stay-dates-narrow-wrap.md docs/tasks/0964-report.md docs/tasks/screenshots-0964`, check `git status --short | tail -30` shows nothing else, then commit with the message `0964: keep stay dates on one line at 320 px` and these two trailer lines at the end of the message:
```
Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014N5J8K21RfgG5itpXC8Mic
```
Push: `git push -u origin claude/zealous-planck-raxu4v 2>&1 | tail -30`. This one push to the existing PR #791 branch is authorised by the orchestrator in this brief; do not open a new PR, never push to `main`. If the push is refused, hand the exact command to the owner in the report.

## 5. Do not touch

- `App/tests/test_0710_v2_mockup_match_browser.py` and its seed dates (`today + timedelta(days=1..3)` in `test_host_quiet_dashboard_browser.py`): never change, skip or weaken an assertion.
- `font-size`, `letter-spacing`, the `.stay-dates` card padding, the `.tot` rule, any rule at 360 px and above, `docs/design/mockup/*`.
- AGENTS.md rules 3, 4 (no new dependency; Playwright is installed in the venv only, it is not added to a requirements file), 6 (light mode only), 7 and 10.

## 6. Commands

Playwright is missing from `App/.venv`. Install it once (CI pins 1.63.0) and use the preinstalled Chromium; never run `playwright install`:
```
cd App && .venv/bin/pip install -q playwright==1.63.0 2>&1 | tail -3
export PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers
```
(The export must be repeated in each command line.) If the browser tests still skip or cannot start, say so in the report; CI is then the check, and the screenshots section of the report says "not taken, no browser".

Tests, each with `-rs` so skips show, expected `N passed` and 0 skipped:
```
cd App && PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -k "stay" -q --tb=short -rs 2>&1 | tail -30
cd App && PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q --tb=short -rs 2>&1 | tail -30
cd App && PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers .venv/bin/python -m pytest tests/test_host_stay_detail_layout_browser.py tests/test_host_stay_actions_browser.py tests/test_0766_phone_stays_browser.py -q --tb=short -rs 2>&1 | tail -30
cd App && .venv/bin/python -m pytest tests/test_static_versions.py tests/test_overhaul.py -q --tb=short 2>&1 | tail -30
cd /home/user/jsfpecharoperations && python3 scripts/context_lint.py 2>&1 | tail -30
```
Before the fix the first command fails with `.stay-dates b height at 320 px: app=56px mockup=28px` (on days where a date is wide); after step 5 it must pass. If `-k "stay"` matches fewer than the `stay-320`, `stay-390` and `stay-768` style cases and the geometry cases, report the count. A failure in test_layout_lint_browser.py: read the last 30 lines, fix once if it is in the lines you changed, otherwise STOP (never silence a finding).

## 7. Acceptance

- [ ] `test_0710_v2_mockup_match_browser.py -k stay`: all pass, 0 skipped (or "no browser, CI is the check").
- [ ] `test_layout_lint_browser.py` green, 0 skipped; stay detail browser tests green.
- [ ] Step 4 scratch output: at 320 px real and worst-case ("Wed 28. 12.") `b` height 28, `scrollW` 320.
- [ ] `git diff --stat` lists only the files of section 3 (plus the screenshots); the scratch test is gone.
- [ ] Design-system checklist (docs/design/design-system.md section 5) ticked in the report: sideways scroll none at 320/390/768/1280, nothing closer than 12 px, no truncated label, no new copy, light mode.
- [ ] Screenshots at 320, 390, 768 and 1280 px in `docs/tasks/screenshots-0964/`, with one line per width in the report on what was seen.
- [ ] Branch pushed (or the push command handed to the owner).

## 8. Stop and ask

Stop, and write the report, if:

- an anchor is not found;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- the measured heights at 320 px are not 28, or the page scrolls sideways;
- a file outside section 3 needs a change, or a test reads the `<b>` text in a way the span breaks;
- you need merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0964-report.md` (600 tokens at most) with `Status: review`: files changed (`git diff --stat`), each command with the last 5 lines, section 7 ticked, per-width screenshot notes, deviations, questions. Known and accepted: dates in another year ("28. 12. 2027") are wider than a 320 px cell and wrap the year to a second line; at 360 to 389 px the widest dates with weekday ("Wed 28. 12.", 107.5 px) can still wrap (content 98 to 112 px), unchanged by this brief; the 0710 seed dates near New Year (year shown) can still fail at 320 px. Say so, do not fix it.

## Risk list (for the reviewer)

- `App/app/static/app2.css` (the new media block only).
- `App/tests/v2_mockup.py` (two lines: widths re-pinned, tolerance and height unchanged).
- `App/app/templates/reservation_detail.html` (span only).

## Owner steps

None. The PR #791 CI re-runs on the push; the owner merges with `scripts/merge-pr-on-green.sh` when green.
