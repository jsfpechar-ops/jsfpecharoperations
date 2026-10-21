# 0206: Urgent alerts switch in Settings (markup, pwa.js, logout, browser test)

Status: review
Depends on: 0205 | Branch: claude/project-thread-w35ftw
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Settings > Phone app gets the "Urgent alerts on this device" row: Turn on (asks the browser's permission, subscribes, sends one test), On badge, Send a test, Turn off, the list of devices with Remove, and clear text for iPhone-not-installed, unsupported and blocked. Logging out turns alerts off on that device.

## 2. Context

- Endpoints from 0205: `POST /account/push/subscribe {subscription, lang}`, `/refresh {endpoint, lang}` → `{known}`, `/unsubscribe {endpoint}`, `/test {endpoint}` → `{ok, message}` or `{error}`, form `POST /account/push/devices/{id}/delete`. JSON posts need header `X-CSRF-Token` from `<meta name="csrf-token">`.
- Settings context from 0205: `push_available` (False while an admin previews), `push_key` (base64url VAPID public key), `push_devices` (rows: `id`, `device`, `created_at`).
- iPhone: push works only in the app opened from the Home Screen (iOS 16.4+), and `Notification.requestPermission()` must run directly inside the click. `pwa.js` already has `ios`, `standalone`, `show()` and `workerReady`.
- Without JavaScript only the help text, the "unsupported" line and the device list with Remove are visible.
- Design lint on `settings.html`: no `style=`, catalog classes only, every new button `ui-btn-secondary` (one primary per template already used). `test_destructive_confirm.py`: a form whose action contains "delete" needs `data-confirm` and `data-confirm-message`.
- Cache rule: `pwa.js` changes, so its `?v=` key changes in `base.html` and `auth_base.html`, and `tests/static_versions.json` is regenerated.
- Screenshots go to `/mnt/project-files/pwa/0206/` (network mount: trailing slash, never search it).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/settings.html` | edit | alerts row and device list |
| `App/app/static/pwa.js` | edit | push block and logout hook |
| `App/app/templates/base.html` | edit | `pwa.js` key |
| `App/app/templates/auth_base.html` | edit | `pwa.js` key |
| `App/app/host_i18n.py` | edit | remove-confirm copy EN, CS |
| `App/app/host_vi_i18n.py` | edit | remove-confirm copy VI |
| `App/tests/test_push_settings_browser.py` | new | browser test and screenshots |
| `App/tests/static_versions.json` | regenerated | |

No other file may change.

## 4. Steps

**Step 1.** `App/app/templates/settings.html`. Anchor (from 0203):

```html
        <p class="ui-sub" data-pwa-other>{{ t('pwa.install.other') }}</p>
      </div>
```

Insert directly after those two lines:

```html
      {% if push_available %}
      <div class="settings-action-list" id="settings-alerts" data-push-row data-push-key="{{ push_key }}">
        <div class="settings-action-row">
          <div>
            <strong>{{ t('push.title') }}</strong>
            <small>{{ t('push.help') }}</small>
          </div>
          <button class="ui-btn ui-btn-secondary ui-btn-compact" type="button" data-push-on hidden>{{ t('push.on') }}</button>
          <span class="ui-badge ui-badge-done" data-tone="green" data-push-state-on hidden>{{ t('push.state_on') }}</span>
        </div>
        <div class="ui-form-actions" data-push-controls hidden>
          <button class="ui-btn ui-btn-secondary ui-btn-compact" type="button" data-push-test>{{ t('push.test') }}</button>
          <button class="ui-btn ui-btn-secondary ui-btn-compact" type="button" data-push-off>{{ t('push.off') }}</button>
        </div>
        <p class="ui-sub" data-push-unsupported>{{ t('push.unsupported') }}</p>
        <p class="ui-sub" data-push-ios-first hidden>{{ t('push.ios_first') }}</p>
        <p class="ui-sub" data-push-denied hidden>{{ t('push.denied') }}</p>
        <p class="ui-sub" data-push-status role="status" hidden></p>
        <p class="ui-sub err-text" data-push-error data-generic="{{ t('push.error.failed') }}" role="alert" hidden></p>
        {% if push_devices %}
          <p class="ui-sub"><strong>{{ t('push.devices') }}</strong></p>
          {% for device in push_devices %}
            <div class="settings-action-row">
              <div>
                <strong>{{ device.device or t('push.device_unknown') }}</strong>
                <small>{{ t('push.device_added', date=device.created_at | datetime_local) }}</small>
              </div>
              <form method="post" action="/account/push/devices/{{ device.id }}/delete"
                    data-confirm data-confirm-message="{{ t('push.device_remove_confirm', name=device.device or t('push.device_unknown')) }}">
                <button class="ui-btn ui-btn-secondary ui-btn-compact" type="submit">{{ t('push.device_remove') }}</button>
              </form>
            </div>
          {% endfor %}
        {% endif %}
      </div>
      {% endif %}
```

Run: `python3 scripts/design_lint.py 2>&1 | tail -5` (repo root). Expected: `OK`.

**Step 2.** `App/app/host_i18n.py`. Anchor (from 0205):

```python
for _lang, _strings in _PUSH_SETTINGS_STRINGS.items():
    STRINGS[_lang].update(_strings)
```

Insert after it:

```python
STRINGS["en"]["push.device_remove_confirm"] = "Stop alerts on %(name)s?"
STRINGS["cs"]["push.device_remove_confirm"] = "Zastavit upozornění na zařízení %(name)s?"
```

**Step 3.** `App/app/host_vi_i18n.py`. Anchor (from 0205): `    "flash.push.signed_out": "Hãy đăng nhập lại rồi thử lần nữa.",`. Insert after it:

```python
    "push.device_remove_confirm": "Dừng cảnh báo trên %(name)s?",
```

**Step 4.** `App/app/static/pwa.js`. Anchor: the last two lines of the file:

```js
  paintInstall();
})();
```

Replace them with:

```js
  paintInstall();

  // --- Settings > urgent alerts (brief 0206) --------------------------------

  var pushRow = document.querySelector("[data-push-row]");
  var pushSupported = "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
  var csrfMeta = document.querySelector('meta[name="csrf-token"]');
  var pageLang = document.documentElement.lang || "en";

  function post(url, body) {
    return fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-CSRF-Token": csrfMeta ? csrfMeta.getAttribute("content") : ""
      },
      body: JSON.stringify(body || {})
    }).then(function (response) {
      return response.json().catch(function () { return {}; }).then(function (data) {
        if (!response.ok) throw new Error(data.error || "");
        return data;
      });
    });
  }

  function keyBytes(value) {
    var b64 = String(value || "").replace(/-/g, "+").replace(/_/g, "/");
    while (b64.length % 4) b64 += "=";
    var raw = atob(b64);
    var bytes = new Uint8Array(raw.length);
    for (var i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
    return bytes;
  }

  // A subscription made for an older server key cannot receive alerts any more.
  function sameKey(subscription, key) {
    var have = subscription.options && subscription.options.applicationServerKey;
    if (!have) return true;
    var a = new Uint8Array(have);
    var b = keyBytes(key);
    if (a.length !== b.length) return false;
    for (var i = 0; i < a.length; i++) {
      if (a[i] !== b[i]) return false;
    }
    return true;
  }

  function currentSubscription() {
    return workerReady.then(function (registration) {
      return registration.pushManager.getSubscription();
    });
  }

  function paintPush(state) {
    show("[data-push-on]", state === "off");
    show("[data-push-state-on]", state === "on");
    show("[data-push-controls]", state === "on");
    show("[data-push-ios-first]", state === "ios");
    show("[data-push-unsupported]", state === "unsupported");
    show("[data-push-denied]", state === "denied");
  }

  function pushMessage(selector, text) {
    show("[data-push-status]", false);
    show("[data-push-error]", false);
    var el = document.querySelector(selector);
    if (!el) return;
    el.textContent = text || el.getAttribute("data-generic") || "";
    el.hidden = false;
  }

  function initPush() {
    if (!pushRow) return;
    if (ios && !standalone) return paintPush("ios");
    if (!pushSupported) return paintPush("unsupported");
    if (Notification.permission === "denied") return paintPush("denied");
    paintPush("off");
    currentSubscription().then(function (subscription) {
      if (!subscription) return null;
      if (!sameKey(subscription, pushRow.getAttribute("data-push-key"))) {
        return subscription.unsubscribe();
      }
      return post("/account/push/refresh", { endpoint: subscription.endpoint, lang: pageLang }).then(function (data) {
        // Removed in Settings on another device: this browser stops too.
        if (!data.known) return subscription.unsubscribe();
        paintPush("on");
        return null;
      });
    }).catch(function () {
      paintPush("off");
    });
  }

  function turnOn() {
    // requestPermission must run inside the click, or Safari refuses.
    Notification.requestPermission().then(function (permission) {
      if (permission !== "granted") {
        paintPush(permission === "denied" ? "denied" : "off");
        return null;
      }
      return workerReady.then(function (registration) {
        return registration.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: keyBytes(pushRow.getAttribute("data-push-key"))
        });
      }).then(function (subscription) {
        return post("/account/push/subscribe", { subscription: subscription.toJSON(), lang: pageLang }).then(function () {
          return post("/account/push/test", { endpoint: subscription.endpoint }).catch(function () { return null; });
        });
      }).then(function () {
        window.location.reload();
      });
    }).catch(function (error) {
      pushMessage("[data-push-error]", error && error.message);
    });
  }

  function sendTest() {
    currentSubscription().then(function (subscription) {
      if (!subscription) throw new Error("");
      return post("/account/push/test", { endpoint: subscription.endpoint });
    }).then(function (data) {
      pushMessage("[data-push-status]", data.message);
    }).catch(function (error) {
      pushMessage("[data-push-error]", error && error.message);
    });
  }

  function turnOff() {
    currentSubscription().then(function (subscription) {
      if (!subscription) return null;
      var endpoint = subscription.endpoint;
      return post("/account/push/unsubscribe", { endpoint: endpoint }).then(function () {
        return subscription.unsubscribe();
      });
    }).then(function () {
      window.location.reload();
    }).catch(function (error) {
      pushMessage("[data-push-error]", error && error.message);
    });
  }

  document.addEventListener("click", function (event) {
    var target = event.target.closest ? event.target.closest("[data-push-on], [data-push-test], [data-push-off]") : null;
    if (!target || !pushRow) return;
    if (target.hasAttribute("data-push-on")) turnOn();
    else if (target.hasAttribute("data-push-test")) sendTest();
    else turnOff();
  });

  // Logging out turns alerts off on this device, so a shared computer stops
  // showing the host's alerts. The logout itself never waits more than 1.5 s.
  document.addEventListener("submit", function (event) {
    var form = event.target;
    if (!form || form.getAttribute("action") !== "/logout" || form.hasAttribute("data-push-cleared")) return;
    if (!pushSupported || Notification.permission !== "granted") return;
    event.preventDefault();
    form.setAttribute("data-push-cleared", "");
    var sent = false;
    function leave() {
      if (sent) return;
      sent = true;
      form.submit();
    }
    var timer = setTimeout(leave, 1500);
    currentSubscription().then(function (subscription) {
      if (!subscription) return null;
      return post("/account/push/unsubscribe", { endpoint: subscription.endpoint }).catch(function () {
        return null;
      }).then(function () {
        return subscription.unsubscribe();
      });
    }).catch(function () {
      return null;
    }).then(function () {
      clearTimeout(timer);
      leave();
    });
  });

  initPush();
})();
```

Run: `node --check App/app/static/pwa.js 2>&1 | tail -3`. Expected: no output.

**Step 5.** Bump the key: in `App/app/templates/base.html` and `App/app/templates/auth_base.html` replace `/static/pwa.js?v=20261021-0203` with `/static/pwa.js?v=20261021-0206`. Then `cd App && .venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -3`.

**Step 6.** Create `App/tests/test_push_settings_browser.py` with exactly:

```python
"""0206: Settings > Phone app > urgent alerts, in a real browser.

The browser's push service is not reachable from CI, so an init script stands
in for PushManager (it hands out the subscription of a test Browser from
tests/test_push.py); everything else (permission, pwa.js, the endpoints, the
database, the encrypted test push) runs for real.
"""
import json
import os
import secrets
from pathlib import Path

