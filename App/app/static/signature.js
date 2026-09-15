// Signature pad and small helpers for the guest form.
(function () {
  "use strict";

  function initSignature() {
    var canvas = document.getElementById("sig-canvas");
    if (!canvas) return;
    var hidden = document.getElementById("signature");
    var clearBtn = document.getElementById("sig-clear");
    var status = document.getElementById("sig-status");
    var ctx = canvas.getContext("2d");
    var drawing = false;
    var dirty = false;
    var ratio = window.devicePixelRatio || 1;

    function resize() {
      // Keep any existing drawing when the viewport changes.
      var snapshot = dirty ? canvas.toDataURL("image/png") : null;
      var rect = canvas.getBoundingClientRect();
      canvas.width = Math.round(rect.width * ratio);
      canvas.height = Math.round(rect.height * ratio);
      ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
      ctx.lineWidth = 2.2;
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
      ctx.strokeStyle = getComputedStyle(document.documentElement).getPropertyValue("--ink").trim() || "#20201e";
      if (snapshot) {
        var img = new Image();
        img.onload = function () { ctx.drawImage(img, 0, 0, rect.width, rect.height); };
        img.src = snapshot;
      }
    }

    function pos(event) {
      var rect = canvas.getBoundingClientRect();
      var point = event.touches ? event.touches[0] : event;
      return { x: point.clientX - rect.left, y: point.clientY - rect.top };
    }

    function start(event) {
      event.preventDefault();
      drawing = true;
      ctx.strokeStyle = getComputedStyle(document.documentElement).getPropertyValue("--ink").trim() || "#20201e";
      var p = pos(event);
      ctx.beginPath();
      ctx.moveTo(p.x, p.y);
    }

    function move(event) {
      if (!drawing) return;
      event.preventDefault();
      var p = pos(event);
      ctx.lineTo(p.x, p.y);
      ctx.stroke();
      dirty = true;
    }

    function end() {
      if (!drawing) return;
      drawing = false;
      if (dirty) {
        hidden.value = canvas.toDataURL("image/png");
        if (status) status.textContent = "";
      }
    }

    resize();
    window.addEventListener("resize", resize);
    ["mousedown", "touchstart"].forEach(function (e) { canvas.addEventListener(e, start, { passive: false }); });
    ["mousemove", "touchmove"].forEach(function (e) { canvas.addEventListener(e, move, { passive: false }); });
    ["mouseup", "mouseleave", "touchend", "touchcancel"].forEach(function (e) { canvas.addEventListener(e, end); });

    // A failed submit re-renders the form with the signature intact. Paint it
    // back so the guest does not think their signature was lost and re-sign.
    if (hidden.value && hidden.value.indexOf("data:image/") === 0) {
      dirty = true;
      var kept = new Image();
      kept.onload = function () {
        var rect = canvas.getBoundingClientRect();
        ctx.drawImage(kept, 0, 0, rect.width, rect.height);
      };
      kept.src = hidden.value;
      if (status) status.textContent = status.getAttribute("data-kept") || "";
    }

    if (clearBtn) {
      clearBtn.addEventListener("click", function () {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        hidden.value = "";
        dirty = false;
        if (status) status.textContent = "";
      });
    }

    var form = canvas.closest("form");
    if (form) {
      form.addEventListener("submit", function (event) {
        if (!hidden.value) {
          event.preventDefault();
          if (status) status.textContent = status.getAttribute("data-missing") || "";
          canvas.scrollIntoView({ behavior: "smooth", block: "center" });
          canvas.focus();
        }
      });
    }
  }

  function initCopy() {
    document.querySelectorAll("[data-copy]").forEach(function (button) {
      button.addEventListener("click", function () {
        var target = document.getElementById(button.getAttribute("data-copy"));
        if (!target) return;
        target.select();
        try {
          navigator.clipboard ? navigator.clipboard.writeText(target.value) : document.execCommand("copy");
          var original = button.textContent;
          button.textContent = button.getAttribute("data-copied-label") || original;
          setTimeout(function () { button.textContent = original; }, 1400);
        } catch (e) { /* the field is selected, the user can copy manually */ }
      });
    });
  }

  function initBirthDate() {
    var input = document.getElementById("birth_date");
    if (!input) return;

    function formatDigits(digits) {
      var out = digits.slice(0, 2);
      if (digits.length > 2) out += "/" + digits.slice(2, 4);
      if (digits.length > 4) out += "/" + digits.slice(4, 8);
      return out;
    }

    function apply(value) {
      var digits = String(value || "").replace(/\D/g, "").slice(0, 8);
      var formatted = formatDigits(digits);
      if (input.value !== formatted) input.value = formatted;
    }

    input.addEventListener("input", function () { apply(input.value); });
    input.addEventListener("paste", function (event) {
      event.preventDefault();
      var text = (event.clipboardData || window.clipboardData).getData("text");
      apply(text);
    });
    apply(input.value);
  }

  function initChildToggle() {
    var toggle = document.getElementById("child_in_passport");
    if (!toggle) return;
    var docWrap = document.getElementById("doc-wrap");
    var parentWrap = document.getElementById("parent-doc-wrap");
    function apply() {
      if (docWrap) docWrap.style.display = toggle.checked ? "none" : "";
      if (parentWrap) parentWrap.style.display = toggle.checked ? "" : "none";
      var docInput = document.querySelector('[name="doc_number"]');
      if (docInput) docInput.required = !toggle.checked;
    }
    toggle.addEventListener("change", apply);
    apply();
  }

  function initResidenceCountry() {
    var nationality = document.getElementById("nationality");
    var resCountry = document.getElementById("res_country");
    if (!nationality || !resCountry) return;
    nationality.addEventListener("change", function () {
      if (!resCountry.value && nationality.value) resCountry.value = nationality.value;
    });
  }

  function initMrzAssist() {
    var assist = document.querySelector("[data-mrz-assist]");
    if (!assist) return;
    var line1 = document.getElementById("mrz_line_1");
    var line2 = document.getElementById("mrz_line_2");
    var button = assist.querySelector("[data-mrz-fill]");
    var status = assist.querySelector("[data-mrz-status]");
    if (!line1 || !line2 || !button || !status) return;

    function clean(value) {
      return String(value || "").toUpperCase().replace(/\s/g, "").replace(/[^A-Z0-9<]/g, "");
    }

    function setValue(id, value) {
      var field = document.getElementById(id);
      if (field && value) field.value = value;
      return field;
    }

    button.addEventListener("click", function () {
      var first = clean(line1.value);
      var second = clean(line2.value);
      var names = first.slice(5).split("<<");
      if (first.length < 20 || second.length < 28 || names.length < 2) {
        status.textContent = status.getAttribute("data-failed") || "";
        status.className = "err";
        return;
      }
      var surname = names[0].replace(/</g, " ").trim();
      var given = names.slice(1).join(" ").replace(/</g, " ").replace(/\s+/g, " ").trim();
      var documentNumber = second.slice(0, 9).replace(/</g, "");
      var nationalityCode = second.slice(10, 13).replace(/</g, "");
      var birth = second.slice(13, 19);
      if (!surname || !given || !documentNumber || !/^\d{6}$/.test(birth)) {
        status.textContent = status.getAttribute("data-failed") || "";
        status.className = "err";
        return;
      }
      var year = Number(birth.slice(0, 2));
      var currentYear = new Date().getFullYear();
      var fullYear = year > currentYear % 100 ? 1900 + year : 2000 + year;
      setValue("surname", surname);
      setValue("first_name", given);
      setValue("doc_number", documentNumber);
      setValue("birth_date", birth.slice(4, 6) + "/" + birth.slice(2, 4) + "/" + fullYear);
      var nationality = setValue("nationality", nationalityCode);
      if (nationality) nationality.dispatchEvent(new Event("change", { bubbles: true }));
      status.textContent = status.getAttribute("data-filled") || "";
      status.className = "hint success";
      assist.open = false;
      document.getElementById("surname").focus();
    });
  }

  function focusFirstError() {
    var first = document.querySelector(".g-field .bad, .g-sign .err:not(:empty)");
    if (!first) return;
    var target = first.matches("input, select, textarea, canvas") ? first : first.closest(".g-sign");
    if (target && typeof target.focus === "function") target.focus();
  }

  function initGuestWizard() {
    var form = document.querySelector("[data-guest-wizard]");
    if (!form) return;
    var steps = Array.prototype.slice.call(form.querySelectorAll("[data-guest-step]"));
    if (steps.length < 2) return;
    var progress = form.querySelector("[data-wizard-progress]");
    var label = form.querySelector("[data-wizard-label]");
    var bar = form.querySelector("[data-wizard-bar]");
    var template = form.getAttribute("data-progress-label") || "";
    var active = Math.max(0, steps.findIndex(function (step) { return step.querySelector(".bad, .err:not(:empty)"); }));

    function stepIsValid(step) {
      var fields = step.querySelectorAll("input, select, textarea");
      for (var i = 0; i < fields.length; i += 1) {
        if (!fields[i].checkValidity()) {
          fields[i].reportValidity();
          fields[i].focus();
          return false;
        }
      }
      return true;
    }

    function show(index, focus) {
      active = Math.max(0, Math.min(index, steps.length - 1));
      steps.forEach(function (step, i) { step.hidden = i !== active; });
      if (progress) progress.hidden = false;
      if (label) {
        label.textContent = template
          .replace("__CURRENT__", String(active + 1))
          .replace("__TOTAL__", String(steps.length));
      }
      if (bar) bar.style.width = ((active + 1) / steps.length * 100) + "%";
      if (focus) {
        var target = steps[active].querySelector("input:not([type=hidden]), select, textarea, button, summary");
        if (target) target.focus({ preventScroll: true });
        steps[active].scrollIntoView({ behavior: "smooth", block: "start" });
      }
    }

    steps.forEach(function (step, index) {
      var nav = document.createElement("div");
      nav.className = "g-wizard-nav";
      if (index > 0) {
        var back = document.createElement("button");
        back.type = "button";
        back.className = "g-btn secondary slim";
        back.textContent = form.getAttribute("data-back-label") || "";
        back.addEventListener("click", function () { show(index - 1, true); });
        nav.appendChild(back);
      }
      if (index < steps.length - 1) {
        var next = document.createElement("button");
        next.type = "button";
        next.className = "g-btn slim";
        next.textContent = form.getAttribute("data-next-label") || "";
        next.addEventListener("click", function () {
          if (stepIsValid(step)) show(index + 1, true);
        });
        nav.appendChild(next);
      }
      if (nav.childNodes.length) step.appendChild(nav);
    });
    show(active, false);
  }

  document.addEventListener("DOMContentLoaded", function () {
    initSignature();
    initCopy();
    initBirthDate();
    initChildToggle();
    initResidenceCountry();
    initMrzAssist();
    initGuestWizard();
    focusFirstError();
  });
})();
