# 1077 report: F1, the completion mail is the bill

Status: review
Executor: Opus 5.5 | Branch: claude/1077-f1-f2 | Base: 14ba49ce

## Files changed

`App/app/stay_fee.py` (new `qr_offered_for_reservation`, `guest_pay_ways`), `App/app/claim.py` (`_completion_fee` uses the ways; QR key on the completion payload), `App/app/mail_notify.py` (new `_fee_block`; `build_completion` and `build_door_code` use it), `App/app/door_codes.py` (fee and QR key on the door-code mail once the completion mail has gone), `App/app/i18n.py`, `App/app/guest_uk_i18n.py` (six keys added, `mail_completion_fee_ways` and `mail_completion_fee_vs` removed, six languages), `App/tests/test_guest_mail.py` (anchor 10 tests only), `App/tests/test_completion_fee_mail_1077.py` (new), this report, brief set to `Status: review`.

No template, CSS, JS, migration, `retention.py`, `mail.py` or dependency change. No new `mail.enqueue`; idempotency keys and kinds unchanged. No browser test or screenshot: no page changed.

## Attempt 2 (review fixes)

- `door_codes._send_code_mail`: the fee read and the fee build sit in one try/except. On any error it logs and rebuilds the code mail with no fee, so the code mail is always queued. The fee also needs the group to be whole now (`reporting.reservation_progress`: `filled >= expected`), not only `completion_notified_at`.
- `stay_fee.guest_pay_ways`: a malformed `bank_account` (`ValueError` from `payments.normalise_account`) drops the bank way only. The other ways and the fee stay.
- New tests: a failing `_fee_block` still gives exactly one `door_code` row; a group that became partial gets no bill on a reissued code; a malformed account drops only the bank way; both no-fee mails are pinned by sha256 of subject, text and HTML, a hash I took from the base commit 14ba49ce's builders (identical before and after); a flag-off flow has the old subject and no `qr_spayd` in the outbox.
- Fixture note: the `fee_stay` flow fixture stubs `stay_fee.charge_for_reservation` (fixed 600 CZK) and `reporting.reservation_progress` (whole or partial group). The pay-way and QR logic run for real.
- Attempt 2 results: command 1 `140 passed`; mail `283 passed`; door codes `170 passed`; invoices and stay fee `994 passed, 2 skipped`; claim `106 passed`; privacy `5 passed`; lint OK. I left out `test_door_code_window_browser.py`: the glob names it explicitly, so `--ignore` has no effect, and webkit is not installed in this sandbox.

## Commands (last lines)

1. `pytest tests/test_completion_fee_mail_1077.py tests/test_guest_mail.py tests/test_guest_languages.py`: `135 passed in 2.18s`
2. Mail, SES row: `283 passed, 5 warnings in 6.15s` (includes `test_mail_golden.py`, unchanged)
3. Door codes row: `170 passed in 4.26s`. Note: `tests/test_door_code*.py` names `test_door_code_window_browser.py` explicitly, so `--ignore` has no effect; run as written it adds 6 webkit failures (webkit is not installed in this sandbox). I ran the glob with that file filtered out.
4. Invoices, stay fee row: `994 passed, 2 skipped` (the 2 skips need `UBYHOST_SHOTS_DIR`, screenshot-only tests, not in scope)
5. Claim row: `106 passed, 1 warning`
6. Privacy: `5 passed`
7. `python3 scripts/context_lint.py`: `context lint: OK` (existing WARN lines only)

## Section 7

- [x] Fee mail states the fee in subject, heading and intro; total, calculation, every working way with full details; QR only with a CZE or SVK guest; block ends with "Already paid?".
- [x] A way that cannot work is never listed; flag or `stay_fee_collect` off leaves both mails unchanged (test g).
- [x] Door-code mail carries the block only when `completion_notified_at` is set; no PIN in the outbox; no new `mail.enqueue`.
- [x] QR is `cid:` only; no new remote or `data:` image; no new outbound request.
- [x] Six languages complete; the two old keys gone everywhere; no sentence states the fee as paid.
- [x] "Copy for owner review" below; the diff touches only section 3 files plus the brief's status line.

