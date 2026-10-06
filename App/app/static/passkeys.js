/* Passkeys (task 0004): add one in Settings or the one-time prompt, and log in
   with one on the login page. Self-served, no third-party code. Every control
   this file drives is hidden until it knows the browser can use a passkey, so
   without JavaScript (or WebAuthn) the e-mail link is simply the only way. */
(function () {
  "use strict";

  var supported = !!(window.PublicKeyCredential && navigator.credentials &&
    typeof navigator.credentials.create === "function");

  var meta = document.querySelector('meta[name="csrf-token"]');
  var csrf = meta ? meta.getAttribute("content") : "";

  function toggleSupport() {
    document.querySelectorAll("[data-passkey-supported]").forEach(function (el) {
      el.hidden = !supported;
    });
    document.querySelectorAll("[data-passkey-unsupported]").forEach(function (el) {
      el.hidden = supported;
    });
  }

  // --- base64url <-> ArrayBuffer ------------------------------------------

  function fromB64url(value) {
    var b64 = String(value).replace(/-/g, "+").replace(/_/g, "/");
    while (b64.length % 4) b64 += "=";
    var raw = atob(b64);
    var bytes = new Uint8Array(raw.length);
    for (var i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
    return bytes.buffer;
  }

  function toB64url(buffer) {
    if (!buffer) return null;
    var bytes = new Uint8Array(buffer);
    var raw = "";
    for (var i = 0; i < bytes.length; i++) raw += String.fromCharCode(bytes[i]);
    return btoa(raw).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  }

  function creationOptions(json) {
    if (typeof PublicKeyCredential.parseCreationOptionsFromJSON === "function") {
      return PublicKeyCredential.parseCreationOptionsFromJSON(json);
    }
    var options = Object.assign({}, json);
    options.challenge = fromB64url(json.challenge);
    options.user = Object.assign({}, json.user, { id: fromB64url(json.user.id) });
    options.excludeCredentials = (json.excludeCredentials || []).map(function (c) {
      return Object.assign({}, c, { id: fromB64url(c.id) });
    });
    return options;
  }

  function requestOptions(json) {
    if (typeof PublicKeyCredential.parseRequestOptionsFromJSON === "function") {
      return PublicKeyCredential.parseRequestOptionsFromJSON(json);
    }
    var options = Object.assign({}, json);
    options.challenge = fromB64url(json.challenge);
    options.allowCredentials = (json.allowCredentials || []).map(function (c) {
      return Object.assign({}, c, { id: fromB64url(c.id) });
    });
    return options;
  }

  function serialise(credential) {
    if (typeof credential.toJSON === "function") {
      try { return credential.toJSON(); } catch (error) { /* fall through */ }
    }
    var r = credential.response;
    var response = { clientDataJSON: toB64url(r.clientDataJSON) };
    if (r.attestationObject) {
      response.attestationObject = toB64url(r.attestationObject);
      response.transports = typeof r.getTransports === "function" ? r.getTransports() : [];
    } else {
      response.authenticatorData = toB64url(r.authenticatorData);
      response.signature = toB64url(r.signature);
      response.userHandle = r.userHandle ? toB64url(r.userHandle) : null;
    }
    return {
      id: credential.id,
      rawId: toB64url(credential.rawId),
      type: credential.type,
      response: response,
      authenticatorAttachment: credential.authenticatorAttachment || null,
      clientExtensionResults: typeof credential.getClientExtensionResults === "function"
        ? credential.getClientExtensionResults() : {}
    };
  }

  // --- talking to the server ----------------------------------------------

  function post(url, body) {
    return fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-CSRF-Token": csrf
      },
      body: JSON.stringify(body || {})
    }).then(function (response) {
      return response.json().catch(function () { return {}; }).then(function (data) {
        if (!response.ok) {
          var error = new Error(data.error || "");
          error.serverMessage = data.error || "";
          throw error;
        }
        return data;
      });
    });
  }

  function showError(scope, error) {
    // The person closed the system sheet: that is a choice, not an error.
    if (error && (error.name === "NotAllowedError" || error.name === "AbortError")) return;
    var box = (scope && scope.querySelector("[data-passkey-error]")) ||
      document.querySelector("[data-passkey-error]");
    if (!box) return;
    box.textContent = (error && error.serverMessage) || box.getAttribute("data-generic") || "";
    box.hidden = !box.textContent;
  }

  // --- adding a passkey ----------------------------------------------------

  function addPasskey(button) {
    var scope = button.closest(".settings-action-list, .security-prompt, .admin-dialog-form") || document;
    button.disabled = true;
    post("/account/passkeys/options")
      .then(function (json) {
        return navigator.credentials.create({ publicKey: creationOptions(json) });
      })
      .then(function (credential) {
        return post("/account/passkeys", { credential: serialise(credential) });
      })
      .then(function (data) {
        window.location.assign(data.redirect || "/settings#settings-security");
      })
      .catch(function (error) {
        button.disabled = false;
        showError(scope, error);
      });
  }

  // --- logging in ----------------------------------------------------------

  var conditional = null;

  function finishLogin(credential, form) {
    var remember = form && form.querySelector('input[name="remember"]');
    var next = form && form.querySelector('input[name="next"]');
    return post("/login/passkey", {
      credential: serialise(credential),
      remember: !!(remember && remember.checked),
      next: next ? next.value : ""
    }).then(function (data) {
      window.location.assign(data.redirect || "/");
    });
  }

  function startConditional(form) {
    if (typeof PublicKeyCredential.isConditionalMediationAvailable !== "function") return;
    PublicKeyCredential.isConditionalMediationAvailable().then(function (ok) {
      if (!ok) return;
      conditional = new AbortController();
      var signal = conditional.signal;
      post("/login/passkey/options")
        .then(function (json) {
          return navigator.credentials.get({
            publicKey: requestOptions(json), mediation: "conditional", signal: signal
          });
        })
        .then(function (credential) {
          if (credential) return finishLogin(credential, form);
        })
        .catch(function (error) {
          if (!signal.aborted) showError(document.querySelector("[data-passkey-login]"), error);
        });
    }).catch(function () { /* no autofill support: the button still works */ });
  }

  function loginWithButton(button, form) {
    var scope = document.querySelector("[data-passkey-login]");
    if (conditional) { conditional.abort(); conditional = null; }
    button.disabled = true;
    post("/login/passkey/options")
      .then(function (json) {
        return navigator.credentials.get({ publicKey: requestOptions(json) });
      })
      .then(function (credential) { return finishLogin(credential, form); })
      .catch(function (error) {
        button.disabled = false;
        showError(scope, error);
        startConditional(form);
      });
  }

  // --- wiring ----------------------------------------------------------------

  function init() {
    toggleSupport();

    var prompt = document.getElementById("security-prompt");
    if (prompt && prompt.hasAttribute("open") && typeof prompt.showModal === "function") {
      prompt.close();
      prompt.showModal();
    }

    if (!supported) return;

    document.querySelectorAll("[data-passkey-add]").forEach(function (button) {
      button.addEventListener("click", function () { addPasskey(button); });
    });

    var loginButton = document.querySelector("[data-passkey-login-button]");
    var loginForm = document.querySelector("[data-login-form]");
    if (loginButton) {
      loginButton.addEventListener("click", function () { loginWithButton(loginButton, loginForm); });
      startConditional(loginForm);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
