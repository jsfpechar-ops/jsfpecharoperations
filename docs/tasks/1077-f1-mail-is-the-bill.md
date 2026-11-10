# 1077: F1, the completion mail is the bill (state-based subject and heading, full pay details, QR inside, "Already paid?" line)

Status: todo
Tier: B | Depends on: 1068 (merged), F0 report (merged) | Base commit: a10d994c | Branch: claude/1077-f1-f2
Executor: Opus 5.5 | Attempts: 3 at most | Fits one session: 30 tool calls, 60k tokens (Haiku caps do not apply; reads stay at 150 lines or fewer)

**One brief, not two.** Plan [guest-group-registration](../plans/guest-group-registration.md) section 9 lists F1 and F2 as two rows. F1 is the mail rewrite; F2 is a ten-line rule change on the guest screen. F1 builds the single shared helper (step 2) and uses it for the mail; F2 (1078, queue item 2.2b) then points the screen at that helper and needs its own UI tests and screenshots. This brief is F1 only. Branch name kept as `claude/1077-f1-f2`.

## 1. Objective

When a booking is complete, the mail to the lead is the bill: it says a fee is owed (subject, heading, intro), lists only the pay ways that really work with every detail inline (bank recipient, account, amount, reference, QR image, Revolut button, cash note) and ends "Already paid? Then there is nothing more to do." The door-code mail repeats the same block when the completion mail has already gone. Fixes plan P1 (mail says "nothing else to do", then asks for money), P2 (mail has no account, QR or Revolut link) and the mail half of P5.

## 2. Context

Rules: UbyPort filing correctness first (this brief touches no filing code; `reporting.py`, `submit_*` and `deadlines.py` stay untouched). Privacy: no new stored field, no new request, no new dependency, no tracking cookies, no third-party script. The account and amount go into the outbox payload as the SPAYD string, as the host's stay-fee mail already does (`mail.QR_SPAYD_KEY`); they are not personal data, so no `retention.py` line. SQL only through `db.py` helpers; no migration (next free number would be 0041, not needed). The guest form and every page keep their exact design: this brief changes mail and one helper only. The app never records or shows a guest stay-fee payment as "paid": the new last line is a question that tells the guest nothing more is needed, and no sentence may say the fee "is paid" or "was received". Copy: AGENTS rule 9 (one explanation in one place; no sentence the button already says; never "no cookies"), in every language present: en, cs, de, es, fr in `App/app/i18n.py` and uk in `App/app/guest_uk_i18n.py`. Legal wording of the fee explanation stays as in the existing `mail_completion_fee_*` texts.

What F0 left in place (`docs/tasks/1069-report.md`): the completion mail is sent only when `filled >= expected` (`claim.py:763`); after a quiet completion with a shortfall only a `door_code` mail goes out, with no fee block (report bug 4). Quiet-completion billing is F4 and needs an owner decision (Owner questions, Q-B), so this brief must NOT bill a partial group.

### Anchors (verified on a10d994c; re-check each with `grep -nF`)

1. `App/app/claim.py:372`: `def _completion_fee(apartment, reservation) -> Optional[Dict]:` returns `{"total", "lines", "rate", "rails", "vs"}`. Its `rails` lists every enabled rail, even one that cannot work (no account, no Revolut link): plan P5.
2. `App/app/claim.py:523`: `fee=_completion_fee(apartment, reservation),` inside `_guest_mail_content`; kind `completion` calls `mail_notify.build_completion`.
3. `App/app/claim.py:786-797`: `payload = mail_notify.guest_payload(apartment, content, lang)` then `mail.enqueue(kind="completion", ...)`. The QR attachment key goes on this payload.
4. `App/app/mail_notify.py:1627`: `def build_completion(` with parameter `fee: Optional[Dict[str, Any]] = None`; line 1652 `subject = _guest_text(lang, "mail_completion_subject", property=property_name)`; lines 1661-1662 `_block_heading(_guest_text(lang, "mail_completion_heading")),` / `_block_paragraph(intro),`; the fee block is `if fee:` at about 1686-1718 and ends with `mail_completion_fee_vs`.
5. `App/app/mail_notify.py:1017`: `f'<img src="cid:{mail.QR_CONTENT_ID}" width="200" height="200" alt="{_esc(qr_alt)}" '` (the existing inline QR in the host mail; copy its style). `App/app/mail.py:370-402`: `QR_SPAYD_KEY = "qr_spayd"`, `QR_CONTENT_ID = "stayfeeqr"`, and `attachments()` builds the PNG from `payload[QR_SPAYD_KEY]` at send time.
6. `App/app/mail_notify.py:1435`: `def build_door_code(` (no fee parameter today). `App/app/door_codes.py:285` `_send_code_mail`, which builds it at line 313 and enqueues `kind="door_code"` with `payload[mail.DOOR_CODE_KEY] = row["pin_enc"]`.
7. `App/app/routes/guest.py:2415-2470`: `_fee_pay_panel(apartment, reservation, t, qr_ok=True)` holds the working rule for rails: iban only `if key == "iban" and account`, revolut only `elif key == "revolut" and apartment["stay_fee_guest_revolut_link"]`, cash note `apartment["stay_fee_guest_cash_note"] or t("fee_cash_default")`; account from `legal_entity` (`iban`, else `payments.normalise_account(entity["bank_account"])[1]`); `payee` is `entity["name"]`.
8. `App/app/payments.py:140` `def spayd(iban, amount, vs, message, bic="")`; `:153` `qr_png_bytes`; `:162` `qr_data_uri`.
9. `App/app/i18n.py:656-679` (en): `mail_completion_subject`, `mail_completion_preheader`, `mail_completion_heading`, `mail_completion_intro`, `mail_completion_fee_heading`, `mail_completion_fee_total`, `mail_completion_fee_calc_title`, `mail_completion_fee_ways`, `mail_completion_fee_vs`. Other languages: `mail_completion_subject` at `i18n.py:1405` (cs), `:1970` (de), `:2501` (es), `:3032` (fr), `guest_uk_i18n.py:476` (uk). Also `fee_rail_iban`, `fee_rail_revolut`, `fee_rail_cash` (`i18n.py:349-351` en).

