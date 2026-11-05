# 0959: Keep the guest draft when the language changes

Status: blocked - the test fails on name case: /relang re-draws names uppercased (validation.normalise_name), the test asserts the typed case. See docs/tasks/0959-report.md.
Depends on: none (batch B01) | Base commit: 7b0355c | Branch: codex/0959-guest-draft-language
Executor: Haiku 5.5 | Fits one session: 30 tool calls, checkpoint 60k tokens

## 1. Objective

Switching language on the guest check-in form (finding G01) must keep the typed identity, birth date, nationality, document, address and visa/purpose values, and the step the guest is on. Today the menu entries are plain `<a href="/new?lang=cs">` links, so the browser reloads an empty form (nationality lost, so the step count also jumps from 3 to 4).

Not in scope: any other batch, 0958 calendar work, filing, signature payload meaning, retention, schema, dependencies, the host UI.

## 2. Context

Decision (one approach): the form is entirely client-side until Save, so nothing is stored server-side. In the form page only, each language menu entry becomes a `<button type="submit" form="guest-form" formaction=".../relang?lang=XX" formnovalidate>`. It POSTs the open form (with its `_csrf` field) to a new route `POST /l/{token}/{reservation_id}/relang`. The server reads the fields from that one request, draws the same form again in the target language with those values and the same step, and stores nothing. No data in the URL (only `?lang=`), no storage, no new field. It works without JavaScript (the form is then one page). The drawn signature, the acknowledgement tick and a chosen passport photo are NOT carried (they attest to the old text, and a file cannot be refilled); JS asks `confirm()` first when one of them exists and, on Cancel, `preventDefault()` leaves the draft untouched. Other guest pages keep the plain links. Validation errors are not carried over a language switch: the guest gets them again on Save.

Rules that apply: AGENTS.md hard rules 2, 3, 5 (no SQL change here), 6, 7 (browser + geometry, 0 skipped, screenshots), 9. Never print guest data in the report.

### Current anchors (each must be found verbatim, else STOP, section 8)

`App/app/templates/guest/base.html` lines 14, 36-38, 72:
```
  <link rel="stylesheet" href="/static/guest.css?v=20261104-0910b">
```
```
        {% for code, url in lang_urls.items() %}
        <a href="{{ url }}" class="{{ 'on' if lang == code }}"{% if lang == code %} aria-current="true"{% endif %} hreflang="{{ code }}" lang="{{ code }}">{{ guest_endonyms[code] }}</a>
        {% endfor %}
```
```
{% if load_signature_js %}<script src="/static/signature.js?v=20261021-0196"></script>{% endif %}
```
`App/app/templates/_signature_script.html` line 2:
```
<script src="/static/signature.js?v=20261021-0196"></script>
```
`App/app/templates/guest/form.html` lines 51-56:
```
<form method="post" action="/l/{{ token }}/{{ reservation.id }}/save?lang={{ lang }}"
      enctype="multipart/form-data" data-guest-wizard
      data-next-label="{{ t('next_step') }}" data-back-label="{{ t('previous_step') }}"
      data-progress-label="{{ t('form_step_progress', current='__CURRENT__', total='__TOTAL__') }}"
      data-progress-title="{{ t('form_step_progress_title', progress='__PROGRESS__', title='__TITLE__') }}">
  <input type="hidden" name="_csrf" value="{{ csrf_token }}">
```
`App/app/static/guest.css` lines 140-153:
```
.g-lang-list a {
  display: flex;
  align-items: center;
  min-height: 44px;
  padding: 0 12px;
  border-radius: 10px;
  color: var(--g-ink);
  font-size: 15px;
  font-weight: 600;
  text-decoration: none;
  transition: background 0.16s var(--g-ease), color 0.16s var(--g-ease);
}
.g-lang-list a:hover { background: var(--g-bg); }
.g-lang-list a.on { background: var(--g-ink); color: var(--g-bg); font-weight: 700; }
```
`App/app/static/signature.js` (wizard, in `initGuestWizard`), and the init list:
```
    var active = Math.max(0, steps.findIndex(function (step) { return step.querySelector(".bad, .err:not(:empty)"); }));
```
```
      active = Math.max(0, Math.min(index, steps.length - 1));
```
```
    initGuestWizard();
```
`App/app/routes/guest.py`:
```
    context["lang_urls"] = _lang_urls(request, form_path)
```
```
@router.post("/l/{token}/{reservation_id}/save")
```
`App/app/i18n.py`: five lines starting `        "signature_kept": ` (en line 364, cs 1080, de 1750, es 2241, fr 2732). `App/app/guest_uk_i18n.py` line 324: `    "signature_kept": `.

