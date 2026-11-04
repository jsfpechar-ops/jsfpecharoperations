# 0932b: fee card, simpler reference (no typing for the guest)

Status: todo
Depends on: 0932 | Base commit: current branch `vibe/stay-fee-guest-payment-plan-73df64` (HEAD ac83583a plus the uncommitted 0932/0934b/0934c work; do not revert or touch it) | Branch: current
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
No commit, no push: the orchestrator commits.

## 1. Objective

Owner request 2026-11-04: "Keep the reference smaller or maybe not at all, I want it smoother." The guest fee card (brief 0932) shows Variable symbol `0000000002` and Message `STAY FEE 0000000002` and asks Revolut payers to type it. Make the reference plain and invisible wherever a machine carries it: the QR carries VS and message itself, only the bank-transfer row shows a short VS, Revolut shows nothing to type.

## 2. Context (decisions, owner-approved)

1. Variable symbol = the plain reservation id, no zero padding (`"2"`; a VS allows up to 10 digits, reservation ids stay far below that).
2. QR rail: only the QR and the amount. VS and a short message are inside the SPAYD payload, so the guest types nothing. No visible IBAN / VS / Message rows.
3. Bank transfer (IBAN) rail: IBAN, amount, `Variable symbol: 2`. No Message row.
4. Revolut rail: amount (already on the button) and the "Pay with Revolut" button only. No intro sentence, no reference.
5. Cash rail: unchanged.
6. Delete the i18n keys that become unused in all 6 guest languages. No new copy. One coral action per screen (the card adds none: the Revolut `g-btn` is the only one it has; leave it). Arrival-lane rules stay (light mode, no JS dependency, no new request).

Note: `payments.spayd()` upper-cases the message (`ascii_upper`, max 60), so the payload will carry `MSG:STAY FEE 2`. That is fine and expected. Do not change `payments.py`.

Anchors (each must be found verbatim, else STOP, section 8).

`App/app/routes/guest.py` in `_fee_pay_panel`:
```python
    vs = f"{int(reservation['id']):010d}"
    message = f"STAY FEE {vs}"
```
```python
            payload = payments.spayd(account, total, vs, message)
            rails.append({"key": "qr", "iban": payments.format_iban(account),
                          "qr": payments.qr_data_uri(payload)})
```
```python
    return {"total": total, "rate": rate, "persons": persons, "rails": rails,
            "vs": vs, "message": message}
```

`App/app/templates/guest/_fee_pay.html`:
```html
              <dl class="g-summary-list">
                <dt>{{ t('fee_iban') }}</dt><dd>{{ rail.iban }}</dd>
                <dt>{{ t('fee_amount_label') }}</dt><dd>{{ fee_total }}</dd>
                <dt>{{ t('fee_vs_label') }}</dt><dd>{{ fee_panel.vs }}</dd>
                <dt>{{ t('fee_message_label') }}</dt><dd>{{ fee_panel.message }}</dd>
              </dl>
```
```html
              <dt>{{ t('fee_vs_label') }}</dt><dd>{{ fee_panel.vs }}</dd>
              <dt>{{ t('fee_message_label') }}</dt><dd>{{ fee_panel.message }}</dd>
            </dl>
```
```html
            <p class="g-intro">{{ t('fee_revolut_intro') }}</p>
```

i18n keys in `App/app/i18n.py` (en ~L344-346, cs ~L1062-1064, de ~L1737-1739, es ~L2230-2232, fr ~L2723-2725) and `App/app/guest_uk_i18n.py` (~L306-308): `fee_message_label` and `fee_revolut_intro` are used only by `_fee_pay.html` and become unused. KEEP `fee_vs_label` (the IBAN rail still shows it) and `fee_iban`, `fee_amount_label`, `fee_qr_alt`.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/routes/guest.py | edit | `_fee_pay_panel`: plain VS, short message, drop `message` from the returned dict, QR rail no longer needs `iban` |
| App/app/templates/guest/_fee_pay.html | edit | QR rail: QR only (amount stays in the card header and on the Revolut button; keep an `<img>` plus the amount line only if section 4 step 2 says so); IBAN rail: drop Message row; Revolut: drop intro |
| App/app/i18n.py | edit | delete `fee_message_label`, `fee_revolut_intro` in en, cs, de, es, fr |
| App/app/guest_uk_i18n.py | edit | delete the same two keys |
| App/app/static/guest.css | edit only if needed | `.g-fee-qr` becomes a lone centred image; if CSS changes, bump `guest.css?v=` in `App/app/templates/guest/base.html` (currently `20261104-0932b`, use `20261104-0910c`) and run `.venv/bin/python scripts/...` exactly as 0932 did: `tests/static_versions.json` rewritten with `--write`, then `tests/test_static_versions.py` must pass |
| App/tests/test_guest_browser_e2e.py | edit | `test_fee_card_shows_with_qr_rail_open_and_enabled_rails`: new row assertions |
| App/tests/test_stay_fee_estimate_0910.py | edit | add the SPAYD/VS unit test |

