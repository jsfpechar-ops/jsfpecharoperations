# WP16: Separate data-encryption key and more encrypted fields (HIGH RISK)

Patch: `WP16-data-key-multifernet.patch` (commit on top of `wpbase`). WP18 is stacked on this commit.

## Summary

- New env `UBYHOST_DATA_KEYS`: Fernet keys separated by commas, newest first. All encryption now goes through one `MultiFernet`. The first data key encrypts. Every data key, plus the old key derived from the session secret, is tried when decrypting.
- New env `UBYHOST_DATA_KEY_LEGACY` (default `1`). Set it to `0` once the migration has finished, and the derived key is dropped. The app refuses `0` while no data key is set. With no data keys set, behaviour is the same as today.
- A malformed data key stops the app at startup (`db.check_data_keys()` in the lifespan). The error message names the entry's position and never prints the value.
- Newly encrypted at rest, using the same `*_enc` column pattern as `doc_number`: `guest.birth_date`, `guest.res_street`, `guest.res_city` and `submission.request_xml`. The plaintext columns are now only a read fallback, and they are blanked whenever a row is written. Names, nationality and `res_country` stay plain.
- `db.ENCRYPTED_COLUMNS` maps each table to its encrypted fields. The write helpers (`insert`, `update`, `update_if`, `update_in`) encrypt every table in the map, not only `guest`. The query helpers decrypt any row that selected an `*_enc` column.
- The request XML download (`/submissions/{id}/request.xml`) reads the decrypted value. The 90-day envelope purge also blanks `request_xml_enc`.
- New tool `App/scripts/reencrypt.py`. It re-encrypts every token column, the stay-fee filing BLOBs, the claim secret inside queued mail JSON and the passport photo files. It also moves leftover plaintext into the `*_enc` columns. It works in batches, can be run again safely, and picks up where it stopped. It has `--dry-run`, `--check`, and counts per table and column. Writing runs need `--backup`. `--rollback-new-fields` exists for going back to an older release.

Birth-date SQL audit, done before encrypting it: no SQL statement filters, sorts, groups or compares on `birth_date`, `res_street` or `res_city`. They are only read through `SELECT g.*` or `SELECT *`:
- `housebook.py` lines about 92, 168, 273
- `reporting.py` about 911
- `stay_fee.py` `_GUESTS_SQL`, which orders by stay date and `g.id`, not by birth date
- `routes/guest.py` residence prefill

The age logic (`stay_fee.conservative_birth`, `validation.age_on`) and the Czech-resident rule (`routes/stay_fees.py`) already run in Python. Nothing had to move.

## Files changed

- `App/app/config.py`: adds `data_keys()` and `legacy_data_key_enabled()`.
- `App/app/db.py`: MultiFernet key handling, `DataKeyError`, `check_data_keys`, `token_is_current`, `rotate_token`, the `ENCRYPTED_COLUMNS` map, a table-aware `_write_values`, and 4 new `ADDED_COLUMNS`.
- `App/app/main.py`: validates the data keys at startup.
- `App/app/reporting.py`: the envelope purge also checks and blanks `request_xml_enc`.
- `App/app/routes/exports.py`: the request XML download selects `request_xml_enc` so the value is decrypted.
- `App/scripts/reencrypt.py`: new migration tool.
- `App/tests/test_data_keys.py`: new tests (18).
- `App/tests/test_retention.py`: raw selects now include `request_xml_enc`.
- `deploy/lightsail/.env.example`: placeholders for the 2 new variables.
- `docs/ENVIRONMENT.md`, `docs/SECURITY.md`: document the new keys and fields.

## Tests added

`tests/test_data_keys.py` (18 tests):
- Legacy key used when no data keys are set.
- Old data readable after a new key is added.
- A second key can read the first key's data.
- Rotating the session secret no longer affects encrypted data.
- With the legacy key off, legacy tokens no longer read.
- A malformed key is refused without echoing it.
- Legacy off with no data key is refused.
- Birth date, address and request XML are stored encrypted and are absent from the raw DB file.
- Rows from before WP16 still read from plaintext.
- Stay-fee age calculation is unchanged with an encrypted birth date (child exempt, adult liable, equal to the plaintext result).
- The purge clears the encrypted envelope.
- Re-encryption moves everything to the new key and values stay equal (guest fields, request XML, TOTP, UbyPort password, outbox claim secret, filing BLOBs, photo file, plaintext backfill), then `--check` passes.
- Resumable: a second run changes nothing.
- Dry run counts and writes nothing.
- Refuses to run without a fresh backup (missing, too old, or the live DB).
- Refuses to run without a new key.
- An unreadable value is left alone and the exit code is 2.
- Rollback of the new fields.

## Test commands and results

