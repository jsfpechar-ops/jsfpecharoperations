# 1091: S17 guest form title on one line at 390 px (guest form option B)

Status: todo
Tier: C | Depends on: none (goes first among the open briefs that name `guest.css`, `guest/base.html` or `static_versions.json`; 0885 is already in main, its `g-head-help` rules are in `guest.css`; a later brief re-bumps the key from `20261110-1091a`) | Base: origin/main | Branch: claude/1091-guest-title-one-line
Executor: Sonnet (Tier C) | Attempts: 3 at most | Fits one session: stop at 60 tool calls or 60k tokens (section 8); reads stay at 150 lines or fewer
Review: orchestrator checks the diff and the screenshots against the mockup before the PR opens.
Report: docs/tasks/1091-report.md

## 1. Objective

Owner decision 2026-11-10 ("B now"), plan [speed-and-ease](../plans/speed-and-ease.md) queue item **S17**: on a 390 px phone the guest registration form title "Guest registration" wraps to 2 lines, which pushes the first field down and the button further below the fold. Make the English title fit on one line, as mockup B shows (scope by language: section 2 table). Nothing else in the form changes: every required field, the legal tick, the wizard steps and the copy stay as they are.

Mockups (look at both once, they show the target): `/mnt/project-files/mockups/guest-form/A-today-4-details-fold.png` (today, 2 lines) and `B-title-fix-details-fold.png` (target, 1 line, same words, smaller type). Context: `/mnt/project-files/mockups/README.md` Part 1, option B.

**Chosen fix: CSS only.** The mockup keeps the same words and shrinks the type; shorter copy would mean touching 6 language files and the translations. The title is the i18n key `title` (`App/app/i18n.py`: en line 105, cs 874, de 1632, es 2175, fr 2718; `App/app/guest_uk_i18n.py:113`), rendered by `<h1>{% block heading %}{{ t('title') }}` in `App/app/templates/guest/base.html:24`. Do not edit any i18n file or template.

## 2. Context

The rule that makes it 28 px is in `App/app/static/guest.css` line 89, and only the form page carries the class (`{% block wrap_class %}g-checkin-page{% endblock %}`, `guest/form.html:16`):

```
.g-head h1 { font-size: 25px; ... }                                   /* line 82 */
.g-checkin-page .g-head h1 { font-size: 28px; letter-spacing: -0.025em; }   /* line 89 */
```

At 390 px the header row holds the property mark, the title column (`flex: 1; min-width: 0`) and the language button, so the title has about 232 px. Measured in Chromium on this branch (review, 2026-11-10; real `tokens.css` + `guest.css`, the `base.html` header markup, title width / room in px):

| Language | Title | 28 px today | 24 px | One line needs |
|---|---|---|---|---|
| en | Guest registration | 2 lines (233 / 232) | **1 line** (200) | 24 px |
| de | Gästeregistrierung | 1 line, overflows by 13 px (245) | **1 line** (210) | 24 px |
| uk | Реєстрація гостей | 2 lines | 1 line (211, system font: Manrope has no Cyrillic) | 24 px |
| es | Registro de huéspedes | 2 lines | 2 lines (256) | 21 px |
| cs | Registrace ubytovaného | 2 lines | 2 lines (272) | 20 px |
| fr | Enregistrement des voyageurs | 2 lines | 2 lines (342) | 16 px |

So 24 px gives one line in en, de and uk. Czech, Spanish and French stay on 2 lines (each line 5 px lower than today, so they gain a little and lose nothing). No sane size fixes them: Czech would need 20 px, which is smaller than the 21 px card heading "Your details" under it. **Do not go below 24 px and do not add per-language rules**; shorter cs/es/fr copy is the owner question in section 8. English also fits at 375 and 360 px (200 px of 217 and 202) and wraps at 320 px, which is accepted.

Fix: inside one media query for narrow phones, set the form-page title to 24 px. The 768 and 1280 layouts keep 28 px (there is room), so they must not change.

