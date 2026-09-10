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
      ctx.strokeStyle = "#16202b";
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

    if (hidden.value && hidden.value.indexOf("data:image/") === 0) {
      dirty = true;
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
          if (status) status.textContent = status.getAttribute("data-missing") || "Signature required.";
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
          button.textContent = "Copied";
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

  function focusFirstError() {
    var first = document.querySelector(".g-field .bad, .g-sign .err:not(:empty)");
    if (!first) return;
    var target = first.matches("input, select, textarea, canvas") ? first : first.closest(".g-sign");
    if (target && typeof target.focus === "function") target.focus();
  }

  document.addEventListener("DOMContentLoaded", function () {
    initSignature();
    initCopy();
    initBirthDate();
    initChildToggle();
    initResidenceCountry();
    focusFirstError();
  });
})();
