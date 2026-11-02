# 0814 brief: small, minimal help "?" on the same line as its title

Status: todo
Executor: Haiku 5.5, alone, in /home/claude/jsfpecharoperations on branch claude/project-thread-a41o7b (checked out; App/.venv exists). Do not commit, push, checkout, reset, stash or restore: the orchestrator commits.

## 1. Objective
Josef (2026-11-02 14:47): the help "?" buttons sit under the headers instead of next to them, and they are huge. He wants them minimalistic. See `docs/tasks/screenshots-0800/property-new-390.png`: 44 px grey circles, and under "After you create it" each "?" is on its own line below the title. Target on every page of `App/tests/test_0800_v2_remaining_pages_browser.py`, all widths: the "?" is a plain round icon, 18 px visible (1px `var(--line)` border, `var(--ink3)` glyph, 12 px font, no fill, no shadow), placed inline 6 px after the last word of its heading/label, vertically centred on that line, never alone on a new line.

## 2. Context
The shared rule is the `/* 0812 help tip (v2) */` block at the end of `App/app/static/app2.css` (24 px desktop, 44 px phone min size: that is the "huge"). Phone tap target stays 44 px but invisible: give `.help-tip-btn` `position:relative` and a `::before{content:"";position:absolute;inset:-13px}` hit area, so layout size stays 18 px. Wrappers from 0809: `.heading-with-tip`, `.prop-name-tip`, `.havel-name-tip`; the new-property "After you create it" list (`App/app/templates/_property_create.html`) puts title and tip in a column.

## 3. Files
`App/app/static/app2.css` (0812 block, plus deleting conflicting help-tip size rules in other 0800-0809 blocks), `App/app/templates/_property_create.html` (markup order only if CSS cannot do it), `App/tests/test_0800_v2_remaining_pages_browser.py`.

