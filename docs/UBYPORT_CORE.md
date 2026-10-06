# UbyPort reporting — the core function (non-negotiable)

UbyHost exists so accommodation providers can **register foreign guests with the
Czech Foreign Police** through **UbyPort** (`ZapisUbytovane`). Everything else —
backups, mail, guest UX, analytics, staging — supports or surrounds that duty.
**If filing breaks, the product is broken**, even when the rest of the app looks fine.

This document is policy for owners, developers, and agents. It does not replace
the technical contract in the official UbyPort materials (see
`docs/archive/UbyHost_workplan/notes/WP30-dorucenka-pdf.md`).

## What “works” means

For every stay that should be reported, the system must:

1. **Build a request** that matches the UbyPort SOAP contract (member order,
   namespaces, mandatory fields, `VracetPDF` when a Doručenka is required).
2. **Send it once** per successful filing attempt (no double submit; the
   `claim_sendable` / submission state machine is the guard).
3. **Read the response correctly**: header and row errors, `PseudoRazitko` /
   stamp when present, and **`DokumentPotvrzeni`** (base64 PDF) when
   `VracetPDF` was honoured — or **`DokumentChybyPotvrzeni`** when UbyPort
   returns an error PDF.
4. **Persist proof**: submission status, error text for the host, and the
   Doručenka PDF on the submission row when UbyPort returns one (hosts download
   it from the report UI; there is no separate “fetch PDF later” API).
5. **Surface failure honestly**: the host must see that filing failed or is
   incomplete; silent success without a PDF when one was requested is a defect.

Mock UbyPort (`UBYHOST_UBYPORT_ENV=mock`) is for development and Render
staging only. It must stay behaviourally close to the real serializer rules so
CI catches ordering and PDF bugs before production.

## What the police confirmed in writing (2026)

ŘSCP, Oddělení CIS, letters CPR-34587-2/ČJ-2026-930023 (24 September) and
CPR-35040-2/ČJ-2026-930023 (2 October). Technical contact: the officer named in
the letters (service e-mail), or ubyport@pcr.cz. Details and code-level effects:
[OPERATIONS](OPERATIONS.md#ubyport-error-codes-and-what-112-and-150-really-do).

- **Severity decides.** The `DejMiCiselnik(Chyby)` code book is complete and
  binding. Severity 0-2: record accepted. 4-6: not accepted.
- **112 = reported late**, severity 0: accepted. Never resend it.
- **Duplicates** are keyed on dates from-to, surname, first name, birth date,
  nationality, document number and purpose (not note, visa or address). A
  duplicate answer proves an earlier accept. No limit, but error rates are watched.
- **Do not auto-resend refused records**: repeated refusals raise the host's
  error count and the police contact the host. Fix the data, then send only the
  refused records again, in a new batch.
- **No receipt** = the request did not match the WSDL or did not arrive. If a
  record arrived but the receipt was lost, ask the police for it by data box or
  e-mail. Records marked accepted in a Doručenka are filed.
- **Batch**: at most 32 records (`MaximalniDelkaSeznamu`), no daily limit.
  `TestDostupnosti` checks the service and its backend.
- **Test environment** behaves exactly like production and is used for the
  police check test that approves a new application. A UBY-WS test account was
  issued on 6 October 2026 (kept outside git).

## Features that must stay aligned with filing

Treat these as **one system** with UbyPort. A bug in any of them can mean wrong
or missing police data:

| Area | Code / behaviour | If it breaks |
|------|------------------|--------------|
| SOAP client | `App/app/ubyport/soap.py`, `client.py` | Requests rejected or PDF flag dropped |
| Auto-submit & scheduler | `worker`, reservation automation | Stays never filed or filed twice |
| Resend after interrupt | WP31 / submission retry rules | Duplicate or missing filings |
| Doručenka storage & download | `receipt_pdf`, report routes, WP30 | Host has no legal proof of filing |
| Filing watchdog & heartbeats | WP23, `UBYHOST_HEARTBEAT_*` | Failures go unnoticed |
| Manual “filed in UbyPort” mark | WP23 | House book and UI disagree with police |
| Guest data → UbyPort mapping | validation, codelists, encryption at rest | Wrong data sent to police |
| Transactions | `db.immediate()` — **no UbyPort inside** | Corrupt state or double send |

Guest forms, e-mail, and translations must **not** change field semantics or
requiredness in ways that produce invalid `ZapisUbytovane` payloads. UI-only
changes still need the guest browser e2e when templates change.

## What is *not* allowed to trade off against filing

- Shipping a “nice” refactor or feature without running filing-related tests.
- Merging a PR that touches `ubyport/` or submission flow without the owner
  **Gate 2** check when the workplan requires it (test filing + Doručenka PDF).
- Deploying to **`UBYHOST_UBYPORT_ENV=prod`** before **`test`** filing and PDF
  behaviour are verified on the same code revision.
- Assuming a past Doručenka on old rows means new filings work — **verify after
  every change** to SOAP, worker, or automation.
- Optional infrastructure (e.g. **Litestream off**, shorter backup retention)
  is acceptable for a deploy window; **incorrect or missing UbyPort traffic is not**.

Backups and Litestream protect the database; they do **not** replace correct
real-time filing or stored Doručenka PDFs.

## Verification (owner and CI)

**Automated (every PR):**

- Full pytest suite in `App/` (includes SOAP/order tests, submission tests,
  end-to-end paths against mock UbyPort).
- CI `smoke` and, when guest templates change, guest browser e2e.

**Owner gates (workplan):**

- **Gate 2** (after Doručenka / resend patches): one stay filed with
  `UBYHOST_UBYPORT_ENV=test`; report shows **Download Doručenka (PDF)** and the
  file opens. If UbyPort rejects the request or no PDF is stored, **stop** and
  fix before later merges.
- **UbyPort submit heartbeat** (`UBYHOST_HEARTBEAT_URL`): alerts when automatic
  filing stops succeeding in production.

**After deploy to production:**

- Spot-check one real or test filing when the release touched filing code.
- If the report shows success but no PDF when you expect one, treat it as
  **P0**: check Technical details on the submission and application logs
  (`ubyhost.ubyport`), not only the green UI state.

## Guidance for code changes

1. Read `AGENTS.md` (database + transaction rules) and this file before editing
   `App/app/ubyport/`, claim/submission logic, or automation that calls UbyPort.
2. Prefer the smallest diff; never reorder SOAP members for “cleanliness”.
3. Add or extend tests when behaviour changes; mock server must reflect contract
   ordering (see WP30 notes).
4. In PR descriptions, state explicitly whether filing behaviour changed and
   how it was tested (mock / test endpoint / owner Gate 2).

## Related docs

- `docs/DEPLOYMENT.md` — environments; prod vs mock/test.
- `docs/archive/UbyHost_workplan/OWNER_MANUAL_SETUP.md` — Gate 2 and per-patch checks.
- `docs/archive/UbyHost_workplan/notes/WP30-dorucenka-pdf.md` — Doručenka root cause.
- `docs/UbyHost_workplan/compliance/05_manual_filing_fallback.md` — when the
  host files by hand in UbyPort.
