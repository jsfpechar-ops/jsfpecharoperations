# 0324: Havel (AI): launcher, panel, havel.js

Status: todo
Depends on: 0313 | Base commit: 92646d3 (check `git rev-parse --short origin/main` first; if it differs, write the current one here) | Branch: task/0324-havel-panel
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Havel gets its entry points (a sidebar item on the computer, a top-bar button and a More-sheet row on the phone) and a modal panel included once in `base.html`, driven by one small `havel.js` (fetch submit, writing state, Enter to send, focus on the answer). The panel shows the 0313 topics as its empty state and the 0312 thread and composer; without JavaScript every launcher is a link to `/havel`.

## 2. Context

Plan: `docs/plans/havel-support-assistant.md` sections 17a (entry points), 17b (panel). Rules: AGENTS.md 6 (light mode only), 7 (browser tests at 390 and 1280, 0 skipped, screenshots), 9 (copy keys); MASTER 6.2.4 (sheets), 7.1 (buttons), 7.9 (dialog), 10 (never do), 11.0 (layout guard). Tokens only in `host2.css`; the tokens live in `App/app/static/tokens.css`.

Excerpts (verbatim; if one is not found, stop, section 8):

- `App/app/templates/_shell_sidebar.html` lines 26–27:

```jinja
    <nav class="ui-nav ui-nav-bottom" aria-label="{{ t('nav.guide') }}">
      <a class="host-help" href="/guide">{{ icon('book-open', 20) }}<span>{{ t('nav.guide') }}</span></a>
```

- `App/app/templates/_shell_topbar.html` line 7:

```jinja
  <button class="ui-btn ui-btn-quiet ui-btn-icon" type="button" data-command-open aria-label="{{ t('command.open') }}">{{ icon('search', 20) }}</button>
```

- `App/app/templates/_shell_tabbar.html` line 21:

```jinja
      <a class="ui-menu-item" href="/guide">{{ icon('book-open', 16) }}{{ t('nav.guide') }}</a>
```

- `App/app/templates/base.html` line 182 opens the command palette dialog: `<dialog id="command-dialog" class="command-dialog" aria-labelledby="command-title">`. Line 248 (the last script line):

```jinja
{% if show_nav | default(true) %}{% include "_shell_tabbar.html" %}<script src="/static/shell.js?v=20261019-v2a" defer></script>{% endif %}
```

  Line 26 after 0312: `  <link rel="stylesheet" href="/static/host2.css?v=20261024-0312">`. `base.html` has `current_user` and `nav` (a `{% set nav = ... %}` in each page; undefined on a few pages).

- `App/app/static/shell.js` lines 8–16: a click on `[data-sheet-open]` opens the dialog with that id (`showModal()`, `preventDefault()`), so an `<a href="/havel">` launcher becomes the opener; `[data-sheet-close]` and the backdrop close it.

- `App/app/static/host2.css` line 83 styles `.host-workspace .ui-dialog` (width `min(var(--dialog-w), ...)`), line 85 `.ui-dialog .ui-sheet`; the `@media (max-width: 767px)` block at line 113 makes it a bottom sheet (`.ui-sheet { max-height: 85vh; overflow: auto; }`). Focus: `box-shadow: var(--focus-ring-2)` (line 27). Button spinner: `ui-btn-loading` + `aria-busy="true"` (line 21).


