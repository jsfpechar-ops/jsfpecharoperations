# 0496: redesign step 1: Manrope font, no phone top bar, coral light shell
Status: todo
Depends on: none | Base commit: origin/main | Branch: task/0496-redesign-shell
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
## 1. Objective
Owner approved the redesign direction on 2026-11-01 (mockup: `/mnt/project-files/ux-redesign/ubyhost-redesign-v2.html`, read it for look and feel; "Wolt for Work" geometry, our coral, light sidebar). Step 1 changes only the shell, so every page picks it up at once: (a) the Manrope font, self-hosted; (b) no top bar on phone; (c) the light sidebar and tab bar with coral active state; (d) page titles with the short coral underline. No page content, route, copy or logic changes.
## 2. Context
- Font: `App/app/static/tokens.css:62` `--font-sans`; fonts live in `App/app/static/fonts/` (DejaVu, Dancing Script only). No third-party font requests are allowed (rule 2): vendor the files.
- Top bar: `_shell_topbar.html`, include at `base.html:37`; CSS in `host2.css` (`.ui-topbar` lines ~285, 329-330, 669, 1113, 1116-1117). `--topbar-h` stays (`.ui-brand` uses it). Search stays reachable: sidebar search row (desktop) and the More sheet first row (phone).
- Tests: `test_design_shell.py:11` asserts the top bar; `test_host_feedback_browser.py:272` comment names it.
- Rules: `docs/design/MASTER.md` §4 (coral budget), §6.2 item 5, §7.7 (selected chip is ink, not coral). Owner wants more coral personality now, so update these text rules to match what you build. `scripts/design_lint.py` and `test_design_guardrails_browser.py` enforce parts of them.
## 3. Files
Create `App/app/static/fonts/Manrope-latin.woff2`, `Manrope-latin-ext.woff2`, `Manrope-vietnamese.woff2`, `LICENSE-Manrope.txt`. Edit `tokens.css`, `host2.css`, `base.html` (remove include; bump `host2.css?v=`), delete `_shell_topbar.html`, edit `test_design_shell.py`, `test_host_feedback_browser.py` (comment only), `docs/design/MASTER.md`, `docs/design/catalog.json` (drop `ui-topbar`), `docs/design/pages/havel.md:15` (drop the topbar launcher mention). Write `docs/tasks/0496-report.md` and `docs/tasks/screenshots-0496/`. Nothing else.
## 4. Steps
1. Font: in an empty directory `/tmp/fnt` run `npm pack @fontsource-variable/manrope` and unpack; copy the variable `wght` woff2 files for the latin, latin-ext and vietnamese subsets (OFL license file too) into `static/fonts/`. `@font-face` in `tokens.css` per subset with `unicode-range` copied from the package css, `font-weight: 200 800`, `font-display: swap`; `--font-sans` becomes `Manrope, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif`. Preload only the latin file in `base.html`. Check with Python `fontTools` in a throwaway venv (not a project dependency) that the three files together contain every letter of `ĚŠČŘŽÝÁÍÉÚŮĎŤŇěščřžýáíéúůďťň` and of `ăâêôơưđ àảãáạ èẻẽéẹ ìỉĩíị òỏõóọ ùủũúụ ỳỷỹýỵ` (upper and lower case). If any is missing, stop and report.
2. Top bar: delete `_shell_topbar.html`, its include, and the `.ui-topbar` rules and `host-topbar` view-transition entries (keep `host-rail` and `host-tabbar`). If phone `main` loses its top spacing, add `padding-top: var(--space-4)` to the existing phone rule for `.host-workspace main.with-sidebar`, no new selector.
3. Coral shell, only in `host2.css`, using existing tokens (`--accent`, `--accent-soft`, `--accent-ink`): sidebar and tab bar stay white; active item = `--accent-soft` background, `--accent-ink` label 600, icon in `--accent`; page title (`h1` in the page header component, see MASTER §5.1) gets a 28 px by 3 px `--accent` underline below it; selected filter chip = `--accent` fill with white text (MASTER §7.7 updated to say so); table row hover tint `--accent-soft` at 40 percent. Nothing else changes.
4. Update the MASTER, catalog and havel.md text as in §3. Update the two tests as in §2: `assert 'class="ui-topbar"' not in page`, and assert the More sheet still has `class="ui-menu-item" type="button" data-command-open`.
## 5. Do not touch
Routes, Python in `App/app/`, other templates, `shell.js`, `app.js`, copy and translation files. No new Python or npm dependency (the npm pack is a one-off download).
## 6. Commands
From `App/`: `.venv/bin/python -m pytest tests/test_design_shell.py tests/test_design_tokens.py tests/test_privacy_first.py -q --tb=short -x 2>&1 | tail -15`; `.venv/bin/python ../scripts/design_lint.py 2>&1 | tail -15`; `.venv/bin/python -m pytest tests/test_host_geometry.py tests/test_host_feedback_browser.py tests/test_design_guardrails_browser.py -q --tb=short -x 2>&1 | tail -15` (0 skipped). Repo root: `python3 scripts/context_lint.py | tail -3`.
## 7. Acceptance
All pass, 0 skipped. 390 px and 1280 px screenshots of `/` and `/reservations` in `docs/tasks/screenshots-0496/` show: Manrope, no top bar on phone, coral active nav, title underline. Czech and Vietnamese sample text renders without fallback glyphs (screenshot one Vietnamese page, lang `vi`).
## 8. Stop and ask
Stop if a font glyph is missing, if `design_lint.py` or a guardrail test needs more than the MASTER update to pass, or if any test other than the two named changes result.
## 9. Report
`docs/tasks/0496-report.md`: pytest and lint tails, `git diff --stat origin/main`, screenshot paths.
