# 1093: guest form title in cs, es, fr short enough for one line at 390 px

Status: todo
Tier: C | Depends on: 1091 (merged in #883; its test file and `font-size: 24px` rule are in main) | Base: origin/main | Branch: claude/1093-guest-title-short-copy
Executor: Sonnet (Tier C) | Attempts: 3 at most | Fits one session: stop at 50 tool calls or 60k tokens (section 8); reads stay at 150 lines or fewer
Review: orchestrator checks the diff and the 9 screenshots before the PR opens.
Report: docs/tasks/1093-report.md

## 1. Objective

Owner decision 2026-11-10 17:57: after 1091 the guest form title is 24 px under 480 px, and it fits on one line in en, de and uk but still wraps to 2 lines in Czech, Spanish and French. Shorten those three titles so they fit on one line at 390 px. Owner-approved candidates: cs "Registrace hosta", es "Registro de huésped", fr "Fiche des voyageurs". Nothing else changes: no CSS, no template, no other language, no field, no legal text.

## 2. Context

**Where the string lives (grepped 2026-11-10, origin/main 66528654).** One catalog key `title` per language in `App/app/i18n.py`: cs line 874 `"Registrace ubytovaného"`, es 2175 `"Registro de huéspedes"`, fr 2718 `"Enregistrement des voyageurs"` (en 105, de 1632 and `guest_uk_i18n.py:113` stay as they are). Those three exact strings appear nowhere else in `App/` (no test, no mail, no PDF, no house book); only the two archived `docs/archive/.../*.patch` files mention them, which stay.

**Where the key is shown.** Only `App/app/templates/guest/base.html` line 10 (page `<title>`) and line 24 (`<h1>`), as the default of `{% block title %}` and `{% block heading %}`. `guest/guide.html` overrides both with `guide_title`. The archive `guest/archive/ticket-wallet/` templates also use it, but they are archived and not routed. No mail, PDF or host page reads `title` from this catalog (the `ct('title')` hits are the cleaning catalog, a different one).

**Decision: change the shared key `title` in the three catalogs, add no new key.** Why: the h1 and the browser tab title are the same words by design (one explanation in one place, rule 9); a second key `title_h1` would need a template change plus 6 catalog entries and a parity check for a difference nobody wants; the only surfaces that change are the h1 and the tab title of the guest pages that do not override them, in cs, es and fr. No test asserts the old strings (checked), so nothing is loosened. The 1091 tests read the title through `i18n.translator(lang)("title")`, so they follow the new text.

**Legal wording check.** Czech: the statutory term "ubytovaný" stays in the body text, in `legal_notice_duty_body` (`i18n.py` line 1194, "Registrovat se musí každý ubytovaný") and at line 1266. The same cs catalog already calls the person "host" in `legal_intro` (line 877, "zaregistrovat každého hosta"), `tw_next_guest` ("Registrovat hosta") and `fee_per_person`. So the heading "Registrace hosta" matches what the page already says and the statutory term is untouched; the heading is not a legal definition. Spanish: the catalog already says "huésped" everywhere (`legal_intro` line 2178, `tw_next_guest`), and "Registro de huésped" is the singular of the current title. French: the body text says "voyageur" (`legal_intro` line 2721); "Fiche des voyageurs" keeps that word and is the usual name of the form a host has to fill in. Report any doubt; do not change body text.

**Measured widths (1091 report, 24 px, system Chromium):** the title column is about 232 px at 390 px, about 217 at 375 and about 202 at 360. Old titles: cs 272, es 256, fr 342. Rough estimate for the candidates from character count (about 12 px per character at 24 px; this is an estimate, **measure it**): cs "Registrace hosta" about 195 px, es "Registro de huésped" about 230 px, fr "Fiche des voyageurs" about 230 px. So es and fr may fit at 390 but **not** at 375 or 360. The owner requires one line at 390, 375 and 360, so step 1 measures first and step 2 picks from the fallback list.

Fallbacks, in order, only if the candidate is wider than the room at 360 px (use the first that fits, same legal reading): es "Ficha de huésped", then "Registro"; fr "Fiche voyageur", then "Fiche d'arrivée"; cs "Registrace hosta" has no fallback (if it does not fit at 360, STOP). Do not invent other strings. If a fallback instead of the owner-named candidate is used, say so first line in the report.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/i18n.py` | edit | the `title` value in `cs`, `es`, `fr` only (3 one-line edits, step 2) |
| `App/tests/test_guest_title_1091_browser.py` | edit | add tests f and g (step 3); no existing test is changed |
| `docs/tasks/screenshots-1093/` | create | 9 screenshots (section 6) |
| `docs/tasks/1093-report.md` | create | the report, and set this brief `Status: review` |

No CSS, template or `static_versions.json` change, so no cache key bump.

## 4. Steps (commit after each: `1093 step k`)

1. Anchors, each with `grep -nF`, STOP if one is missing: `"title": "Registrace ubytovaného",`, `"title": "Registro de huéspedes",`, `"title": "Enregistrement des voyageurs",` in `App/app/i18n.py`; `.g-checkin-page .g-head h1` in `App/app/static/guest.css`. Then measure the three candidates (and the fallbacks you may need) before editing: write a throwaway script in the scratchpad (not in the repo) or a temporary `print` test using the `_open_url`/`_measure` helpers of `test_guest_title_1091_browser.py`. Simplest: temporarily put the candidate in `i18n.py`, run the new test f (step 3) with `-s`, and print `h1.scrollWidth` and `clientWidth`. Write the measured widths (px, per language and per viewport) into the report.
2. Edit the three `title` values (value only, keep the keys, quotes, commas and the UTF-8 "é"): cs `"Registrace hosta"`, es `"Registro de huésped"`, fr `"Fiche des voyageurs"`, or the fallback chosen in step 1. Use the Edit tool with the full unique line as `old_string`. `git diff` must show exactly 3 changed lines in `i18n.py`.
3. Extend `test_guest_title_1091_browser.py` (reuse `_open_url`, `_measure`, `_one_line`, `H1_JS`; add the new tests at the end of the file; leave tests a to e, including d's `["cs", "es", "fr", "uk"]` parametrization, byte for byte):
   - f. `test_1093_f_title_is_one_line_cs_es_fr`: parametrize `lang` over `cs`, `es`, `fr` and `(width, height)` over `(390, 844)`, `(375, 812)`, `(360, 740)`. Assert the `h1` text equals `i18n.translator(lang)("title")` and is not the English title; `_one_line(info)`; `info["size"] == "24px"`. `-s` output: print the `scrollWidth` too (extend nothing in `H1_JS` for this; use a second `page.evaluate` or add a new constant, do not edit `H1_JS`).
   - g. `test_1093_g_screenshots`: for `cs`, `es`, `fr` at 390 x 844, 768 x 1024, 1280 x 800, write `docs/tasks/screenshots-1093/form-{lang}-{width}.png` the way test e writes `screenshots-1091` (`full_page=False`, `document.fonts.ready` first). A `SHOTS_1093` constant next to `SHOTS`.
   Update the module docstring first line to mention "and brief 1093: cs, es, fr". Do not loosen any assertion anywhere.
4. Run section 6, take and read the screenshots, write the report.

## 5. Do not touch

Any other key or language in `i18n.py`, `guest_uk_i18n.py`, `de`, `en`, the legal notice keys, every template, `guest.css`, `static_versions.json`, `host*`, routes, the archive patches, any dependency. Never push to `main`.

## 6. Commands (each ends `2>&1 | tail -30`; from `App/`; never the full suite)

Test-map rows: "Guest pages, guest templates" and the i18n row (`docs/context/test-map.md`; `grep -n i18n` it and run the row it names).

1. `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_guest_title_1091_browser.py -q --tb=short -x 2>&1 | tail -30`: green, **0 skipped**; the 10 old tests plus 9 f cases plus g.
2. `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_guest_*.py tests/test_guest_browser_e2e.py -q --tb=short -x 2>&1 | tail -30`: green, **0 skipped**. If a test fails because it pinned an old title, STOP and report (the grep found none).
3. `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_guest_ocr_geometry_browser.py tests/test_layout_lint_browser.py -q --tb=short -x 2>&1 | tail -30`: green, 0 skipped.
4. The i18n tests the test-map names (catalog parity, privacy): green.
5. Repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

### Screenshots (rules 7 and 10)

Page: guest registration form, step 1 "Your details", cs, es, fr, mock data, first screen, at 390, 768 and 1280 px (9 files from test g). Open each once. One line per language in the report: at 390 the title is on one line, the property name is under it, the language button is not squeezed or overlapping, no text is cut; at 768 and 1280 the title is on one line at 28 px and nothing moved. Do not retake to hide a problem.

## 7. Acceptance

- [ ] cs, es, fr titles are one line at 390, 375 and 360 px (test f green for 9 cases), `24px`, not cut.
- [ ] `git diff --stat origin/main`: `i18n.py` 3 lines, the 1091 test file (additions only), screenshots, report, this brief. Tests a to e untouched, no assertion loosened.
- [ ] Section 6 commands 1 to 5 green, 0 skipped in 1 to 3.
- [ ] 9 screenshots with one line per language in the report.
- [ ] The report gives the measured widths and states which strings were used (candidate or fallback).

## 8. Stop and ask

STOP and report `blocked` if: an anchor is missing; a browser test skips; cs "Registrace hosta" is not one line at 360 px; no listed string for es or fr fits at 360 px; an existing test fails on the old title text; a test fails twice on the same cause (attempt 3 of 3); 50 tool calls or 60k tokens (finish the step, commit, `Done: steps 1 to k. Left: steps k+1 to n.`). Never add CSS, `white-space`, a smaller size or a new key to make a string fit.

## 9. Report

`docs/tasks/1093-report.md`, 400 tokens at most: strings used (and whether a fallback was needed), widths per language and viewport, files, each command with its last 5 lines, section 7 ticked, the screenshot lines, deviations, questions (a native-reader check of es and fr is still advisable). Set this brief `Status: review`. Then open one PR (draft until the owner says it may ship). Body: copy-only change to three catalog values, no new request, no personal data, no dependency; paste the screenshot lines and tick the [design-system checklist](../design/design-system.md).
