// Signature pad and small helpers for the guest form.
(function () {
  "use strict";

/* The line under the pad says two different kinds of thing: the error that
   stops a submit, and the reassurance that an already-saved signature is
   still there. Red bold text announced as an alert is right for the first
   and wrong for the second, so the line is re-dressed with every message. */
function setSignatureStatus(text, kind) {
  var status = document.getElementById("sig-status");
  if (!status) return;
  var hint = kind === "hint";
  status.textContent = text;
  status.className = hint ? "hint" : "err";
  status.setAttribute("role", hint ? "status" : "alert");
}

// Brief 1090: a guest under 15 has no pad to fill.
function signatureWaived() { var block = document.getElementById("sig-block"); return !!(block && block.hidden); }

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
      var rect = canvas.getBoundingClientRect();
      // A pad on a wizard step that is not showing measures 0 x 0. Sizing the
      // canvas then leaves it with no pixels at all: the guest's strokes draw
      // nothing and the saved value is an empty "data:," that the server
      // refuses. Phones fire resize all the time (the keyboard opening, the
      // address bar hiding), so wait until the pad is visible instead.
      if (!rect.width || !rect.height) return;
      var width = Math.round(rect.width * ratio);
      var height = Math.round(rect.height * ratio);
      // Nothing to do when the pad itself did not change size; re-creating the
      // bitmap would only risk the drawing.
      if (canvas.width === width && canvas.height === height) return;
      // Keep any existing drawing when the viewport changes.
      var snapshot = dirty && canvas.width && canvas.height ? canvas.toDataURL("image/png") : null;
      canvas.width = width;
      canvas.height = height;
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
      if (!canvas.width || !canvas.height) resize();
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
      if (dirty && canvas.width && canvas.height) {
        hidden.value = canvas.toDataURL("image/png");
        setSignatureStatus("");
      }
    }

    resize();
    window.addEventListener("resize", resize);
    // The wizard shows one step at a time, so the pad is often hidden when the
    // page loads. Size it again whenever its step is shown.
    var ownForm = canvas.closest("form");
    if (ownForm) ownForm.addEventListener("guest-wizard:shown", function () { setTimeout(resize, 0); });
    if (window.ResizeObserver) new ResizeObserver(function () { resize(); }).observe(canvas);
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
      setSignatureStatus(status ? status.getAttribute("data-kept") || "" : "", "hint");
    }

    if (clearBtn) {
      clearBtn.addEventListener("click", function () {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        hidden.value = "";
        dirty = false;
        setSignatureStatus("");
      });
    }

    var form = canvas.closest("form");
    if (form) {
      form.addEventListener("submit", function (event) {
        // 0979: the language buttons (data-lang-draft) post the open form to
        // /relang. They need no signature, so they must not hit this guard.
        if (event.submitter && event.submitter.hasAttribute("data-lang-draft")) return;
        if (!hidden.value && !signatureWaived()) {
          event.preventDefault();
          // The signature step is not always the one on screen, and its
          // message would be invisible there. Ask the wizard to reveal the
          // step that owns the canvas before saying anything.
          form.dispatchEvent(new CustomEvent("guest-wizard:show", {
            detail: { target: canvas }
          }));
          setSignatureStatus(
            status ? status.getAttribute("data-missing") || "" : "", "err"
          );
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
    var readback = document.getElementById("birth-date-readback");
    var template = readback ? readback.getAttribute("data-template") || "" : "";
    var locales = { cs: "cs-CZ", de: "de-DE", es: "es-ES", fr: "fr-FR", uk: "uk-UA" };
    var locale = (readback && locales[readback.getAttribute("data-locale")]) || "en-GB";
    var formatter = null;
    try {
      formatter = new Intl.DateTimeFormat(locale, { day: "numeric", month: "long", year: "numeric" });
    } catch (e) { formatter = null; }

    function formatDigits(digits) {
      var out = digits.slice(0, 2);
      if (digits.length > 2) out += "." + digits.slice(2, 4);
      if (digits.length > 4) out += "." + digits.slice(4, 8);
      return out;
    }

    // "1990-07-04" is year-first. Reading it as eight digits would give
    // 19.90.0704, so reorder it before anything else touches the value.
    function fromIso(value) {
      var match = /^\s*(\d{4})-(\d{2})-(\d{2})\s*$/.exec(String(value || ""));
      return match ? match[3] + match[2] + match[1] : "";
    }

    function toDate(formatted) {
      var match = /^(\d{2})\.(\d{2})\.(\d{4})$/.exec(formatted);
      if (!match) return null;
      var day = parseInt(match[1], 10);
      var month = parseInt(match[2], 10);
      var year = parseInt(match[3], 10);
      var date = new Date(year, month - 1, day);
      // 31/02 and friends roll over instead of failing, so round-trip them.
      if (date.getFullYear() !== year || date.getMonth() !== month - 1 || date.getDate() !== day) return null;
      return date;
    }

    function say(date) {
      var pretty = "";
      if (date && formatter) {
        try { pretty = formatter.format(date); } catch (e) { pretty = ""; }
      }
      if (readback) {
        var text = pretty && template ? template.replace("%(date)s", pretty) : "";
        if (readback.textContent !== text) readback.textContent = text;
      }
      // The review list shows the date the guest just confirmed, not the
      // ambiguous digits they typed.
      if (pretty) input.setAttribute("data-review-value", pretty);
      else input.removeAttribute("data-review-value");
    }

    function apply(value) {
      var raw = String(value || "");
      var iso = fromIso(raw);
      var digits = iso || raw.replace(/\D/g, "").slice(0, 8);
      var formatted = formatDigits(digits);
      if (input.value !== formatted) input.value = formatted;
      say(toDate(formatted));
    }

    input.addEventListener("input", function () { apply(input.value); });
    input.addEventListener("paste", function (event) {
      event.preventDefault();
      var text = (event.clipboardData || window.clipboardData).getData("text");
      apply(text);
    });
    apply(input.value);
  }

  /* Brief 1090: a guest under 15 on the arrival day does not sign. This only
     shows and hides: the pad, the note, and the adult's role radios. Nothing
     posted is set here; the server decides again on save. */
  function initUnder15() {
    var sigBlock = document.getElementById("sig-block");
    if (!sigBlock) return;
    var u15Block = document.getElementById("u15-block");
    var forChildren = document.getElementById("sign-for-children");
    var sentence = document.getElementById("sign-for-child-text");
    var birth = document.getElementById("birth_date");
    var firstName = document.getElementById("first_name");
    var surname = document.getElementById("surname");
    var stayFrom = document.querySelector('input[name="stay_from"]');

    // A copy of initChildToggle's childBirth parse; d and m stay 0 when unknown.
    function childBirth(text) {
      var value = String(text || "").trim();
      var m = /^(\d{2})\.(\d{2})\.(\d{4})$/.exec(value);
      var year;
      if (m) {
        year = parseInt(m[3], 10);
      } else {
        m = /^(\d{2})\.(\d{2})\.(\d{2})$/.exec(value);
        if (!m) return null;
        var n = parseInt(m[3], 10);
        year = 2000 + n <= new Date().getFullYear() ? 2000 + n : 1900 + n;
      }
      if (year === 0) return null;
      var month = parseInt(m[2], 10) || 1;
      var day = parseInt(m[1], 10) || 1;
      var date = new Date(Date.UTC(year, month - 1, day));
      if (date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) return null;
      return { y: year, m: parseInt(m[2], 10), d: parseInt(m[1], 10) };
    }

    // The rule is the arrival day, never today.
    function arrival() {
      var s = /^(\d{4})-(\d{2})-(\d{2})$/.exec(stayFrom ? String(stayFrom.value || "").trim() : "");
      if (!s) return null;
      return { y: parseInt(s[1], 10), m: parseInt(s[2], 10), d: parseInt(s[3], 10) };
    }

    function age(y, m, d, when) {
      var years = when.y - y;
      if (when.m < m || (when.m === m && when.d < d)) years -= 1;
      return years;
    }

    // Under 15 for certain: the earliest birthday (00 read as 1) is the oldest
    // the guest can be. 18 for certain: the latest birthday (00 month as 12,
    // 00 day as the month's last day). An unparsed date is neither.
    function ages() {
      var born = childBirth(birth ? birth.value : "");
      var when = arrival();
      if (!born || !when) return { under15: false, adult: false };
      var lateMonth = born.m || 12;
      var lateDay = born.d || new Date(Date.UTC(born.y, lateMonth, 0)).getUTCDate();
      return {
        under15: age(born.y, born.m || 1, born.d || 1, when) < 15,
        adult: age(born.y, lateMonth, lateDay, when) >= 18
      };
    }

    function typing() {
      return birth && document.activeElement === birth && !/^\d{2}\.\d{2}\.\d{4}$/.test(birth.value);
    }

    function fillName() {
      if (!sentence) return;
      var template = sentence.getAttribute("data-template") || "";
      var name = ((firstName ? firstName.value : "") + " " + (surname ? surname.value : "")).trim();
      sentence.textContent = template.replace("{names}", function () { return name; });
    }

    function apply() {
      fillName();
      if (typing()) return;
      // No birth date yet and no script decision to make: a new form shows
      // the pad, as today.
      var now = ages();
      sigBlock.hidden = now.under15;
      if (u15Block) u15Block.hidden = !now.under15;
      if (forChildren) forChildren.hidden = !now.adult;
    }

    apply();
    if (birth) {
      birth.addEventListener("input", apply);
      birth.addEventListener("change", apply);
      birth.addEventListener("blur", apply);
      // initBirthDate's paste handler sets the value without an input event.
      birth.addEventListener("paste", function () { setTimeout(apply, 0); });
    }
    if (firstName) firstName.addEventListener("input", fillName);
    if (surname) surname.addEventListener("input", fillName);
    window.addEventListener("pageshow", apply);
  }

  function initChildToggle() {
    var toggle = document.getElementById("child_in_passport");
    if (!toggle) return;
    var docWrap = document.getElementById("doc-wrap");
    var parentWrap = document.getElementById("parent-doc-wrap");
    var childWrap = document.getElementById("child-wrap");
    var birth = document.getElementById("birth_date");
    var stayFrom = document.querySelector('input[name="stay_from"]');
    var nationality = document.getElementById("nationality");

    // Owner 2026-11-13: only a Czech child may use the box. Czech nationals
    // are never reported to the police; everyone else enters their own
    // document (UbyPort refused an INPASS child). The server enforces it too.
    // Until a nationality is picked nothing is decided, as with the birth date.
    function czech() {
      var code = nationality ? String(nationality.value || "").toUpperCase() : "";
      return code === "" || code === "CZE";
    }

    /* 1079 (S15): the box can only apply to a guest under 18, so an adult does
       not see it. Only childWrap.style.display is ever set here: a ticked box
       is always shown and nothing that is posted changes. */
    // The same parse as feeBirth; exact is false when the day or month is 00.
    function childBirth(text) {
      var value = String(text || "").trim();
      var m = /^(\d{2})\.(\d{2})\.(\d{4})$/.exec(value);
      var year;
      if (m) {
        year = parseInt(m[3], 10);
      } else {
        m = /^(\d{2})\.(\d{2})\.(\d{2})$/.exec(value);
        if (!m) return null;
        var n = parseInt(m[3], 10);
        year = 2000 + n <= new Date().getFullYear() ? 2000 + n : 1900 + n;
      }
      if (year === 0) return null;
      var exact = parseInt(m[2], 10) !== 0 && parseInt(m[1], 10) !== 0;
      var month = parseInt(m[2], 10) || 1;
      var day = parseInt(m[1], 10) || 1;
      var date = new Date(Date.UTC(year, month - 1, day));
      if (date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) return null;
      return { y: year, m: month, d: day, exact: exact };
    }

    // Under 18 on the earlier of the arrival day and today: the earlier day is
    // the younger guest, so the box shows whenever it could apply.
    function mayBeChild() {
      var born = childBirth(birth ? birth.value : "");
      if (!born) return false;
      var now = new Date();
      var ref = { y: now.getFullYear(), m: now.getMonth() + 1, d: now.getDate() };
      var s = /^(\d{4})-(\d{2})-(\d{2})$/.exec(stayFrom ? String(stayFrom.value || "").trim() : "");
      if (s) {
        var from = { y: parseInt(s[1], 10), m: parseInt(s[2], 10), d: parseInt(s[3], 10) };
        var real = new Date(Date.UTC(from.y, from.m - 1, from.d));
        var valid = real.getUTCFullYear() === from.y && real.getUTCMonth() === from.m - 1 && real.getUTCDate() === from.d;
        if (valid && (from.y < ref.y || (from.y === ref.y && (from.m < ref.m || (from.m === ref.m && from.d < ref.d))))) ref = from;
      }
      if (!born.exact) return ref.y - born.y <= 18;
      var y18 = born.y + 18;
      return y18 > ref.y || (y18 === ref.y && (born.m > ref.m || (born.m === ref.m && born.d > ref.d)));
    }

    // The mask passes through 01.01.19 on the way to 01.01.1980; a half-typed
    // date decides nothing.
    function typing() {
      return birth && document.activeElement === birth && !/^\d{2}\.\d{2}\.\d{4}$/.test(birth.value);
    }

    function showBox(mayHide) {
      if (!childWrap) return;
      if (toggle.checked) { childWrap.style.display = ""; return; }
      if (typing()) return;
      if (mayBeChild() && czech()) childWrap.style.display = "";
      else if (mayHide) childWrap.style.display = "none";
    }

    function apply() {
      if (docWrap) docWrap.style.display = toggle.checked ? "none" : "";
      if (parentWrap) parentWrap.style.display = toggle.checked ? "" : "none";
      var docInput = document.querySelector('[name="doc_number"]');
      if (docInput) docInput.required = !toggle.checked;
      // The parent's number is what stands in for the child's own, so it is
      // required exactly when the child has none. Without this the omission is
      // only found on the server, by which time the form is locked.
      var parentInput = document.getElementById("parent_doc_number");
      if (parentInput) parentInput.required = toggle.checked;
      showBox(false);
    }
    toggle.addEventListener("change", apply);
    apply();
    showBox(true);
    if (birth) {
      birth.addEventListener("input", function () { showBox(true); });
      birth.addEventListener("change", function () { showBox(true); });
      birth.addEventListener("blur", function () { showBox(true); });
      // initBirthDate's paste handler sets the value without an input event.
      birth.addEventListener("paste", function () { setTimeout(function () { showBox(true); }, 0); });
    }
    if (nationality) nationality.addEventListener("change", function () { showBox(true); });
    // A restored page can bring back a ticked box or a birth date with no event.
    window.addEventListener("pageshow", function () { apply(); showBox(true); });
  }

  function initResidenceCountry() {
    var nationality = document.getElementById("nationality");
    var resCountry = document.getElementById("res_country");
    if (!nationality || !resCountry) return;
    nationality.addEventListener("change", function () {
      if (!resCountry.value && nationality.value) resCountry.value = nationality.value;
    });
  }

  /* A Schengen visa is something a guest needs in order to enter. A Czech or
     EU/EEA/Swiss guest is entering on their own document, so the question can
     only be answered one way — the majority of guests were being asked to
     decide something they cannot have. The field is hidden and emptied rather
     than removed, so a number typed before the nationality was picked cannot
     be saved behind the guest's back. */
  var VISA_FREE_COUNTRIES = [
    "AUT", "BEL", "BGR", "CHE", "CYP", "CZE", "DEU", "DNK", "ESP", "EST",
    "FIN", "FRA", "GRC", "HRV", "HUN", "IRL", "ISL", "ITA", "LIE", "LTU",
    "LUX", "LVA", "MLT", "NLD", "NOR", "POL", "PRT", "ROU", "SVK", "SVN",
    "SWE"
  ];

  function initVisaVisibility() {
    var nationality = document.getElementById("nationality");
    var visa = document.getElementById("visa_number");
    if (!nationality || !visa) return;
    var wrap = visa.closest(".g-field") || visa;
    function apply() {
      var free = VISA_FREE_COUNTRIES.indexOf(nationality.value) !== -1;
      wrap.style.display = free ? "none" : "";
      if (free) visa.value = "";
    }
    nationality.addEventListener("change", apply);
    apply();
  }

  /* The last step saves and locks the record, so the guest gets one final look
     at what they typed — with a way straight back to the step that owns each
     answer, instead of hunting for it behind a step that is no longer shown. */
  function initGuestReview() {
    var form = document.querySelector("[data-guest-wizard]");
    if (!form) return;
    var card = form.querySelector("[data-wizard-review]");
    if (!card) return;
    var list = card.querySelector(".g-review-list");
    if (!list) return;
    var editLabel = card.getAttribute("data-edit-label") || "";
    // Read the labels off the form itself rather than duplicating them here.
    var groups = [
      { ids: ["first_name", "surname"], join: " " },
      { ids: ["birth_date"] },
      { ids: ["nationality"] },
      { ids: ["doc_number", "parent_doc_number"] },
      { ids: ["res_street", "res_city", "res_country"], join: ", " }
    ];

    function labelFor(input) {
      if (!input.id) return "";
      var label = document.querySelector('label[for="' + input.id + '"]');
      if (!label) return "";
      var copy = label.cloneNode(true);
      Array.prototype.forEach.call(copy.querySelectorAll(".opt, small"), function (node) {
        node.parentNode.removeChild(node);
      });
      return copy.textContent.trim();
    }

    function valueFor(input) {
      var override = input.getAttribute("data-review-value");
      if (override) return override;
      if (input.tagName === "SELECT") {
        var option = input.options[input.selectedIndex];
        return option ? option.textContent.trim() : "";
      }
      return String(input.value || "").trim();
    }

    function isHidden(input) {
      var wrap = input.parentNode;
      while (wrap && wrap !== form) {
        // The wizard hides the steps you are not on. That says nothing about
        // the field itself, so stop looking at the step boundary.
        if (wrap.hasAttribute("data-guest-step")) return false;
        if (wrap.style && wrap.style.display === "none") return true;
        if (wrap.hidden) return true;
        wrap = wrap.parentNode;
      }
      return false;
    }

    function collect() {
      var rows = [];
      groups.forEach(function (group) {
        var values = [];
        var labels = [];
        var target = null;
        group.ids.forEach(function (id) {
          var input = document.getElementById(id);
          if (!input || isHidden(input)) return;
          var value = valueFor(input);
          if (!value) return;
          if (!target) target = input;
          labels.push(labelFor(input));
          values.push(value);
        });
        if (!target) return;
        rows.push({
          label: labels.filter(Boolean).join(" / "),
          value: values.join(group.join || ", "),
          target: target
        });
      });
      return rows;
    }

    /* 0898/1025: the estimate is drawn when the page loads, before the guest has
       typed a birth date or a home address. Recompute it as they type, by the
       rules of stay_fee.guest_period: counted days are (arrival, departure];
       a day is exempt while the guest is under 18 on it (an unknown day or
       month counts as the 1st, as conservative_birth does); a resident of the
       property's municipality pays nothing (same folding as stay_fee._obec_key). */
    function feeBirth(text) {
      var value = String(text || "").trim();
      var m = /^(\d{2})\.(\d{2})\.(\d{4})$/.exec(value);
      var year;
      if (m) {
        year = parseInt(m[3], 10);
      } else {
        // validation.normalise_birth_date: a two-digit year takes the century closest to today.
        m = /^(\d{2})\.(\d{2})\.(\d{2})$/.exec(value);
        if (!m) return null;
        var n = parseInt(m[3], 10);
        year = 2000 + n <= new Date().getFullYear() ? 2000 + n : 1900 + n;
      }
      if (year === 0) return null;
      var month = parseInt(m[2], 10) || 1;
      var day = parseInt(m[1], 10) || 1;
      var date = new Date(Date.UTC(year, month - 1, day));
      if (date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) return null;
      return { y: year, m: month, d: day };
    }

    function feeIso(text) {
      var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(text || ""));
      return m ? Date.UTC(parseInt(m[1], 10), parseInt(m[2], 10) - 1, parseInt(m[3], 10)) : null;
    }

    function feeLiableDays(live, birth) {
      var start = feeIso(live.from), end = feeIso(live.to), day = 86400000, count = 0;
      if (start === null || end === null) return -1;
      for (var t = start + day; t <= end; t += day) {
        var when = new Date(t);
        var y = when.getUTCFullYear(), mo = when.getUTCMonth() + 1, d = when.getUTCDate();
        var age = birth ? y - birth.y - ((mo < birth.m || (mo === birth.m && d < birth.d)) ? 1 : 0) : 99;
        if (age >= 18) count += 1;
      }
      return count;
    }

    function feeLiableAmount(live, birth) {
      // 1031: the amount for the liable nights; per-night rates when the stay crosses a rate change.
      var start = feeIso(live.from), end = feeIso(live.to), day = 86400000, amount = 0;
      if (start === null || end === null) return -1;
      for (var t = start + day; t <= end; t += day) {
        var when = new Date(t);
        var y = when.getUTCFullYear(), mo = when.getUTCMonth() + 1, d = when.getUTCDate();
        var age = birth ? y - birth.y - ((mo < birth.m || (mo === birth.m && d < birth.d)) ? 1 : 0) : 99;
        if (age < 18) continue;
        var iso = when.toISOString().slice(0, 10);
        amount += (live.nights && live.nights[iso] !== undefined) ? live.nights[iso] : live.rate;
      }
      return amount;
    }

    function feeObecResident(box) {
      var raw = box.getAttribute("data-obec-rule");
      if (!raw) return false;
      var rule;
      try { rule = JSON.parse(raw); } catch (e) { return false; }
      function fold(text) {
        var plain = String(text || "").normalize("NFKD").replace(/[\u0300-\u036f]/g, "");
        return plain.toUpperCase().replace(/\s+/g, " ").trim();
      }
      function key(text) {
        // 1031: same steps as stay_fee._obec_key; the tables and the pattern come from the server.
        var t = fold(text).replace(/\s*[-\u2010-\u2015\u2212]\s*/g, "-");
        var after = new RegExp("^(?:" + rule.after + ")");
        function base(s) {
          for (var i = 0; i < rule.bases.length; i++) {
            var b = rule.bases[i];
            if (s.indexOf(b) === 0 && after.test(s.slice(b.length))) return b;
          }
          return null;
        }
        for (var p = 0; p < rule.prefixes.length; p++) {
          var rest = t.slice(rule.prefixes[p].length).trim();
          if (t.indexOf(rule.prefixes[p]) === 0 && base(rest)) { t = rest; break; }
        }
        for (var k = 0; k < rule.okres.length; k++) {
          var n = rule.okres[k];
          if (t.indexOf(n) === 0 && !/[A-Z]/.test(t.charAt(n.length))) return t;
        }
        var found = base(t);
        if (found) t = found;
        return Object.prototype.hasOwnProperty.call(rule.aliases, t) ? rule.aliases[t] : t;
      }
      var country = document.getElementById("res_country");
      var city = document.getElementById("res_city");
      return !!(country && city && country.value === rule.country &&
                key(city.value) === rule.obec);
    }

    function syncFeeBox() {
      var box = document.getElementById("fee-estimate");
      if (!box) return;
      // 1031: the same-town rule first; it needs no stay window.
      if (feeObecResident(box)) { box.hidden = true; return; }
      var raw = box.getAttribute("data-fee-live");
      if (!raw) { box.hidden = false; return; }
      var live;
      try { live = JSON.parse(raw); } catch (e) { return; }
      var input = document.getElementById("birth_date");
      var days = feeLiableDays(live, feeBirth(input ? input.value : ""));
      if (days < 0) return;
      if (days === 0) { box.hidden = true; return; }
      var amount = box.querySelector(".g-fee-amt");
      var calc = box.querySelector(".g-fee-calc");
      if (amount) amount.textContent = String(box.getAttribute("data-fee-amount") || "").replace("{amount}", String(feeLiableAmount(live, feeBirth(input ? input.value : ""))));
      if (calc) calc.textContent = String(box.getAttribute("data-fee-calc") || "").replace("{days}", String(days));
      box.hidden = false;
    }

    function build() {
      syncFeeBox();
      var rows = collect();
      list.textContent = "";
      if (!rows.length) { card.hidden = true; return; }
      rows.forEach(function (row) {
        // One row per fact: the label above, the value and its Edit action
        // on one line below. A div around a dt/dd pair is valid in a dl.
        var item = document.createElement("div");
        item.className = "g-review-row";
        var dt = document.createElement("dt");
        dt.textContent = row.label;
        var dd = document.createElement("dd");
        var value = document.createElement("span");
        value.className = "g-review-value";
        value.textContent = row.value;
        dd.appendChild(value);
        var button = document.createElement("button");
        button.type = "button";
        button.className = "g-review-change";
        button.textContent = editLabel;
        // Five buttons that all say "Change" are useless read aloud on their own.
        button.setAttribute("aria-label", editLabel + ": " + row.label);
        button.addEventListener("click", function () {
          form.dispatchEvent(new CustomEvent("guest-wizard:show", { detail: { target: row.target } }));
          if (typeof row.target.focus === "function") row.target.focus({ preventScroll: true });
          row.target.scrollIntoView({ behavior: "smooth", block: "center" });
        });
        dd.appendChild(button);
        item.appendChild(dt);
        item.appendChild(dd);
        list.appendChild(item);
      });
      card.hidden = false;
    }

    form.addEventListener("guest-wizard:shown", build);
    // 1031: re-count on every edit and when the browser restores the page from its cache.
    ["birth_date", "res_city", "res_country"].forEach(function (id) {
      var field = document.getElementById(id);
      if (!field) return;
      field.addEventListener("input", syncFeeBox);
      field.addEventListener("change", syncFeeBox);
    });
    window.addEventListener("pageshow", build);
    build();
  }

  /* A ticked acknowledgement is a finished answer, not a mistake. The red
     look is kept for an attempted submit with the box still empty: the browser
     fires "invalid" on it then, and ticking the box clears the mark again. */
  function initLegalAck() {
    var box = document.getElementById("legal_ack");
    if (!box) return;
    var wrap = box.closest(".legal-ack");
    if (!wrap) return;
    box.addEventListener("invalid", function () {
      wrap.classList.add("is-invalid");
      box.setAttribute("aria-invalid", "true");
    });
    box.addEventListener("change", function () {
      if (!box.checked) return;
      wrap.classList.remove("is-invalid");
      box.removeAttribute("aria-invalid");
    });
  }

  function focusFirstError() {
    var first = document.querySelector(".g-field .bad, .g-sign .err:not(:empty)");
    if (!first) return;
    var target = first.matches("input, select, textarea, canvas") ? first : first.closest(".g-sign");
    if (target && typeof target.focus === "function") target.focus();
  }

  /* The claim secret lives in the fragment (#c=…), which the browser never
     sends to the server. Carry it across the PIN gate by hand, so a guest
     whose mail app opened the link in its own browser does not lose it. */
  function initPinReturn() {
    var field = document.querySelector('form[action*="/pin"] input[name="return_to"]');
    if (!field) return;
    var hash = window.location.hash || "";
    if (hash.indexOf("#c=") !== 0) return;
    if (field.value.indexOf("#") !== -1) return;
    field.value += hash;
  }

  /* The error summary sits at the top of the page, but the field it names can
     be three steps further in. A plain "#field" jump lands on a hidden step and
     looks like nothing happened, so the link asks the wizard to bring that step
     on screen first. */
  function initErrorSummary() {
    var links = document.querySelectorAll(".g-err a[href^='#']");
    if (!links.length) return;
    var form = document.querySelector("[data-guest-wizard]");
    Array.prototype.forEach.call(links, function (link) {
      link.addEventListener("click", function (event) {
        var id = (link.getAttribute("href") || "").slice(1);
        var field = id ? document.getElementById(id) : null;
        if (!form || !field) return;
        event.preventDefault();
        form.dispatchEvent(new CustomEvent("guest-wizard:show", { detail: { target: field } }));
        if (typeof field.focus === "function") field.focus({ preventScroll: true });
        field.scrollIntoView({ behavior: "smooth", block: "center" });
      });
    });
  }

  function initGuestWizard() {
    var form = document.querySelector("[data-guest-wizard]");
    if (!form) return;
    var allSteps = Array.prototype.slice.call(form.querySelectorAll("[data-guest-step]"));
    if (allSteps.length < 2) return;
    var nationality = form.querySelector('[name="nationality"]');
    var progress = form.querySelector("[data-wizard-progress]");
    var label = form.querySelector("[data-wizard-label]");
    var bar = form.querySelector("[data-wizard-bar]");
    var template = form.getAttribute("data-progress-label") || "";
    var titleTemplate = form.getAttribute("data-progress-title") || "";

    // A step can say which nationality it does not apply to — a Czech guest
    // never uploads a document. The list is what the progress bar counts and
    // what Back and Next walk, so it is worked out on demand rather than baked
    // in at load: pick Czech and the form really is four steps, not five.
    function stepsFor() {
      return allSteps.filter(function (step) {
        var skip = step.getAttribute("data-guest-step-skip-when");
        return !skip || !nationality || nationality.value !== skip;
      });
    }

    var steps = stepsFor();
    var errorAt = steps.findIndex(function (step) { return step.querySelector(".bad, .err:not(:empty)"); });
    // 0979: after a language change the server hands back the step the guest
    // was on; a step with an error still wins, so nothing invalid is hidden.
    var startAt = parseInt(form.getAttribute("data-start-step") || "0", 10);
    var active = errorAt >= 0 ? errorAt : Math.max(0, Math.min(isNaN(startAt) ? 0 : startAt, steps.length - 1));
    // The entry the page loaded on is the starting point for the back gesture;
    // it replaces rather than pushes so the guest is not trapped in the wizard.
    var pushed = active;
    history.replaceState({ guestWizardStep: active }, "");

    function stepIsValid(step) {
      // The pad is a canvas and the signature itself is a hidden input, so no
      // constraint ever fails here: without this the guest walks straight past
      // an empty signature and only finds out at Submit.
      var canvas = step.querySelector("#sig-canvas");
      var signature = document.getElementById("signature");
      if (canvas && signature && !signature.value && !signatureWaived()) {
        var status = document.getElementById("sig-status");
        setSignatureStatus(
          status ? status.getAttribute("data-missing") || "" : "", "err"
        );
        canvas.focus();
        return false;
      }
      var fields = step.querySelectorAll("input, select, textarea");
      for (var i = 0; i < fields.length; i += 1) {
        if (!fields[i].checkValidity()) {
          // The passport file input is hidden, and a browser cannot show a
          // validation bubble on, or focus, a hidden control: Continue would
          // silently do nothing. Say why in the error line and send the guest
          // to the button that actually opens the picker.
          if (fields[i].type === "file" && fields[i].hidden) {
            var fileErr = document.getElementById("passport-file-err");
            if (fileErr) {
              fileErr.textContent = fileErr.getAttribute("data-missing") || "";
              fileErr.hidden = !fileErr.textContent;
            }
            var takeBtn = document.getElementById("passport-take-btn");
            if (takeBtn) takeBtn.focus();
            return false;
          }
          fields[i].reportValidity();
          fields[i].focus();
          return false;
        }
      }
      return true;
    }

    function show(index, focus) {
      steps = stepsFor();
      active = Math.max(0, Math.min(index, steps.length - 1));
      form.setAttribute("data-active-step", String(active));
      // The OS back gesture used to leave the page and throw the whole form
      // away. Every step gets its own history entry, so back now steps back.
      if (active !== pushed) {
        pushed = active;
        history.pushState({ guestWizardStep: active }, "");
      }
      // Hide every step first, so a step that has just dropped out of the list
      // cannot be left visible behind the one the guest is on.
      allSteps.forEach(function (step) { step.hidden = true; });
      if (steps[active]) steps[active].hidden = false;
      if (progress) progress.hidden = false;
      if (label) {
        var progressText = template
          .replace("__CURRENT__", String(active + 1))
          .replace("__TOTAL__", String(steps.length));
        // Which step you are on only means something if you are also told what
        // the step is for, so the bar carries the step's own title.
        var stepTitle = steps[active].getAttribute("data-step-title") || "";
        label.textContent = stepTitle && titleTemplate
          ? titleTemplate.replace("__PROGRESS__", progressText).replace("__TITLE__", stepTitle)
          : progressText;
      }
      if (bar) bar.style.width = ((active + 1) / steps.length * 100) + "%";
      if (focus) {
        var target = steps[active].querySelector("input:not([type=hidden]), select, textarea, button, summary");
        if (target) target.focus({ preventScroll: true });
        steps[active].scrollIntoView({ behavior: "smooth", block: "start" });
      }
      // Anything that renders a summary of the answers (the review list) or
      // the check-in rail needs to rebuild after the guest has been back and
      // changed something. The filtered list travels with the event so the
      // rail counts the same steps the bar does.
      form.dispatchEvent(new CustomEvent("guest-wizard:shown", { detail: { index: active, steps: steps } }));
    }

    // Other scripts (the signature pad's submit guard) need to bring their own
    // step on screen without reaching into the wizard's state.
    form.addEventListener("guest-wizard:show", function (event) {
      var target = event.detail && event.detail.target;
      if (!target) return;
      steps = stepsFor();
      for (var i = 0; i < steps.length; i += 1) {
        if (steps[i].contains(target)) { show(i, false); return; }
      }
    });

    window.addEventListener("popstate", function (event) {
      var state = event.state;
      if (!state || typeof state.guestWizardStep !== "number") return;
      pushed = state.guestWizardStep;
      show(state.guestWizardStep, true);
    });

    // Back and Next work out where they are from the live list, so a step that
    // has been skipped cannot make them jump to the wrong card.
    allSteps.forEach(function (step, index) {
      var nav = document.createElement("div");
      nav.className = "g-wizard-nav";
      if (index > 0) {
        var back = document.createElement("button");
        back.type = "button";
        back.className = "g-btn secondary slim";
        back.textContent = form.getAttribute("data-back-label") || "";
        back.addEventListener("click", function () {
          var at = stepsFor().indexOf(step);
          if (at > 0) show(at - 1, true);
        });
        nav.appendChild(back);
      }
      if (index < allSteps.length - 1) {
        var next = document.createElement("button");
        next.type = "button";
        next.className = "g-btn slim";
        next.textContent = form.getAttribute("data-next-label") || "";
        next.addEventListener("click", function () {
          if (!stepIsValid(step)) return;
          var list = stepsFor();
          var at = list.indexOf(step);
          if (at !== -1 && at < list.length - 1) show(at + 1, true);
        });
        nav.appendChild(next);
      }
      if (nav.childNodes.length) step.appendChild(nav);
    });

    // Enter in a field used to press the first submit button in the page, which
    // was a language button. Now it presses the button of the step on screen:
    // Continue (which checks that step first) or, on the last step, Save. A
    // plain submit from an earlier step could not work anyway, because the
    // later steps' required fields are hidden and a browser cannot show a
    // validation bubble on them.
    form.addEventListener("keydown", function (event) {
      if (event.key !== "Enter" || event.defaultPrevented || event.isComposing) return;
      var target = event.target;
      if (!target || target.tagName !== "INPUT") return;
      if (/^(button|submit|reset|file|image)$/.test(target.type)) return;
      var step = target.closest("[data-guest-step]");
      if (!step) return;
      event.preventDefault();
      var list = stepsFor();
      var at = list.indexOf(step);
      if (at !== -1 && at < list.length - 1) {
        var next = step.querySelector(".g-wizard-nav .g-btn:not(.secondary)");
        if (next) next.click();
      } else {
        var save = form.querySelector("[data-guest-save]");
        if (save && form.requestSubmit) form.requestSubmit(save);
        else if (save) save.click();
      }
    });

    // The nationality field lives on the first step, so a Czech guest is on it
    // when the passport step drops out: re-count the bar under their feet.
    if (nationality) {
      nationality.addEventListener("change", function () {
        var current = steps[active];
        var list = stepsFor();
        var at = current ? list.indexOf(current) : -1;
        // If the guest was standing on a step that has just stopped applying,
        // keep their place in the list rather than throwing them to the end.
        show(at === -1 ? Math.min(active, list.length - 1) : at, false);
        pushed = active;
        history.replaceState({ guestWizardStep: active }, "");
      });
    }

    show(active, false);
  }

  /* 0979: the language menu on the form posts the open form back (see
     guest_form_relang). A drawn signature, the acknowledgement tick and a
     chosen photo are not carried over, so ask first; Cancel leaves the page
     and every answer exactly as it is. Nothing is stored anywhere. */
  function initLanguageDraft() {
    var form = document.getElementById("guest-form");
    if (!form) return;
    var buttons = document.querySelectorAll("[data-lang-draft]");
    Array.prototype.forEach.call(buttons, function (button) {
      button.addEventListener("click", function (event) {
        var signature = document.getElementById("signature");
        var ack = document.getElementById("legal_ack");
        var photo = document.getElementById("passport_photo");
        var drawn = !!(signature && signature.value && signature.value !== signature.defaultValue);
        var ticked = !!(ack && ack.checked);
        var picked = !!(photo && photo.files && photo.files.length);
        if ((drawn || ticked || picked) && !window.confirm(form.getAttribute("data-lang-warning") || "")) {
          event.preventDefault();
          return;
        }
        // What is dropped need not travel.
        if (drawn) signature.value = "";
        if (picked) photo.value = "";
        var step = document.getElementById("form-step");
        if (step) step.value = form.getAttribute("data-active-step") || "0";
      });
    });
  }

  /* A save sent with no connection used to drop the guest on the browser's own
     error page, with the form gone. While the browser reports it is offline
     the submit is held back instead: nothing is sent, the form stays exactly
     as it is, and a plain sentence above Save says to try again once back
     online. The submit itself stays an ordinary form post (not fetch), so a
     save that does go out behaves as it always has: no second request, no
     page rewriting. A connection that drops while a request is already in
     flight is still the browser's own page. */
  function initSaveRetry() {
    var form = document.getElementById("guest-form");
    var note = document.getElementById("save-net-error");
    if (!form || !note) return;
    form.addEventListener("submit", function (event) {
      if (event.defaultPrevented) return;
      if (event.submitter && event.submitter.hasAttribute("data-lang-draft")) return;
      if (navigator.onLine !== false) return;
      event.preventDefault();
      note.hidden = false;
      if (note.scrollIntoView) note.scrollIntoView({ block: "center" });
    });
    window.addEventListener("online", function () { note.hidden = true; });
  }

  /* Brief 1087: the unfinished new-guest form is saved as a draft while the
     guest types, so closing the page and opening it again on the same device
     brings the typed answers back. It only posts the fields the server lists
     in data-draft-fields, and it only reads the form. Without JavaScript
     there is no draft. The document picture and the drawn name are never
     part of it. */
  function initGuestDraft() {
    var form = document.getElementById("guest-form");
    if (!form || !form.hasAttribute("data-draft-url") || !window.fetch || !window.FormData) return;
    var url = form.getAttribute("data-draft-url");
    var names = (form.getAttribute("data-draft-fields") || "").split(" ").filter(function (name) { return name; });
    var DEBOUNCE_MS = 2000;
    var MIN_GAP_MS = 15000;
    var timer = null;
    var last = 0;
    var dirty = false;
    var stopped = false;

    function body() {
      var data = new FormData();
      data.append("_csrf", form.elements._csrf.value);
      data.append("draft_owned", form.getAttribute("data-draft-owned") || "0");
      names.forEach(function (name) {
        var el = form.elements[name];
        if (!el) return;
        if (el.type === "checkbox") {
          if (el.checked) data.append(name, "1");
          return;
        }
        data.append(name, el.value);
      });
      return data;
    }

    function send(keepalive) {
      if (stopped || !dirty) return;
      dirty = false;
      last = Date.now();
      fetch(url, { method: "POST", body: body(), credentials: "same-origin", keepalive: !!keepalive })
        .catch(function () { dirty = true; });
    }

    function schedule(event) {
      if (stopped) return;
      if (!event.target || names.indexOf(event.target.name) < 0) return;
      dirty = true;
      clearTimeout(timer);
      timer = setTimeout(function () { send(false); }, Math.max(DEBOUNCE_MS, MIN_GAP_MS - (Date.now() - last)));
    }

    function flush() {
      clearTimeout(timer);
      send(true);
    }

    form.addEventListener("input", schedule);
    form.addEventListener("change", schedule);
    window.addEventListener("pagehide", flush);
    document.addEventListener("visibilitychange", function () {
      if (document.visibilityState === "hidden") flush();
    });
    form.addEventListener("submit", function (event) {
      if (event.defaultPrevented) return;
      if (event.submitter && event.submitter.hasAttribute("data-lang-draft")) {
        flush();
        return;
      }
      stopped = true;
      clearTimeout(timer);
    });
  }

  /* The wide check-in layout shows the stay summary and the step list beside
     the active form. The list is built from the same data-step-title elements
     the wizard walks, so it can never disagree with the bar, and each visited
     step becomes a way back that keeps everything the guest already typed. */
  function initCheckinRail() {
    var list = document.querySelector("[data-checkin-steps]");
    var form = document.querySelector("[data-guest-wizard]");
    if (!list || !form) return;
    var doneLabel = list.getAttribute("data-done-label") || "";
    var editLabel = list.getAttribute("data-edit-label") || "";

    function render(event) {
      var detail = event && event.detail ? event.detail : {};
      var steps = detail.steps
        ? Array.prototype.slice.call(detail.steps)
        : Array.prototype.slice.call(form.querySelectorAll("[data-guest-step]"));
      var active = typeof detail.index === "number"
        ? detail.index
        : Math.max(0, steps.indexOf(steps.find(function (step) { return !step.hidden; })));
      list.textContent = "";
      steps.forEach(function (step, index) {
        var item = document.createElement("li");
        item.className = "g-checkin-step" + (index < active ? " is-done" : "") +
          (index === active ? " is-current" : "");
        var state = document.createElement("i");
        state.setAttribute("aria-hidden", "true");
        state.textContent = index < active ? "\u2713" : String(index + 1);
        item.appendChild(state);
        var name = document.createElement("span");
        name.textContent = step.getAttribute("data-step-title") || "";
        item.appendChild(name);
        if (index < active) {
          var sr = document.createElement("span");
          sr.className = "sr-only";
          sr.textContent = doneLabel;
          item.appendChild(sr);
          var button = document.createElement("button");
          button.type = "button";
          button.className = "g-checkin-step-edit";
          button.textContent = editLabel;
          button.setAttribute("aria-label", editLabel + ": " + (step.getAttribute("data-step-title") || ""));
          button.addEventListener("click", function () {
            form.dispatchEvent(new CustomEvent("guest-wizard:show", { detail: { target: step } }));
          });
          item.appendChild(button);
        } else if (index === active) {
          item.setAttribute("aria-current", "step");
        }
        list.appendChild(item);
      });
    }

    form.addEventListener("guest-wizard:shown", render);
    render();
  }

  document.addEventListener("DOMContentLoaded", function () {
    initSignature();
    initCopy();
    initBirthDate();
    initChildToggle();
    initUnder15();
    initResidenceCountry();
    initVisaVisibility();
    initPinReturn();
    initGuestWizard();
    initLanguageDraft();
    initSaveRetry();
    initCheckinRail();
    initErrorSummary();
    initGuestReview();
    initLegalAck();
    initGuestDraft();
    focusFirstError();
  });
})();