- Icons present in `App/app/templates/_icons.html`: `calendar-days`, `external-link`, `send`, `refresh-cw`, `triangle-alert`, `x`, `chevron-right`, `book-open`; `message-circle-question` was added by 0312.
- From 0312 (`grep -n` each before editing): `App/app/routes/havel.py` has `NAV_TO_PAGE`, `_page_context(...)`, `havel_page` (GET), `havel_send` (POST; `fragment = request.headers.get("x-havel") == "1"` renders `_havel_thread.html`). Templates `havel.html`, `_havel_thread.html`, `_havel_form.html` (hidden `_csrf, history, history_sig, page, device, topic, return_to`; textarea `id="havel-message"`; `data-havel-send`). `App/app/havel.py`: `Host(..., page="", topic="", read_keys=[])`, `MAX_MESSAGE_CHARS`, `PAGES`, `page_url(page, property_id, owned_ids)`. Keys `havel.*` exist in en/cs/vi (`havel.launcher`, `havel.open_page`, `havel.close`, `havel.topics_title`, `havel.topic.*`, `havel.q.*`, `havel.writing`, `havel.error`, `havel.retry`, `havel.support.mailto`). Fixtures: `tests.test_submission_retry_cap.host`, `tests.ai_fake.FakeClient`/`reply`, `ai.set_client_for_tests`.
- From 0313 (`grep -n` each before editing): `_havel_topics.html`, `_havel_fragment.html` (`data-havel-items data-mode="replace|append"`, `data-havel-form-wrap`), the hidden `q` field (`data-havel-q`), `havel_topics.ordered(nav)`, `_page_context(..., topic, q, page, return_to, error)`, `GET /havel?topic=&q=` and `POST /havel` both return `_havel_fragment.html` when `X-Havel: 1`; `havel.html` sets `nav = 'havel'`; `base.html` line 26 is `  <link rel="stylesheet" href="/static/host2.css?v=20261024-0313">`.
- `App/app/templating.py` line 16: `from . import (` lists modules alphabetically, one per line, `    host_i18n,` at line 22; line 381: `templates.env.filters["weekday"] = _weekday`.
- Browser harness: `App/tests/test_cleaning_browser.py` lines 1–60 (uvicorn thread on a free port, `chromium_launch_kwargs()`, cookie `auth.SESSION_COOKIE`); `UBYHOST_REQUIRE_BROWSER=1` turns a skip into a failure. Static keys: `App/tests/test_static_versions.py --write`.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/templates/_havel_panel.html | new | the `<dialog id="havel-sheet">` |
| App/app/templating.py | edit | import `havel_topics`, global `havel_topics_for` |
| App/app/templates/base.html | edit | include the panel, load `havel.js`, new CSS key |
| App/app/templates/_shell_sidebar.html | edit | sidebar item |
| App/app/templates/_shell_topbar.html | edit | top-bar button |
| App/app/templates/_shell_tabbar.html | edit | More-sheet row |
| App/app/static/havel.js | new | panel behaviour |
| App/app/static/host2.css | edit | append panel and launcher rules |
| App/tests/test_havel_panel.py | new | panel on every page |
| App/tests/test_havel_browser.py | new | panel at 1280 and 390, screenshots |
| App/tests (static versions manifest) | edit | via `test_static_versions.py --write` only |
| docs/design/catalog.json | edit | classes, enforced template |
| docs/design/MASTER.md | edit | 7.15 Havel panel |
| docs/design/pages/havel.md | edit | panel note |
| docs/tasks/screenshots-0324/*.png | new | 390 and 1280 |

No other file may change.

## 4. Steps

1. **Branch.** `git fetch origin && git checkout -b task/0324-havel-panel origin/task/0313-havel-topics` if that branch exists; otherwise `origin/main` after 0313 is merged. Then `grep -c "data-havel-form-wrap" App/app/templates/_havel_fragment.html` must print `1`, else stop.

2. **Panel template and the template global.** Create `App/app/templates/_havel_panel.html`:

```jinja
{#- 0324: the Havel panel (plan 17b). One <dialog>, included once in base.html
    for signed-in hosts. shell.js opens it from any [data-sheet-open="havel-sheet"];
    havel.js does the rest. Without JavaScript the launchers lead to /havel. -#}
{% from "_icons.html" import icon with context %}
{% set havel_fresh = true %}
{% set havel_show_topics = true %}
{% set havel_max = 600 %}
{% set havel_page = nav | default('') %}
{% set havel_return_to = request.url.path %}
{% set havel_topics = havel_topics_for(nav | default('')) %}
<dialog id="havel-sheet" class="ui-dialog havel-dialog" aria-labelledby="havel-title" data-havel-panel
        data-writing="{{ t('havel.writing') }}" data-error="{{ t('havel.error') }}" data-retry="{{ t('havel.retry') }}" data-name="{{ t('havel.name') }}">
  <div class="ui-sheet">
    <span class="ui-sheet-handle" aria-hidden="true"></span>
    <div class="havel-head">
      <span class="havel-avatar" aria-hidden="true">{{ icon('message-circle-question', 16) }}</span>
      <div class="havel-head-text"><h2 id="havel-title">{{ t('havel.name') }}</h2><p>{{ t('havel.subtitle') }}</p></div>
      <a class="ui-btn ui-btn-quiet ui-btn-icon" href="/havel" aria-label="{{ t('havel.open_page') }}" title="{{ t('havel.open_page') }}">{{ icon('external-link', 20) }}</a>
      <button class="ui-btn ui-btn-quiet ui-btn-icon" type="button" data-sheet-close aria-label="{{ t('havel.close') }}">{{ icon('x', 20) }}</button>
    </div>
    <div class="havel-thread" role="log" aria-live="polite" data-havel-thread>
      {% include "_havel_topics.html" %}
    </div>
    <div data-havel-form-wrap>{% include "_havel_form.html" %}</div>
  </div>
</dialog>
```

   `havel_topics_for` is a template global: in `App/app/templating.py` the import block `from . import (` (line 16) lists modules alphabetically, one per line, with `    host_i18n,` at line 22. Insert the line `    havel_topics,` directly before `    host_i18n,`. Then find the line `templates.env.filters["weekday"] = _weekday` (line 381) and add directly after it:

```python
templates.env.globals["havel_topics_for"] = havel_topics.ordered  # 0324: topics for the panel in base.html
```

   (`havel_topics` imports only `host_i18n`, so there is no import cycle.) The panel's `havel_max` is the literal 600; the test in step 8 ties it to `havel.MAX_MESSAGE_CHARS`.

3. **base.html.** Directly before the line `<dialog id="command-dialog" class="command-dialog" aria-labelledby="command-title">` insert:

```jinja
{% if (show_nav | default(true)) and current_user %}{% include "_havel_panel.html" %}{% endif %}
```

   and replace the last script line (quoted in section 2) with:

```jinja
{% if show_nav | default(true) %}{% include "_shell_tabbar.html" %}<script src="/static/shell.js?v=20261019-v2a" defer></script>{% endif %}
{% if (show_nav | default(true)) and current_user %}<script src="/static/havel.js?v=20261024-0324" defer></script>{% endif %}
```

4. **Launchers.** In `_shell_sidebar.html`, directly before the `<a class="host-help" href="/guide">` line insert:

```jinja
      <a class="host-help havel-launcher" href="/havel" title="{{ t('havel.name') }}" data-sheet-open="havel-sheet" data-havel-launcher {% if nav == 'havel' %}aria-current="page"{% endif %}>{{ icon('message-circle-question', 20) }}<span>{{ t('havel.name') }}</span></a>
```

   In `_shell_topbar.html`, directly before the search button line insert:

```jinja
  <a class="ui-btn ui-btn-quiet ui-btn-icon havel-launcher" href="/havel" data-sheet-open="havel-sheet" data-havel-launcher aria-label="{{ t('havel.launcher') }}">{{ icon('message-circle-question', 20) }}</a>
```

   In `_shell_tabbar.html`, directly before the guide row insert:

```jinja
      <a class="ui-menu-item" href="/havel" data-havel-more>{{ icon('message-circle-question', 16) }}{{ t('havel.name') }}</a>
```

   (A plain link: `havel.js` closes the More sheet and opens the panel.)

   On `/havel` itself (`nav == 'havel'` since 0313) the panel would duplicate the page: in `_havel_panel.html` wrap the `<dialog>…</dialog>` in `{% if nav | default('') != 'havel' %}…{% endif %}` (no dialog, so `shell.js` lets the launcher link through).

   Command: `cd App && .venv/bin/python -c "from app.main import app" && grep -c 'havel-sheet' app/templates/_shell_sidebar.html app/templates/_shell_topbar.html app/templates/_havel_panel.html`. Expected: `1`, `1`, `1`.

5. **havel.js.** Create `App/app/static/havel.js`:

```js
/* 0313: Havel panel. shell.js opens/closes the dialog; this file submits by fetch, swaps the
   fragment, shows the writing state, sends on Enter, counts from 500, focuses the answer. */
