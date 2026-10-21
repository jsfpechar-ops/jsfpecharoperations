# 0203: Onboarding flow fixes from the first user test

Status: done (test follow-up in 0204 step 0)
Depends on: none | Base commit: 2f043c8 | Branch: claude/project-thread-cf47ju
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

The first user test (2026-10-21) found two places where onboarding drops the host: adding a passkey from the one-time pop-up ends on Settings, and connecting TTLock from the setup wizard ends in property settings, never back in the wizard. Fix both, make the demo step say "Continue" once the demo is done, and end the wizard on the dashboard with a short celebration.

## 2. Context

- Owner decision (Josef, 2026-10-21): "build all as proposed". Plan: claude.ai doc "Onboarding test fixes", rows 1, 2 and 9.
- AGENTS hard rules 6, 7, 9 apply. Changed CSS/JS gets a new `?v=` key and `tests/static_versions.json` is rewritten with `--write`.
- Copy: no em dashes. Every new key exists in `en`, `cs` and `vi`.
- `security.safe_local_path(value, default)` returns `default` for anything that is not a same-site path.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/routes/passkeys.py | edit | redirect to the posted `return_to` |
| App/app/templates/base.html | edit | pop-up button carries the page path; new `passkeys.js` and `host2.css` and `host.js` keys |
| App/app/templates/login.html | edit | new `passkeys.js` key |
| App/app/static/passkeys.js | edit | post `return_to` |
| App/app/routes/admin.py | edit | lock answers return to the wizard lock step |
| App/app/routes/onboarding_wizard.py | edit | lock panel context on the lock step |
| App/app/templates/setup_wizard/door_lock.html | edit | lock panel inside the wizard |
| App/app/templates/setup_wizard/done.html | edit | celebration, button to the dashboard |
| App/app/templates/setup_wizard/try_it.html | edit | waiting marker |
| App/app/static/host.js | edit | reload the demo step when the host comes back |
| App/app/static/host2.css | edit | celebration styles |
| App/app/host_i18n.py | edit | one new strings block |
| App/app/host_vi_i18n.py | edit | the same keys in Vietnamese |
| App/tests/test_passkeys.py | edit | one new test |
| App/tests/test_smart_locks_page.py | edit | one new test |
| App/tests/static_versions.json | regenerate | `--write` |

No other file may change.

## 4. Steps

### Step 1. `App/app/routes/passkeys.py`

Anchor: `    target = _back(_SECURITY, msg=_flash(request, "flash.passkeys.added"))`

Replace that one line with:

```python
    # 0203: a passkey added from the one-time pop-up returns the host to the
    # page they were on (onboarding, the setup wizard), not to Settings.
    return_to = security.safe_local_path(str(data.get("return_to") or ""), _SECURITY)
    target = _back(return_to, msg=_flash(request, "flash.passkeys.added"))
```

### Step 2. `App/app/templates/base.html`

a) Anchor: `<button class="btn primary" type="button" data-passkey-add>{{ t('security_prompt.passkey') }}</button>`
Replace with:
`<button class="btn primary" type="button" data-passkey-add data-passkey-return="{{ request.url.path }}">{{ t('security_prompt.passkey') }}</button>`

b) Anchor: `/static/passkeys.js?v=20261006a` → replace with `/static/passkeys.js?v=20261021-0203`
c) Anchor: `/static/host2.css?v=20261021-0201d` → replace with `/static/host2.css?v=20261021-0203`
d) Anchor: `/static/host.js?v=20261014-0102d` → replace with `/static/host.js?v=20261021-0203`

### Step 3. `App/app/templates/login.html`

Anchor: `/static/passkeys.js?v=20261007a` → replace with `/static/passkeys.js?v=20261021-0203`

### Step 4. `App/app/static/passkeys.js`

Anchor: `        return post("/account/passkeys", { credential: serialise(credential) });`
Replace with:

```js
        return post("/account/passkeys", {
          credential: serialise(credential),
          return_to: button.getAttribute("data-passkey-return") || ""
        });
```

### Step 5. `App/app/routes/admin.py` (`_lock_property_return`)

Anchor (exact, 7 lines):

```python
    match = re.fullmatch(r"/apartments/(\d+)", return_to.split("?", 1)[0])
    if not match:
        return None
    apartment_id = int(match.group(1))
    if not access.apartment(request, apartment_id):
        return None
    return f"/apartments/{apartment_id}?view=settings&section=lock#door-code"
```

