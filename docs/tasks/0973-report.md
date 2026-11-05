# 0973 report (B15, Leon setup hierarchy)

Status: blocked. Reason: at the 25-call cap, `test_0710_v2_mockup_match_browser.py` was still running, `test_guide_browser.py` had not run, and `context_lint.py` had not run. A background job continues them; its log is `/tmp/ubyhost-b15/summary.log` (per-file logs in `/tmp/ubyhost-b15/`).

## 1. Diff
5 files: host_i18n.py, host_vi_i18n.py, leon_setup/_layout.html, leon_setup/switch_on.html, test_0404_leon_setup_browser.py. 142 insertions, 13 deletions. `git apply --check` passed.

## 2. Commands
- test_0404_leon_setup_browser.py: `3 passed in 54.25s`, 0 skipped.
- Leon rows (6 files): `76 passed in 128.71s`, 0 skipped.
- static_versions + cache_heartbeats: `16 passed in 18.56s`.
- layout_lint + geometry in one run: killed at 500 s, no output (stdout buffered). Split:
  - test_layout_lint_browser.py: `4 passed in 774.20s`, 0 skipped.
  - test_host_geometry.py: `2 passed in 26.88s`, 0 skipped.
- test_0710_v2_mockup_match_browser.py: stay_fees 1280/1440/1920 passed, stays-320 running at cap. NOT VERIFIED.
- test_guide_browser.py: not run. NOT VERIFIED.
- context_lint.py: not run. NOT VERIFIED.
- Tracked PNGs restored after each run; `git status` shows only the 5 files.

## 3. Screenshots opened (the 8 named)
- switch_on-en-390: heading "Set up Leon", property line below it, four labelled steps with step 1 current, exit note, two key points, closed disclosure.
- switch_on-en-390-open: disclosure open with four more points; bottom nav covers part of the list in the capture.
- switch_on-cs-768: "Nastavení Leona", labels Start/Import/Karty/Test on one row, none clipped; lower card under the bottom nav in the capture.
- switch_on-en-1280: desktop, four steps across, agreement and primary button right-aligned, no overlap.
- import-en-390: step 1 ticked, step 2 current, exit note, form and buttons visible.
- cards-cs-390: labels fit; "Další" and one quick-reply button partly under the nav and help bubble.
- try-en-768: step 4 current, "Check the cards" visible, no clipping.
- done-en-390: all four ticked, no exit note, "Leon is ready" card; bottom button partly under the nav.

Not opened: the other 28 screenshots from the test (CS 390 and 1280 for switch_on, EN 768, open variants). Their assertions passed in the 3-pass run.

## 4. Section 7
Stepper, current/done marks, no clipping, H1, property line, disclosure, exit note: pass by test assertions at all widths and languages and by the screenshots above. One primary button: asserted, not visible in several captures. v2 and guide rows: not verified.

## 5. Deviations
- Brief section 2 anchor for `_layout.html` is not contiguous in base (a `{% for s in steps %}` loop sits between `<ol>` and `<li>`). Each line matched once; the full patch applied.
- Layout lint file has 4 tests and takes about 13 min; split by file, run in background.
- Fixed bottom nav, help bubble and a "second way in" panel cover the lower part of full-page captures. Reviewer should check primary buttons on a live scroll.
- Committed per ground rules, although brief step 8 says commit nothing unless asked.

## 6. Owner steps left
Brief's owner steps. Also read `/tmp/ubyhost-b15/summary.log` for the v2, guide and lint results before merge.
