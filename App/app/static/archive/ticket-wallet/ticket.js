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
    function relabel(event) {
      // signature.js passes the wizard's filtered step list with the event and
      // rebuilds the rail from it. Its first paint happens before this listener
      // exists and uses every step, so mirror that rather than filtering here:
      // one filter, owned by signature.js, keeps the rail and its labels aligned.
      var steps = event && event.detail && event.detail.steps
        ? Array.prototype.slice.call(event.detail.steps)
        : Array.prototype.slice.call(form.querySelectorAll("[data-guest-step]"));
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
      // No second row of labels above the boxes: "Day / Month / Year" pushed
      // the boxes below every other field, so a date of birth beside the
      // nationality sat a line lower. The placeholder shows the format and
      // the accessible name says which part it is.
      var wrap = document.createElement("span");
      wrap.className = "tw-dob-part";
      var box = document.createElement("input");
      box.setAttribute("aria-label", n[0]);
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
    function clampPart(box, part) {
      if (!box.value || box.value.length < 2) return;
      var n = parseInt(box.value, 10);
      if (part === "month" && box.value !== "00" && n > 12) box.value = "12";
      if (part === "day" && box.value !== "00" && n > 31) box.value = "31";
    }
    boxes.forEach(function (box, k) {
      var part = k === 0 ? "day" : k === 1 ? "month" : "year";
      box.addEventListener("input", function () {
        box.value = box.value.replace(/\D/g, "").slice(0, box.maxLength);
        if (part === "month" && box.value.length === 2) {
          var m = parseInt(box.value, 10);
          if (box.value !== "00" && m > 12) box.value = "12";
        }
        if (part === "day" && box.value.length === 2) {
          var d = parseInt(box.value, 10);
          if (box.value !== "00" && d > 31) box.value = "31";
        }
        box.classList.remove("bad");
        join();
        if (box.value.length === box.maxLength && boxes[k + 1]) boxes[k + 1].focus();
      });
      box.addEventListener("blur", function () {
        pad(box);
        clampPart(box, part);
        join();
      });
      box.addEventListener("keydown", function (e) {
        if (e.key === "Backspace" && !box.value && boxes[k - 1]) boxes[k - 1].focus();
      });
      box.addEventListener("paste", function (e) {
        var text = ((e.clipboardData || window.clipboardData).getData("text") || "").trim();
        // Read the parts in the order they were written, then pad each one.
        // Passing the raw text through would let signature.js regroup the
        // digits, so an unpadded "14.3.1988" would become 14.31.988.
        var groups = text.split(/\D+/).filter(Boolean);
        var parts = null;
        if (groups.length === 3) {
          parts = groups[0].length === 4
            ? [groups[2], groups[1], groups[0]]
            : [groups[0], groups[1], groups[2]];
        } else if (groups.length === 1 && groups[0].length === 8) {
          parts = [groups[0].slice(0, 2), groups[0].slice(2, 4), groups[0].slice(4, 8)];
        }
        if (!parts || parts[2].length !== 4 || parts[0].length > 2 || parts[1].length > 2) return;
        var moNum = parseInt(parts[1], 10);
        if (parts[1] !== "00" && moNum > 12) parts[1] = "12";
        var dayNum = parseInt(parts[0], 10);
        if (parts[0] !== "00" && dayNum > 31) parts[0] = "31";
        e.preventDefault();
        real.value = parts[0].padStart(2, "0") + parts[1].padStart(2, "0") + parts[2];
        real.dispatchEvent(new Event("input", { bubbles: true }));
        split();
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
        // Fold accents and drop punctuation, so "guinea bissau" matches
        // "Guinea-Bissau" and a curly apostrophe matches a straight one.
        return String(s || "").toLowerCase().normalize("NFD")
          .replace(/[\u0300-\u036f]/g, "").replace(/[^a-z0-9]+/g, "");
      }
      var wrap = document.createElement("div");
      wrap.className = "tw-combo";
      var required = select.getAttribute("data-tw-required") || "";
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
      // The real select is clipped and aria-hidden, so its native message has
      // nowhere to show. Give the visible control a message of its own.
      var error = document.createElement("p");
      error.className = "hint tw-combo-error";
      error.id = id + "_error";
      error.setAttribute("role", "alert");
      error.hidden = true;
      wrap.appendChild(error);
      select.parentNode.insertBefore(wrap, select);
      select.classList.add("tw-vh");
      select.setAttribute("tabindex", "-1");
      select.setAttribute("aria-hidden", "true");
      var label = document.querySelector('label[for="' + id + '"]');
      // Keep the label pointing at the real <select>: signature.js builds the
      // review rows by looking it up as label[for="<control id>"]. Clicking the
      // label focuses the select, which forwards focus to the search input.
      if (label) {
        if (!label.id) label.id = id + "_label";
        input.setAttribute("aria-labelledby", label.id);
      }

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
        active = k < 0 ? items.length - 1 : k % items.length;
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
        error.hidden = true;
        open(false);
      }
      input.addEventListener("focus", function () { input.select(); render(""); });
      input.addEventListener("input", function () {
        input.removeAttribute("aria-invalid");
        error.hidden = true;
        if (input.getAttribute("aria-describedby") === error.id) input.removeAttribute("aria-describedby");
        render(input.value);
      });
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
      select.addEventListener("invalid", function () {
        input.classList.add("bad");
        // Mark the visible control as well: the real select is clipped and
        // aria-hidden, so a red border alone is only a colour signal.
        input.setAttribute("aria-invalid", "true");
        if (required) {
          error.textContent = required;
          error.hidden = false;
          input.setAttribute("aria-describedby", error.id);
        }
      });
      // Other scripts change the select directly (residence copies nationality).
      document.addEventListener("change", function () { setTimeout(sync, 0); });
      sync();
    });
  }

  // 9. Purpose: the four common codes as chips over the real <select>.
  function initPurposeChips() {
    var select = document.getElementById("purpose");
    if (!select || select.getAttribute("data-tw-chips")) return;
    select.setAttribute("data-tw-chips", "1");
    var common = (select.getAttribute("data-tw-common") || "10,01,03,11").split(",");
    var group = document.createElement("div");
    group.className = "tw-chips";
    group.setAttribute("role", "group");
    var label = document.querySelector('label[for="purpose"]');
    if (label) {
      if (!label.id) label.id = "purpose_label";
      group.setAttribute("aria-labelledby", label.id);
    }
    var buttons = [];
    common.forEach(function (code) {
      var o = select.querySelector('option[value="' + code + '"]');
      if (!o) return;
      var b = document.createElement("button");
      b.type = "button";
      b.className = "tw-chip";
      b.textContent = o.textContent.trim();
      b.setAttribute("data-code", code);
      b.addEventListener("click", function () {
        select.value = code;
        select.dispatchEvent(new Event("change", { bubbles: true }));
        paint(false);
      });
      group.appendChild(b);
      buttons.push(b);
    });
    var other = document.createElement("button");
    other.type = "button";
    other.className = "tw-chip is-other";
    other.textContent = select.getAttribute("data-tw-other") || "Other…";
    other.addEventListener("click", function () { paint(true); select.focus(); });
    group.appendChild(other);
    select.parentNode.insertBefore(group, select);

    function paint(showSelect) {
      var inCommon = common.indexOf(select.value) !== -1;
      var openSelect = showSelect || !inCommon;
      buttons.forEach(function (b) {
        b.setAttribute("aria-pressed", !openSelect && b.getAttribute("data-code") === select.value ? "true" : "false");
      });
      other.setAttribute("aria-pressed", openSelect ? "true" : "false");
      select.classList.toggle("tw-vh", !openSelect);
      if (openSelect) select.removeAttribute("tabindex"); else select.setAttribute("tabindex", "-1");
    }
    select.addEventListener("change", function () { paint(common.indexOf(select.value) === -1); });
    paint(false);
  }

  // 10. Signature pad: mirror "has a signature" onto the pad for styling.
  function initSignState() {
    var pad = document.querySelector(".tw .g-sign");
    var hidden = document.getElementById("signature");
    var canvas = document.getElementById("sig-canvas");
    if (!pad || !hidden || !canvas) return;
    function sync() { pad.classList.toggle("is-signed", hidden.value.indexOf("data:image/") === 0); }
    ["mouseup", "mouseleave", "touchend", "touchcancel", "pointerup", "keyup"].forEach(function (name) {
      canvas.addEventListener(name, function () { setTimeout(sync, 30); });
    });
    var clear = document.getElementById("sig-clear");
    if (clear) clear.addEventListener("click", function () { setTimeout(sync, 30); });
    sync();
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
    initPurposeChips();
    initSignState();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
