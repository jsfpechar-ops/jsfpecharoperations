# 0013: Door code on the guest page and by mail

Status: done
Depends on: 0012 | Base commit: after 0012 merges | Branch: task/0013-door-code-delivery
Executor: Cursor local agent (composer, Kimi or GLM) | Fits one session

## 1. Objective

Once a stay's code is issued, the guest sees it on their stay page and gets it by e-mail, with the host in copy. The host sees the code's state on the stay page. The PIN is never stored in plain text in the outbox or the console mail log.

## 2. Context

- Plan: `docs/plans/ttlock-door-codes.md` §8.3 (controls) and §10 (guest block, mails, host line). Rule 7: guest-page and CSS changes need browser and geometry tests with 0 skipped, and screenshots.
- `door_code` row (tasks 0008 and 0012): `state` (`pending`, `issuing`, `retrying`, `issued`, `failed`, `expired`), `pin_enc`, `valid_from`, `valid_to` (UTC ISO, margin included), `notified_at`. `door_codes.issue` succeeds in one `with db.cursor()` block and then resolves the alert and writes the audit row.
- Guest stay page: `stay_overview` in `App/app/routes/guest.py` (near line 1090) builds the context with `context = _shared(request, token, lang, apartment)` then `context.update({...})` and renders `guest/stay.html` (near line 1176). All guards (claim, device, PIN) run before. Responses already carry `Cache-Control: no-store, private` (`App/app/main.py` middleware).
- `guest/stay.html` lines 36 to 54, the "all done" card:
  ```
  {% elif remaining is not none and remaining <= 0 %}
    <div class="g-card">
      <div class="g-big-ok"> ... <h2>{{ t('all_done_title') }}</h2> ... </div>
      {% if can_raise_party %} <form ...> ... </form> {% endif %}
    </div>
  {% else %}
  ```
