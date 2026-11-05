(function () {
  "use strict";

  var collect = document.getElementById("stay_fee_collect");
  var rateInput = document.getElementById("stay_fee_rate_czk");
  var warning = document.querySelector("[data-rate-warning]");
  if (collect && rateInput && warning) {
    var syncRate = function () {
      var rate = parseInt(rateInput.value, 10);
      warning.hidden = !(collect.checked && !(rate > 0));
    };
    collect.addEventListener("change", syncRate);
    rateInput.addEventListener("input", syncRate);
    syncRate();
  }

  var root = document.querySelector("[data-guest-pay-operator]");
  if (!root) return;
  var input = root.querySelector("#stay_fee_guest_operator_account");
  var box = root.querySelector("[data-preview-box]");
  var invalid = root.querySelector("[data-preview-invalid]");
  var account = root.querySelector("[data-preview-account]");
  var qr = root.querySelector("[data-preview-qr]");
  var meta = document.querySelector('meta[name="csrf-token"]');
  if (!input || !box || !invalid || !account || !qr || !root.dataset.previewUrl) return;

  var timer = null;
  var serial = 0;

  function show(data) {
    if (data.ok && data.qr) {
      account.textContent = data.account;
      qr.src = data.qr;
      box.hidden = false;
      invalid.hidden = true;
    } else {
      box.hidden = true;
      invalid.hidden = !data.invalid;
    }
  }

  function refresh() {
    var mine = ++serial;
    var body = new FormData();
    body.set("account", input.value);
    var rate = document.getElementById("stay_fee_rate_czk");
    if (rate) body.set("rate", rate.value);
    fetch(root.dataset.previewUrl, {
      method: "POST",
      body: body,
      credentials: "same-origin",
      headers: { "x-csrf-token": meta ? meta.getAttribute("content") || "" : "" }
    })
      .then(function (response) { return response.ok ? response.json() : null; })
      .then(function (data) { if (data && mine === serial) show(data); })
      .catch(function () {});
  }

  input.addEventListener("input", function () {
    window.clearTimeout(timer);
    timer = window.setTimeout(refresh, 300);
  });
})();
