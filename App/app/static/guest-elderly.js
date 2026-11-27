// Progressive enhancements and error-prevention guards for the guest registration flow:
// 1. Calm inline validation + top error summary on Step 1 & Step 2 (catches UbyPort rules:
//    non-Latin scripts, impossible/future DOBs, doc length 4..20, digits-only street/city).
// 2. Soft, non-blocking sanity warnings (DOB age 0 / >110, identical given & surname,
//    digits in names, placeholder doc numbers, non-EU passport reminder).
// 3. Forgiving date-of-birth separator normalization on blur and before Continue.
// 4. Real signature stroke-length check before marking "Signature added" / saving.
// Zero cookies and zero localStorage writes.
(function () {
  "use strict";

  var COPY = {
    en: {
      fixBelow: "Please check the highlighted fields:", requiredField: "Please fill in this field.",
      invalidDate: "Please enter a valid date as DD.MM.YYYY (for example 14.05.1951).",
      futureDate: "Date of birth cannot be in the future.", yearTooOld: "Year must be 1900 or later.",
      nonLatin: "Please write this using Latin letters (as shown in the bottom line of your passport).",
      docLength: "Travel document number must be between 4 and 20 characters.",
      digitsOnly: "This field cannot contain only numbers.",
      warnDobYoung: "This enters an age of 0 — please check you typed your date of birth, not your arrival date.",
      warnDobOld: "Please check the birth year — this gives an age over 110.",
      warnSameName: "Given name and surname are identical — please check both fields.",
      warnNameDigits: "Names normally do not contain numbers — did you paste a document number here?",
      warnPlaceholderDoc: "This looks like a placeholder number — please enter the number from your passport or ID.",
      warnNonEuPassport: "Non-EU citizens must enter a passport number (national ID cards and driving licences are not accepted).",
      signedOk: "Signature added", signNeeded: "Please draw your signature across the box before saving."
    },
    cs: {
      fixBelow: "Zkontrolujte prosím zvýrazněná pole:", requiredField: "Vyplňte prosím toto pole.",
      invalidDate: "Zadejte prosím platné datum ve tvaru DD.MM.RRRR (např. 14.05.1951).",
      futureDate: "Datum narození nemůže být v budoucnosti.", yearTooOld: "Rok narození musí být 1900 nebo novější.",
      nonLatin: "Napište prosím údaj latinkou (jako ve spodním řádku pasu).",
      docLength: "Číslo dokladu musí mít 4 až 20 znaků.",
      digitsOnly: "Toto pole nemůže obsahovat pouze číslice.",
      warnDobYoung: "Podle tohoto data je věk 0 let — zkontrolujte, zda jste nezadali datum příjezdu místo data narození.",
      warnDobOld: "Zkontrolujte prosím rok narození — vychází věk přes 110 let.",
      warnSameName: "Jméno a příjmení jsou stejné — zkontrolujte prosím obě pole.",
      warnNameDigits: "Jméno obvykle neobsahuje číslice — nevložili jste sem číslo dokladu?",
      warnPlaceholderDoc: "Vypadá to jako zkušební číslo — zadejte prosím číslo z pasu nebo občanského průkazu.",
      warnNonEuPassport: "Občané mimo EU musí uvést číslo cestovního pasu (národní průkazy a řidičské průkazy policie nepřijímá).",
      signedOk: "Podpis je zaznamenán", signNeeded: "Před uložením se prosím podepište do rámečku."
    },
    de: {
      fixBelow: "Bitte prüfen Sie die markierten Felder:", requiredField: "Bitte füllen Sie dieses Feld aus.",
      invalidDate: "Bitte geben Sie ein gültiges Datum als TT.MM.JJJJ ein (z. B. 14.05.1951).",
      futureDate: "Das Geburtsdatum darf nicht in der Zukunft liegen.", yearTooOld: "Das Jahr muss 1900 oder später sein.",
      nonLatin: "Bitte verwenden Sie lateinische Buchstaben (wie in der unteren Zeile Ihres Reisepasses).",
      docLength: "Die Dokumentennummer muss zwischen 4 und 20 Zeichen lang sein.",
      digitsOnly: "Dieses Feld darf nicht nur aus Ziffern bestehen.",
      warnDobYoung: "Dieses Datum ergibt ein Alter von 0 — haben Sie vielleicht Ihr Anreisedatum statt Ihres Geburtsdatums eingegeben?",
      warnDobOld: "Bitte prüfen Sie das Geburtsjahr — es ergibt ein Alter über 110.",
      warnSameName: "Vorname und Nachname sind identisch — bitte prüfen Sie beide Felder.",
      warnNameDigits: "Namen enthalten normalerweise keine Ziffern — haben Sie versehentlich eine Dokumentennummer eingefügt?",
      warnPlaceholderDoc: "Das sieht nach einer Platzhalternummer aus — bitte geben Sie die Nummer Ihres Reisepasses oder Ausweises ein.",
      warnNonEuPassport: "Nicht-EU-Bürger müssen eine Reisepassnummer angeben (Personalausweise und Führerscheine werden nicht akzeptiert).",
      signedOk: "Unterschrift erfasst", signNeeded: "Bitte zeichnen Sie Ihre Unterschrift in das Feld, bevor Sie speichern."
    },
    es: {
      fixBelow: "Por favor, revise los campos marcados:", requiredField: "Por favor, complete este campo.",
      invalidDate: "Introduzca una fecha válida como DD.MM.AAAA (por ejemplo, 14.05.1951).",
      futureDate: "La fecha de nacimiento no puede ser futura.", yearTooOld: "El año debe ser 1900 o posterior.",
      nonLatin: "Escriba este dato con letras latinas (como aparece en la parte inferior de su pasaporte).",
      docLength: "El número de documento debe tener entre 4 y 20 caracteres.",
      digitsOnly: "Este campo no puede contener solo números.",
      warnDobYoung: "Esta fecha da una edad de 0 años — compruebe que escribió su fecha de nacimiento y no la de llegada.",
      warnDobOld: "Compruebe el año de nacimiento — da una edad superior a 110 años.",
      warnSameName: "El nombre y el apellido son idénticos — revise ambos campos.",
      warnNameDigits: "Los nombres no suelen contener números — ¿pegó aquí un número de documento?",
      warnPlaceholderDoc: "Parece un número de ejemplo — introduzca el número real de su pasaporte o documento.",
      warnNonEuPassport: "Los ciudadanos de fuera de la UE deben indicar el número de pasaporte (no se aceptan carnés nacionales ni licencias de conducir).",
      signedOk: "Firma añadida", signNeeded: "Por favor, dibuje su firma dentro del recuadro antes de guardar."
    },
    fr: {
      fixBelow: "Veuillez vérifier les champs indiqués :", requiredField: "Veuillez remplir ce champ.",
      invalidDate: "Veuillez saisir une date valide au format JJ.MM.AAAA (ex. 14.05.1951).",
      futureDate: "La date de naissance ne peut pas être dans le futur.", yearTooOld: "L'année doit être 1900 ou ultérieure.",
      nonLatin: "Veuillez écrire en caractères latins (comme sur la ligne inférieure de votre passeport).",
      docLength: "Le numéro de document doit contenir entre 4 et 20 caractères.",
      digitsOnly: "Ce champ ne peut pas contenir uniquement des chiffres.",
      warnDobYoung: "Cette date donne un âge de 0 an — vérifiez que vous avez saisi votre date de naissance et non votre date d'arrivée.",
      warnDobOld: "Veuillez vérifier l'année de naissance — elle indique un âge supérieur à 110 ans.",
      warnSameName: "Le prénom et le nom sont identiques — veuillez vérifier les deux champs.",
      warnNameDigits: "Un nom ne contient normalement pas de chiffres — avez-vous collé un numéro de document ?",
      warnPlaceholderDoc: "Cela ressemble à un numéro factice — veuillez saisir le numéro de votre passeport ou pièce d'identité.",
      warnNonEuPassport: "Les ressortissants hors UE doivent saisir un numéro de passeport (cartes d'identité nationales et permis de conduire refusés).",
      signedOk: "Signature ajoutée", signNeeded: "Veuillez tracer votre signature dans le cadre avant d'enregistrer."
    },
    uk: {
      fixBelow: "Будь ласка, перевірте виділені поля:", requiredField: "Будь ласка, заповніть це поле.",
      invalidDate: "Введіть дійсну дату у форматі ДД.ММ.РРРР (наприклад, 14.05.1951).",
      futureDate: "Дата народження не може бути в майбутньому.", yearTooOld: "Рік народження має бути 1900 або пізніший.",
      nonLatin: "Введіть, будь ласка, латинськими літерами (як у нижньому рядку закордонного паспорта).",
      docLength: "Номер документа має містити від 4 до 20 символів.",
      digitsOnly: "Це поле не може містити лише цифри.",
      warnDobYoung: "За цією датою вік становить 0 років — перевірте, чи ви не ввели дату заїзду замість дати народження.",
      warnDobOld: "Перевірте рік народження — виходить вік понад 110 років.",
      warnSameName: "Ім'я та прізвище однакові — перевірте обидва поля.",
      warnNameDigits: "Ім'я зазвичай не містить цифр — чи не вставили ви сюди номер документа?",
      warnPlaceholderDoc: "Це схоже на тестовий номер — введіть номер із вашого паспорта.",
      warnNonEuPassport: "Громадянам країн поза ЄС потрібно вказати номер закордонного паспорта (внутрішні ID-картки та водійські посвідчення не приймаються).",
      signedOk: "Підпис додано", signNeeded: "Будь ласка, поставте підпис у полі перед збереженням."
    },
    vi: {
      fixBelow: "Vui lòng kiểm tra các mục được đánh dấu:", requiredField: "Vui lòng điền vào mục này.",
      invalidDate: "Vui lòng nhập ngày hợp lệ theo dạng DD.MM.YYYY (ví dụ 14.05.1951).",
      futureDate: "Ngày sinh không thể ở trong tương lai.", yearTooOld: "Năm sinh phải từ 1900 trở đi.",
      nonLatin: "Vui lòng nhập bằng chữ cái Latinh (như ở dòng dưới cùng trên hộ chiếu của bạn).",
      docLength: "Số giấy tờ phải có từ 4 đến 20 ký tự.",
      digitsOnly: "Mục này không thể chỉ gồm các chữ số.",
      warnDobYoung: "Ngày này cho kết quả 0 tuổi — vui lòng kiểm tra xem bạn có nhập nhầm ngày nhận phòng thay vì ngày sinh không.",
      warnDobOld: "Vui lòng kiểm tra lại năm sinh — tuổi tính ra lớn hơn 110.",
      warnSameName: "Tên và họ giống hệt nhau — vui lòng kiểm tra lại cả hai mục.",
      warnNameDigits: "Tên thường không có chữ số — bạn có dán nhầm số hộ chiếu vào đây không?",
      warnPlaceholderDoc: "Số này giống số mẫu — vui lòng nhập đúng số trên hộ chiếu hoặc giấy tờ tùy thân.",
      warnNonEuPassport: "Công dân ngoài EU cần nhập số hộ chiếu (thẻ căn cước và bằng lái xe không được chấp nhận).",
      signedOk: "Đã lưu chữ ký", signNeeded: "Vui lòng ký tên vào khung trước khi lưu."
    }
  };

  var EU_EEA_CH = {
    AUT: 1, BEL: 1, BGR: 1, HRV: 1, CYP: 1, CZE: 1, DNK: 1, EST: 1, FIN: 1, FRA: 1,
    DEU: 1, GRC: 1, HUN: 1, IRL: 1, ITA: 1, LVA: 1, LTU: 1, LUX: 1, MLT: 1, NLD: 1,
    POL: 1, PRT: 1, ROU: 1, SVK: 1, SVN: 1, ESP: 1, SWE: 1, ISL: 1, LIE: 1, NOR: 1, CHE: 1
  };
  var NON_LATIN_RE = /[\u0370-\u052F\u0530-\u06FF\u0900-\u0E7F\u10A0-\u10FF\u3040-\u30FF\u4E00-\u9FFF\uAC00-\uD7AF]/;
  var PLACEHOLDER_DOCS = {
    "123456": 1, "1234567": 1, "12345678": 1, "123456789": 1, "012345678": 1,
    "ABCDEF": 1, "TEST": 1, "TEST123": 1, "NONE": 1, "NA": 1, "UNKNOWN": 1, "XXXX": 1, "XXXXX": 1
  };
  var MIN_SIG_DIST = 24;

  function strings() {
    var raw = (document.documentElement.getAttribute("lang") || "en").toLowerCase().slice(0, 2);
    return COPY[raw] || COPY.en;
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

  function setFieldWarning(el, text) {
    var field = el && el.closest ? el.closest(".g-field") : null;
    if (!field) return;
    var existing = field.querySelector(".g-field-warn");
    if (!text) { if (existing) existing.remove(); return; }
    if (!existing) {
      existing = document.createElement("p");
      existing.className = "g-field-warn";
      existing.setAttribute("role", "status");
      field.appendChild(existing);
    }
    existing.textContent = text;
  }

  function normalizeBirthDateInput(dob) {
    if (!dob) return "";
    var raw = (dob.value || "").trim();
    if (!raw) return "";
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
    return normalized;
  }

  function parseBirthDate(val) {
    var m = /^(\d{2})\.(\d{2})\.(\d{4})$/.exec((val || "").trim());
    if (!m) return null;
    var day = parseInt(m[1], 10), month = parseInt(m[2], 10), year = parseInt(m[3], 10);
    if (year < 1900) return { error: "yearTooOld" };
    if (month < 1 || month > 12 || day < 1 || day > 31) return { error: "invalidDate" };
    var d = new Date(year, month - 1, day);
    if (d.getFullYear() !== year || d.getMonth() !== month - 1 || d.getDate() !== day) return { error: "invalidDate" };
    var now = new Date();
    var today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    if (d > today) return { error: "futureDate" };
    var age = today.getFullYear() - year;
    if (today.getMonth() < month - 1 || (today.getMonth() === month - 1 && today.getDate() < day)) age -= 1;
    return { date: d, age: age };
  }

  function checkFieldUbyPortRule(el, t) {
    var id = el.id || el.name || "";
    var val = (el.value || "").trim();
    if (!val) return null;
    if ((id === "first_name" || id === "surname" || id === "res_city" || id === "res_street") && NON_LATIN_RE.test(val)) {
      return t.nonLatin;
    }
    if ((id === "res_city" || id === "res_street") && /^\d+$/.test(val.replace(/\s+/g, ""))) {
      return t.digitsOnly;
    }
    if (id === "birth_date") {
      val = normalizeBirthDateInput(el);
      var parsed = parseBirthDate(val);
      if (!parsed) return t.invalidDate;
      if (parsed.error) return t[parsed.error] || t.invalidDate;
    }
    if (id === "doc_number") {
      var inpass = document.getElementById("inpass_toggle");
      if (inpass && inpass.checked) return null;
      var compact = val.replace(/\s+/g, "");
      if (compact.length < 4 || compact.length > 20) return t.docLength;
    }
    return null;
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
    var t = strings(), bad = [];
    Array.prototype.forEach.call(step.querySelectorAll("input, select, textarea"), function (el) {
      if (el.disabled || el.type === "hidden" || el.type === "button" || el.type === "submit") return;
      var field = el.closest(".g-field");
      if (field && field.hidden) return;
      if (el.classList.contains("g-vh")) { if (!el.required) return; }
      else if (el.offsetParent === null) return;
      if (el.id === "birth_date") normalizeBirthDateInput(el);
      var customMsg = null;
      if (!el.checkValidity()) {
        customMsg = el.getAttribute("data-guest-required") || t.requiredField;
        if (el.id === "birth_date" && el.value.trim()) customMsg = t.invalidDate;
      } else {
        customMsg = checkFieldUbyPortRule(el, t);
      }
      if (customMsg) { setFieldError(el, customMsg); bad.push({ el: el, label: labelForField(el), message: customMsg }); }
      else clearFieldError(el);
    });
    return bad;
  }

  function evaluateSanityWarnings() {
    var t = strings();
    var first = document.getElementById("first_name"), sur = document.getElementById("surname");
    var dob = document.getElementById("birth_date"), nat = document.getElementById("nationality");
    var doc = document.getElementById("doc_number");

    if (first) setFieldWarning(first, /\d/.test((first.value || "").trim()) ? t.warnNameDigits : "");
    if (sur) {
      var sv = (sur.value || "").trim(), fv = first ? (first.value || "").trim() : "";
      if (/\d/.test(sv)) setFieldWarning(sur, t.warnNameDigits);
      else if (fv && sv && fv.toLowerCase() === sv.toLowerCase()) setFieldWarning(sur, t.warnSameName);
      else setFieldWarning(sur, "");
    }
    if (dob) {
      var dv = (dob.value || "").trim(), parsed = dv ? parseBirthDate(dv) : null;
      if (parsed && !parsed.error) {
        if (parsed.age < 1) setFieldWarning(dob, t.warnDobYoung);
        else if (parsed.age > 110) setFieldWarning(dob, t.warnDobOld);
        else setFieldWarning(dob, "");
      } else setFieldWarning(dob, "");
    }
    if (doc) {
      var docVal = (doc.value || "").trim();
      var compact = docVal.replace(/[\s\-\/]+/g, "").toUpperCase();
      var natVal = nat ? (nat.value || "").trim().toUpperCase() : "";
      if (!docVal) setFieldWarning(doc, "");
      else if (/^(\d)\1{3,}$/.test(compact) || PLACEHOLDER_DOCS[compact]) setFieldWarning(doc, t.warnPlaceholderDoc);
      else if (natVal && !EU_EEA_CH[natVal] && (compact.length < 6 || /[\/]/.test(docVal))) setFieldWarning(doc, t.warnNonEuPassport);
      else setFieldWarning(doc, "");
    }
  }

  function initCalmValidation() {
    var form = document.getElementById("guest-form");
    if (!form) return;
    form.addEventListener("input", function (e) {
      var el = e.target, field = el && el.closest ? el.closest(".g-field") : null;
      if (!field) return;
      var msg = field.querySelector(".g-field-inline-err");
      if (msg) msg.remove();
      el.classList.remove("bad");
      el.removeAttribute("aria-invalid");
    });
    form.addEventListener("change", function (e) {
      if (e.target && e.target.closest) clearFieldError(e.target);
      evaluateSanityWarnings();
    });
    form.addEventListener("focusout", function (e) {
      var el = e.target;
      if (el && el.id === "birth_date") normalizeBirthDateInput(el);
      if (el && (el.id === "first_name" || el.id === "surname" || el.id === "birth_date" || el.id === "doc_number" || el.id === "nationality")) {
        evaluateSanityWarnings();
      }
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

  function initSignatureGuard() {
    var form = document.getElementById("guest-form");
    var pad = document.querySelector(".g-sign");
    var canvas = pad && pad.querySelector("canvas");
    var bar = pad && pad.querySelector(".bar");
    var clearBtn = bar && bar.querySelector("button");
    var hidden = document.getElementById("signature");
    if (!canvas || !bar) return;

    var status = bar.querySelector("#sig-status");
    var tracking = false, lastPt = null, totalDist = 0;
    var hasStoredSig = !!(hidden && hidden.defaultValue && hidden.defaultValue.indexOf("data:image/png") === 0);

    function pt(ev) {
      var rect = canvas.getBoundingClientRect();
      var p = ev.touches && ev.touches[0] ? ev.touches[0] : ev;
      return { x: p.clientX - rect.left, y: p.clientY - rect.top };
    }
    function clearSigError() {
      pad.classList.remove("bad");
      var field = pad.closest(".g-field"), err = field && field.querySelector(".g-field-inline-err");
      if (err) err.remove();
    }
    function showSigError() {
      pad.classList.add("bad");
      var field = pad.closest(".g-field");
      if (!field) return;
      var err = field.querySelector(".g-field-inline-err");
      if (!err) { err = document.createElement("p"); err.className = "g-field-inline-err"; err.setAttribute("role", "alert"); field.appendChild(err); }
      err.textContent = strings().signNeeded;
    }
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
      clearSigError();
    }
    function clearSigned() {
      totalDist = 0; hasStoredSig = false;
      var badge = bar.querySelector(".g-sign-ready");
      if (badge) badge.hidden = true;
    }

    canvas.addEventListener("mousedown", function (ev) { tracking = true; lastPt = pt(ev); });
    canvas.addEventListener("touchstart", function (ev) { tracking = true; lastPt = pt(ev); }, { passive: true });
    function onMove(ev) {
      if (!tracking) return;
      var cur = pt(ev);
      if (lastPt) totalDist += Math.hypot(cur.x - lastPt.x, cur.y - lastPt.y);
      lastPt = cur;
    }
    function onEnd() {
      if (!tracking) return;
      tracking = false; lastPt = null;
      if (totalDist >= MIN_SIG_DIST) markSigned();
    }
    canvas.addEventListener("mousemove", onMove);
    canvas.addEventListener("touchmove", onMove, { passive: true });
    canvas.addEventListener("mouseup", onEnd);
    canvas.addEventListener("mouseleave", onEnd);
    canvas.addEventListener("touchend", onEnd);
    if (clearBtn) clearBtn.addEventListener("click", clearSigned);

    if (form) {
      form.addEventListener("submit", function (ev) {
        if (ev.submitter && ev.submitter.hasAttribute("data-lang-draft")) return;
        if (pad.offsetParent === null) return;
        var field = pad.closest(".g-field");
        if (field && field.hidden) return;
        var hasValue = !!(hidden && hidden.value && hidden.value.indexOf("data:image/png") === 0);
        var tooShort = totalDist > 0 && totalDist < MIN_SIG_DIST;
        if (!hasStoredSig && (!hasValue || tooShort)) {
          ev.preventDefault();
          showSigError();
          pad.scrollIntoView({ behavior: "smooth", block: "center" });
        }
      });
    }
  }

  function start() { initCalmValidation(); initSignatureGuard(); evaluateSanityWarnings(); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
