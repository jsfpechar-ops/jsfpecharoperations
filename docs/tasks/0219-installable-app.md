# 0219 (was 0203): Installable phone app (manifest, icons, service worker, offline page)

Status: todo
Depends on: none | Base commit: 2f043c8 | Branch: claude/project-thread-w35ftw
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Make the host app installable: "Add to Home Screen" on iPhone and "Install app" on Android give a full-screen app with the UbyHost icon, and a lost connection shows a calm offline page instead of the browser's error. Settings gets a "Phone app" group that tells each phone exactly how to install.

## 2. Context

- Owner decision 2026-10-21: an installable web app (PWA), not Flutter. Push notifications follow in 0225-0227, so `sw.js` already contains the push handlers.
- **Caching rule (static-cache-keys, PR #401 stale-CSS bug):** the service worker stores exactly ONE response, the offline page. It never stores app pages (they are `no-store` and carry passport numbers, see `App/app/main.py` middleware) and never stores `/static` files (they are versioned with `?v=` and cached by the browser). `/sw.js` is served with `Cache-Control: no-cache`, so a fix reaches phones on their next open.
- Guest links (`/l/...`) are never handled by the worker. Guest pages (`templates/guest/`) get no manifest.
- The CSP (`main.py` `_csp`) has `default-src 'self'`, which already allows a same-origin manifest and worker. Do not change it.
- iPhone: an e-mail login link opens in Safari, not in the installed app, so inside the app the host logs in with a passkey. The copy says so.
- Copy rules: EN, CS and VI; no em dashes; no sentence the button already says.
- Design lint (`scripts/design_lint.py`) checks `settings.html`: no `style=`, only catalog classes, at most ONE `ui-btn-primary` (the passkey button already is), so every new button is `ui-btn-secondary`. `offline.html` is not an enforced template and is self-contained on purpose.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/tools/make_pwa_icons.py` | new | builds the icons from `ubyhost-mark.png` |
| `App/app/static/icons/icon-192.png`, `icon-512.png`, `icon-maskable-512.png`, `badge-96.png` | new (generated) | app icons and Android notification badge |
| `App/app/static/sw.js` | new | service worker |
| `App/app/static/pwa.js` | new | registers the worker, drives Settings > Phone app and the login hint |
| `App/app/templates/offline.html` | new | offline page |
| `App/app/main.py` | edit | `import json`; routes `/manifest.webmanifest`, `/sw.js`, `/offline` |
| `App/app/templates/base.html` | edit | manifest and Apple tags; `pwa.js` |
| `App/app/templates/auth_base.html` | edit | same |
| `App/app/templates/login.html` | edit | in-app login hint |
| `App/app/templates/settings.html` | edit | index card and "Phone app" group |
| `App/app/host_i18n.py` | edit | EN and CS strings |
| `App/app/host_vi_i18n.py` | edit | VI strings |
| `App/tests/test_pwa.py` | new | server tests |
| `App/tests/test_pwa_browser.py` | new | worker + offline test, screenshots |
| `App/tests/static_versions.json` | regenerated | new `pwa.js` key |

No other file may change.

## 4. Steps

**Step 1.** Create `App/tools/make_pwa_icons.py` with exactly:

```python
"""Build the installable-app icons from static/ubyhost-mark.png (brief 0203).

Run from App/: .venv/bin/python tools/make_pwa_icons.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

STATIC = Path(__file__).resolve().parent.parent / "app" / "static"
OUT = STATIC / "icons"
CANVAS = (247, 247, 245, 255)  # tokens.css --canvas, the same light square as apple-touch-icon.png


def _mark() -> Image.Image:
    mark = Image.open(STATIC / "ubyhost-mark.png").convert("RGBA")
    return mark.crop(mark.getchannel("A").getbbox())


def _on_canvas(size: int, mark_share: float) -> Image.Image:
    """The mark centred on the light canvas, its width ``mark_share`` of the side."""
    mark = _mark()
    width = round(size * mark_share)
    height = round(mark.height * width / mark.width)
    mark = mark.resize((width, height), Image.LANCZOS)
    icon = Image.new("RGBA", (size, size), CANVAS)
    icon.alpha_composite(mark, ((size - width) // 2, (size - height) // 2))
    # Opaque: iOS and Android paint transparent corners black.
    return icon.convert("RGB")


def _badge(size: int) -> Image.Image:
    """Android's status-bar badge: the mark's shape in white, the rest transparent."""
    mark = _mark()
    width = round(size * 0.84)
    height = round(mark.height * width / mark.width)
    alpha = mark.getchannel("A").resize((width, height), Image.LANCZOS)
    badge = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    white = Image.new("RGBA", (width, height), (255, 255, 255, 255))
    white.putalpha(alpha)
    badge.alpha_composite(white, ((size - width) // 2, (size - height) // 2))
    return badge


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    # "any": the proportions of apple-touch-icon.png (mark about 72% wide).
    _on_canvas(192, 0.72).save(OUT / "icon-192.png", optimize=True)
    _on_canvas(512, 0.72).save(OUT / "icon-512.png", optimize=True)
    # "maskable": Android crops to a circle of 80% diameter; 56% keeps the mark inside.
    _on_canvas(512, 0.56).save(OUT / "icon-maskable-512.png", optimize=True)
    _badge(96).save(OUT / "badge-96.png", optimize=True)
    for path in sorted(OUT.glob("*.png")):
        print(path.name, Image.open(path).size)


if __name__ == "__main__":
    main()
```

Run: `cd App && .venv/bin/python tools/make_pwa_icons.py 2>&1 | tail -5`. Expected: four lines, `badge-96.png (96, 96)`, `icon-192.png (192, 192)`, `icon-512.png (512, 512)`, `icon-maskable-512.png (512, 512)`. Commit the script and the four PNGs.

**Step 2.** Create `App/app/static/sw.js` with exactly:

```js
/* UbyHost service worker (brief 0203). Served from /sw.js so its scope is the
   whole app.

   It stores exactly one response: the offline page, in the host's language.
   App pages are never stored (they are no-store and carry guest data), and
   /static files are never stored either: they are versioned with ?v= and the
   browser caches them already, so a deploy can never hide behind an old copy
   here. Bump VERSION whenever this file changes. */
"use strict";

var VERSION = "20261021-0203";
var CACHE = "ubyhost-offline-" + VERSION;
var OFFLINE_URL = "/offline";
var LANGS = ["en", "cs", "vi"];
var ICON = "/static/icons/icon-192.png?v=20261021-0203";
var BADGE = "/static/icons/badge-96.png?v=20261021-0203";

function storeOffline(lang) {
  var url = LANGS.indexOf(lang) >= 0 ? OFFLINE_URL + "?lang=" + lang : OFFLINE_URL;
  return fetch(url, { cache: "reload", credentials: "same-origin" }).then(function (response) {
    if (!response.ok) return undefined;
    return caches.open(CACHE).then(function (cache) {
      return cache.put(OFFLINE_URL, response);
    });
  });
}

self.addEventListener("install", function (event) {
  event.waitUntil(storeOffline("").then(function () {
    return self.skipWaiting();
  }));
});

self.addEventListener("activate", function (event) {
  event.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (key) {
      return key.indexOf("ubyhost-") === 0 && key !== CACHE;
    }).map(function (key) {
      return caches.delete(key);
    }));
  }).then(function () {
    if (self.registration.navigationPreload) {
      return self.registration.navigationPreload.enable();
    }
    return undefined;
  }).then(function () {
    return self.clients.claim();
  }));
});

// Page loads go to the network as always; only a failed one gets the offline page.
self.addEventListener("fetch", function (event) {
  var req = event.request;
  if (req.mode !== "navigate" || req.method !== "GET") return;
  var url = new URL(req.url);
  // Guest links (/l/...) belong to the guest, never to the host's app.
  if (url.origin !== self.location.origin || url.pathname === "/l" || url.pathname.indexOf("/l/") === 0) return;
  event.respondWith(Promise.resolve(event.preloadResponse).then(function (preloaded) {
    return preloaded || fetch(req);
  }).catch(function () {
    return caches.open(CACHE).then(function (cache) {
      return cache.match(OFFLINE_URL);
    }).then(function (offline) {
      return offline || Response.error();
    });
  }));
});

// pwa.js tells the worker the page language, so the offline page matches it.
self.addEventListener("message", function (event) {
  var data = event.data || {};
  if (data.type !== "lang" || LANGS.indexOf(data.lang) < 0) return;
  event.waitUntil(caches.open(CACHE).then(function (cache) {
    return cache.match(OFFLINE_URL);
  }).then(function (stored) {
    if (stored && stored.headers.get("Content-Language") === data.lang) return undefined;
    return storeOffline(data.lang);
  }));
});

// Urgent alerts (0225-0227). Every push shows a notification: Safari stops
// delivering to a site that pushes silently. A rotated subscription needs no
// pushsubscriptionchange handler: pwa.js sends the current one on every visit.
self.addEventListener("push", function (event) {
  var data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch (error) {
    data = {};
  }
  event.waitUntil(self.registration.showNotification(data.title || "UbyHost", {
    body: data.body || "",
    tag: data.tag || "",
    renotify: !!data.tag,
    lang: data.lang || "",
    icon: ICON,
    badge: BADGE,
    data: { url: data.url || "/" }
  }));
});

self.addEventListener("notificationclick", function (event) {
  event.notification.close();
  var target = new URL((event.notification.data && event.notification.data.url) || "/", self.location.origin);
  // Only ever open this app's own pages.
  if (target.origin !== self.location.origin) target = new URL("/", self.location.origin);
  event.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true }).then(function (windows) {
    for (var i = 0; i < windows.length; i++) {
      var client = windows[i];
      if (client.url.indexOf(self.location.origin) === 0 && "navigate" in client) {
        return client.focus().then(function (focused) {
          return (focused || client).navigate(target.href);
        }).catch(function () {
          return self.clients.openWindow(target.href);
        });
      }
    }
    return self.clients.openWindow(target.href);
  }));
});
```

Run: `node --check App/app/static/sw.js 2>&1 | tail -3` (if `node` is missing, skip and say so in the report). Expected: no output.

**Step 3.** Create `App/app/static/pwa.js` with exactly:

```js
/* Installable app (brief 0203): registers the service worker, keeps its
   offline page in the page's language, and drives Settings > Phone app and the
   login page hint. Without JavaScript, Settings still says how to add the app. */
(function () {
  "use strict";

  var standalone = window.matchMedia("(display-mode: standalone)").matches ||
    window.navigator.standalone === true;
  var ua = navigator.userAgent || "";
  // iPadOS reports itself as a Mac; the touch screen tells them apart.
  var ios = /iPhone|iPad|iPod/.test(ua) || (/Macintosh/.test(ua) && navigator.maxTouchPoints > 1);
  var installed = standalone;
  var deferredPrompt = null;

  function show(selector, visible) {
    document.querySelectorAll(selector).forEach(function (el) {
      el.hidden = !visible;
    });
  }

  // --- service worker ------------------------------------------------------

  var workerReady = "serviceWorker" in navigator
    ? navigator.serviceWorker.register("/sw.js", { scope: "/" }).then(function () {
      return navigator.serviceWorker.ready;
    })
    : Promise.reject(new Error("no service worker"));

  workerReady.then(function (registration) {
    if (registration.active) {
      registration.active.postMessage({ type: "lang", lang: document.documentElement.lang || "en" });
    }
  }).catch(function () {
    /* The app works without it; only the offline page and alerts need it. */
  });

  // --- Settings > Phone app --------------------------------------------------

  function paintInstall() {
    if (!document.querySelector("[data-pwa-install-row]")) return;
    show("[data-pwa-installed]", installed);
    show("[data-pwa-ios]", !installed && ios);
    show("[data-pwa-install]", !installed && !ios && !!deferredPrompt);
    show("[data-pwa-other]", !installed && !ios && !deferredPrompt);
  }

  window.addEventListener("beforeinstallprompt", function (event) {
    // Settings offers the button, so the browser's own install bar stays away.
    event.preventDefault();
    deferredPrompt = event;
    paintInstall();
  });

  window.addEventListener("appinstalled", function () {
    deferredPrompt = null;
    installed = true;
    paintInstall();
  });

  document.addEventListener("click", function (event) {
    var button = event.target.closest ? event.target.closest("[data-pwa-install]") : null;
    if (!button || !deferredPrompt) return;
    var prompt = deferredPrompt;
    deferredPrompt = null;
    prompt.prompt();
    prompt.userChoice.then(paintInstall, paintInstall);
  });

  // Login page: inside the installed app an e-mail link opens the browser instead.
  show("[data-pwa-standalone]", standalone);

  paintInstall();
})();
```

Run: `node --check App/app/static/pwa.js 2>&1 | tail -3`. Expected: no output.

**Step 4.** Create `App/app/templates/offline.html` with exactly:

```html
<!doctype html>
<html lang="{{ lang }}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="theme-color" content="#f7f7f5">
  <meta name="robots" content="noindex">
  <title>{{ t('offline.title') }} · UbyHost</title>
  {# Brief 0203: self-contained on purpose. The service worker stores only this
     one response, so it cannot depend on a stylesheet. The values are copied
     from tokens.css (--canvas, --ink, --ink-secondary, --brand-action,
     --font-sans), the same way the e-mail templates do it. #}
  <style>
    html { background: #f7f7f5; color: #20201e; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
    body { margin: 0; min-height: 100vh; display: grid; place-items: center; box-sizing: border-box; padding: max(24px, env(safe-area-inset-top)) 24px max(24px, env(safe-area-inset-bottom)); }
    main { max-width: 26rem; text-align: center; }
    h1 { font-size: 1.375rem; line-height: 1.3; margin: 0 0 12px; }
    p { margin: 0 0 24px; line-height: 1.5; color: #50504c; }
    a { display: inline-block; min-height: 44px; box-sizing: border-box; padding: 11px 20px; border-radius: 8px; background: #ad4942; color: #ffffff; font-weight: 600; text-decoration: none; }
    a:focus-visible { outline: 3px solid #20201e; outline-offset: 2px; }
  </style>
</head>
<body>
  <main>
    <h1>{{ t('offline.title') }}</h1>
    <p>{{ t('offline.body') }}</p>
    {# An empty href reloads the address the host was trying to open. #}
    <a href="">{{ t('offline.retry') }}</a>
  </main>
</body>
</html>
```

**Step 5.** `App/app/main.py`. Anchor `import logging` (line 4): add `import json` on the line before it, so the block reads `import json` / `import logging` / `import os`.

**Step 6.** `App/app/main.py`. Anchor (find with `grep -nF 'def tdmrep():' App/app/main.py`):

```python
@app.get("/.well-known/tdmrep.json", include_in_schema=False)
def tdmrep():
    return Response(seo.TDMREP_JSON, media_type="application/json")
```

Insert after it (one blank line before, two blank lines after as usual):

```python
# Brief 0203: the installable app. The manifest and the service worker sit at
# the root so the worker's scope covers the whole app. Both are public, like
# robots.txt, and carry nothing about any account.
_PWA_ICON_KEY = "20261021-0203"
_MANIFEST = {
    "id": "/",
    "name": "UbyHost",
    "short_name": "UbyHost",
    "description": "Guest registration and police reports for short-term rentals.",
    "lang": "en",
    # /login sends a signed-in host straight to the dashboard and never shows
    # the public landing page inside the app.
    "start_url": "/login",
    "scope": "/",
    "display": "standalone",
    "background_color": "#f7f7f5",
    "theme_color": "#f7f7f5",
    "icons": [
        {"src": f"/static/icons/icon-192.png?v={_PWA_ICON_KEY}", "sizes": "192x192",
         "type": "image/png", "purpose": "any"},
        {"src": f"/static/icons/icon-512.png?v={_PWA_ICON_KEY}", "sizes": "512x512",
         "type": "image/png", "purpose": "any"},
        {"src": f"/static/icons/icon-maskable-512.png?v={_PWA_ICON_KEY}", "sizes": "512x512",
         "type": "image/png", "purpose": "maskable"},
    ],
}


@app.get("/manifest.webmanifest", include_in_schema=False)
def web_manifest():
    response = Response(json.dumps(_MANIFEST), media_type="application/manifest+json")
    response.headers["Cache-Control"] = "public, max-age=86400"
    return response


@app.get("/sw.js", include_in_schema=False)
def service_worker():
    # no-cache: the browser asks for a new worker on every visit, so a fix
    # reaches installed phones the next time they open the app.
    body = (config.BASE_DIR / "static" / "sw.js").read_text(encoding="utf-8")
    response = Response(body, media_type="text/javascript; charset=utf-8")
    response.headers["Cache-Control"] = "no-cache"
    return response


@app.get("/offline", include_in_schema=False)
def offline_page(request: Request):
    # The service worker keeps this page and shows it when a page load fails.
    response = templating.render(request, "offline.html", {"show_nav": False, "open_alerts": []})
    response.headers["Content-Language"] = request.state.lang
    response.headers["X-Robots-Tag"] = "noindex"
    return response
```

Run: `cd App && .venv/bin/python -c "import app.main" 2>&1 | tail -3`. Expected: no error.

**Step 7.** `App/app/templates/base.html`. Anchor: `  <link rel="apple-touch-icon" sizes="180x180" href="/static/apple-touch-icon.png?v=20261004a">`. Insert after it:

```html
  <link rel="manifest" href="/manifest.webmanifest">
  <meta name="mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-title" content="UbyHost">
  <meta name="apple-mobile-web-app-status-bar-style" content="default">
```

**Step 8.** `App/app/templates/base.html`. Anchor: `{% if show_nav | default(true) %}<script src="/static/host.js?v=20261014-0102d" defer></script>{% endif %}`. Insert after it:

```html
{% if show_nav | default(true) %}<script src="/static/pwa.js?v=20261021-0203" defer></script>{% endif %}
```

**Step 9.** `App/app/templates/auth_base.html`. Same insert as step 7 after its `apple-touch-icon` line. Then anchor `  <script src="/static/auth.js?v=20260925a"></script>` and insert after it:

```html
  <script src="/static/pwa.js?v=20261021-0203" defer></script>
```

**Step 10.** `App/app/templates/login.html`. Anchor:

```html
        <button class="auth-submit" type="button" data-passkey-login-button>{{ t('login.passkey') }}</button>
```

Insert after it:

```html
        <p class="auth-hint" data-pwa-standalone hidden>{{ t('pwa.login_hint') }}</p>
```

**Step 11.** `App/app/templates/settings.html`. In the index line (line 12), replace `('#settings-group-security', 'settings.group.security'), ` with `('#settings-group-security', 'settings.group.security'), ('#settings-group-phone', 'settings.group.phone'), `.

**Step 12.** `App/app/templates/settings.html`. Anchor: `{% call settings_group('data', t('settings.group.data')) %}`. Insert BEFORE it (followed by one blank line):

```html
{% call settings_group('phone', t('settings.group.phone')) %}
    <div class="ui-section" id="settings-phone">
      <div class="settings-action-list" id="settings-install" data-pwa-install-row>
        <div class="settings-action-row">
          <div>
            <strong>{{ t('pwa.install.title') }}</strong>
            <small>{{ t('pwa.install.help') }}</small>
          </div>
          <button class="ui-btn ui-btn-secondary ui-btn-compact" type="button" data-pwa-install hidden>{{ t('pwa.install.button') }}</button>
          <span class="ui-badge ui-badge-done" data-tone="green" data-pwa-installed hidden>{{ t('pwa.install.installed') }}</span>
        </div>
        <p class="ui-sub" data-pwa-ios hidden>{{ t('pwa.install.ios') }}</p>
        {% if passkeys_available %}<p class="ui-sub" data-pwa-ios hidden>{{ t('pwa.install.ios_passkey') }}</p>{% endif %}
        <p class="ui-sub" data-pwa-other>{{ t('pwa.install.other') }}</p>
      </div>
    </div>
{% endcall %}
```

Run: `python3 scripts/design_lint.py 2>&1 | tail -5`. Expected: `OK`.

**Step 13.** `App/app/host_i18n.py`. Anchor (line ~5794):

```python
for _lang, _strings in _PASSKEY_STRINGS.items():
    STRINGS[_lang].update(_strings)
```

Insert after it:

```python

# Brief 0203: the installable app (Settings > Phone app, login hint, offline page).
_PWA_STRINGS = {
    "en": {
        "settings.group.phone": "Phone app",
        "pwa.install.title": "Add UbyHost to your home screen",
        "pwa.install.help": "It opens full screen, like any other app, and can show urgent alerts.",
        "pwa.install.button": "Install app",
        "pwa.install.installed": "Installed",
        "pwa.install.ios": "In Safari, tap Share (the square with an arrow), then Add to Home Screen.",
        "pwa.install.ios_passkey": "Add a passkey first (under Security). In the app you log in with it, because a login link from your e-mail opens in Safari.",
        "pwa.install.other": "Open this page on your phone, in Safari on iPhone or Chrome on Android, to add UbyHost to the home screen.",
        "pwa.login_hint": "In the app, log in with your passkey. A login link from your e-mail opens in your browser instead.",
        "offline.title": "You are offline",
        "offline.body": "UbyHost needs an internet connection. Check Wi-Fi or mobile data, then try again.",
        "offline.retry": "Try again",
    },
    "cs": {
        "settings.group.phone": "Aplikace v telefonu",
        "pwa.install.title": "Přidejte si UbyHost na plochu",
        "pwa.install.help": "Otevře se přes celou obrazovku jako běžná aplikace a může zobrazovat naléhavá upozornění.",
        "pwa.install.button": "Nainstalovat aplikaci",
        "pwa.install.installed": "Nainstalováno",
        "pwa.install.ios": "V Safari klepněte na Sdílet (čtverec se šipkou) a pak na Přidat na plochu.",
        "pwa.install.ios_passkey": "Nejdřív si přidejte přístupový klíč (v části Zabezpečení). V aplikaci se přihlásíte právě jím, protože odkaz z e-mailu se otevře v Safari.",
        "pwa.install.other": "Otevřete tuto stránku v telefonu, na iPhonu v Safari nebo na Androidu v Chrome, a přidejte si UbyHost na plochu.",
        "pwa.login_hint": "V aplikaci se přihlaste přístupovým klíčem. Odkaz z e-mailu se otevře v prohlížeči, ne tady.",
        "offline.title": "Jste offline",
        "offline.body": "UbyHost potřebuje připojení k internetu. Zkontrolujte Wi-Fi nebo mobilní data a zkuste to znovu.",
        "offline.retry": "Zkusit znovu",
    },
}
for _lang, _strings in _PWA_STRINGS.items():
    STRINGS[_lang].update(_strings)
```

**Step 14.** `App/app/host_vi_i18n.py`. The `STRINGS` dict ends with the line `    "calendar.cleaning_timing_unavailable": ...` followed by `}` at the end of the file. Insert these lines just before that final `}`:

```python
    # Brief 0203: installable app.
    "settings.group.phone": "Ứng dụng trên điện thoại",
    "pwa.install.title": "Thêm UbyHost vào màn hình chính",
    "pwa.install.help": "Ứng dụng mở toàn màn hình như mọi ứng dụng khác và có thể hiện cảnh báo khẩn.",
    "pwa.install.button": "Cài ứng dụng",
    "pwa.install.installed": "Đã cài",
    "pwa.install.ios": "Trong Safari, bấm Chia sẻ (hình vuông có mũi tên), rồi chọn Thêm vào MH chính.",
    "pwa.install.ios_passkey": "Hãy thêm passkey trước (trong mục Bảo mật). Trong ứng dụng, bạn đăng nhập bằng passkey, vì liên kết đăng nhập trong email sẽ mở trong Safari.",
    "pwa.install.other": "Mở trang này trên điện thoại, bằng Safari trên iPhone hoặc Chrome trên Android, để thêm UbyHost vào màn hình chính.",
    "pwa.login_hint": "Trong ứng dụng, hãy đăng nhập bằng passkey. Liên kết trong email sẽ mở trong trình duyệt, không mở ở đây.",
    "offline.title": "Bạn đang ngoại tuyến",
    "offline.body": "UbyHost cần kết nối Internet. Hãy kiểm tra Wi-Fi hoặc dữ liệu di động, rồi thử lại.",
    "offline.retry": "Thử lại",
```

Run: `cd App && .venv/bin/python -m pytest tests/test_host_i18n.py tests/test_no_em_dashes.py -q --tb=short -x 2>&1 | tail -5`. Expected: all pass.

**Step 15.** Create `App/tests/test_pwa.py` with exactly:

```python
"""Brief 0203: the installable app (manifest, icons, service worker, offline page)."""
from __future__ import annotations

import secrets
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import auth, db
from app.main import app
from tests.conftest import login_as

APP_DIR = Path(__file__).resolve().parent.parent / "app"
STATIC = APP_DIR / "static"


def _client() -> TestClient:
    return TestClient(app, base_url="https://testserver")


def _signed_in() -> TestClient:
    db.init_db()
    username = f"pwa{secrets.token_hex(3)}"
    auth.create_account(f"{username}@example.test", "Pwa Host", role="host", username=username)
    client = _client()
    login_as(client, username, url="/login?lang=en")
    return client


def test_the_manifest_makes_an_installable_standalone_app():
    response = _client().get("/manifest.webmanifest")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/manifest+json")
    manifest = response.json()
    assert manifest["display"] == "standalone"
    assert manifest["start_url"] == "/login"
    assert manifest["scope"] == "/" and manifest["id"] == "/"
    assert manifest["theme_color"] == manifest["background_color"] == "#f7f7f5"
    purposes = {(icon["sizes"], icon["purpose"]) for icon in manifest["icons"]}
    assert {("192x192", "any"), ("512x512", "any"), ("512x512", "maskable")} <= purposes


def test_every_manifest_icon_exists_at_its_stated_size_and_is_opaque():
    for icon in _client().get("/manifest.webmanifest").json()["icons"]:
        path = STATIC / icon["src"].split("?")[0].removeprefix("/static/")
        width, height = icon["sizes"].split("x")
        with Image.open(path) as image:
            assert image.size == (int(width), int(height)), icon["src"]
            assert image.mode == "RGB", icon["src"]
    with Image.open(STATIC / "icons" / "badge-96.png") as badge:
        assert badge.size == (96, 96) and badge.mode == "RGBA"


def test_the_service_worker_is_served_from_the_root_and_always_revalidated():
    response = _client().get("/sw.js")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/javascript")
    assert response.headers["cache-control"] == "no-cache"


def test_the_service_worker_stores_only_the_offline_page():
    # Pages are no-store (they carry passport numbers) and /static is versioned
    # and cached by the browser, so the worker must never keep either.
    source = (STATIC / "sw.js").read_text(encoding="utf-8")
    assert source.count("cache.put(") == 1
    assert "cache.put(OFFLINE_URL, response)" in source
    assert "addAll(" not in source and "cache.add(" not in source
    assert 'req.mode !== "navigate"' in source
    assert '"/l/"' in source


@pytest.mark.parametrize(
    "lang,title", [("en", "You are offline"), ("cs", "Jste offline"), ("vi", "Bạn đang ngoại tuyến")]
)
def test_the_offline_page_speaks_the_requested_language(lang, title):
    response = _signed_in().get(f"/offline?lang={lang}")
    assert response.status_code == 200
    assert response.headers["content-language"] == lang
    assert title in response.text
    assert "noindex" in response.headers["x-robots-tag"]


def test_login_and_host_pages_link_the_manifest_and_the_app_script():
    login_page = _client().get("/login?lang=en").text
    assert '<link rel="manifest" href="/manifest.webmanifest">' in login_page
    assert '<meta name="apple-mobile-web-app-capable" content="yes">' in login_page
    assert "/static/pwa.js?v=" in login_page
    assert "data-pwa-standalone" in login_page
    settings = _signed_in().get("/settings?lang=en").text
    assert '<link rel="manifest" href="/manifest.webmanifest">' in settings
    assert "/static/pwa.js?v=" in settings
    assert 'id="settings-group-phone"' in settings
    assert 'href="#settings-group-phone"' in settings
    # Without JavaScript the generic how-to is the one visible line.
    assert "<p class=\"ui-sub\" data-pwa-other>" in settings


def test_guest_pages_never_offer_the_host_app():
    guest_base = (APP_DIR / "templates" / "guest" / "base.html").read_text(encoding="utf-8")
    assert "manifest" not in guest_base and "pwa.js" not in guest_base
```

Run: `cd App && .venv/bin/python -m pytest tests/test_pwa.py -q --tb=short -x 2>&1 | tail -15`. Expected: all pass.

**Step 16.** Create `App/tests/test_pwa_browser.py` with exactly:

```python
"""0203: the service worker installs, and a lost connection shows the offline page."""
import os
import secrets
from pathlib import Path

import pytest

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

from app import auth
from tests.browser_support import chromium_launch_kwargs
from tests.test_host_geometry import _browser_session_cookie, base  # noqa: F401

SHOT_DIR = "/mnt/project-files/pwa/0203/"

_OFFLINE_CACHED = """async (lang) => {
  for (const key of await caches.keys()) {
    const stored = await (await caches.open(key)).match('/offline');
    if (stored && stored.headers.get('Content-Language') === lang) return true;
  }
  return false;
}"""


def _open(playwright, base, width, height, target):
    username = f"pwa{secrets.token_hex(3)}"
    auth.create_account(f"{username}@example.test", "Pwa", role="host", username=username)
    try:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
    except Exception as exc:
        if REQUIRE_BROWSER:
            raise
        pytest.skip(f"Chromium is not available: {exc}")
    context = browser.new_context(viewport={"width": width, "height": height})
    context.add_cookies([{"name": auth.SESSION_COOKIE, "value": _browser_session_cookie(username), "url": base + "/"}])
    page = context.new_page()
    page.goto(base + target)
    page.wait_for_selector("#main-content", timeout=30000)
    return browser, context, page


def _shot(page, name):
    Path(SHOT_DIR).mkdir(parents=True, exist_ok=True)
    page.screenshot(path=f"{SHOT_DIR}{name}.png", full_page=True)


@pytest.mark.parametrize(
    "lang,title", [("en", "You are offline"), ("cs", "Jste offline"), ("vi", "Bạn đang ngoại tuyến")]
)
def test_a_failed_page_load_shows_the_offline_page_in_the_hosts_language(base, lang, title):
    with sync_api.sync_playwright() as playwright:
        browser, context, page = _open(playwright, base, 390, 844, f"/settings?lang={lang}")
        try:
            page.wait_for_function("navigator.serviceWorker.controller !== null", timeout=30000)
            page.wait_for_function(_OFFLINE_CACHED, arg=lang, timeout=30000)
            # Settings > Phone app: on desktop Chromium the generic how-to shows.
            assert page.is_visible("#settings-group-phone [data-pwa-other]")
            assert not page.is_visible("#settings-group-phone [data-pwa-ios]")
            page.locator("#settings-group-phone").scroll_into_view_if_needed()
            _shot(page, f"settings-phone-390-{lang}")
            context.set_offline(True)
            page.goto(base + "/stays")
            assert page.locator("h1").inner_text() == title
            _shot(page, f"offline-390-{lang}")
            context.set_offline(False)
        finally:
            browser.close()


def test_guest_links_are_never_answered_by_the_worker(base):
    with sync_api.sync_playwright() as playwright:
        browser, context, page = _open(playwright, base, 390, 844, "/settings?lang=en")
        try:
            page.wait_for_function("navigator.serviceWorker.controller !== null", timeout=30000)
            context.set_offline(True)
            with pytest.raises(Exception):
                page.goto(base + "/l/not-a-real-link")
            context.set_offline(False)
        finally:
            browser.close()
```

Run: `cd App && UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium .venv/bin/python -m pytest tests/test_pwa_browser.py -q -rs --tb=short -x 2>&1 | tail -15`. Expected: 4 passed, 0 skipped. If `context.set_offline` does not reach the service worker's own fetch in this Chromium (the offline test then shows a browser error, not the title), STOP and report it with the last 15 lines. Do not weaken the test.

**Step 17.** Regenerate the cache-key manifest: `cd App && .venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -3`. Then run §6.

## 5. Do not touch

`App/app/templates/guest/`, the CSP in `main.py`, `host.css`/`host2.css`/any CSS, `passkeys.js`, `auth.js`. Hard rules: no new dependency (Pillow is already installed through `qrcode[pil]`), light mode only, no em dashes, no secrets.

## 6. Commands

From `App/`, each ending `2>&1 | tail -30`:

1. `.venv/bin/python -m pytest tests/test_pwa.py tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py tests/test_cookie_inventory.py tests/test_host_i18n.py tests/test_no_em_dashes.py tests/test_design_lint.py tests/test_privacy_first.py -q --tb=short -x`
2. `.venv/bin/python -m pytest tests/test_login_*.py tests/test_passkeys.py -q --tb=short -x`
3. `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium .venv/bin/python -m pytest tests/test_pwa_browser.py tests/test_host_geometry.py tests/test_design_guardrails_browser.py -q -rs --tb=short -x` (0 skipped)
4. From the repo root: `python3 scripts/context_lint.py`

## 7. Acceptance

- [ ] §6 commands 1 to 4 pass, 0 skipped.
- [ ] Screenshots exist: `/mnt/project-files/pwa/0203/settings-phone-390-{en,cs,vi}.png` and `offline-390-{en,cs,vi}.png`. Look at each once: the offline page is centred, the button is coral, nothing is cut off.
- [ ] `git diff --stat` lists only §3 files.

## 8. Stop and ask

As in TEMPLATE §8. Also stop if any anchor is missing, or if a test outside §6 needs a change.

## 9. Report

`docs/tasks/0219-report.md` per TEMPLATE §9; set `Status: review`. Do not open a PR; the orchestrator does after 0227.

## Risk list (for the reviewer)

`App/app/static/sw.js`, `App/app/static/pwa.js`, `App/app/main.py`, `App/app/templates/settings.html`.

## Owner steps

None for this brief. After deploy: on iPhone open the app in Safari, Share, Add to Home Screen; on Android Chrome, Settings > Phone app > Install app.
