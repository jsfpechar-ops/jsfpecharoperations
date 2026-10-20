# 0166: accessibility guard (WCAG 2.2 AA, the GOV.UK standard) in CI

Status: review
Depends on: 0165 | Branch: claude/project-thread-5hw8cf
Executor: Haiku 5.5 | Fits one session

## 1. Objective

The owner wants the app to follow the UK government accessibility rules for public sector sites, which means WCAG 2.2 level AA (gov.uk/guidance/accessibility-requirements-for-public-sector-websites-and-apps). Add a browser check that fails the build on the testable parts of it, on every host page, in English and Czech. This brief builds the check and reports what it finds. It does not fix any finding: fixes are separate briefs, so the new test is EXPECTED to fail when you finish.

## 2. Context

Same pattern as the layout guard: `App/tests/design_guard.js` plus `App/tests/test_design_guardrails_browser.py` (read its first 115 lines first). The page script is already written and syntax-checked at `/mnt/project-files/design-reset/tools/a11y_guard.js`: copy it unchanged to `App/tests/a11y_guard.js`. It takes the expected page language (`"en"` or `"cs"`) and returns findings `[rule, ...details]` for: html lang, page title, one h1, heading order, one main, labelled navs, skip link, controls without an accessible name, generic link text, images without alt, duplicate ids, broken aria references, navs with no current item, text contrast, and targets smaller than 24 by 24. The keyboard, reflow and text-spacing checks are written in Python in step 2 below. No new dependency: no axe-core, no npm package.

## 3. Files

`App/tests/a11y_guard.js` (copy), `App/tests/test_a11y_guard_browser.py` (create), `.github/workflows/ci.yml` (one line), `docs/design/MASTER.md` (one section), `docs/tasks/0166-*`.

## 4. Steps

1. `cp /mnt/project-files/design-reset/tools/a11y_guard.js App/tests/a11y_guard.js`.
2. Create `App/tests/test_a11y_guard_browser.py`. Start from the imports, fixtures, `ROUTES` and route formatting in `test_design_guardrails_browser.py` (import `ROUTES`, `REQUIRE_BROWSER`, `sync_api` and the helpers from it with `from test_design_guardrails_browser import ROUTES, REQUIRE_BROWSER, sync_api, wide_host, wide_base, _wait_for_host_layout, _dismiss_optional_security_prompt, chromium_launch_kwargs, auth` and add `# noqa: F401` the same way; if a name is not importable from there, import it from where that file gets it). Write one helper `_routes(wide_host)` that returns the formatted route dict exactly as the first test does, and four tests. Each writes its findings to `/tmp/ubyhost-a11y-<name>.json` and fails with `assert not findings, f"{len(findings)} findings {counts}\n" + "\n".join(lines[:40])`, where `counts` groups by rule name, as the first test does.
   - `test_every_page_passes_the_page_checks`: for `lang` in `("en", "cs")` and width in `(390, 1280)` (sidebar open), visit every route with `?lang=<lang>` (use `&` when the path has a `?`), wait with `_wait_for_host_layout`, dismiss the prompt, run `page.evaluate(A11Y, lang)` where `A11Y` is the text of `a11y_guard.js`, and collect `(route, lang, width, finding)`.
   - `test_keyboard_focus_is_visible_and_not_covered`: at width 1280, language en, for every route press Tab up to 40 times (stop when focus returns to `body`). After each press evaluate in the page: the active element's `getComputedStyle` `outlineStyle`, `outlineWidth`, `boxShadow`, whether its bounding box has width and height above 0, and whether `document.elementFromPoint` at the box centre is the element or a descendant or ancestor of it. Findings: `["focus-not-visible", label]` when the element has neither an outline of at least 2px (style not `none`) nor a non-`none` box-shadow; `["focus-obscured", label]` when the centre point belongs to a different element that is not an ancestor or descendant. Skip elements that are not visible. Label is tag, id, and first 30 characters of the text.
   - `test_pages_reflow_at_320_and_200_percent`: for width in `(320, 640)`, language en, sidebar open, every route: finding `["page-scroll", scrollWidth, width]` when `document.documentElement.scrollWidth > width + 1`; then run the existing `design_guard.js` (`GUARD`, read it the same way as the first test, argument `width < 1024`) and keep only findings named `text-clipped`, `spills-out-of-row`, `past-right-edge` and `under-rail`.
   - `test_pages_survive_wide_text_spacing`: at width 1280 and 390, language en, every route, after loading add the style `* { line-height: 1.5 !important; letter-spacing: 0.12em !important; word-spacing: 0.16em !important; } p { margin-bottom: 2em !important; }` with `page.add_style_tag(content=...)`, wait 100 ms, run `GUARD`, and keep only `text-clipped`, `spills-out-of-row`, `page-scroll`, `past-right-edge` and `buttons-misaligned` findings.
3. Run: `cd App && UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium .venv/bin/python -m pytest tests/test_a11y_guard_browser.py -q -rs -p no:cacheprovider 2>&1 | tail -60` (foreground, timeout 900000). Expected: the tests run to completion (no Python error, 0 skipped) and some or all FAIL with findings. If a test errors for a Python reason (not a finding), fix the test code and rerun once. Then from the repo root `git checkout -- docs/tasks/0102-evidence; git clean -fdq docs/tasks/0102-evidence`.
4. In `.github/workflows/ci.yml`, add `tests/test_a11y_guard_browser.py` to the fixed list of browser tests in the step named "Walk the guest flow in a browser", on its own line next to `tests/test_design_guardrails_browser.py`, in the same style.
5. In `docs/design/MASTER.md`, after section 11.0, add `### 11.1 Accessibility (WCAG 2.2 AA, as the UK public sector requires)` with these bullets, one line each: the standard is WCAG 2.2 AA; `test_a11y_guard_browser.py` fails the build on missing page language or title, not exactly one h1, skipped heading levels, no skip link, controls without a name, generic link text, text below 4.5:1 (3:1 for large text), targets under 24 by 24 CSS px, focus that is invisible or covered, sideways scroll at 320 px, and clipped text under wide text spacing; every page works with the keyboard alone and every form error names the field and says how to fix it (checked by hand when a form changes); no allowlist and no skip.
6. Commit: `git add App/tests/a11y_guard.js App/tests/test_a11y_guard_browser.py .github/workflows/ci.yml docs/design/MASTER.md docs/tasks/0166-* && git commit` with message `0166: accessibility guard for WCAG 2.2 AA` and the two trailers from your prompt.

## 5. Do not touch

Any template, CSS or other test; hard rules 1, 3, 8. Do not fix findings, do not add an allowlist, do not skip a rule.

## 6. Commands

As in each step.

## 7. Acceptance

- [ ] Four tests exist and run without Python errors; CI list and MASTER updated; report lists the findings.

## 8. Stop and ask

An import in step 2 cannot be resolved, or a test errors twice for a non-finding reason.

## 9. Report

`docs/tasks/0166-report.md`; `Status: review`. Section "Findings": for each test, the counts by rule, and for each rule up to three example lines (route, language, width, detail), copied from the failure output. Also copy the four `/tmp/ubyhost-a11y-*.json` files to `/mnt/project-files/design-reset/a11y/` (create the folder).