import pytest

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

from app import auth, config, push
from tests.browser_support import chromium_launch_kwargs
from tests.test_host_geometry import _browser_session_cookie, base  # noqa: F401
from tests.test_push import Browser, PushService

SHOT_DIR = "/mnt/project-files/pwa/0206/"
IPHONE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1"
)

_FAKE_PUSH = """
(() => {
  const made = {
    endpoint: %s,
    options: { applicationServerKey: null },
    expirationTime: null,
    toJSON() { return { endpoint: this.endpoint, keys: %s }; },
    unsubscribe() { sessionStorage.removeItem('fake-push'); return Promise.resolve(true); },
  };
  PushManager.prototype.getSubscription = () =>
    Promise.resolve(sessionStorage.getItem('fake-push') ? made : null);
  PushManager.prototype.subscribe = () => {
    sessionStorage.setItem('fake-push', '1');
    return Promise.resolve(made);
  };
})();
"""


@pytest.fixture(autouse=True)
def push_on(monkeypatch):
    monkeypatch.setattr(config, "WEB_PUSH", True)


def _host():
    username = f"ps{secrets.token_hex(3)}"
    owner = auth.create_account(f"{username}@example.test", "Push", role="host", username=username)
    return username, owner


def _browser(playwright):
    try:
        return playwright.chromium.launch(**chromium_launch_kwargs())
    except Exception as exc:
        if REQUIRE_BROWSER:
            raise
        pytest.skip(f"Chromium is not available: {exc}")


