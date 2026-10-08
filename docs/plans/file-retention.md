# Stored files: keep for a set time, host downloads before a deadline

Status: draft v2 for owner discussion, council-lite reviewed (§0, §10). **Owner 2026-10-08: no Files page; invoices stay 10 years; storage module only when a new large file kind is planned (§0a).** Earlier recommendation: Path R (§0). Option B (§5–§7, deletion) is kept only as a corrected design in case the owner still wants it.** No brief runs until the owner answers §9.
Risk: **HIGH** (data deletion and legal copy). Owner: Josef. Written 2026-10-08.

## 0. Council verdict and recommendation (read this first)

Three advisors (Contrarian, First Principles, Executor) reviewed v1 independently. All three reached the same core conclusion, and the code confirms their factual points:

1. **The space saving is not real.** A few KB per document, and NULLing a BLOB does not shrink the database or the backups without `VACUUM`.
2. **Deleting original invoices is the wrong trade.** The privacy policy promises 10 years (`privacy_policy_i18n.py:142`), hosts treat the app as their archive, and a reprint is not the byte-identical original the host must keep under § 34/§ 35 zák. 235/2004 Sb. The privacy gain is small because the invoice row (buyer name, address) stays anyway. The cost is a contract change, a lawyer gate and a weaker immutability trigger, all for a few dollars.
3. **Stay-fee files already expire at 6 years** (v1 said "indefinitely"; corrected in §2).

**Recommendation, Path R (2 briefs, no deletion, no Terms change):**

- **R1 `0019-host-archive-export`:** a "Files" page (`/files`) listing the host's stored documents (invoice PDFs, stay-fee PDF/CSV) with "Download all (ZIP)" + `MANIFEST.csv` (file name, kind, number/period, SHA-256, created). The host can keep their own archive any time, which also answers lock-in worries. Reuses the zip-on-disk-then-unlink pattern of `routes/exports.py:144`. Host-only, IDOR-tested, works without JS.
- **R2 `0020-storage-module`:** `App/app/storage.py` with `put(kind, owner_id, bytes) -> key`, `get`, `delete`, and a per-kind `ttl_days` (None = keep). Binaries are encrypted files under `DATA_DIR/files/` (pattern of `passport_photos.py`), not SQLite BLOBs. **No existing kind moves.** The rule (a decision line): every *new* large file kind (TTLock exports, reports, attachments) uses this module and declares its TTL and its legal basis when it is designed. That is the future-proofing, with the deadline-and-reminder UI built the first time a kind with a TTL exists.
- **Optional R3 (ops, owner):** if backup size ever matters, a monthly `VACUUM` + compression in `backup-s3.sh` is the real lever, not deleting documents.
- **Invoices: unchanged, 10 years, original PDF kept.** Stay-fee files: unchanged, 6 years.

If the owner still wants deletion (Option B below), the council's corrections in §10 are mandatory, and it must start with a written lawyer opinion on L3/L4 before any code.

## 0a. Owner decisions and corrections (2026-10-08)

- **Files page (R1): dropped** by the owner.
- **Invoices stay 10 years.** Correction to §4 L3: the "10 years" line in the privacy policy (`privacy.own_retention_body`, privacy_policy_i18n.py:142) covers **UbyHost's own invoices to hosts**, where the law binds UbyHost (§ 35 zák. 235/2004 Sb. if UbyHost is a VAT payer). Host-issued invoices are not promised in the Terms or DPA; their 10 years is the app's own choice (`invoices.purge_expired`), matching the host's longest duty. It stays: the cost is tiny and a shorter period only adds risk.
- **Storage module (R2): not now.** Correction to §0: the TTLock plan creates no files, so no large file kind is planned. Rule instead (decision line): the first new kind of stored file gets the storage module in its own brief, with its keep-period and legal basis.
- To add in the legal-copy round (lawyer): one Terms/DPA sentence that the app is not the host's statutory archive and the host keeps their own copies.

## 1. Goal