Replace with:

```python
    path = return_to.split("#", 1)[0].split("?", 1)[0]
    match = re.fullmatch(r"/apartments/(\d+)(/setup/door_lock)?", path)
    if not match:
        return None
    apartment_id = int(match.group(1))
    if not access.apartment(request, apartment_id):
        return None
    if match.group(2):
        # 0203: the setup wizard's lock step; every lock answer returns to it.
        return f"/apartments/{apartment_id}/setup/door_lock"
    return f"/apartments/{apartment_id}?view=settings&section=lock#door-code"
```

### Step 6. `App/app/routes/onboarding_wizard.py` (`_wizard_context`)

Anchor: `        "lock_available": lock_available,`
Replace with:

```python
        "lock_available": lock_available,
        # 0203: the lock step shows the lock panel itself, so connecting a lock
        # never leaves the wizard.
        "lock_panel": (
            {
                **admin_routes._smart_lock_panel_context(request),
                "return_to": f"/apartments/{apartment_id}/setup/door_lock",
            }
            if step == "door_lock" else None
        ),
```

If the anchor occurs more than once, STOP.

### Step 7. `App/app/templates/setup_wizard/door_lock.html`

a) Anchor (exact, 6 lines):

```
  {% if not door_code.account %}
  <a class="ui-btn ui-btn-secondary" href="/smart-locks?return_to=/apartments/{{ apartment.id }}/setup/door_lock#smart-locks-how">{{ t('apartment.form.door_code.setup') }}</a>
  {% elif not door_code.locks %}
  <p class="setup-wizard-instruction">{{ t('apartment.form.door_code.no_locks') }}</p>
  <a class="ui-btn ui-btn-secondary" href="/smart-locks?return_to=/apartments/{{ apartment.id }}/setup/door_lock#smart-locks-share">{{ t('smart_locks.title') }}</a>
  {% else %}
```

Replace with:

```
  {% if not (door_code.account and door_code.locks) %}
  {#- 0203: no lock yet; the lock panel under this form connects one. -#}
  {% else %}
```

b) Anchor (exact, 3 lines):

```
</form>
{% else %}
<p class="setup-wizard-instruction">{{ t('wizard.door_lock.unavailable') }}</p>
```

Replace with:

```
</form>
{% if not (door_code.account and door_code.locks) and lock_panel and lock_panel.smart_locks_enabled %}
<section class="setup-wizard-lock-panel" id="door-code">
  {% with account=lock_panel.account, receiver=lock_panel.receiver, locks=lock_panel.locks, fetched_at=lock_panel.fetched_at, reauth=lock_panel.reauth, return_to=lock_panel.return_to, properties_using=lock_panel.properties_using %}
  {% include "_smart_locks_panel.html" %}
  {% endwith %}
</section>
{% endif %}
{% else %}
<p class="setup-wizard-instruction">{{ t('wizard.door_lock.unavailable') }}</p>
```

### Step 8. `App/app/templates/setup_wizard/done.html`

a) Anchor: `<h2 class="setup-wizard-section-title">{{ t('wizard.done.title') }}</h2>`
Replace with:

```
<div class="ui-banner setup-wizard-celebrate" role="status">
  <span class="setup-wizard-confetti" aria-hidden="true">{% for n in range(12) %}<i></i>{% endfor %}</span>
  <div class="grow"><strong>{{ t('wizard.done.celebrate') }}</strong></div>
</div>
<h2 class="setup-wizard-section-title">{{ t('wizard.done.title') }}</h2>
```

b) Anchor: `<a class="ui-btn ui-btn-primary" href="/apartments/{{ apartment.id }}?view=overview">{{ t('wizard.done.go') }}</a>`
Replace with: `<a class="ui-btn ui-btn-primary" href="/">{{ t('wizard.done.go') }}</a>`

### Step 9. `App/app/templates/setup_wizard/try_it.html`

Anchor: `<p class="setup-wizard-instruction">{{ t('wizard.try_it.waiting') }}</p>`
Replace with: `<p class="setup-wizard-instruction" data-wizard-demo-wait>{{ t('wizard.try_it.waiting') }}</p>`

### Step 10. `App/app/static/host.js`

Anchor: `  document.querySelectorAll('[data-phone-country-code]').forEach(function (input) {`
Insert these lines immediately BEFORE the anchor (keep the anchor line):