(function () {
  "use strict";
  var panel = document.querySelector("[data-havel-panel]");
  var page = document.querySelector("[data-havel-page]");
  var root = panel || page;
  if (!root) return;
  var PHONE = window.matchMedia("(max-width: 1023px)");

  function thread() { return root.querySelector("[data-havel-thread]"); }
  function form() { return root.querySelector("[data-havel-form]"); }
  function textarea() { return root.querySelector("#havel-message"); }

  function setDevice() {
    var d = root.querySelector("[data-havel-device]");
    if (d) d.value = PHONE.matches ? "phone" : "computer";
  }

  function scrollDown() {
    var t = thread();
    if (t) t.scrollTop = t.scrollHeight;
  }

  function focusAnswer() {
    var bubbles = root.querySelectorAll(".havel-msg-havel");
    var last = bubbles[bubbles.length - 1];
    if (last) last.focus({ preventScroll: true });
    scrollDown();
  }

  function swap(html, mode) {
    var box = document.createElement("div");
    box.innerHTML = html;
    var items = box.querySelector("[data-havel-items]");
    var formWrap = box.querySelector("[data-havel-form-wrap]");
    var t = thread();
    if (items && t) {
      var replace = mode === "replace" || items.getAttribute("data-mode") === "replace";
      if (replace) t.innerHTML = "";
      var old = t.querySelector("[data-havel-topics]");
      if (old && !replace) old.remove();
      while (items.firstChild) t.appendChild(items.firstChild);
    }
    var wrap = root.querySelector("[data-havel-form-wrap]");
    if (formWrap && wrap) wrap.innerHTML = formWrap.innerHTML;
    setDevice();
    bindCounter();
  }

  function writing(on) {
    var t = thread();
    var send = root.querySelector("[data-havel-send]");
    var old = t && t.querySelector("[data-havel-writing]");
    if (old) old.remove();
    if (send) { send.classList.toggle("ui-btn-loading", on); send.toggleAttribute("aria-busy", on); send.disabled = on; }
    if (on && t) {
      var el = document.createElement("div");
      el.className = "havel-msg havel-msg-havel havel-writing";
      el.setAttribute("data-havel-writing", "");
      el.setAttribute("aria-busy", "true");
      el.innerHTML = '<div class="havel-bubble"><span class="havel-dots" aria-hidden="true"><i></i><i></i><i></i></span><span class="sr-only"></span></div>';
      el.querySelector(".sr-only").textContent = root.getAttribute("data-writing");
      t.appendChild(el);
      scrollDown();
    }
  }

  function showError(text) {
    var t = thread();
    if (!t) return;
    var el = document.createElement("div");
    el.className = "havel-msg havel-msg-havel";
    el.setAttribute("tabindex", "-1");
    el.innerHTML = '<div class="havel-bubble"><p></p></div><div class="havel-links"><button class="ui-btn ui-btn-secondary ui-btn-compact" type="button" data-havel-retry></button></div>';
    el.querySelector("p").textContent = root.getAttribute("data-error") || "Error";
    el.querySelector("button").textContent = root.getAttribute("data-retry") || "Retry";
    t.appendChild(el);
    var ta = textarea();
    if (ta) ta.value = text;
    el.focus({ preventScroll: true });
    scrollDown();
  }

  function echo(text) {
    var t = thread();
    if (!t) return;
    var topics = t.querySelector("[data-havel-topics]");
    if (topics) topics.remove();
    var el = document.createElement("div");
    el.className = "havel-msg havel-msg-host";
    el.innerHTML = '<div class="havel-bubble"><p></p></div>';
    el.querySelector("p").textContent = text;
    t.appendChild(el);
  }

  function send(extra) {
    var f = form();
    if (!f) return;
    var ta = textarea();
    var text = ta ? ta.value.trim() : "";
    if (!extra && !text) return;
    var data = new FormData(f);
    if (extra) Object.keys(extra).forEach(function (k) { data.set(k, extra[k]); });
    if (!extra) echo(text);
    writing(true);
    fetch(f.getAttribute("action") || "/havel", {
      method: "POST", body: data, credentials: "same-origin",
      headers: { "X-Havel": "1", "Accept": "text/html" }
    }).then(function (res) {
      if (!res.ok) throw new Error(String(res.status));
      return res.text();
    }).then(function (html) {
      writing(false);
      swap(html, extra && extra.reset ? "replace" : "append");
      focusAnswer();
    }).catch(function () {
      writing(false);
      showError(text);
    });
  }

  function load(url, mode) {
    fetch(url, { credentials: "same-origin", headers: { "X-Havel": "1", "Accept": "text/html" } })
      .then(function (res) { return res.ok ? res.text() : Promise.reject(new Error(String(res.status))); })
      .then(function (html) {
        swap(html, mode || "replace");
        var answer = root.querySelector(".havel-answer");
        if (answer) answer.focus({ preventScroll: true });
        var t = thread();
        if (t) t.scrollTop = 0;
      })
      .catch(function () { window.location.href = url; });
  }

  function bindCounter() {
    var ta = textarea();
    if (!ta || ta.hasAttribute("data-havel-counted")) return;
    ta.setAttribute("data-havel-counted", "");
    var max = parseInt(ta.getAttribute("maxlength") || "600", 10);
    var counter = document.createElement("p");
    counter.className = "havel-meta havel-counter";
    counter.setAttribute("aria-live", "polite");
    counter.hidden = true;
    ta.insertAdjacentElement("afterend", counter);
    ta.addEventListener("input", function () {
      var n = ta.value.length;
      counter.hidden = n < max - 100;
      counter.textContent = n + " / " + max;
    });
    ta.addEventListener("keydown", function (event) {
      if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
        event.preventDefault();
        send();
      }
    });
  }

  root.addEventListener("submit", function (event) {
    var f = event.target.closest ? event.target.closest("[data-havel-form]") : null;
    if (!f) return;
    event.preventDefault();
    var submitter = event.submitter;
    if (submitter && submitter.name === "reset") { send({ reset: "1", message: "" }); return; }
    send();
  });

  root.addEventListener("click", function (event) {
    var link = event.target.closest ? event.target.closest("[data-havel-topic-link]") : null;
    if (link) { event.preventDefault(); load(link.getAttribute("href"), "replace"); return; }
    var ask = event.target.closest ? event.target.closest("[data-havel-ask]") : null;
    if (ask) {
      event.preventDefault();
      var topic = root.querySelector("[data-havel-topic]");
      var q = root.querySelector("[data-havel-q]");
      if (topic) topic.value = ask.getAttribute("data-topic") || "";
      if (q) q.value = ask.getAttribute("data-q") || "";
      var ta = textarea();
      if (ta) ta.focus();
      return;
    }
    var retry = event.target.closest ? event.target.closest("[data-havel-retry]") : null;
    if (retry) { retry.closest(".havel-msg").remove(); send(); }
  });

  document.addEventListener("click", function (event) {
    var more = event.target.closest ? event.target.closest("[data-havel-more]") : null;
    if (!more || !panel || typeof panel.showModal !== "function") return;
    event.preventDefault();
    var sheet = document.getElementById("more-sheet");
    if (sheet && sheet.open) sheet.close();
    if (!panel.open) panel.showModal();
    var ta = textarea();
    if (ta && !PHONE.matches) ta.focus();
  });

  if (panel) {
    panel.addEventListener("close", function () {
      var opener = document.querySelector("[data-havel-launcher]:not([hidden])");
      if (opener && opener.offsetParent !== null) opener.focus();
    });
    // For 0322 (command palette): open with a prefilled question.
    window.UbyHavel = { open: function (text) {
      if (!panel.open) panel.showModal();
      var ta = textarea();
      if (ta) { if (text) ta.value = text; ta.focus(); ta.dispatchEvent(new Event("input")); }
    } };
  }

  setDevice();
  bindCounter();
  PHONE.addEventListener("change", setDevice);
})();
```

   Command: `cd App && node --check app/static/havel.js && echo js-ok` (no `node`: rely on the browser test). Expected: `js-ok`.

6. **CSS.** Append to the very end of `App/app/static/host2.css` (after the 0313 block):

```css