- Guest strings: `App/app/i18n.py`, `STRINGS` for `en`, `cs`, `de`, `es`, `fr`, placeholders `%(name)s` (for example `"all_done_receipt": "We have sent a confirmation to %(email)s."`). Guest CSS: `App/app/static/guest.css` (`.g-card`, `.g-intro`, `.g-big-ok`); the stylesheet link in `App/app/templates/guest/base.html` is `/static/guest.css?v=20261004z`, and rule "Guest pages" says to bump `?v=` when the CSS changes.
- Mail (`App/app/mail.py`): `KINDS`, `GUEST_KINDS`, `HOST_KINDS` (a kind must be in exactly one of the last two), `CLAIM_SECRET_MARKER = "{{claim_secret}}"`, `CLAIM_SECRET_KEY = "claim_secret_enc"`, `_with_secret(value, payload)`, `delivery_body`, `delivery_html`, `_reveal_claim_secret` (the console log path). `enqueue(kind=, idempotency_key=, to_email=, subject=, payload=, reservation_id=, apartment_id=, owner_user_id=, cc_email=)`.
- The model to copy is `claim.maybe_notify_completion` (`App/app/claim.py` near line 645): `lang = claim["lang"] or "en"`, `payload = mail_notify.guest_payload(apartment, content, lang)`, `mail.enqueue(..., to_email=claim["email"], cc_email=payload.get("reply_to", ""), ...)`, then `mail.drain(limit=4)`. Its builder `mail_notify.build_completion` (near line 1245) uses `_guest_text`, `_block_heading`, `_block_paragraph`, `_guest_footer_lines`.
- Tests that pin mail kinds: `tests/test_claim_mail.py` (the exact `KINDS` set near line 1785, and the GUEST/HOST split near line 1781) and the local tuples at the top of `tests/test_guest_mail.py`.
- Host stay page: `App/app/templates/reservation_detail.html`, `<section class="panel stay-command-panel" id="now">`, with `<p class="stay-command-note">…</p>` inside `stay-command-main`. Route `reservation_detail` in `App/app/routes/admin.py` (near line 1609).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/door_codes.py` | edit | Steps 1 and 4 |
| `App/app/mail.py` | edit | Step 3 |
| `App/app/mail_notify.py` | edit | Step 4, one builder |
| `App/app/routes/guest.py` | edit | Step 2 |
| `App/app/templates/guest/stay.html` | edit | Step 2 |
| `App/app/templates/guest/base.html` | edit | Bump `guest.css?v=` only |
| `App/app/static/guest.css` | edit | Step 2, one class |
| `App/app/i18n.py` | edit | Step 5 |
| `App/app/routes/admin.py` | edit | Step 6 |
| `App/app/templates/reservation_detail.html` | edit | Step 6 |
| `App/app/host_i18n.py` | edit | Step 6 |
| `App/tests/test_door_code_delivery.py` | create | Step 7 |
| `App/tests/test_claim_mail.py` | edit | Add `"door_code"` to the pinned kinds set only |
| `App/tests/test_guest_mail.py` | edit | Add `"door_code"` to the local GUEST tuple only |
| `App/tests/test_wp28_geometry.py` | edit | Step 8, one test |

No other file may change.

## 4. Steps

1. **View helper** in `door_codes.py`:
   ```python
   def view(reservation, apartment) -> Optional[dict]:
       """What the guest and host pages show. None when the property has no door codes."""
   ```
   - `None` if `apartment["lock_provider"] != "ttlock"`.
   - `None` if `not config.DOOR_CODES_LIVE and reservation["source"] != "manual"` (test mode: calendar stays get no code, so they show nothing).
   - Read the `door_code` row. No row, or state `pending`/`issuing`/`retrying`: `{"state": "preparing"}` if `reservation["registration_completed_at"]` is set, else `{"state": "waiting"}`.
   - `failed`: `{"state": "failed"}`. `expired`: `None`.
   - `issued`: `{"state": "issued", "pin": db.decrypt_field(row["pin_enc"]), "works_from": f(valid_from), "works_until": f(valid_to), "first_use_by": f(valid_from + 24 h), "checkin": f(date_from at checkin_hour), "checkout": f(date_to at checkout_hour)}`, where `f` formats a time as `%d.%m.%Y %H:%M` in `config.TIMEZONE`.
2. **Guest block.**
   - In `stay_overview`, add `"door_code": door_codes.view(reservation, apartment)` to the `context.update({...})` that renders `stay.html`.
   - In `stay.html`, right after the closing `</div>` of the "all done" `g-card` and before `{% else %}`:
     ```
     {% if door_code %}
       <div class="g-card" id="door-code">
         <h2>{{ t('door_code_title') }}</h2>
         {% if door_code.state == 'issued' %}
           <p class="g-door-code" aria-label="{{ t('door_code_title') }}">{{ door_code.pin }}</p>
           <p class="g-intro">{{ t('door_code_times', checkin=door_code.checkin, checkout=door_code.checkout) }}</p>
           <p class="g-intro"><strong>{{ t('door_code_first_use', deadline=door_code.first_use_by) }}</strong></p>
           {% if claim_email_masked %}<p class="g-intro">{{ t('door_code_sent', email=claim_email_masked) }}</p>{% endif %}
         {% elif door_code.state == 'failed' %}
           <p class="g-intro">{{ t('door_code_failed') }}</p>
         {% else %}
           <p class="g-intro">{{ t('door_code_preparing') }}</p>
         {% endif %}
       </div>
     {% endif %}
     ```
   - In `guest.css`, add after `.g-big-ok` rules:
     ```css
     .g-door-code { font: 700 34px/1.2 ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace; letter-spacing: .14em; font-variant-numeric: tabular-nums; margin: 4px 0 14px; overflow-wrap: anywhere; }
     ```
     Then bump `?v=` on the `guest.css` link in `guest/base.html` to `20261008a`.
3. **Mail kind and marker** in `mail.py`:
   - Add `"door_code"` to `KINDS` and to `GUEST_KINDS`.
   - Add `DOOR_CODE_MARKER = "{{door_code}}"` and `DOOR_CODE_KEY = "door_code_enc"`, and `_with_door_code(value, payload)` written exactly like `_with_secret` but for these two names.
   - In `delivery_body` and `delivery_html`, apply `_with_door_code` to the result of `_with_secret`.
   - Do **not** change `_reveal_claim_secret`: the console log keeps `{{door_code}}` as is, so the PIN never reaches it.
4. **Send it.**
   - In `mail_notify.py` add `build_door_code(*, lang, property_name, checkin, checkout, first_use_by, host=None) -> Dict[str, str]`, modelled on `build_completion`: subject `mail_door_code_subject`; a heading `door_code_title`; a paragraph with `mail.DOOR_CODE_MARKER` as the code (a heading block or a bold paragraph, whichever `build_completion`'s helpers support); paragraphs `door_code_times` and `door_code_first_use`; the usual `_guest_footer_lines`. The text part holds the same lines in the same order. The marker is the only way the code appears.
   - In `door_codes.py` add `send_code_mail(door_code_id) -> None`, wrapped in `try/except Exception: log.exception(...)` so it never raises. Read the row (must be `issued` and `notified_at` NULL), the reservation, the apartment and the claim row (`SELECT * FROM reservation_claim WHERE reservation_id = ?`). Skip if the claim has no e-mail. Then, like `maybe_notify_completion`: `lang = claim["lang"] or "en"`, build the content with `view()` values, `payload = mail_notify.guest_payload(apartment, content, lang)`, `payload[mail.DOOR_CODE_KEY] = row["pin_enc"]` (already encrypted, do not decrypt), and `mail.enqueue(kind="door_code", idempotency_key=f"door_code:{reservation_id}:{row['valid_from']}", to_email=claim["email"], cc_email=payload.get("reply_to", ""), subject=..., payload=payload, reservation_id=..., apartment_id=..., owner_user_id=...)`. Then set `notified_at = db.utcnow()` and call `mail.drain(limit=4)`.
   - In `issue`, right after the success audit line, call `send_code_mail(door_code_id)`.
5. **Guest strings** in `i18n.py`, all five languages:

   | Key | en | cs | de | es | fr |
   |---|---|---|---|---|---|
   | `door_code_title` | Your door code | Váš kód ke dveřím | Ihr Türcode | Su código de la puerta | Votre code de porte |
   | `door_code_times` | Check-in from %(checkin)s. Check-out by %(checkout)s. | Příjezd od %(checkin)s. Odjezd do %(checkout)s. | Check-in ab %(checkin)s. Check-out bis %(checkout)s. | Entrada desde %(checkin)s. Salida hasta %(checkout)s. | Arrivée à partir de %(checkin)s. Départ avant %(checkout)s. |
   | `door_code_first_use` | Use the code for the first time before %(deadline)s, or it stops working. | Kód poprvé použijte před %(deadline)s, jinak přestane fungovat. | Verwenden Sie den Code zum ersten Mal vor %(deadline)s, sonst funktioniert er nicht mehr. | Use el código por primera vez antes del %(deadline)s; si no, dejará de funcionar. | Utilisez le code pour la première fois avant le %(deadline)s, sinon il ne fonctionnera plus. |
   | `door_code_sent` | We have also sent it to %(email)s. | Poslali jsme ho také na %(email)s. | Wir haben ihn auch an %(email)s gesendet. | También lo hemos enviado a %(email)s. | Nous l'avons aussi envoyé à %(email)s. |
   | `door_code_preparing` | Your door code is being prepared. Reload this page in a minute. | Váš kód ke dveřím se připravuje. Za minutu tuto stránku obnovte. | Ihr Türcode wird vorbereitet. Laden Sie diese Seite in einer Minute neu. | Estamos preparando su código de la puerta. Vuelva a cargar esta página en un minuto. | Votre code de porte est en préparation. Rechargez cette page dans une minute. |
   | `door_code_failed` | Your host will send you the door code. | Kód ke dveřím vám pošle hostitel. | Ihr Gastgeber schickt Ihnen den Türcode. | Su anfitrión le enviará el código de la puerta. | Votre hôte vous enverra le code de porte. |
   | `mail_door_code_subject` | Your door code for %(property)s | Váš kód ke dveřím pro %(property)s | Ihr Türcode für %(property)s | Su código de la puerta para %(property)s | Votre code de porte pour %(property)s |
6. **Host line.**
   - In `reservation_detail`, add `"door_code": door_codes.view(reservation, apartment)` to the render context (use the apartment row the route already loads; if it has none, `db.query_one` it).
   - In `reservation_detail.html`, right after the `</p>` that closes `stay-command-note`:
     ```
     {% if door_code %}<p class="small" id="door-code-line">
       {% if door_code.state == 'issued' %}{{ t('stay.detail.door_code.issued', pin=door_code.pin, start=door_code.works_from, end=door_code.works_until) }}
       {% elif door_code.state == 'failed' %}{{ t('stay.detail.door_code.failed') }}
       {% elif door_code.state == 'preparing' %}{{ t('stay.detail.door_code.preparing') }}
       {% else %}{{ t('stay.detail.door_code.waiting') }}{% endif %}
     </p>{% endif %}
     ```
   - Host strings (EN, CS): `stay.detail.door_code.issued` "Door code %(pin)s · works %(start)s to %(end)s" / "Kód ke dveřím %(pin)s · platí %(start)s až %(end)s"; `stay.detail.door_code.preparing` "Door code is being created." / "Kód ke dveřím se vytváří."; `stay.detail.door_code.waiting` "Door code waits for registration." / "Kód ke dveřím čeká na registraci."; `stay.detail.door_code.failed` "Door code could not be created. Create one in the TTLock app." / "Kód ke dveřím se nepodařilo vytvořit. Vytvořte ho v aplikaci TTLock."
7. **Tests** (`App/tests/test_door_code_delivery.py`). Seed an issued row directly (`pin_enc = db.encrypt_field("0563456")`). Use `complete_guest_claim` from `tests/conftest.py` for the claimed device, as other guest tests do. Tests:
   - `test_stay_page_shows_the_code_when_issued` (PIN, both times, the first-use deadline as `13.10.2026 14:00` for a stay from 12 Oct with check-in 15 and margin 1).
   - `test_stay_page_says_preparing_or_failed` (parametrized over `pending` and `failed`).
   - `test_no_block_without_door_codes` (`lock_provider` NULL).
   - `test_no_block_for_calendar_stays_in_test_mode` (`source='ical'`, live off).
   - `test_another_device_does_not_see_the_code` (an unclaimed client gets the claim page, and the PIN is not in it).
   - `test_mail_is_queued_with_marker_and_host_cc`: one `email_outbox` row of kind `door_code`, `cc_email` is the entity contact address, `"0563456"` not in the row's `payload` or `subject`, `{{door_code}}` in the payload text.
   - `test_delivery_puts_the_code_in` (`mail.delivery_body(payload)` and `delivery_html` contain `0563456` and no marker).
   - `test_console_log_never_shows_the_code` (with the console backend, drain, then `"0563456"` is not in `console_mail_log`).
   - `test_mail_is_sent_once` (calling `send_code_mail` twice queues one row).
   - `test_host_stay_page_shows_the_state` (issued line with the PIN; failed line).
   - `test_issue_sends_the_mail` (with `ttlock.create_period_code` faked, `door_codes.issue` leads to one outbox row).
8. **Geometry.** In `App/tests/test_wp28_geometry.py` add `test_door_code_card_fits_a_phone(base, world, browser, width)` for 360, 390 and 1280 in the style of `test_stay_page_cards_hold_their_buttons`: seed an issued code for a completed stay, open the stay page, assert no horizontal overflow and that `#door-code` lies inside the viewport width. Save screenshots of the stay page at each width to `docs/tasks/0013-shots/`, plus one of the host stay page at 1280.