```js
  // 0203: while the demo stay waits for its registration, coming back to this
  // tab reloads the step, so a finished demo shows "Continue" at once.
  // Only on a tab switch: a reload on load or focus could loop.
  if (document.querySelector('[data-wizard-demo-wait]')) {
    document.addEventListener('visibilitychange', function () {
      if (document.visibilityState === 'visible') window.location.reload();
    });
  }

```

### Step 11. `App/app/static/host2.css`

Append at the very end of the file:

```css

/* 0203: the setup wizard's finish screen. A short one-time burst; none for reduced motion. */
.host-workspace .setup-wizard-celebrate { position: relative; overflow: hidden; background: var(--green-bg); border: 1px solid var(--green-300); }
.host-workspace .setup-wizard-confetti { position: absolute; inset: 0; pointer-events: none; }
.host-workspace .setup-wizard-confetti i { position: absolute; top: -12px; width: 8px; height: 12px; border-radius: 2px; background: var(--brand); opacity: 0; animation: setup-wizard-confetti 1.8s ease-out 1 forwards; }
.host-workspace .setup-wizard-confetti i:nth-child(3n) { background: var(--green); }
.host-workspace .setup-wizard-confetti i:nth-child(3n+1) { background: var(--amber); }
.host-workspace .setup-wizard-confetti i:nth-child(1) { left: 4%; }
.host-workspace .setup-wizard-confetti i:nth-child(2) { left: 12%; animation-delay: .15s; }
.host-workspace .setup-wizard-confetti i:nth-child(3) { left: 20%; animation-delay: .3s; }
.host-workspace .setup-wizard-confetti i:nth-child(4) { left: 28%; animation-delay: .05s; }
.host-workspace .setup-wizard-confetti i:nth-child(5) { left: 36%; animation-delay: .25s; }
.host-workspace .setup-wizard-confetti i:nth-child(6) { left: 44%; animation-delay: .1s; }
.host-workspace .setup-wizard-confetti i:nth-child(7) { left: 52%; animation-delay: .35s; }
.host-workspace .setup-wizard-confetti i:nth-child(8) { left: 60%; animation-delay: .2s; }
.host-workspace .setup-wizard-confetti i:nth-child(9) { left: 68%; animation-delay: .05s; }
.host-workspace .setup-wizard-confetti i:nth-child(10) { left: 76%; animation-delay: .3s; }
.host-workspace .setup-wizard-confetti i:nth-child(11) { left: 84%; animation-delay: .15s; }
.host-workspace .setup-wizard-confetti i:nth-child(12) { left: 92%; animation-delay: .25s; }
@keyframes setup-wizard-confetti { 0% { opacity: 1; transform: translateY(0) rotate(0deg); } 100% { opacity: 0; transform: translateY(72px) rotate(300deg); } }
@media (prefers-reduced-motion: reduce) { .host-workspace .setup-wizard-confetti { display: none; } }
.host-workspace .setup-wizard-lock-panel { margin-top: var(--space-6); }
```

### Step 12. `App/app/host_i18n.py`

Anchor: `STRINGS["vi"] = dict(_VI_STRINGS)`
Insert immediately BEFORE the anchor:

```python
# 0203: onboarding user test (2026-10-21): the demo step says "Continue" once
# done, and the wizard ends on the dashboard.
_ONBOARDING_TEST_0203_STRINGS = {
    "en": {
        "wizard.try_it.skip": "Continue without the demo",
        "wizard.try_it.keep": "Continue",
        "wizard.done.go": "Go to the overview",
        "wizard.done.celebrate": "All set. Your property is ready for guests.",
    },
    "cs": {
        "wizard.try_it.skip": "Pokračovat bez ukázky",
        "wizard.try_it.keep": "Pokračovat",
        "wizard.done.go": "Přejít na přehled",
        "wizard.done.celebrate": "Hotovo. Vaše ubytování je připravené na hosty.",
    },
}
for _lang, _strings in _ONBOARDING_TEST_0203_STRINGS.items():
    STRINGS[_lang].update(_strings)

```

### Step 13. `App/app/host_vi_i18n.py`

Append at the very end of the file:

```python

# 0203: onboarding user test (2026-10-21).
STRINGS.update({
    "wizard.try_it.skip": "Tiếp tục mà không dùng bản mẫu",
    "wizard.try_it.keep": "Tiếp tục",
    "wizard.done.go": "Đến trang tổng quan",
    "wizard.done.celebrate": "Xong. Chỗ ở của bạn đã sẵn sàng đón khách.",
})
```

