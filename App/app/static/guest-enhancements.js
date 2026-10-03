// Arrival-lane guest UX: party stepper, country search, PIN cells.
// Progressive enhancement — forms work with this file missing.
(function () {
  "use strict";

  function initSteppers() {
    var wraps = document.querySelectorAll("[data-guest-stepper]");
    Array.prototype.forEach.call(wraps, function (wrap) {
      var input = wrap.querySelector('input[type="number"]');
      if (!input || wrap.querySelector(".g-stepper")) return;
      var min = parseInt(input.getAttribute("min") || "1", 10);
      var max = parseInt(input.getAttribute("max") || "60", 10);
      var box = document.createElement("div");
      box.className = "g-stepper";

      function button(label, delta, text) {
        var b = document.createElement("button");
        b.type = "button";
        b.className = "g-step-btn";
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

  function initPinCells() {
    var input = document.querySelector(".g-pin-input");
    if (!input || input.getAttribute("data-guest-pin-cells")) return;
    input.setAttribute("data-guest-pin-cells", "1");
    var size = parseInt(input.getAttribute("maxlength") || "6", 10);
    var box = document.createElement("div");
    box.className = "g-pin-cells";
    var cells = [];
    for (var i = 0; i < size; i += 1) {
      var cell = document.createElement("span");
      cell.className = "g-pin-cell";
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

  function initCountryCombos() {
    ["nationality", "res_country"].forEach(function (id) {
      var select = document.getElementById(id);
      if (!select || select.getAttribute("data-guest-combo")) return;
      select.setAttribute("data-guest-combo", "1");
      var seen = {};
      var options = [];
      Array.prototype.forEach.call(select.options, function (o) {
        if (!o.value || seen[o.value]) return;
        seen[o.value] = true;
        options.push({ code: o.value, label: o.textContent.trim() });
      });
      function norm(s) {
        return String(s || "").toLowerCase().normalize("NFD")
          .replace(/[\u0300-\u036f]/g, "").replace(/[^a-z0-9]+/g, "");
      }
      var wrap = document.createElement("div");
      wrap.className = "g-combo";
      var required = select.getAttribute("data-guest-required") || "";
      var input = document.createElement("input");
      input.type = "text";
      input.id = id + "_search";
      input.className = select.className;
      input.autocomplete = "off";
      input.setAttribute("role", "combobox");
      input.setAttribute("aria-autocomplete", "list");
      input.setAttribute("aria-expanded", "false");
      input.setAttribute("aria-controls", id + "_list");
      input.placeholder = select.getAttribute("data-guest-placeholder") || "";
      if (select.getAttribute("aria-invalid")) {
        input.setAttribute("aria-invalid", "true");
        input.setAttribute("aria-describedby", select.getAttribute("aria-describedby") || "");
      }
      var list = document.createElement("ul");
      list.id = id + "_list";
      list.className = "g-combo-list";
      list.setAttribute("role", "listbox");
      list.hidden = true;
      wrap.appendChild(input);
      wrap.appendChild(list);
      var error = document.createElement("p");
      error.className = "hint g-combo-error";
      error.id = id + "_error";
      error.setAttribute("role", "alert");
      error.hidden = true;
      wrap.appendChild(error);
      select.parentNode.insertBefore(wrap, select);
      select.classList.add("g-vh");
      select.setAttribute("tabindex", "-1");
      select.setAttribute("aria-hidden", "true");
      var label = document.querySelector('label[for="' + id + '"]');
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
          none.className = "g-combo-none";
          none.textContent = select.getAttribute("data-guest-none") || "—";
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
      select.addEventListener("focus", function () { input.focus(); });
      select.addEventListener("invalid", function () {
        input.classList.add("bad");
        input.setAttribute("aria-invalid", "true");
        if (required) {
          error.textContent = required;
          error.hidden = false;
          input.setAttribute("aria-describedby", error.id);
        }
      });
      document.addEventListener("change", function () { setTimeout(sync, 0); });
      sync();
    });
  }

  function start() {
    initSteppers();
    initPinCells();
    initCountryCombos();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