## 3. Files (exhaustive)

| Path (under App/ unless noted) | Action | What |
|---|---|---|
| app/routes/guest.py | edit | new POST route `relang`; one context line |
| app/templates/guest/base.html | edit | menu entries as buttons when `lang_relang_url` is set; bump 2 cache keys |
| app/templates/guest/form.html | edit | form id, `data-start-step`, `data-lang-warning`, hidden `_step` |
| app/templates/_signature_script.html | edit | cache key bump only |
| app/static/signature.js | edit | start step, publish active step, language-draft guard |
| app/static/guest.css | edit | style `button` like `a` in the menu |
| app/i18n.py | edit | key `lang_draft_warning` in en, cs, de, es, fr |
| app/guest_uk_i18n.py | edit | same key, uk |
| tests/test_guest_browser_e2e.py | append | one regression test |
| tests/static_versions.json | regenerate | via the script, not by hand |
| docs/tasks/0959-report.md | create | report |

Anything else = STOP. (`routes/guest.py` and the i18n files are listed because the chosen approach needs a route and one warning sentence in every guest language; the language-parity test requires all six.)

## 4. Steps

### Step 1: route and context (`app/routes/guest.py`)

1a. Replace `    context["lang_urls"] = _lang_urls(request, form_path)` with:
```
    context["lang_urls"] = _lang_urls(request, form_path)
    # 0959: the menu on this page posts the open form here, so a language
    # change keeps what the guest typed. Nothing is stored.
    context["lang_relang_url"] = _guest_link(token, reservation["id"]) + "/relang"
```

1b. Insert immediately BEFORE the line `@router.post("/l/{token}/{reservation_id}/save")` (keep two blank lines either side):
```
@router.post("/l/{token}/{reservation_id}/relang")
async def guest_form_relang(token: str, reservation_id: int, request: Request):
    """0959: draw the open form again in another language, keeping the answers.

    The language menu posts the form here with ``?lang=`` set to the new
    language. The answers are read from this one request and drawn back into
    the form; nothing is stored and no answer goes into a URL. A drawn
    signature and the acknowledgement tick are left out on purpose: they attest
    to text the guest can no longer see. A chosen photo cannot be refilled.
    """
    lang = _language(request)
    apartment, token, early = _open_link(request, token, lang)
    if early:
        return early
    pin_guard = _require_pin(request, token, lang)
    if pin_guard:
        return pin_guard
    reservation = _reservation_for_guest(apartment, reservation_id, request)
    if not reservation:
        return _unavailable(request, lang, "stay_gone", 404, token)
    throttle = _throttle_guest_post(request, token, "guest_relang", lang)
    if throttle:
        return throttle
    claim_guard = _require_claim_session(request, reservation, token, lang)
    if claim_guard:
        return _with_lang(claim_guard, lang)

    form = await request.form()
    existing = None
    raw_id = (form.get("guest_id") or "").strip()
    if raw_id.isdigit() and int(raw_id) in _owned_ids(request):
        existing = db.query_one(
            "SELECT * FROM guest WHERE id = ? AND reservation_id = ?",
            (int(raw_id), reservation_id),
        )
    if existing:
        if existing["submit_state"] == reporting.SENT:
            return _unavailable(request, lang, "already_filed", 403, token)
        if existing["restricted_at"] or reporting.guest_form_locked(existing, reservation):
            return _unavailable(request, lang, "form_locked", 403, token)

    values = validation.normalise_guest(_guest_form_raw(form, apartment), clamp=False)
    stay_from, stay_to = _stay_dates_from_form(
        form, (reservation["date_from"], reservation["date_to"])
    )
    context = _form_context(
        request,
        apartment,
        reservation,
        existing,
        lang,
        values=values,
        back_url=_form_back_url(token, apartment, reservation_id, lang, editing=bool(existing)),
        token=token,
    )
    context["values"].update(
        {
            "stay_from": stay_from,
            "stay_to": stay_to,
            "child_in_passport": bool(form.get("child_in_passport")),
            "parent_doc_number": form.get("parent_doc_number") or "",
            "party_size": (form.get("party_size") or "").strip(),
            "signature": "",
            "legal_ack": "",
        }
    )
    step = (form.get("_step") or "").strip()
    context["start_step"] = int(step) if step.isdigit() and len(step) <= 2 else 0
    return _with_lang(render_guest(request, "guest/form.html", context), lang)


```
Run: `.venv/bin/python -c "import app.routes.guest" 2>&1 | tail -30` (from App/). Commit later (single step 1 commit, see section 6).