No other file may change.

## 4. Steps

1. `guest.py` `_fee_pay_panel`: replace the two anchor lines with
```python
    vs = str(int(reservation["id"]))  # plain id, no zero padding; the bank VS field takes up to 10 digits
    message = f"Stay fee {vs}"  # goes only into the SPAYD payload; never shown
```
   Change the QR rail dict to `{"key": "qr", "qr": payments.qr_data_uri(payload)}` and the final return to `"vs": vs}` (drop `"message"`). Command: `grep -n 'fee_panel.message\|"message": message' App/app/routes/guest.py App/app/templates/guest/_fee_pay.html | tail -30` must show no match for the panel after step 2.
2. `_fee_pay.html` QR rail: replace the whole `<div class="g-fee-qr">...</div>` block body with just the image:
```html
            <div class="g-fee-qr">
              <img class="g-fee-qr-img" src="{{ rail.qr }}" width="176" height="176" alt="{{ t('fee_qr_alt') }}">
            </div>
```
   The amount is already the large `g-fee-amount` line at the top of the same card; do not repeat it in the rail (one explanation in one place). Add no new text.
3. `_fee_pay.html` IBAN rail: delete only the `fee_message_label` line; keep IBAN, amount, `fee_vs_label` rows.
4. `_fee_pay.html` Revolut rail: delete the `<p class="g-intro">{{ t('fee_revolut_intro') }}</p>` line; the `<a class="g-btn" ...>` stays.
5. `i18n.py` and `guest_uk_i18n.py`: delete the two unused keys in all 6 languages (one line each, 12 lines). Command: `grep -rn 'fee_message_label\|fee_revolut_intro' App/app | grep -v pycache | tail -30` must print nothing. Then `.venv/bin/python -m pytest tests/test_i18n*.py -q --tb=short -x 2>&1 | tail -30` (run only if such files exist; `ls tests | grep -i i18n` first; also run the catalog-parity test if the test-map names one for guest strings).
6. CSS: `.g-fee-qr` is a flex row with a `.g-summary-list` sibling that no longer exists. Look at the 390 screenshot; if the lone QR is left-aligned and looks fine, leave the CSS alone (no `?v=` bump). If it needs centring, change only `.g-fee-qr` in `guest.css` to `display: flex; justify-content: center;` and remove the dead rule `.g-fee-qr .g-summary-list { flex: 1 1 180px; min-width: 0; }`, then bump `?v=` and rewrite `tests/static_versions.json` as in section 2 (files table row). Keep `.g-fee dd` rule (the IBAN rail still uses it).
7. Test `test_stay_fee_estimate_0910.py`: add a test that builds the payload the way the route does and checks the plain values:
```python
def test_fee_qr_payload_carries_plain_vs_and_short_message():
    from app import payments
    payload = payments.spayd("CZ6508000000192000145399", 150, "2", "Stay fee 2")
    assert "*X-VS:2*" in payload
    assert payload.endswith("MSG:STAY FEE 2")
    assert "0000000002" not in payload
```
   If you can reach `_fee_pay_panel` cheaply with the seeded rows from `_fee_seed` in the e2e file (same DB, `db.query_one` the apartment and reservation, call `guest._fee_pay_panel(apartment, reservation, translate_fn)`), also assert `panel["vs"] == str(reservation_id)` and `"message" not in panel`. If that takes more than 2 tool calls, skip it and say so in the report.