/* 0324: Havel panel and launcher (MASTER 7.15, plan 17a-17b). Computer: the dialog is anchored
   bottom-right, 400 x 680 at most; phone: the existing bottom sheet, 92dvh. Tokens only. */
.host-workspace .havel-launcher span { white-space: nowrap; }
.host-workspace .havel-dialog { --havel-w: 400px; --havel-h: 680px; width: min(var(--havel-w), calc(100vw - var(--space-12))); }
@media (min-width: 768px) {
  .host-workspace .havel-dialog { position: fixed; inset: auto var(--space-6) var(--space-6) auto; margin: 0; }
  .host-workspace .havel-dialog .ui-sheet { height: min(var(--havel-h), calc(100dvh - var(--space-12))); }
}
.host-workspace .havel-dialog .ui-sheet { display: flex; flex-direction: column; padding: var(--space-4) var(--space-4) var(--space-3); overflow: hidden; }
.host-workspace .havel-dialog .havel-thread { flex: 1 1 auto; min-height: 0; overflow-y: auto; padding: var(--space-2) var(--space-1); }
.host-workspace .havel-dialog .havel-composer { margin-top: var(--space-2); padding-bottom: env(safe-area-inset-bottom); }
.host-workspace .havel-head { display: flex; align-items: center; gap: var(--space-3); padding-bottom: var(--space-3); border-bottom: 1px solid var(--line); }
.host-workspace .havel-head .havel-avatar { width: var(--space-6); height: var(--space-6); }
.host-workspace .havel-head-text { flex: 1 1 auto; min-width: 0; }
.host-workspace .havel-dialog .havel-head h2 { margin: 0; font-size: var(--size-16); font-weight: 600; line-height: 1.3; }
.host-workspace .havel-head-text p { margin: 0; font-size: var(--size-13); color: var(--ink-3); }
.host-workspace .havel-writing .havel-bubble { padding: var(--space-3) var(--space-4); }
.host-workspace .havel-dots { display: inline-flex; gap: var(--space-1); }
.host-workspace .havel-dots i { width: var(--space-2); height: var(--space-2); border-radius: var(--radius-pill); background: var(--ink-3); animation: havel-blink 1.2s infinite ease-in-out; }
.host-workspace .havel-dots i:nth-child(2) { animation-delay: 0.2s; }
.host-workspace .havel-dots i:nth-child(3) { animation-delay: 0.4s; }
@keyframes havel-blink { 0%, 80%, 100% { opacity: 0.3; } 40% { opacity: 1; } }
@media (prefers-reduced-motion: reduce) { .host-workspace .havel-dots i { animation: none; opacity: 0.6; } }
@media (max-width: 767px) {
  .host-workspace .havel-dialog .ui-sheet { max-height: 92dvh; height: 92dvh; }
}
```

   Check the tokens exist: `grep -c -- "--space-12:\|--size-16:\|--control-h:" App/app/static/tokens.css` (expected `3`). Then the cache key: `sed -i 's/host2.css?v=20261024-0313"/host2.css?v=20261024-0324"/' App/app/templates/base.html && grep -c 'host2.css?v=20261024-0324"' App/app/templates/base.html` (expected `1`), then `cd App && .venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -3`, then from the repo root `python3 scripts/design_lint.py 2>&1 | tail -5` (the two `px` values are custom properties on the component, like `--dialog-w`; if the lint still rejects them, stop, section 8).

7. **Catalog, MASTER, page note.** From the repo root:

```python
import json
from pathlib import Path

