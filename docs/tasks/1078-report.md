# 1078 report: F3, update mail when the stay-fee total changes

Status: review. Branch `claude/1078-f3`. No template, CSS or JS change, so no browser test, screenshot or design-system line.

## Files changed

Section 3 files: `0041_claim_fee_mailed.sql`, `00012_claim_fee_mailed.sql`, `retention.py` (one comment), `RETENTION.md` (one row), `fee_update.py` (new), `claim.py` (the two edits of step 3), `mail.py` (two lines), `mail_notify.py` (`build_fee_update`), `scheduler.py` (import and tuple), `i18n.py`, `guest_uk_i18n.py`, `tests/test_fee_update_1078.py` (27 tests). Outside section 3: see Deviations 1 to 3.

## Commands (from `App/`)

1. `pytest tests/test_fee_update_1078.py tests/test_claim_mail.py tests/test_guest_mail.py tests/test_guest_languages.py -q --tb=short -x`: `178 passed, 1 warning in 5.26s`.
2. All section 6 rows in one run (mail, claim, privacy, database, scheduler, plus row 1), SQLite: `495 passed, 6 skipped, 5 warnings in 22.07s`. The 6 skips are the PostgreSQL-only tests.
3. The same PostgreSQL tests against a local PostgreSQL 16 (`UBYHOST_TEST_DATABASE_URL` set, disposable database): `tests/test_goose_migrations.py tests/test_pg_row_locks.py tests/test_migrations.py`: `13 passed, 10 skipped` (the 10 are `sqlite_only`). `tests/test_fee_update_1078.py tests/test_claim_mail.py` with the same variable: `76 passed`.
4. Repo root `python3 scripts/context_lint.py`: `context lint: OK` (warnings only, one names RETENTION.md as shared by open briefs 0347, 0350, 1078).

## Acceptance (section 7)

- [x] 0041 and goose twin 00012 add four nullable columns; retention line and RETENTION row exist; migration and privacy tests green.
- [x] A changed total yields exactly one `completion_update` after 10 quiet minutes; reruns, a second worker and a crash before the record add none; NULL baseline, fee None, revoked claim and gone reservation never mail.
- [x] Flag off: completion path and outbox identical to main. The `claim.py` diff is the two edits of step 3. `git diff --stat origin/main`: section 3 files plus the three test-demanded lines under Deviations.
- [x] No `qr_spayd`, added image, button, link or pay details in the update mail; six languages complete; no sentence states a fee as paid.
- [x] This report has "Copy for owner review" and "Follow-ups".

## Deviations

1. `App/app/host_i18n.py`: two lines, `notification.mail_kind.completion_update` in en ("stay fee change") and cs ("změna poplatku za pobyt"). `test_mail_failed_alert.py` demands a host-facing name for every outbox kind (section 6 allows the registry entry). This is host copy too: owner may reword.
2. `App/tests/test_claim_mail.py`: one entry `"completion_update"` in the pinned `mail.KINDS` set (same allowance). So step 6j is "pass with one registry line", not "unchanged".
3. `App/tests/test_migrations.py`: `test_python_runner_is_frozen` pins the highest SQLite migration; bumped 40 to 41. Not named in the brief; every SQLite migration has to move this pin.
4. Test h, images: the brief asks for no `<img` and no `src="http` in the HTML. The shared `_shell` that every guest mail uses puts the UbyHost logo there, and the brief also says to build like `build_completion`. The test asserts exactly one `<img` and one `src=` (the logo), no data image, no `<a href="http`.
5. Test h, "received": the shared guest footer says "You received this e-mail because ...". The paid/received/settled check covers subject and body above the footer.
6. Tests set the live total by patching `stay_fee.charge_for_reservation` (the real `_completion_fee` with its flag, collection and rails checks still runs) instead of inserting guest rows. Test i therefore compares the guest rows of a stay that has none; the whole `reservation` row is compared. `submit_state` is not a `reservation` column here, so there is no separate assertion on it.
7. The preheader reuses `mail_fee_update_heading` (no sixth key). Steps 2 to 6 are one commit. Anchors 4 and 9 sit one line lower than the brief says (499, 92).
8. Mail disabled: the pending columns are still written (the baseline is not), as step 2 orders the decision before the enqueue.

## Questions

1. Deviation 4: is the shell logo acceptable in this mail, as in all other guest mails?
2. When the total falls and the iban rail is on, the mail still shows the variable symbol line (see the "less" sample). Keep it, or show it only on the "more" mail?
3. The scheduler runs `drain` before `fee_updates` in a tick, so the mail leaves on the next tick (the brief expects this).

## Owner steps

1. Read "Copy for owner review"; say "copy ok" or name the lines.
2. After the merge, deploy by hand as usual; the migration runs with it.