def _page(browser, base, username, width, *, fake=None, user_agent=None, collapsed=False, grant=True):
    options = {"viewport": {"width": width, "height": 900}}
    if user_agent:
        options["user_agent"] = user_agent
    context = browser.new_context(**options)
    if grant:
        context.grant_permissions(["notifications"], origin=base)
    context.add_cookies([{"name": auth.SESSION_COOKIE, "value": _browser_session_cookie(username), "url": base + "/"}])
    if fake:
        context.add_init_script(_FAKE_PUSH % (json.dumps(fake.endpoint), json.dumps(fake.subscription()["keys"])))
    context.add_init_script(
        "try { localStorage.setItem('ubyhost-sidebar-collapsed', '%s'); } catch (e) {}" % ("1" if collapsed else "0")
    )
    return context.new_page()


def _shot(page, name):
    Path(SHOT_DIR).mkdir(parents=True, exist_ok=True)
    page.locator("#settings-group-phone").screenshot(path=f"{SHOT_DIR}{name}.png")


def _open_settings(page, base, lang):
    page.goto(f"{base}/settings?lang={lang}")
    page.wait_for_selector("#settings-group-phone", timeout=30000)
    page.wait_for_function("navigator.serviceWorker.controller !== null", timeout=30000)


@pytest.mark.parametrize("lang", ["en", "cs", "vi"])
def test_turning_alerts_on_sends_one_test_and_lists_this_device(base, lang, monkeypatch):
    service = PushService(monkeypatch)
    username, owner = _host()
    fake = Browser()
    with sync_api.sync_playwright() as playwright:
        browser = _browser(playwright)
        try:
            page = _page(browser, base, username, 390, fake=fake)
            _open_settings(page, base, lang)
            assert page.is_visible("[data-push-on]")
            assert not page.is_visible("[data-push-unsupported]")
            _shot(page, f"alerts-off-390-{lang}")
            page.click("[data-push-on]")
            page.wait_for_selector("[data-push-state-on]:not([hidden])", timeout=30000)
            assert push.count_for(owner) == 1
            assert len(service.sent) == 1
            assert fake.read(service.sent[0]["data"])["title"] == push.message("test", lang, {})["title"]
            assert page.is_visible("[data-push-controls]")
            assert page.locator("#settings-alerts form[action^='/account/push/devices/']").count() == 1
            _shot(page, f"alerts-on-390-{lang}")
        finally:
            browser.close()