Binary files (PDFs, CSVs, ZIPs) are kept in the app for a known period only. From the moment a file is created, the host sees the date it will be removed, gets reminders, and can download one file or everything in one ZIP. After the deadline the binary is deleted; the structured record the law requires stays. This keeps the database and every backup small and gives one lifecycle that all future file types (TTLock exports, larger reports) plug into.

## 2. What the app stores today (checked in code, 2026-10-08)

| File | Where | Who creates it | Controller | Statutory duty (whose) | Kept today |
|---|---|---|---|---|---|
| Issued invoice PDF (host → guest) | `invoice.pdf_blob` + `pdf_sha256` (SQLite BLOB) | host, invoice tool | **host**; UbyHost processor | VAT § 35 zák. 235/2004 Sb. (10 y, VAT payers); accounting § 31 zák. 563/1991 Sb. (5 y) — **the host's** | 10 years, row + PDF, immutable (`invoice_issued_guard`, `invoices.purge_expired`) |
| Stay-fee period PDF + CSV | `stay_fee_filing.pdf_enc`, `csv_enc` (encrypted BLOB); data in `payload_enc` | host seals a period (`stay_fee_filing.save`) | host | stay-fee book 6 y, § 3g(4) zák. 565/1990 Sb. — **the host's** | 6 years: `retention._stay_fee_records_step` (retention.py:120) deletes whole rows on the guest cutoff |
| Passport / ID image | `DATA_DIR/passport_photos/` (encrypted file) | guest | host | none (proportionality) | ≤ 30 days after stay end. **Out of scope, already short.** |
| Guest form PDF, UbyPort receipt / errors PDF | rendered on request | — | — | — | **not stored.** Out of scope. |
| Workspace / house-book ZIP | temp file, unlinked after streaming | — | — | — | **not stored.** Out of scope. |
| UbyHost's own invoices to hosts | (billing not built yet) | UbyHost | **UbyHost** | 10 y, UbyHost's own duty | must never expire early (§4 L7) |

Only two file kinds exist today: invoice PDFs and stay-fee PDF/CSV. Everything lives inside the SQLite file, which Litestream replicates and `backup-s3.sh` copies to S3 (30-day lifecycle) and Drive.

**Honest cost picture.** A reportlab invoice is about 5–30 KB. 10,000 invoices ≈ 0.2 GB; S3 Standard ≈ $0.023/GB-month, times about 30 daily snapshots. The saving today is a few dollars a month, and **setting a BLOB to NULL does not shrink the SQLite file**: freed pages are only reused, and Litestream and `backup-s3.sh` still copy the full file unless a `VACUUM` runs (none runs today). The real reasons to do this are (a) the DB and every backup grow without bound as hosts issue documents, (b) restores get slower, (c) less copies of guests' names and addresses lying around (GDPR storage limitation), and (d) one lifecycle ready for bigger files later. The plan is scoped to match: small, safe, no new dependency.

## 3. Principle

**Renderings expire; records do not.** The binary is a rendering of rows we keep for the statutory period. After the deadline the host can still get a **reprint** generated from the stored data, clearly marked "Copy / Kopie — reprinted <date>, original SHA-256 <hash>". The host never loses the content; they lose only the byte-identical original, and only after we told them several times.

## 4. Legal review (counsel memo, for the lawyer to confirm)

I'm giving the owner my best legal analysis; it is not a substitute for the engaged lawyer, and the copy in F5 stays **LAWYER REVIEW** (new row K-L10).

