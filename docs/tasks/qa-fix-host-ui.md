# qa-fix-host-ui: long-word overflow, phone "fix N fields" line, security prompt modal

Status: ready
Depends on: none | Base commit: main @ pull | Branch: task/qa-fix-host-ui
Executor: Haiku 5.5 | Fits one session (about 22 tool calls)

## 1. Objective
Fix three P1/P2 QA findings (host-properties-01, host-properties-02, host-account-empty-01), verified in code: (A) a long unbroken word in public property page text makes the page 25,000 px wide; (B) on the phone-width property editor an invalid save shows no "fix N fields" line and closed sections hide the bad fields; (C) the one-time "Add a second way in?" dialog renders as an open non-modal box below the fold and is marked shown at render, not when seen.

## 2. Context
AGENTS.md rules 6, 7, 9 apply (light mode, browser tests 0 skipped, 390 px screenshot per changed page, no new copy needed). Findings: /mnt/project-files/qa/findings/host-properties-v2.md (01, 02), host-account-empty-v2.md (01). Verified: `.pp` public page has no CSS for `<li>`/`<p>`; the `.prop-fixline` code in `app.js` hides itself when `!mq.matches` (below 768 px) and nothing listens to native `invalid` events; `base.html` renders `<dialog ... open>`, `templating.py` `_security_prompt` marks `two_factor_prompted_at` inside render, and the only `showModal()` call is in `passkeys.js`, which loads only when passkeys are enabled (so staging/passkeys-off never gets a modal). No false alarms among these three.

## 3. Files
- `App/app/templates/_pp_booking_css.html` (A)
- `App/app/static/app.js` (B, C)
- `App/app/static/passkeys.js` (C, remove 5 lines)
- `App/app/templates/base.html` (C; also the `?v=` key of app.js and passkeys.js)
- `App/app/templating.py` (C)
- `App/app/routes/passkeys.py` (C, new route)
- `App/tests/test_security_prompt_delay.py`, `App/tests/test_passkeys.py` (C, adjust)
- new: `App/tests/test_property_page_overflow.py`
- `App/tests/test_property_fixline_browser.py` (B, add one test)
- `App/app/static/manifest` file written by `test_static_versions.py --write` (whatever path that script writes)

## 4. Steps
Commit after each step: `qa-fix-host-ui step k`. Find every anchor with `grep -nF` first; not found: STOP.

### Step 1: public page overflow (A)
In `App/app/templates/_pp_booking_css.html`, immediately before the closing `</style>` line add:
```
.pp, .pp p, .pp li, .pp h1, .pp h2, .pp h3, .pp summary, .pp-card { overflow-wrap: anywhere; min-width: 0; }
.pp-amenities { padding-left: 0; list-style-position: inside; max-width: 100%; }
```
(The file is included by `property_page.html` in `head_extra`, so this reaches the whole `<main class="pp">`.) Do not change the list markup.

New test `App/tests/test_property_page_overflow.py` (non-browser; copy the `owner` fixture import style from `tests/test_property_page_rules.py` lines 1-45; grep that file for `def owner`): save a page with `house_rules="A" * 3000`, `description="B" * 3000`, `amenities=["C" * 3000]`, publish, GET `/p/<slug>`, assert 200 and `overflow-wrap: anywhere` is in the body and `"A" * 3000` is present (escaped text intact).