p = Path("docs/design/catalog.json")
c = json.loads(p.read_text(encoding="utf-8"))
new = ["havel-launcher", "havel-dots"]
c["classes"] += [k for k in new if k not in c["classes"]]
for t in ["App/app/templates/_havel_panel.html"]:
    if t not in c["enforced_templates"]:
        c["enforced_templates"].append(t)
p.write_text(json.dumps(c, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("catalog ok")
```

   In `docs/design/MASTER.md`, directly before the line `## 8. Copy tone` insert:

```markdown
### 7.15 Havel panel: `_havel_panel.html` (0324)

One `<dialog class="ui-dialog havel-dialog">` for the AI support assistant. Computer: anchored bottom-right, 400 x 680 max; phone: the 7.9 bottom sheet at 92dvh. Header: 24 px avatar (`--accent-soft`, `message-circle-question`), title "Havel (AI)" 16/600 (AI never dropped), subtitle 13 `--ink-3`, quiet icon buttons "Open as a page" and close. Thread `role="log"`: host bubbles right on `--surface-2`, Havel bubbles left on `--surface` with a hairline, steps as `<ol>`, at most three `secondary compact` links and a 7.5 card under a bubble. Composer: textarea, `primary` Send (the only primary), 12 px remaining line. Empty state: five `ui-menu-item` topics (plan 17c). Launchers: sidebar item above Help & guide; phone top-bar icon button and More row. No floating bubble, no toasts in the panel. Plan section 17.

```

   In `docs/design/pages/havel.md` (0312) append:

```markdown

## Panel (0324)
- `#havel-sheet` in `base.html` for signed-in hosts, not on `/havel` itself. Launchers: `_shell_sidebar.html` (above Help & guide), `_shell_topbar.html` (left of search), `_shell_tabbar.html` More row.
- `havel.js`: fetch submit with `X-Havel: 1`, writing state, Enter sends, counter from 500, focus to the answer, `window.UbyHavel.open(text)` for 0322.
```

   Command: `python3 scripts/design_lint.py 2>&1 | tail -3`. Expected: OK or only pre-existing warnings.

8. **Unit test.** Create `App/tests/test_havel_panel.py`:

```python
"""0324: the panel is on every host page; its launchers are links."""
from __future__ import annotations

import re

from app import havel
from tests.test_submission_retry_cap import host as host  # noqa: F401


def test_panel_max_matches_the_engine_constant():
    assert havel.MAX_MESSAGE_CHARS == 600  # the literal in _havel_panel.html


def test_panel_and_launchers_on_the_dashboard_but_not_on_havel(host):
    page = host.get("/").text
    assert 'id="havel-sheet"' in page and page.count('data-sheet-open="havel-sheet"') == 2
    assert 'data-havel-more' in page and '/static/havel.js?v=' in page
    assert re.search(r'<a class="host-help havel-launcher" href="/havel"', page)
    assert page.count("Havel (AI)") >= 3
    own = host.get("/havel").text
    assert 'id="havel-sheet"' not in own and 'aria-current="page"' in own.split('havel-launcher')[1][:200]
```

   Command: `cd App && .venv/bin/python -m pytest tests/test_havel_panel.py tests/test_havel_topics.py tests/test_havel_page.py -q 2>&1 | tail -30`. Expected: all pass.

9. **Browser test and screenshots** (rule 7). Create `App/tests/test_havel_browser.py`, modelled on `tests/test_cleaning_browser.py` lines 1–60 (copy its `origin`-style fixture: uvicorn thread on a free port; cookie `auth.SESSION_COOKIE` from the `host` TestClient):

```python
"""0324: the Havel panel in a real browser at 1280 and 390 (rule 7)."""
from __future__ import annotations

import os
import socket
import threading
import time
from pathlib import Path

import pytest
import uvicorn

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

from app import ai, auth, config, db
from app.main import app
from tests.ai_fake import FakeClient, reply
from tests.browser_support import chromium_launch_kwargs
from tests.test_submission_retry_cap import host as host  # noqa: F401

SHOTS = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0324"
ANSWER = {"kind": "answer", "reply": "Open Stays.\n1. Tap Add stay.\n2. Pick the dates.", "sources": ["guide.stays.body"],
          "links": [{"page": "add_stay", "property_id": None}], "action": None, "support_summary": None}


@pytest.fixture
def origin(host, monkeypatch):
    db.init_db()
    monkeypatch.setattr(config, "AI_FEATURES", frozenset({"havel"}))
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "k")
    ai.set_client_for_tests(FakeClient([reply(ANSWER), reply(ANSWER), reply(ANSWER)]))
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 15
    while not server.started and time.time() < deadline:
        time.sleep(.05)
    assert server.started
    yield f"http://127.0.0.1:{port}", host.cookies.get(auth.SESSION_COOKIE)
    server.should_exit = True
    thread.join(timeout=5)
    ai.set_client_for_tests(None)


def _context(playwright, origin, width, js=True):
    try:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
    except Exception:
        if REQUIRE_BROWSER:
            raise
        pytest.skip("Chromium is required for the Havel browser test")
    context = browser.new_context(viewport={"width": width, "height": 900}, java_script_enabled=js)
    context.add_cookies([{"name": auth.SESSION_COOKIE, "value": origin[1], "url": origin[0] + "/"}])
    return browser, context


def test_computer_panel_topics_handoff_and_answer(origin):
    SHOTS.mkdir(parents=True, exist_ok=True)
    with sync_api.sync_playwright() as pw:
        browser, context = _context(pw, origin, 1280)
        page = context.new_page()
        page.goto(origin[0] + "/")
        launcher = page.locator("#app-sidebar [data-havel-launcher]")
        assert launcher.is_visible()
        launcher.click()
        dialog = page.locator("#havel-sheet[open]")
        dialog.wait_for()
        assert dialog.locator("[data-havel-topic-link]").count() == 5
        assert dialog.locator("h2#havel-title").inner_text().strip() == "Havel (AI)"
        box = dialog.locator(".ui-sheet").bounding_box()
        assert box["width"] <= 400 and box["height"] <= 680
        dialog.locator("[data-havel-topic-link]", has_text="stay").first.click()
        dialog.locator("[data-havel-topic-link][href*='q=cancelled']").wait_for()
        dialog.locator("[data-havel-topic-link][href*='q=cancelled']").click()
        dialog.locator("[data-havel-ask]").wait_for()
        page.screenshot(path=str(SHOTS / "panel-topic-1280.png"))
        dialog.locator("[data-havel-ask]").click()
        assert page.evaluate("document.activeElement.id") == "havel-message"
        assert dialog.locator("[data-havel-topic]").input_value() == "stays"
        page.keyboard.type("And if the guest never arrives?")
        page.keyboard.press("Enter")
        dialog.locator(".havel-msg-havel:not([data-havel-writing])").last.wait_for()
        assert dialog.locator(".havel-msg-host").count() == 1
        assert dialog.locator(".havel-bubble ol li").count() == 2
        assert page.evaluate("document.activeElement.className").startswith("havel-msg havel-msg-havel")
        assert dialog.locator("[data-havel-topics]").count() == 0
        page.screenshot(path=str(SHOTS / "panel-answer-1280.png"))
        page.keyboard.press("Escape")
        assert page.locator("#havel-sheet[open]").count() == 0
        browser.close()


def test_phone_launcher_and_sheet(origin):
    SHOTS.mkdir(parents=True, exist_ok=True)
    with sync_api.sync_playwright() as pw:
        browser, context = _context(pw, origin, 390)
        page = context.new_page()
        page.goto(origin[0] + "/")
        topbar = page.locator(".ui-topbar [data-havel-launcher]")
        assert topbar.is_visible()
        tb = topbar.bounding_box()
        assert tb["width"] >= 44 and tb["height"] >= 44
        topbar.click()
        dialog = page.locator("#havel-sheet[open]")
        dialog.wait_for()
        sheet = dialog.locator(".ui-sheet").bounding_box()
        assert sheet["width"] == 390 and sheet["height"] <= 900 * 0.92 + 1
        assert dialog.locator("[data-havel-device]").input_value() == "phone"
        assert page.evaluate("document.documentElement.scrollWidth") <= 390
        page.screenshot(path=str(SHOTS / "panel-topics-390.png"))
        dialog.locator("[data-sheet-close]").click()
        page.locator("[data-sheet-open='more-sheet']").click()
        page.locator("#more-sheet[open] [data-havel-more]").click()
        page.locator("#havel-sheet[open]").wait_for()
        assert page.locator("#more-sheet[open]").count() == 0
        browser.close()

```

   (`#app-sidebar` is the `<aside>` in `_shell_sidebar.html` line 6.) Commands, from `App/` with `export UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome UBYHOST_REQUIRE_BROWSER=1`:

   `.venv/bin/python -m pytest tests/test_havel_browser.py -q 2>&1 | tail -30` (expected: 2 passed, 0 skipped; three PNGs in `docs/tasks/screenshots-0324/`; look at each once and say what you see).

   `.venv/bin/python -m pytest tests/test_design_guardrails_browser.py tests/test_a11y_guard_browser.py -q 2>&1 | tail -30` (expected: pass, 0 skipped; the panel is closed on every guarded page, and `ROUTES["havel"]` from 0312 now also renders the topics).

## 5. Do not touch

`App/app/ai.py`, `App/app/havel.py`, `App/app/havel_prompt.py`, `App/app/havel_topics.py` (0310–0313), the migrations, `requirements*.txt`, `App/app/static/shell.js`, `App/app/static/host.js`, `App/app/static/app.js`, `tokens.css`, any `guide_*` file, the cards (0314). Rules: no dark mode, no new primitive, no colour outside tokens, no hard-coded copy, no floating bubble, no toast inside the panel, no new dependency, no push.

## 6. Commands (from `App/`, `export UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome UBYHOST_REQUIRE_BROWSER=1`)

1. `.venv/bin/python -c "from app.main import app" && echo import-ok` → `import-ok`.
2. `.venv/bin/python -m pytest tests/test_havel_panel.py tests/test_havel_topics.py tests/test_havel_page.py -q 2>&1 | tail -30` → all passed.
3. `.venv/bin/python -m pytest tests/test_havel_browser.py -q 2>&1 | tail -30` → 2 passed, 0 skipped.
4. `.venv/bin/python -m pytest tests/test_design_guardrails_browser.py tests/test_a11y_guard_browser.py tests/test_static_versions.py -q 2>&1 | tail -30` → passed, 0 skipped.
5. From the repo root: `python3 scripts/design_lint.py 2>&1 | tail -5` and `python3 scripts/context_lint.py 2>&1 | tail -3` → OK.

## 7. Acceptance

- [ ] `/` at 1280 shows the sidebar item "Havel (AI)" above Help & guide; clicking it opens `#havel-sheet` bottom-right, 400 x 680 at most, with the five topics, the "Havel (AI)" title and the close button; Escape closes and focus returns to the launcher.
- [ ] At 390 the top bar has a 44 px Havel button left of search; the sheet is full width, 92dvh; the More sheet has a "Havel (AI)" row that opens the panel; no horizontal scroll.
- [ ] Topic → question → answer works inside the panel by fetch (the 0313 pages as fragments); "Still need help? Ask Havel" focuses the textarea and sets the hidden `topic` and `q`.
- [ ] Enter sends, Shift+Enter breaks a line, a writing bubble appears while waiting, the answer gets focus, the host's text stays in the box after a network error with a Retry button.
- [ ] Without JavaScript every launcher is a link to `/havel` (route test); `/havel` has no panel of its own.
- [ ] Three screenshots in `docs/tasks/screenshots-0324/`, looked at; layout and a11y guards pass, 0 skipped; design lint OK; static version manifest written.

## 8. Stop and ask

As in docs/tasks/TEMPLATE.md section 8, plus: a 0312 or 0313 anchor is missing, `templating.py` has no `templates.env.filters["weekday"]` line, the design lint rejects the two `px` custom properties, or the layout guard flags a page because of the closed dialog (report the selector; never hide the dialog with inline styles).

## 9. Report

Write `docs/tasks/0324-report.md` (600 tokens at most) and set `Status: review`: files changed (`git diff --stat`), each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps left, and one sentence per screenshot.

## Risk list (for the reviewer)

`App/app/static/havel.js` (fetch, swap, focus; no HTML built from server text except `innerHTML` of the fragment, which is the server's own template), `App/app/templates/_havel_panel.html` (included on every host page: must not break pages where `nav` is undefined), `App/app/templates/base.html`, `App/app/routes/havel.py` (nav → page mapping, `q` sanitising), `App/app/static/host2.css` (dialog anchoring on the computer, 92dvh on the phone), `App/app/templating.py` (the import and the global).

## Owner steps

1. Open the pull request and look at the three screenshots in `docs/tasks/screenshots-0324/`: panel bottom-right on the computer, full-width sheet on the phone.
2. On staging (0310 configured): click "Havel (AI)" at the bottom of the left menu, then "Guest link and PIN", then "Where do I find the link and PIN?", then "Still need help? Ask Havel"; type "and where is it on the phone?" and press Enter. A reply arrives within about ten seconds and the counter goes down by one.
3. On the phone: the chat icon is top right next to search; the More tab has "Havel (AI)".
