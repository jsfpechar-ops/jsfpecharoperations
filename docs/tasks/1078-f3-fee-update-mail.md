# 1078: F3, one update mail when the stay-fee total changes after the bill (stores the last mailed total)

Status: todo
Tier: B | Depends on: nothing (main alone) | Base commit: 11dcfb6c | Branch: claude/1078-f3
Executor: Opus 5.5 | Attempts: 3 at most | Fits one session: stop at 25 tool calls or 60k tokens (section 8); reads stay at 150 lines or fewer

**Standalone.** F3 does not use F1 (draft PR #868, brief 1077). It builds its own small fee-update mail from main's `_completion_fee`. If F1 merges first the two touch different functions (`build_completion` is not edited here); a rebase is trivial. Numbering: 1077's text calls F2 "1078"; the queue gave 1078 to F3, so F2 needs another number.

## 1. Objective

Plan [guest-group-registration](../plans/guest-group-registration.md) P3: the completion mail goes once, with the fee at that moment. If a guest is added, removed or edited afterwards, the screen shows a new total and the mailed amount is stale. F3 stores the last mailed total per booking and, when the live total differs, sends the lead one update mail, gathered over 10 minutes, with old and new total and the pay reference unchanged.

Owner assumption (decisions.md line 62, 2026-11-09): "Owner asleep: orchestrator takes recommended answers and merges green, reviewed PRs itself (this build only). Assumed: F3, F4 yes; G11 no stored preference; ..." Plan open question (2) "Update mail on a changed total (F3): recommended yes". So F3 is built; the copy still goes to the owner (section 9).

**Tier B, not A.** Filing code (`reporting.py`, `submit_*`, `deadlines.py`, UbyPort payloads) is untouched and only read through `reporting.reservation_progress`'s existing path. The one edit in a claim function (`maybe_notify_completion`) writes a mail bookkeeping value after the mail is queued. Test 7h pins that no filing table or submit state changes. If the executor finds it must edit a filing file, STOP (section 8); the orchestrator then re-tiers to A.

## 2. Context

- **Filing unchanged:** nothing sent to the police changes, nor when. No `submit_state` write.
- **Privacy:** four new `reservation_claim` columns hold an amount and two timestamps: not personal data, but listed (step 1, `retention.py` line, RETENTION.md row). No new script, dependency, outbound request or cookie. No QR or image in the update mail: it links nothing and carries no pay details (reference only), so it is never a second bill.
- **Never "paid":** the app never records or shows a stay fee as paid. No sentence may say the fee was paid, received or settled. The plan's example ("If you already paid 400 CZK, ...") is conditional, but see open question Q1.
- **Flag:** `STAY_FEE_GUEST_PAY` treated as on (decisions.md). Everything sits behind `_completion_fee`'s existing check; when it returns None (collection off, fee 0) no update goes.
- **No double sending:** one `completion_update` mail per distinct new total; the idempotency key includes the old and new total and the send count; a sweep rerun adds no row.
- **No baseline, no mail:** claims whose completion mail went before this migration have `fee_mailed_total` NULL. They get no update mail (we do not know what was mailed). Q2 asks for a backfill.
- **Partial groups:** F4 is not built. A quiet-completion mail sent with `force=True` records its total like any other; later changes then mail an update.
- **Copy (rule 9):** one explanation in one place; "no tracking cookies" never "no cookies" (not needed here). Languages en, cs, de, es, fr in `App/app/i18n.py`, uk in `App/app/guest_uk_i18n.py`. Five new keys (step 5).

### Anchors (verified on 11dcfb6c; re-check each with `grep -nF`)

1. `App/app/claim.py:372`: `def _completion_fee(apartment, reservation) -> Optional[Dict]:` returns `{"total", "lines", "rate", "rails", "vs"}`; `"vs": str(int(reservation["id"]))`.
2. `App/app/claim.py:757`: `def maybe_notify_completion(reservation, apartment, *, force: bool = False) -> None:`. Line 789 `kind="completion",`; line 801 the write `"UPDATE reservation_claim SET completion_notified_at = ?, updated_at = ? "`.
3. `App/app/claim.py:814`: `def sweep_reminders() -> Dict[str, int]:`; `App/app/scheduler.py:285`: `("reminders", claim.sweep_reminders),` inside `_job_mail`.
4. `App/app/claim.py:440`: `def _guest_mail_content(`; line 512 `if kind == "completion":`; subject map at 566 `"completion": "mail_completion_subject",`; plain body at 625 `if kind == "completion":`.
5. `App/app/mail.py:40` and `:96`: `"completion",` in `KINDS` and in `GUEST_KINDS`. `App/app/mail.py:242`: `def enqueue(` (raises on an unknown kind).
6. `App/app/mail_notify.py:1627`: `def build_completion(` (model for blocks: `_block_heading`, `_block_paragraph`, `_block_panel`, `_guest_text`, `_guest_footer_lines`); `:1319` `def guest_payload(`.
7. `App/app/db.py:377`: `completion_notified_at  TEXT,` in the `reservation_claim` table. db.py line 989 says new columns live only in a numbered migration file; do not edit db.py.
8. `App/app/migrations/0040_stay_fee_rate_history.sql` is the last file; style model `0038_property_page_house_rules.sql` (`ALTER TABLE ... ADD COLUMN`).
9. `App/app/retention.py:91`: `"""Null ``reservation_claim.email`` once the stay is past the grace window."""`; `docs/privacy/RETENTION.md:17` the claim-email row.
10. `App/app/i18n.py:656` `"mail_completion_subject": (` (en); cs 1405; de 1970; es 2501; fr 3032; `guest_uk_i18n.py:476`. Existing keys reused: `mail_completion_fee_heading`, `fee_vs_label`, `fee_amount`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/migrations/0041_claim_fee_mailed.sql` | create | Four columns (step 1) |
| `App/app/retention.py`, `docs/privacy/RETENTION.md` | edit | One line / one row naming the columns |
| `App/app/fee_update.py` | create | `record_mailed`, `sweep_fee_updates` (step 2) |
| `App/app/claim.py` | edit | `maybe_notify_completion` records the baseline; `_guest_mail_content` gets kind `completion_update` (step 3) |
| `App/app/mail.py` | edit | `"completion_update"` in `KINDS` and `GUEST_KINDS` only |
| `App/app/mail_notify.py` | edit | New `build_fee_update` (step 4) |
| `App/app/scheduler.py` | edit | One tuple in `_job_mail`: `("fee_updates", fee_update.sweep_fee_updates),` plus import |
| `App/app/i18n.py`, `App/app/guest_uk_i18n.py` | edit | Five new keys, six languages (step 5) |
| `App/tests/test_fee_update_1078.py` | create | Step 7 |
| `docs/tasks/1078-report.md` | create | Report, plus `Status: review` here |

No template, CSS or JS changes, so no page changes: no browser test and no screenshot are needed (`docs/tasks/screenshots-1078/` stays absent) and no design-system line; the report says so. A new component (a mail block) is not added. If a template, CSS or JS edit becomes necessary, STOP.

## 4. Steps (commit after each: `1078 step k`)

1. Confirm anchors 1 to 10 with `grep -nF`; any missing: STOP. Create `0041_claim_fee_mailed.sql`: `ALTER TABLE reservation_claim ADD COLUMN fee_mailed_total INTEGER;`, `... fee_mailed_at TEXT;`, `... fee_pending_total INTEGER;`, `... fee_pending_since TEXT;` (one statement each, Postgres-portable, no default). Add the `retention.py` line next to anchor 9 as a comment on the claim-row step: these columns hold an amount and timestamps, are not personal data, and go with the claim row (no separate purge). Add the RETENTION.md row after line 17: item "Last mailed stay-fee total and pending change", where `reservation_claim.fee_*`, trigger stay end, period "with the claim row", mechanism "none needed: amount and timestamps only", basis "Storage limitation". Check the lint accepts it (step 8).
2. New `fee_update.py`, SQL only through `db.query`, `db.query_one`, `db.execute`:
   - `record_mailed(reservation_id, total)`: `UPDATE reservation_claim SET fee_mailed_total = ?, fee_mailed_at = ?, fee_pending_total = NULL, fee_pending_since = NULL, updated_at = ? WHERE reservation_id = ?`.
   - `sweep_fee_updates() -> Dict[str, int]`: select claims with `state = 'claimed'`, `completion_notified_at IS NOT NULL`, `fee_mailed_total IS NOT NULL`, `email IS NOT NULL`, joined to active reservations of active, non-archived apartments (copy the `WHERE` of `sweep_reminders`, anchor 3, lines 830-832; `source != 'demo'`). Per row: `fee = claim._completion_fee(apartment, reservation)`, `live = fee["total"] if fee else 0` (a fee that fell to 0 still counts as a change). Compare to `fee_mailed_total`:
     - equal: clear `fee_pending_*` if set; continue.
     - different and `fee_pending_total != live`: set `fee_pending_total = live`, `fee_pending_since = now`; continue (the 10-minute wait restarts on every further change).
     - different, `fee_pending_total == live` and `now - fee_pending_since >= 10 minutes` (constant `QUIET_MINUTES = 10`): enqueue (step 3) then `record_mailed(id, live)`.
   Wrap each reservation in `try/except Exception` with `log.exception` and `continue`, as `sweep_reminders` does for `db.DecryptionError`. Return `{"queued": n, "pending": m}`.
   - Enqueue: `mail.enqueue(kind="completion_update", idempotency_key=f"completion_update:{id}:{old}:{live}:{n}", ...)` where `n` is the count of earlier `completion_update` rows for the reservation (`SELECT COUNT(*) AS n FROM email_outbox WHERE reservation_id = ? AND kind = 'completion_update'`), so a total that returns to an earlier value later still mails. Same `to_email`, `cc_email=payload.get("reply_to", "")`, `subject`, `owner_user_id` pattern as `maybe_notify_completion` (anchor 2). If `mail.enqueue` returns None (mail off, demo) do not call `record_mailed`.
3. Wiring. In `claim.maybe_notify_completion`, directly after the `UPDATE ... completion_notified_at` write (anchor 2), add `fee = _completion_fee(apartment, reservation)` and `fee_update.record_mailed(reservation["id"], fee["total"] if fee else 0)` (import `fee_update` inside the function, as `door_codes` is). The baseline is the live total at queue time. In `_guest_mail_content` add `if kind == "completion_update":` returning `mail_notify.build_fee_update(lang=..., property_name=..., dates=..., stay_url=..., host=..., old_total=..., new_total=..., vs=...)`; add the three extra keyword parameters `old_total: int = 0`, `new_total: int = 0`, `vs: str = ""` to its signature; add `"completion_update": "mail_fee_update_subject"` to the subject map (anchor 4) and a plain-body branch only if the file's own pattern needs one (read 625-640 first). Add the kind to `mail.py` (anchor 5), two lines.
4. `mail_notify.build_fee_update(*, lang, property_name, dates, stay_url, host, old_total, new_total, vs) -> Dict[str, str]`, built like `build_completion` blocks: subject `mail_fee_update_subject` (property, total); heading `mail_fee_update_heading`; paragraph `mail_fee_update_body` (property, old, new, vs); a second paragraph, only when `new_total > old_total`, `mail_fee_update_more` (difference, vs); when `new_total < old_total` or `new_total == 0`, `mail_fee_update_less` (old) instead. The stay link is not added (the guest's device already has it; the lead can open the stay page as today). Footer via `_guest_footer_lines`. No QR, no pay details, no button, no `qr_spayd` key. Return the same keys as `build_completion` returns (read its `return` first).
5. i18n, six languages. English is fixed, others written natively with the same placeholders ("Kč" in cs):
   - `mail_fee_update_subject`: "Stay fee for %(property)s changed: now %(total)s CZK"
   - `mail_fee_update_heading`: "The stay fee changed"
   - `mail_fee_update_body`: "The stay fee for your group at %(property)s is now %(new)s CZK (was %(old)s CZK). Payment reference: %(vs)s."
   - `mail_fee_update_more`: "If you already sent the earlier amount, send the %(diff)s CZK difference with the same reference. The payment details are in the earlier e-mail."
   - `mail_fee_update_less`: "If you already sent the earlier amount, ask your host about the difference."
   The six-language check covers all five. No key may say "paid", "received" or "settled". Do not change any other key.
6. Run step 1 and 7 commands.
7. Tests, `test_fee_update_1078.py`, reusing the fixtures and setup helpers of `test_claim_mail.py` (read the setup only):
   a. full completion records `fee_mailed_total` equal to the mailed total; completing with collection off records 0 and later never mails.
   b. add a guest (total rises): first sweep sets pending and queues nothing; a second sweep after 11 minutes (use the file's time-travel helper or set `fee_pending_since` back through `db.execute`) queues exactly one `completion_update` with old and new total in its text, then `fee_mailed_total` is the new total; a third sweep adds no row.
   c. two changes within the window: one mail, with the last total and the first mailed total as "was".
   d. total drops: the "less" line shows, the "more" line does not; total falls to 0: one mail, no "more" line.
   e. total changes then returns to the mailed value before the window ends: no mail, pending cleared.
   f. NULL baseline (completion mail sent before the migration) never mails. Mail disabled: nothing recorded as mailed.
   g. update mail in six languages: no `%(`, new keys differ from English outside English; HTML has no `<img`, no `src="http`, no `qr_spayd` key; none of "fee is paid", "was paid", "has been paid", "payment received", "settled" appears.
   h. filing untouched: guest and submission rows byte-identical before and after a sweep; the sweep never calls `reporting.submit_stay_if_complete` (monkeypatch it to raise).
   i. `build_completion` output for a given input is identical to before (existing `test_guest_mail.py` passes unchanged).
8. Retention lint and `context_lint` (section 6).

## 5. Do not touch

`reporting.py`, `deadlines.py`, `submit_*`, `door_codes.py`, `routes/*`, `build_completion`, `build_door_code`, templates, CSS, JS, `db.py`, any dependency, any i18n key not named in step 5. Never push to `main`.

## 6. Commands (each ends `2>&1 | tail -30`)

From `App/`: `.venv/bin/python -m pytest tests/test_fee_update_1078.py tests/test_claim_mail.py tests/test_guest_mail.py tests/test_guest_languages.py -q --tb=short -x`. Then test-map rows: mail `tests/test_ses_mail.py tests/test_mail_*.py tests/test_*_mail.py tests/test_lifecycle_mail.py tests/test_notification_copy.py`; claim `tests/test_claim_*.py`; privacy `tests/test_privacy_first.py tests/test_retention*.py`; migrations `tests/test_migrations*.py` (run `ls tests | grep -i 'migration\|schema' | tail -30` first and run what exists); `tests/test_scheduler*.py`. Repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`. `test_mail_golden.py` must pass unchanged; do not regenerate golden files.

## 7. Acceptance

- [ ] Migration 0041 adds four nullable columns; retention line and RETENTION row exist; privacy test green.
- [ ] A changed total yields exactly one `completion_update` mail after 10 quiet minutes; reruns add none; NULL baseline and fee-off never mail.
- [ ] No filing file changed; `git diff --stat origin/main` touches only section 3 files; no `qr_spayd`, image, button or pay details in the update mail.
- [ ] Six languages complete, no sentence states a fee as paid; report has "Copy for owner review" (five keys, six languages, plus the English text of one "more" and one "less" mail).

## 8. Stop and ask

STOP and report `blocked` if: an anchor is missing; a filing file or template would change; `retention.py` or the lint rejects the line shape; a test fails twice on the same cause (attempt 3 of 3); 25 tool calls or 60k tokens (finish the step, commit, `Done: steps 1 to k. Left: steps k+1 to n.`). Never guess a production setting.

## 9. Open questions for the owner, and what is safe meanwhile

- **Q1 (copy and "paid"):** the plan's text says "If you already paid 400 CZK". This brief words it as "If you already sent the earlier amount", which avoids saying the fee is paid. Owner reads the copy in the report. Safe now: everything; only wording may change.
- **Q2 (backfill):** bookings completed before this ships have no baseline and get no update mail. Option: a one-time backfill of `fee_mailed_total` from the live total at deploy. Not built; safe: leave NULL (no mail is sent, never a wrong mail).
- **Q3 (door-code mail, F1):** once F1 lands, the door-code mail repeats the fee block with the live total, which can differ from the last update mail's total for up to 10 minutes. Not handled here; decide when F1 is reviewed.
- **Q4 (F4 interplay):** F4 (bill at quiet completion) is separate; F3 already mails updates for a forced completion, which F4's mail should not duplicate.

## 10. Report

`docs/tasks/1078-report.md`, 600 tokens at most apart from the copy section: files changed, each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps. Set this brief `Status: review`, open one PR, do not merge it. PR body: new retention line, no new outbound request, filing untouched.

## Owner steps

1. Read "Copy for owner review" in the report; say "copy ok" or name the lines. 2. Answer Q2. 3. After the merge, run the migration with the normal deploy by hand.
