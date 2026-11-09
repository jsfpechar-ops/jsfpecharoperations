# 1030 Property editor redesign (wide screens)

Status: todo. Executor: Haiku 5.5. Read AGENTS.md, docs/context/executor.md, this brief. Open only files named here.
Report: write `docs/tasks/1030-editor-redesign-report.md` (600 tokens max), set `Status: review` or `blocked`, open one PR.
Branch: `claude/editor-redesign` from `origin/main` in a fresh worktree:
`git fetch origin main && git worktree add ../ubyhost-1030 -b claude/editor-redesign origin/main`, work only there. Never push to main.

## 1. Objective
Redesign the host property editor at >= 768 px (section list, one section at a time, one error line, fewer help icons). Phone unchanged.

## 2. Context
### Design direction (owner, 2026-11-08, binding)

Make it as simple as Wolt's app. Plenty of whitespace, ONE clear column, large rounded section rows or cards, few borders, ONE primary button, minimal text, no repeated explanations, no decorative badges. When in doubt, REMOVE an element rather than restyle it.
Spacing scale (use design tokens `--space-*` where they exist; no other values): 24 to 32 px between rows and between sections; 16 px inside a row or card; tap targets at least 48 px high; wide side padding (at least 24 px at 768, 32 px at 1280). Same rhythm everywhere on the page; no one-off margins. Card radius 12 to 16 px, 1 px `--line` only where a card needs an edge, no shadows, no card in a card. Light mode only.

### Owner decisions this brief implements

- 2026-11-08: FULL REDESIGN of the host property editor at >= 768 px.
- 2026-11-08 (kept): at 390 px the editor stays the existing accordion layout (phone = old settings page). Do not change phone look.
- Reference screenshots (read once): `/mnt/project-files/ux-shots/spacing3/property-editor-1280-full.png`, `-768-full.png`, `-390-top.png`.

### Problems to fix at >= 768 px

1. "Missing: X" plus grey "X is required." box lists every field twice, tall grey panel inside Basic details.
2. Six status cards plus a "Continue setup" box above the form.
3. A "?" help icon on nearly every label.
4. All sections are stacked accordions; Basic details form is very long.

### Target (>= 768 px)