### Owner questions (do not decide; the buildable part is marked)

- Q-A (open): is `UBYHOST_STAY_FEE_GUEST_PAY` on in production? Not in decisions.md. Safe: all new fee text sits behind the existing `STAY_FEE_GUEST_PAY` and `stay_fee_collect` checks in `_completion_fee`; with the flag off the mail is byte-for-byte today's.
- Q-B (open, F4): bill the registered people when a booking completes after 12 quiet hours (plan section 9, "Open for the owner" 1). Not built here. The door-code mail repeats the fee block ONLY when `claim["completion_notified_at"]` is set (the full-group completion mail has gone). A quiet-completion door-code mail stays without a fee block, as today.
- Q-C (open, legal): the plan marks F1 "legal: mail copy". The new texts only restate the existing fee wording plus pay details; the owner or lawyer reads them in the PR before merge. The brief changes no privacy policy text.
- Q-D (open): the plan puts the "Already paid?" line in every fee mail, so a second mail (door code) never reads as a second bill. Built as planned.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/stay_fee.py` | edit | New `guest_pay_ways(apartment, reservation, charge, qr_ok)` (step 2) |
| `App/app/claim.py` | edit | `_completion_fee` uses it; completion payload gets the QR key; door-code helper |
| `App/app/mail_notify.py` | edit | `build_completion` and `build_door_code` render the new block |
| `App/app/door_codes.py` | edit | `_send_code_mail` passes the fee block and QR key |
| `App/app/i18n.py`, `App/app/guest_uk_i18n.py` | edit | New and removed keys in all six languages |
| `App/tests/test_completion_fee_mail_1077.py` | create | The tests of step 7 |
| `docs/tasks/1077-report.md` | create | Report; also set this brief `Status: review` |

No template, CSS or JS file changes. If you find you must edit one, STOP (section 8).

## 4. Steps (commit after each: `1077 step k`)

1. Confirm anchors 1 to 9 with `grep -nF`. Any missing: STOP.
2. In `stay_fee.py` add `guest_pay_ways(apartment, reservation, charge, qr_ok)` returning `[{"key": "iban", "payee", "account_display", "spayd"}, {"key": "revolut", "link"}, {"key": "cash", "note"}]`, in the order of `stay_fee_guest_default_rail` first (as `_fee_pay_panel` orders them), listing only ways that work (anchor 7 conditions), `spayd` set only when `qr_ok` (via `payments.spayd(account, total, vs, f"Stay fee {vs}")`). Plus `qr_offered_for_reservation(reservation)`: True when any non-archived guest of the booking has nationality `CZE` or `SVK` (the plan's one rule). Do NOT edit `_fee_pay_panel` or anything in `routes/guest.py` (that is F2).
3. `claim._completion_fee`: build `rails` from `guest_pay_ways` (so a way that cannot work is never listed) and add `"ways"` with the details. Keep the `try/except` returning None: a failure drops the fee block, never the mail.
4. `mail_notify.build_completion`: when `fee` is set use the fee variants of subject, preheader, heading and intro; keep today's texts when not. Fee block order: total line, calculation panel (unchanged), "Pay once for the whole group, in any one way:", then per way: bank transfer with recipient, account, amount, reference (VS) and `<img src="cid:...">` QR only when `spayd` is present (alt text `mail_completion_fee_qr_alt`); a button "Pay {total} CZK with Revolut" (`_block_button`); the cash note; last line `mail_completion_fee_already`. Remove the sentence "The payment details are on your stay page" (key `mail_completion_fee_ways`, delete it from all six languages). The plain-text part carries the same lines and the account and reference in plain text. Door code stays below the fee block as today.
5. `claim.py` ~786: `payload[mail.QR_SPAYD_KEY] = spayd` when the fee has a `spayd`. Door code path: `_send_code_mail` builds the same fee block (call a small `claim`-side function; no circular import: import inside the function, as the file already does) only when `claim["completion_notified_at"]` is set; pass `fee=` to `build_door_code`, which appends the identical block and the "Already paid?" line, and set the QR key on its payload. The door-code mail subject stays "Your door code for ...".
6. i18n: add to all six languages `mail_completion_subject_fee` (en: "Everyone is registered for %(property)s. Stay fee to pay: %(total)s CZK"), `mail_completion_preheader_fee`, `mail_completion_heading_fee`, `mail_completion_intro_fee`, `mail_completion_fee_once`, `mail_completion_fee_bank` (with recipient, account, amount, reference), `mail_completion_fee_qr_alt`, `mail_completion_fee_revolut` (button), `mail_completion_fee_already` (en: "Already paid? Then there is nothing more to do."). The fee intro must not say "nothing else to do" and no text may claim the fee is paid. Every language gets a native line; the uk file uses the same key set. Rule 9: do not repeat the total in three sentences; the subject and the fee line each state it once.
7. Tests in `App/tests/test_completion_fee_mail_1077.py` (build on `test_claim_*.py` fixtures): fee on, bank only, Czech guest: subject names the total, body has account, reference, `cid:` image, payload has `qr_spayd`, no sentence "nothing else"; non-Czech guest: no QR, bank details still shown; Revolut without a link or bank without an account: that way absent; cash note shown; flag off or collect off: mail equals today's text; all six languages render and contain no `%(`; door-code mail after a sent completion mail repeats the block, before it (quiet completion) has none; the door-code PIN still appears only as `mail.DOOR_CODE_MARKER` in the stored outbox row; no body contains "paid" except the question line.

## 5. Do not touch

`reporting.py`, `deadlines.py`, anything filing; `routes/guest.py` and `_fee_pay_panel` (that is F2); templates, CSS, JS, migrations; `retention.py`; any dependency. Never push to `main`.

## 6. Commands (each ends `2>&1 | tail -30`)

From `App/`: `.venv/bin/python -m pytest tests/test_completion_fee_mail_1077.py -q --tb=short -x`. Then the [test-map](../context/test-map.md) rows for what changed: Mail, SES (`test_ses_mail.py test_mail_*.py test_*_mail.py test_lifecycle_mail.py test_notification_copy.py`), Door codes (`test_door_code*.py`), Invoices, stay fee (`test_stay_fee*.py`), Filing/claim (`test_claim_*.py`) and the privacy file `test_privacy_first.py`. From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`. No browser test is needed because no page changes; say so in the report.

## 7. Acceptance

- [ ] A fee mail shows total, calculation, every working way with full details, the QR image for Czech or Slovak bookings only, and ends with the "Already paid?" line; no "nothing else to do" sentence appears above it.
- [ ] A way that cannot work is never listed; flag off or collect off leaves the mail unchanged.
- [ ] Door-code mail repeats the block only after the completion mail went; no PIN is stored in the outbox.
- [ ] Six languages complete; `mail_completion_fee_ways` removed everywhere; no sentence says "paid" as a status.
- [ ] `git diff --stat origin/main` touches only section 3 files; no `reporting.py`, migration, template or dependency change.

## 8. Stop and ask

Stop and write the report as `blocked` if: an anchor is missing; the work needs a template, CSS, migration or new dependency; a test fails twice (attempt 3 of 3); you reach 25 tool calls. Never guess a production setting.

## 9. Report

`docs/tasks/1077-report.md`, 600 tokens at most: files changed, each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps. Set this brief `Status: review`, then open one PR (never push to `main`; merge only with `scripts/merge-pr-on-green.sh`).

## Owner steps

Answer Q-A to Q-C. Deploy by hand after merge. F2 (1078) follows; F3 and F4 stay waiting on their decisions.
