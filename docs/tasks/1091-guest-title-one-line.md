# 1091: S17 guest form title on one line at 390 px (guest form option B)

Status: todo
Tier: C | Depends on: none | Base: origin/main | Branch: claude/1091-guest-title-one-line
Executor: Sonnet (Tier C) | Attempts: 3 at most | Fits one session: stop at 60 tool calls or 60k tokens (section 8); reads stay at 150 lines or fewer
Review: orchestrator checks the diff and the screenshots against the mockup before the PR opens.
Report: docs/tasks/1091-report.md

## 1. Objective

Owner decision 2026-11-10 ("B now"), plan [speed-and-ease](../plans/speed-and-ease.md) queue item **S17**: on a 390 px phone the guest registration form title "Guest registration" wraps to 2 lines, which pushes the first field down and the button further below the fold. Make the title fit on one line. Nothing else in the form changes: every required field, the legal tick, the wizard steps and the copy stay as they are.

Mockups (look at both once, they show the target): `/mnt/project-files/mockups/guest-form/A-today-4-details-fold.png` (today, 2 lines) and `B-title-fix-details-fold.png` (target, 1 line, same words, smaller type). Context: `/mnt/project-files/mockups/README.md` Part 1, option B.

**Chosen fix: CSS only.** The mockup keeps the same words and shrinks the type; shorter copy would mean touching 6 language files and the translations. The title is the i18n key `title` (`App/app/i18n.py`: en line 105, cs 874, de 1632, es 2175, fr 2718; `App/app/guest_uk_i18n.py:113`), rendered by `<h1>{% block heading %}{{ t('title') }}` in `App/app/templates/guest/base.html:24`. Do not edit any i18n file or template.

## 2. Context

The rule that makes it 28 px is in `App/app/static/guest.css` line 89, and only the form page carries the class (`{% block wrap_class %}g-checkin-page{% endblock %}`, `guest/form.html:16`):

```
.g-head h1 { font-size: 25px; ... }                                   /* line 82 */
.g-checkin-page .g-head h1 { font-size: 28px; letter-spacing: -0.025em; }   /* line 89 */
```

At 390 px the header row holds the property mark (about 54 px with its gap), the title column (`flex: 1; min-width: 0`) and the language button (about 64 px with its gap), so the title has about 216 px. "Guest registration" at 28 px is about 235 px: it wraps. At 24 px it is about 200 px: it fits, which is what the mockup shows (about 182 px).

Fix: inside one media query for narrow phones, set the form-page title to 24 px. The 768 and 1280 layouts keep 28 px (there is room), so they must not change.

Check these anchors with `grep -nF` first; if one is missing, STOP: `.g-checkin-page .g-head h1 { font-size: 28px;` in `App/app/static/guest.css`, `g-checkin-page` in `App/app/templates/guest/form.html`, `"title": "Guest registration"` in `App/app/i18n.py`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/static/guest.css` | edit | add the narrow-phone rule right after line 89 (step 1) |
| `App/app/templates/guest/base.html` | edit | bump the one `guest.css?v=` key (line 14, now `20261110-1074a`) to `20261110-1091a` |
| `App/tests/static_versions.json` | edit | the matching entry for `guest.css` (grep `20261110-1074a`) |
| `App/tests/test_guest_title_1091_browser.py` | create | the one-line test (step 3) |
| `docs/tasks/screenshots-1091/` | create | the 9 screenshots (section 6) |
| `docs/tasks/1091-report.md` | create | the report, and set this brief `Status: review` |

## 4. Steps (commit after each: `1091 step k`)

1. Confirm the anchors (section 2). Add to `guest.css` right after line 89:
   ```
   @media (max-width: 480px) {
     .g-checkin-page .g-head h1 { font-size: 24px; }
   }
   ```
   Keep `letter-spacing` from the line above. No other property, no other selector, no `white-space: nowrap` (a long title in another language must still be allowed to wrap rather than overflow or be cut).
2. Bump the cache key in `guest/base.html` and `static_versions.json` (both must carry the same new key; `test_static_versions.py` checks it).
3. Create `test_guest_title_1091_browser.py`. Copy the app, page and guest-link setup from `App/tests/test_guest_form_draft_1087_browser.py` (open the new-guest form step 1 the same way; do not invent a new fixture). For languages `en`, `cs`, `de`, `es`, `uk` (via `?lang=` as that file does) at viewport 390 x 844: the `h1` inside `.g-head` has a rendered height of one line (`h1.getBoundingClientRect().height <= parseFloat(getComputedStyle(h1).lineHeight) * 1.1`) and `h1.scrollWidth <= h1.clientWidth`. At 768 and 1280 (en): the computed `font-size` of that `h1` is still `28px`. At 390 (en): the computed `font-size` is `24px`. Use `fr` in a separate test that only records the line count and asserts nothing (see section 8 question): "Enregistrement des voyageurs" is long and may wrap; that is accepted for now.
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

Page changed: the guest registration form, step 1 "Your details" (English, mock data, first screen). Take it at **390, 768 and 1280 px** into `docs/tasks/screenshots-1091/form-{390,768,1280}.png` (the way `test_guest_form_draft_1087_browser.py` writes `docs/tasks/screenshots-1087/`). Open each once and write one line per width in the report: at 390 the title is on one line, the property name is under it, the language button is not squeezed or overlapping, the first field is higher than in A-today; at 768 and 1280 nothing moved. Compare with the mockup B. Do not retake to hide a problem.

## 7. Acceptance

- [ ] The form title is one line at 390 px in en, cs, de, es, uk; the 768 and 1280 title stays 28 px.
- [ ] Diff is `guest.css` (one media rule), the cache key in two places, the new test, screenshots and report. No i18n, template body, route or field change; every required field and the legal tick still render.
- [ ] Section 6 commands 1 to 5 green, 0 skipped in 1 to 3.
- [ ] Three screenshots in the report with one line each.
- [ ] `git diff --stat origin/main` touches only section 3 files. Never push to `main`.

## 8. Stop and ask

STOP and report `blocked` if: an anchor is missing; a browser test skips; the title still wraps at 24 px in en (do not go below 22 px without asking); a test fails twice on the same cause (attempt 3 of 3); 60 tool calls or 60k tokens (finish the step, commit, `Done: steps 1 to k. Left: steps k+1 to n.`).

Open question for the owner (put it in the report, do not decide it): French "Enregistrement des voyageurs" likely stays 2 lines at 390 px even at 24 px. The only fix would be shorter French copy (for example "Fiche des voyageurs"), which needs owner and translator approval.

## 9. Report

`docs/tasks/1091-report.md`, 400 tokens at most: files, each command with its last 5 lines, section 7 ticked, the 3 screenshot lines, the `fr` line count, deviations and questions. Set this brief `Status: review`. Then open one PR (draft until the owner says it may ship). Body: CSS-only title size at 390 px, no new request, no personal data, no dependency; paste the screenshot lines and tick the [design-system checklist](../design/design-system.md).