@pytest.mark.parametrize("width,collapsed", [(1280, False), (1280, True), (2000, False), (2000, True)])
def test_the_alerts_row_fits_wide_layouts(base, width, collapsed):
    username, owner = _host()
    fake = Browser()
    push.save_subscription(owner, fake.subscription(), lang="en", device="iPhone")
    with sync_api.sync_playwright() as playwright:
        browser = _browser(playwright)
        try:
            page = _page(browser, base, username, width, fake=fake, collapsed=collapsed)
            page.add_init_script("sessionStorage.setItem('fake-push', '1')")
            _open_settings(page, base, "en")
            page.wait_for_selector("[data-push-state-on]:not([hidden])", timeout=30000)
            overflow = page.evaluate(
                "[...document.querySelectorAll('#settings-group-phone *')]"
                ".filter(e => e.scrollWidth > e.clientWidth + 1 && getComputedStyle(e).overflowX === 'visible').length"
            )
            assert overflow == 0
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            _shot(page, f"alerts-on-{width}{'-collapsed' if collapsed else ''}-en")
        finally:
            browser.close()


@pytest.mark.parametrize("lang", ["en", "cs", "vi"])
def test_an_iphone_outside_the_home_screen_app_is_told_to_add_it_first(base, lang):
    username, _owner = _host()
    with sync_api.sync_playwright() as playwright:
        browser = _browser(playwright)
        try:
            page = _page(browser, base, username, 390, user_agent=IPHONE, grant=False)
            page.goto(f"{base}/settings?lang={lang}")
            page.wait_for_selector("#settings-group-phone", timeout=30000)
            page.wait_for_selector("[data-push-ios-first]:not([hidden])", timeout=30000)
            assert not page.is_visible("[data-push-on]")
            assert page.is_visible("[data-pwa-ios]")
            _shot(page, f"iphone-390-{lang}")
        finally:
            browser.close()