Command: `cd App && .venv/bin/python -c "from app import host_i18n as h; print(h.translate('vi','wizard.done.celebrate'), h.translate('cs','wizard.try_it.keep'))" 2>&1 | tail -3`
Expected: the Vietnamese sentence and `Pokračovat`.

### Step 14. `App/tests/test_passkeys.py`

Append at the end of the file:

```python


def test_a_passkey_added_from_the_prompt_returns_to_the_page_it_was_on():
    """0203: the one-time pop-up sends the host back to onboarding, not Settings."""
    account = _account()
    client = _signed_in(account)
    authenticator = SoftAuthenticator(origin=ORIGIN, rp_id=RP_ID)
    options = _post(client, "/account/passkeys/options")
    answer = authenticator.create(options.json())
    response = _post(client, "/account/passkeys", {"credential": answer, "return_to": "/onboarding"})
    assert response.status_code == 200, response.text
    assert response.json()["redirect"].startswith("/onboarding?msg=")


def test_a_foreign_passkey_return_falls_back_to_settings():
    account = _account()
    client = _signed_in(account)
    authenticator = SoftAuthenticator(origin=ORIGIN, rp_id=RP_ID)
    options = _post(client, "/account/passkeys/options")
    answer = authenticator.create(options.json())
    response = _post(client, "/account/passkeys", {"credential": answer, "return_to": "https://evil.example/x"})
    assert response.json()["redirect"].startswith("/settings?msg=")
```

### Step 15. `App/tests/test_smart_locks_page.py`

Append at the end of the file:

```python


def test_the_setup_wizard_lock_step_gets_every_lock_answer_back(hosts, flats, monkeypatch):
    """0203: a lock connected from the setup wizard returns to the wizard, not to Settings."""
    _connect(hosts[0], "hjhfa_uhaaaa")
    wizard = f"/apartments/{flats[0]}/setup/door_lock"
    client = _client(USERS[0])
    monkeypatch.setattr(ttlock, "check_locks", lambda _id: ([], []))
    response = _post(client, "/smart-locks/refresh", return_to=wizard, section="share")
    location = response.headers["location"]
    assert location.startswith(wizard) and location.endswith("#smart-locks-share"), location
    found = [{"lock_id": "1", "alias": "Door A", "battery": 90, "tz_offset_ms": 3600000}]
    monkeypatch.setattr(ttlock, "check_locks", lambda _id: (found, []))
    response = _post(client, "/smart-locks/refresh", return_to=wizard, section="share")
    assert response.headers["location"].startswith(wizard), response.headers["location"]
    foreign = f"/apartments/{flats[1]}/setup/door_lock"
    response = _post(client, "/smart-locks/refresh", return_to=foreign, section="share")
    assert f"/apartments/{flats[1]}" not in response.headers["location"]
```

### Step 16. Cache keys

Command: `cd App && .venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5`

## 5. Do not touch

Guest templates and `guest.css`. `_smart_locks_panel.html` (only included). Filing code. AGENTS hard rules 1, 3, 5, 8.

## 6. Commands

From `App/`, each ending `-q --tb=short -x 2>&1 | tail -30`:

1. `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_passkeys.py tests/test_smart_locks_page.py tests/test_door_codes_view.py tests/test_onboarding.py tests/test_onboarding_wizard_survival.py tests/test_static_versions.py -rs`
2. `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_onboarding_wizard_browser.py tests/test_design_setup_wizard_browser.py tests/test_design_guardrails_browser.py -rs` (0 skipped)
3. `.venv/bin/python -m pytest tests/test_host_i18n.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py`

A file in the list that does not exist: drop it and say so in the report.

## 7. Acceptance

- [ ] Both new tests pass; every command in §6 passes with 0 skipped.
- [ ] `grep -n "smart-locks?return_to" App/app/templates/setup_wizard/door_lock.html` prints nothing.
- [ ] `git diff --stat` lists only §3 files.

## 8. Stop and ask

As in TEMPLATE.md §8.

## 9. Report

`docs/tasks/0203-report.md`, as in TEMPLATE.md §9.

## Risk list (for the reviewer)

`routes/admin.py` `_lock_property_return`, `routes/passkeys.py`, `door_lock.html`.

## Owner steps

1. After merge, deploy as usual. New cache keys ship with it.