- **L1 Roles.** For invoices the host issues and for stay-fee records, the host is the controller and bears the storage duty; UbyHost is a processor (Art. 28 GDPR, our DPA). The statutory archive duty does not move to UbyHost because we host the file. Our duty is to do what the DPA says and not lose data contrary to it.
- **L2 Shorter storage is allowed if it is the documented instruction.** Art. 28(3)(a) and (g): the processor acts on documented instructions and deletes or returns data at the end. A DPA/Terms clause "the app keeps files for N months; the archive is your responsibility; export before the date shown" is a valid documented instruction. It must be in the DPA, the Terms and visible in the UI, not only in a help page.
- **L3 Existing hosts.** Today's privacy policy says invoices are kept 10 years, and the host's reasonable expectation is that the app is their archive. Applying a shorter period to files already stored is a change to the contract. It needs: new Terms/DPA version, active acceptance (the existing `legal_acceptance` flow), and a notice period of at least 30 days (§ 1752 OZ; for any host who is a consumer, § 1814 unfair-terms risk if the change is a surprise). **No existing file may expire earlier than 90 days after the host accepted the new version.**
- **L4 Invoice integrity.** § 34 zák. 235/2004 Sb.: the issuer must keep the invoice with authenticity, integrity and legibility for the full period. Once the host has downloaded the original, the host keeps those properties. A reprint is a copy, not the original. Our UI must say this plainly, and the download must carry the SHA-256 so the host can prove integrity of their copy. Penalty risk for a host who loses invoices (§ 247 daňový řád, up to 500,000 CZK) is the host's, but it is our reputational and contract risk; hence reminders and the "not downloaded" safety rule (L9).
- **L5 Stay-fee records.** § 3g(4) zák. 565/1990 Sb. requires the evidence book entries for 6 years. The book is the structured data (`payload_enc`, guest rows), which stays. The sealed PDF/CSV is a convenience copy; expiring it is low risk.
- **L6 GDPR upside.** Art. 5(1)(c) and (e): fewer copies of buyer names/addresses. This supports, not weakens, our privacy-first claim; the copy must not overclaim ("we delete your invoices" is false; "we delete the stored PDF file, the invoice data stays for 10 years" is true).
- **L7 What never expires early.** Anything UbyHost itself must keep (its own invoices to hosts, `legal_acceptance`, audit rows), and the structured statutory records (guest book, stay-fee data, invoice rows). The new mechanism handles host-owned binaries only, and refuses any `kind` not on an allow-list.
- **L8 Irreversibility.** Backups keep a deleted file up to 30 days (G-D3). The copy says "removed from the app on <date>, from backups within 30 days". We never restore an expired file from backup for a host except in a disaster restore.
- **L9 Safety rule.** If a host never downloaded a file and has not opened the app since the first reminder, we extend once by 90 days and send a final mail. The total extension is capped so the rule stays predictable (one extension only).
- **L10 Account closure.** Unchanged: export offered, then deletion per K-L01. Expiry never runs after a closure request is open (the closure flow owns the data then).
- **Verdict:** lawful and defensible if all of these hold: (1) records stay, only renderings go; (2) the date is shown from creation; (3) at least three reminders; (4) one-click bulk export; (5) Terms + DPA + privacy policy updated and accepted; (6) every deletion audited by id and hash; (7) existing files get ≥ 90 days after acceptance; (8) the job ships dry-run behind a flag.

## 5. Option B design (not recommended; corrected per §10)

### 5.1 Data model (migration `0007_stored_file.sql`, Postgres-portable SQL via `db.py` helpers)

```sql
CREATE TABLE IF NOT EXISTS stored_file (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_user_id    INTEGER NOT NULL REFERENCES user_account(id),
    kind             TEXT NOT NULL,          -- 'invoice_pdf' | 'stay_fee_pdf' | 'stay_fee_csv'
    ref_id           INTEGER NOT NULL,       -- invoice.id or stay_fee_filing.id
    size_bytes       INTEGER NOT NULL,
    sha256           TEXT NOT NULL,
    created_at       TEXT NOT NULL,
    expires_at       TEXT NOT NULL,          -- UTC ISO; set at creation, only ever moved later
    first_downloaded_at TEXT,
    last_downloaded_at  TEXT,
    reminder_stage   INTEGER NOT NULL DEFAULT 0,  -- 0 none, 1 = 30 d, 2 = 7 d, 3 = 1 d sent
    extended_at      TEXT,                   -- L9, set once
    expired_at       TEXT,                   -- binary removed
    UNIQUE (kind, ref_id)
);
CREATE INDEX IF NOT EXISTS idx_stored_file_due ON stored_file (expired_at, expires_at);
CREATE INDEX IF NOT EXISTS idx_stored_file_owner ON stored_file (owner_user_id, expires_at);
```