def test_logging_out_turns_alerts_off_on_this_device(base):
    username, owner = _host()
    fake = Browser()
    push.save_subscription(owner, fake.subscription(), lang="en", device="Mac")
    with sync_api.sync_playwright() as playwright:
        browser = _browser(playwright)
        try:
            page = _page(browser, base, username, 1280, fake=fake)
            page.add_init_script("sessionStorage.setItem('fake-push', '1')")
            _open_settings(page, base, "en")
            page.wait_for_selector("[data-push-state-on]:not([hidden])", timeout=30000)
            with page.expect_navigation(timeout=30000):
                page.evaluate("document.querySelector('form[action=\"/logout\"]').requestSubmit()")
            assert "/login" in page.url
            assert push.count_for(owner) == 0
        finally:
            browser.close()
```

Run: `cd App && UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium .venv/bin/python -m pytest tests/test_push_settings_browser.py -q -rs --tb=short -x 2>&1 | tail -20`. Expected: 11 passed, 0 skipped. Fix the code once if needed (never weaken the test); a second failure: STOP and report.

**Step 7.** Look at each screenshot in `/mnt/project-files/pwa/0206/` once (Read tool). Check: nothing cut off, the On badge and the two buttons sit on one line at 1280/2000, labels fit at 390 in VI. If a measured layout fault needs CSS, STOP and report it (no CSS file is in §3).

## 5. Do not touch

Any CSS, `sw.js`, Python outside the two i18n files. Hard rules: no new dependency, light mode, no em dashes, one primary button per template.

## 6. Commands

From `App/`, each ending `2>&1 | tail -30`:

1. `.venv/bin/python -m pytest tests/test_pwa.py tests/test_push_routes.py tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py tests/test_destructive_confirm.py tests/test_design_lint.py tests/test_host_i18n.py tests/test_no_em_dashes.py tests/test_cookie_inventory.py -q --tb=short -x`
2. `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium .venv/bin/python -m pytest tests/test_push_settings_browser.py tests/test_pwa_browser.py tests/test_host_geometry.py tests/test_design_guardrails_browser.py -q -rs --tb=short -x` (0 skipped)
3. From the repo root: `python3 scripts/context_lint.py`

## 7. Acceptance

- [ ] §6 passes, 0 skipped.
- [ ] Screenshots in `/mnt/project-files/pwa/0206/`: `alerts-off-390-{en,cs,vi}`, `alerts-on-390-{en,cs,vi}`, `alerts-on-{1280,2000}[-collapsed]-en`, `iphone-390-{en,cs,vi}`, each looked at once.
- [ ] `git diff --stat` lists only §3 files.

## 8. Stop and ask

As in TEMPLATE §8.

## 9. Report

`docs/tasks/0206-report.md` per TEMPLATE §9; set `Status: review`.

## Risk list (for the reviewer)

`App/app/static/pwa.js` (permission inside the click, logout hook), `App/app/templates/settings.html`.

## Owner steps

None.
