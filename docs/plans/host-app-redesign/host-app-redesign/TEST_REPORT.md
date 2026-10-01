# Verification report — 30 September 2026

## Tested source

- Repository: `jsfpechar-ops/jsfpecharoperations`.
- Base main: `ceb1bc5ed34d020b0c6e21cac3c88bada74d1955`.
- Working branch: `codex/host-app-redesign`.
- Python 3.13 on macOS ARM64; actual application code from this checkout, dependencies from an existing project virtualenv. No production data used.
- Local browser app: UbyPort mock, scheduler disabled, console mail, disposable SQLite database, bound to loopback.

## Results

| Check | Result |
|---|---|
| Full pytest suite | **2,068 passed, 2 skipped**, 6 dependency/deprecation warnings. Latest full run: 114.60 seconds. |
| CI coverage invocation | **2,068 passed, 2 skipped; 89.72% coverage**, above required 86%; 107.99 seconds. |
| Runtime lint | `ruff check app tests tools --select E9,F63,F7,F82,F401,F841`: **passed**. |
| JavaScript syntax | `node --check` for host.js and app.js: **passed**. |
| Backup shell syntax | `bash -n scripts/backup_data.sh`: **passed**. |
| Git whitespace validation | `git diff --check`: **passed**. |
| Informational mypy baseline | **95 errors in 22 files** on both baseline and redesigned source. Normalizing line-number shifts produces no added or removed errors. This gate is informational in repository CI; it is not claimed green. |
| Bilingual route rendering | 24 host destinations in EN and CS, checked for HTTP 200, host assets/search, one h1, unique IDs and nonnested/balanced forms. |
| Browser invoice | Validation preserved customer/line fields; local sample issued at **1 234,56 Kč**; real PDF downloaded successfully through Download PDF. |
| Browser interaction | Desktop Search type/Enter to Invoices; mobile drawer focus/Escape; mobile drawer → Search → close restores usable main; property anchors open sections; inline guest details; empty-slot correction. |
| Browser console | No captured application errors during inspected flows. |

The two skips are existing encrypted-backup tests requiring `age` and `age-keygen`, unavailable on this machine. The warnings are existing Starlette/httpx, datetime and Pillow deprecations. No failed tests remain in the measured suite.

## New regression coverage

`App/tests/test_host_redesign.py` exercises:

- Conditional fee navigation using active, accessible properties, including archive/deactivation.
- Contextual destinations and command-palette discovery without host access to admin destinations.
- Empty-slot correction changes only expected count; saved guest rows remain byte-for-byte equivalent.
- Stale replay/double click, inactive stay, attempted actual-guest removal, owner boundary, CSRF/login and a newly filled last slot.
- Fee decision cannot be attributed to a different property even if both properties belong to the same owner.
- Invoice list points to a real PDF attachment and has no inferred bank payment column.
- Exact haler display and fractional quantities.
- Matching English/Czech design translation keys.

The full existing suite also covers login/roles, guest registration/signatures, ownership, calendar imports, reporting, invoices, stay fees, exports, retention, backups and privacy. Existing mock end-to-end behavior is exercised by the suite. No external service was contacted to send a real filing or mail.

## Browser evidence

- `evidence/today-desktop.png` — actual 1280px running host workspace, compact rail and task rows.
- `evidence/stay-mobile.png` — 390px guest details visible inline with direct Edit, count correction and clear primary action.
- `evidence/invoice-desktop.png` — actual issued sample invoice, precise amount and PDF download.

The screenshots deliberately retain the mock-environment banner/marker. They are not screenshots of production. Sample identities and document numbers are fictional.

Browser checks caught and corrected floating notifications obscuring mobile content, stale asset versions, and a drawer-to-Search inert-state interaction. The final navigation script was syntax-checked and browser-checked after the last fix. Python coverage does not measure JavaScript branch coverage.

## Package verification

The delivery additionally checks the generated source package against a clean copy of the baseline:

1. Installer dry-run accepts the baseline without changing files.
2. Installer applies all payload files and verifies every resulting checksum.
3. A second application detects already-applied files and is safe.
4. A deliberately diverged target causes a failure before any source file is changed.
5. The source patch passes `git apply --check` on the baseline.
6. ZIP contents match the generated manifest; runtime database, credentials, .git, virtualenv and caches are excluded.

See `package-verification.json` in the downloadable handoff for measured counts/results.

## Limits and integration requirements

- This tests the implemented redesign against the stated baseline. The separate fee-audit commit `cbbc632` was reported by another task but not merged or tested here. Run combined tests after integrating it; do not overwrite its newer fee semantics.
- No production deployment, live police filing, municipal filing, real bank payment, real email delivery or live-account acceptance test was performed.
- Desktop and mobile checks used the available Chromium-based in-app browser. Safari/Firefox, assistive-technology audits, slow-network behavior and usability sessions with novice/elderly hosts were not separately tested.
- Existing Python type debt and the two encryption-test environment skips remain visible above.
- Shared styling covers signed-in pages; deep operational pages retain their existing field structures. See IMPLEMENTATION.md for targeted versus shared changes.
- No dependency changes were made. A new dependency-advisory audit was not run here; retain the repository's dependency/security CI checks on integration.

This evidence supports a reviewable integration. It is not a claim of perfect software or certification of a future merge.
