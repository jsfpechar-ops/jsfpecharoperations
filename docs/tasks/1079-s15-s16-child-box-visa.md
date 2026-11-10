# 1079: S15 child-on-parent's-passport box only for under-18s; S16 visa field check (already on main)

Status: todo
Tier: A | Depends on: nothing (main alone) | Base commit: 951fda6c | Branch: claude/1079-s15-s16
Executor: Fable 5.2 | Attempts: 3 at most | Fits one session: stop at 25 tool calls or 60k tokens (section 8); reads stay at 150 lines or fewer
Review: a fresh Fable reviews the diff against this brief before the PR opens.
Report: docs/tasks/1079-report.md

## 1. Objective

Plan [speed-and-ease](../plans/speed-and-ease.md) section 11, queue item 2.5. Both are owner-agreed ("filing: owner agreed").

- **S15:** "The 'child travelling on a parent's passport' box appears only when the birth date says under 18". Adults never see a block that cannot apply to them.
- **S16:** "The visa number field appears only for nationalities outside the EU and Schengen". **Already on main** (UX-113, commit 746d9985): `initVisaVisibility` and `VISA_FREE_COUNTRIES` in `signature.js:264-291`, pinned at source by `App/tests/test_guest_visa_hidden.py`. No S16 code change here. This brief only adds a real-browser test of it (step 3), because the existing test has no JavaScript runtime.

Overnight line (decisions.md line 62): G6, G13, S17 parked or skipped, 7b numbers not confirmed. S15 and S16 depend on none of them. S14 (under-15 signature, G13) is **not** built: the signature step stays for everyone.

**Tier A (orchestrator decision):** it changes what a guest sees next to a police field on the guest form. It is a client-only change, and the box is never unchecked by the script.

## 2. Context

- **Filing unchanged (rule 1):** the police payload (`reporting.py:158` `"cVisN": guest["visa_number"] or None,` and the `INPASS` doc path, `validation.py:60` `INPASS = "INPASS"`) and when it is sent stay byte-identical. No edit to `reporting.py`, `validation.py`, `routes/guest.py`, `submit_*`, `deadlines.py`. The server keeps reading `child_in_passport` exactly as today (`routes/guest.py:2084` `child_in_passport = bool(form.get("child_in_passport"))`).
- **The rule that makes S15 safe:** the script only ever sets `style.display` on a new wrapper `#child-wrap`. It never changes `toggle.checked`, `required` or any value. A **checked box is always shown**, whatever the birth date says (an existing INPASS guest, or a typo in the birth date, stays visible and fixable). So the submitted form differs from main only in what the guest can see, never in what is posted.
- **When the box shows:** `toggle.checked`, or the birth date parses and the guest is under 18 on the reference day R = the earlier of the hidden `stay_from` value and today (local date). Earlier day = younger guest, so this shows the box in every case where it could apply (late registration included). Birth date empty or not yet parseable: hidden (the birth date field comes first in the order). Unknown day or month (`00`): show when `R.year - birth.year <= 18` (year-only test, conservative).
- **Birth date parsing:** the same rules as `feeBirth` (`signature.js:377`, `function feeBirth(text) {`): `dd.mm.yyyy`, or `dd.mm.yy` with the century closest to today. `feeBirth` sits inside another init function, so copy its parse into a new private helper; do not move or edit `feeBirth`.
- **No JavaScript:** the box is visible exactly as today (the wrapper has no inline style; only the script hides it).
- **Scan path:** `_ocr_scan.html:45-46` already dispatches `input` and `change` on `birth_date`; listen to both so a scanned birth date updates the box.
- **Host form:** `guest_form_admin.html` has no `#child_in_passport`, so `initChildToggle` returns early there (`if (!toggle) return;`). Do not touch the host form.
- **Design (owner request):** same cards, colours, type, step strip and field order. The only markup change is `id="child-wrap"` on an existing `div`. No CSS change, no new copy, no i18n key, so rule 9 has nothing to add in any of the six languages (`en cs de es fr uk`).
- **Privacy:** no new field, column, cookie, script, request or dependency. No migration (0042 and goose 00013 stay free).
- **Never "paid":** not touched; no fee copy changes.

### Anchors (verified on 951fda6c; re-check each with `grep -nF`)

