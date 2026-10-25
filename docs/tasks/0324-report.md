# 0324 report: Havel panel

Status: review
Base: 1c78d95 (pre-0324 HEAD). Branch task/0324-havel-panel (already checked out; step 1 skipped).

## Files changed
`git diff --stat 1c78d95..HEAD` covers the 0324 commits (steps 2 to 9 and fix): `_havel_panel.html` (new), `havel.js` (new), `templating.py`, `base.html`, `_shell_sidebar.html`, `_shell_topbar.html`, `_shell_tabbar.html`, `host2.css`, `static_versions.json`, `catalog.json`, `MASTER.md`, `pages/havel.md`, `test_havel_panel.py` (new), `test_havel_browser.py` (new), 3 PNGs.

## Commands (last lines)
- `from app.main import app`: `import-ok`
- `test_havel_panel.py test_havel_topics.py test_havel_page.py`: `13 passed`
- `test_havel_browser.py` (1280 and 390): `2 passed`, 0 skipped
- `test_design_guardrails_browser.py test_a11y_guard_browser.py test_static_versions.py test_havel_browser.py test_havel_panel.py`: 19 passed, then `test_static_versions.py` after the key bump: `7 passed` (with panel and browser), 0 skipped
- `design_lint.py`: `design lint: OK`
- `context_lint.py`: `context lint: OK`

## Section 7
- [x] Sidebar item above Help and guide, computer panel 400 x 680 max, five topics, title, close; Escape returns focus.
- [x] 390: 44 px top-bar button, full-width sheet at 92dvh, More row opens the panel, no horizontal scroll.
- [x] Topic, question, answer by fetch; "Ask Havel" sets topic and q.
- [x] Enter sends; writing bubble; answer focused (Shift+Enter and network-error Retry not exercised by a test).
- [x] Without JS launchers are `/havel` links (route test); `/havel` has no panel.
- [x] Three screenshots in `docs/tasks/screenshots-0324/`, looked at; guards pass, 0 skipped; design lint OK; manifest written.

## Screenshots
- panel-topics-390.png: phone sheet full width, five topics at the bottom, large empty gap above them.
- panel-topic-1280.png: computer panel bottom-right, topic page with "Add or change a stay" breadcrumb.
- panel-answer-1280.png: answer bubble focused (red ring), host question on top. Send wraps below the counter line.

## Deviations
- Step 1 skipped: branch already checked out.
- Cache keys: base.html `host2.css` and `havel.js` are `20261025-0324b`, not `20261024-0324`. The manifest refuses same-version content changes, so the key was bumped again after the CSS and JS fixes. The host2 bump was done in step 3.
- `_havel_panel.html` header comment contains `havel-sheet`, so `grep -c` prints 2, not 1 (the dialog line is 1).
- Test: `aria-current` assertion split on the first `havel-launcher`, which is the top-bar button; now a regex on the sidebar launcher.
- Browser test: host bubble count is `before + 1` (the 0313 fragment already carries the host bubble).
- havel.js: local echo bubble is removed on success and error (it duplicated the server bubble); `echo()` returns the element.
- host2.css: the `width` rule moved into the `min-width: 768px` block (on phone it made the sheet 342 px, not 390).
- havel.js uses `innerHTML` for the server fragment only (as briefed); writing and error bubbles use fixed text. A security hook warned on this.

## Questions
- Send button wraps below the counter line on the answer screen at 1280. Keep, or move it onto the row?

## Owner steps left
1. Review the three screenshots, then open the PR.
2. Staging: Havel (AI) at the bottom of the left menu, topic, "Still need help? Ask Havel", send a question, check the counter drops.
3. Phone: chat icon top right beside search; More tab has "Havel (AI)".
