// Brief 0412: the /cenik calculator. The server renders 1 apartment, yearly;
// this only updates the numbers. No library, no network, no storage.
(function () {
  "use strict";
  var calc = document.querySelector("[data-pricing-calc]");
  if (!calc) return;
  var rates = JSON.parse(calc.getAttribute("data-rates"));
  var lang = calc.getAttribute("data-lang");
  var signupBase = calc.getAttribute("data-signup-base");
  var MIN = 1;
  var MAX = 50;
  var state = { interval: "year", n: 1, ttlock: false };

  function graduated(n, r) {
    var total = 0;
    for (var i = 1; i <= n; i++) total += i <= 4 ? r[0] : (i <= 9 ? r[1] : r[2]);
    return total;
  }

  function kc(value) {
    var text = String(Math.round(value));
    return text.replace(/\B(?=(\d{3})+(?!\d))/g, lang === "cs" ? " " : ",");
  }

  function fill(pattern, name, value) {
    return pattern.replace("%(" + name + ")s", value);
  }

  function aptsLabel(n) {
    var attr = n === 1 ? "data-apts-one" : (n >= 2 && n <= 4 ? "data-apts-few" : "data-apts-many");
    return fill(calc.getAttribute(attr), "count", String(n));
  }

  function totals() {
    var n = state.n;
    var year = graduated(n, rates.base.year);
    var month = graduated(n, rates.base.month);
    return {
      standard: {
        year: year + (state.ttlock ? rates.ttlock.year * n : 0),
        month: month + (state.ttlock ? rates.ttlock.month * n : 0)
      },
      max: {
        year: year + graduated(n, rates.max.year),
        month: month + graduated(n, rates.max.month)
      }
    };
  }

  function render() {
    var all = totals();
    var yearly = state.interval === "year";
    ["standard", "max"].forEach(function (plan) {
      var card = document.querySelector('[data-plan="' + plan + '"]');
      var t = all[plan];
      card.querySelector("[data-total]").textContent = kc(yearly ? t.year / 12 : t.month);
      card.querySelector("[data-sub]").textContent = yearly
        ? fill(calc.getAttribute("data-billed-year"), "amount", kc(t.year))
        : fill(calc.getAttribute("data-month-hint"), "price", kc(t.year / 12));
      card.querySelector("[data-apts]").textContent = aptsLabel(state.n);
    });
    document.querySelector('[data-plan="standard"] [data-note]').textContent =
      calc.getAttribute(state.ttlock ? "data-std-note-ttlock" : "data-std-note");
    document.querySelectorAll("[data-band]").forEach(function (el) {
      var i = Number(el.getAttribute("data-band"));
      el.textContent = kc(yearly ? rates.base.year[i] / 12 : rates.base.month[i]);
    });
    document.querySelectorAll("[data-unit]").forEach(function (el) {
      el.textContent = calc.getAttribute(yearly ? "data-unit-year" : "data-unit-month");
    });
    calc.querySelector("[data-count]").textContent = String(state.n);
    calc.querySelectorAll("[data-interval]").forEach(function (button) {
      button.setAttribute("aria-pressed", button.getAttribute("data-interval") === state.interval ? "true" : "false");
    });
    calc.querySelector('[data-step="-1"]').disabled = state.n <= MIN;
    calc.querySelector('[data-step="1"]').disabled = state.n >= MAX;
    if (signupBase) {
      document.querySelectorAll("a[data-cta-plan]").forEach(function (link) {
        var plan = link.getAttribute("data-cta-plan");
        var interval = link.getAttribute("data-cta-interval") || state.interval;
        var href = signupBase + "&plan=" + plan + "&interval=" + interval + "&apts=" + state.n;
        if (plan === "standard" && state.ttlock) href += "&ttlock=1";
        link.setAttribute("href", href);
      });
    }
  }

  calc.querySelectorAll("[data-interval]").forEach(function (button) {
    button.addEventListener("click", function () {
      state.interval = button.getAttribute("data-interval");
      render();
    });
  });
  calc.querySelectorAll("[data-step]").forEach(function (button) {
    button.addEventListener("click", function () {
      state.n = Math.min(MAX, Math.max(MIN, state.n + Number(button.getAttribute("data-step"))));
      render();
    });
  });
  calc.querySelector("[data-ttlock]").addEventListener("change", function (event) {
    state.ttlock = event.target.checked;
    render();
  });
  calc.hidden = false;
  render();
})();
