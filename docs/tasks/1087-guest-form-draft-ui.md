# 1087: S5 guest form draft: autosave script and "Welcome back" line

Status: todo (ready for the executor once 1082 is merged; the lint has no "ready" status)
Tier: A | Depends on: [1082](1082-guest-form-draft.md) (server half, merged first) | Base: claude/1082-guest-form-draft, rebased on main after 1082 merges | Branch: claude/1087-guest-form-draft-ui
Executor: Fable 5.2 (owner tier override in decisions.md) | Attempts: 3 at most | Fits one session: stop at 25 tool calls or 60k tokens (section 8); reads stay at 150 lines or fewer
Review: a fresh Fable reviews the diff against this brief before the PR opens.
Report: docs/tasks/1087-report.md

## 1. Objective

Plan [speed-and-ease](../plans/speed-and-ease.md) decision **7b**, queue item **S5**, the visible half. A guest who closes the new-guest form half-filled and opens it again on the same device sees one line, "Welcome back. Continue where you left off.", above the form, with the fields they typed filled in. 1082 built the store, the `/draft` route, the purge and the restore into `values`; it ships dark. This brief turns it on: the form posts its draft, and the page says so when it restored one.

**Tier A (orchestrator decision):** the guest form next to police fields. Filing, routes and storage are untouched.

## 2. Context