## Copy for owner review

| Key | en | cs | de | es | fr | uk |
|---|---|---|---|---|---|---|
| `mail_fee_update_subject` | Stay fee for %(property)s changed: now %(total)s | Poplatek za pobyt v %(property)s se změnil: nově %(total)s | Ortstaxe für %(property)s geändert: jetzt %(total)s | La tasa de estancia de %(property)s ha cambiado: ahora %(total)s | La taxe de séjour pour %(property)s a changé : désormais %(total)s | Збір за проживання в %(property)s змінився: тепер %(total)s |
| `mail_fee_update_heading` | The stay fee changed | Poplatek za pobyt se změnil | Die Ortstaxe hat sich geändert | La tasa de estancia ha cambiado | La taxe de séjour a changé | Збір за проживання змінився |
| `mail_fee_update_body` | The stay fee for your group at %(property)s (%(dates)s) is now %(new)s. It was %(old)s. | Poplatek za pobyt vaší skupiny v %(property)s (%(dates)s) je nově %(new)s. Původně to bylo %(old)s. | Die Ortstaxe für Ihre Gruppe in %(property)s (%(dates)s) beträgt jetzt %(new)s. Zuvor waren es %(old)s. | La tasa de estancia de su grupo en %(property)s (%(dates)s) es ahora de %(new)s. Antes era de %(old)s. | La taxe de séjour de votre groupe pour %(property)s (%(dates)s) est désormais de %(new)s. Elle était de %(old)s. | Збір за проживання вашої групи в %(property)s (%(dates)s) тепер становить %(new)s. Раніше було %(old)s. |
| `mail_fee_update_more` | If you already sent the earlier amount, the remaining difference is %(diff)s. The payment details are in the earlier e-mail. | Pokud jste už poslali původní částku, zbývá doplatit rozdíl %(diff)s. Platební údaje najdete v předchozím e-mailu. | Falls Sie den früheren Betrag bereits überwiesen haben, bleibt eine Differenz von %(diff)s. Die Zahlungsdaten stehen in der früheren E-Mail. | Si ya envió el importe anterior, la diferencia pendiente es de %(diff)s. Los datos de pago están en el correo anterior. | Si vous avez déjà envoyé le montant précédent, la différence restante est de %(diff)s. Les informations de paiement figurent dans l'e-mail précédent. | Якщо ви вже надіслали попередню суму, залишається різниця %(diff)s. Платіжні дані є в попередньому листі. |
| `mail_fee_update_less` | If you already sent the earlier amount, ask your host about the difference. | Pokud jste už poslali původní částku, domluvte se na rozdílu s hostitelem. | Falls Sie den früheren Betrag bereits überwiesen haben, klären Sie die Differenz bitte mit Ihrem Gastgeber. | Si ya envió el importe anterior, consulte la diferencia con su anfitrión. | Si vous avez déjà envoyé le montant précédent, voyez la différence avec votre hôte. | Якщо ви вже надіслали попередню суму, з’ясуйте різницю з господарем. |

Amounts use the existing `fee_amount` key ("550 CZK"; "550 Kč" in Czech). The HTML part shows the heading above the body; the text part does not, as in the completion mail.

**English "more" mail** (400 to 550, iban rail on; example values):

```
Subject: Stay fee for Example flat changed: now 550 CZK

The stay fee for your group at Example flat (12–15 Nov 2026) is now 550 CZK. It was 400 CZK.
Bank transfer: use variable symbol 1234.

If you already sent the earlier amount, the remaining difference is 150 CZK. The payment details are in the earlier e-mail.

--
UbyHost is the guest-registration service your host uses.
You received this e-mail because your stay at Example flat is registered with this address.
Your host: Example Host s.r.o.
host@example.test · +420 111 222 333
Reply to this e-mail to reach your host.
```

**English "less" mail** (400 to 250, iban rail on):

```
Subject: Stay fee for Example flat changed: now 250 CZK

The stay fee for your group at Example flat (12–15 Nov 2026) is now 250 CZK. It was 400 CZK.
Bank transfer: use variable symbol 1234.

If you already sent the earlier amount, ask your host about the difference.

--
(same footer)
```

## Follow-ups

- A fee that falls to 0 (or that `_completion_fee` cannot compute) sends no mail; the baseline is kept.
- If the process dies between enqueue and record and the total changes again before the next sweep, the next mail's "was" is the amount before the lost record.
- No update mail after `date_to`.
- Also open: Q3 (F1 door-code mail can show a live total up to 10 minutes ahead of the last mailed one) and Q4 (F4 must record its baseline through `maybe_notify_completion` or `fee_update.record_baseline`).
