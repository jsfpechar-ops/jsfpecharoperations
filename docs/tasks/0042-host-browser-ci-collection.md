# 0042: Restore CI collection for optional host browser modules

Status: review
Report: docs/tasks/0042-host-browser-ci-collection-report.md
Branch: task/host-design-staging | Base: 3ee59854e0a801a054e5d11ebb9d38beacd1e19e
Executor: owner-authorized Luna; Codex orchestrates and reviews.

## 1. Objective

Owner reported CI failure after PR #338 conflict resolution. Diagnose and repair
only collection compatibility, preserving the paused design and required-browser
checks. Do not claim the current design is accepted or all browser tests pass.

## 2. Context

Run 38089667240 fails Run tests with coverage, exit 2. Dependencies, runtime lint,
context and secrets pass. Signed GitHub logs are inaccessible (EOF/403); exact
collection cause must be reproduced. The coverage job installs requirements-dev
without Playwright. Three host modules import it unconditionally, unlike the
existing optional/required contract in test_host_geometry.py. Confirm this is
the cause before changing anything. Read AGENTS.md, status and session exception.

## 3. Files

- App/tests/test_host_controls_browser.py: conditional Playwright import only.
- App/tests/test_host_property_controls_browser.py: conditional import only.
- App/tests/test_host_wide_geometry_browser.py: conditional import and placement
  of the existing REQUIRE_BROWSER flag only.
- App/tests/test_host_geometry.py, App/requirements-dev.txt and
  .github/workflows/ci.yml: read-only reference for the existing contract.
- docs/tasks/0042-host-browser-ci-collection-report.md: exact evidence and results.

## 4. Steps

1. Reproduce collection with the exact head and CI dependencies, no Playwright.
2. If confirmed, use hard import when UBYHOST_REQUIRE_BROWSER=1; otherwise use
   pytest.importorskip as existing modules do. Preserve all assertions and tests.
3. Verify collection/full coverage in the ordinary CI environment. Verify that
   required mode still errors when Playwright is absent; no silent skip permitted.
4. With installed Playwright/Chromium, run the three changed modules in required
   mode. Record any genuine existing WIP failures, without fixing UI here.
5. Write report; tell Codex exactly which checks pass and which remain failing.

## 5. Do not touch

No App implementation, workflow, dependencies, backend, guest access, status,
filters, geometry, or broader design changes. Do not hide an installed-browser
failure, alter assertions, or reduce required-browser checks. 0041 remains blocked.

## 6. Commands

Executor: CI-equivalent pytest collection/full coverage, optional-versus-required
missing-Playwright checks, and required installed-Chromium runs of the named
modules. Preserve exact environment, command, exit status and log locations.
Orchestrator: python3 scripts/context_lint.py and git diff --check only.

## 7. Acceptance

- [ ] Missing optional Playwright no longer produces CI collection errors.
- [ ] Required mode still fails when Playwright is unavailable.
- [ ] Assertions, test selection and application files unchanged.
- [ ] Full ordinary CI coverage and required browser results accurately reported.

## 8. Stop and ask

Report a different root cause or a fix outside the three import blocks to Codex.
Do not resume paused design implementation to obtain a green result.

## 9. Report

Write the explicit Report path, maximum 1,500 tokens. Record prior/final commands,
results, limitations, skips and existing WIP failures; set this brief to review.

## 10. Owner steps

Review the narrow fix and actual CI result. PR #338 remains draft; its known
design failures and hand-picking decisions remain separate from collection.
