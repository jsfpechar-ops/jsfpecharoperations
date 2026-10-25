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
  // 0373: the corner button is hidden while the panel is open; the opener gets focus on close.
  var opener = null;
  function fab() { return document.querySelector("[data-havel-fab]"); }
  function hideFab() { var f = fab(); if (f) f.hidden = true; }
  // 0391: the box exists only once a host has opened it ("Other topic", "Didn't help?").
  function composerOpen() { var f = form(); return !!(f && !f.hidden); }
  function openComposer() { var f = form(); if (f) { f.hidden = false; f.removeAttribute("data-havel-locked"); } }
  function focusPanel() {
    if (PHONE.matches || !composerOpen()) {
      var h = root.querySelector("#havel-title");
      if (h) h.focus({ preventScroll: true });
    } else {
      var ta = textarea();
      if (ta) ta.focus();
    }
  }

  // 0374: the chat follows the host across pages. It lives in this tab's sessionStorage only;
  // every access is wrapped, so a throwing or full storage just means no restore.
  var KEY = "ubyhost.havel.chat";
  var TWELVE_HOURS = 43200000;
  function owner() { return root.getAttribute("data-havel-owner") || ""; }
  function loadChat() {
    try {
      var s = JSON.parse(sessionStorage.getItem(KEY) || "null");
      if (s && s.owner === owner()) return s;
      sessionStorage.removeItem(KEY);
    } catch (e) {}
    return null;
  }
  function clear() { try { sessionStorage.removeItem(KEY); } catch (e) {} }
  function formValue(sel, key, prev) {
    var el = root.querySelector(sel);
    return el ? el.value : (prev[key] || "");
  }
  function save(extra) {
    var t = thread();
    if (!t) return;
    try {
      var prev = JSON.parse(sessionStorage.getItem(KEY) || "null");
      if (!prev || prev.owner !== owner()) prev = {};
      var copy = t.cloneNode(true);
      copy.querySelectorAll("[data-havel-writing]").forEach(function (n) { n.remove(); });
      copy.querySelectorAll("[data-havel-retry]").forEach(function (b) { var m = b.closest(".havel-msg"); if (m) m.remove(); });
      var rec = {
        owner: owner(), saved: Date.now(), html: copy.innerHTML,
        history: formValue("[data-havel-history]", "history", prev),
        sig: formValue("[data-havel-sig]", "sig", prev),
        topic: formValue("[data-havel-topic]", "topic", prev),
        q: formValue("[data-havel-q]", "q", prev),
        open: panel ? panel.open : false,
        unread: prev.unread === true,
        composer: composerOpen() || (!form() && prev.composer === true)
      };
      Object.keys(extra || {}).forEach(function (k) { rec[k] = extra[k]; });
      sessionStorage.setItem(KEY, JSON.stringify(rec));
    } catch (e) {}
  }
  function fill(s) {
    [["[data-havel-history]", s.history], ["[data-havel-sig]", s.sig], ["[data-havel-topic]", s.topic], ["[data-havel-q]", s.q]].forEach(function (p) {
      var el = root.querySelector(p[0]);
      if (el && typeof p[1] === "string") el.value = p[1];
    });
    save();
    scrollDown();
  }
  function restore() {
    var s = loadChat();
    if (!s || !s.html) return;
    if (!(Date.now() - s.saved < TWELVE_HOURS)) { clear(); return; }
    // A non-JS post on /havel rendered its own chat: the page wins.
    var have = root.querySelector("[data-havel-history]");
    if (have && have.value && have.value !== s.history) { save(); return; }
    var t = thread();
    if (!t) return;
    // The composer fragment can replace the thread (swap with items), so the stored chat is
    // put back after the composer has loaded, never before.
    var apply = function () {
      // 0395: a saved start screen is never newer than the server's (topics change per page and per deploy).
      if (s.html.indexOf("havel-msg-host") !== -1) t.innerHTML = s.html;
      if (s.composer) openComposer();
      fill(s);
      if (!panel || typeof panel.show !== "function") return;
      if (s.open) { panel.show(); hideFab(); scrollDown(); }
      else if (s.unread) { var fb = fab(); if (fb) fb.setAttribute("data-unread", ""); }
    };
    if (panel) ensureForm(apply); else apply();
  }
  function onOpen() {
    var fb = fab();
    if (fb) fb.removeAttribute("data-unread");
    save({ open: true, unread: false });
    scrollDown();
  }

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
      if (!replace) t.querySelectorAll("[data-havel-next]").forEach(function (n) { n.remove(); });
      if (old && !replace) old.remove();
      if (!replace && t.querySelector("[data-havel-greeting]")) items.querySelectorAll("[data-havel-greeting]").forEach(function (g) { g.remove(); });
      while (items.firstChild) t.appendChild(items.firstChild);
    }
    var wrap = root.querySelector("[data-havel-form-wrap]");
    if (formWrap && wrap) wrap.innerHTML = formWrap.innerHTML;
    setDevice();
    bindCounter();
    save();
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
    if (!t) return null;
    var topics = t.querySelector("[data-havel-topics]");
    if (topics) topics.remove();
    var el = document.createElement("div");
    el.className = "havel-msg havel-msg-host";
    el.innerHTML = '<div class="havel-bubble"><p></p></div>';
    el.querySelector("p").textContent = text;
    t.appendChild(el);
    return el;
  }

  function send(extra) {
    var f = form();
    if (!f) return;
    var ta = textarea();
    var text = ta ? ta.value.trim() : "";
    if (!extra && !text) return;
    var data = new FormData(f);
    if (extra) Object.keys(extra).forEach(function (k) { data.set(k, extra[k]); });
    var echoed = extra ? null : echo(text);
    if (!extra && ta) { ta.value = ""; ta.dispatchEvent(new Event("input")); }
    writing(true);
    fetch(f.getAttribute("action") || "/havel", {
      method: "POST", body: data, credentials: "same-origin",
      headers: { "X-Havel": "1", "Accept": "text/html" }
    }).then(function (res) {
      if (!res.ok) throw new Error(String(res.status));
      return res.text();
    }).then(function (html) {
      writing(false);
      if (echoed) echoed.remove();
      swap(html, extra && extra.reset ? "replace" : "append");
      // 0374: a reply that arrives while the panel is closed shows the unread dot.
      if (panel && !panel.open) { save({ unread: true }); var fb = fab(); if (fb) fb.setAttribute("data-unread", ""); }
      focusAnswer();
    }).catch(function () {
      writing(false);
      if (echoed) echoed.remove();
      showError(text);
      save();
    });
  }

  // 0391: topic links keep the hosting page and return_to from the panel's data-src.
  function withPanelContext(url) {
    if (!panel) return url;
    var src = new URL(panel.getAttribute("data-src") || "", location.origin);
    var u = new URL(url, location.origin);
    if (u.searchParams.has("page")) return url;
    ["page", "return_to"].forEach(function (k) {
      if (!u.searchParams.has(k) && src.searchParams.has(k)) u.searchParams.set(k, src.searchParams.get(k));
    });
    return u.pathname + u.search;
  }
  function load(url, mode) {
    url = withPanelContext(url);
    fetch(url, { credentials: "same-origin", headers: { "X-Havel": "1", "Accept": "text/html" } })
      .then(function (res) { return res.ok ? res.text() : Promise.reject(new Error(String(res.status))); })
      .then(function (html) {
        swap(html, mode || "replace");
        var t = thread();
        // 0391: an ask link opens the box and puts the cursor in it.
        if (new URL(url, location.origin).searchParams.get("ask") === "1" && composerOpen()) {
          var ta = textarea();
          if (ta) ta.focus();
          scrollDown();
          return;
        }
        var answer = root.querySelector(".havel-answer");
        if (answer) answer.focus({ preventScroll: true });
        if (t) t.scrollTop = 0;
      })
      .catch(function () { window.location.href = url; });
  }

  // 0324: the panel's composer is fetched on first open; topics are already in the page.
  function ensureForm(done) {
    if (!panel || form()) { if (done) done(); return; }
    var url = panel.getAttribute("data-src");
    fetch(url, { credentials: "same-origin", headers: { "X-Havel": "1", "Accept": "text/html" } })
      .then(function (res) { return res.ok ? res.text() : Promise.reject(new Error(String(res.status))); })
      .then(function (html) { if (!form()) swap(html, "replace"); if (done) done(); })
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
    (ta.closest(".havel-input") || ta).insertAdjacentElement("afterend", counter);
    ta.addEventListener("input", function () {
      var n = ta.value.length;
      counter.hidden = n < max - 100;
      counter.textContent = n + " / " + max;
    });
    function grow() { ta.style.height = "auto"; ta.style.height = Math.min(ta.scrollHeight, 132) + "px"; }
    ta.addEventListener("input", grow);
    ta.addEventListener("keydown", function (event) {
      if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
        event.preventDefault();
        send();
      }
    });
  }

  root.addEventListener("submit", function (event) {
    var nf = event.target.closest ? event.target.closest("[data-havel-next]") : null;
    if (nf) {
      event.preventDefault();
      var picked = event.submitter && event.submitter.value;
      if (!picked) return;
      nf.remove();
      echo(picked);
      send({ message: picked });
      return;
    }
    var f = event.target.closest ? event.target.closest("[data-havel-form]") : null;
    if (!f) return;
    event.preventDefault();
    var submitter = event.submitter;
    if (submitter && submitter.name === "reset") { clear(); send({ reset: "1", message: "" }); return; }
    send();
  });

  root.addEventListener("click", function (event) {
    var link = event.target.closest ? event.target.closest("[data-havel-topic-link]") : null;
    if (link) { event.preventDefault(); load(link.getAttribute("href"), "replace"); return; }
    var cancel = event.target.closest ? event.target.closest("[data-havel-cancel]") : null;
    if (cancel) { var card = cancel.closest(".havel-card"); if (card) card.remove(); var ta = textarea(); if (ta) ta.focus(); return; }
    var retry = event.target.closest ? event.target.closest("[data-havel-retry]") : null;
    if (retry) { retry.closest(".havel-msg").remove(); send(); }
  });

  document.addEventListener("click", function (event) {
    var launcher = event.target.closest ? event.target.closest('[data-sheet-open="havel-sheet"]') : null;
    if (launcher) {
      opener = launcher;
      ensureForm(function () { hideFab(); focusPanel(); });
    }
    var more = event.target.closest ? event.target.closest("[data-havel-more]") : null;
    if (!more || !panel || typeof panel.show !== "function") return;
    event.preventDefault();
    opener = more;
    var sheet = document.getElementById("more-sheet");
    if (sheet && sheet.open) sheet.close();
    if (!panel.open) panel.show();
    ensureForm(function () { hideFab(); focusPanel(); });
  });

  if (panel) {
    panel.addEventListener("close", function () {
      save({ open: false });
      var f = fab();
      if (f) f.hidden = false;
      var back = opener;
      opener = null;
      // getClientRects, not offsetParent: the tab bar and the corner button are position: fixed.
      if (back && document.body.contains(back) && back.getClientRects().length > 0) back.focus();
      else if (f) f.focus();
    });
    // For 0322 (command palette): open with a prefilled question.
    window.UbyHavel = { open: function (text) {
      if (!panel.open) panel.show();
      ensureForm(function () {
        hideFab();
        openComposer();
        var ta = textarea();
        if (ta) { if (text) ta.value = text; ta.focus(); ta.dispatchEvent(new Event("input")); }
      });
    } };
  }

  // 0374: opening the panel saves it as open; the stored chat is restored; sign-out clears it.
  if (panel && window.MutationObserver) {
    new MutationObserver(function () { if (panel.open) onOpen(); }).observe(panel, { attributes: true, attributeFilter: ["open"] });
  }
  restore();
  document.addEventListener("submit", function (event) {
    if (event.target && event.target.matches && event.target.matches('form[action="/logout"]')) clear();
  });
  setDevice();
  bindCounter();
  PHONE.addEventListener("change", setDevice);
})();