Check these anchors with `grep -nF` first; if one is missing, STOP: `.g-checkin-page .g-head h1 { font-size: 28px;` in `App/app/static/guest.css`, `g-checkin-page` in `App/app/templates/guest/form.html`, `"title": "Guest registration"` in `App/app/i18n.py`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/static/guest.css` | edit | add the narrow-phone rule right after line 89 (step 1) |
| `App/app/templates/guest/base.html` | edit | bump the one `guest.css?v=` key (line 14, now `20261110-1074a`) to `20261110-1091a` |
| `App/tests/static_versions.json` | regenerate | by `tests/test_static_versions.py --write` (step 2); never by hand, the entry also holds the file's sha256 |
| `App/tests/test_guest_title_1091_browser.py` | create | the one-line test (step 3) |
| `docs/tasks/screenshots-1091/` | create | the 3 screenshots, one per width (section 6) |
| `docs/tasks/1091-report.md` | create | the report, and set this brief `Status: review` |

## 4. Steps (commit after each: `1091 step k`)

1. Confirm the anchors (section 2). Add to `guest.css` right after line 89:
   ```
   @media (max-width: 480px) {
     .g-checkin-page .g-head h1 { font-size: 24px; }
   }
   ```
   Exactly these 3 lines. Do not repeat `letter-spacing` (line 89 still applies it). No other property, no other selector, no `white-space: nowrap` (a long title in another language must still be allowed to wrap rather than overflow or be cut).
2. In `guest/base.html` line 14 replace `guest.css?v=20261110-1074a` with `guest.css?v=20261110-1091a` (do not touch `templates/guest/archive/`). Then from `App/` run `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5`: it rewrites `tests/static_versions.json` (new key and new sha256 for `guest.css`; `git diff` must show only that one entry changed). Commit both files.
3. Create `test_guest_title_1091_browser.py`. Copy the app, page and guest-link setup from `App/tests/test_guest_form_draft_1087_browser.py` (its imports and its `_open_url(live_server, monkeypatch, part, lang)`, which opens the new-guest form step 1; do not invent a new fixture). `tests/conftest.py` already switches on all six guest languages. Measure `h1 = document.querySelector('.g-head h1')` after `document.fonts.ready`; "one line" means `h1.getBoundingClientRect().height <= parseFloat(getComputedStyle(h1).lineHeight) * 1.1` and `h1.scrollWidth <= h1.clientWidth`. Four tests:
   - a. Viewport 390 x 844, parametrized over `en` and `de`: the `h1` text equals `i18n.translator(lang)("title")` (`from app import i18n`, as the 1087 file imports it) (this proves the page is really in that language, not fallen back to English); the `h1` is one line; its computed `font-size` is `24px`.
   - b. Viewports 768 x 1024 and 1280 x 800, `en`: computed `font-size` is `28px` and the `h1` is one line.
   - c. Viewport 390 x 844, `en`: each of these is in the DOM (`count() >= 1`), so the change hid nothing: `#guest-form`, `[name="first_name"]`, `[name="surname"]`, `[name="birth_date"]`, `[name="nationality"]`, `[name="doc_number"]`, `[name="legal_ack"]`. (The tick lives in `guest/_legal_notice.html`, which the form includes.) If one count is 0, STOP: do not rename or drop the check.
   - d. Viewport 390 x 844, parametrized over `cs`, `es`, `fr`, `uk`: assert only that the `h1` text is not the English title and that `h1.scrollWidth <= h1.clientWidth` (it wraps, it is never cut); `print` the line count (`round(height / lineHeight)`) and copy the 4 numbers into the report. Expected: cs 2, es 2, fr 2, uk 1 (uk depends on the machine's Cyrillic font, so it is not asserted).
4. Run section 6, take the screenshots (its last part), write the report.

## 5. Do not touch

Every i18n file, every template, the routes, the other guest pages, `host*.css`, `layout_lint.js`, `db.py`, migrations, any dependency. No JavaScript. Never push to `main`.

## 6. Commands (each ends `2>&1 | tail -30`; from `App/`; never the full suite)

Test-map rows (`docs/context/test-map.md`): "Guest pages, guest templates" and "Static files under App/app/static (any), cache keys".

1. `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_guest_title_1091_browser.py -q --tb=short -x 2>&1 | tail -30`: green, 0 skipped.
2. `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_guest_*.py tests/test_guest_browser_e2e.py -q --tb=short -x 2>&1 | tail -30`: green, **0 skipped** (the browser tests must run, not skip; if any skips, report the reason and STOP).
3. `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_guest_ocr_geometry_browser.py tests/test_layout_lint_browser.py -q --tb=short -x 2>&1 | tail -30`: green, 0 skipped (the geometry test of the changed guest page; the layout lint reports guest findings only, but look at them and name any new one).
4. `.venv/bin/python -m pytest tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py tests/test_form_chrome.py tests/test_privacy_first.py -q --tb=short -x 2>&1 | tail -30`.
5. Repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

### Screenshots (rules 7 and 10)

Page changed: the guest registration form, step 1 "Your details" (English, mock data, first screen). Take it at **390, 768 and 1280 px** into `docs/tasks/screenshots-1091/form-{390,768,1280}.png` (a fifth test in the new file, written the way `test_guest_form_draft_1087_browser.py` line 289 writes `docs/tasks/screenshots-1087/`, but with `full_page=False`: the first screen is the point). Open each once and write one line per width in the report: at 390 the title is on one line, the property name is under it, the language button is not squeezed or overlapping, the first field is higher than in A-today; at 768 and 1280 nothing moved. Compare with the mockup B. Do not retake to hide a problem.

## 7. Acceptance

- [ ] The form title is one line at 390 px in en and de at 24 px; the 768 and 1280 title stays 28 px on one line. cs, es, fr, uk line counts are in the report (not a failure when cs, es, fr are 2).
- [ ] Diff is `guest.css` (one media rule), the cache key in two places, the new test, screenshots and report. No i18n, template body, route or field change; every required field and the legal tick are still in the form (test c).
- [ ] Section 6 commands 1 to 5 green, 0 skipped in 1 to 3.
- [ ] Three screenshots in the report with one line each.
- [ ] `git diff --stat origin/main` touches only section 3 files. Never push to `main`.

## 8. Stop and ask

STOP and report `blocked` if: an anchor is missing; a browser test skips; the title still wraps at 24 px in en or de (never go below 24 px, never add `white-space`, `overflow`, `:lang()` or a second size); a test fails twice on the same cause (attempt 3 of 3); 60 tool calls or 60k tokens (finish the step, commit, `Done: steps 1 to k. Left: steps k+1 to n.`).

Open question for the owner (put it in the report with the 4 measured line counts, do not decide it): at 390 px the Czech, Spanish and French titles stay on 2 lines at 24 px (section 2 table). Only shorter copy would fix them, for example cs "Registrace hosta", es "Registro de huésped", fr "Fiche des voyageurs"; that needs owner approval and a native reader, and is a separate brief (i18n files and the tests that pin the titles).

## 9. Report

`docs/tasks/1091-report.md`, 400 tokens at most: files, each command with its last 5 lines, section 7 ticked, the 3 screenshot lines, the cs/es/fr/uk line counts, deviations and questions. Set this brief `Status: review`. Then open one PR (draft until the owner says it may ship). Body: CSS-only title size at 390 px, no new request, no personal data, no dependency; paste the screenshot lines and tick the [design-system checklist](../design/design-system.md).