8. `test_guest_browser_e2e.py` `test_fee_card_shows_with_qr_rail_open_and_enabled_rails`: after the existing `.g-fee-qr-img` assertions add (card is `#fee-pay`; open each rail's `<summary>` by clicking it before reading its text; rails are the four `details.g-summary` that contain `.g-fee-rail`, in order qr, iban, revolut, cash):
```python
        qr_rail = card.locator("details.g-summary").filter(has=page.locator(".g-fee-qr-img"))
        qr_text = qr_rail.locator(".g-fee-rail").inner_text()
        assert qr_text.strip() == ""  # QR only: no IBAN, VS or message to type
        card.get_by_text("Bank transfer", exact=False).first.click()   # use the real en label of fee_rail_iban
        iban_text = card.locator("details[open]").filter(has_text="Variable symbol").inner_text()
        assert "Variable symbol" in iban_text and "Message" not in iban_text
        assert "0000000" not in card.inner_text()
        card.get_by_text("Revolut", exact=False).first.click()
        assert "Open your host" not in card.inner_text()
        assert card.get_by_role("link", name="Revolut", exact=False).count() == 1
```
   Read `fee_rail_iban` / `fee_rail_revolut` / `fee_revolut_button` in `i18n.py` (en) first and use the real strings. Use the seeded reservation id: `_fee_seed` returns the stay token; the VS is the reservation id (`str(int(id))`), assert that exact short value appears in the IBAN rail text and that no 10-digit zero-padded form does. The existing 4 widths parametrization stays.

## 5. Do not touch

`App/app/payments.py`, `App/app/stay_fee.py`, anything under `App/app/migrations/`, host templates and host CSS/JS (the uncommitted 0934b/0934c work), `docs/`, `.env`. Hard rules that apply: light mode only; no new dependency; no new outbound request; no tracking cookies; no personal data stored (the VS is the reservation id, nothing new); `?v=` bump only if `guest.css` changed.

## 6. Commands (from `App/`; foreground only; each ends `| tail -30`)

Seeded guest tests need `mail.mail_enabled` monkeypatched False, as already in the three fee tests (0932); copy that if you add a seeded test.

1. Quick: `.venv/bin/python -m pytest tests/test_stay_fee_estimate_0910.py -q --tb=short -x 2>&1 | tail -30` -> all pass.
2. Full set for this change: `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_guest_browser_e2e.py tests/test_stay_fee_estimate_0910.py tests/test_layout_lint_browser.py -q --tb=short -rs 2>&1 | tail -30` -> all pass, `0 skipped` in the summary line.
3. If `guest.css` changed: `.venv/bin/python -m pytest tests/test_static_versions.py -q --tb=short 2>&1 | tail -30` -> passed.
4. From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30` -> no new error.

## 7. Acceptance

- [ ] `grep -rn 'fee_message_label\|fee_revolut_intro' App/app | grep -v pycache | tail -30` prints nothing; the 6 language catalogs still load (command 2 green).
- [ ] The SPAYD unit test passes: `X-VS:2`, `MSG:STAY FEE 2`, no `0000000002`.
- [ ] Command 2: all pass, 0 skipped.
- [ ] Rendered card: QR rail is the image alone; IBAN rail shows IBAN, amount, `Variable symbol` with the plain id and no Message; Revolut rail shows only the button; cash unchanged.
- [ ] No `0000000` string anywhere in the rendered card (`card.inner_text()`).
- [ ] Screenshots in `docs/tasks/screenshots-0932b/` (create the folder; take them with a small throwaway Playwright script in the scratchpad dir, or by reusing the e2e fixtures with `page.screenshot`; do not commit the script): `hub-fee-card-320.png` and `hub-fee-card-390.png` (QR rail open), `iban-open-390.png`, `revolut-open-390.png`, `hub-cs-390.png` (Czech, `?lang=cs`, card visible with a rail open). Look at each file with Read; in the report write one line per image on what you saw (QR not clipped, no horizontal scroll, one coral action, Czech labels not cut off).
- [ ] No host page was touched, so the host UX gate (rule 10) does not apply; guest rule 7 is covered by the three test files above plus the screenshots.

## 8. Stop and ask

Stop, and write the report, if:

- an anchor in section 2 is not found verbatim;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside section 3 needs a change (including `payments.py`);
- section 5 would be touched, or the uncommitted 0934b/0934c host work shows up in your diff;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0932b-report.md` (600 tokens at most) and set `Status: review`. The report has: 1. files changed (`git diff --stat` limited to the section 3 files); 2. each command with the last 5 lines of output; 3. section 7 ticked, with the per-image screenshot lines; 4. deviations (for example the optional panel-level assertion skipped); 5. questions; 6. owner steps left (none expected).

## Risk list (for the reviewer)

`App/app/routes/guest.py` `_fee_pay_panel` (VS format change: any host bank-match logic that expects the old padded VS? Reviewer greps `stay_fee` and `bank_import` for `010d` before merge), `App/app/templates/guest/_fee_pay.html`, the two i18n files (key deletion, 6 languages).

## Owner steps

None for this brief. After merge and deploy, optional: pay a test stay fee by scanning the QR in the bank app and check the bank pre-fills amount, VS `2`-style id and the message.
