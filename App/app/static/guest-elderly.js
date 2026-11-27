// Elderly-friendly progressive enhancements for the guest registration flow:
// 1. A / A+ larger-text toggle stored strictly in localStorage (zero cookies).
// 2. Calm, persistent inline validation + top error summary (replaces fleeting
//    native browser tooltips).
// 3. Forgiving date-of-birth separator normalization on blur.
// 4. Clear visual confirmation on the signature pad once signed.
(function () {
  "use strict";

  var STORAGE_KEY = "ubyhost_guest_text_lg";
  var COPY = {
    en: { largerText: "Larger text", fixBelow: "Please check the highlighted fields:", requiredField: "Please fill in this field.", invalidDate: "Please enter the date as DD.MM.YYYY (for example 14.05.1951).", signedOk: "Signature added" },
    cs: { largerText: "Větší písmo", fixBelow: "Zkontrolujte prosím zvýrazněná pole:", requiredField: "Vyplňte prosím toto pole.", invalidDate: "Zadejte prosím datum ve tvaru DD.MM.RRRR (např. 14.05.1951).", signedOk: "Podpis je zaznamenán" },
    de: { largerText: "Größere Schrift", fixBelow: "Bitte prüfen Sie die markierten Felder:", requiredField: "Bitte füllen Sie dieses Feld aus.", invalidDate: "Bitte geben Sie das Datum als TT.MM.JJJJ ein (z. B. 14.05.1951).", signedOk: "Unterschrift erfasst" },
    es: { largerText: "Texto más grande", fixBelow: "Por favor, revise los campos marcados:", requiredField: "Por favor, complete este campo.", invalidDate: "Introduzca la fecha como DD.MM.AAAA (por ejemplo, 14.05.1951).", signedOk: "Firma añadida" },
    fr: { largerText: "Texte plus grand", fixBelow: "Veuillez vérifier les champs indiqués :", requiredField: "Veuillez remplir ce champ.", invalidDate: "Veuillez saisir la date au format JJ.MM.AAAA (ex. 14.05.1951).", signedOk: "Signature ajoutée" },
    uk: { largerText: "Більший шрифт", fixBelow: "Будь ласка, перевірте виділені поля:", requiredField: "Будь ласка, заповніть це поле.", invalidDate: "Введіть дату у форматі ДД.ММ.РРРР (наприклад, 14.05.1951).", signedOk: "Підпис додано" },
    vi: { largerText: "Chữ lớn hơn", fixBelow: "Vui lòng kiểm tra các mục được đánh dấu:", requiredField: "Vui lòng điền vào mục này.", invalidDate: "Vui lòng nhập ngày theo dạng DD.MM.YYYY (ví dụ 14.05.1951).", signedOk: "Đã lưu chữ ký" }
  };

  function strings() {
    var raw = (document.documentElement.getAttribute("lang") || "en").toLowerCase().slice(0, 2);
    return COPY[raw] || COPY.en;
  }

  function readSavedLarge() {
    try { return window.localStorage.getItem(STORAGE_KEY) === "1"; } catch (_) { return false; }
  }

  function writeSavedLarge(on) {
    try {
      if (on) window.localStorage.setItem(STORAGE_KEY, "1");
      else window.localStorage.removeItem(STORAGE_KEY);
    } catch (_) {}
  }

  function applyLargeText(on) {
    document.documentElement.classList.toggle("g-text-lg", Boolean(on));
  }

  applyLargeText(readSavedLarge());

  function initTextSizeToggle() {
    var head = document.querySelector(".g-head");
    if (!head || head.querySelector("[data-text-size-toggle]")) return;
    var controls = head.querySelector(".g-head-controls");
    if (!controls) {
      controls = document.createElement("div");
      controls.className = "g-head-controls";
      var lang = head.querySelector(".g-lang");
      if (lang) { head.insertBefore(controls, lang); controls.appendChild(lang); }
      else head.appendChild(controls);
    }
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "g-text-toggle";
    btn.setAttribute("data-text-size-toggle", "1");
    btn.setAttribute("aria-label", strings().largerText);
    function sync(on) {
      applyLargeText(on);
      btn.setAttribute("aria-pressed", on ? "true" : "false");
      btn.textContent = on ? "A\u2212" : "A+";
    }
    btn.addEventListener("click", function () {
      var next = !document.documentElement.classList.contains("g-text-lg");
      writeSavedLarge(next);
      sync(next);
    });
    controls.insertBefore(btn, controls.firstChild);
    sync(document.documentElement.classList.contains("g-text-lg"));
  }

  function cleanLabelText(el) {
    if (!el) return "";
    var clone = el.cloneNode(true);
    Array.prototype.forEach.call(clone.querySelectorAll(".opt"), function (o) { o.remove(); });
    return clone.textContent.trim();
  }

  function labelForField(el) {
    if (!el) return "";
    if (el.id) {
      var lbl = document.querySelector('label[for="' + el.id + '"]');
      if (lbl) return cleanLabelText(lbl);
    }
    var field = el.closest(".g-field");
    var fl = field && field.querySelector("label, .g-label");
    return fl ? cleanLabelText(fl) : (el.name || "");
  }

  function focusTargetFor(el) {
    if (el.tagName === "SELECT" && el.classList.contains("g-vh")) {
      return document.getElementById(el.id + "_search") || el;
    }
    return el;
  }

  function clearFieldError(el) {
    var target = focusTargetFor(el);
    target.classList.remove("bad");
    target.removeAttribute("aria-invalid");
    el.classList.remove("bad");
    el.removeAttribute("aria-invalid");
    var field = el.closest(".g-field");
    var msg = field && field.querySelector(".g-field-inline-err");
    if (msg) msg.remove();
  }

  function setFieldError(el, text) {
    var target = focusTargetFor(el);
    target.classList.add("bad");
    target.setAttribute("aria-invalid", "true");
    el.classList.add("bad");
    el.setAttribute("aria-invalid", "true");
    var field = el.closest(".g-field");
    if (!field) return;
    var comboErr = field.querySelector(".g-combo-error");
    if (comboErr) comboErr.hidden = true;
    var msg = field.querySelector(".g-field-inline-err");
    if (!msg) {
      msg = document.createElement("p");
      msg.className = "g-field-inline-err";
      msg.setAttribute("role", "alert");
      field.appendChild(msg);
    }
    msg.textContent = text;
  }

  function clearStepSummary(step) {
    var old = step && step.querySelector(".g-step-error-summary");
    if (old) old.remove();
  }

  function showStepSummary(step, items) {
    clearStepSummary(step);
    if (!items.length) return;
    var box = document.createElement("div");
    box.className = "g-step-error-summary";
    box.setAttribute("role", "alert");
    box.setAttribute("tabindex", "-1");
    var title = document.createElement("strong");
    title.textContent = strings().fixBelow;
    box.appendChild(title);
    var ul = document.createElement("ul");
    items.forEach(function (item) {
      var li = document.createElement("li");
      var a = document.createElement("a");
      var focusEl = focusTargetFor(item.el);
      a.href = "#" + (focusEl.id || item.el.id || "");
      a.textContent = item.label ? (item.label + ": " + item.message) : item.message;
      a.addEventListener("click", function (e) {
        e.preventDefault();
        focusEl.scrollIntoView({ behavior: "smooth", block: "center" });
        focusEl.focus({ preventScroll: true });
      });
      li.appendChild(a);
      ul.appendChild(li);
    });
    box.appendChild(ul);
    var head = step.querySelector(".g-step-head");
    if (head && head.nextSibling) step.insertBefore(box, head.nextSibling);
    else step.insertBefore(box, step.firstChild);
  }

  function validateStepControls(step) {
    var t = strings();
    var bad = [];
    Array.prototype.forEach.call(step.querySelectorAll("input, select, textarea"), function (el) {
      if (el.disabled || el.type === "hidden" || el.type === "button" || el.type === "submit") return;
      var field = el.closest(".g-field");
      if (field && field.hidden) return;
      if (el.classList.contains("g-vh")) { if (!el.required) return; }
      else if (el.offsetParent === null) return;
      if (!el.checkValidity()) {
        var msg = el.getAttribute("data-guest-required") || t.requiredField;
        if (el.id === "birth_date" && el.value.trim()) msg = t.invalidDate;
        setFieldError(el, msg);
        bad.push({ el: el, label: labelForField(el), message: msg });
      } else {
        clearFieldError(el);
      }
    });
    return bad;
  }

  function initCalmValidation() {
    var form = document.getElementById("guest-form");
    if (!form) return;
    form.addEventListener("input", function (e) {
      var el = e.target;
      var field = el && el.closest ? el.closest(".g-field") : null;
      if (!field) return;
      var msg = field.querySelector(".g-field-inline-err");
      if (msg) msg.remove();
      el.classList.remove("bad");
      el.removeAttribute("aria-invalid");
    });
    form.addEventListener("change", function (e) {
      if (e.target && e.target.closest) clearFieldError(e.target);
    });
    form.addEventListener("click", function (e) {
      var nextBtn = e.target && e.target.closest ? e.target.closest("[data-wizard-next], .g-wizard-nav .g-btn:not(.secondary)") : null;
      if (!nextBtn || nextBtn.type === "submit") return;
      var step = nextBtn.closest("[data-guest-step]");
      if (!step) return;
      var bad = validateStepControls(step);
      if (!bad.length) { clearStepSummary(step); return; }
      e.preventDefault();
      e.stopImmediatePropagation();
      showStepSummary(step, bad);
      var summary = step.querySelector(".g-step-error-summary");
      if (summary) summary.scrollIntoView({ behavior: "auto", block: "start" });
      focusTargetFor(bad[0].el).focus({ preventScroll: true });
    }, true);
  }

  function initForgivingBirthDate() {
    var dob = document.getElementById("birth_date");
    if (!dob) return;
    dob.addEventListener("blur", function () {
      var raw = (dob.value || "").trim();
      if (!raw) return;
      var normalized = raw;
      var digitsOnly = raw.replace(/\D/g, "");
      if (/^\d{8}$/.test(digitsOnly) && !/[./\-]/.test(raw)) {
        normalized = digitsOnly.slice(0, 2) + "." + digitsOnly.slice(2, 4) + "." + digitsOnly.slice(4, 8);
      } else if (/^\d{1,2}\s*[\/\- ]\s*\d{1,2}\s*[\/\- ]\s*\d{4}$/.test(raw)) {
        var parts = raw.split(/\s*[\/\- ]\s*/);
        normalized = parts[0].padStart(2, "0") + "." + parts[1].padStart(2, "0") + "." + parts[2];
      }
      if (normalized !== raw) {
        dob.value = normalized;
        dob.dispatchEvent(new Event("input", { bubbles: true }));
        dob.dispatchEvent(new Event("change", { bubbles: true }));
      }
    });
  }

  function initSignatureConfirmation() {
    var pad = document.querySelector(".g-sign");
    var canvas = pad && pad.querySelector("canvas");
    var bar = pad && pad.querySelector(".bar");
    var clearBtn = bar && bar.querySelector("button");
    if (!canvas || !bar) return;
    var status = bar.querySelector("#sig-status");
    function markSigned() {
      var badge = bar.querySelector(".g-sign-ready");
      if (!badge) {
        badge = document.createElement("span");
        badge.className = "g-sign-ready";
        badge.setAttribute("role", "status");
        badge.textContent = "\u2713 " + strings().signedOk;
        bar.insertBefore(badge, clearBtn || null);
      }
      badge.hidden = false;
      if (status) status.textContent = "";
    }
    function clearSigned() {
      var badge = bar.querySelector(".g-sign-ready");
      if (badge) badge.hidden = true;
    }
    canvas.addEventListener("pointerup", markSigned);
    canvas.addEventListener("mouseup", markSigned);
    canvas.addEventListener("touchend", markSigned);
    if (clearBtn) clearBtn.addEventListener("click", clearSigned);
  }

  function start() {
    initTextSizeToggle();
    initCalmValidation();
    initForgivingBirthDate();
    initSignatureConfirmation();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
