# Operations runbook

How the machinery behind the three product steps actually behaves, for whoever
is holding the pager. Deployment mechanics live in
[DEPLOYMENT.md](DEPLOYMENT.md) and [LIGHTSAIL.md](LIGHTSAIL.md); environment
variables live in [ENVIRONMENT.md](ENVIRONMENT.md). This file covers the things
you need when something has gone wrong and the answer is not in either.

## Contents

- [Scheduled jobs](#scheduled-jobs)
- [The `submit_state` state machine](#the-submit_state-state-machine)
- [UbyPort error codes, and what 112 and 150 really do](#ubyport-error-codes-and-what-112-and-150-really-do)
- [Alert kinds](#alert-kinds)
- [Schema migrations](#schema-migrations)
- [If the secret key is lost or rotated](#if-the-secret-key-is-lost-or-rotated)
- [Retention and what is actually deleted](#retention-and-what-is-actually-deleted)
- [Backup and restore](#backup-and-restore)

## Scheduled jobs

Registered by `App/app/scheduler.py:start()` on a single `BackgroundScheduler`
running in the web process, in `Europe/Prague`. All five are skipped entirely
when `UBYHOST_ENABLE_SCHEDULER=0`.

| Job id | Interval | What it does |
| --- | --- | --- |
| `ical` | `UBYHOST_ICAL_POLL_MINUTES` (60) | Re-reads every active calendar feed and reconciles reservations. |
| `submit` | `UBYHOST_SUBMIT_SWEEP_MINUTES` (10) | Sends everything currently sendable for apartments not in `manual` mode. |
| `deadlines` | 30 min | Raises and clears `deadline` alerts for stays running out of statutory time. |
| `mail` | 5 min | Expires 30-minute claim holds, drains the guest e-mail outbox, sends day-before reminders, purges mail rows older than 14 days. |
| `photo_sweep` | 12 h | Deletes passport images for stays that ended more than 30 days ago, plus orphaned files, and blanks the request/response envelopes on submissions older than 90 days. |

Two behaviours to know:

- **The `ical` job is registered paused.** It is un-paused on boot only if at
  least one active feed already exists. A host who starts the app and *then*
  adds their first calendar gets the one inline sync that the "add feed" action
  performs, and no further automatic polling until the process restarts.
  Restart after adding the first feed.
- **A job that raises is logged and forgotten.** Each job body catches
  `Exception`, writes `log.exception`, and returns. No alert is raised, so a
  repeatedly failing job is invisible in the UI. If ingestion or sending looks
  stalled, read the container log before looking anywhere else.

The dashboard's "last updated" timestamp is a single global setting, not
per-host, and there is no staleness threshold or alert behind it. It is the only
in-app signal that polling has stopped.

## The `submit_state` state machine

One value per guest row, defined in `App/app/reporting.py`. It is the record of
whether that individual has been reported.

| State | Meaning |
| --- | --- |
| `pending` | Not yet accepted by UbyPort. The default, and where a record sits between the guest signing and the next sweep. |
| `sent` | UbyPort holds this record. Never resent automatically. |
| `error` | Rejected in a way that correcting the data can fix. |
| `blocked` | Rejected in a way resending will not fix — in practice code 150, a duplicate. 112 does **not** belong here; see below. |
| `not_required` | Czech national: house book only, no reporting duty. |

Transitions:

- `pending → sent` — the response carried no error codes for this record.
- `pending → error` — correctable code(s) returned.
- `pending → blocked` — a non-correctable code (150, or a codebook text
  matching `duplic`/`pozd`/`late`).
- `error`/`blocked`/`pending` **→ `sent`** when the response says duplicate
  (code 150). See below.
- `error`/`blocked`/`not_required` → `pending` when a host edits the guest —
  rule 10.4(5), correcting a rejected record must make it sendable again. A host
  edit of a reportable guest also stamps `identity_verified_at`.
- anything → `not_required` when the nationality is changed to Czech.
- **A transport failure changes nothing.** The guest stays `pending` and the
  `submission` row is marked `transport_error`, so the next sweep retries. This
  is deliberate: rule 10.2(e) forbids losing the queue on a network blip.

`sent` rows refuse edit and delete from both the host and guest surfaces. A
deliberate resend of a `sent` or `blocked` record requires an explicit
confirmation in the UI, and a record blocked *as a duplicate* is refused even
then, because a second duplicate cannot be accepted and duplicates count
against the host's web-service access.

## UbyPort error codes, and what 112 and 150 really do

Codes come back as a `;`-separated string per record. The authoritative code
book is fetched from the service with `DejMiCiselnik(Chyby)` and cached in the
`codelist` table; `App/app/ubyport/errors.py` holds the handful that must be
understood even with an empty cache.

Classification is partly **substring matching on the code book's Czech text**
(`duplic`, `pozd`, `late`). A wording change on the police side can therefore
reclassify records without any change here. Only 112 and 150 are pinned to their
code, so they cannot be reclassified by prose.

Each send writes one `submission` row. Its `state` is what the call itself
produced, and it is independent of the guest's `submit_state` above:

| `submission.state` | Meaning |
| --- | --- |
| `ok` | At least one record was accepted for the first time and no error codes came back. A Doručenka or a stamp is expected; `receipt_missing` fires if neither arrived. |
| `ok_duplicate` | Every record was already held by the register (code 150). A success, but nothing new was filed and no Doručenka exists for this call — see below. |
| `partial` | Some records were accepted for the first time and some were not. |
| `error` | Records came back with correctable codes. The guest stays `error` and is retried. |
| `transport_error` | The service could not be reached, or answered with a fault. Nothing was filed. |

A `partial` row whose only rejection is a duplicate is still `partial`: the
duplicate half is settled, the other half is not. `ok_duplicate` is reserved for
a call where duplicates were the *whole* result.

The two codes that matter:

**150 — duplicate.** The register already holds this record. The app treats
that as proof of acceptance and sets the guest to `sent`, backfilling
`submitted_at` if it was empty. This is intentional and it is also the recovery
path for a submission whose HTTP response was lost: the retry comes back as a
duplicate, and the record correctly lands as reported.

The consequence to be aware of: a duplicate files nothing new, so the
`submission` row for that call is recorded in state `ok_duplicate` — a success,
but not the same thing as a first-time accept — and it carries **no Doručenka**,
because a duplicate response has none. `guest.receipt_submission_id` therefore
points at the submission that actually holds the confirmation, and the Reports
detail page links to it. If you need the receipt for such a record, follow that
link; if there is none, the app says so rather than implying a missing document.

A submission row is `ok` only when at least one record was accepted for the
first time *and* the service returned no error codes. `ok` with no stamp and no
Doručenka behind it raises the `receipt_missing` warning — the register has the
record and we hold no proof of it.

**112 — critical transmission error.** The Foreign Police answered this in
writing: in UBYPORT, 112 falls into the category of critical transmission
errors (the 1xx series) and means **the batch of accommodated foreigners was
not received at all**. The register does not hold the data. The usual causes
they give are a structural fault in the submitted file (an invalid character in
the generated `.UNZ`/`.XML`), an empty mandatory field, or an interrupted
connection to the Police of the Czech Republic server during upload.

So 112 is correctable, not permanent: the guest goes to `error`, stays in the
queue, and the next send — automatic or manual — picks the record up again.
The remedy the police prescribe is to check the guest's card in the
accommodation system for correct nationality, date of birth and document
number, and then **repeat the submission**.

Be honest about what we cannot tell apart: an interrupted connection is
transient and simply retrying is right, while an invalid character or an empty
mandatory field is a data fault that no number of retries will clear. We
receive the same code for both, so if a record comes back 112 twice, stop
retrying and check the data — the guest card, and the generated file — before
sending again.

112 is pinned in `App/app/ubyport/errors.py` as correctable regardless of the
code book's wording, so a police-side text change cannot quietly turn a batch
that was never received into a record we abandon. The rest of the 1xx series is
deliberately **not** generalised from this answer: no code book entry tells us
the other 1xx codes mean the same thing, and treating a batch the service did
accept as never received risks a strike against the host. An unrecognised code
falls through to `error`, which is correctable anyway.

The `request_xml` and `response_xml` columns on the `submission` row hold the
exact envelope sent and received. They are the authoritative record for an
incident, and they contain guest passport numbers in cleartext — treat a copy
of them as you would a copy of the passports.

## Alert kinds

Every alert has a level, a kind, and a dedupe key. An unresolved alert with a
given dedupe key is unique (enforced by a partial index), so re-raising updates
rather than duplicates. Alerts are cleared by the code path that fixes the
condition, not by time.

| Kind | Level | Raised when | Cleared when |
| --- | --- | --- | --- |
| `deadline` | critical / warning | A stay is overdue or due now with data still missing. | The stay reaches `reported` or `not_required`. |
| `submission_transport` | **critical** | UbyPort could not be reached, or returned a fault. | The next successful call to that apartment's endpoint. |
| `submission_rejected` | **critical** | UbyPort did not accept one or more records. | A later submission for that apartment comes back clean — including one that only produced duplicates. |
| `receipt_missing` | warning | UbyPort accepted records for the first time but returned neither a Doručenka nor a stamp, so the register holds them and we hold no proof. | A submission for that apartment returns a Doručenka or a stamp. |
| `submission_immediate` | warning | An automatic send triggered by form completion threw. | Not auto-cleared; resolve by sending successfully. |
| `apartment_setup` | warning | UbyPort settings are incomplete, so nothing can be reported for that apartment. | The settings validate. |
| `feed_error` | warning | A calendar could not be fetched or parsed. | The next successful parse of that feed. |
| `cancelled_after_report` | warning | A stay vanished from the feed, or was cancelled in it, **after** it had already been reported. | Not auto-cleared; the host decides whether it was cancelled or moved. |
| `guest_incomplete_checkin` | warning | Check-in day arrived with the guest's form still incomplete. | — |
| `guest_pin_abuse` | warning | Repeated wrong PIN attempts on an apartment's guest link. | — |
| `mail_failed` | warning | A queued guest e-mail exhausted its attempts. | — |

`submission_transport` and `submission_rejected` are the two criticals. Either
one means a filing did not land.

## Schema migrations

There is no migration framework. The schema in `App/app/db.py` is applied with
`CREATE TABLE IF NOT EXISTS`, which leaves an existing database untouched, so
**every column added after the first release must also be appended to the
`ADDED_COLUMNS` tuple** in the same file. `_add_missing_columns` walks that
tuple on every connection and issues `ALTER TABLE ... ADD COLUMN` for anything
missing.

Rules that follow from this:

- `ADDED_COLUMNS` is append-only. Never reorder it, never remove an entry — an
  older database restored from backup still needs every step.
- Add the column to the `SCHEMA` literal **and** to `ADDED_COLUMNS`. A fresh
  database gets it from the first; an existing one from the second.
- `NOT NULL` needs a `DEFAULT`, because SQLite cannot add a `NOT NULL` column
  to a populated table without one.
- A `REFERENCES` clause in an added column is recorded but not enforced against
  rows that already exist.
- Renames, type changes and drops are not supported by this mechanism at all.
  They need a hand-written table rebuild, which nothing here does today.
- There is no downgrade path. A rollback to an earlier image leaves the extra
  columns in place, which is harmless, but the reverse is not.

One change could not be made by adding a column alone. `guest.doc_number` and
`guest.visa_number` are now stored encrypted in `doc_number_enc` and
`visa_number_enc`, and an added column arrives empty — it does not carry the
existing rows across. The release that introduced the pair also ships
`App/scripts/migrate_encrypt_doc_fields.py`, which has to be run once as a
deploy step:

    .venv/bin/python scripts/migrate_encrypt_doc_fields.py --dry-run
    .venv/bin/python scripts/migrate_encrypt_doc_fields.py

It is idempotent and safe to re-run, and it blanks the plaintext column as it
goes. Until it has run, the numbers are still in the clear in that database;
the app keeps reading the plaintext column as a fallback so nothing breaks in
the meantime.

`deploy/lightsail/scripts/deploy.sh` dry-runs the new schema against a copy of
the live database before switching over. Do not skip it.

## If the secret key is lost or rotated

`UBYHOST_SECRET_KEY` (or `data/secret_key`) signs cookies and CSRF tokens, and
derives the Fernet key that encrypts **UbyPort web-service passwords, host
TOTP secrets and guest travel-document numbers**. Losing it or changing it has
a wide, and partly silent, blast radius.

What happens, in the order you will notice it:

1. Every host session is invalid — everyone is logged out.
2. Every guest PIN cookie, claim cookie and ownership cookie is invalid.
   Guests mid-registration will be asked for the PIN again; a guest who had
   confirmed a claim keeps their access, because that lives in the database.
3. Stored TOTP secrets cannot be decrypted. Since production forces 2FA, a host
   whose secret is undecryptable needs their recovery codes, or an
   administrator to reset their second factor.
4. **Reporting stops, quietly.** `db.decrypt_secret` returns an empty string
   rather than raising, so each apartment fails its setup validation, raises an
   `apartment_setup` warning, and every send returns `not_configured`. Nothing
   is lost and nothing is sent. The deadline clock keeps running.
5. **Stored guest document numbers will not decrypt either, and this one is
   loud.** `db.decrypt_field` raises instead of returning empty, so opening a
   guest, exporting the house book or filing to the police fails with an error
   the host can see. That is deliberate: an empty `cDocN` filed with the police
   is worse than a visible failure. Restoring the old key clears it.

Recovery:

1. If the old key still exists anywhere — a backup of `data/secret_key`, the
   old `.env` — restore it. That undoes all four items above. Back up the key
   and the database **together**; a database without its key is only partly
   usable.
2. Otherwise, sign in as an administrator (the bootstrap admin password is
   unaffected; it is a hash, not an encrypted value).
3. Re-enter the UbyPort web-service password for **every** apartment. Check
   each one with the Test-connection button. Watch for the `apartment_setup`
   alert clearing.
4. Re-enrol 2FA for every host account that had it, or issue new recovery
   codes.
5. Run a manual send for anything that queued up while reporting was blocked,
   and check the deadline alerts before assuming you are caught up.

Rotating deliberately is the same procedure, done in a maintenance window, with
step 1 skipped. Do not rotate without allocating time for steps 3 and 4.

## Retention and what is actually deleted

Automatic:

- **Passport images** — every 12 hours, for stays that ended more than 30 days
  ago, plus orphaned files. Also deleted immediately when a host confirms a
  guest's identity against the document, and when the guest is archived or
  deleted: archiving keeps the row but hides it, and the scan existed only for
  the check the host has now made. The 30-day sweep is the backstop for a host
  who never pressed Verify.
- **Mail rows** — `email_outbox` and `console_mail_log` older than 14 days.
  A stored body never holds a working claim link: the secret is kept beside it
  in the payload, encrypted, and put back when the message is sent. The sweep
  still matters for the rest of the body — the guest's address, the apartment
  name, the stay dates — but a row that outlives its welcome cannot be used to
  open someone's registration.
- **Submission envelopes** — `submission.request_xml` and `response_xml` are
  blanked 90 days after the submission was created, by the 12-hour sweep and by
  the Settings button. These envelopes hold every reported guest's name, birth
  date and travel-document number, so this is the clock that matters for the
  reported data. The Doručenka (`receipt_pdf`), the error PDF and the pseudo
  stamp are **kept**: they are the evidence the host has to be able to produce,
  and none of them carries guest data.

Manual only:

- **Expired house-book records** — the six-year duty is displayed per record and
  computed from the end of each stay, but expiry is **not** deleted on a
  schedule. It is the "purge expired records" button in Settings. If nobody
  presses it, expired guest rows stay indefinitely. The same button also clears
  the passport images and blanks the submission envelopes described above, so a
  host who never presses it is still covered by the sweeps.

Deleted by either path:

- **Orphaned submission rows** — a submission that no surviving `guest` row
  points at, and that is itself older than the six-year cutoff, is deleted by
  the retention purge. `guest.submission_id` is `ON DELETE SET NULL`, so once
  the guests age out the row is unreachable from every screen. The cutoff is
  applied here so that deleting a guest by hand cannot take a recent Doručenka
  with it.

Never deleted by any code path today:

- **`guest.filled_ip`**, retained for the life of the house-book record.

## Backup and restore

The scripts are documented in
[deploy/lightsail/README.md](../deploy/lightsail/README.md). What they do not
tell you:

- **Back up `data/secret_key` (or the `.env` holding `UBYHOST_SECRET_KEY`)
  together with the database.** A database restored without its key needs every
  UbyPort password re-entered and every TOTP secret re-enrolled — see above.
- **Passport images are not in the database.** They are files under the data
  directory and need to be in scope separately, or accepted as lost. Since they
  are short-lived by design, losing them is usually the right trade.
- **Also outside the database backup:** Caddy's certificates, the `.env`
  itself, and the mock service's state file.
- **Verify a restore before trusting it.** `sqlite3 ubyhost.db 'PRAGMA
  integrity_check;'` then start the app against a copy and check that the
  submissions list renders and one Doručenka downloads. A truncated WAL
  restore can look fine until a blob is read.
- **Backups are not encrypted** by the supplied scripts. Guest passport
  numbers are encrypted *inside* the database, but the key that decrypts them
  travels in the same backup, so a copy of both is as readable as a copy of the
  plaintext was. Encrypting them off-host is an operator action that nothing
  here performs for you.