The binary stays where it is (`invoice.pdf_blob`, `stay_fee_filing.pdf_enc/csv_enc`). `stored_file` is the lifecycle ledger only. Moving binaries out of SQLite is a separate, optional brief (F6).

`retention.py` gets a line for `stored_file` (it holds no personal data: ids, sizes, hashes, dates), and RETENTION.md a row.

### 5.2 Periods (`App/app/file_retention.py`, constants, owner can change by env later)

| kind | expires_at | Why |
|---|---|---|
| `invoice_pdf` | 31 December of the year **after** the issue year, 23:59 Europe/Prague (12–24 months) | covers the annual tax return and the adviser deadline (1 July) for the issue year |
| `stay_fee_pdf`, `stay_fee_csv` | 31 December of the year after the period end | same rhythm; the fee return to the municipality is due long before |
| backfill of existing files | `max(rule above, acceptance date of new terms + 90 days)` | L3 |

Owner may pick another rule in §9 Q1; everything reads one function `expires_for(kind, created_at)`.

### 5.3 Expiry of the binary

- Invoice: a new migration trigger change. `invoice_issued_guard` keeps every column except `pdf_blob`; a new `invoice_pdf_expire_guard` allows `UPDATE invoice SET pdf_blob = NULL` only when `settings.invoice_pdf_expire_unlock = '1'` and `NEW.pdf_blob IS NULL`; any other change to `pdf_blob` still aborts. `pdf_sha256` never changes (it is the proof).
- Stay fee: `UPDATE stay_fee_filing SET pdf_enc = NULL / csv_enc = NULL`. `payload_enc` stays.
- Each expiry: `stored_file.expired_at = now`, `db.audit("file_expired", "kind=… ref=… sha256=…")` (ids and hash only, never names).
- The step runs in `retention.run` and obeys the same dry-run switch plus its own flag `UBYHOST_FILE_EXPIRY=1` (default off). Dry run logs counts only.
- Guards: never expire if the owner account has a closure request open (L10); never for a kind not in `ALLOWED_KINDS`; batch of at most 500 per run.

### 5.4 Reprint after expiry

`invoices.download_pdf` today raises `invoice_pdf_missing`. New `invoices.reprint_pdf(invoice_id)` renders from the immutable row with a banner "KOPIE — vytištěno <date> z uložených údajů. Originál SHA-256: <hash>" / English equivalent. Stay fee: render from `payload_enc` with the same banner. The download route serves the original while it exists, otherwise the reprint, and the page says which one you get.

### 5.5 Host UI

- **New page "Files"** (`/files`, host nav under Settings next to Archive): table of stored files, newest first, with kind, document number/period, size, "removed on <date>", downloaded yes/no. Filters chips: all / not downloaded / removing within 30 days. Buttons: download one; **"Download everything not yet downloaded (ZIP)"**; "Download all (ZIP)". The ZIP is built on disk and unlinked after streaming (same pattern as `routes/exports.py:144`) and includes `MANIFEST.csv` (file name, kind, number, sha256, created, removal date).
- Invoice detail and stay-fee period pages: one line "Stored PDF is kept until <date>. Download it for your records." Once expired: "The original was removed on <date>; you get a reprint marked as a copy."
- Dashboard: one banner only when files are removed within 30 days and not downloaded ("3 files will be removed on 31 Dec. Download them") linking to `/files?filter=soon`. No JS needed; forms work without JS (rule 6).
- Download (single or ZIP) sets `first/last_downloaded_at`. Admin preview downloads must **not** count as the host's download.

### 5.6 Reminders (transactional mail through `mail_notify`, never blocked by marketing unsubscribe)