## 4. Steps
Env (from App/): `export PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1`.
a. Rewrite the 0812 block: `.help-tip` inline-flex, vertical-align middle, margin-left 6px, flex none; `.help-tip-btn` width/height 18px (all widths), min-width/min-height 0, padding 0, border 1px solid var(--line), border-radius 50%, background transparent, color var(--ink3), font-size 12px, line-height 1, plus the invisible `::before` hit area (inset -13px below 1024 px, -3px above). Wrappers (`.heading-with-tip`, `.prop-name-tip`, `.havel-name-tip`, the create-next item title row): `display:flex;flex-wrap:nowrap;align-items:center;gap:6px`, the heading text `min-width:0`.
b. Remove the 44 px/24 px help-tip size rules elsewhere in app2.css that beat this (grep `help-tip-btn`; keep the stay-detail and `details` rules outside these pages).
c. Test: for every visible `.help-tip-btn` in `main` on each page and width: visible box <= 20 x 20 px; its vertical centre is within the line box of the text it follows (the previous sibling or the wrapper's heading: |centre difference| <= 4 px); its left edge is >= that text's right edge and <= right edge + 12 px. Fail with page, width and the label text. The check must fail on the current screenshot state (run it before the CSS fix to confirm).
d. Update any older assertion that requires 44 px help buttons on these pages to check the hit area instead (element bounding box of the `::before` cannot be measured; assert the computed `inset` or use `elementFromPoint` 10 px outside the visible circle).
e. Full commands, then screenshots.

## 5. Do not touch
Other pages, copy, behaviour, the cache key, sidebar/top bar.

## 6. Commands
From App/, env above:
- `.venv/bin/python -m pytest tests/test_0800_v2_remaining_pages_browser.py tests/test_onboarding_wizard_browser.py tests/test_property_create_browser.py -q --tb=line -p no:cacheprovider 2>&1 | tail -8` → 0 failed
- `UBYHOST_SHOTS_0800=1 .venv/bin/python -m pytest tests/test_0800_v2_remaining_pages_browser.py -q 2>&1 | tail -3`
- repo root: `python3 scripts/design_lint.py 2>&1 | tail -3`

## 7. Acceptance
Section 6 green; property-new-390 and havel-1280 screenshots show a small "?" right after the title text.

## 8. Stop and ask
Stop at 30 tool calls, or if a template change beyond markup order is needed.

## 9. Report
`docs/tasks/0814-report.md`: rules changed/removed, test added, final tails.

## 10. Added scope: Add property (/apartments/new), Josef 15:23
h. Phone: the "Copy from another property" button floats on its own line offset right, not aligned with the "How does this work?" help pill. Put the two on one row, left-aligned, vertically centred, 12 px apart (wrap to two left-aligned lines only below 360 px).
i. Remove fine print: the "Start with the basics…" subtitle and the "Fields marked * are required." line (move into the page-title help "?" if not already there; keep the translation keys).
j. Desktop 1024/1280/1440: the Cancel link sits 8 px from the create card (0813 neighbour check fails). Find the real cause with a computed-style probe (which element's margin/gap sets the 8 px) and make it >= 12 px.
k. Remove the subtitle under the "Help & guide" h1 on /guide the same way (i).
Files for 10: `App/app/templates/apartment_form.html`, `App/app/templates/_property_create.html`, `App/app/templates/guide.html` (subtitle only), app2.css 0800 block. Another executor is editing guide.html/guide.js at the same time: touch only the subtitle line there and re-read before editing.

## 11. Round 2 decisions (orchestrator)
- Long labels at 320 px: the "?" must ride on the LAST line of the text, right after the last word, never on a line of its own. So wrappers are not flex: `.heading-with-tip`, `.prop-name-tip`, `.havel-name-tip` and label rows become `display:block` (heading inline: `h1,h2,h3,label{display:inline}` inside the wrapper, or the tip placed inside the heading element), and `.help-tip` stays `display:inline-flex;vertical-align:middle;margin-left:6px;white-space:nowrap`. Glue the last word to the tip if needed with a non-breaking structure (the tip inline right after the text node, no whitespace that allows a break is not required: the 24 px tip fits after any last word at 320 px).
- Update `test_help_tip_is_small_and_inline`: compare the tip with the last line box of the label text (Range over the text node, `getClientRects()`, take the last rect): |centre diff| <= 4 px and left gap 0-12 px. Havel 1024 5.5 px offset: align with `vertical-align:middle` against the h1's line, or give the h1 wrapper `align-items:center` if it stays flex there.
- Onboarding choice_card[390-False-*] card-edge click: check on the commit before 0814 (`git stash` is forbidden: use `git worktree add /tmp/wt0814 HEAD~1` read-only and run that one test there, then `git worktree remove /tmp/wt0814`); if it passes there, fix it.
- Then section 10 (h-k).

## 12. Round 3 decisions (orchestrator, from "Round 2 (tip wrapping)" in the report)
- cleaning-new ("Cleaning date", "Cleaning notes"): move each help tip into the label element in `App/app/templates/cleaning_edit.html` (right after the label text), not after the whole `.ui-field` block. If the field macro renders the label, pass the tip the way other v2 pages do (grep `help=` in `_ui_*.html` / `_components.html`).
- cleaning-shares "Create sharing link": a "?" next to a button is allowed. In the test, when the tip's previous element sibling is a button or `.ui-btn`, compare with the button box instead (|centre diff| <= 4 px, gap 6-12 px). "Share schedule" at >=1024: move the tip inside the h1/h2 element in `App/app/templates/cleaning_shares.html`, right after the text.
- havel 1024-1440: remove the flex row rule `.head>div:has(>.havel-name-tip)` and let the tip sit inline inside/after the h1 text like the others.
- Then run the whole 0800 file and fix any property-new, setup-*, guest-guide, guide case the same way (tip inside the heading/label, inline).
- The modified PNGs under docs/tasks/screenshots-guide/ come from test runs: ignore them.

## 13. Round 4 decisions (orchestrator, from "Round 3" in the report)
- Phone geometry: keep the box from overlapping the text and keep the visible gap 6 px: below 1024 px the 18 px circle (`::after`) sits at the LEFT of the 44 px box (`left:0;top:13px`, not centred), the box margins are `-13px -26px -13px 0` (layout footprint 18 px wide), `.help-tip{margin-left:6px}`. Desktop unchanged (24 px box, circle centred, -3px margins).
- The test measures the gap and the vertical centre from the visible circle: circle rect = box rect offset by the `::after` computed `left`/`top` and sized by its `width`/`height`. Limits stay: centre <= 4 px, gap 0-12 px.
- setup-* and guest-guide: change the shared `field_label` macro in `App/app/templates/_components.html` so its help tip renders inside the `<label>` right after the text (same markup otherwise). Then also run `.venv/bin/python -m pytest tests -q -k "label or help_tip or field" --tb=line -p no:cacheprovider 2>&1 | tail -8` to catch other pages.
- guide and property-new: the other executor is done; their title tips may now be fixed here (tip inside the h1, after the text).

## 14. Round 5 (next thread)
Open items from "Round 4" in the report:
- setup-calendar/police/guest-guide-link/stay-fee: `.field-label-row` h2 rows (setup_wizard/*.html, _property_editor.html) do not use field_label; put their tip inside the h2 after the text like field_label does now.
- guest-guide "Import from Booking or Airbnb" row in guest_guide.html: tip inside its heading.
- property-new "After you create it" list tips (_property_create.html): tip inside each item title.
- Popover overflow (test_host_help_browser 360/390/1280): the tip body is `left:0` of the tip, so a tip near the right edge overflows. Below 1024 px show the body as `position:fixed;left:16px;right:16px;width:auto` under the tip; at >=1024 clamp with `right:0;left:auto` when the tip is in the right half (add a `.help-tip-end` class from help.js if needed, or simply anchor the body to the heading wrapper).
- test_endtoend test_26 KeyError 'id': check on origin/main first; fix only if this branch caused it.

## 15. Round 5 decisions (orchestrator, 2026-11-02 16:40)
Two executors run at the same time in the same checkout. Each edits ONLY its files. Do not commit.

### 15A. Tips inside headings (templates only)
Files: `App/app/templates/_property_editor.html`, `App/app/templates/setup_wizard/police.html`, `App/app/templates/setup_wizard/guest_link.html`, `App/app/templates/_ui_layout.html`, `App/app/templates/guest_guide.html`, `App/app/templates/_property_create.html`.
- Every `.field-label-row` whose first child is an `<h2>` followed by `{{ help_tip(...) }}`: move the `help_tip(...)` call inside the h2, right before `</h2>` (after the text). Keep everything else (e.g. the police sample link stays after the h2). Do not touch the `<label>` row in reservation_detail.html.
- `_ui_layout.html` `ui_section`: add a param `tip=''` and render `{{ tip }}` inside the h2 after `{{ title }}`. In `guest_guide.html` import section, pass the import tip as `tip=help_tip(...)` (off-state tip when `not import_on`, otherwise the import-help tip) and delete the two standalone `{{ help_tip('guide-import...') }}` lines. Use `{% set %}` before the call if needed.
- `_property_create.html` "After you create it" list: move each `help_tip(...)` inside its `<strong>`, after the text (for the door-code item: after the `opt` span).
Tests (from App/, env as §4): `.venv/bin/python -m pytest tests/test_0800_v2_remaining_pages_browser.py -k small_and_inline -q --tb=line -p no:cacheprovider 2>&1 | tail -8` → 0 failed; then `.venv/bin/python -m pytest tests/test_onboarding_wizard_browser.py tests/test_property_create_browser.py -q --tb=line -p no:cacheprovider 2>&1 | tail -5`.

### 15B. Popover overflow and endtoend check
Files: `App/app/static/app2.css` (the 0812 help-tip block only), `App/app/static/app.js` (help-tip open function near line 1950 only).
- Below 1024 px: open `.help-tip-body` is `position:fixed;left:16px;right:16px;width:auto;top:auto` (vertical position stays under the tip).
- At >=1024 px: in app.js, when a tip opens, toggle class `help-tip-end` on the tip if `tip.getBoundingClientRect().left > window.innerWidth / 2`. CSS: `body.v2 .help-tip-end>.help-tip-body{left:auto;right:0}`.
- Tests: `.venv/bin/python -m pytest tests/test_host_help_browser.py -q --tb=line -p no:cacheprovider 2>&1 | tail -6` → 0 failed.
- endtoend test_26: run `.venv/bin/python -m pytest tests/test_endtoend.py -k test_26 -q --tb=short -p no:cacheprovider 2>&1 | tail -15`. If it fails, report the traceback only; do not fix (orchestrator checks main).
Report: append "## Round 5A" or "## Round 5B" to `docs/tasks/0814-report.md` (changed, final tails, deviations).

## 16. Round 6 decisions (orchestrator, 2026-11-02 17:10)
After 5A+5B: the four-file run is `8 failed, 217 passed`. Remaining reds and decisions (one executor, all files below allowed):
a. setup-* (all five): `App/app/templates/setup_wizard/_layout.html` line ~38: move `{% block wizard_help %}{% endblock %}` inside the `<h2 class="setup-wizard-question">`, right after the text.
b. guest-guide at 320 px: the tip wraps alone onto the next line of the h2 (gap -237 px). First: make the `help_tip` macro in `_components.html` emit no leading/trailing whitespace (`{%- ... -%}` trims) and add `white-space:nowrap` to `body.v2 .help-tip` in the 0812 block. If it still wraps, add to the 0812 block: `body.v2 :is(h1,h2,label):has(>.help-tip){display:flex;align-items:last baseline;gap:6px}` with `body.v2 :is(h1,h2,label):has(>.help-tip)>.help-tip{margin-left:0}` and check the other pages stay green.
c. property-new: one tip reports `(no label)`. Print all findings for property-new (call `_HELP_TIP_SIZE_JS` in a scratch run) to find it, then move that tip inside its heading/label like §15A. Do not change the test.
d. `tests/test_host_help_browser.py[1280]` property-create `addr_house_no-help`: popover box x=1234.8 overflows. Find why the 5B `help-tip-end`/`place()` logic does not keep it inside the viewport at 1280 and fix it in app.js/app2.css. Do not change the test.
e. `guest_guide.html` import section: replace the now-empty `{% if not import_on %}` / `{% else %}` pair with `{% if import_on %}` (same `{% endif %}`).
Commands (from App/, env §4): `.venv/bin/python -m pytest tests/test_0800_v2_remaining_pages_browser.py tests/test_onboarding_wizard_browser.py tests/test_property_create_browser.py tests/test_host_help_browser.py tests/test_guest_guide*.py -q --tb=line -p no:cacheprovider 2>&1 | tail -10` → 0 failed. Report: "## Round 6" in 0814-report.md.

## 17. Round 7 decisions (orchestrator, 2026-11-02 17:45)
Round 6 left one red (guest-guide 320 px, gap 174 px) and an unverified broad rule. Decisions:
a. Delete the two `:is(h1,h2,label):has(>.help-tip)` flex lines that round 6 added to the 0812 block in app2.css (too broad, not run against the full set).
b. `ui_section` in `_ui_layout.html`: when `tip` is set, keep the tip glued to the last word: `{% set parts = title.rsplit(' ', 1) %}<h2>{% if parts|length == 2 %}{{ parts[0] }} {% endif %}<span class="tip-nowrap">{{ parts[-1] }}{{ tip }}</span></h2>`; without a tip render as before. CSS in the 0812 block: `body.v2 .tip-nowrap{white-space:nowrap}` and `body.v2 .tip-nowrap .help-tip-body{white-space:normal}`.
c. Run the §16 command → 0 failed. Then `.venv/bin/python -m pytest tests -q -k "wizard_polish or label or help_tip or field" --tb=line -p no:cacheprovider 2>&1 | tail -8` (test_endtoend test_26 is a known pre-existing red on main).
d. Orchestrator after green: bump the app2.css key in base.html, `.venv/bin/python tests/test_static_versions.py --write`, commit only App/ + docs/tasks/0814* (never the rewritten evidence PNGs), push to BOTH a41o7b and r3es5m, screenshots to Josef.