1. `App/app/templates/guest/form.html:170-171`: the line `    <div class="g-field">` directly above `      <label class="checkline" for="child_in_passport">` (171).
2. `App/app/templates/guest/form.html:69`: `  <input type="hidden" name="stay_from"`.
3. `App/app/static/signature.js:236` `  function initChildToggle() {`; `:240` `    var parentWrap = document.getElementById("parent-doc-wrap");`; `:252` `    toggle.addEventListener("change", apply);`.
4. `App/app/static/signature.js:278` `  function initVisaVisibility() {` (read only).
5. `App/app/templates/guest/base.html:84` and `App/app/templates/_signature_script.html:2`: `signature.js?v=20261109-qa2`.
6. `App/tests/test_guest_child_document.py:225`: `toggle = script.split("function initChildToggle()", 1)[1].split("\n  }", 1)[0]` (this test must stay green: keep `parentInput.required = toggle.checked` inside `initChildToggle`, and add no line starting `\n  }` before it).
7. `App/tests/test_guest_form_input_browser.py:15`: `from tests.test_guest_browser_e2e import Guest, _fee_seed, browser, live_server  # noqa: F401` and its helpers `_fill_step_one` (27), `_open_url` (42): the model for the new browser test.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/guest/form.html` | edit | `id="child-wrap"` on anchor 1's div, nothing else |
| `App/app/static/signature.js` | edit | `initChildToggle` only (step 2) |
| `App/app/templates/guest/base.html` | edit | cache key `?v=20261110-1079` |
| `App/app/templates/_signature_script.html` | edit | the same cache key |
| `App/tests/test_guest_child_visa_1079.py` | create | Source and server tests (step 4) |
| `App/tests/test_guest_child_visa_1079_browser.py` | create | Browser and geometry tests (step 3) |
| `docs/tasks/screenshots-1079/` | create | Six PNGs (step 3) |
| `docs/tasks/1079-report.md` | create | Report, plus `Status: review` here |

## 4. Steps (commit after each: `1079 step k`)

1. Confirm anchors 1 to 7 with `grep -nF`; any missing: STOP. In `form.html` change anchor 1's line to `    <div class="g-field" id="child-wrap">`. Bump both cache keys (anchor 5) to `20261110-1079`.
2. In `initChildToggle`, after anchor 3's `parentWrap` line add `childWrap = document.getElementById("child-wrap")`, `birth = document.getElementById("birth_date")`, `stayFrom = document.querySelector('input[name="stay_from"]')`. Add two private helpers inside the function: `childBirth(text)` (feeBirth's parse, but return `{y, m, d, exact}` where `exact` is false when day or month was `00`) and `mayBeChild()` (section 2 rule; R from `stayFrom.value` `yyyy-mm-dd` if valid, else today, and today if earlier). Add `function showBox() { if (childWrap) childWrap.style.display = (toggle.checked || mayBeChild()) ? "" : "none"; }`. Call `showBox()` at the end of `apply()`. After anchor 3's `toggle.addEventListener("change", apply);` add, guarded by `if (birth)`, `input` and `change` listeners that call `showBox`. Nothing in the function may assign `toggle.checked`, `.required` (beyond the two existing lines) or `.value`. Do not edit any other function.
3. Browser test `test_guest_child_visa_1079_browser.py`, modelled on anchor 7 (`_open_url`, `Guest.pick_country`), `@pytest.mark.parametrize("width", [390, 768, 1280])` where a test checks layout:
   a. Adult birth date `01011980`: `#child-wrap` hidden, `#parent-doc-wrap` hidden, `#doc_number` required. Child birth date two years before today: box visible. Edit the date back to adult: hidden again. Same sequence twice in a row ends in the same state (idempotent).
   b. Box checked, then birth date changed to adult: box stays visible and still checked; `#parent_doc_number` still required.
   c. Born 17 years and 360 days before today with `stay_from` 30 days ago: visible (reference day is the earlier one). Born 30 years ago with `stay_from` in the future: hidden.
   d. Scan path: set `#birth_date` by `page.evaluate` and dispatch `input` and `change` as `_ocr_scan.html` does: box follows.
   e. S16 in a real browser: nationality `DEU` hides the visa field and empties a typed value; `USA` shows it; back to `CZE` hides it.
   f. Geometry at each width: no horizontal scroll (`scrollWidth <= innerWidth`); with the box hidden, the gap between `#doc-wrap` and the visa field's wrapper equals the gap between two other neighbouring `.g-field`s on the same card within 1 px; with it shown, the box sits between `#doc-wrap` and the visa field with no overlap. Use `Guest.check_layout` and `Guest.check_spacing` where they fit.
   g. Screenshots into `docs/tasks/screenshots-1079/`: `adult-{390,768,1280}.png` and `child-{390,768,1280}.png` (step 1 card, full page). Look at each once and write one line per width in the report.