Per owner, one digest mail per stage (not per file): 30 days, 7 days, 1 day before the earliest removal of files **not downloaded**. Files already downloaded get no reminder. L9 extension: if at the 1-day stage the host has not logged in since stage 1, move those files' `expires_at` by 90 days once, set `extended_at`, send "final notice". Mail lists counts and the link, never guest names.

## 6. Briefs for Cursor (run in order; each one PR)

| # | Brief | Depends | Main files | Behaviour change |
|---|---|---|---|---|
| F1 | `0019-stored-file-ledger` | — | `migrations/0007_stored_file.sql`, `file_retention.py` (new), `invoices.py` (register on issue), `stay_fee_filing.py` (register on seal), `retention.py` (line only), backfill function + CLI `python -m app.file_retention backfill --dry-run` | none visible; ledger rows created |
| F2 | `0020-files-page-and-download-tracking` | F1 | `routes/files.py` (new), `templates/files.html`, `_host_navigation.html`, invoice/stay-fee download routes (track), `host_i18n.py` | page + tracking; nothing deleted |
| F3 | `0021-file-reminders` | F2 | `file_retention.py`, `mail_notify.py`, `scheduler.py` (daily), `templates/dashboard.html` banner, i18n | mails + banner; nothing deleted |
| F4 | `0022-file-expiry-job` | F3 + F5 accepted | migration `0008_invoice_pdf_expire_guard.sql`, `file_retention.py` expire step, `retention.py` call, `invoices.reprint_pdf`, stay-fee reprint, `ENVIRONMENT.md` `UBYHOST_FILE_EXPIRY` | deletion, **dry-run by default** |
| F5 | `0023-file-retention-legal-copy` | — (parallel) | `terms_i18n.py`, `dpa_i18n.py`, `privacy_policy_i18n.py`, `guide_i18n.py`, legal version bump, `docs/privacy/RETENTION.md`, `docs/privacy/ROPA.md` | new Terms version; **LAWYER REVIEW** |
| F6 | optional later `00xx-blob-storage-backend` | F4 | move binaries to encrypted files under `DATA_DIR/files/` behind a `storage.put/get/delete` interface, S3 later | none visible |

Per-brief detail the executor needs (the orchestrator writes each brief from this when the owner says go):

**F1 tests** (`tests/test_file_retention.py`): issuing an invoice creates one `stored_file` with the right sha256 and `expires_at`; sealing a stay-fee period creates two; `expires_for` for an invoice issued 2026-03-10 returns 2027-12-31T22:59:59Z (CET) and for 2026-12-31 returns 2027-12-31; backfill is idempotent (run twice → same row count) and honours the "acceptance + 90 days" floor; a `kind` outside `ALLOWED_KINDS` raises.

**F2 tests:** host sees only own files (IDOR test with a second host → 404); ZIP contains every file + `MANIFEST.csv` with matching hashes; download sets `first_downloaded_at` once and `last_downloaded_at` every time; admin-preview download leaves both NULL; page works without JS; browser + geometry tests 0 skipped, screenshots 360/390/1280.

**F3 tests:** with a frozen clock, stage 1/2/3 mails send once each, only for not-downloaded files, one digest per host; downloaded files cancel later stages; L9 extends once and never twice; mail body contains no guest name (assert the seeded buyer name is absent).

**F4 tests:** with the flag off, nothing changes and the log has counts; with the flag on, due binaries become NULL, `expired_at` set, audit row has id and hash; the invoice trigger still aborts any other column change and any non-NULL `pdf_blob` update; a closure-pending owner is skipped; download after expiry returns the reprint with the "KOPIE" banner and the original hash; `invoices.purge_expired` (10-year rule) still works on rows whose PDF already expired.

**F5:** wording drafted by the orchestrator, marked LEGAL-GATED, shipped only after the lawyer signs; the Terms version bump forces re-acceptance through the existing flow; `privacy_first.*` brand copy checked for truth (rules: privacy).

## 7. Rollout

