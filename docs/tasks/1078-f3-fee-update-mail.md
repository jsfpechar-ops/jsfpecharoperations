# 1078: F3, one update mail when the stay-fee total changes after the bill (stores the last mailed total)

Status: todo
Tier: A | Depends on: nothing (main alone) | Base commit: 11dcfb6c | Branch: claude/1078-f3
Executor: Fable 5.2 | Attempts: 3 at most | Fits one session: stop at 25 tool calls or 60k tokens (section 8); reads stay at 150 lines or fewer
Review: a fresh Fable reviews the diff against this brief before the PR opens. The PR is then held for the owner's copy review, as F1 was.

**Standalone.** F3 does not use F1 (draft PR #868, brief 1077). It builds its own small fee-update mail from main's `_completion_fee`. `build_completion` and `_guest_mail_content` are not edited here, so a rebase after F1 is trivial. Numbering: 1077's text calls F2 "1078"; the queue gave 1078 to F3, so F2 needs another number.

## 1. Objective

Plan [guest-group-registration](../plans/guest-group-registration.md) P3: the completion mail goes once, with the fee at that moment. If a guest is added, removed or edited afterwards, the screen shows a new total and the mailed amount is stale. F3 stores the last mailed total per booking and, when the live total differs for 10 quiet minutes, sends the lead one update mail with the old and new total.

Owner assumption (decisions.md line 62, 2026-11-09): "Owner asleep: orchestrator takes recommended answers ... Assumed: F3, F4 yes". Plan open question (2): "Update mail on a changed total (F3): recommended yes". So F3 is built; the copy still goes to the owner (section 9).

**Tier A (orchestrator decision).** The brief edits `claim.maybe_notify_completion`, the claim completion function, and adds a read-decide-write sweep that two workers can run at once. Filing code is not edited; if you find you must edit a filing file, STOP (section 8).

## 2. Context

- **Filing unchanged:** nothing sent to the police changes, nor when. No `submit_state` read or write, no call into `reporting` except the existing `_completion_fee` path.
- **Flag off means no change:** when `_completion_fee` returns None (flag `STAY_FEE_GUEST_PAY` off, collection off, total 0, or its own error) the completion path writes nothing new and the sweep sends nothing.
- **A fee that falls to None or 0 sends no mail.** `_completion_fee` returns None for a zero fee and for any internal failure alike, so "now 0 CZK" could be false. The baseline is kept; a later non-zero total that differs mails as usual. Known limit, in the report.
- **Baseline only when a bill went:** the baseline is recorded only if the completion mail was queued and carried a fee. Claims completed before this ships have `fee_mailed_total` NULL and never get an update mail. **No backfill (decided):** NULL stays, because we do not know what was mailed.
- **Privacy:** four new `reservation_claim` columns hold an amount and timestamps: no personal data, but listed (step 1). No new script, dependency, outbound request, cookie, QR or image. The update mail carries amounts and the variable symbol only, never pay details, so it is never a second bill.
- **Never "paid":** no sentence may say the fee was paid, received or settled. The plan's "If you already paid 400 CZK" becomes "If you already sent the earlier amount".
- **Idempotency:** the mail key is `completion_update:{reservation_id}:{fee_mailed_at}:{live}`. `fee_mailed_at` changes only when a send is recorded, so a rerun, a second worker or a crash between enqueue and record reuses the key and `mail.enqueue` returns the existing row. Never put an outbox count or the current time in the key.
- **Concurrency (rules: database):** the decide-and-write step runs inside `with db.immediate() as cur:` after `db.lock_key(cur, "fee_update", reservation_id)`. Inside that block use only `cur.execute` (`?` placeholders): no `db.*` helper, no `mail.enqueue`, no fee computation. The enqueue happens after the block; the record write is a compare-and-set on `fee_mailed_at`.
- **Copy (rule 9):** one explanation in one place. Amounts are formatted with the existing `fee_amount` key; the variable symbol line reuses `mail_completion_fee_vs`. Languages: `i18n.LANGUAGES = ("en", "cs", "de", "es", "fr", "uk")`; uk lives in `App/app/guest_uk_i18n.py`.

### Anchors (verified on 11dcfb6c; re-check each with `grep -nF`)

1. `App/app/claim.py:372`: `def _completion_fee(apartment, reservation) -> Optional[Dict]:` returns `{"total", "lines", "rate", "rails", "vs"}` or None.
2. `App/app/claim.py:757`: `def maybe_notify_completion(reservation, apartment, *, force: bool = False) -> None:`. Line 788 `mail.enqueue(`, 789 `kind="completion",`; line 801 `"UPDATE reservation_claim SET completion_notified_at = ?, updated_at = ? "`; the function ends with `mail.drain(limit=4)`.
3. `App/app/claim.py:814`: `def sweep_reminders() -> Dict[str, int]:` (its `WHERE r.status = 'active' AND r.archived_at IS NULL AND a.active = 1 ` / `"AND a.archived_at IS NULL"` is the model); `App/app/claim.py:28` `def prague_today():`; `App/app/scheduler.py:285`: `("reminders", claim.sweep_reminders),` inside `_job_mail`.
4. `App/app/claim.py:498`: `host = mail_notify.host_details(` (how the host block is read); `App/app/mail_notify.py:1341` `def property_label(apartment: Any, lang: str) -> str:`.
5. `App/app/mail.py:40` and `:96`: `"completion",` in `KINDS` and in `GUEST_KINDS`. `App/app/mail.py:242`: `def enqueue(` (raises on an unknown kind; returns None when mail is off or the stay is a demo; returns the existing id for a known key).
6. `App/app/mail_notify.py:1627`: `def build_completion(` (model for `_block_heading`, `_block_paragraph`, `_guest_text`, `_guest_footer_lines`; line 1709 `if "iban" in fee["rails"]:` with key `mail_completion_fee_vs`); `:1319` `def guest_payload(`.
7. `App/app/db.py:951` `def immediate():`, `:957` `def lock_key(cur, name: str, key: int) -> None:`. Do not edit db.py.
8. `App/app/migrations/0040_stay_fee_rate_history.sql` is the last SQLite file; `App/migrations_pg/00011_stay_fee_rate_history.sql` the last goose file. Models: `0038_property_page_house_rules.sql` and its twin `00009_property_page_house_rules.sql`.
9. `App/app/retention.py:91`: `"""Null ``reservation_claim.email`` once the stay is past the grace window."""`; `docs/privacy/RETENTION.md:17` the claim-email row.
10. `App/app/i18n.py:656` `"mail_completion_subject": (` (en); cs 1405; de 1970; es 2501; fr 3032; `guest_uk_i18n.py:476`. Reused keys: `fee_amount` (en 344), `mail_completion_fee_vs` (en 676).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/migrations/0041_claim_fee_mailed.sql` | create | Four nullable columns (step 1) |
| `App/migrations_pg/00012_claim_fee_mailed.sql` | create | Goose twin (step 1) |
| `App/app/retention.py` | edit | One comment line naming the columns |
| `docs/privacy/RETENTION.md` | edit | One row |
| `App/app/fee_update.py` | create | `record_baseline`, `sweep_fee_updates` (step 2) |
| `App/app/claim.py` | edit | `maybe_notify_completion` only: record the baseline (step 3) |
| `App/app/mail.py` | edit | `"completion_update",` in `KINDS` and `GUEST_KINDS` only |
| `App/app/mail_notify.py` | edit | New `build_fee_update` (step 4) |
| `App/app/scheduler.py` | edit | One tuple after anchor 3: `("fee_updates", fee_update.sweep_fee_updates),` plus the import |
| `App/app/i18n.py` | edit | Five new keys in five languages (step 5) |
| `App/app/guest_uk_i18n.py` | edit | The same five keys in uk |
| `App/tests/test_fee_update_1078.py` | create | Step 6 |
| `docs/tasks/1078-report.md` | create | Report, plus `Status: review` here |

No template, CSS or JS change, so no browser test, screenshot or design-system line; the report says so. If one becomes necessary, STOP.

## 4. Steps (commit after each: `1078 step k`)

1. Confirm anchors 1 to 10 with `grep -nF`; any missing: STOP. Create `0041_claim_fee_mailed.sql` with a two-line comment (brief 1078; amount and timestamps, no personal data) and four statements: `ALTER TABLE reservation_claim ADD COLUMN fee_mailed_total INTEGER;`, `... fee_mailed_at TEXT;`, `... fee_pending_total INTEGER;`, `... fee_pending_since TEXT;`. No default, no `NOT NULL`. Create the goose twin `00012_claim_fee_mailed.sql` exactly in the shape of `00009`: `-- +goose Up`, the twin comment, the same four columns as `ADD COLUMN IF NOT EXISTS` (`BIGINT` for the two totals, `TEXT` for the two timestamps), then the `INSERT INTO schema_migrations (version, name, applied_at) VALUES (41, 'claim_fee_mailed', '2026-11-10T00:00:00+00:00') ON CONFLICT (version) DO NOTHING;`. In `retention.py` add one comment line above anchor 9's function: the `fee_*` columns hold an amount and timestamps, are not personal data and go with the claim row. In RETENTION.md add a row after line 17: "Last mailed stay-fee total and pending change" | `reservation_claim.fee_*` | stay end | with the claim row | none needed: amount and timestamps only | Storage limitation. Run the migration tests of section 6.
2. New `fee_update.py` (`log = logging.getLogger("ubyhost.fee_update")`, `QUIET_MINUTES = 10`). SQL only through `db.query`, `db.query_one`, `db.execute` and, inside the lock, `cur.execute`.
   - `record_baseline(reservation_id: int, total: int) -> None`: `UPDATE reservation_claim SET fee_mailed_total = ?, fee_mailed_at = ?, fee_pending_total = NULL, fee_pending_since = NULL, updated_at = ? WHERE reservation_id = ?`.
   - `sweep_fee_updates(now: Optional[datetime] = None) -> Dict[str, int]` (`now` defaults to UTC now; tests pass it). Candidates: `SELECT r.* FROM reservation r JOIN apartment a ON a.id = r.apartment_id JOIN reservation_claim c ON c.reservation_id = r.id WHERE` anchor 3's four conditions `AND r.source != 'demo' AND r.date_to >= ? AND c.state = 'claimed' AND c.completion_notified_at IS NOT NULL AND c.fee_mailed_total IS NOT NULL AND c.email IS NOT NULL` (parameter `claim.prague_today().isoformat()`: no update mail after departure). So a deleted, cancelled or archived reservation, a revoked claim and a minimised e-mail all drop out.
   - Per candidate, inside `try/except Exception: log.exception(...); continue`: load the apartment (`SELECT * FROM apartment WHERE id = ?`); `fee = claim._completion_fee(apartment, reservation)`; `live = fee["total"] if fee else None`. Then open the lock block (section 2) and re-read `state, email, lang, fee_mailed_total, fee_mailed_at, fee_pending_total, fee_pending_since` with `cur.execute`; if the row is gone, not `claimed`, without e-mail or without baseline: nothing. Otherwise decide:
     - `live is None` or `live == fee_mailed_total`: if a pending value is set, clear both pending columns. No mail.
     - `fee_pending_total != live`: set `fee_pending_total = live`, `fee_pending_since = now` (the wait restarts on every further change); count `pending`.
     - pending equals `live` but younger than `QUIET_MINUTES`: count `pending`.
     - otherwise: due. Leave the block, remembering `old = fee_mailed_total`, `mailed_at = fee_mailed_at`, `email`, `lang`.
   - Due, after the block: build the content (step 4) with `property_name = mail_notify.property_label(apartment, lang)`, `dates = validation.fmt_date_range(reservation["date_from"], reservation["date_to"])`, host as at anchor 4, `vs = fee["vs"] if "iban" in fee["rails"] else ""`; `payload = mail_notify.guest_payload(apartment, content, lang)`; `outbox_id = mail.enqueue(kind="completion_update", idempotency_key=f"completion_update:{id}:{mailed_at}:{live}", to_email=email, cc_email=payload.get("reply_to", ""), subject=content["subject"], payload=payload, reservation_id=..., apartment_id=..., owner_user_id=apartment["owner_user_id"])`. If `outbox_id` is None (mail off) write nothing. Else call `_record_sent(id, live, mailed_at, now_iso)`, which runs `db.execute("UPDATE reservation_claim SET fee_mailed_total = ?, fee_mailed_at = ?, fee_pending_total = NULL, fee_pending_since = NULL, updated_at = ? WHERE reservation_id = ? AND fee_mailed_at = ?", (live, now_iso, now_iso, id, mailed_at))` and count `queued`. There is no plain-text fallback: a composer error is logged and the row retried on the next sweep.
   - Return `{"queued": n, "pending": m}`. The sweep does not call `mail.drain`; the scheduler's `drain` step sends on the next tick.
3. `claim.maybe_notify_completion` (anchor 2), two edits and no other: (a) line 788 `mail.enqueue(` becomes `outbox_id = mail.enqueue(`; (b) directly above the final `mail.drain(limit=4)` add
   ```python
       if outbox_id:
           try:
               fee = _completion_fee(apartment, reservation)
               if fee:
                   from . import fee_update

                   fee_update.record_baseline(reservation["id"], fee["total"])
           except Exception:
               log.exception("fee baseline not recorded reservation_id=%s", reservation["id"])
   ```
   A failure here leaves the baseline NULL (no update mail), never a broken completion. Add the kind to `mail.py` (anchor 5), two lines. Add the scheduler tuple.
4. `mail_notify.build_fee_update(*, lang, property_name, dates, host, old_total, new_total, vs="") -> Dict[str, str]`, built like `build_completion` and returning the same keys (read its `return` first). Format every amount with `_guest_text(lang, "fee_amount", amount=...)`. Subject `mail_fee_update_subject` (property, total); heading `mail_fee_update_heading`; paragraph `mail_fee_update_body` (property, dates, old, new); when `vs` is not empty the existing `mail_completion_fee_vs` line; then `mail_fee_update_more` (diff) when `new_total > old_total`, else `mail_fee_update_less`. Footer via `_guest_footer_lines`. No stay link, button, QR, image, pay details or `qr_spayd` key.
5. i18n, six languages. English is fixed; write the others natively with the same placeholders. Do not change any other key.
   - `mail_fee_update_subject`: "Stay fee for %(property)s changed: now %(total)s"
   - `mail_fee_update_heading`: "The stay fee changed"
   - `mail_fee_update_body`: "The stay fee for your group at %(property)s (%(dates)s) is now %(new)s. It was %(old)s."
   - `mail_fee_update_more`: "If you already sent the earlier amount, the remaining difference is %(diff)s. The payment details are in the earlier e-mail."
   - `mail_fee_update_less`: "If you already sent the earlier amount, ask your host about the difference."
6. Tests, `test_fee_update_1078.py`, reusing the setup helpers of `test_claim_mail.py` (read the setup only). Pass `now=` to the sweep instead of sleeping.
   a. Completion with a fee records `fee_mailed_total` equal to the mailed total. With the flag off, and separately with collection off: the four columns stay NULL, the outbox holds the same single `completion` row with the same key and subject as on main, and no later sweep mails.
   b. Add a guest: first sweep sets pending, queues nothing; a sweep 11 minutes later queues exactly one `completion_update` with old and new total in its text and moves the baseline; two more sweeps add no row (scheduler run twice).
   c. Two changes inside the window: the wait restarts; one mail, with the last total and the first mailed total.
   d. Total drops to a lower non-zero value: the "less" line, not the "more" line. Fee becomes None (set the apartment's `stay_fee_collect` to 0): no mail, baseline unchanged, pending cleared; a later different non-zero total mails once.
   e. Change, then back to the mailed value inside the window: no mail, pending cleared. A → B (mailed) → A (mailed) → B (mailed): three mails, three different keys.
   f. Crash between enqueue and record: monkeypatch `fee_update._record_sent` to raise once; the next sweep leaves exactly one outbox row and moves the baseline. Two workers: after a send, put the four `fee_*` columns back to their values from before the send with `db.execute` and sweep again: still one outbox row (same key).
   g. No mail and no write when: baseline NULL; claim state not `claimed`; claim e-mail NULL; reservation status not `active`; reservation archived; reservation row deleted; `date_to` before today; mail disabled (baseline stays the old value).
   h. Six languages: no `%(` left, each new key differs from English outside English, HTML has no `<img`, no `src="http`, no `qr_spayd` key; none of "paid", "received", "settled" appears in the English text; the `vs` line shows only with the iban rail.
   i. Filing untouched: the whole `reservation` row (every column, so `submit_state` too) and all `guest` rows are identical before and after the sweeps of test b; `reporting.submit_stay_if_complete` monkeypatched to raise is never hit; `fee_update.py` does not contain the string `submit`.
   j. `test_guest_mail.py`, `test_claim_mail.py` and `test_mail_golden.py` pass unchanged.
7. Run section 6, then write the report.

## 5. Do not touch

`reporting.py`, `deadlines.py`, `submit_*`, `door_codes.py`, `stay_fee.py`, `routes/*`, `build_completion`, `build_door_code`, `_guest_mail_content`, `_completion_fee`, templates, CSS, JS, `db.py`, any dependency, any i18n key not named in step 5, existing golden files. Never push to `main`.

## 6. Commands (each ends `2>&1 | tail -30`)

From `App/`: `.venv/bin/python -m pytest tests/test_fee_update_1078.py tests/test_claim_mail.py tests/test_guest_mail.py tests/test_guest_languages.py -q --tb=short -x`. Then the test-map rows: mail `tests/test_ses_mail.py tests/test_mail_*.py tests/test_*_mail.py tests/test_lifecycle_mail.py tests/test_notification_copy.py`; claim `tests/test_claim_*.py`; privacy `tests/test_privacy_first.py tests/test_retention*.py`; database `tests/test_migrations.py tests/test_goose_migrations.py tests/test_pg_row_locks.py`; `tests/test_scheduler.py`. Repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`. If a listed test demands a registry entry for the new mail kind (a preview or kind list), add only that entry and name it under Deviations.

## 7. Acceptance

- [ ] 0041 and its goose twin add four nullable columns; retention line and RETENTION row exist; migration and privacy tests green.
- [ ] A changed total yields exactly one `completion_update` after 10 quiet minutes; reruns, a second worker and a crash before the record add none; NULL baseline, fee None, revoked claim and gone reservation never mail.
- [ ] Flag off: completion path and outbox identical to main. `git diff --stat origin/main` touches only section 3 files; the `claim.py` diff is the two edits of step 3.
- [ ] No `qr_spayd`, image, button or pay details in the update mail; six languages complete; no sentence states a fee as paid.
- [ ] Report has "Copy for owner review" and "Follow-ups".

## 8. Stop and ask

STOP and report `blocked` if: an anchor is missing; a filing file, `_completion_fee`, `_guest_mail_content` or a template would change; `cur.execute` inside `db.immediate()` cannot do the re-read and write; the retention or goose test rejects the shape given; a test fails twice on the same cause (attempt 3 of 3); 25 tool calls or 60k tokens (finish the step, commit, `Done: steps 1 to k. Left: steps k+1 to n.`). Never guess a production setting.

## 9. Report

`docs/tasks/1078-report.md`, 600 tokens at most apart from the copy section: files changed, each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps. Two extra sections:

- **Copy for owner review:** the five keys in six languages, plus the full English text of one "more" mail and one "less" mail.
- **Follow-ups:** the three known limits of section 10, one line each.

Set this brief `Status: review`. After the fresh Fable diff review, open one **draft** PR and do not merge it: it is held until the owner says "copy ok". PR body: new retention line, no new outbound request, filing untouched, goose twin 00012.

## 10. Decisions and known follow-ups

- **Q1 (copy and "paid"), open for the owner:** the plan says "If you already paid 400 CZK"; this brief says "If you already sent the earlier amount". Only wording may change after his review.
- **Q2 (backfill), decided: none.** Bookings completed before this ships keep a NULL baseline and get no update mail. Safe: never a wrong mail.
- **Q3 (door-code mail, F1), known follow-up:** once F1 lands, the door-code mail repeats the fee block with the live total, which can differ from the last mailed total for up to 10 minutes. Not handled here; the orchestrator adds a known-issues line at review.
- **Q4 (constraint on F4):** F4's bill at quiet completion must go through `maybe_notify_completion` (or call `fee_update.record_baseline` with the total it mailed) and must send no fee-change mail of its own. After any baseline, F3 alone mails changes; a forced completion already records its total here.
- **Known limits:** a fee that falls to 0 sends no mail (section 2); if the process dies between enqueue and record and the total changes again before the next sweep, the next mail's "was" is the amount before the lost record; no update mail after `date_to`.

## Owner steps

1. Read "Copy for owner review" in the report; say "copy ok" or name the lines. 2. After the merge, deploy by hand as usual; the migration runs with it.
