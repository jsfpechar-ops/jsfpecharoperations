# Cursor task: integrate the tested UbyHost host-app redesign

Implement this handoff in the actual application. Finish the code integration, tests and reviewable feature branch. Do not respond with another design proposal. The approved result is the simple host workspace in this package.

## Inputs and authority

Start in the repository root. Read `AGENTS.md`, `docs/DESIGN.md`, then these files under `docs/plans/host-app-redesign/`:

1. `README.md`
2. `IMPLEMENTATION.md`
3. `TEST_REPORT.md`
4. `payload/docs/HOST_APP_DESIGN.md` (or the applied `docs/HOST_APP_DESIGN.md`)
5. `manifest.json`, `implementation.patch`
6. `evidence/` screenshots and `approved-preview.html`

This is working implementation source, not only mockups. The baseline is `ceb1bc5ed34d020b0c6e21cac3c88bada74d1955`. Runtime code belongs at the repository paths inside `payload/`, never only under `docs/plans`. The preview's fake data/actions must never be copied into application logic.

The selected design supersedes the older host navigation layout. Preserve current legal, data, security and business behavior. The source screenshot is the implementation reference; the HTML is the visual direction. Do not try to reproduce its fake counts instead of real application state.

## 1. Inspect before applying

- Read `git status --short`, current branch, HEAD and remote main. Preserve uncommitted user work. Create an integration branch from current main in an available clean checkout; do not reset or overwrite another task's checkout.
- Inspect changes since the baseline in files named by the manifest. Do not assume that a clean patch apply proves semantic compatibility with later code.
- Check for the separate stay-fee legal audit. Another task reported commit `cbbc632` on `fix/stay-fee-legal-audit`; verify its full commit and final tests yourself. Preserve newer per-facility report units, finalized snapshots and protected-register data requirements. This redesign was tested on the baseline fee feature and does not certify that later combined merge.
- When the source is already integrated, verify it instead of applying twice.

## 2. Apply exact source when compatible

From the repository root:

```bash
python3 docs/plans/host-app-redesign/apply_handoff.py --check
```

If every source path is baseline-identical or already delivered:

```bash
python3 docs/plans/host-app-redesign/apply_handoff.py --apply
```

The installer verifies payload hashes and original hashes before writing. It is idempotent. If any file diverges, it exits without changing source. Do not bypass the check, force-copy `payload/`, or reset main to the older baseline.

For diverged files, merge the individual changes in `implementation.patch` into the current source. Use payload files to inspect the complete intended result. Preserve newer fields/routes/validations, and record each substantive conflict resolution. The patch is an alternative review/application path; don't apply it after the installer has already applied the same changes.

## 3. Required implementation result

### Shell and navigation

- Keep FastAPI/Jinja and plain CSS/JS. No SPA, bundler, dependency or dark mode.
- Load host.css/host.js after shared assets only for the signed-in navigation shell. Preserve the `host-workspace` boundary and CSS alias rebinding.
- Desktop rail 216px: Search, Today, Stays, Properties, Invoices; Stay fees only if an active, accessible, nonarchived property has a positive rate.
- Stays local tabs: Stays / Police reports / Guest register.
- Properties local tabs: Properties / Business details; Property tools menu contains Guest links and Automation.
- Help/account at the bottom; Settings, archive, privacy, language, sign out and role-aware administration remain reachable. Search must include destinations removed from the rail. Preserve environment and impersonation context.
- Mobile drawer must release main-content inert state when Search or shortcuts open. Close with Escape, restore trigger focus, trap Tab only while the drawer is actually open. Preserve collapsed rail and browser asset-version updates.

### Today, stays and guest details

- Date + Today + truthful action count. Compact rows contain property, dates/urgency, one concise state and an Open stay action.
- Keep existing queue order, failed/unknown states, setup links, empty states and calendar operations. Do not fabricate successful reporting.
- Guest cards show identity/document facts inline and a direct Edit action. Keep stay source and dates visible.
- Edit count and Remove extra guest must be visible where applicable. Preserve the exact owner/CSRF/atomic compare-and-update contract in IMPLEMENTATION.md. Never delete a saved guest as a shortcut for fixing expected headcount.
- Removing an empty slot can complete a stay; retain the confirmation and existing automatic-reporting opt-in behavior.
- Put the real police-report section after guests; keep real deadlines/results/downloads and anchors. Do not show technical mode boilerplate in the summary.

### Properties, business, setup and advanced screens

- Keep the six-card property hub and existing fields inside their original form. Closed sections remain submitted; partial edits must not erase other settings.
- Business records remain shared legal entities, linked through `/entities?edit={id}`. Do not clone entities per property.
- Calendar/guest link/reporting/automation/fee tools are contextual; existing global overviews remain accessible.
- A first host can set up a property and add a stay without invoices or stay fees. Fee remains optional.
- Preserve shared styling and reachable actions on reports, register, guest forms, settings, archive, privacy, team, incidents, guide and onboarding. Do not erase advanced controls to make screenshots cleaner.