### Step 2: phone fix line (B)
In `App/app/static/app.js`, function `initPropertyTabs` (about line 2530), anchors by `grep -nF`:
1. After `var fix = layout.querySelector("[data-prop-fixline]");` add `var clientFailed = false;`.
2. In `fixLine()` replace `var failed = !!document.querySelector("[data-save-summary][data-first-error]");` with `var failed = clientFailed || !!document.querySelector("[data-save-summary][data-first-error]");`.
3. In `fixLine()` replace `if (!items.length || !mq.matches) {` with `if (!items.length || (!mq.matches && !failed)) {` (phone: line shows only after a failed save, server or client; wide behaviour unchanged).
4. After the line `window.setTimeout(fixLine, 0);` add:
```
    // 1030 fix: a native-invalid submit never reaches the server. Open the section of every bad field and build the line once.
    var invalidForm = layout.querySelector("form");
    if (invalidForm) {
      var invalidTimer = null;
      invalidForm.addEventListener("invalid", function (e) {
        var sec = sectionFor(e.target);
        if (sec) sec.open = true;
        clientFailed = true;
        window.clearTimeout(invalidTimer);
        invalidTimer = window.setTimeout(fixLine, 0);
      }, true);
    }
```
(`invalid` does not bubble, hence capture.) Do not touch CSS: `.prop-fixline` already styles at all widths.

Add to `App/tests/test_property_fixline_browser.py` a test `test_a_native_invalid_save_shows_the_fix_line_at_390` copying the existing test's setup, but: viewport 390 (use the same `_context`; if it takes no width, call `page.set_viewport_size({"width": 390, "height": 844})` before `goto`), clear `addr_house_no` and `addr_zip` WITHOUT setting `noValidate`, click the form's save button (`#property-settings-form button[type=submit]`, first), then `page.wait_for_function("() => !document.querySelector('[data-prop-fixline]').hidden")` and assert the line text contains both a "House number" and a "Postcode" link.

### Step 3: security prompt is a true modal, marked when seen (C)
a) `App/app/templates/base.html`: on the `<dialog id="security-prompt" ...>` tag delete the ` open` attribute (grep `id="security-prompt" class`). Replace the comment above it with `{# Task 0004: shown once. app.js opens it as a modal and tells the server it was seen; without JavaScript it stays closed and unmarked. #}`.
b) `App/app/templating.py` in `_security_prompt.prompt()`: delete the whole `if not db.update_if(...): return None` block (4 lines). Keep everything else. Update the docstring sentence "so the account is only marked as prompted when the page that shows it actually renders" to "the account is marked as prompted by POST /account/security-prompt/seen, sent by app.js when the dialog opens".
c) `App/app/routes/passkeys.py`: after `passkey_register_options` add a route (reuse `_owner`; look at the 401 handling right there and mirror it):
```
@router.post("/account/security-prompt/seen")
async def security_prompt_seen(request: Request):
    account = _owner(request)
    if not account:
        return Response(status_code=401)
    db.execute(
        "UPDATE user_account SET two_factor_prompted_at = ? WHERE id = ? AND two_factor_prompted_at IS NULL",
        (db.utcnow(), account["id"]),
    )
    return Response(status_code=204)
```
Add `Response` to the existing `starlette`/`fastapi` import if absent (grep the file's imports).
d) `App/app/static/passkeys.js`: delete the block `var prompt = document.getElementById("security-prompt"); if (prompt && prompt.hasAttribute("open") ... { prompt.close(); prompt.showModal(); }` (about lines 288-292, 5 lines incl. closing brace). Leave `toggleSupport()`.
e) `App/app/static/app.js`: add a function before `initPropertyTabs` and call `initSecurityPrompt();` next to `initPropertyTabs();` (about line 2732):
```
  // The one-time "second way in" prompt: a real modal in view, marked as shown only once it is open.
  function initSecurityPrompt() {
    var dialog = document.getElementById("security-prompt");
    if (!dialog || typeof dialog.showModal !== "function" || !claimNode(dialog, "initSecurityPrompt")) return;
    var meta = document.querySelector('meta[name="csrf-token"]');
    if (!dialog.open) dialog.showModal();
    window.scrollTo(0, 0);
    fetch("/account/security-prompt/seen", {
      method: "POST",
      credentials: "same-origin",
      headers: { "X-CSRF-Token": meta ? meta.getAttribute("content") || "" : "" }
    }).catch(function () {});
  }
```
f) Cache keys: in `base.html` change the `?v=` of `/static/app.js` and `/static/passkeys.js` to `20261109-qa1` (grep each src). Then from `App/`: `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -30`.
g) Tests: in `test_security_prompt_delay.py` `test_security_pop_up_appears_after_seven_days` replace the last line with `assert _prompted_at(account) is None` and add a test that after `client.post("/account/security-prompt/seen", headers={"x-csrf-token": <token>})` (copy how `test_passkeys.py` posts to `/account/passkeys/options` for the token; grep `x-csrf-token\|csrf` in that file) returns 204 and `_prompted_at(account)` is set; to share a client, make `_home_html` callers build their own `TestClient`. In `test_passkeys.py` `test_the_prompt_shows_once_after_the_first_login` (line ~371) change: the second `client.get("/")` now still contains the prompt; then POST `/account/security-prompt/seen`, and only then assert `'id="security-prompt"' not in client.get("/").text` (also the later re-login assert). Line ~392 and ~400 area: read 15 lines around each; if a test relies on render-time marking, add the same POST before its "not in" assert.