## Deviations

- Test c: the mail shell already carries one remote image, the UbyHost logo (`mail_notify.LOGO_PATH`, `/static/ubyhost-logo.jpg`), in every mail. `src="http` therefore cannot be absent. The test strips that existing logo, then asserts no `src="http`, no `src="data:` and that the only other image is `cid:stayfeeqr`.
- Test j (NULL case): with a full group, `_send_code_mail` releases the completion mail first and the code rides in it, so no `door_code` row exists. The test models the quiet case as a partial group (expected 2, filled 1): one `door_code` row, no fee block, no `qr_spayd`, no completion row.
- Flow tests use `_stay` from `test_door_codes_safeguards.py` (the same fixture `test_door_code_handover.py` imports), and they monkeypatch `stay_fee.charge_for_reservation` to a fixed 600 CZK charge. `guest_pay_ways` and `qr_offered_for_reservation` run for real.
- Bank panel: the IBAN and VS rows use `_block_panel`'s existing monospace flag (`(label, value, True)`), as that function's docstring prescribes for copied values. Plain text adds one blank line between ways.
- `stay_fee.GUEST_RAIL_ORDER` is a copy of `routes/guest.RAIL_ORDER`, because a module must not import from routes.

## Questions

1. Is the shell's remote logo image acceptable under "no remote image" for these mails, or should a later brief make it `cid:`?
2. Brief section 6 door-code command: should it drop the explicit glob match on `test_door_code_window_browser.py`?

## Owner steps

1. Read "Copy for owner review" below. 2. Say "copy ok" or name the lines to change. 3. Before the deploy, confirm that production has sent at least one SESv2 Raw guest mail. Guest QR mails now take the raw path (inline attachment), and an IAM gap there would hold billed completion and door-code mails. 4. After the merge, deploy by hand.

## Copy for owner review

### The six new keys

| Key | en | cs | de | es | fr | uk |
|---|---|---|---|---|---|---|
| `mail_completion_subject_fee` | Everyone is registered for %(property)s. Stay fee to pay: %(total)s CZK | Všichni jsou zaregistrovaní pro %(property)s. Poplatek za pobyt k úhradě: %(total)s Kč | Alle sind für %(property)s registriert. Zu zahlende Aufenthaltsgebühr: %(total)s CZK | Todos están registrados para %(property)s. Tasa de estancia a pagar: %(total)s CZK | Tout le monde est enregistré pour %(property)s. Taxe de séjour à payer : %(total)s CZK | Усіх зареєстровано в %(property)s. Збір за проживання до сплати: %(total)s CZK |
| `mail_completion_preheader_fee` | Everyone on this stay is registered. How to pay the stay fee is inside. | Všichni na tomto pobytu jsou zaregistrovaní. Jak zaplatit poplatek za pobyt, najdete v tomto e-mailu. | Alle Gäste dieses Aufenthalts sind registriert. Wie Sie die Aufenthaltsgebühr zahlen, steht in dieser E-Mail. | Todos los huéspedes de esta estancia están registrados. En este correo verá cómo pagar la tasa de estancia. | Tous les voyageurs de ce séjour sont enregistrés. Vous trouverez dans cet e-mail comment payer la taxe de séjour. | Усіх гостей цього проживання зареєстровано. Як сплатити збір за проживання, дивіться в листі. |
| `mail_completion_heading_fee` | One thing left: the stay fee | Zbývá jediná věc: poplatek za pobyt | Nur noch eines: die Aufenthaltsgebühr | Solo queda una cosa: la tasa de estancia | Une dernière chose : la taxe de séjour | Залишилося одне: збір за проживання |
| `mail_completion_intro_fee` | Everyone for %(property)s is registered. Only the local stay fee below is left. | Všichni hosté pro %(property)s jsou zaregistrovaní. Zbývá jen místní poplatek za pobyt níže. | Alle Gäste für %(property)s sind registriert. Es fehlt nur noch die örtliche Aufenthaltsgebühr unten. | Todos los huéspedes de %(property)s están registrados. Solo queda la tasa local de estancia que figura abajo. | Tous les voyageurs pour %(property)s sont enregistrés. Il ne reste que la taxe de séjour locale ci-dessous. | Усіх гостей проживання в %(property)s зареєстровано. Залишився лише місцевий збір за проживання нижче. |
| `mail_completion_fee_once` | Choose one way to pay: | Vyberte si jeden způsob platby: | Wählen Sie eine Zahlungsart: | Elija una forma de pago: | Choisissez un moyen de paiement : | Оберіть один спосіб оплати: |
| `mail_completion_fee_already` | Already paid? Then there is nothing more to do. | Už máte zaplaceno? Pak už nemusíte nic dalšího dělat. | Schon bezahlt? Dann müssen Sie nichts weiter tun. | ¿Ya ha pagado? Entonces no tiene que hacer nada más. | Déjà payé ? Alors vous n'avez plus rien à faire. | Уже сплатили? Тоді більше нічого робити не потрібно. |