### Invoices and stay fees

- Keep standalone invoice creation; the stay's invoice link opens the builder without pretending there is a stored stay association.
- Preserve 422 state, seller selection, VAT, numbering, immutable issued snapshots, cancellation/correction, e-mail and signed/authenticated PDF downloads.
- Show PDF links in invoice list/detail. Manual payment state says Payment recorded / No payment recorded, never bank-monitoring status.
- Keep exact decimal amounts; do not restore `// 100` truncation in display.
- Preserve the newest audited fee calculation/export/snapshot behavior. Apply UI to it instead of copying older domain code over it.
- Fee appears only as property opt-in + dedicated workspace section; no guest fee flow, no stay-detail fee card, no fee onboarding requirement.
- QR means payment details available, not paid or filed. Keep blockers and recovery links. Do not infer municipal filing or bank settlement.
- Preserve the guest-to-selected-property association check in the fee-decision endpoint.

## 4. Test the actual resulting code

Run from `App/` using a project virtualenv. Do not set `PYTHONPATH=App` on macOS. Follow the repository's supported Python version and pinned requirements. If preparing a fresh environment:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements.lock
.venv/bin/python -m pip install -r requirements-dev.txt
```

Run the same CI gates:

```bash
.venv/bin/ruff check app tests tools --select E9,F63,F7,F82,F401,F841
UBYHOST_UBYPORT_ENV=mock UBYHOST_DEPLOYMENT=staging UBYHOST_ENABLE_SCHEDULER=0 .venv/bin/python -m pytest tests -q --cov=app --cov-report=term-missing --cov-fail-under=86
node --check app/static/app.js
node --check app/static/host.js
bash -n scripts/backup_data.sh
```

Also run the repository's informational mypy invocation and compare against the branch's baseline. Do not describe existing baseline errors as clean. Run `git diff --check` from repo root. Follow any additional current CI gates, including dependency/security checks required by the repository; do not disable them to get green.

`tests/test_host_redesign.py` covers rendered structure in EN/CS, discoverability, conditional fee navigation, empty-slot mutation/replay/CSRF/ownership/new registration, invoice PDF and decimal display, and fee decision association. Keep those checks. Older visual assertions were updated for the chosen layout; business/security assertions must not be weakened to pass a redesign.

Run the full suite after resolving fee-audit overlaps. Prior 2,068-test results are evidence of this snapshot only, not a substitute for testing the merged branch.

## 5. Browser acceptance on disposable local data

Run the actual app against a disposable database, scheduler off, mail console, UbyPort mock, bound to localhost. Never use production guest data or send real reports/email for visual testing.

Verify desktop at 1280px, tablet around 1024px and phone at 390px (also check 360px for overflow). Exercise:

1. Today → Stays → stay: short copy, source/date orientation, readable inline document details.
2. Remove an accidental empty guest slot: expected count decreases once, saved guests remain; stale repeat does not remove another. Edit actual guest separately.
3. Properties → property hub → each settings section, repeated anchor click, failed validation inside a closed section, save and reload values in another section.
4. Business details, guest links and automation reachable through Properties and Search.
5. Generate a sample invoice; verify a failed validation preserves form fields, issue it locally, download a real PDF and verify decimal total.
6. Fee disabled/enabled properties, period detail, blockers, PDF/CSV/QR and exemption behavior allowed by the newest audited backend.
7. Search keyboard open/type/Enter/Escape; mobile menu → Search → close must leave main interactive; focus trap and collapsed rail.
8. Notifications expand/dismiss without covering content or losing important errors.
9. English/Czech, host/admin roles, empty/partial/failed/long-name states, no page-level horizontal overflow.
10. No browser console errors. Save screenshots showing actual changed screens.

If a check fails, fix the underlying implementation and rerun the relevant gate. Do not stop at a screenshot or syntax check.

## 6. Deliver and stop

Update TEST_REPORT.md with your actual environment, counts, coverage, conflicts resolved and remaining limitations. Keep the design documentation aligned with the source. Review the diff for unintended files, secrets, sample runtime databases, broken exports and unrelated removals. Commit on the integration branch with repository-required attribution. Prepare a reviewable PR only if the user's current instruction authorizes it; never merge or deploy without the owner's release instruction.

Your final response must state: source branch/commit, actual implemented scope, test/coverage results, current audit integration status, screenshot links and any precise remaining blocker. Avoid “perfect”, “everything is guaranteed” or “production verified” unless evidence actually supports that statement. Finish the working implementation rather than handing the owner another plan.
