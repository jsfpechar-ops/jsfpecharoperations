# 1077: F1, the completion mail is the bill (state-based subject and heading, full pay details, QR inside, "Already paid?" line)

Status: todo
Tier: B | Depends on: 1068 (merged), F0 report (merged) | Base commit: a10d994c | Branch: claude/1077-f1-f2
Executor: Opus 5.5 | Attempts: 3 at most | Fits one session: stop at 25 tool calls or 60k tokens (section 8); reads stay at 150 lines or fewer

**One brief, not two.** Plan [guest-group-registration](../plans/guest-group-registration.md) section 9 lists F1 and F2 as two rows. F1 is the mail rewrite; F2 is a ten-line rule change on the guest screen. F1 builds the single shared helper (step 2) and uses it for the mail; F2 (1078, queue item 2.2b) then points the screen at that helper and needs its own UI tests and screenshots. This brief is F1 only. Branch name kept as `claude/1077-f1-f2`.

## 1. Objective

When a booking is complete, the mail to the lead is the bill: it says a fee is owed (subject, heading, intro), lists only the pay ways that really work with every detail inline (bank recipient, account, amount, variable symbol, QR image, Revolut button, cash note) and ends "Already paid? Then there is nothing more to do." The door-code mail repeats the same block when the completion mail has already gone. Fixes plan P1 (mail says "nothing else to do", then asks for money), P2 (mail has no account, QR or Revolut link) and the mail half of P5.

## 2. Context

Rules that bind this brief:

- **Filing:** no filing code changes (`reporting.py`, `submit_*`, `deadlines.py` untouched).
- **Privacy:** no new stored field, no migration, no `retention.py` line, no new dependency, no new outbound request. The QR is an inline attachment (`cid:`), built from the payload at send time by the existing `mail.attachments()`. Never write `<img src="http...">` or a `data:` image into a mail: no remote image, no tracking pixel. The outbox gains only the SPAYD string (host account, amount, reservation id), as the host stay-fee mail already stores it. The Revolut button is the host's own link, unchanged, with no added parameter.
- **Never "paid":** the app never records or shows a guest stay-fee payment as paid. No new sentence may say the fee is paid, was received or is settled. The closing line is a question.
- **No double sending:** add no `mail.enqueue` call and change no `idempotency_key`, no `kind`, no `completion_notified_at` or `notified_at` write. This brief changes what two existing mails say, never when or how often they go.
- **Flag (owner decision):** `STAY_FEE_GUEST_PAY` is treated as on (decisions.md, 2026-11-09). Everything new still sits behind the existing check in `_completion_fee` (`apartment["stay_fee_collect"] and config.STAY_FEE_GUEST_PAY`); when it returns None both mails are byte-for-byte today's.
- **Partial groups (owner decision):** F4 is not built, so a partial group is not billed. The completion mail goes only when `filled >= expected` (`claim.py:763`, unchanged). The door-code mail carries the fee block only when `completion_notified_at` is set on the claim row.
- **Copy (rule 9):** one explanation in one place, so the mail reuses the guest screen's keys for labels (anchor 9) and adds only six keys. State the total once in the subject and once in the fee line; the amount row and the Revolut button reuse screen keys. Languages: en, cs, de, es, fr in `App/app/i18n.py`, uk in `App/app/guest_uk_i18n.py`. The owner reads the new copy in the PR before merge (step 8).

### Anchors (verified on a10d994c; re-check each with `grep -nF`)

