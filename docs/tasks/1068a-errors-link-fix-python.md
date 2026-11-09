# 1068a: Errors that link to the fix, and no Bank QR without a bank account (Python)

Status: blocked at step 12, continued in 1068a-cont-1
Depends on: none (1066 and 1067 go first, see §2) | Base commit: origin/main at brief time | Branch: `claude/1068-errors-link-fix` (same branch as 1068b; 1068a goes first)
Executor: Opus (owner override) | Fits one session: 12 steps. Queue item 1.4, Tier B. Plan: docs/plans/speed-and-ease.md section 4.5 and Q8, Q9.

## 1. Objective

Every error named below says in one line what is wrong and carries a link to the page that fixes it. A Bank QR request cannot be created without a bank account: the form shows "Add bank account (1 min)" in place, and the bare QR 404 becomes a plain message. This brief is the Python half. 1068b makes the Go service (live for `/payments/requests/new` and both QR PNG routes) behave the same. The change is too big for one session, so it is split: 1068a (Python) then 1068b (Go), same branch.

## 2. Context

Rules: AGENTS.md 7 (browser tests 0 skipped, 390 px screenshot), 9 (one explanation in one place, no sentence the button already says), 10 (UX gate, design-system checklist). No new dependency, no new outbound request, no schema change, no new personal-data field. The app never shows or records a guest stay-fee payment as "paid"; this brief adds no paid state and no write to `payment_request.status`.

Flashes are plain text carried in `?msg=` / `?err=`; they have no link. Fix: a short allowlisted code `?fix=<code>` that `base.html` turns into one link in the toast. Never put a URL or label in the query string.

Errors found (all by grep) and their fix target:

| # | Error (key) | Where raised | Fix target (code) |
|---|---|---|---|
| 1 | No bank account, invoice (`invoice.warn_no_iban`) | `App/app/templates/invoice_form.html:288-290` | `/entities` (`bank`) |
| 2 | No bank account, Bank QR create (`payments.err.no_iban`, new check) | `App/app/routes/payments.py` `payment_request_new` (~line 172-212); form `App/app/templates/payments_new.html:37-41`; Go twin `go/internal/payments/requests.go` `RequestNewHandler` (1068b) | `/entities` (`bank`) |
| 3 | No bank account, QR preview (`payments.err.no_iban`) | `App/app/routes/payments.py:387` | `/entities` (`bank`) |
| 4 | Bare QR 404 (host PNG, guest PNG, guest page) | `App/app/routes/payments.py:366,370,762,766,775,779`; Go twins `go/internal/payments/qrpng.go:273-276`, `go/internal/payments/paylink_routes.go` (1068b) | plain message, steps 5 and 7 |
| 5 | Stripe not ready (`payments.err.not_ready`) | `App/app/routes/payments.py:261,283,331`; Go twin `requests.go:253` (1068b) | `/payments#stripe-setup` (`stripe`) |
| 6 | Lock offline (`health.door.offline` note) | `App/app/templates/_property_editor.html:443` | `/guide#door-codes` (`lock_guide`) |
| 7 | TTLock shared lock not found (`flash.ok.smart_locks_none_yet`, `flash.error.smart_locks_plain_key`) | `App/app/routes/admin.py:803-805` | `/guide#door-codes` (`lock_guide`) |

Not changed on purpose: `payments.err.stripe_off` (server switch, the host cannot fix it), `smart_locks.reauth` (the Remove button is beside it), `apartment.form.door_code.no_locks` (no template or route uses it; only the catalog has it). `property_health.py:114` already links the offline lock row (`health.door.fix`).

Copy (EN / CS, added together; no em dash; the link label is the only place that says the action):

| Key (file) | EN | CS |
|---|---|---|
| `payments.fix.bank` (new, host_i18n) | Add bank account (1 min) | Přidat bankovní účet (1 min) |
| `payments.fix.stripe` (new, host_i18n) | Open Stripe setup | Otevřít nastavení Stripe |
| `payments.err.no_iban` (replace, host_i18n) | Bank QR needs a bank account. | Bankovní QR potřebuje bankovní účet. |
| `payments.err.not_ready` (replace, host_i18n) | Stripe is not ready yet. | Stripe ještě není připraven. |
| `invoice.warn_no_iban` (replace, host_i18n and host_vi_i18n) | This invoice will have no payment QR code. | Na této faktuře nebude platební QR kód. (VI: Hóa đơn này sẽ không có mã QR thanh toán.) |
| `smart_locks.offline_fix` (new, host_i18n) | Check that the TTLock gateway has power and Wi-Fi. | Zkontrolujte, že brána TTLock má proud a Wi-Fi. |
| `pay_no_account` (new, i18n.py, six guest languages) | step 4 | step 4 |

