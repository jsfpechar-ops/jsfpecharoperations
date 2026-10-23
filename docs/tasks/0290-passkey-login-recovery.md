# 0290: Recover passkey login after early taps

Status: review
Depends on: none | Base commit: c830ef5563e02617d07fb8c87f4b2786c6315771 | Branch: fix/passkey-login-recovery
Executor: Codex, directly authorized by the owner on 2026-10-23.

## 1. Objective

Prevent an early passkey tap from leaving login permanently disabled. Cover shared phone, tablet and desktop code, including cancelled autofill and stalled requests.

## 2. Context

Owner reported iPhone login staying unresponsive after tapping before Turnstile completed and explicitly authorized Codex to implement. Application passkey routes do not consume a Turnstile token. Their shared client disabled the button before an unbounded promise chain, created the conditional abort controller only after an asynchronous capability check, and accepted stale conditional credentials after cancellation. The exact production trigger remains unconfirmed.

## 3. Files

- App/app/static/passkeys.js: bounded operations, response checks, conditional cancellation, button recovery.
- App/app/templates/login.html and App/app/templates/base.html: passkeys.js cache key only.
- App/tests/static_versions.json: matching hash and cache version.
- App/tests/passkeys_client_cases.js and App/tests/test_passkeys_client.cjs: deterministic regressions.
- App/tests/test_passkeys_client_browser.py: rendered controls, touch sizes and screenshots.
- .github/workflows/passkeys-client.yml: Node and Chromium/WebKit checks.
- docs/context/status.md, docs/context/known-issues.md, docs/context/decisions.md: task record.
- docs/tasks/0290-report.md: results and limits.

## 4. Steps

1. Bound fetch plus JSON-body reads to 15 seconds; reject redirects, non-JSON and malformed responses.
2. Bound explicit WebAuthn system sheets to 90 seconds, abort timed-out operations, ignore late settlements.
3. Own conditional mediation before checking support; cancel it across options fetching and credential submission. Ignore late cancelled credentials.
4. Restore the login button on completion/failure, hide stale errors on retry, and avoid an automatic extra options request after a failed tap.
5. Bump both live cache references and the manifest.
6. Add 19 deterministic cases and browser runs at 390, 820, 1024, 1180 and 1280 px.

## 5. Do not touch

No server authentication, CSRF, RP ID, origin checks, rate limits, Turnstile validation, dependencies or production settings change. No merge or deploy.

## 6. Commands

- Node: node --test App/tests/test_passkeys_client.cjs
- Browser CI: UBYHOST_REQUIRE_BROWSER=1 PASSKEY_BROWSER=chromium (and webkit) python -m pytest tests/test_passkeys_client_browser.py -q --tb=short -x
- Existing CI covers the login/auth/passkey/security tests, static cache manifest and host geometry/design guards.
- Context: python3 scripts/context_lint.py

## 7. Acceptance

- [x] 19 deterministic cases pass in the tool's V8 runtime; timing/race failures reproduced on the base.
- [ ] Native Node CI passes.
- [ ] Chromium and WebKit: 95 cases each, zero skips, 390 px screenshots.
- [ ] Existing CI and context lint pass.
- [ ] Owner reproduces the original timing on a physical phone after deployment.

## 8. Stop and ask

Report blocked verification honestly if the workspace cannot start. Do not claim real-device reproduction from mocked WebAuthn tests.

## 9. Report

See 0290-report.md. Review requires the full JavaScript diff.

## Risk list

App/app/static/passkeys.js, App/tests/passkeys_client_cases.js, App/tests/test_passkeys_client_browser.py and .github/workflows/passkeys-client.yml.

## Owner steps

1. Review the PR and its CI results.
2. Merge with the repository's green-CI merge script.
3. Deploy manually.
4. On iPhone, tap early, cancel/retry, and check email login still works.
