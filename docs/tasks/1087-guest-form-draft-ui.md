# 1087: S5 guest form draft: autosave script and "Welcome back" line

Status: review
Tier: A | Depends on: [1082](1082-guest-form-draft.md) (server half, PR #876, merged first) | Base: claude/1082-guest-form-draft plus origin/main (step 0) | Branch: claude/1087-guest-form-draft-ui
Executor: Fable 5.2 (owner tier override in decisions.md) | Attempts: 3 at most | Fits one session: stop at 60 tool calls or 60k tokens (section 8; the Fable executor's cap under the owner's tier override); reads stay at 150 lines or fewer
Review: a fresh Fable reviews the diff against this brief before the PR opens.
Report: docs/tasks/1087-report.md

## 1. Objective

Plan [speed-and-ease](../plans/speed-and-ease.md) decision **7b**, queue item **S5**, the visible half. A guest who closes the new-guest form half-filled and opens it again on the same device sees one line, "Welcome back. Continue where you left off.", above the form, with the fields they typed filled in. 1082 built the store, the `/draft` route, the purge and the restore into `values`; it ships dark. This brief turns it on: the form posts its draft (also after a language switch or a validation error), and the page says so when it restored one.

**Tier A (orchestrator decision):** the guest form next to police fields. Filing and storage are untouched; the only route change is adding the draft keys to two existing renders (step 2).

## 2. Context

- **What 1082 gives you (read only):** `POST /l/{token}/{reservation_id}/draft` (204, CSRF by the middleware, 120 writes per 15 min, stores only `guest_draft.DRAFT_FIELDS`, sets the `ubyhost_draft` cookie). `guest_form_new` puts `draft_restored`, `draft_url`, `draft_fields` (space-separated names) and `draft_owned` (the device's sent-guest count, from `_draft_owned(request)`) in the context; `draft_url` is absent for the host preview. A draft whose posted `draft_owned` no longer matches is dropped on load, so the script posts the count **of the page it runs on**.
- **Gap this brief closes:** the language switch (`/relang`, the `render_guest(request, "guest/form.html", context)` at the end of the relang handler, about `guest.py:2129` after 1082) and the save's validation error (the `status_code=422` render in `guest_form_save`, about `:2301` after 1082) render `form.html` without `draft_url`, so autosave would stop there. Step 2 adds the keys to both, for a new guest only (`existing` is None), never for the host preview, and never `draft_restored` (no welcome line on those renders).
- **Language buttons:** they already carry `data-lang-draft` (`base.html:46`, `<button type="submit" form="guest-form" formaction="{{ lang_relang_url }}?lang={{ code }}" formnovalidate data-lang-draft ...>`); `initLanguageDraft` and `initSaveRetry` use it. A submit whose `event.submitter` has `data-lang-draft` flushes the draft (`send(true)`) and does **not** stop autosave. Only a real save stops it.
- **Design (owner request, hard):** the guest form keeps its exact design. The only visible change is one line, `<p class="g-ok" id="draft-welcome" role="status">`, with the existing `.g-ok` style (`guest.css:943`, the flash line in `base.html:56`), only when a draft was restored. Three `data-` attributes on the form tag. No CSS change, no other markup.
- **Autosave (`initGuestDraft` in `signature.js`):** debounce 2 s after the last `input` or `change` **on an allowlisted field** (events from the legal tick, the photo input, the signature or anything not in `data-draft-fields` are ignored), at most one write per 15 s, flush with `fetch(..., {keepalive: true})` on `pagehide` and on `visibilitychange` to hidden. Body: a new `FormData` with `_csrf` (from `form.elements._csrf.value`, as `_ocr_scan.html:98-104`), `draft_owned` from `data-draft-owned`, and each allowlisted name **that has an element on the page** (`party_size` is only rendered when `ask_party_size`, `form.html:100`). It never reads `#passport_photo`, `#signature` or `#legal_ack`, never writes a field, never touches the DOM.
- **No JavaScript:** no autosave, no cookie, the form works as today (it already says JavaScript is needed to finish, `form.html:76`).
- **Copy:** one key `draft_welcome` in `en cs de es fr uk` (step 3). Rule 9: it is the only explanation of the draft on the page.
- **Host form:** `guest_form_admin.html` has no `data-draft-url`, so `initGuestDraft` returns early there.

### Anchors (verified on f1ca4288; line numbers in `guest.py` move with 1082, so find each with `grep -nF`)

1. `App/app/templates/guest/form.html:60` `      enctype="multipart/form-data" data-guest-wizard`; `:76` `  <noscript><p class="g-err g-nojs-note" role="alert">{{ t('nojs_needed') }}</p></noscript>`.
2. `App/app/static/signature.js:930` `  function initCheckinRail() {` (its comment block starts at `:926`); `:996` `    initLegalAck();`.
3. `App/app/templates/guest/base.html:84` and `App/app/templates/_signature_script.html:2`: `signature.js?v=20261110-1079` (if main has moved it, bump from the key you find); `App/tests/static_versions.json:162` `"signature.js": {`.
4. `lang_draft_warning`: `App/app/i18n.py` lines 391 (en), 1153 (cs), 1872 (de), 2414 (es), 2956 (fr); `App/app/guest_uk_i18n.py:354` (uk).
5. `App/tests/test_guest_form_input_browser.py`: import line 15, `_fill_step_one` (27), `_open_url` (42), the no-JavaScript test at 87, the language-button test at 57: the models for the browser test.
6. `App/app/routes/guest.py`: `    return _with_lang(render_guest(request, "guest/form.html", context), lang)` (the relang render; unique) and `        return _with_lang(render_guest(request, "guest/form.html", context, status_code=422), lang)` (the 422 render; unique); in both handlers `existing` is the saved guest or None. 1082's `def guest_form_draft`, `def _draft_owned` and the `new_context["draft_url"]` lines in `guest_form_new` (read only, the model for step 2).
7. `App/app/templates/guest/base.html:46` the language button with `data-lang-draft` (read only).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/routes/guest.py` | edit | `_add_draft_keys` and two calls (step 2) |
| `App/app/templates/guest/form.html` | edit | Three data attributes, the welcome line (step 1) |
| `App/app/static/signature.js` | edit | `initGuestDraft` and its init call (step 1) |
| `App/app/templates/guest/base.html`, `App/app/templates/_signature_script.html` | edit | Cache key `?v=20261110-1087` (only the `signature.js` key) |
| `App/tests/static_versions.json` | regenerate | Only by `--write` (step 1) |
| `App/app/i18n.py`, `App/app/guest_uk_i18n.py` | edit | `draft_welcome` (step 3) |
| `App/tests/test_guest_form_draft_1087.py` | create | Source and render tests (step 4) |
| `App/tests/test_guest_form_draft_1087_browser.py` | create | Browser tests (step 5) |
| `docs/tasks/screenshots-1087/` | create | `fresh-{390,768,1280}.png`, `welcome-back-{390,768,1280}.png` |
| `docs/tasks/1087-report.md` | create | Report, plus `Status: review` here |

## 4. Steps (commit after each: `1087 step k`)

0. **Base.** `git fetch origin main && git merge origin/main` into this branch (1082 is PR #876). Then `grep -n guest_form_draft App/app/routes/guest.py 2>&1 | tail -30` and `git log origin/main --oneline -5 2>&1 | tail -30`. If `guest_form_draft` is not in `guest.py` on `origin/main`, or the merge conflicts: STOP, report `blocked` ("1082 not on main"). Commit the merge as `1087 step 0`.
1. Confirm anchors 1 to 7; any missing: STOP. `form.html` anchor 1 line 60 becomes `      enctype="multipart/form-data" data-guest-wizard{% if draft_url %} data-draft-url="{{ draft_url }}" data-draft-fields="{{ draft_fields }}" data-draft-owned="{{ draft_owned }}"{% endif %}`. Directly under the `<noscript>` line add `  {% if draft_restored %}<p class="g-ok" id="draft-welcome" role="status">{{ t('draft_welcome') }}</p>{% endif %}`. Nothing else in `form.html`.
   In `signature.js`, above anchor 2's comment block, add a comment (what, why, no JavaScript means no draft, never the photo or signature) and `function initGuestDraft()`, 2-space indent like its neighbours:
   - Return early unless `#guest-form` has `data-draft-url` and `window.fetch` and `window.FormData` exist. `names` = `data-draft-fields` split on spaces (empty strings dropped).
   - `DEBOUNCE_MS = 2000`, `MIN_GAP_MS = 15000`; state `timer`, `last = 0`, `dirty = false`, `stopped = false`.
   - `body()`: `new FormData()`; append `_csrf` from `form.elements._csrf.value` and `draft_owned` from `data-draft-owned`; for each name in `names`: `var el = form.elements[name]; if (!el) return;` (skip absent fields such as `party_size`); a checkbox appends `"1"` only when checked; any other element appends its `value`.
   - `send(keepalive)`: if `stopped || !dirty` return; `dirty = false; last = Date.now();` `fetch(url, {method: "POST", body: body(), credentials: "same-origin", keepalive: !!keepalive}).catch(function () { dirty = true; });`.
   - `schedule(event)`: if `stopped` return; if `!event.target || names.indexOf(event.target.name) < 0` return (the tick, the photo, the signature and the wizard's own controls never post); `dirty = true`; clear `timer`; wait `Math.max(DEBOUNCE_MS, MIN_GAP_MS - (Date.now() - last))`, then `send(false)`.
   - `flush()`: clear the timer, `send(true)`.
   - Listeners: `form` `input` and `change` call `schedule`; `window` `pagehide` calls `flush`; `document` `visibilitychange` calls `flush` when `document.visibilityState === "hidden"`; `form` `submit`: if `event.defaultPrevented` return (the offline hold of `initSaveRetry`); if `event.submitter && event.submitter.hasAttribute("data-lang-draft")`, `flush()` and return (autosave stays on; the next page continues it); else `stopped = true` and clear the timer.
   Add `    initGuestDraft();` directly under anchor 2's `initLegalAck();`. Bump the `signature.js` cache key in both files (anchor 3) to `20261110-1087`. From `App/` run `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -30` and commit `tests/static_versions.json` (diff: only the `signature.js` entry). If you edit `signature.js` again later, bump to `20261110-1087b` and rerun it.
2. **Draft keys on the two re-renders (`routes/guest.py`).** Directly above `def _with_lang` add:
   ```python
   def _add_draft_keys(context, request: Request, apartment, existing, token: str, reservation_id: int, lang: str) -> None:
       """Brief 1087: keep autosave on after a language switch or a validation error.

       New guests only, never the host preview, and never the welcome line.
       """
       if existing or _host_owns_apartment(request, apartment):
           return
       context["draft_url"] = f"/l/{token}/{reservation_id}/draft" + _lang_q(lang)
       context["draft_fields"] = " ".join(guest_draft.DRAFT_FIELDS)
       context["draft_owned"] = _draft_owned(request)
   ```
   Directly above each anchor 6 render line (relang and 422) add, at that line's indent, `_add_draft_keys(context, request, apartment, existing, token, reservation_id, lang)`. Nothing else in either handler; `guest_form_new` stays as 1082 left it. Run command A.
3. `draft_welcome` directly under each `lang_draft_warning` line (anchor 4): en `"Welcome back. Continue where you left off."`, cs `"Vítejte zpět. Pokračujte tam, kde jste skončili."`, de `"Willkommen zurück. Machen Sie dort weiter, wo Sie aufgehört haben."`, es `"Bienvenido de nuevo. Continúe donde lo dejó."`, fr `"Bon retour. Reprenez là où vous vous êtes arrêté."`, uk `"З поверненням. Продовжте з того місця, де зупинилися."`. Run command A.
4. **`App/tests/test_guest_form_draft_1087.py`** (no browser; seed with `_cleanup`, `_seed`, `_payload` of `test_guest_child_document.py`, lines 39 to 130 only):
   a. Source pin: inside `initGuestDraft` there is no `.value =`, no `.checked =`, no `innerHTML`, no `passport_photo`, `signature` or `legal_ack`; it contains `keepalive`, `pagehide`, `draft_owned`, `data-lang-draft`, `if (!el) return;`, `names.indexOf(`, `2000` and `15000`. `form.html` has exactly one `id="draft-welcome"` and one `data-draft-owned`.
   b. Render: after a `/draft` post, `/new` from the same client has `#draft-welcome` with the text in each of the six languages (`?lang=`); a fresh client gets `data-draft-url` but no welcome line; `/edit/{guest_id}` and the host preview have no `data-draft-url`; `data-draft-owned` equals the number of guests this client has sent.
   c. Re-renders: a `/relang` post of a new-guest form and a `/save` post that fails validation (422) both render `data-draft-url` and `data-draft-owned`, and no `#draft-welcome`; the same posts with a `guest_id` of a saved guest (edit) render no `data-draft-url`.
   Run command A.
5. **`App/tests/test_guest_form_draft_1087_browser.py`**, modelled on anchor 5 (`_open_url` with mail off, `_fill_step_one`, `Guest`, `browser`, `live_server`). One `browser.new_context(viewport={"width": W, "height": 812})` per device; count `/draft` requests with `page.on("request")`:
   a. **Close and return at 390 px:** fill step one, wait for the `/draft` response (`page.expect_response` on `**/draft*`, status 204), `page.close()`, open a new page in the **same** context at the same URL: `#draft-welcome` visible with the English text, every step-one field has the typed value, signature and photo empty, the wizard on step one, no horizontal scroll (`scrollWidth <= innerWidth`), `Guest.check_layout` where it fits.
   b. **Another device:** a second context opens the same URL: no `#draft-welcome`, `#first_name` empty.
   c. **Debounce and throttle:** type into `#surname` ten times within 3 s: at most one `/draft` request in those 3 s; none of the posts contains `signature`, `passport_photo` or `legal_ack`. Ticking `#legal_ack` alone and waiting 3 s sends no `/draft`.
   d. **Flush on hide:** type into `#first_name`, and within 2 s dispatch `visibilitychange` with `document.visibilityState` reported `hidden` (`page.evaluate`: `Object.defineProperty(document, "visibilityState", {configurable: true, get: () => "hidden"})`, then `document.dispatchEvent(new Event("visibilitychange"))`): exactly one `/draft` request. A second hide with no typing in between: no further request. Also on a form without the party-size field (`ask_party_size` false): the flushed post has no `party_size` key and still answers 204.
   e. **Language switch keeps the draft:** type step one, click the `cs` language button (`[data-lang-draft][lang="cs"]`): one `/draft` request goes out before the navigation; on the re-rendered Czech page `#guest-form` has `data-draft-url`; typing there sends a `/draft` again; closing and reopening `/new?lang=cs` in the same context shows `#draft-welcome` in Czech with the typed values.
   f. **Sent, same phone:** complete and send the form as `test_guest_browser_e2e.py` does for one guest, then open `/new` in the same context: no `#draft-welcome`, fields empty. Fill step one for person 2, wait for the draft, return: person 2's values only.
   g. **Design unchanged, at 390, 768 and 1280** (`@pytest.mark.parametrize("width", [390, 768, 1280])`): on the restored page, record the `#first_name` top and the step-one card height, then remove `#draft-welcome` with `page.evaluate`: both drop by the line's own height plus its vertical margins, within 1 px, and every step-one `.g-field` keeps its `left` and `width`. Screenshots (full page) into `docs/tasks/screenshots-1087/`: `fresh-{width}.png` (no draft) and `welcome-back-{width}.png` (restored), six in all.
   h. **No JavaScript** (`java_script_enabled=False`, as anchor 5 line 87): the form renders, no `#draft-welcome`, no `ubyhost_draft` cookie in the context after the page loads.
   Look at each screenshot once and write one line each in the report. Run command B.
6. Run section 6, then write the report.

## 5. Do not touch

Everything else 1082 built (`guest_draft.py`, the migration files, `scheduler.py`, `retention.py`, `cookie_inventory.py`, the `/draft` route, `guest_form_new`, the delete in `guest_form_save`), `reporting.py`, `validation.py`, `submit_*`, `App/app/ubyport/`, `_ocr_scan.html`, `guest_form_admin.html`, archive templates, any CSS file, any other function in `signature.js` (`initLanguageDraft` and `initSaveRetry` stay as they are), the language button markup, any dependency. Never push to `main`.

## 6. Commands (each ends `2>&1 | tail -30`)

From `App/`:
- A: `.venv/bin/python -m pytest tests/test_guest_form_draft_1087.py tests/test_guest_form_draft_1082.py tests/test_static_versions.py tests/test_guest_languages.py tests/test_no_em_dashes.py tests/test_guest_child_visa_1079.py tests/test_design_guest_admin.py -q --tb=short -x`.
- B (0 skipped): `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_guest_form_draft_1087_browser.py tests/test_guest_form_input_browser.py tests/test_guest_browser_e2e.py tests/test_host_geometry.py tests/test_layout_lint_browser.py -q --tb=short -rs`.
- Test-map guest row: `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_guest_*.py -q --tb=short -x -rs` (0 skipped).

Repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance

- [ ] 1082 on main and merged in (step 0).
- [ ] Close and return on the same device at 390 px: "Welcome back. Continue where you left off." and the typed fields; another device sees nothing; after a send, the next person's form is empty.
- [ ] Autosave debounced (2 s), at most one write per 15 s, only for allowlisted fields; one flush on hide and none on a second hide; absent fields skipped; never posts the photo, signature or tick.
- [ ] Language switch flushes and keeps autosave on; the relang and 422 renders carry the draft keys for new guests only.
- [ ] No JavaScript: the form works as today, no cookie, no line.
- [ ] Guest form design unchanged apart from the one line (5g); no CSS change; the key in six languages.
- [ ] Browser tests 0 skipped; layout lint run (guest pages report-only, findings in the report); six screenshots (fresh and welcome back at 390, 768, 1280), one line each.
- [ ] `git diff --stat origin/main` touches only section 3 files; cache key bumped and `static_versions.json` regenerated.

## 8. Stop and ask

STOP and report `blocked` if: step 0 finds 1082 not on main or the merge conflicts; an anchor is missing; the change would need a storage, CSS, filing or language-button edit, or a route edit beyond step 2; a browser test skips; a test fails twice on the same cause (attempt 3 of 3); 60 tool calls or 60k tokens (finish the step, commit, `Done: steps 0 to k. Left: steps k+1 to 6.`).

## 9. Report

`docs/tasks/1087-report.md`, 600 tokens at most: files changed, each command with its last 5 lines, section 7 ticked, one line per screenshot on what you saw, layout-lint findings for the guest form, deviations, questions. Set this brief `Status: review`. After the fresh Fable diff review, open one PR (body: client-side on top of 1082 plus the draft keys on two re-renders; no new field, cookie or request beyond 1082's; filing untouched). Merge only with `scripts/merge-pr-on-green.sh`.