## 5. Do not touch
Section chips/list duplication (finding 03), maxlength, tap-target sizes, any other QA finding, `app2.css`, `app.css`, translations, migrations, the retention file (no new personal data).

## 6. Commands (from `App/`, each ending `2>&1 | tail -30`)
1. `.venv/bin/python -m pytest tests/test_property_page_overflow.py tests/test_security_prompt_delay.py tests/test_passkeys.py tests/test_static_versions.py -q --tb=short -x 2>&1 | tail -30`
2. Public property pages row: `.venv/bin/python -m pytest tests/test_property_slug.py tests/test_property_page.py tests/test_property_page_photos.py tests/test_property_page_meta.py tests/test_property_page_rules.py -q --tb=short -x 2>&1 | tail -30`
3. Host pages row: `.venv/bin/python -m pytest tests/test_host_*.py tests/test_host_geometry.py tests/test_property_fixline_browser.py tests/test_design_guardrails_browser.py -q --tb=short -x -rs 2>&1 | tail -30` (0 skipped)
4. `.venv/bin/python -m pytest tests/test_layout_lint_browser.py -q --tb=short -x -rs 2>&1 | tail -30` (0 skipped)
5. From repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`
Fix a red test once; second failure: STOP and report.

## 7. Acceptance
- [ ] Commands 1-5 green, 0 skipped.
- [ ] 390 px screenshot of `/p/<slug>` with a 3000-character house rule: no horizontal scroll (`document.documentElement.scrollWidth <= 390`), in the report.
- [ ] 390 px screenshot of the editor `/apartments/<id>?view=settings` after an empty-required save: fix line visible and the sections open, in the report.
- [ ] 390 px screenshot of `/` for an account that gets the prompt: centred modal in view, backdrop shown (use the `later` locator pattern in `tests/test_0710_v2_mockup_match_browser.py` line 76 only to dismiss afterwards).
- [ ] Per touched page, one sentence of what was seen at 390/768/1280 (rule 10 UX gate) and the design-system checklist ticked in the PR.
- [ ] No other file changed (`git diff --stat`).

## 8. Stop and ask
Anchor not found; `_owner` or `Response` import pattern differs from the brief; a test other than those listed needs the prompt marked at render; command 4 reports a new finding on a touched page (never silence it).

## 9. Report
`docs/tasks/qa-fix-host-ui-report.md`, per executor.md. One PR, never push to main.

## Deferred (not in this brief)
- host-properties-03 chips duplicate sections and "Business details" chip opens "Basic details" (nav redesign, needs an owner choice of chips or list).
- host-properties-04 house rules silently cut at 4000 characters (add maxlength and counter; needs a copy line in both languages).
- host-properties-05/06/07 tap targets, aria-labels on read-only copy inputs, 12-13 px captions (wide CSS sweep).
- host-account-empty-02..05, 07, 08 (empty housebook box, floating help button overlap, security row layout). Item 06 (practice-server banner) is a staging-only artefact: dropped.
- Anything needing passkey hardware.
