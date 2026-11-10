# 1093: guest form title in cs, es, fr short enough for one line at 390 px

Status: review
Tier: C | Depends on: 1091 (merged in #883; its test file and `font-size: 24px` rule are in main) | Base: origin/main | Branch: claude/1093-guest-title-short-copy
Executor: Sonnet (Tier C) | Attempts: 3 at most | Fits one session: stop at 50 tool calls or 60k tokens (section 8); reads stay at 150 lines or fewer
Review: orchestrator checks the diff and the 6 screenshots before the PR opens. Brief reviewed 2026-11-10 by a fresh Fable (widths measured, strings settled).
Report: docs/tasks/1093-report.md

## 1. Objective

Owner decision 2026-11-10 17:57: after 1091 the guest form title is 24 px under 480 px, and it fits on one line in en, de and uk but still wraps to 2 lines in Czech, Spanish and French. Shorten those three titles so they fit on one line on phones (390, 375 and 360 px). **Final strings (settled by measurement, section 2; the executor does not choose):** cs `Registrace hosta`, es `Ficha de huésped`, fr `Fiche voyageur`. The owner's candidates for es ("Registro de huésped") and fr ("Fiche des voyageurs") fit only at 390 px and wrap at 375 and 360, so the shorter form of each is used. Nothing else changes: no CSS, no template, no other language, no field, no legal text.

## 2. Context

**Where the string lives (grepped 2026-11-10, origin/main 66528654).** One catalog key `title` per language in `App/app/i18n.py`: cs line 874 `"Registrace ubytovaného"`, es 2175 `"Registro de huéspedes"`, fr 2718 `"Enregistrement des voyageurs"` (en 105, de 1632 and `guest_uk_i18n.py:113` stay as they are). Those three exact strings appear nowhere else in `App/` (no test, no mail, no PDF, no house book); only the two archived `docs/archive/.../*.patch` files mention them, which stay.

**Where the key is shown.** Only `App/app/templates/guest/base.html` line 10 (page `<title>`) and line 24 (`<h1>`), as the default of `{% block title %}` and `{% block heading %}`. `guest/guide.html` overrides both with `guide_title`. The archive `guest/archive/ticket-wallet/` templates also use it, but they are archived and not routed. No mail, PDF or host page reads `title` from this catalog (the `ct('title')` hits are the cleaning catalog, a different one).

**Decision: change the shared key `title` in the three catalogs, add no new key.** Why: the h1 and the browser tab title are the same words by design (one explanation in one place, rule 9); a second key `title_h1` would need a template change plus 6 catalog entries and a parity check for a difference nobody wants; the only surfaces that change are the h1 and the tab title of the guest pages that do not override them, in cs, es and fr. No test asserts the old strings (checked), so nothing is loosened. The 1091 tests read the title through `i18n.translator(lang)("title")`, so they follow the new text.

**Legal and native-reader check (reviewer, 2026-11-10).** The form registers one person per page (a group fills it once per person), so the singular is right in all three. Czech: the statutory term "ubytovaný" stays in the body text, in `legal_notice_duty_body` (`i18n.py` line 1194, "Registrovat se musí každý ubytovaný") and at line 1266. The same cs catalog already calls the person "host" in `legal_intro` (line 877, "zaregistrovat každého hosta"), `tw_next_guest` ("Registrovat hosta") and `fee_per_person`. "Registrace hosta" is natural Czech, matches the old singular ("ubytovaného") and is not a legal definition; "Registrace hostů" would be equally correct but says less precisely what one page does. Spanish: the catalog says "huésped" everywhere (`legal_intro` line 2178, `tw_next_guest`); "Ficha de huésped" (one guest's registration card) is idiomatic hotel Spanish in Spain and Latin America, and reads better than the article-less "Registro de huésped". The Spain-only police term "parte de viajeros" is deliberately not used: the stay is in Czechia. French: the body text says "voyageur" (`legal_intro` line 2721); "Fiche voyageur" is the usual hotel name of the per-person form (like "fiche client"), and the singular is more accurate than "Fiche des voyageurs" for a one-person page. "Fiche de police" is not used: it is the French statutory form, not the Czech one. Do not change body text.

**Measured widths (reviewer, 2026-11-10).** Static harness with the real `base.html` header markup (property mark, h1, property name, language button), this branch's `tokens.css` and `guest.css`, Playwright Chromium, 24 px bold, font Inter (the guest stack is `-apple-system, BlinkMacSystemFont, "SF Pro Text", "Inter", ...`; this machine and CI resolve to Inter). The harness reproduces the 1091 report's old widths exactly (cs 272, es 256, fr 342). Room for the title: cs 232 / 217 / 202 px at 390 / 375 / 360; es and fr 234 / 219 / 204 (their language button is 2 px narrower).

| Lang | String | Width px | 390 | 375 | 360 | Spare at 360 |
|---|---|---|---|---|---|---|
| cs | Registrace ubytovaného (old) | 272.3 | 2 lines | 2 | 2 | |
| cs | **Registrace hosta** (owner candidate, used) | 187.5 | 1 line | 1 | 1 | 14 px |
| cs | Registrace hostů | 188.4 | 1 | 1 | 1 | 14 px |
| es | Registro de huéspedes (old) | 255.7 | 2 | 2 | 2 | |
| es | Registro de huésped (owner candidate) | 229.1 | 1 | **2** | **2** | |
| es | **Ficha de huésped** (used) | 197.0 | 1 | 1 | 1 | 7 px |
| es | Registro | 92.8 | 1 | 1 | 1 | 111 px |
| fr | Enregistrement des voyageurs (old) | 341.8 | 2 | 2 | 2 | |
| fr | Fiche des voyageurs (owner candidate) | 230.8 | 1 | **2** | **2** | |
| fr | **Fiche voyageur** (used) | 171.8 | 1 | 1 | 1 | 32 px |
| fr | Fiche d'arrivée | 166.8 | 1 | 1 | 1 | 37 px |

Cross-check with Arial metrics (Liberation Sans, close to Android's Roboto): cs 183.8, es "Ficha de huésped" 193.1, fr "Fiche voyageur" 167.7, so the used strings also fit there; Inter is the wider case. At 320 px (room about 163) all three used strings wrap to 2 lines without being cut; 320 is outside the owner's request.

**Other guest pages that show the same key** (`assigned`, `claim`, `confirm`, `pick`, `pin`, `privacy`, `remove`, `stay`, `unavailable`: they extend `guest/base.html` and override neither block; their h1 is 25 px at every width). Measured at 25 px: cs 197.3 and fr 180.7 are one line at 390, 375 and 360; es 207.2 is one line at 390 and 375 and wraps at 360 (room 204), where the old title wrapped at every width. That is accepted and out of scope; do not add CSS for it. The new strings read correctly as the page heading and tab title on those pages (a per-person form label above the PIN, the group list, the thank-you and the privacy text), exactly as the old ones did.

The strings are final. Do not pick another string. If test f fails for a final string, STOP (section 8).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/i18n.py` | edit | the `title` value in `cs`, `es`, `fr` only (3 one-line edits, step 2) |
| `App/tests/test_guest_title_1091_browser.py` | edit | add tests f and g (step 3); no existing test is changed |
| `docs/tasks/screenshots-1093/` | create | 6 screenshots (section 6) |
| `docs/tasks/1093-report.md` | create | the report, and set this brief `Status: review` |

No CSS, template or `static_versions.json` change, so no cache key bump.

## 4. Steps (commit after each: `1093 step k`)

1. Anchors, each with `grep -nF`, STOP if one is missing: `"title": "Registrace ubytovaného",`, `"title": "Registro de huéspedes",`, `"title": "Enregistrement des voyageurs",` in `App/app/i18n.py` (each exactly once: lines 874, 2175, 2718); `.g-checkin-page .g-head h1` in `App/app/static/guest.css`. No measuring step: the widths are in section 2.
2. Edit the three `title` values (value only, keep the keys, quotes, commas and the UTF-8 "é"): cs `"title": "Registrace hosta",`, es `"title": "Ficha de huésped",`, fr `"title": "Fiche voyageur",`. Use the Edit tool with the full unique line as `old_string`. `git diff` must show exactly 3 changed lines in `i18n.py`.
3. Extend `test_guest_title_1091_browser.py` (reuse `_open_url`, `_measure`, `_one_line`, `H1_JS`; add the new tests at the end of the file; leave tests a to e, including d's `["cs", "es", "fr", "uk"]` parametrization, byte for byte):
   - f. `test_1093_f_title_is_one_line_cs_es_fr`: parametrize `lang` over `cs`, `es`, `fr` and `(width, height)` over `(390, 844)`, `(375, 812)`, `(360, 740)` (9 cases). `info, _, _ = _measure(...)`. Assert `info["text"] == i18n.translator(lang)("title")`; assert `info["text"] == EXPECTED_1093[lang]` with a module constant `EXPECTED_1093 = {"cs": "Registrace hosta", "es": "Ficha de huésped", "fr": "Fiche voyageur"}`; `_one_line(info)`; `info["size"] == "24px"`. Do not call `page.evaluate` on the page `_measure` returns: its context is already closed.
   - g. `test_1093_g_screenshots`: for `cs`, `es`, `fr` at 390 x 844 and 360 x 740, write `docs/tasks/screenshots-1093/form-{lang}-{width}.png` the way test e writes `screenshots-1091` (own context per shot, `page.evaluate("document.fonts.ready")` first, `full_page=False`). A `SHOTS_1093` constant next to `SHOTS`. 360 is included because it is the tightest width; 768 and 1280 are not, because the titles are shorter than the old ones that already fit there at 28 px.
   Update the module docstring first line to mention "and brief 1093: cs, es, fr". Do not loosen any assertion anywhere.
4. Run section 6, take and read the screenshots, write the report.

## 5. Do not touch

Any other key or language in `i18n.py`, `guest_uk_i18n.py`, `de`, `en`, the legal notice keys, every template, `guest.css`, `static_versions.json`, `host*`, routes, the archive patches, any dependency. Never push to `main`.

## 6. Commands (each ends `2>&1 | tail -30`; from `App/`; never the full suite)

Test-map rows: "Guest pages, guest templates" and "Copy, translations" (already written out below; do not open the test-map).

1. `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_guest_title_1091_browser.py -q --tb=short -x 2>&1 | tail -30`: `20 passed`, **0 skipped** (the 10 old cases, 9 f cases, g). Add `-rs` if anything skips.
2. `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_guest_*.py tests/test_guest_browser_e2e.py -q --tb=short -x 2>&1 | tail -30`: green, **0 skipped**. If a test fails because it pinned an old title, STOP and report (the grep found none).
3. `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_guest_ocr_geometry_browser.py tests/test_layout_lint_browser.py -q --tb=short -x 2>&1 | tail -30`: green, 0 skipped.
4. `.venv/bin/python -m pytest tests/test_go_host_i18n.py tests/test_host_i18n.py tests/test_public_copy_i18n.py tests/test_validation_i18n.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py tests/test_flash_literals.py -q --tb=short -x 2>&1 | tail -30` (the test-map row "Copy, translations"): green.
5. Repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

### Screenshots (rules 7 and 10)

Page: guest registration form, step 1 "Your details", cs, es, fr, mock data, first screen, at 390 and 360 px (6 files from test g). Open each once. One line per language in the report: at 390 and at 360 the title is on one line, the property name is under it, the language button is not squeezed or overlapping, no text is cut. Do not retake to hide a problem.

## 7. Acceptance

- [ ] cs, es, fr titles are one line at 390, 375 and 360 px (test f green for 9 cases), `24px`, not cut.
- [ ] `git diff --stat origin/main`: `i18n.py` 3 lines, the 1091 test file (additions only, plus the docstring first line), screenshots, report, this brief. Tests a to e untouched, no assertion loosened.
- [ ] Section 6 commands 1 to 5 green, 0 skipped in 1 to 3.
- [ ] 6 screenshots with one line per language in the report.
- [ ] The report states the three strings used; they equal section 1.

## 8. Stop and ask

STOP and report `blocked` if: an anchor is missing; a browser test skips; test f fails for any of the three final strings (do not swap the string, do not edit the test); an existing test fails on the old title text; a test fails twice on the same cause (attempt 3 of 3); 50 tool calls or 60k tokens (finish the step, commit, `Done: steps 1 to k. Left: steps k+1 to n.`). Never add CSS, `white-space`, a smaller size or a new key to make a string fit.

## 9. Report

`docs/tasks/1093-report.md`, 400 tokens at most: strings used, files, each command with its last 5 lines, section 7 ticked, the screenshot lines, deviations, questions. Set this brief `Status: review`. Then open one PR (draft until the owner says it may ship). Body: copy-only change to three catalog values (say that es and fr use the shorter form because the owner's candidates wrap at 375 and 360 px, with the widths from section 2), no new request, no personal data, no dependency; paste the screenshot lines and tick the [design-system checklist](../design/design-system.md).
