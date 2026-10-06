# UbyHost host-app redesign — implementation handoff

## What this is

Actual Python, Jinja, CSS and JavaScript implementation of the selected simple host workspace. It starts from main `ceb1bc5ed34d020b0c6e21cac3c88bada74d1955` (30 September 2026). It includes the completed stay-fee feature present at that revision. No marketing, login or guest-facing redesign is included.

The separate stay-fee legal-audit branch is not part of this snapshot. Integrate against the newest audited fee implementation; do not replace it wholesale with this baseline. See the conflict rules in `IMPLEMENTATION.md` and `CURSOR_PROMPT.md`.

## Read in this order

1. `CURSOR_PROMPT.md` — copy its entire contents into Cursor after uploading the folder.
2. `IMPLEMENTATION.md` — source ownership, exact data contracts and route coverage.
3. `TEST_REPORT.md` — executed checks, evidence and limits.
4. `docs/HOST_APP_DESIGN.md` — design authority, included in the payload in the upload package.
5. `approved-preview.html` — selected visual reference. The screenshots in `evidence/` show the actual implementation.

## Upload package layout

The downloadable ZIP opens with `docs/plans/host-app-redesign/`. Upload that **folder** under GitHub `docs/plans`, preserving the subfolders. Do not upload only the ZIP and expect the app to execute it.

The package adds these integration files alongside this README:

- `payload/` — exact changed source files, with their repository-relative paths.
- `implementation.patch` — reviewable source diff against the baseline above.
- `manifest.json` — baseline, original-file checksums, resulting-file checksums and modes.
- `apply_handoff.py` — standard-library-only installer. Checks every file before writing. Refuses to overwrite diverged files. Already-applied files are recognized.

These transport files are included in the downloadable upload package; they are not duplicated inside the source checkout. The complete-source ZIP is a separate snapshot of the whole repository, excluding Git metadata, runtime data, caches and local secrets.

## Cursor integration

From the repository root, after reading the prompt:

```bash
python3 docs/plans/host-app-redesign/apply_handoff.py --check
```

If all target files match their baseline or their delivered version:

```bash
python3 docs/plans/host-app-redesign/apply_handoff.py --apply
```

If any file diverges, **no source file is written**. Cursor must merge the intended changes using `implementation.patch` and `payload/`, preserve newer work, then run the complete suite. Do not use forced copying or `git reset --hard` to get past the check. The patch and installer are alternatives; do not apply both blindly.

Review on a feature branch. Existing source behavior and newer fixes must survive. No migration is needed. Deploy only through the repository's owner-approved release process.

## What changes for a host

- Search plus a short rail: Today, Stays, Properties, Invoices, conditional Stay fees.
- Police reports and Guest register under Stays; Business details and Property tools under Properties.
- A compact Today queue and notifications that do not cover mobile content.
- Property settings grouped behind six clear cards, with all current fields preserved.
- Guest identity details visible on the stay. Edit count and Remove extra guest correct accidental empty slots.
- Invoice PDF downloads visible in the list and detail; payment labels describe host records.
- Shared responsive styling across all signed-in destinations, in English and Czech.

Open `evidence/today-desktop.png`, `evidence/stay-mobile.png` and `evidence/invoice-desktop.png` to inspect the running-app result. The yellow banner is the truthful mock-environment indicator in the disposable test workspace.
