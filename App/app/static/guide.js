/* 0828: /guide search and topic folding. Without JavaScript the topics are plain closed <details>
   and the search field stays hidden. */
(function () {
  "use strict";

  var DEBOUNCE_MS = 100;

  function fold(text) {
    return String(text || "")
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "")
      .toLowerCase()
      .replace(/\s+/g, " ")
      .trim();
  }

  function topics() {
    return Array.prototype.slice.call(document.querySelectorAll(".guide-topic"));
  }

  function topicFor(el) {
    if (!el) return null;
    if (el.classList && el.classList.contains("guide-topic")) return el;
    return el.closest ? el.closest(".guide-topic") : null;
  }

  function openForHash() {
    var id = "";
    try {
      id = decodeURIComponent(window.location.hash.slice(1));
    } catch (e) {
      return;
    }
    if (!id) return;
    var target = document.getElementById(id);
    var topic = topicFor(target);
    if (!topic) return;
    topic.hidden = false;
    topic.open = true;
    target.scrollIntoView({ block: "start" });
  }

  function applySearch(input) {
    var q = fold(input.value);
    var empty = document.querySelector(".guide-search-empty");
    var shown = 0;
    topics().forEach(function (topic) {
      if (!q) {
        topic.hidden = false;
        topic.open = false;
        shown += 1;
        return;
      }
      var match = fold(topic.textContent).indexOf(q) !== -1;
      topic.hidden = !match;
      topic.open = match;
      if (match) shown += 1;
    });
    if (empty) empty.hidden = !(q && shown === 0);
  }

  function bindSearch() {
    var input = document.getElementById("guide-search");
    if (!input || input.dataset.guideBound === "1") return;
    input.dataset.guideBound = "1";
    input.hidden = false;
    var timer = null;
    input.addEventListener("input", function () {
      window.clearTimeout(timer);
      timer = window.setTimeout(function () {
        applySearch(input);
      }, DEBOUNCE_MS);
    });
    input.addEventListener("keydown", function (event) {
      if (event.key !== "Escape" || !input.value) return;
      event.preventDefault();
      window.clearTimeout(timer);
      input.value = "";
      applySearch(input);
    });
  }

  function boot() {
    bindSearch();
    openForHash();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }

  if (!window.__guideListeners) {
    window.__guideListeners = true;
    window.addEventListener("hashchange", openForHash);
    document.addEventListener("turbo:load", boot);
    document.addEventListener("click", function (event) {
      var link = event.target && event.target.closest
        ? event.target.closest('.guide-nav a[href^="#"]')
        : null;
      if (link) window.setTimeout(openForHash, 0);
    });
  }
})();
