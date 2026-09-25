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
          // The signature step is not always the one on screen, and its
          // message would be invisible there. Ask the wizard to reveal the
          // step that owns the canvas before saying anything.
          form.dispatchEvent(new CustomEvent("guest-wizard:show", {
            detail: { target: canvas }
          }));
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
    var readback = document.getElementById("birth-date-readback");
    var template = readback ? readback.getAttribute("data-template") || "" : "";
    var locale = readback && readback.getAttribute("data-locale") === "cs" ? "cs-CZ" : "en-GB";
    var formatter = null;
    try {
      formatter = new Intl.DateTimeFormat(locale, { day: "numeric", month: "long", year: "numeric" });
    } catch (e) { formatter = null; }

    function formatDigits(digits) {
      var out = digits.slice(0, 2);
      if (digits.length > 2) out += "/" + digits.slice(2, 4);
      if (digits.length > 4) out += "/" + digits.slice(4, 8);
      return out;
    }

    // "1990-07-04" is year-first. Reading it as eight digits would give
    // 19/90/0704, so reorder it before anything else touches the value.
    function fromIso(value) {
      var match = /^\s*(\d{4})-(\d{2})-(\d{2})\s*$/.exec(String(value || ""));
      return match ? match[3] + match[2] + match[1] : "";
    }

    function toDate(formatted) {
      var match = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(formatted);
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

    function build() {
      var rows = collect();
      list.textContent = "";
      if (!rows.length) { card.hidden = true; return; }
      rows.forEach(function (row) {
        var dt = document.createElement("dt");
        dt.textContent = row.label;
        var dd = document.createElement("dd");
        dd.appendChild(document.createTextNode(row.value));
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
        list.appendChild(dt);
        list.appendChild(dd);
      });
      card.hidden = false;
    }

    form.addEventListener("guest-wizard:shown", build);
    build();
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
    var active = Math.max(0, steps.findIndex(function (step) { return step.querySelector(".bad, .err:not(:empty)"); }));
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
      if (canvas && signature && !signature.value) {
        var status = document.getElementById("sig-status");
        if (status) status.textContent = status.getAttribute("data-missing") || "";
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
      // Anything that renders a summary of the answers (the review list) needs
      // to rebuild it after the guest has been back and changed something.
      form.dispatchEvent(new CustomEvent("guest-wizard:shown", { detail: { index: active } }));
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

  document.addEventListener("DOMContentLoaded", function () {
    initSignature();
    initCopy();
    initBirthDate();
    initChildToggle();
    initResidenceCountry();
    initPinReturn();
    initGuestWizard();
    initErrorSummary();
    initGuestReview();
    focusFirstError();
  });
})();