4. `test_guest_child_visa_1079.py` (no browser; reuse `_cleanup`, `_seed`, `_payload` of `test_guest_child_document.py`, reading lines 39 to 130 only):
   a. Source pin: inside `initChildToggle` there is no `toggle.checked =`, no `.value =`, and `childWrap.style.display` appears; `form.html` has exactly one `id="child-wrap"`, with no `style=` on that line.
   b. Filing pin: a save without `child_in_passport` stores the typed `doc_number`; a save with it and a parent number stores `INPASS` and the parent note (`validation.INPASS_NOTE_PREFIX`), the same as on main. (The no-edit check on `reporting.py`, `validation.py` and `routes/` is section 7's `git diff --stat`, not a test.)
   c. Idempotency: post the same edit of one existing guest (with `guest_id`) twice: one guest row, same `doc_number`, `note`, `visa_number`, `submit_state` after both.
   d. Concurrency: two existing guests of one booking, an adult (no box) and a child (box plus parent number), saved at the same moment from two threads with two clients: each row ends with its own values (adult keeps the doc number, child has `INPASS`); no row has the other's data; guest count unchanged. Use edits of existing guests only (the add-guest race is a known bug, not in scope).
5. Run section 6, then write the report.

## 5. Do not touch

`reporting.py`, `validation.py`, `routes/*`, `submit_*`, `deadlines.py`, `door_codes.py`, `stay_fee.py`, `_ocr_scan.html`, `guest_form_admin.html`, the archive templates, any CSS file, any i18n file, `initVisaVisibility`, `VISA_FREE_COUNTRIES`, `feeBirth`, `db.py`, migrations, any dependency. Never push to `main`.

## 6. Commands (each ends `2>&1 | tail -30`)

From `App/`: `.venv/bin/python -m pytest tests/test_guest_child_visa_1079.py tests/test_guest_child_document.py tests/test_guest_visa_hidden.py tests/test_guest_record_extraction.py tests/test_design_guest_admin.py -q --tb=short -x`. Browser, 0 skipped: `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_guest_child_visa_1079_browser.py tests/test_guest_form_input_browser.py tests/test_guest_ocr_geometry_browser.py tests/test_guest_browser_e2e.py tests/test_host_geometry.py tests/test_layout_lint_browser.py -q --tb=short -rs`. Test-map guest row: `.venv/bin/python -m pytest tests/test_guest_*.py -q --tb=short -x`. Repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance

- [ ] Adult birth date: box hidden; under 18 on the earlier of arrival and today: shown; a checked box is never hidden or unchecked.
- [ ] No JavaScript: box visible as on main. Posted form and stored guest row identical to main for the same inputs.
- [ ] Idempotency and concurrency tests green; S16 browser test green; existing visa and child tests unchanged and green.
- [ ] Browser and geometry tests 0 skipped; layout lint run (guest pages report-only, findings copied to the report); six screenshots in `docs/tasks/screenshots-1079/`.
- [ ] `git diff --stat origin/main` touches only section 3 files; design, copy and field order unchanged.

## 8. Stop and ask

STOP and report `blocked` if: an anchor is missing; the change would need a server, filing, CSS, i18n or host-form edit; anchor 6's test cannot stay green; a browser test skips; a test fails twice on the same cause (attempt 3 of 3); 25 tool calls or 60k tokens (finish the step, commit, `Done: steps 1 to k. Left: steps k+1 to n.`).

## 9. Report

`docs/tasks/1079-report.md`, 600 tokens at most: files changed, each command with its last 5 lines, section 7 ticked, one line per screenshot on what you saw, layout-lint findings for the guest form, deviations, questions. Set this brief `Status: review`. After the fresh Fable diff review, open one PR (body: client-only, filing untouched, no new field or request, S16 already on main). Merge only with `scripts/merge-pr-on-green.sh`.

## 10. Open questions (not blocking)

- **Q1:** microstates (Andorra, Monaco, San Marino, Vatican) are not on `VISA_FREE_COUNTRIES`, so their guests still see the optional visa field. Left as on main; the owner may add them later.
- **Q2:** the plan's S14 (no signature under 15) stays parked with G13.