`host_vi_i18n.py` carries no `payments.*` keys; a missing key falls back to English through `host_i18n.lookup`. Add VI only to `invoice.warn_no_iban` (already there). The label `smart_locks.guide_link` already exists in all host languages and is reused for the lock links.

The QR PNG routes are images, so a person never reads their body. On a refusal because the owner has no bank account they answer `404`, `text/plain; charset=utf-8`, body exactly `No bank account is set up for this payment request.` plus a newline, identical in Python and Go. Every other refusal (wrong rail, wrong owner, missing row, bad token, cancelled) stays an empty 404. The human text lives on the pages: the host sees the toast and the form block; the guest sees `pay_no_account` on `/pay/{id}/{token}` (Python only; `/pay/*/*.png` is the only guest path routed to Go).

**Which goes first:** 1066 (guest form, entity fields, `base.html`, `app2.css`, `static_versions.json`) and 1067 (`base.html` line 10, `static_versions.json`) merge before 1068a. This brief edits `base.html` only in the two toast blocks (about lines 100-110) and does not touch `app2.css` or `static_versions.json`. If an anchor below is missing because 1066 or 1067 moved it, STOP (§8). If the toast link needs CSS to be readable, STOP and report; do not edit `app2.css`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templating.py` | edit | `FIX_TARGETS`, `flash_fix` in both render paths |
| `App/app/routes/admin_helpers.py` | edit | `back(..., fix="")` |
| `App/app/templates/base.html` | edit | one link in each toast |
| `App/app/payment_request.py` | edit | `has_bank_account`, `NO_ACCOUNT_BODY` |
| `App/app/routes/payments.py` | edit | block create, PNG bodies, fix codes, guest page |
| `App/app/templates/payments_new.html` | edit | disabled Bank QR chip plus in-place block |
| `App/app/templates/payments_qr.html` | edit | guest message instead of image |
| `App/app/templates/payments.html` | edit | `id="stripe-setup"` |
| `App/app/templates/invoice_form.html` | edit | link under the warning |
| `App/app/templates/_property_editor.html` | edit | lock offline note gets fix text and link |
| `App/app/routes/admin.py` | edit | `fix="lock_guide"` on two flashes |
| `App/app/host_i18n.py`, `App/app/host_vi_i18n.py`, `App/app/i18n.py`, `App/app/guest_uk_i18n.py` | edit | keys from §2 |
| `App/tests/test_payment_rails.py` | edit | new tests |
| the test that asserts `warn_no_iban` text, if grep finds one | edit | new text |

No other file may change. Never edit `go/`.

## 4. Steps

Work from `App/`. Each step: edit, run the command, check the result.

1. **Helper and constant.** In `App/app/payment_request.py`, directly above `def qr_payload(request: Dict[str, Any]) -> tuple:` add:
```python
NO_ACCOUNT_BODY = "No bank account is set up for this payment request.\n"


def has_bank_account(owner_user_id: int) -> bool:
    """True when the owner's legal entity carries an IBAN or a Czech account."""
    entity = db.query_one(
        "SELECT iban, bank_account FROM legal_entity WHERE owner_user_id = ?",
        (owner_user_id,),
    )
    return bool(entity and (entity["iban"] or entity["bank_account"]))
```
Command: `.venv/bin/python -c "from app import payment_request as p; print(p.NO_ACCOUNT_BODY.strip())" 2>&1 | tail -3`. Expect the sentence.

2. **Fix registry.** In `App/app/templating.py` add at module level after the imports:
```python
# 1068: ?fix=<code> on a flash redirect shows one link to the page that fixes the error.
FIX_TARGETS = {
    "bank": ("/entities", "payments.fix.bank"),
    "stripe": ("/payments#stripe-setup", "payments.fix.stripe"),
    "lock_guide": ("/guide#door-codes", "smart_locks.guide_link"),
}


def _flash_fix(request):
    return FIX_TARGETS.get(request.query_params.get("fix", ""))