From `/tmp/wp/wp16/App`, before the WP18 commit:
- `pytest -q tests/test_data_keys.py tests/test_pii_encryption.py`: 32 passed.
- Broad chunks:
  - `tests/test_[a-d]*.py`: 400 passed, 2 skipped.
  - `tests/test_[e-h]*.py`: 579 passed, 5 skipped, 1 failed.
  - `tests/test_[i-p]*.py`: 635 passed.
  - `tests/test_[q-s]*.py`: 415 passed, 1 failed.
  - `tests/test_[t-z]*.py`: 152 passed.
- Both failures happen on the untouched base too:
  - `test_host_geometry.py::test_the_month_filter_shares_its_page_edges`: Chromium cannot launch in this sandbox.
  - `test_stale_submission.py::test_a_running_batch_without_a_live_claim_becomes_outcome_unknown`: fails only when run after other q-s files, and passes alone.
- `ruff check app tests tools scripts --select E9,F63,F7,F82,F401,F841`: all checks passed.

## Deviations from the spec and why

- The tool is `App/scripts/reencrypt.py`, not `App/tools/reencrypt.py`. `.dockerignore` excludes `App/tools`, so a tool there is not in the production image and could not run on the server. `App/scripts` is where the existing migration scripts (`migrate_encrypt_doc_fields.py`, `migrate_encrypt_signatures.py`) already live.
- `--backup` is required for writing runs only. `--dry-run` and `--check` write nothing and run without it. The backup must exist, be non-empty, not be the live DB, and be at most `--max-backup-age-hours` old (default 3).
- `res_country` stays plain. It is a country code like nationality, and the stay-fee resident rule reads it. Street and town are encrypted.
- Removing the old key means `UBYHOST_DATA_KEY_LEGACY=0`, not editing a list. The legacy key is derived, so there is nothing to delete.
- Added `--rollback-new-fields`. Without it, going back to a release older than WP16 would show empty birth dates and file `cDate` empty to the police, because the older release reads only the plaintext columns.
- The DSR export (`dsr.py`) already copied every guest column, including `*_enc` ciphertext. It now also includes the new `*_enc` columns. The decrypted values are present as before. Not changed (noticed only).

## What Cursor must verify or adapt when applying on the real main

- HIGH RISK hunks to review by hand:
  - `db.py` "secret handling" section (`_key_material`, `_fernet`, `_primary_fernet`, `token_is_current`, `rotate_token`).
  - `_hydrate` and `_write_values`.
  - The `ENCRYPTED_GUEST_COLUMNS` additions.
  - `routes/exports.py` `submission_xml`.
  - `reporting.purge_submission_payloads`.
- Grep main again for any SQL naming `birth_date`, `res_street`, `res_city` or `request_xml` outside `SELECT *`. If a query selects one of them explicitly without its `*_enc` column, it reads NULL after this change. On this branch there are none.
- Any new raw `cur.execute("INSERT INTO guest ...")` or `INSERT INTO submission` bypasses encryption. On this branch all writes use the `db` helpers.
- `scripts/backup_data.sh` copies `secret_key` but not `UBYHOST_DATA_KEYS`. A backup is unreadable without the data keys, so the owner must keep the keys outside the server (see Manual steps). Changing the backup script is not in this WP.
- Deploy on staging first (README rule for HIGH RISK WPs).

## Manual steps for the owner (runbook)

Stage 1, deploy the code with no new key:
1. Take a backup: `deploy/lightsail/scripts/backup.sh` or `App/scripts/backup_data.sh`.
2. Deploy this release with `UBYHOST_DATA_KEYS` empty. Behaviour is the same as today, except that birth date, street, town and new request envelopes are now encrypted under the old derived key.
3. Click through staging, then production.
4. If you must roll back now: run `scripts/reencrypt.py --rollback-new-fields --backup <fresh backup>` in the app container first, then deploy the old release.

Stage 2, add the key:
1. Generate a key: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
2. Store it in your password manager, next to the age identity. Without it no backup can be read.
3. Put it in the server `.env` as `UBYHOST_DATA_KEYS=<key>`, leave `UBYHOST_DATA_KEY_LEGACY=1`, and restart.
4. From here on, rolling back to a release older than WP16 is not possible without restoring a backup. Data written under the new key cannot be read by old code.

Stage 3, migrate, in the app container (`docker compose exec app ...`):
1. Take a fresh backup.
2. Run `python scripts/reencrypt.py --dry-run` and note the counts per table and column.
3. Run `python scripts/reencrypt.py --backup /path/to/that/backup`. It is safe while the app runs. If it is interrupted, run it again.
4. Run `python scripts/reencrypt.py --check`. It must exit 0, with every line showing `rotated=0 encrypted=0 blanked=0 unreadable=0`.
5. If the run reports `unreadable`, stop and investigate before going further. Those values are left untouched.

Stage 4, a later deploy:
1. Set `UBYHOST_DATA_KEY_LEGACY=0` and restart.
2. Rotating `UBYHOST_SECRET_KEY` now only logs everyone out.
3. To rotate the data key later: put the new key first (`UBYHOST_DATA_KEYS=<new>,<old>`), restart, run stages 3.1 to 3.4, then remove `<old>` on a later deploy.