1. F1–F3 merge and deploy. Nothing is deleted. Watch the Files page and reminder mails on staging (Render) with demo data.
2. Lawyer signs F5; deploy F5; hosts accept the new Terms.
3. F4 deploys with `UBYHOST_FILE_EXPIRY` unset → dry-run counts in the log for at least one month.
4. Owner sets `UBYHOST_FILE_EXPIRY=1` on production. First real removal can be no earlier than acceptance + 90 days, and with the default rule not before 31 December 2027 for anything issued in 2026.

## 8. Do not touch

UbyPort filing code and `submit_state`; the 10-year `invoices.purge_expired` rule; `passport_photos.py`; guest pages; `legal_acceptance` and audit retention; backups scripts.

## 9. Questions for the owner

0. **Path R (recommended) or Option B (deletion)?** If R, only questions 5 applies.
1. (Option B) Period rule: "31 Dec of the year after creation" (recommended), or a flat N months (e.g. 13)?
2. Reprint after expiry: yes (recommended, lowest legal risk) or "gone for good"?
3. L9 one-time 90-day extension for hosts who never logged in: keep?
4. Should invoice **rows** (buyer name, address) also be shortened, keeping only a numbering stub? This is a bigger privacy win but changes the "records stay" principle and needs the lawyer; recommended: not now.
5. R2 now (recommended, before TTLock exports land in 0015/0016) or later?

## 10. Council-lite review (2026-10-08, 3 advisors on Sonnet, no peer round)

Mandatory corrections to Option B, verified against the code:

| # | Severity | Finding | Fix |
|---|---|---|---|
| C1 | blocker | `invoice_issued_guard` lists `pdf_blob` (db.py:488-497); an additive trigger cannot override it, and `SCHEMA` re-creates the old guard on start (`CREATE TRIGGER IF NOT EXISTS`) | Migration `DROP TRIGGER` + re-create without `pdf_blob`, **and** the same edit in the `SCHEMA` text of db.py; new guard allows only `NEW.pdf_blob IS NULL` with the unlock; unlock set and reset inside one `db.immediate()` like `invoice_purge_unlock` |
| C2 | blocker | §2 wrongly said stay-fee files are kept forever | Fixed; ledger rows must be deleted in `_stay_fee_records_step` and `invoices.purge_expired`, or expiry and `/files` must skip missing refs; test it |
| C3 | major | NULLing BLOBs does not shrink DB or backups | Needs `VACUUM`; or accept no saving |
| C4 | major | Ledger row written outside the issue transaction | Insert it with the same `cur` in `invoices._write_issued` (~407-446) and in `stay_fee_filing.save` (~90/156), owner from the apartment |
| C5 | major | Admin-preview detection unspecified | `auth.impersonating(request)` (auth.py:349); test with an impersonation session |
| C6 | major | Scheduler wiring unspecified | Cron job in `scheduler.start()` mirroring `_job_retention`, plus an entry in `job_intervals()` (scheduler.py:62); closure guard = `_workspace_deletion_step` (retention.py:217) |
| C7 | major | Contract change: the 30-day figure under § 1752 OZ and adhesion-contract terms (§ 1798-1801 OZ) must come from the lawyer; most hosts are businesses, so § 1814 is secondary | Lawyer opinion before F1 |
| C8 | minor | L9 looks only at login | Never delete a file whose reminder hard-bounced |
| C9 | minor | "Removed from backups within 30 days" | Verify Litestream and Drive retention, or drop the claim |
| C10 | minor | § 247 daňový řád amounts unverified | Lawyer |
| C11 | split | F2 and F4 too big for one executor session | F2a page+tracking, F2b ZIP+manifest; F4a trigger+expire step, F4b reprints |
| C12 | minor | Timezone | `zoneinfo(config.TIMEZONE)`, store UTC ISO like `db.utcnow()` |

Orchestrator verdict: the council is right on the economics and on invoice originals. I withdraw my v1 recommendation and recommend Path R.