### Step 2: templates

2a. `guest/base.html`: replace the 3-line `{% for code, url ... %}` block with:
```
        {% for code, url in lang_urls.items() %}
        {% if lang_relang_url %}
        {# 0959: on the form the entry posts the open form back, so the typed answers survive; see guest_form_relang. #}
        <button type="submit" form="guest-form" formaction="{{ lang_relang_url }}?lang={{ code }}" formnovalidate data-lang-draft class="{{ 'on' if lang == code }}"{% if lang == code %} aria-current="true"{% endif %} lang="{{ code }}">{{ guest_endonyms[code] }}</button>
        {% else %}
        <a href="{{ url }}" class="{{ 'on' if lang == code }}"{% if lang == code %} aria-current="true"{% endif %} hreflang="{{ code }}" lang="{{ code }}">{{ guest_endonyms[code] }}</a>
        {% endif %}
        {% endfor %}
```
Cache keys: in `guest/base.html` and `_signature_script.html` change `guest.css?v=20261104-0910b` to `guest.css?v=20261105-0959` and both `signature.js?v=20261021-0196` to `signature.js?v=20261105-0959`. Do not touch `guest/archive/`.

2b. `guest/form.html`: replace the first two lines of the `<form` tag (`<form method="post" ...save?lang={{ lang }}"` and `      enctype="multipart/form-data" data-guest-wizard`) with:
```
<form id="guest-form" method="post" action="/l/{{ token }}/{{ reservation.id }}/save?lang={{ lang }}"
      enctype="multipart/form-data" data-guest-wizard
      data-start-step="{{ start_step | default(0) }}"
      data-lang-warning="{{ t('lang_draft_warning') }}"
```
and replace `  <input type="hidden" name="_csrf" value="{{ csrf_token }}">` (first occurrence, line 56 only, inside this form) with:
```
  <input type="hidden" name="_csrf" value="{{ csrf_token }}">
  <input type="hidden" id="form-step" name="_step" value="">
```
Check: `grep -c 'name="_step"' app/templates/guest/form.html` prints 1.

### Step 3: CSS (`app/static/guest.css`)

Replace the 14 lines quoted in section 2 (from `.g-lang-list a {` to the `.g-lang-list a.on` line) with:
```
.g-lang-list a,
.g-lang-list button {
  display: flex;
  align-items: center;
  width: 100%;
  min-height: 44px;
  padding: 0 12px;
  border: 0;
  border-radius: 10px;
  background: transparent;
  color: var(--g-ink);
  font: inherit;
  font-size: 15px;
  font-weight: 600;
  text-align: left;
  text-decoration: none;
  cursor: pointer;
  transition: background 0.16s var(--g-ease), color 0.16s var(--g-ease);
}
.g-lang-list a:hover,
.g-lang-list button:hover { background: var(--g-bg); }
.g-lang-list a.on,
.g-lang-list button.on { background: var(--g-ink); color: var(--g-bg); font-weight: 700; }
```

### Step 4: JS (`app/static/signature.js`)