1. `App/app/claim.py:372`: `def _completion_fee(apartment, reservation) -> Optional[Dict]:` returns `{"total", "lines", "rate", "rails", "vs"}`. Its `rails` lists every enabled rail, even one that cannot work.
2. `App/app/claim.py:523`: `fee=_completion_fee(apartment, reservation),` inside `_guest_mail_content`.
3. `App/app/claim.py:785`: `payload = mail_notify.guest_payload(apartment, content, lang)` in `maybe_notify_completion`, followed by `mail.enqueue(` with `kind="completion",`.
4. `App/app/mail_notify.py:1627`: `def build_completion(`. Line 1652: `subject = _guest_text(lang, "mail_completion_subject", property=property_name)`. Line 1661: `_block_heading(_guest_text(lang, "mail_completion_heading")),`. Fee block: `if fee:` at 1685 down to the `mail_completion_fee_vs` lines at about 1712. Preheader: `preheader=_guest_text(lang, "mail_completion_preheader"),`.
5. `App/app/mail_notify.py:1017`: `f'<img src="cid:{mail.QR_CONTENT_ID}" width="200" height="200" alt="{_esc(qr_alt)}" '` (lines 1016-1018 are the whole `<tr>`; copy them). `App/app/mail.py:370`: `QR_SPAYD_KEY = "qr_spayd"`; `attachments()` turns `payload[QR_SPAYD_KEY]` into the inline PNG.
6. `App/app/mail_notify.py:1435`: `def build_door_code(` (no fee parameter today). `App/app/door_codes.py:285`: `def _send_code_mail(door_code_id: int) -> None:`; line 299 `if not claim["completion_notified_at"]:`; line 316 `payload = mail_notify.guest_payload(apartment, content, lang)`. In this function the name `claim` is the claim ROW.
7. `App/app/routes/guest.py:2414`: `def _fee_pay_panel(apartment, reservation, t, qr_ok=True):`. Read 2414-2465 only, as the model for step 2. Do not edit it.
8. `App/app/payments.py:140`: `def spayd(iban: str, amount, vs: str, message: str, bic: str = "") -> str:`; `:128` `def format_iban(iban: str) -> str:`.
9. Screen keys that already exist in all six languages (`grep -c '"fee_payee":' App/app/i18n.py` gives 5, the uk file 1): `fee_rail_iban`, `fee_rail_cash`, `fee_payee`, `fee_iban`, `fee_amount_label`, `fee_vs_label`, `fee_amount`, `fee_qr_alt`, `fee_revolut_button`, `fee_cash_default`, `fee_no_rails`. Mail keys: `"mail_completion_subject"` at `i18n.py:656` (en), `:1405` (cs), `:1970` (de), `:2501` (es), `:3032` (fr), `guest_uk_i18n.py:476` (uk); `mail_completion_fee_ways` and `mail_completion_fee_vs` sit about 20 lines below each.
10. `App/tests/test_guest_mail.py:1077-1108`: three tests that assert the two sentences this brief removes.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/stay_fee.py` | edit | New `guest_pay_ways` and `qr_offered_for_reservation` (step 2) |
| `App/app/claim.py` | edit | `_completion_fee` (step 3); QR key on the completion payload (step 5) |
| `App/app/mail_notify.py` | edit | New `_fee_block`; `build_completion` and `build_door_code` use it (step 4) |
| `App/app/door_codes.py` | edit | `_send_code_mail` passes the fee and the QR key (step 5) |
| `App/app/i18n.py`, `App/app/guest_uk_i18n.py` | edit | Six new keys, two removed, in all six languages (step 6) |
| `App/tests/test_guest_mail.py` | edit | Only the three tests of anchor 10 (step 7) |
| `App/tests/test_completion_fee_mail_1077.py` | create | The tests of step 7 |
| `docs/tasks/1077-report.md` | create | Report; also set this brief `Status: review` |

No template, CSS or JS file changes. If you find you must edit one, STOP (section 8).

## 4. Steps (commit after each: `1077 step k`)

1. Confirm anchors 1 to 10 with `grep -nF`. Any missing: STOP. From the repo root run `grep -rln 'mail_completion_fee_ways\|mail_completion_fee_vs' App | tail -30`; a hit outside `i18n.py`, `guest_uk_i18n.py`, `mail_notify.py`: STOP.
2. `stay_fee.py`, two new functions (the file already imports `db` and `payments`):
   - `qr_offered_for_reservation(reservation) -> bool`: True when any row of `SELECT nationality FROM guest WHERE reservation_id = ? AND archived_at IS NULL` has `(nationality or "").upper()` in `("CZE", "SVK")`.
   - `guest_pay_ways(apartment, reservation, charge, qr_ok) -> list`: copy the account, payee, enabled-set and order logic of `_fee_pay_panel` (anchor 7) exactly, including "qr" meaning "iban" and the default rail first. Emit only ways that work: `{"key": "iban", "payee": payee, "account": payments.format_iban(account), "spayd": spayd}` only when an account exists, with `spayd = payments.spayd(account, total, vs, f"Stay fee {vs}") if qr_ok else ""`; `{"key": "revolut", "link": ...}` only when `stay_fee_guest_revolut_link` is set; `{"key": "cash", "note": apartment["stay_fee_guest_cash_note"] or ""}`. `total = int(charge["total_czk"])`, `vs = str(int(reservation["id"]))`.
3. `claim._completion_fee`: after `lines`, set `ways = stay_fee.guest_pay_ways(apartment, reservation, charge, stay_fee.qr_offered_for_reservation(reservation))`. Return the same dict with `"rails": [way["key"] for way in ways]` and a new `"ways": ways`. Delete the now unused `keys` set. Keep the flag check first and the `try/except` returning None. When no way works the fee is still returned (the amount is owed) with `ways == []`.
4. `mail_notify.py`:
   - New `_fee_block(lang, fee) -> Tuple[List[str], List[str], str]` returning HTML blocks, plain-text lines and the SPAYD string ("" when no QR). Order: heading `mail_completion_fee_heading`; paragraph `mail_completion_fee_total` (total=fee["total"]); the calculation panel exactly as today (move lines 1690-1701 in). Then, with `ways = fee.get("ways") or []`: if empty, one paragraph `fee_no_rails`; else paragraph `mail_completion_fee_once`, then per way in list order:
     - iban: `_block_panel(fee_rail_iban text, rows)` with rows (`fee_payee`, payee) only when payee is not empty, (`fee_iban`, account), (`fee_amount_label`, `fee_amount` with amount=total), (`fee_vs_label`, fee["vs"]). When `way["spayd"]`: the anchor 5 `<tr>` with alt `fee_qr_alt`, and return that string as the third value. Text: the panel title, then `label: value` per row. No QR line in the text part.
     - revolut: `_block_button(link, label)` with label `fee_revolut_button` (amount = the `fee_amount` text). Text: `f"{label}: {link}"`.
     - cash: `_block_paragraph(f"{fee_rail_cash text}: {note}")` where note is `way["note"]` or the `fee_cash_default` text. Same line in the text part.
     Last, always: paragraph `mail_completion_fee_already`. `_block_paragraph`, `_block_panel` and `_button` already escape; pass raw strings and escape nothing twice.
   - `build_completion`: when `fee` is set use `mail_completion_subject_fee` (property, total), `mail_completion_preheader_fee`, `mail_completion_heading_fee`, `mail_completion_intro_fee` (property, dates); otherwise today's four keys, unchanged. Replace the body of `if fee:` with the `_fee_block` output (text lines after one `""`). Delete the `mail_completion_fee_ways` and `mail_completion_fee_vs` uses. When the SPAYD string is not empty, add `"qr_spayd": spayd` to the returned dict. Door code stays below the fee block. In the docstring and the "Slot 1" comment, change "buttonless" to "buttonless unless a fee has a Revolut way".
   - `build_door_code`: add `fee: Optional[Dict[str, Any]] = None` after `host`. When set, append the `_fee_block` blocks and text lines after the `first_use` lines and add `"qr_spayd"` to the returned dict the same way. Subject, title and preheader stay as today.
5. Wiring. The image and its attachment must never disagree, so the key comes from the built content only:
   - `claim.py`, right after anchor 3: `if content.get("qr_spayd"): payload[mail.QR_SPAYD_KEY] = content["qr_spayd"]`.
   - `door_codes._send_code_mail`: before `build_door_code`, set `fee = None`; `if claim["completion_notified_at"]:` then `from . import claim as claim_module` (inside the function: `claim` is the row here and the modules import each other) and `fee = claim_module._completion_fee(apartment, reservation)`. Use the claim row as already read at the top; do not re-read it. Pass `fee=fee`. After anchor 6 line 316 add the same `qr_spayd` line as above.
6. i18n, all six languages. Delete `mail_completion_fee_ways` and `mail_completion_fee_vs`. Add next to `mail_completion_subject` (English is fixed; write a natural native line for each other language, with the same placeholders, "Kč" in cs as its neighbours do):
   - `mail_completion_subject_fee`: "Everyone is registered for %(property)s. Stay fee to pay: %(total)s CZK"
   - `mail_completion_preheader_fee`: "Everyone on this stay is registered. How to pay the stay fee is inside."
   - `mail_completion_heading_fee`: "One thing left: the stay fee"
   - `mail_completion_intro_fee`: "Everyone for %(property)s is registered. Only the local stay fee below is left."
   - `mail_completion_fee_once`: "Choose one way to pay:"
   - `mail_completion_fee_already`: "Already paid? Then there is nothing more to do."
   Do not change any other key. No fee text may say "nothing else to do".
7. Tests.
   - `test_guest_mail.py`, anchor 10 only: give each `fee` dict a matching `"ways"` list; replace the asserts on "payment details are on your stay page", "Pay by:" and "Bank transfer: use variable symbol" with asserts on the new lines ("Variable symbol: 1234" for bank, the cash line for cash only, no "Variable symbol" without a bank way). Keep `"paid by" not in` and `"used" not in`.
   - New `test_completion_fee_mail_1077.py`. Builder tests call `mail_notify.build_completion` and `build_door_code` with a hand-made `fee`; flow tests reuse the fixtures of `test_claim_mail.py` and `test_door_code_handover.py` (read only their setup helpers). Cover:
     a. bank way with spayd: subject names the total; text has recipient, formatted account, amount and "Variable symbol"; HTML has `src="cid:stayfeeqr"`; content has `qr_spayd`; no "nothing else" in subject, text or HTML; text ends the fee block with the "Already paid?" line.
     b. bank way without spayd: bank rows shown, no `<img`, no `qr_spayd` key.
     c. no HTML of any case contains `src="http` or `src="data:`.
     d. `guest_pay_ways`: bank enabled without an account is absent; Revolut enabled without a link is absent; cash without a note gives `note == ""` and the mail shows the `fee_cash_default` text; default rail comes first; `qr_offered_for_reservation` is True with one SVK guest, False with only DEU guests and ignores archived guests.
     e. `ways == []`: the mail shows the total and the `fee_no_rails` text, no "Choose one way".
     f. a cash note `<b>x</b>` arrives escaped in the HTML.
     g. `_completion_fee` returns None with `config.STAY_FEE_GUEST_PAY` False and with `stay_fee_collect` 0; `build_completion(fee=None)` keeps subject `mail_completion_subject` and has no `qr_spayd`; `build_door_code()` without `fee` equals its output with `fee=None` and has no fee heading.
     h. all six languages, fee with all three ways: build both mails; no `%(` in subject, text or HTML; the six new keys differ from English in every other language.
     i. flow: after a full-group completion the outbox has exactly one `completion` row and its payload has `qr_spayd` (Czech guest); calling `maybe_notify_completion` again adds no row.
     j. flow: door-code mail with `completion_notified_at` set carries the fee heading and the "Already paid?" line; with it NULL (quiet completion) it carries neither and no `qr_spayd`; one `door_code` row either way; the stored row holds `mail.DOOR_CODE_MARKER`, never the PIN.
     k. English fee mail and door-code mail with the block: none of these exact phrases appears: "fee is paid", "was paid", "has been paid", "payment received", "settled". (The existing fee line "It is paid once, to your host." stays and is allowed.)
8. Report section "Copy for owner review": a table of the six new keys with the final text in all six languages (36 cells), plus the English plain-text part of one full fee mail (three ways) and one door-code mail with the block, built with invented data. This section does not count toward the 600-token report cap.

## 5. Do not touch

`reporting.py`, `deadlines.py`, anything filing; `routes/guest.py` and `_fee_pay_panel` (that is F2); templates, CSS, JS, migrations; `retention.py`; `mail.py`; any dependency; any i18n key not named in step 6. Never push to `main`.

## 6. Commands (each ends `2>&1 | tail -30`)

From `App/`, in this order:

1. `.venv/bin/python -m pytest tests/test_completion_fee_mail_1077.py tests/test_guest_mail.py tests/test_guest_languages.py -q --tb=short -x`
2. [test-map](../context/test-map.md) rows. Mail, SES: `tests/test_ses_mail.py tests/test_mail_*.py tests/test_*_mail.py tests/test_lifecycle_mail.py tests/test_notification_copy.py`. Door codes: `tests/test_door_code*.py --ignore=tests/test_door_code_window_browser.py`. Invoices, stay fee: `tests/test_invoice_*.py tests/test_stay_fee*.py`. Claim: `tests/test_claim_*.py`. Privacy: `tests/test_privacy_first.py`.

From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`. No browser test and no screenshot are needed because no page changes; say so in the report. `test_mail_golden.py` pins other mails and must pass unchanged; do not regenerate golden files.

## 7. Acceptance

- [ ] A fee mail states the fee in subject, heading and intro, shows total, calculation and every working way with full details, the QR for bookings with a Czech or Slovak guest only, and ends the block with the "Already paid?" line.
- [ ] A way that cannot work is never listed; with the flag or `stay_fee_collect` off both mails are unchanged.
- [ ] Door-code mail carries the block only when `completion_notified_at` is set; no PIN in the outbox; no new `mail.enqueue`, idempotency keys unchanged.
- [ ] QR is `cid:` only; no remote or `data:` image; no new outbound request.
- [ ] Six languages complete; `mail_completion_fee_ways` and `mail_completion_fee_vs` gone everywhere; no sentence states the fee as paid.
- [ ] The report has "Copy for owner review"; `git diff --stat origin/main` touches only section 3 files.

## 8. Stop and ask

Stop and write the report as `blocked` if: an anchor is missing; the work needs a template, CSS, migration, new dependency or a file outside section 3; a test fails twice on the same cause (attempt 3 of 3); you reach 25 tool calls or 60k tokens (finish the step, commit, report `Done: steps 1 to k. Left: steps k+1 to n.`). Never guess a production setting.

## 9. Report

`docs/tasks/1077-report.md`, 600 tokens at most apart from the copy section: files changed, each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps, then "Copy for owner review". In the PR body state: no new outbound request, the QR is an inline attachment, and the PR is held until the owner has read the copy. Set this brief `Status: review`, then open one PR. Do not merge it.

## Owner steps

1. Open the PR and read "Copy for owner review" in `docs/tasks/1077-report.md`. 2. Say "copy ok" or name the lines to change. 3. After the merge, deploy by hand. F2 (1078) follows; F3 and F4 are separate briefs.