```
After BOTH occurrences of `    data.setdefault("flash_error", request.query_params.get("err"))` (lines ~709 and ~766) add `    data.setdefault("flash_fix", _flash_fix(request))`. In `App/app/routes/admin_helpers.py` change `def back(path: str, msg: str = "", err: str = "") -> RedirectResponse:` to `def back(path: str, msg: str = "", err: str = "", fix: str = "") -> RedirectResponse:` and directly after
```python
    if err:
        query.append(f"err={quote(err)}")
```
add
```python
    if fix:
        from ..templating import FIX_TARGETS

        if fix in FIX_TARGETS:
            query.append(f"fix={quote(fix)}")
```
Command: `.venv/bin/python -c "import app.main" 2>&1 | tail -5`. Expect no output (an import cycle means STOP).

3. **Toast link.** In `App/app/templates/base.html`, in the block `{% if flash and not inline_flash_section and not editor_saved %}` replace `<span class="grow">{{ flash }}</span>` with `<span class="grow">{{ flash }}{% if flash_fix %} <a href="{{ flash_fix[0] }}">{{ t(flash_fix[1]) }}</a>{% endif %}</span>`; in the block `{% if flash_error and not inline_flash_section %}` replace `<span class="grow">{{ flash_error }}</span>` with `<span class="grow">{{ flash_error }}{% if flash_fix %} <a href="{{ flash_fix[0] }}">{{ t(flash_fix[1]) }}</a>{% endif %}</span>`. Command: `grep -c "flash_fix" app/templates/base.html`. Expect `2` lines containing it (each line holds one use; the count of lines is 2).

4. **Copy.** Add the keys from §2 to `host_i18n.py` (en block and cs block). Replace the en and cs lines of `payments.err.no_iban` (~1551, ~3687), `payments.err.not_ready` (~1550, ~3686) and `invoice.warn_no_iban` (~1895, ~4031); add `payments.fix.bank` and `payments.fix.stripe` beside `payments.err.no_iban`; add `smart_locks.offline_fix` beside `smart_locks.offline` (~4860, ~5703). Replace the `host_vi_i18n.py` line `"invoice.warn_no_iban"` (~1521). Add `pay_no_account` beside `guide_not_ready_help` in each guest catalog (`i18n.py` en, cs, de, es, fr; `guest_uk_i18n.py` uk):
- en: `The host has not set up bank payment yet. Please ask the host for another way to pay.`
- cs: `Hostitel zatím nemá nastavenou platbu převodem. Zeptejte se ho na jiný způsob platby.`
- de: `Der Gastgeber hat die Banküberweisung noch nicht eingerichtet. Bitte fragen Sie ihn nach einer anderen Zahlungsweise.`
- es: `El anfitrión aún no ha configurado el pago por transferencia. Pídale otra forma de pago.`
- fr: `L'hôte n'a pas encore configuré le paiement par virement. Demandez-lui un autre moyen de paiement.`
- uk: `Господар ще не налаштував оплату переказом. Запитайте в нього інший спосіб оплати.`
Command: `.venv/bin/python -m pytest tests/test_*_i18n.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py tests/test_flash_literals.py tests/test_guest_languages.py -q --tb=short -x 2>&1 | tail -30`. Expect green except `test_go_host_i18n.py` (it is in the glob): the changed `payments.err.not_ready` makes `go/internal/payments/i18n.json` stale; 1068b regenerates it. If only that test fails, continue; do not edit `go/`.

5. **Routes.** In `App/app/routes/payments.py`:
 a. In `payment_request_new`, directly after
```python
    if rail not in payment_request.RAILS:
        return back
```
add
```python
    if rail == "qr" and not payment_request.has_bank_account(owner_id):
        return _back("/payments/new", err=_flash(request, "payments.err.no_iban"), fix="bank")
```
 b. The three `return _back("/payments", err=_flash(request, "payments.err.not_ready"))` (~261, ~283, ~331) become `... "payments.err.not_ready"), fix="stripe")`.
 c. Line ~387 `return _back("/payments", err=_flash(request, "payments.err.no_iban"))` becomes `..., fix="bank")`.
 d. In `payment_request_qr_png` replace
```python
    except ValueError:
        return Response(status_code=404)
    return Response(content=png, media_type="image/png")
```
with
```python
    except ValueError:
        return Response(payment_request.NO_ACCOUNT_BODY, status_code=404, media_type="text/plain; charset=utf-8")
    return Response(content=png, media_type="image/png")
