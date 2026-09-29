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

  // 5. PIN: paint the one real #pin input as six cells. The input sits on
  //    top of the cells, invisible, so focus, typing, paste and one-time-code
  //    autofill all still go to the real field.
  function initPinCells() {
    var input = document.querySelector(".tw .g-pin-input");
    if (!input || input.getAttribute("data-tw-cells")) return;
    input.setAttribute("data-tw-cells", "1");
    var size = parseInt(input.getAttribute("maxlength") || "6", 10);
    var box = document.createElement("div");
    box.className = "tw-pin";
    var cells = [];
    for (var i = 0; i < size; i += 1) {
      var cell = document.createElement("span");
      cell.className = "tw-pin-cell";
      cell.setAttribute("aria-hidden", "true");
      box.appendChild(cell);
      cells.push(cell);
    }
    input.parentNode.insertBefore(box, input);
    box.appendChild(input);
    if (input.getAttribute("aria-invalid") === "true") box.classList.add("is-bad");

    function paint() {
      var digits = input.value.replace(/\D/g, "").slice(0, size);
      if (digits !== input.value) input.value = digits;
      var focused = document.activeElement === input;
      cells.forEach(function (c, k) {
        c.textContent = digits.charAt(k);
        c.classList.toggle("is-filled", k < digits.length);
        c.classList.toggle("is-caret", focused && k === Math.min(digits.length, size - 1));
      });
      box.classList.toggle("is-complete", digits.length === size);
      if (digits.length) box.classList.remove("is-bad");
    }
    ["input", "focus", "blur", "keyup", "change"].forEach(function (name) {
      input.addEventListener(name, paint);
    });
    paint();
  }

  // 6. The check-in rail (built by signature.js) becomes the top tracker.
  //    Its labels are the long step titles; show the short ones instead.
  function initTrackerLabels() {
    var form = document.querySelector("[data-guest-wizard]");
    var list = document.querySelector("[data-checkin-steps]");
    if (!form || !list) return;
    var nationality = form.querySelector('[name="nationality"]');
    function liveSteps() {
      // The same filter signature.js uses: a step can opt out for one nationality.
      return Array.prototype.slice.call(form.querySelectorAll("[data-guest-step]")).filter(function (s) {
        var skip = s.getAttribute("data-guest-step-skip-when");
        return !skip || !nationality || nationality.value !== skip;
      });
    }
    function relabel(event) {
      var steps = event && event.detail && event.detail.steps
        ? Array.prototype.slice.call(event.detail.steps)
        : liveSteps();
      var items = list.querySelectorAll(".g-checkin-step");
      Array.prototype.forEach.call(items, function (item, index) {
        var step = steps[index];
        var short = step && step.getAttribute("data-tw-short");
        var name = item.querySelector("span:not(.sr-only)");
        if (short && name) {
          name.textContent = short;
          item.setAttribute("title", step.getAttribute("data-step-title") || short);
        }
      });
    }
    form.addEventListener("guest-wizard:shown", relabel);
    relabel();
  }

  // 7. Date of birth: Day / Month / Year boxes that write "DD.MM.YYYY" into
  //    the real #birth_date, so signature.js keeps formatting, the read-back
  //    and validation exactly as before.
  function initDobCells() {
    var real = document.getElementById("birth_date");
    if (!real || real.getAttribute("data-tw-cells")) return;
    real.setAttribute("data-tw-cells", "1");
    var names = [
      [real.getAttribute("data-tw-day") || "Day", 2, "DD", "bday-day"],
      [real.getAttribute("data-tw-month") || "Month", 2, "MM", "bday-month"],
      [real.getAttribute("data-tw-year") || "Year", 4, "YYYY", "bday-year"]
    ];
    var group = document.createElement("div");
    group.className = "tw-dob";
    group.setAttribute("role", "group");
    var label = document.querySelector('label[for="birth_date"]');
    if (label) {
      if (!label.id) label.id = "birth_date_label";
      group.setAttribute("aria-labelledby", label.id);
    }
    var boxes = names.map(function (n, k) {
      var wrap = document.createElement("label");
      wrap.className = "tw-dob-part";
      var small = document.createElement("small");
      small.textContent = n[0];
      var box = document.createElement("input");
      box.type = "text";
      box.inputMode = "numeric";
      box.maxLength = n[1];
      box.placeholder = n[2];
      box.autocomplete = n[3];
      box.id = "birth_date_" + ["d", "m", "y"][k];
      if (real.getAttribute("aria-invalid")) {
        box.setAttribute("aria-invalid", "true");
        box.setAttribute("aria-describedby", real.getAttribute("aria-describedby") || "");
        box.className = "bad";
      }
      wrap.appendChild(small);
      wrap.appendChild(box);
      group.appendChild(wrap);
      return box;
    });
    real.parentNode.insertBefore(group, real);
    real.classList.add("tw-vh");
    real.setAttribute("tabindex", "-1");
    real.setAttribute("aria-hidden", "true");

    function split() {
      var m = /^(\d{0,2})\.?(\d{0,2})\.?(\d{0,4})$/.exec(real.value || "");
      boxes[0].value = m ? m[1] : "";
      boxes[1].value = m ? m[2] : "";
      boxes[2].value = m ? m[3] : "";
    }
    function join() {
      var d = boxes[0].value, mo = boxes[1].value, y = boxes[2].value;
      var digits = d + (d.length === 2 ? mo : "") + (d.length === 2 && mo.length === 2 ? y : "");
      real.value = digits;
      real.dispatchEvent(new Event("input", { bubbles: true }));
    }
    function pad(box) {
      if (box.value.length === 1 && box !== boxes[2]) box.value = "0" + box.value;
    }
    boxes.forEach(function (box, k) {
      box.addEventListener("input", function () {
        box.value = box.value.replace(/\D/g, "").slice(0, box.maxLength);
        box.classList.remove("bad");
        join();
        if (box.value.length === box.maxLength && boxes[k + 1]) boxes[k + 1].focus();
      });
      box.addEventListener("blur", function () { pad(box); join(); });
      box.addEventListener("keydown", function (e) {
        if (e.key === "Backspace" && !box.value && boxes[k - 1]) boxes[k - 1].focus();
      });
      box.addEventListener("paste", function (e) {
        var text = ((e.clipboardData || window.clipboardData).getData("text") || "").trim();
        if (/\d{1,4}\D\d{1,2}\D\d{1,4}|\d{8}/.test(text)) {
          e.preventDefault();
          real.value = text;
          real.dispatchEvent(new Event("input", { bubbles: true }));
          split();
        }
      });
    });
    // The wizard focuses the real field when it is invalid; send the guest
    // to the first box that still needs digits instead.
    real.addEventListener("focus", function () {
      var target = boxes.filter(function (b) { return b.value.length < b.maxLength; })[0] || boxes[0];
      target.focus();
    });
    real.addEventListener("invalid", function () {
      boxes.forEach(function (b) { if (b.value.length < b.maxLength) b.classList.add("bad"); });
    });
    split();
  }

  // 8. Country search over the real <select> (nationality, residence country).
  function initCountryCombos() {
    ["nationality", "res_country"].forEach(function (id) {
      var select = document.getElementById(id);
      if (!select || select.getAttribute("data-tw-combo")) return;
      select.setAttribute("data-tw-combo", "1");
      var seen = {};
      var options = [];
      Array.prototype.forEach.call(select.options, function (o) {
        if (!o.value || seen[o.value]) return;
        seen[o.value] = true;
        options.push({ code: o.value, label: o.textContent.trim() });
      });
      function norm(s) {
        return String(s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
      }
      var wrap = document.createElement("div");
      wrap.className = "tw-combo";
      var input = document.createElement("input");
      input.type = "text";
      input.id = id + "_search";
      input.className = select.className;
      input.autocomplete = "off";
      input.setAttribute("role", "combobox");
      input.setAttribute("aria-autocomplete", "list");
      input.setAttribute("aria-expanded", "false");
      input.setAttribute("aria-controls", id + "_list");
      input.placeholder = select.getAttribute("data-tw-placeholder") || "";
      if (select.getAttribute("aria-invalid")) {
        input.setAttribute("aria-invalid", "true");
        input.setAttribute("aria-describedby", select.getAttribute("aria-describedby") || "");
      }
      var list = document.createElement("ul");
      list.id = id + "_list";
      list.className = "tw-combo-list";
      list.setAttribute("role", "listbox");
      list.hidden = true;
      wrap.appendChild(input);
      wrap.appendChild(list);
      select.parentNode.insertBefore(wrap, select);
      select.classList.add("tw-vh");
      select.setAttribute("tabindex", "-1");
      select.setAttribute("aria-hidden", "true");
      var label = document.querySelector('label[for="' + id + '"]');
      if (label) label.setAttribute("for", input.id);

      var active = -1;
      var shown = [];
      function currentLabel() {
        var o = select.options[select.selectedIndex];
        return o && o.value ? o.textContent.trim() : "";
      }
      function sync() { if (document.activeElement !== input) input.value = currentLabel(); }
      function render(query) {
        var q = norm(query);
        shown = options.filter(function (o) {
          return !q || norm(o.label).indexOf(q) !== -1 || norm(o.code).indexOf(q) === 0;
        }).slice(0, 60);
        list.textContent = "";
        if (!shown.length) {
          var none = document.createElement("li");
          none.className = "tw-combo-none";
          none.textContent = select.getAttribute("data-tw-none") || "—";
          list.appendChild(none);
        }
        shown.forEach(function (o, k) {
          var li = document.createElement("li");
          li.id = id + "_opt_" + k;
          li.setAttribute("role", "option");
          li.setAttribute("aria-selected", o.code === select.value ? "true" : "false");
          var code = document.createElement("b");
          code.textContent = o.code;
          li.appendChild(code);
          li.appendChild(document.createTextNode(o.label));
          li.addEventListener("mousedown", function (e) { e.preventDefault(); pick(o); });
          list.appendChild(li);
        });
        active = -1;
        open(true);
      }
      function open(yes) {
        list.hidden = !yes;
        input.setAttribute("aria-expanded", yes ? "true" : "false");
        if (!yes) input.removeAttribute("aria-activedescendant");
      }
      function highlight(k) {
        var items = list.querySelectorAll('[role="option"]');
        if (!items.length) return;
        active = (k + items.length) % items.length;
        Array.prototype.forEach.call(items, function (li, i) { li.classList.toggle("is-active", i === active); });
        input.setAttribute("aria-activedescendant", items[active].id);
        items[active].scrollIntoView({ block: "nearest" });
      }
      function pick(o) {
        select.value = o.code;
        select.dispatchEvent(new Event("change", { bubbles: true }));
        input.value = o.label;
        input.classList.remove("bad");
        input.removeAttribute("aria-invalid");
        open(false);
      }
      input.addEventListener("focus", function () { input.select(); render(""); });
      input.addEventListener("input", function () { render(input.value); });
      input.addEventListener("keydown", function (e) {
        if (e.key === "ArrowDown") { e.preventDefault(); if (list.hidden) render(input.value); highlight(active + 1); }
        else if (e.key === "ArrowUp") { e.preventDefault(); highlight(active - 1); }
        else if (e.key === "Enter" && !list.hidden) {
          e.preventDefault();
          if (shown[active]) pick(shown[active]); else if (shown.length === 1) pick(shown[0]);
        } else if (e.key === "Escape") { open(false); input.value = currentLabel(); }
      });
      input.addEventListener("blur", function () { setTimeout(function () { open(false); input.value = currentLabel(); }, 120); });
      // Wizard validation focuses the hidden select; hand focus to the search.
      select.addEventListener("focus", function () { input.focus(); });
      select.addEventListener("invalid", function () { input.classList.add("bad"); });
      // Other scripts change the select directly (residence copies nationality).
      document.addEventListener("change", function () { setTimeout(sync, 0); });
      sync();
    });
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
    initPinCells();
    initTrackerLabels();
    initDobCells();
    initCountryCombos();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
