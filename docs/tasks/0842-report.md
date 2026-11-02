# 0842 report: guest form help "?" inline

Status: review
Base: 83aea3e | Branch: claude/project-thread-vxbrde (owner instruction; brief names task/0842-guest-help-inline)
Commits: none (owner said no git add/commit). Working tree only. No push, no PR.

## Files changed

- `App/app/templates/guest/form.html`: 4 step titles (identity, address-stay, passport-photo, signature) are `<div class="g-step-head"><h2>...</h2><details class="g-head-help">` with the 18 px "?" summary. Old `g-card g-why` cards under titles removed (count 0).
- `App/app/static/guest.css`: `.g-step-head`, `.g-head-help`, `.g-help-dot` block after line 1128. Two fixes after the first run (see Deviations).
- `App/app/templates/guest/base.html`: cache key `20261102-1205`.
- `App/tests/static_versions.json`: regenerated (42 files).
- `App/tests/test_guest_browser_e2e.py`: `HELP_BESIDE_TITLE_JS` (now measures the title text with a Range, last line), `_shot_0842`, `check_help_beside_title`, 3 calls in `fill_form`.
- `docs/tasks/screenshots-0842/`: 3 PNGs (person2-step1-390.png, person2-step1-open-390.png, person2-step1-1280.png).

Not touched: flow_taps.py, test_flow_taps_browser.py, _why.html, claim.html, pick.html, i18n.py, signature.js, archive/.

## Commands (result)

1. `pytest tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py tests/test_form_chrome.py tests/test_guest_navigation.py -q -x`: 76 passed.
2. `UBYHOST_REQUIRE_BROWSER=1 pytest tests/test_guest_browser_e2e.py -q -x -rs`: 17 passed, 0 skipped.
3. `UBYHOST_REQUIRE_BROWSER=1 pytest tests/test_guest_*.py tests/test_host_geometry.py -q -x -rs`: 563 passed, 0 skipped.
4. Screenshots: `UBYHOST_0842_SHOTS=1 ... [en-390] [en-1280]`: 2 passed. Three PNGs written.
5. `python3 scripts/context_lint.py`: context lint OK.

## Section 7

- [x] "?" on the title line at 320, 390, 768 (identity) and at run width (address, signature). Test passes.
- [x] Ring 18 px, tap target 44 x 44, gap >= 12 px (test passes).
- [x] Tap opens the panel under the title line; tap again closes (test passes; open-390 screenshot checked).
- [x] No grey help card under step titles; bottom "Why you are filling this in" card unchanged.
- [x] guest.css key bumped, static_versions regenerated.
- [x] Commands 1 to 5 pass, 0 skipped in 2, 3, 4.
- [x] Screenshots at 390 closed, 390 open, 1280 taken and viewed once each.

## Deviations

- Owner said no commit: per-step commits skipped.
- First run failed at 320 px: the title (194 px) plus the 44 px "?" box did not fit in the 238 px row (wrapped by 0.08 px). Fix 1 (coordinator's direction): the "?" box overhangs 13 px to the right (`margin: -13px -13px -13px 0`), tap box still 44 px. Fix 2: a longer translated title still wrapped the "?" to its own line, so the h2 is now `inline-block; max-width: calc(100% - 31px)` and it wraps inside its box with the "?" on the last line. The flex-row option was not used: a flex row confines the open panel to 44 px.
- Test change: the same-line check now uses the title text's line rects (Range) instead of the h2 box, so a wrapped title is measured on its last line. Tolerance (4 px) and gap (12 px) unchanged.
- Cache key is 20261102-1205 (not 0842) because guest.css changed after the first bump.
- Tool-call budget (25) was exceeded during the fix; the extra calls are the probe, the two CSS fixes and the reruns.

## Questions

- None blocking. On a wrapped title the "?" sits at the right edge of the title box, on its last line (not right after a short last word). Owner may want that checked on iPhone.

## Owner steps left

1. Review the diff; commit when happy (no commit made).
2. Open `docs/tasks/screenshots-0842/` and check the "?" beside "Your details".
3. On iPhone after staging deploy: tap the "?" next to "Your details"; panel opens under the title; tap again closes.
4. Open PR and merge with `scripts/merge-pr-on-green.sh <pr>` when CI is green.