```
 e. In `guest_qr_png` replace the `except ValueError:\n        raise HTTPException(status_code=404)` after `_, png = payment_request.qr_payload(row)` with `except ValueError:\n        return Response(payment_request.NO_ACCOUNT_BODY, status_code=404, media_type="text/plain; charset=utf-8")`.
 f. In `guest_qr_page` replace the `try: payload, _ = payment_request.qr_payload(row) ... except ValueError: raise HTTPException(status_code=404)` block and the `render(` call with:
```python
    no_account_text = ""
    payload = ""
    try:
        payload, _ = payment_request.qr_payload(row)
    except ValueError:
        from .guest import _language

        no_account_text = i18n.translator(_language(request))("pay_no_account")
    response = render(
        request,
        "payments_qr.html",
        {
            "pay_request": row,
            "qr_payload": payload,
            "show_nav": False,
            "png_url": f"/pay/{request_id}/{token}.png",
            "no_account_text": no_account_text,
        },
    )
```
 g. In `payments_new_page` add `"no_bank": not payment_request.has_bank_account(owner_id),` after `"prefill": prefill,`.
Command: `.venv/bin/python -c "import app.main" 2>&1 | tail -5`. Expect no output.

6. **Form, in place.** In `App/app/templates/payments_new.html` replace
`<label class="ui-chip"><input type="radio" name="rail" value="qr"> {{ t('payments.new.rail_qr') }}</label>`
with
`<label class="ui-chip"><input type="radio" name="rail" value="qr"{% if no_bank %} disabled{% endif %}> {{ t('payments.new.rail_qr') }}</label>`
and directly after the closing `</div>` of `<div class="ui-chips payments-seg">` (inside the fieldset) add
```
      {% if no_bank %}<p class="ui-sub">{{ t('payments.err.no_iban') }}</p>{{ ui_button(t('payments.fix.bank'), 'secondary', href='/entities', size='compact') }}{% endif %}
```
`ui_button` is already imported there; `size='compact'` is used the same way at `payments.html:77`. No new CSS. If the screenshot shows under 12 px between the chips, the sentence and the button, STOP.

7. **Guest page.** In `App/app/templates/payments_qr.html` keep the `<h1>` and the `paid` badge line; wrap the amount line, the VS line, the `<img ...>` and the disclosure `<p class="ui-sub">` in `{% if no_account_text %}<p>{{ no_account_text }}</p>{% else %}` ... `{% endif %}`. The new text contains no "paid" wording and no new status.

8. **Anchor.** In `App/app/templates/payments.html` change `<section class="card payments-box">` (line ~62, the only match) to `<section class="card payments-box" id="stripe-setup">`. Command: `grep -c 'id="stripe-setup"' app/templates/payments.html`. Expect `1`.

9. **Invoice, lock offline, lock not found.**
 a. `invoice_form.html` ~288-290: replace
```
      {{ t('invoice.warn_no_iban') }}
    </p>
```
with
```
      {{ t('invoice.warn_no_iban') }} <a href="/entities">{{ t('payments.fix.bank') }}</a>
    </p>
```
Then `grep -rn "warn_no_iban\|The operator has no bank account" tests | head -5`; update any assertion on the old text.
 b. `_property_editor.html:443`: replace `<p>{{ t('health.door.offline') if door_code.state == 'offline' else t('health.door.times') }}</p>` with `<p>{% if door_code.state == 'offline' %}{{ t('health.door.offline') }} {{ t('smart_locks.offline_fix') }} <a href="/guide#door-codes">{{ t('smart_locks.guide_link') }}</a>{% else %}{{ t('health.door.times') }}{% endif %}</p>`.
 c. `routes/admin.py` ~803-805: append `, fix="lock_guide"` to the two `_back(share, ...)` calls for `flash.error.smart_locks_plain_key` and `flash.ok.smart_locks_none_yet`.
Command: `.venv/bin/python -c "import app.main" 2>&1 | tail -5`. Expect no output.

10. **Tests.** Append to `App/tests/test_payment_rails.py`, reusing its `owner`, `client`, `_draft` helpers (read fixtures at lines 38-100 first; to remove the account run `db.execute("UPDATE legal_entity SET iban = NULL, bank_account = NULL WHERE owner_user_id = ?", (owner_id,))`):
 - POST `/payments/requests/new` rail `qr`, no account: 303 to `/payments/new?...fix=bank`, no `payment_request` row created; with an account: row created.
 - GET `/payments/new`, no account: Bank QR radio `disabled` and "Add bank account (1 min)" link to `/entities`; with an account: not disabled.
 - Host PNG and guest PNG, no account: 404, `text/plain`, body equals `payment_request.NO_ACCOUNT_BODY`; wrong rail still an empty 404.
 - Guest page, no account: 200, `pay_no_account` text in en, cs and de (`?lang=de`), no `<img`, no word "paid".
 - `?err=x&fix=bank` renders `href="/entities"`; `?err=x&fix=evil` renders no extra link.
Command: `.venv/bin/python -m pytest tests/test_payment_rails.py tests/test_payment_request_model.py tests/test_stripe_connect.py tests/test_payments_dashboard.py tests/test_payment_links.py tests/test_payment_qr.py tests/test_payment_services.py -q --tb=short -x 2>&1 | tail -30`. Expect green.

11. **Other test-map rows.** Each `-q --tb=short -x 2>&1 | tail -30`, expect green: `.venv/bin/python -m pytest tests/test_invoice_*.py tests/test_stay_fee*.py`; `.venv/bin/python -m pytest tests/test_door_code*.py tests/test_ttlock*.py tests/test_smart_locks_page.py`; `.venv/bin/python -m pytest tests/test_host_*.py tests/test_host_geometry.py` (0 skipped); `.venv/bin/python -m pytest tests/test_guest_*.py tests/test_guest_browser_e2e.py` (0 skipped).

12. **UX gate and screenshots.** From `App/`: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py tests/test_design_guardrails_browser.py -q -x 2>&1 | tail -30`, 0 skipped, zero host findings. Open and describe 390/768/1280 of `/payments/new` (no account), `/invoices/new` (no account), the property lock section with an offline lock, and a toast carrying a fix link. Guest: one 390 px screenshot of `/pay/{id}/{token}` with no account, plus the guest browser tests of step 11 with 0 skipped. Tick the design-system checklist in the PR body. From the repo root run `python3 scripts/context_lint.py`.

## 5. Do not touch

`go/`, `App/app/static/*` (CSS, JS, `static_versions.json`), migrations, any write to `payment_request.status`, stay-fee payment code (`stay_fee.py`, `routes/stay_fees.py`, the stay-fee QR in `routes/guest.py`), UbyPort filing code. AGENTS.md rules 2, 4, 5, 8, 9.

## 6. Commands

As in the steps. Never the full suite.

## 7. Acceptance

- [ ] `grep -rn 'fix="' app/routes` shows `bank` x2 (create, preview), `stripe` x3, `lock_guide` x2. The invoice link is a template `href`, not a `fix=`.
- [ ] POST `/payments/requests/new` rail `qr` with no bank account creates no row and redirects with `fix=bank`.
- [ ] `/payments/new` with no account: Bank QR radio disabled, one sentence plus one "Add bank account (1 min)" button, nothing else added.
- [ ] Host and guest QR PNG with no account: 404 `text/plain`, body `NO_ACCOUNT_BODY`; guest page 200 with `pay_no_account` in en, cs, de, es, fr, uk.
- [ ] An unknown `?fix=` renders no link.
- [ ] `git diff | grep -i paid` shows no added line.
- [ ] Steps 4, 10, 11, 12 green; 0 skipped in browser files; 390 px screenshots in the report; `context_lint` clean except the known status.md cap.

## 8. Stop and ask

Stop and write the report as `blocked` if an anchor is not found verbatim (1066 or 1067 may have moved `base.html`), an import cycle appears, a test fails twice, the toast link is unreadable and would need CSS, a file outside §3 needs a change, or you reach 25 tool calls or about 50k tokens.

## 9. Report

`docs/tasks/1068a-report.md` (600 tokens at most), `Status: review`: files changed, each command with its last 5 output lines, §7 ticked, deviations, questions.

## Risk list (for the reviewer)

`routes/payments.py` (new refusal, PNG bodies, guest page), `templating.py` and `base.html` (every host page), `payments_qr.html` (guest, public), `admin_helpers.py`.

## Owner steps

1. After merge nothing to run. Deploy 1068b together with 1068a: the Go service answers `/payments/requests/new` and both QR PNG routes in production, and must match.
