// Ticket Wallet helpers for the guest pages. Progressive enhancement only:
// every form works exactly the same with this file missing.
(function () {
  "use strict";

  // 1. Party size: wrap the number input in a - / + stepper. The input keeps
  //    its name, min, max and required, so the server sees nothing new.
  function initSteppers() {
    var wraps = document.querySelectorAll("[data-tw-stepper]");
    Array.prototype.forEach.call(wraps, function (wrap) {
      var input = wrap.querySelector('input[type="number"]');
      if (!input || wrap.querySelector(".tw-stepper")) return;
      var min = parseInt(input.getAttribute("min") || "1", 10);
      var max = parseInt(input.getAttribute("max") || "60", 10);
      var box = document.createElement("div");
      box.className = "tw-stepper";

      function button(label, delta, text) {
        var b = document.createElement("button");
        b.type = "button";
        b.className = "tw-step-btn";
        b.setAttribute("aria-label", label);
        b.textContent = text;
        b.addEventListener("click", function () {
          var now = parseInt(input.value, 10);
          if (isNaN(now)) now = delta > 0 ? min - 1 : min + 1;
          var next = Math.min(max, Math.max(min, now + delta));
          input.value = String(next);
          input.dispatchEvent(new Event("input", { bubbles: true }));
          input.dispatchEvent(new Event("change", { bubbles: true }));
        });
        return b;
      }

      input.parentNode.insertBefore(box, input);
      box.appendChild(button(wrap.getAttribute("data-less-label") || "-", -1, "−"));
      box.appendChild(input);
      box.appendChild(button(wrap.getAttribute("data-more-label") || "+", 1, "+"));
    });
  }

  // 2. The form wizard already moves its own bar (data-wizard-bar). Mirror
  //    it into the app bar so the top line keeps growing through the form.
  function initProgressMirror() {
    var top = document.querySelector("[data-tw-progress]");
    var bar = document.querySelector("[data-wizard-bar]");
    if (!top || !bar || !window.MutationObserver) return;
    var base = parseFloat(top.getAttribute("data-tw-base") || "50");
    var span = parseFloat(top.getAttribute("data-tw-span") || "42");
    function sync() {
      var pct = parseFloat(bar.style.width) || 0;
      top.style.width = Math.min(100, base + (span * pct) / 100) + "%";
    }
    new MutationObserver(sync).observe(bar, { attributes: true, attributeFilter: ["style"] });
    sync();
  }

  // 3. Show a spinner on the button that was pressed while the page posts.
  function initSending() {
    var forms = document.querySelectorAll(".tw form");
    Array.prototype.forEach.call(forms, function (form) {
      form.addEventListener("submit", function (ev) {
        if (ev.defaultPrevented) return;
        form.classList.add("is-sending");
      });
    });
  }

  // 4. The last form step ends in the Submit button plus the wizard's own
  //    Back button. Put both in one stub so the step has one tear-off line.
  function initSubmitStub() {
    var steps = document.querySelectorAll("[data-guest-step]");
    if (!steps.length) return;
    var last = steps[steps.length - 1];
    var submit = last.querySelector(':scope > .g-btn[type="submit"]');
    var nav = last.querySelector(":scope > .g-wizard-nav");
    if (submit && nav) nav.appendChild(submit);
  }

  // A page restored from the back/forward cache must not keep spinning.
  window.addEventListener("pageshow", function () {
    Array.prototype.forEach.call(document.querySelectorAll("form.is-sending"), function (f) {
      f.classList.remove("is-sending");
    });
  });

  function start() {
    initSteppers();
    initProgressMirror();
    initSending();
    initSubmitStub();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
