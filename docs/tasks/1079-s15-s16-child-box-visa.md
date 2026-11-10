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
- **When the box shows:** `toggle.checked`, or the birth date parses and the guest is under 18 on the reference day R = the earlier of the hidden `stay_from` value and today (local date). Under 18 means R is before the 18th birthday: compare the number triples `(y + 18, m, d) > (R.y, R.m, R.d)`, no `Date` arithmetic (29 February safe). Earlier day = younger guest, so the box shows in every case where it could apply (late registration, arrival in the past). Unknown day or month (`00`): show when `R.year - birth.year <= 18` (year-only, conservative). Birth date empty or not parseable, and the field not being typed in: hidden (the birth date field comes first in the order).
- **While the guest types (no flicker, no lost focus):** the mask writes `01.01.19` on the way to `01.01.1980`, which the two-digit rule reads as 2019. So while `#birth_date` has the focus and its value is not a full `dd.mm.yyyy`, the script leaves the box as it is. It decides on a full date, on `blur`, on load and on `pageshow`. The box sits below the birth date, so showing or hiding it never moves the field in focus.
- **The box is never hidden under the guest's finger:** the checkbox's own `change` may only reveal the wrapper, never hide it. An adult who unticks a ticked box keeps seeing it (and can tick it again) until the birth date is next evaluated.
- **Back button, restored page, autofill:** a browser can restore a ticked box or a birth date without any event. On `pageshow` the script runs `apply()` and re-decides the box, so a restored ticked box is shown with its parent field. This is the only way a ticked box could have stayed hidden; step 3h pins it.
- **Server error re-render and saved guests:** the template ticks the box from `values` or an `INPASS` guest (`form.html:173`), so it renders ticked and the script shows it. **One guest per page:** a group registers one guest per form load, so every id here is unique on the page.
- **Birth date parsing:** the same rules as `feeBirth` (`signature.js:377`, `function feeBirth(text) {`): `dd.mm.yyyy`, or `dd.mm.yy` with the century closest to today. `feeBirth` sits inside another init function, so copy its parse into a new private helper; do not move or edit `feeBirth`. `initBirthDate` (`signature.js:165`) is initialised before `initChildToggle` (lines 912-913), so its mask has already run when your `input` listener reads the value; its `paste` handler sets the value **without** an `input` event, so listen to `paste` too.
- **No JavaScript:** the box is visible exactly as today (the wrapper has no inline style; only the script hides it).
- **Scan path:** `App/app/templates/guest/_ocr_scan.html:45-46` already dispatches `input` and `change` on `birth_date` (focus is not in the field then), so a scanned birth date updates the box.
- **Host form:** `guest_form_admin.html` has no `#child_in_passport`, so `initChildToggle` returns early there (`if (!toggle) return;`). Do not touch the host form.
- **Design (owner request, hard):** the guest form keeps its exact design: same cards, colours, type, step strip, spacing and field order. The only markup change is `id="child-wrap"` on an existing `div`. No CSS change, no new copy, no i18n key, so rule 9 has nothing to add in any of the six languages (`en cs de es fr uk`). A hidden `.g-field` leaves no gap: the visa wrapper is already hidden the same way on main (step 3f measures it).
- **Privacy:** no new field, column, cookie, script, request or dependency. No migration (0042 and goose 00013 stay free).
- **Never "paid":** not touched; no fee copy changes.

### Anchors (verified on 951fda6c; re-check each with `grep -nF`)