- Left in-page section list (Basic details, Foreigner police, Calendars, Automatic messages, Smart lock, Stay fee). Each item: name plus a small status dot (green ok, red needs fixing, grey off). This REPLACES the six status cards and the Continue-setup box at >= 768 (hide them there with CSS; delete nothing the phone uses).
- Exactly one section visible at a time; the others hidden. Selected section comes from the URL hash / existing `?section=` value; default Basic details (or the first red one if setup is incomplete).
- One slim error line at the top of the visible section when fields are missing: "Fix N fields: House number, Postcode, ..." Each name is a link that focuses its field (and switches section if the field is in another). Never repeat the sentence per field; the per-field grey "X is required." text is hidden at >= 768 (the input keeps its own invalid state and aria-describedby).
- "?" help kept ONLY where the text is truly needed (police reporting, stay fee, smart lock). Everywhere else the text moves to placeholder or a one-line hint under the input. Keep no more than 3 "?" per section.
- One primary Save button per form (already a lint rule). Tighter, regular spacing per the scale above.
- No-JS: all sections are stacked and visible (today's accordion markup), the section list is anchor links (`#sec-...`). JS adds the one-at-a-time behaviour via a class on the form wrapper. Forms and saved field names unchanged.

## 3. Files
`App/app/templates/_property_editor.html`, `App/app/static/app2.css`, `App/app/static/app.js`, `App/app/templates/base.html`, `App/tests/static_versions.json`, `App/tests/test_property_navigation_browser.py`, `App/tests/v2_mockup.py`, translation files (step 4).

## 4. Steps (each = one commit `1030 step k`; stop rules in executor.md apply)

Find anchors first with `grep -nF`. Not found: STOP.

### Step 1. Section list markup
Files: `App/app/templates/_property_editor.html` (sections are `<details class="prop-sec" id="sec-basics|sec-messages|sec-police|sec-fee|sec-calendars|sec-lock">`, about lines 140, 211, 289, 367, 418, 426).
Add above the form's first `<details>` a `<nav class="prop-nav" aria-label="...">` with one `<a href="#sec-...">` per section, a dot span (same g/r/n logic already in each summary) and the title (reuse existing `t('property_page.sec.*.title')` keys). Order: basics, police, calendars, messages, lock, fee. Wrap the nav and the `<form>` in `<div class="prop-layout">`. Add `prop-phone-hide`-style class `prop-wide-only` to the nav.
Test (test-map row "Onboarding, properties"): from `App/`: `.venv/bin/python -m pytest tests/test_property_*.py -q --tb=short -x 2>&1 | tail -30`.
Done: tests green; nav renders (grep the rendered HTML via the test or `grep -c prop-nav` in the template).

### Step 2. Replace cards and setup box at wide widths
Files: `_property_editor.html` (the status cards and "Continue setup"/readiness block above the form, anchor `readiness-group`, about line 85 to 120) and `App/app/static/app2.css`.
Add a class `prop-phone-only-block` to that wrapper (check the existing class name with `grep -n 'prop-phone-only' App/app/static/app2.css` and reuse it) so it shows only below 768. In app2.css add `@media (min-width:768px)` rules to hide it. Do not delete markup.
Test: same as step 1 plus `tests/test_0786_settings_geometry_browser.py` (0 skipped, `-rs`).
Done: no status card visible at 768/1280 in a quick screenshot.

### Step 3. Layout and one-section-at-a-time CSS
File: `App/app/static/app2.css`, inside a NEW `@media (min-width:768px)` block appended near the existing `.prop-sec` rules (grep `prop-sec` lines ~995 to 1015 are the phone rules; leave them).
CSS: `.prop-layout` two columns (nav 220 px sticky, content max 640 px, gap 32 px); nav links 48 px high, rounded 12 px, current one tinted `--accs`; `.prop-sec` rendered as an open flat card (hide the `<summary>` chevron and sub-state text, show title only as heading); hidden sections via `.prop-layout.is-tabbed .prop-sec:not(.is-current){display:none}`. Apply the spacing scale. Remove nothing for phone.
Test: `test_0786_settings_geometry_browser.py` and `tests/test_design_guardrails_browser.py` (0 skipped).
Done: both green.

### Step 4. JS: section switching and error line
Files: `App/app/static/app.js` (grep `initSaveSummary`, `initStayFeeStars`; add a new `initPropertyTabs()` next to them and call it where they are called), `App/app/templates/_property_editor.html` (error line container `<p class="prop-fixline" data-prop-fixline hidden>`).
Behaviour (only when `matchMedia('(min-width:768px)')` matches; re-evaluate on change): add `is-tabbed` to `.prop-layout`; show the `.prop-sec` matching `location.hash` / nav click (set `is-current`, force `open` on the details, update hash with `history.replaceState`); build the fix line from existing invalid/required fields: text "Fix N fields: " plus links (field label text, `href="#fieldid"`); click switches to the field's section and focuses the field. Reuse the data `initSaveSummary` already reads for missing fields; do not add a second source. i18n: add two keys (`property_page.fix_fields`, `property_page.fix_fields_one`) to the translation files the other `property_page.*` keys live in (grep one key to find them), all languages present there, no em dashes.
No new dependency. No JS: nothing changes.
Test: `tests/test_property_*.py`, `tests/test_property_navigation_browser.py`, `tests/test_*_i18n.py tests/test_no_em_dashes.py` (0 skipped for the browser one).
Done: green.

### Step 5. Remove duplicate errors and prune "?" help
Files: `_property_editor.html`, and the server error list: `grep -rn 'save_errors' App/app --include=*.py` (named in the task as admin.py save_errors); change nothing server-side unless the message is rendered twice there; keep messages for the no-JS and phone paths.
At >= 768 hide the per-field `.field-error`/readiness "why" text via CSS (new media block). In the template, for each help "?" outside police, stay fee, smart lock: delete the help-tip and move its text into the input `placeholder` or a one-line `ui-hint` under it if the text carries information; delete it if it only repeats the label. Keep field `name`/`id` unchanged. Do NOT touch label text used by tests (grep a label before editing).
Test: `tests/test_property_*.py tests/test_*_i18n.py tests/test_flash_literals.py` and browser rows below.
Done: green; "?" count per section <= 3 (`grep -c help-tip` per section range).

### Step 6. Update tests that pin the old layout (owner-decision comments)
Files: `App/tests/test_property_navigation_browser.py` (`SETTINGS_NAMES`, line ~38; assertion line ~173) and `App/tests/v2_mockup.py` (`WIDE_OVERRIDES`, line ~63).
Saved field names must stay identical: if `SETTINGS_NAMES` still matches, leave it. Only if a browser assertion expects all sections visible at wide widths, change it to open the section first. Add to every changed pin the comment `# Owner decision 2026-11-08: property editor redesigned at >=768px (brief 1030); phone unchanged.` For `WIDE_OVERRIDES`, add entries (with the same comment) only for selectors in `tests/test_0710_v2_mockup_match_browser.py` that now differ, found by running it.
Test: `tests/test_property_navigation_browser.py tests/test_0710_v2_mockup_match_browser.py` (0 skipped).
Done: green. A fix that needs more than the pins above: STOP and report.

### Step 7. Cache keys
Files: `App/app/static/app2.css`, `App/app/static/app.js` changed, so bump their `?v=` in `App/app/templates/base.html` (grep `app2.css`, `app.js`) to `20261108-1030` and update `App/tests/static_versions.json` (`sha256` and `v`) for those two files. Use the repo's way: `grep -rn static_versions scripts App/tests/test_static_versions.py | head -5` to find the update command; otherwise compute `sha256sum` by hand.
Test (test-map "Static files"): `.venv/bin/python -m pytest tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py -q --tb=short -x 2>&1 | tail -30`.
Done: green.

### Step 8. UX gate (workflow.md#ux-gate; rule 10)
From `App/`: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py -rs -q -x 2>&1 | tail -30`: green, 0 skipped, zero findings on host pages. Never silence a finding.
Copy the property-editor screenshots at 390, 768, 1280 from `/tmp/shots/layout-lint/` to `/mnt/project-files/ux-shots/editor-redesign/` (create it). Open each once. 390 must look like the old accordion page. Tick `docs/design/design-system.md` checklist (section 5b: `ui-section-card`, `ui-page-narrow`, no nested boxes, help "?" beside title) in the PR. PR body per page: "390: ...; 768: ...; 1280: ...". If the executor hits its tool cap, report `Done: steps 1 to k. Left: ...` per executor.md.

## 5. Do not touch
Anything under `App/app/migrations/`, auth code, saved field names, phone (<768 px) CSS, `main`, secrets, deploy.

## 6. Commands
The per-step test commands above, run from `App/`, each ending `2>&1 | tail -30`. No full suite.

## 7. Acceptance
- [ ] At >= 768: left section list with status dots, one section shown, no status cards, no Continue-setup box, one slim "Fix N fields" line, no repeated error text, <= 3 "?" per section.
- [ ] 390 unchanged (accordion).
- [ ] Without JS all sections visible, forms post as before; saved field names unchanged.
- [ ] No new dependency, no new outbound request, light mode only, no tracking cookies change.
- [ ] Pins updated with the dated owner-decision comment; static versions bumped; layout lint green; screenshots in `/mnt/project-files/ux-shots/editor-redesign/`.

## 8. Stop and ask
Anchor not found, a test fails twice, or a step needs a file not named here: STOP, write the report with `Status: blocked`, ask. Do not guess. Owner steps after merge: none besides the usual manual deploy.

## 9. Report
Write `docs/tasks/1030-editor-redesign-report.md` (600 tokens max): files changed, each command with last 5 lines, section 7 ticked, Deviations, Questions. Then `Status: review` and one PR.