4a. Replace the `var active = Math.max(0, steps.findIndex(...));` line with:
```
    var errorAt = steps.findIndex(function (step) { return step.querySelector(".bad, .err:not(:empty)"); });
    // 0959: after a language change the server hands back the step the guest
    // was on; a step with an error still wins, so nothing invalid is hidden.
    var startAt = parseInt(form.getAttribute("data-start-step") || "0", 10);
    var active = errorAt >= 0 ? errorAt : Math.max(0, Math.min(isNaN(startAt) ? 0 : startAt, steps.length - 1));
```
4b. Replace `      active = Math.max(0, Math.min(index, steps.length - 1));` with the same line followed by:
```
      form.setAttribute("data-active-step", String(active));
```
4c. Insert this function immediately before `  function initCheckinRail() {` (find the line with `grep -nF "function initCheckinRail"`; if a comment block `/* The wide check-in layout ...` sits directly above it, insert above that comment instead):
```
  /* 0959: the language menu on the form posts the open form back (see
     guest_form_relang). A drawn signature, the acknowledgement tick and a
     chosen photo are not carried over, so ask first; Cancel leaves the page
     and every answer exactly as it is. Nothing is stored anywhere. */
  function initLanguageDraft() {
    var form = document.getElementById("guest-form");
    if (!form) return;
    var buttons = document.querySelectorAll("[data-lang-draft]");
    Array.prototype.forEach.call(buttons, function (button) {
      button.addEventListener("click", function (event) {
        var signature = document.getElementById("signature");
        var ack = document.getElementById("legal_ack");
        var photo = document.getElementById("passport_photo");
        var drawn = !!(signature && signature.value && signature.value !== signature.defaultValue);
        var ticked = !!(ack && ack.checked);
        var picked = !!(photo && photo.files && photo.files.length);
        if ((drawn || ticked || picked) && !window.confirm(form.getAttribute("data-lang-warning") || "")) {
          event.preventDefault();
          return;
        }
        // What is dropped need not travel.
        if (drawn) signature.value = "";
        if (picked) photo.value = "";
        var step = document.getElementById("form-step");
        if (step) step.value = form.getAttribute("data-active-step") || "0";
      });
    });
  }

```
4d. In the `DOMContentLoaded` list replace `    initGuestWizard();` with `    initGuestWizard();\n    initLanguageDraft();`.
Run: `node --check app/static/signature.js 2>&1 | tail -30` (skip if node is missing).

### Step 5: strings

Insert one new line directly after each `"signature_kept"` line (same indentation as that line: 8 spaces in `i18n.py`, 4 in `guest_uk_i18n.py`; find each with `grep -n '"signature_kept"'`; there are 5 in i18n.py in the order en, cs, de, es, fr, and 1 in guest_uk_i18n.py):

- en: `"lang_draft_warning": "Your answers stay. The signature, the acknowledgement tick and any passport photo do not carry over, so you will add them again. Change the language?",`
- cs: `"lang_draft_warning": "Vaše odpovědi zůstanou. Podpis, zaškrtnutí potvrzení a fotka pasu se nepřenesou, budete je zadávat znovu. Změnit jazyk?",`
- de: `"lang_draft_warning": "Ihre Angaben bleiben erhalten. Unterschrift, Bestätigungshaken und Passfoto werden nicht übernommen und müssen erneut hinzugefügt werden. Sprache ändern?",`
- es: `"lang_draft_warning": "Sus respuestas se conservan. La firma, la casilla de confirmación y la foto del pasaporte no se conservan; deberá añadirlas de nuevo. ¿Cambiar el idioma?",`
- fr: `"lang_draft_warning": "Vos réponses sont conservées. La signature, la case de confirmation et la photo du passeport ne le sont pas : vous les ajouterez à nouveau. Changer de langue ?",`
- uk: `"lang_draft_warning": "Ваші відповіді збережуться. Підпис, позначка підтвердження та фото паспорта не переносяться, їх потрібно буде додати знову. Змінити мову?",`

Check: `grep -c '"lang_draft_warning"' app/i18n.py` prints 5; same grep on `app/guest_uk_i18n.py` prints 1.

### Step 6: regression test (append to the end of `tests/test_guest_browser_e2e.py`)