- **What 1082 gives you (read only, do not edit):** `POST /l/{token}/{reservation_id}/draft` (204, CSRF by the middleware, 120 writes per 15 min, stores only `guest_draft.DRAFT_FIELDS`, sets the `ubyhost_draft` cookie). `guest_form_new` puts `draft_restored`, `draft_url`, `draft_fields` (space-separated names) and `draft_owned` (the device's sent-guest count) in the context; `draft_url` is absent for the host preview. A draft whose posted `draft_owned` no longer matches is dropped on load, so the script must post the count **of the page it runs on**.
- **Design (owner request, hard):** the guest form keeps its exact design. The only visible change is one line, `<p class="g-ok" id="draft-welcome" role="status">`, with the existing `.g-ok` style (`guest.css:943`, the flash line in `base.html:56`), only when a draft was restored. Three `data-` attributes on the form tag. No CSS change, no other markup.
- **Autosave (`initGuestDraft` in `signature.js`):** debounce 2 s after the last `input` or `change`, at most one write per 15 s, flush with `fetch(..., {keepalive: true})` on `pagehide` and on `visibilitychange` to hidden. Body: a new `FormData` with `_csrf` (from `form.elements._csrf.value`, as `_ocr_scan.html:98-104`), `draft_owned` from the form's `data-draft-owned`, and the allowlisted names only. It never reads `#passport_photo`, `#signature` or `#legal_ack`, never writes a field, never touches the DOM. After a real submit it stops (the offline hold of `initSaveRetry` does not count as a submit).
- **No JavaScript:** no autosave, no cookie, the form works as today (it already says JavaScript is needed to finish, `form.html:76`).
- **Copy:** one key `draft_welcome` in `en cs de es fr uk` (step 2). Rule 9: it is the only explanation of the draft on the page.
- **Host form:** `guest_form_admin.html` has no `data-draft-url`, so `initGuestDraft` returns early there.

### Anchors (verified on f1ca4288 plus 1082; re-check each with `grep -nF`)

1. `App/app/templates/guest/form.html:60` `      enctype="multipart/form-data" data-guest-wizard`; `:76` `  <noscript><p class="g-err g-nojs-note" role="alert">{{ t('nojs_needed') }}</p></noscript>`.
2. `App/app/static/signature.js:930` `  function initCheckinRail() {` (its comment block starts at `:926`); `:996` `    initLegalAck();`.
3. `App/app/templates/guest/base.html:84` and `App/app/templates/_signature_script.html:2`: `signature.js?v=20261110-1079` (if main has moved it, use the key you find and bump from there); `App/tests/static_versions.json:162` `"signature.js": {`.
4. `lang_draft_warning`: `App/app/i18n.py` lines 391 (en), 1153 (cs), 1872 (de), 2414 (es), 2956 (fr); `App/app/guest_uk_i18n.py:354` (uk).
5. `App/tests/test_guest_form_input_browser.py`: import line 15, `_fill_step_one` (27), `_open_url` (42), the no-JavaScript test at 87: the model for the browser test.
6. 1082's route: `grep -n "def guest_form_draft" App/app/routes/guest.py` (read only).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/guest/form.html` | edit | Three data attributes, the welcome line (step 1) |
| `App/app/static/signature.js` | edit | `initGuestDraft` and its init call (step 1) |
| `App/app/templates/guest/base.html`, `App/app/templates/_signature_script.html` | edit | Cache key `?v=20261110-1087` |
| `App/tests/static_versions.json` | regenerate | Only by `--write` (step 1) |
| `App/app/i18n.py`, `App/app/guest_uk_i18n.py` | edit | `draft_welcome` (step 2) |
| `App/tests/test_guest_form_draft_1087.py` | create | Source and render tests (step 3) |
| `App/tests/test_guest_form_draft_1087_browser.py` | create | Browser tests (step 4) |
| `docs/tasks/screenshots-1087/` | create | `welcome-back-390.png`, `fresh-390.png` (plus 768 and 1280 for the UX gate) |
| `docs/tasks/1087-report.md` | create | Report, plus `Status: review` here |

## 4. Steps (commit after each: `1087 step k`)

1. Confirm anchors 1 to 6; any missing: STOP. `form.html` anchor 1 line 60 becomes `      enctype="multipart/form-data" data-guest-wizard{% if draft_url %} data-draft-url="{{ draft_url }}" data-draft-fields="{{ draft_fields }}" data-draft-owned="{{ draft_owned }}"{% endif %}`. Directly under the `<noscript>` line add `  {% if draft_restored %}<p class="g-ok" id="draft-welcome" role="status">{{ t('draft_welcome') }}</p>{% endif %}`. Nothing else in `form.html`.
   In `signature.js`, above anchor 2's comment block, add a comment (what, why, no JavaScript means no draft, never the photo or signature) and `function initGuestDraft()`, 2-space indent like its neighbours:
   - Return early unless `#guest-form` has `data-draft-url` and `window.fetch` and `window.FormData` exist.
   - `DEBOUNCE_MS = 2000`, `MIN_GAP_MS = 15000`; state `timer`, `last = 0`, `dirty = false`, `stopped = false`.
   - `body()`: `new FormData()`; append `_csrf` from `form.elements._csrf.value` and `draft_owned` from `data-draft-owned`; then for each name of `data-draft-fields`: a checkbox appends `"1"` only when checked; any other element appends its `value`.
   - `send(keepalive)`: if `stopped || !dirty` return; `dirty = false; last = Date.now();` `fetch(url, {method: "POST", body: body(), credentials: "same-origin", keepalive: !!keepalive}).catch(function () { dirty = true; });`.
   - `schedule()`: if `stopped` return; `dirty = true`; clear `timer`; wait `Math.max(DEBOUNCE_MS, MIN_GAP_MS - (Date.now() - last))`, then `send(false)`.
   - Listeners: `form` `input` and `change` call `schedule`; `window` `pagehide`, and `document` `visibilitychange` when `document.visibilityState === "hidden"`, clear the timer and `send(true)`; `form` `submit`: if `event.defaultPrevented` return, else `stopped = true` and clear the timer.
   Add `    initGuestDraft();` directly under anchor 2's `initLegalAck();`. Bump both cache keys (anchor 3) to `20261110-1087`. From `App/` run `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -30` and commit `tests/static_versions.json` (diff: only the `signature.js` entry). If you edit `signature.js` again later, bump to `20261110-1087b` and rerun it.
2. `draft_welcome` directly under each `lang_draft_warning` line (anchor 4): en `"Welcome back. Continue where you left off."`, cs `"Vítejte zpět. Pokračujte tam, kde jste skončili."`, de `"Willkommen zurück. Machen Sie dort weiter, wo Sie aufgehört haben."`, es `"Bienvenido de nuevo. Continúe donde lo dejó."`, fr `"Bon retour. Reprenez là où vous vous êtes arrêté."`, uk `"З поверненням. Продовжте з того місця, де зупинилися."`. Run command A.
3. **`App/tests/test_guest_form_draft_1087.py`** (no browser; seed with `_cleanup`, `_seed`, `_payload` of `test_guest_child_document.py`, lines 39 to 130 only):
   a. Source pin: inside `initGuestDraft` there is no `.value =`, no `.checked =`, no `innerHTML`, no `passport_photo`, `signature` or `legal_ack`; it contains `keepalive`, `pagehide`, `draft_owned`, `2000` and `15000`. `form.html` has exactly one `id="draft-welcome"` and one `data-draft-owned`.
   b. Render: after a `/draft` post, `/new` from the same client has `#draft-welcome` with the text in each of the six languages (`?lang=`); a fresh client gets `data-draft-url` (it can start a draft) but no welcome line; `/edit/{guest_id}` and the host preview have no `data-draft-url`; `data-draft-owned` equals the number of guests this client has sent.
   Run command A.
4. **`App/tests/test_guest_form_draft_1087_browser.py`**, modelled on anchor 5 (`_open_url` with mail off, `_fill_step_one`, `Guest`, `browser`, `live_server`). One `browser.new_context(viewport={"width": W, "height": 812})` per device:
   a. **Close and return at 390 px:** fill step one, wait for the `/draft` response (`page.expect_response` on `**/draft*`, status 204), `page.close()`, open a new page in the **same** context at the same URL: `#draft-welcome` visible with the English text, every step-one field has the typed value, signature and photo empty, the wizard on step one, no horizontal scroll (`scrollWidth <= innerWidth`), `Guest.check_layout` where it fits. Screenshot `docs/tasks/screenshots-1087/welcome-back-390.png` (full page).
   b. **Another device:** a second context opens the same URL: no `#draft-welcome`, `#first_name` empty. Screenshot `fresh-390.png`.
   c. **Debounce and throttle in the page:** type into `#surname` ten times within 3 s: at most one `/draft` request in those 3 s (`page.on("request")`); none of the requests' post data contains `signature` or `passport_photo`.
   d. **Sent, same phone:** complete and send the form as `test_guest_browser_e2e.py` does for one guest, then open `/new` in the same context: no `#draft-welcome`, fields empty. Then fill step one for person 2, wait for the draft, return: person 2's values only.
   e. **Design unchanged:** on the restored page, record the `#first_name` top and the step-one card height, then remove `#draft-welcome` with `page.evaluate`: both drop by the line's own height plus its vertical margins, within 1 px, and every step-one `.g-field` keeps its `left` and `width`. Repeat at 768 and 1280 (`@pytest.mark.parametrize("width", [390, 768, 1280])`) and save `welcome-back-768.png` and `welcome-back-1280.png` for the UX gate.
   f. **No JavaScript** (`java_script_enabled=False`, as anchor 5 line 87): the form renders, no `#draft-welcome`, no `ubyhost_draft` cookie in the context after the page loads.
   Look at each screenshot once and write one line each in the report. Run command B.
5. Run section 6, then write the report.

## 5. Do not touch

Everything 1082 built (`guest_draft.py`, the migration files, `routes/guest.py`, `scheduler.py`, `retention.py`, `cookie_inventory.py`), `reporting.py`, `validation.py`, `submit_*`, `App/app/ubyport/`, `_ocr_scan.html`, `guest_form_admin.html`, archive templates, any CSS file, any other function in `signature.js`, any dependency. Never push to `main`.

## 6. Commands (each ends `2>&1 | tail -30`)

From `App/`:
- A: `.venv/bin/python -m pytest tests/test_guest_form_draft_1087.py tests/test_guest_form_draft_1082.py tests/test_static_versions.py tests/test_guest_languages.py tests/test_no_em_dashes.py tests/test_guest_child_visa_1079.py tests/test_design_guest_admin.py -q --tb=short -x`.
- B (0 skipped): `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_guest_form_draft_1087_browser.py tests/test_guest_form_input_browser.py tests/test_guest_browser_e2e.py tests/test_host_geometry.py tests/test_layout_lint_browser.py -q --tb=short -rs`.
- Test-map guest row: `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_guest_*.py -q --tb=short -x -rs` (0 skipped).

Repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance

- [ ] Close and return on the same device at 390 px: "Welcome back. Continue where you left off." and the typed fields; another device sees nothing; after a send, the next person's form is empty.
- [ ] Autosave debounced (2 s), at most one write per 15 s, flushed on `pagehide`; never posts the photo, signature or tick; stops after a real submit.
- [ ] No JavaScript: the form works as today, no cookie, no line.
- [ ] Guest form design unchanged apart from the one line (4e); no CSS change; the key in six languages.
- [ ] Browser tests 0 skipped; layout lint run (guest pages report-only, findings in the report); screenshots in `docs/tasks/screenshots-1087/`, one line each.
- [ ] `git diff --stat origin/main` touches only section 3 files; cache keys bumped and `static_versions.json` regenerated.

## 8. Stop and ask

STOP and report `blocked` if: 1082 is not merged or an anchor is missing; the change would need a route, storage, CSS or filing edit; a browser test skips; a test fails twice on the same cause (attempt 3 of 3); 25 tool calls or 60k tokens (finish the step, commit, `Done: steps 1 to k. Left: steps k+1 to n.`).

## 9. Report

`docs/tasks/1087-report.md`, 600 tokens at most: files changed, each command with its last 5 lines, section 7 ticked, one line per screenshot on what you saw, layout-lint findings for the guest form, deviations, questions. Set this brief `Status: review`. After the fresh Fable diff review, open one PR (body: client-only on top of 1082, no new field, cookie or request beyond 1082's, filing untouched). Merge only with `scripts/merge-pr-on-green.sh`.