1. `App/app/templates/guest/form.html:170-171`: the line `    <div class="g-field">` directly above `      <label class="checkline" for="child_in_passport">` (171).
2. `App/app/templates/guest/form.html:69`: `  <input type="hidden" name="stay_from"`.
3. `App/app/static/signature.js:236` `  function initChildToggle() {`; `:240` `    var parentWrap = document.getElementById("parent-doc-wrap");`; `:252` `    toggle.addEventListener("change", apply);`.
4. `App/app/static/signature.js:278` `  function initVisaVisibility() {` (read only).
5. `App/app/templates/guest/base.html:84` and `App/app/templates/_signature_script.html:2`: `signature.js?v=20261109-qa2`. `App/tests/static_versions.json:162-165` records the same key and the file's sha256.
6. `App/tests/test_guest_child_document.py:225`: `toggle = script.split("function initChildToggle()", 1)[1].split("\n  }", 1)[0]` (this test must stay green: keep `parentInput.required = toggle.checked` inside `initChildToggle`, and add no line starting `\n  }` before it).
7. `App/tests/test_guest_form_input_browser.py:15`: `from tests.test_guest_browser_e2e import Guest, _fee_seed, browser, live_server  # noqa: F401` and its helpers `_fill_step_one` (27), `_open_url` (42), and the no-JavaScript test at line 87: the model for the new browser test.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/guest/form.html` | edit | `id="child-wrap"` on anchor 1's div, nothing else |
| `App/app/static/signature.js` | edit | `initChildToggle` only (step 2) |
| `App/app/templates/guest/base.html` | edit | cache key `?v=20261110-1079` |
| `App/app/templates/_signature_script.html` | edit | the same cache key |
| `App/tests/static_versions.json` | regenerate | Only by the `--write` command in step 2, never by hand |
| `App/tests/test_guest_child_visa_1079.py` | create | Source and server tests (step 4) |
| `App/tests/test_guest_child_visa_1079_browser.py` | create | Browser and geometry tests (step 3) |
| `docs/tasks/screenshots-1079/` | create | Six PNGs (step 3) |
| `docs/tasks/1079-report.md` | create | Report, plus `Status: review` here |

## 4. Steps (commit after each: `1079 step k`)

1. Confirm anchors 1 to 7 with `grep -nF`; any missing: STOP. In `form.html` change anchor 1's line to `    <div class="g-field" id="child-wrap">`. Bump both cache keys (anchor 5) to `20261110-1079`.
2. In `initChildToggle`, after anchor 3's `parentWrap` line add `var childWrap = document.getElementById("child-wrap");`, `var birth = document.getElementById("birth_date");`, `var stayFrom = document.querySelector('input[name="stay_from"]');`. Add private helpers inside the function, indented 4 spaces (anchor 6): `childBirth(text)` (feeBirth's parse, returning `{y, m, d, exact}`, `exact` false when day or month was `00`), `mayBeChild()` (section 2 rule; R from `stayFrom.value` `yyyy-mm-dd` if valid, else today, and today if earlier), `typing()` (`birth && document.activeElement === birth && !/^\d{2}\.\d{2}\.\d{4}$/.test(birth.value)`) and:
   ```js
    function showBox(mayHide) {
      if (!childWrap) return;
      if (toggle.checked) { childWrap.style.display = ""; return; }
      if (typing()) return;
      if (mayBeChild()) childWrap.style.display = "";
      else if (mayHide) childWrap.style.display = "none";
    }
   ```
   Wiring, nothing else: last line of `apply()` is `showBox(false);`. After the existing final `apply();` add `showBox(true);`. If `birth`: `input`, `change` and `blur` listeners calling `showBox(true)`, and a `paste` listener calling `setTimeout(function () { showBox(true); }, 0)`. Then `window.addEventListener("pageshow", function () { apply(); showBox(true); });`. Nothing in the function may assign `toggle.checked` or `.value`, or `.required` beyond the two existing lines. Do not edit any other function. Then, from `App/`, run `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -30` and commit `tests/static_versions.json` (its diff: only the `signature.js` entry). If you edit `signature.js` again after this, the command refuses: bump both cache keys again (`20261110-1079b`) and rerun it.
3. Browser test `test_guest_child_visa_1079_browser.py`, modelled on anchor 7 (`_open_url`, `Guest.pick_country`), `@pytest.mark.parametrize("width", [390, 768, 1280])` where a test checks layout:
   a. Typed with the keyboard into `#birth_date` (`page.type`): adult `01011980`: `#child-wrap` hidden at every keystroke (also at `01.01.19`), `#parent-doc-wrap` hidden, `#doc_number` required. Child birth date two years before today: box visible once the date is complete, `document.activeElement.id` is still `birth_date` and the field's `getBoundingClientRect().top` moved by less than 1 px. Edit the date back to adult: hidden again. Same sequence twice in a row ends in the same state (idempotent). `01.01.19` then Tab (blur): visible. Empty field after blur: hidden.
   b. Box checked, then birth date changed to adult: box stays visible and still checked; `#parent_doc_number` still required. Then untick it: the box is **still visible** and can be ticked again; `#doc_number` required again. Only the next birth date edit hides it.
   c. Born 17 years and 360 days before today with `stay_from` 30 days ago: visible (reference day is the earlier one). Born 30 years ago with `stay_from` in the future: hidden.
   d. Scan path: set `#birth_date` by `page.evaluate` and dispatch `input` and `change` as `_ocr_scan.html` does: box follows. Paste path: paste a child date into `#birth_date`: box visible.
   e. S16 in a real browser: nationality `DEU` hides the visa field and empties a typed value; `USA` shows it; back to `CZE` hides it.
   f. Geometry at each width: no horizontal scroll (`scrollWidth <= innerWidth`); with the box hidden, the gap between `#doc-wrap` and the visa field's wrapper equals the gap between two other neighbouring `.g-field`s on the same card within 1 px; with it shown, the box sits between `#doc-wrap` and the visa field with no overlap. Use `Guest.check_layout` and `Guest.check_spacing` where they fit.
   g. Screenshots into `docs/tasks/screenshots-1079/`: `adult-{390,768,1280}.png` and `child-{390,768,1280}.png` (step 1 card, full page). Look at each once and write one line per width in the report.
   h. Restored page: adult date, then `page.evaluate` sets `#child_in_passport.checked = true` with no event and dispatches `new PageTransitionEvent("pageshow", {persisted: true})` on `window`: `#child-wrap` and `#parent-doc-wrap` visible, `#parent_doc_number` required. Saved `INPASS` guest (or a server error re-render with the box ticked) and an adult birth date: box visible and ticked on load.
   i. No JavaScript (`java_script_enabled=False`, as anchor 7's line 87): `#child-wrap` visible for an adult birth date.
   j. Posted values: for the adult and the child case, `page.evaluate` reads `new FormData(form)` keys and values before and after the box is hidden and shown: identical (no `child_in_passport` key when unticked, hidden or not).
4. `test_guest_child_visa_1079.py` (no browser; reuse `_cleanup`, `_seed`, `_payload` of `test_guest_child_document.py`, reading lines 39 to 130 only):
   a. Source pin: inside `initChildToggle` there is no `toggle.checked =`, no `.value =`, exactly two `.required =`, a `pageshow` listener, and `childWrap.style.display` appears; `form.html` has exactly one `id="child-wrap"`, with no `style=` on that line.
   b. Filing pin: a save without `child_in_passport` stores the typed `doc_number`; a save with it and a parent number stores `INPASS` and the parent note (`validation.INPASS_NOTE_PREFIX`), the same as on main. (The no-edit check on `reporting.py`, `validation.py` and `routes/` is section 7's `git diff --stat`, not a test.)
   c. Idempotency: post the same edit of one existing guest (with `guest_id`) twice: one guest row, same `doc_number`, `note`, `visa_number`, `submit_state` after both.
   d. Concurrency: two existing guests of one booking, an adult (no box) and a child (box plus parent number), saved at the same moment from two threads with two clients: each row ends with its own values (adult keeps the doc number, child has `INPASS`); no row has the other's data; guest count unchanged. Use edits of existing guests only (the add-guest race is a known bug, not in scope).
5. Run section 6, then write the report.

## 5. Do not touch

`reporting.py`, `validation.py`, `routes/*`, `submit_*`, `deadlines.py`, `door_codes.py`, `stay_fee.py`, `_ocr_scan.html`, `guest_form_admin.html`, the archive templates, any CSS file, any i18n file, `initVisaVisibility`, `VISA_FREE_COUNTRIES`, `feeBirth`, `db.py`, migrations, any dependency. Never push to `main`.

## 6. Commands (each ends `2>&1 | tail -30`)

From `App/`: `.venv/bin/python -m pytest tests/test_guest_child_visa_1079.py tests/test_guest_child_document.py tests/test_guest_visa_hidden.py tests/test_static_versions.py tests/test_guest_record_extraction.py tests/test_design_guest_admin.py -q --tb=short -x`. Browser, 0 skipped: `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_guest_child_visa_1079_browser.py tests/test_guest_form_input_browser.py tests/test_guest_ocr_geometry_browser.py tests/test_guest_browser_e2e.py tests/test_host_geometry.py tests/test_layout_lint_browser.py -q --tb=short -rs`. Test-map guest row: `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_guest_*.py -q --tb=short -x -rs` (0 skipped). Repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance

- [ ] Adult birth date: box hidden; under 18 on the earlier of arrival and today: shown; a checked box is never hidden or unchecked.
- [ ] Typing never flashes the box, focus stays in the birth date field, the checkbox's own change never hides it, and a box ticked by a restored page (`pageshow`) is shown.
- [ ] No JavaScript: box visible as on main. Posted form and stored guest row identical to main for the same inputs.
- [ ] Idempotency and concurrency tests green; S16 browser test green; existing visa and child tests unchanged and green.
- [ ] Browser and geometry tests 0 skipped at 390, 768 and 1280; layout lint run (guest pages report-only, findings copied to the report); six screenshots in `docs/tasks/screenshots-1079/`.
- [ ] `git diff --stat origin/main` touches only section 3 files; design, copy and field order unchanged; both cache keys bumped and `static_versions.json` regenerated (`test_static_versions.py` green).

## 8. Stop and ask

STOP and report `blocked` if: an anchor is missing; the change would need a server, filing, CSS, i18n or host-form edit; anchor 6's test cannot stay green; a browser test skips; a test fails twice on the same cause (attempt 3 of 3); 25 tool calls or 60k tokens (finish the step, commit, `Done: steps 1 to k. Left: steps k+1 to n.`).

## 9. Report

`docs/tasks/1079-report.md`, 600 tokens at most: files changed, each command with its last 5 lines, section 7 ticked, one line per screenshot on what you saw, layout-lint findings for the guest form, deviations, questions. Set this brief `Status: review`. After the fresh Fable diff review, open one PR (body: client-only, filing untouched, no new field or request, S16 already on main). Merge only with `scripts/merge-pr-on-green.sh`.

## 10. Open questions (not blocking)

- **Q1:** microstates (Andorra, Monaco, San Marino, Vatican) are not on `VISA_FREE_COUNTRIES`, so their guests still see the optional visa field. Left as on main; the owner may add them later.
- **Q2:** the plan's S14 (no signature under 15) stays parked with G13.