```
def test_0959_changing_language_keeps_the_draft_the_step_and_leaves_no_trace(
    live_server, browser, monkeypatch
):
    """G01: EN -> CS -> EN keeps what was typed and the step; a drawn signature
    asks first and Cancel keeps the draft; no answer reaches a URL or storage."""
    from app import config

    monkeypatch.setattr(config, "GUEST_PIN_REQUIRED", False)
    monkeypatch.setattr(mail, "mail_enabled", lambda: False)
    token = "browser-0959-lang"
    stay = _fee_seed(token, signed=False)
    page = browser.new_page(viewport={"width": 390, "height": 812})
    urls = []
    page.on("request", lambda request: urls.append(request.url))
    secrets = ["Synthetica", "Testovic", "SYN0959X", "Examplova 5", "Testov"]
    guest = Guest(page, 390)

    def progress():
        return [int(n) for n in re.findall(r"\d+", page.inner_text("[data-wizard-label]"))[:2]]

    def pick(lang):
        page.locator("[data-lang-menu] summary").click()
        page.locator(f'[data-lang-draft][lang="{lang}"]').click()

    try:
        page.goto(f"{live_server}/l/{token}/{stay}/new?lang=en")
        page.fill("#first_name", secrets[0])
        page.fill("#surname", secrets[1])
        page.click("#birth_date")
        page.keyboard.type("01011980")
        guest.pick_country("nationality", "CZE")
        page.fill("#doc_number", secrets[2])
        guest.next()
        page.fill("#res_street", secrets[3])
        page.fill("#res_city", secrets[4])
        page.evaluate("() => { document.querySelector('#res_country').value = 'CZE'; }")
        guest.next()
        before = progress()
        assert before[0] == before[1], before  # on the last step; Czech has no photo step
        guest.sign()
        page.check("#legal_ack")

        # Cancel: the warning appears, nothing is lost, no navigation happens.
        messages = []
        page.once("dialog", lambda dialog: (messages.append(dialog.message), dialog.dismiss()))
        pick("cs")
        page.wait_for_timeout(300)
        assert messages == [i18n.translator("en")("lang_draft_warning")], messages
        assert page.get_attribute("html", "lang") == "en"
        assert page.input_value("#first_name") == secrets[0]
        assert page.eval_on_selector("#signature", "e => e.value").startswith("data:image/png")
        assert page.is_checked("#legal_ack")

        # Accept: Czech page, same answers, same step, signature and tick asked again.
        page.once("dialog", lambda dialog: dialog.accept())
        with page.expect_navigation():
            page.locator(f'[data-lang-draft][lang="cs"]').click()
        assert page.get_attribute("html", "lang") == "cs"
        assert progress() == before, (progress(), before)
        assert page.input_value("#first_name") == secrets[0]
        assert page.input_value("#surname") == secrets[1]
        assert page.input_value("#birth_date") == "01.01.1980"
        assert page.input_value("#nationality") == "CZE"
        assert page.input_value("#doc_number") == secrets[2]
        assert page.input_value("#res_street") == secrets[3]
        assert page.input_value("#res_city") == secrets[4]
        assert page.eval_on_selector("#signature", "e => e.value") == ""
        assert not page.is_checked("#legal_ack")

        # Back to English with nothing to lose: no warning, still the same.
        shots = os.environ.get("UBYHOST_SHOTS_DIR")
        if shots:
            Path(shots).mkdir(parents=True, exist_ok=True)
            for width in (390, 768, 1280):
                page.set_viewport_size({"width": width, "height": 900})
                page.screenshot(path=str(Path(shots) / f"0959-review-cs-{width}.png"), full_page=True)
            page.set_viewport_size({"width": 390, "height": 812})
        page.once("dialog", lambda dialog: pytest.fail("no warning expected"))
        with page.expect_navigation():
            pick("en")
        assert page.get_attribute("html", "lang") == "en"
        assert progress() == before
        assert page.input_value("#surname") == secrets[1]
        assert page.input_value("#nationality") == "CZE"

        # Step 1 of a foreign nationality keeps its longer step count.
        page.locator("[data-guest-step]:not([hidden]) .g-wizard-nav button.secondary").first.click()
        page.locator("[data-guest-step]:not([hidden]) .g-wizard-nav button.secondary").first.click()
        guest.pick_country("nationality", "DEU")
        page.fill("#first_name", secrets[0])
        pick("cs")
        page.wait_for_load_state()
        assert page.input_value("#nationality") == "DEU"
        assert page.input_value("#first_name") == secrets[0]

        assert not [u for u in urls if any(s.lower() in u.lower() for s in secrets)], urls
        assert "01.01.1980" not in " ".join(urls) and "01011980" not in " ".join(urls)
        assert page.evaluate("() => [localStorage.length, sessionStorage.length]") == [0, 0]
        assert not any(
            any(s in cookie["value"] for s in secrets) for cookie in page.context.cookies()
        )
    finally:
        page.close()
```
If a locator in this test is wrong against the real DOM (for example `.g-wizard-nav button.secondary` or the `res_country` select), fix the locator once only; a second failure = STOP.