### English completion mail, three ways (invented data; plain-text part)

```
SUBJECT: Everyone is registered for Sample Flat. Stay fee to pay: 600 CZK
Everyone for Sample Flat is registered. Only the local stay fee below is left.

Guests registered: 2 of 2
Check-in: 5 Jan 2026, from 15:00
Check-out: 7 Jan 2026, by 10:00

Local stay fee
600 CZK to pay for your group. It is paid once, to your host.

How it is calculated
Guest 1: 2 nights × 150 CZK = 300 CZK
Guest 2: 2 nights × 150 CZK = 300 CZK

Choose one way to pay:

Bank transfer
Recipient: Example Host s.r.o.
Account (IBAN): CZ65 0800 0000 1920 0014 5399
Amount: 600 CZK
Variable symbol: 1234

Pay 600 CZK with Revolut: https://revolut.me/examplehost

Cash: Pay in cash when you arrive. Ask your host where and when.

Already paid? Then there is nothing more to do.

Your host takes care of the official registration with the authorities. This e-mail is your receipt, not an official confirmation.

--
UbyHost is the guest-registration service your host uses.
You received this e-mail because your stay at Sample Flat is registered with this address.
Your host: Example Host s.r.o.
host@example.test
Reply to this e-mail to reach your host.
```

The HTML part also shows the payment QR (inline `cid:` image) under the bank panel, and the Revolut way is a button.

### English door-code mail with the block (invented data; plain-text part)

```
SUBJECT: Your door code for Sample Flat
Your door code
{{door_code}}

The code is active from check-in at 5 Jan 2026, 15:00 until check-out by 7 Jan 2026, 10:00.
You must enter it on the lock for the first time within 24 hours of check-in, by 6 Jan 2026, 15:00, or it expires. Contact your host and they will issue a new code.

Local stay fee
600 CZK to pay for your group. It is paid once, to your host.

How it is calculated
Guest 1: 2 nights × 150 CZK = 300 CZK
Guest 2: 2 nights × 150 CZK = 300 CZK

Choose one way to pay:

Bank transfer
Recipient: Example Host s.r.o.
Account (IBAN): CZ65 0800 0000 1920 0014 5399
Amount: 600 CZK
Variable symbol: 1234

Pay 600 CZK with Revolut: https://revolut.me/examplehost

Cash: Pay in cash when you arrive. Ask your host where and when.

Already paid? Then there is nothing more to do.

--
UbyHost is the guest-registration service your host uses.
You received this e-mail because your stay at Sample Flat is registered with this address.
Your host: Example Host s.r.o.
host@example.test
Reply to this e-mail to reach your host.
```

`{{door_code}}` is the outbox marker; the PIN is filled in only at send time.

PR body must state: no new outbound request; the QR is an inline attachment; the PR is held until the owner has read this copy.
