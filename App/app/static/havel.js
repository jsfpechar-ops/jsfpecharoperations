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
  function focusPanel() {
    if (PHONE.matches) {
      var h = root.querySelector("#havel-title");
      if (h) h.focus({ preventScroll: true });
    } else {
      var ta = textarea();
      if (ta) ta.focus();
    }
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
      focusAnswer();
    }).catch(function () {
      writing(false);
      if (echoed) echoed.remove();
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
        var ta = textarea();
        if (ta) { if (text) ta.value = text; ta.focus(); ta.dispatchEvent(new Event("input")); }
      });
    } };
  }

  setDevice();
  bindCounter();
  PHONE.addEventListener("change", setDevice);
})();
