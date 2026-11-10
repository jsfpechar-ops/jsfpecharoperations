# 1089: Under-15 guests do not sign: server, storage, filing check and house book

Status: todo
Tier: A | Depends on: none | Base: origin/main | Branch: claude/1089-under-15-signature
Executor: Fable 5.2 (owner tier override in decisions.md) | Attempts: 3 at most | Fits one session: stop at 60 tool calls or 60k tokens (section 8); reads stay at 150 lines or fewer
Review: a fresh Fable reviews the diff against this brief before the PR opens.
Report: docs/tasks/1089-report.md
Next: [1090](1090-under-15-signature-ui.md) (the guest form half; branch cut from this one)

## 1. Objective

Close known issue **K-L04**. Owner decision 2026-11-10, after the legal memo `/mnt/project-files/legal/under-15-signature.md` (read only; not in the repo):

- A guest **under 15 on the arrival date** does not sign (Act 326/1999 § 103(b)). No signature is collected or stored for them.
- An adult guest (**18 or over on the arrival date**) on the same booking may sign for the child and ticks one role: `parent` ("Parent or legal guardian") or `responsible_adult` ("Adult responsible for the child during this stay") (§ 103(u)). No proof is asked for.
- Record "Signed by <adult> for <child>, as <role>, <timestamp>" plus the wording version. One signature image (the adult's own), never a copy per child.
- No adult signs: do not block; the record says "Under 15, no signature required (§ 103(b))".
- Guests aged 15 to 17 still sign themselves. The child is still reported to the police exactly as today.

This brief is the server half: the age rule, the completeness check (Python **and** the Go port, which the Go submit job uses), the guest save, four new columns, the house book and the retention line. The form markup, script and copy are brief 1090. After this brief the guest form still shows the pad to a child (the script still asks for it), but the server accepts a child's form without one.

**Tier A:** this touches the completeness gate that decides what is filed. Filing correctness first: the child's UbyPort envelope and every `submit_state` value must be byte-for-byte what they are today (step 9).

## 2. Context

- **Where the signature is required today.** `reporting.guest_signature_issue` (`App/app/reporting.py:236`) returns an issue for an empty value. Two callers: `reporting.guest_issues` (`:319`, the stored-record check behind `guest_is_complete`, `collect_sendable`, the host form previews at `routes/admin.py:4333` and `:4452`) and the guest save `guest_form_save` (`App/app/routes/guest.py:2243`, `allow_imported=False`). A child under 15 therefore can never be saved by the guest form and never counts as complete.
- **The Go port decides filing too.** `go/internal/validation/validation.go:423` `guestSignatureIssue` and `:440` `GuestIssues` mirror the Python. `GuestIsComplete` is read by the Go submit job (`go/internal/ubyport/collect.go:230`), the recovery pass (`go/internal/ubyport/recover.go:199`) and the calendar progress (`go/internal/calendar/progress.go:103`). If only Python changes, the Go submit job skips every unsigned child for ever. The parity test compares Go with `go/internal/validation/testdata/golden.json`, written by `App/scripts/validation_golden.py` from the real Python.
- **Arrival date.** `reporting._stay_dates` (`:132`): the guest's `stay_from`, else the reservation's `date_from`. Go: `stayDates` (`validation.go:191`). The guest save has `stay_from` from `_locked_stay_dates` (`guest.py:2201`).
- **Birth dates may be partial** (`00` day or month). The rule must never make an older guest look younger: **under 15** uses the *earliest* possible birthday (day or month `00` read as `1`, as `stay_fee.conservative_birth`); **18 or over** uses the *latest* (month `00` read as 12, day `00` read as the month's last day). Year `0000` or unparseable: neither under 15 nor adult. `validation.age_on` (`App/app/validation.py:164`) does the arithmetic.
- **Storage today.** `guest.signature_png` (encrypted pair `signature_png_enc`, `db.py:2331`), `guest.signed_at`. The guest save writes `"signature_png": signature` and `"signed_at": now` in `payload` (`guest.py:2326`). `routes/admin_helpers.kept_signature` keeps a stored signature when none is posted (`guest.py:2202`).
- **Ownership.** `_owned_ids(request)` (`guest.py:161`) lists the guest ids this device saved (signed cookie). Only those may be linked, so nobody signs for, or learns the name of, a child entered on another phone.
- **House book.** `housebook._housebook_export_row` (`App/app/housebook.py:163`) writes `"signed": "yes"/"no"` from `reporting.guest_has_signature`; `housebook.registration_form_pdf` (`:294`) draws the image under "Podpis cizince / Signature of the foreigner" and "Signed electronically: ..." (`:376`-`:394`). Both rows come from `SELECT g.*, r.date_from AS res_from, r.date_to AS res_to` (`:104`, `:299`). `guest_has_signature` stays as it is (also read by `dsr.py:135`).
- **Brief 1079 (child on a parent's passport)** is a different thing: the `child_in_passport` box (`form.html:171`, `initChildToggle` in `signature.js`) shows for under 18 and stores `doc_number = INPASS` plus the parent's number in `note`. It is filed as today and this brief does not touch it. A child may be both.
- **Schema.** Last SQLite migration `App/app/migrations/0042_guest_form_draft.sql`; last goose file `App/migrations_pg/00013_guest_form_draft.sql`. Next: **0043** and **00014**. Model both on `0041_claim_fee_mailed.sql` (four `ALTER TABLE ... ADD COLUMN`) and `00013` (header comment, `IF NOT EXISTS`, the `schema_migrations` insert, `+goose Down`). Pins that move from 42 to 43 (version only; **table counts stay**, no new table): `App/tests/test_migrations.py:245`; `App/tests/test_db_postgres.py` lines 250 (`== 42`; leave `70`/`71`), 288 area (`list(range(1, 43))` to `44`), 309, 318, `"schema version 42 is planned"`, `"version=42"` (leave `tables=71`), 1055, 1068. Find each with `grep -n "42" App/tests/test_db_postgres.py`; change only schema-version 42s.
- **Retention.** The four columns are personal data about the adult and the child, kept with the guest row (6 years, deleted with it by `housebook.purge_expired` and the workspace delete). Comment line next to `# 1082:` at `App/app/retention.py:197`; the guest-record row in `docs/privacy/RETENTION.md:14`.

### New columns on `guest` (all nullable, none encrypted: an id, a code, a time, a version)

| Column | Type | Value |
|---|---|---|
| `signed_for_guest_id` | INTEGER (PG BIGINT) | the signing adult's `guest.id`, same reservation |
| `signed_for_role` | TEXT | `parent` or `responsible_adult` |
| `signed_for_at` | TEXT | `db.utcnow()` when the adult confirmed |
| `signed_for_wording` | TEXT | `reporting.SIGN_FOR_WORDING_VERSION` (`"u15-2026-11-10"`) |

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/migrations/0043_guest_signed_for.sql` | create | Four columns (step 1) |
| `App/migrations_pg/00014_guest_signed_for.sql` | create | Goose twin (step 1) |
| `App/tests/test_migrations.py`, `App/tests/test_db_postgres.py` | edit | Version pins 42 to 43 (step 1) |
| `App/app/validation.py` | edit | `certainly_under_age`, `certainly_at_least_age` (step 2) |
| `App/app/reporting.py` | edit | Constants, `guest_under_15`, `guest_signature_issue(under_15=)`, `guest_issues`, `signature_record` (step 3) |
| `App/scripts/validation_golden.py`, `go/internal/validation/testdata/golden.json` | edit, regenerate | Six cases (step 4) |
| `go/internal/validation/validation.go` | edit | `certainlyUnderAge`, `guestSignatureIssue(value, under15)` (step 4) |
| `App/app/routes/guest.py` | edit | Save path, link helper, remove (steps 5, 6) |
| `App/app/housebook.py` | edit | CSV `signed`, PDF block (step 7) |
| `App/app/retention.py`, `docs/privacy/RETENTION.md` | edit | Retention line (step 8) |
| `App/tests/test_under15_signature_1089.py` | create | Tests (step 9) |
| `docs/tasks/1089-report.md` | create | Report, plus `Status: review` here |

## 4. Steps (commit after each: `1089 step k`)

0. `git fetch origin main && git merge origin/main`. `ls App/app/migrations | tail -2` and `ls App/migrations_pg | tail -2 2>&1 | tail -30`: if anything above 0042 or 00013 exists, renumber to the next free pair and say so under Deviations.
1. **Migration.** `0043_guest_signed_for.sql`: a two-line comment (brief 1089, what the columns hold, personal data kept with the guest row) and four `ALTER TABLE guest ADD COLUMN ...` lines (table in section 2). `00014_guest_signed_for.sql`: `-- +goose Up`, the twin comment as in 00013, `ALTER TABLE guest ADD COLUMN IF NOT EXISTS signed_for_guest_id BIGINT;` and the three TEXT columns, `INSERT INTO schema_migrations (version, name, applied_at) VALUES (43, 'guest_signed_for', '2026-11-10T00:00:00+00:00') ON CONFLICT (version) DO NOTHING;`, `-- +goose Down`, `DELETE FROM schema_migrations WHERE version = 43;` and four `ALTER TABLE guest DROP COLUMN IF EXISTS ...`. Move the pins (section 2). Run command A1.
2. **Age rule (`validation.py`)**, directly under `def age_on`:
   ```python
   def certainly_under_age(raw: Optional[str], when: Optional[date], years: int) -> bool:
       """True only when the guest is under ``years`` on ``when`` whatever a 00 day or month hides.

       Brief 1089: the earliest possible birthday (00 read as 1) is the oldest the guest can be.
       """
   def certainly_at_least_age(raw: Optional[str], when: Optional[date], years: int) -> bool:
       """True only when the guest is at least ``years`` on ``when`` (00 month read as 12, 00 day as the month's last day)."""
   ```
   Both: `when` None, `normalise_birth_date(raw)` not 8 digits, year 0, or no real date: `False`. Day and month from `digits[:2]`, `digits[2:4]`, year `digits[4:]`, as `stay_fee.conservative_birth` (`stay_fee.py:206`); the last day via `calendar.monthrange` (stdlib). Then `age_on(birth, when) < years` and `>= years`. Run command A2.
3. **`reporting.py`.**
   a. Above `def guest_has_signature`: `UNDER_SIGN_AGE = 15`, `ADULT_SIGNER_AGE = 18`, `SIGN_FOR_WORDING_VERSION = "u15-2026-11-10"`, `SIGN_FOR_ROLES = {"parent": "parent or legal guardian", "responsible_adult": "adult responsible for the child during this stay"}` (one comment line: brief 1089, Act 326/1999 § 103(b) and (u)).
   b. `def guest_under_15(guest, reservation) -> bool:` `start, _end = _stay_dates(guest, reservation)`; `return validation.certainly_under_age(guest["birth_date"], start, UNDER_SIGN_AGE)`.
   c. `guest_signature_issue` gains the keyword `under_15: bool = False` and, as its first check after `text = ...`: `if under_15 and not text: return None`. Add one docstring sentence. Nothing else in it changes (an imported marker or a junk value is judged as today).
   d. `guest_issues`: `guest_signature_issue(guest["signature_png"], translate, under_15=guest_under_15(guest, reservation))`.
   e. `def signature_record(guest, reservation) -> Dict[str, str]:` returns `{"kind": k, "text": t}` in this order: `imported` (value `IMPORTED_SIGNATURE`; text `"Signature on paper (host)"`); `own` (`validation.is_valid_signature`; text `""`); then if `guest_under_15`: when `signed_for_guest_id` is set and `db.query_one("SELECT * FROM guest WHERE id = ? AND reservation_id = ?", (that id, guest["reservation_id"]))` finds the adult, `signed_for` with text `f"Signed by {adult first_name} {adult surname} for {child first_name} {child surname}, as {SIGN_FOR_ROLES.get(role, role)}, {signed_for_at}, wording {signed_for_wording}"`; else `exempt` with `"Under 15, no signature required (§ 103(b))"`; otherwise `missing`, `""`. Read optional columns with `_field(guest, "...")` (`:188`). Run command A2.
4. **Go parity.** In `validation_golden.py`, after `g("signature_empty", signature_png="")` (`:195`) add (RES arrival is 2026-10-20):
   `g("u15_no_signature", birth_date="21102011", signature_png="")`; `g("u15_turns_15_on_arrival", birth_date="20102011", signature_png="")`; `g("u15_month_unknown_certain", birth_date="00002012", signature_png="")`; `g("u15_month_unknown_uncertain", birth_date="00002011", signature_png="")`; `g("u15_bad_signature", birth_date="21102011", signature_png="data:image/png;base64,QUJ")`; `g("u15_stay_from_decides", birth_date="21102011", stay_from="2026-10-22", signature_png="")`.
   In `validation.go`: add `certainlyUnderAge(raw string, when time.Time, years int) bool` beside `parseBirthDate` (same rules as step 2's first function; 8 ASCII digits, `00` read as 1, year 0 false, `roundTrip` must succeed). `guestSignatureIssue(value string, under15 bool)`: first line after `text :=`, `if under15 && text == "" { return nil }`; update its comment. In `GuestIssues`: `under15 := from != nil && certainlyUnderAge(g.BirthDate, *from, 15)` and pass it. From `App/`: `.venv/bin/python scripts/validation_golden.py 2>&1 | tail -30`, then command G. `git diff --stat` on `golden.json`: only the six new cases added. If an existing case changed: STOP.
5. **Guest save (`guest_form_save`, `guest.py`).**
   a. Directly after `signature = _kept_signature(...)` (`:2202`): `child = validation.certainly_under_age(values["birth_date"], validation.parse_iso_date(stay_from), reporting.UNDER_SIGN_AGE)`, then `if child: signature = ""` with a comment (§ 103(b): a child's signature is neither asked for nor kept, even one posted or stored before).
   b. The `guest_signature_issue(...)` call (`:2243`) gains `under_15=child`.
   c. Above `def _with_lang` add `def _sign_for_fields(request, reservation, signer_raw, role_raw, now) -> Dict[str, Any]` and `def _link_signed_children(request, reservation, adult_id, ids_raw, role_raw, now) -> None` (`reservation` is the row the handler holds; use `reservation["id"]`), docstrings citing brief 1089 and § 103(u). A **valid signer** is: an int in `_owned_ids(request)`, a `guest` row with that id and this reservation's id, `validation.is_valid_signature(row["signature_png"])`, and `validation.certainly_at_least_age(row["birth_date"], arrival, reporting.ADULT_SIGNER_AGE)` with `arrival` from `reporting._stay_dates(row, reservation)[0]`. A **valid role** is a key of `reporting.SIGN_FOR_ROLES`. `_sign_for_fields` returns the four columns (`signed_for_wording = reporting.SIGN_FOR_WORDING_VERSION`) when both are valid, else `{}`. `_link_signed_children` does nothing unless the role is valid; for each distinct int in `ids_raw` that is in `_owned_ids(request)`, is not `adult_id`, is a row of this reservation and `reporting.guest_under_15(row, reservation)` holds: `db.execute("UPDATE guest SET signed_for_guest_id = ?, signed_for_role = ?, signed_for_at = ?, signed_for_wording = ? WHERE id = ? AND reservation_id = ? AND signed_for_guest_id IS NULL", ...)`. It writes **only** those four columns: never `updated_at`, `submit_state`, `submit_attempts`, `last_errors` (the first adult to sign wins; a filed child gets the house-book line without being refiled).
   d. In the `payload.update({...})` block: `"signed_at": now` stays. After the block: `if child: payload.update(_sign_for_fields(request, reservation, form.get("signed_by"), form.get("child_sign_role"), now))`. An empty result adds nothing, so an edit without a posted signer keeps an earlier link.
   e. Directly above the `db.audit("guest_form_saved", ...)` call: `if not child and validation.certainly_at_least_age(values["birth_date"], validation.parse_iso_date(stay_from), reporting.ADULT_SIGNER_AGE): _link_signed_children(request, reservation, saved_id, form.getlist("sign_for_ids"), form.get("sign_for_role"), now)`. (The adult's own signature was validated above, so the adult is a valid signer.)
   Form field names, for 1090: child form `signed_by`, `child_sign_role`; adult form `sign_for_ids` (repeated), `sign_for_role`. Run command A2.
6. **Remove (`guest_remove`, `guest.py:2024`).** Directly after the `if not removed:` branch, before `passport_photos.delete_photo(guest_id)`: `db.execute("UPDATE guest SET signed_for_guest_id = NULL, signed_for_role = NULL, signed_for_at = NULL, signed_for_wording = NULL WHERE signed_for_guest_id = ? AND reservation_id = ?", (guest_id, reservation_id))` with a one-line comment. Run command A2.
7. **House book (`housebook.py`).** `_housebook_export_row` `"signed"`: `{"own": "yes", "imported": "yes", "signed_for": "by adult", "exempt": "not required"}.get(kind, "no")` with `kind = reporting.signature_record(row, {"date_from": row["res_from"], "date_to": row["res_to"]})["kind"]`. In `registration_form_pdf` compute the same `record` once; keep the image branch as is; when `record["kind"]` is `signed_for` or `exempt`, draw `record["text"]` with `FONT_REGULAR` 9 at `(left, y + 8)` in place of the image, and draw `record["text"]` instead of `f"Signed electronically: {signed}"` on the grey line. Nothing else in the PDF. Run command A2.
8. **Retention.** `retention.py`, directly under the `# 1082:` line: `# 1089: guest.signed_for_guest_id / signed_for_role / signed_for_at / signed_for_wording (the adult who signed for a guest under 15, their role and the wording version) are kept with the guest row and go with it (guest step, workspace deletion); removing the adult on the guest link clears them.` `RETENTION.md:14`: in the first cell change `signature)` to `signature; for a guest under 15 the signing adult's id, role, time and wording version)`. Run command A3.
9. **`App/tests/test_under15_signature_1089.py`.** Seed with `_cleanup`, `_seed`, `_payload` of `test_guest_child_document.py` (lines 39 to 130 only); the filing tests model `test_ubyport_golden.py:72`-`:125` (`_seed_owned`, `collect_sendable`, `submit_batch` with `_post` captured). Arrival 2026-10-20 style fixed dates; never `date.today()` for the boundary.
   a. Age rule: `certainly_under_age` for 14 years 364 days (True), exactly 15 on the day (False), `00002012`/`00002011` against 2026-10-20 (True/False), `00000000` and `""` (False); `certainly_at_least_age` 18th birthday on the day (True), the day before (False), `00122008` with month unknown cases (latest-birthday rule).
   b. Completeness: `guest_issues` for an unsigned child has no `signature` issue and `guest_is_complete` is True; 15 and 17 years old unsigned: the issue stays; a child with `"imported"` or a junk value: same result as before this brief.
   c. **Filing unchanged:** an adult (signed) and an unsigned foreign child under 15 on one stay: `collect_sendable` returns both; the captured envelope equals `soap.build_zapis_ubytovane(...)` of their `guest_payload`s; then give the child a valid drawn signature and all four `signed_for_*` values and rebuild: the envelope bytes and each `guest_payload` dict are identical. `git diff origin/main -- App/tests/golden` is empty (do not regenerate UbyPort goldens).
   d. **Save path:** a foreign child posted without `signature` saves (303), stores `signature_png == ""`, `submit_state == reporting.PENDING`; a Czech child: `NOT_REQUIRED`; a child posting a drawn signature stores `""`; a 15-year-old without one gets 422 with the signature issue; an adult without one: 422 as today.
   e. **Adult first, then child (same client):** child posted with `signed_by=<adult id>` and `child_sign_role=parent` stores the four fields (wording `u15-2026-11-10`) and `submit_state` PENDING. No fields stored when: `signed_by` is a guest of another client, of another reservation, a 17-year-old, an adult with `"imported"` signature, or the role is `"boss"`; each still saves (303).
   f. **Child first, then adult:** snapshot the child row (`submit_state`, `submit_attempts`, `last_errors`, `updated_at`, `guest_payload`); the adult posts `sign_for_ids=<child id>` and `sign_for_role=responsible_adult`: the four fields are set and the snapshot is unchanged. A child already `SENT` stays `SENT` with the same snapshot. Not linked: a child saved by another client, a 15-year-old, a child already linked to another adult (first wins), and any id when the role is missing.
   g. **Remove:** the device removes the adult: the child's four fields are NULL, its snapshot unchanged.
   h. **Record:** `signature_record` gives `signed_for` with the exact sentence `"Signed by <first> <surname> for <first> <surname>, as parent or legal guardian, <at>, wording u15-2026-11-10"`, `exempt` with `"Under 15, no signature required (§ 103(b))"` (also when the linked adult row is gone), `own`, `imported`, `missing`; `_housebook_export_row(...)["signed"]` gives `by adult` / `not required` / `yes` / `no`; `registration_form_pdf` returns PDF bytes (`%PDF`) for a signed-for and an exempt child.
   Run command A2, then A1, A3, G.
10. Run section 6, write the report.

## 5. Do not touch

`App/app/ubyport/`, `go/internal/ubyport/`, `go/internal/calendar/`, `reporting.guest_payload`, `collect_sendable`, `submit_*`, every `submit_state` write, `App/tests/golden/`, `guest_has_signature`, `dsr.py`, `routes/admin.py` and `guest_form_admin.html` (the host form gains the exemption through `guest_issues` only), `stay_fee.py`, the 1079 child-in-passport logic, every template, `signature.js`, any CSS, i18n catalogs, `db.SCHEMA`, `db.ADDED_COLUMNS`, any dependency. Never push to `main`.

## 6. Commands (each ends `2>&1 | tail -30`)

From `App/`:
- A1: `.venv/bin/python -m pytest tests/test_migrations.py tests/test_db_postgres.py tests/test_goose_migrations.py -q --tb=short -x`.
- A2: `.venv/bin/python -m pytest tests/test_under15_signature_1089.py tests/test_guest_child_document.py tests/test_guest_child_visa_1079.py tests/test_guest_signature_kept.py tests/test_guest_form_draft_1082.py -q --tb=short -x`.
- A3 (retention row): `.venv/bin/python -m pytest tests/test_retention.py tests/test_retention_alignment.py tests/test_retention_job.py tests/test_privacy_first.py tests/test_pii_encryption.py tests/test_dsr_audit.py tests/test_data_keys.py -q --tb=short -x`.
- F (filing row): `.venv/bin/python -m pytest tests/test_ubyport_golden.py tests/test_ubyport_*.py tests/test_submission_*.py tests/test_stale_submission.py tests/test_filed_by_hand.py tests/test_endtoend.py -q --tb=short -x`.
- G (repo root): `cd go && go test ./internal/validation/ ./internal/ubyport/ ./internal/calendar/`.

Repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance

- [ ] Migration 0043 and goose 00014 additive; pins at 43, table counts unchanged; A1 green.
- [ ] Under 15 on arrival (conservative for partial dates): no signature issue in Python and Go; 15 to 17 and adults unchanged; golden.json only gains six cases; G green.
- [ ] A child's form saves without a signature and stores none; `submit_state` values as today.
- [ ] Adult links: both orders, only this device's people, adult 18+ with own valid signature, valid role, first wins; the child row's filing columns untouched; remove clears.
- [ ] Filing unchanged: identical envelope and payload with and without a child signature or link (9c); F green; `git diff origin/main -- App/app/ubyport go/internal/ubyport App/tests/golden` empty.
- [ ] House book CSV and PDF show "Signed by ... for ..., as ..." or "Under 15, no signature required (§ 103(b))".
- [ ] Retention line in `retention.py` and `RETENTION.md`; A3 green.
- [ ] `git diff --stat origin/main` touches only section 3 files.

## 8. Stop and ask

STOP and report `blocked` if: an anchor is missing; the golden regeneration changes an existing case; a filing or submission test fails; the change would need a `submit_state` write, a payload change, a template or a host-route edit; a test fails twice on the same cause (attempt 3 of 3); 60 tool calls or 60k tokens (finish the step, commit, `Done: steps 0 to k. Left: steps k+1 to 10.`).

## 9. Report

`docs/tasks/1089-report.md`, 600 tokens at most: files changed, each command with its last 5 lines, section 7 ticked, deviations, questions. Set this brief `Status: review`. After the fresh Fable diff review, open one PR (body: K-L04 server half; four new personal-data columns on `guest` with their retention line; no new request, cookie or dependency; filing envelope proven identical; owner step: `scripts/pg_schema.py apply` for goose 00014 before deploy). Keep it a draft until 1090 is ready, then merge 1089 first, only with `scripts/merge-pr-on-green.sh`.