## 5. Do not touch

Everything outside §3. `_reveal_claim_secret`, the claim mail kinds, `App/app/reporting.py`, every UbyPort module. No cancellation or date-move handling (task 0014).

## 6. Commands

From `App/`: `.venv/bin/python -m pytest tests -q` (all pass), then `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_guest_browser_e2e.py tests/test_wp28_geometry.py tests/test_host_geometry.py -q -rs` (0 skipped). From the repo root: `python3 scripts/context_lint.py` (last line `context lint: OK`).

## 7. Acceptance

- [ ] The 11 tests in step 7 and the geometry test pass. The full suite passes. Browser and geometry: 0 skipped.
- [ ] Screenshots at 360, 390 and 1280 px in `docs/tasks/0013-shots/`.
- [ ] `grep -n "door_code" App/app/mail.py` shows the kind in `KINDS` and `GUEST_KINDS` and the marker, and `_reveal_claim_secret` is unchanged (`git diff` of that function is empty).
- [ ] `git diff --stat` shows only the files in §3 plus the screenshots.

## 8. Stop and ask

Stop, and write the report, if:

- a name or excerpt in §2 is not found;
- `build_completion`'s helpers cannot show the marker on its own line;
- a mail test outside the two files in §3 fails because of the new kind;
- a test fails twice;
- a new dependency seems needed;
- a file outside §3 needs a change;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/0013-report.md` (1,500 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `App/app/mail.py` (marker substitution)
- `App/app/door_codes.py` (`view`, `send_code_mail`)
- `App/app/templates/guest/stay.html` (the block sits inside the all-done branch only)

## Owner steps

None. Test mode stays on (`UBYHOST_DOOR_CODES_LIVE` unset).