### Step 7: cache keys and manifest

From `App/`: `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -30` then `.venv/bin/python tests/test_static_versions.py 2>&1 | tail -30`.

## 5. Do not touch

`guest/archive/`, host templates, `reporting`, `validation`, `db`, migrations, `retention.py`, requirements, `.env`, any other batch or 0958 file. No localStorage, sessionStorage or cookie for draft content. No SQL. Never push or merge.

## 6. Commands

Setup if `App/.venv` is missing: `ln -s /tmp/ubyhost-0958-worktree/App/.venv /tmp/ubyhost-b01-worktree/App/.venv`. Work in `/tmp/ubyhost-b01-worktree`, branch `codex/0959-guest-draft-language` (verify with `git branch --show-current`). Then from `App/`:
```
export UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-b01
.venv/bin/python -m pytest tests/test_guest_browser_e2e.py -k 0959 -q --tb=short -x -rs 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_guest_*.py tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py tests/test_privacy_first.py tests/test_cookie_inventory.py -q --tb=short -x -rs 2>&1 | tail -30
```
From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30` and `git diff --check 2>&1 | tail -30`.
Expected: all pass, `0 skipped`; lint and diff-check print nothing alarming.
Commit 1 (after these pass), from the repo root:
`git add App/app App/tests && git commit -m "0959 step 1" -m "Keep the guest draft when the language changes." -m "Co-authored-by: Codex <noreply@openai.com>"`

## 7. Acceptance

- [ ] The new test passes: EN to CS to EN keeps values and step; Cancel keeps the draft; no entered value in any URL, cookie or storage.
- [ ] Czech nationality gives 3 steps before and after; German keeps its longer list (test and `progress()`).
- [ ] Guest rows of the test-map pass, 0 skipped; static version and cache heartbeat tests pass.
- [ ] Screenshots exist in `/tmp/ubyhost-b01`: `0959-review-cs-390.png`, `-768`, `-1280` (opened and looked at once: the language menu rows, the review list, no overflow). Also take, with a small throwaway script outside the repo or by opening the menu in the test, one 390 px shot of the open language menu on the form step and look at it once. Nothing is saved in the repo.
- [ ] `git diff --stat` shows only section 3 files.

## 8. Stop and ask

Stop and write the report as `blocked` if: an anchor is not found verbatim; a command fails twice; a file outside section 3 needs a change; any entered value shows up in a URL, cookie or storage; the `/relang` POST is rejected by CSRF or middleware in a way a one-line fix does not clear; a schema, dependency or stored draft seems needed; 25 tool calls or about 50k tokens reached.

## 9. Report

Write `docs/tasks/0959-report.md` (600 tokens at most): files changed (`git diff --stat`), each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps (none expected; the owner merges and deploys). Describe, never print, guest data. Set `Status: review`. Commit: `git add docs/tasks/0959-report.md && git commit -m "0959 step 2" -m "Report." -m "Co-authored-by: Codex <noreply@openai.com>"`. No push, no PR (the orchestrator does that).

## Risk list (for the reviewer)

`App/app/routes/guest.py` (new route: guards copied from save, throttle scope `guest_relang`), `App/app/static/signature.js` (start step, confirm guard), `App/app/templates/guest/base.html` (buttons in the language menu). Known limits: validation errors are not carried across a language switch; the URL after a switch is the POST-only `/relang?lang=..` (reload asks to resubmit); the host-side guest language list is unchanged.

## Owner steps

None for this brief.
