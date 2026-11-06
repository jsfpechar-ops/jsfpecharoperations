# 0962: host note under bank transfer is wrong, IBAN is for every guest (executor: Haiku 5.5, alone)
Status: todo

## 1. Objective
In Settings > Stay fee > "Collect from guests" > Bank transfer (IBAN), the note says "Only Czech and Slovak guests see and can use this." That reads as if the whole bank transfer is limited. It is not: the IBAN details show to guests of every country (any EU guest can pay by IBAN); only the payment QR code (Czech SPAYD) is limited to Czech and Slovak guests.

## 2. Context (research done; do not redo)
Key `stay_fees.guest_pay.qr_note` in `App/app/host_i18n.py` (lines ~10674 en, ~10706 cs, ~10738 vi), used at `App/app/templates/_stay_fee_fields.html:106` under the bank card. Guest side (`_fee_pay_panel` in guest.py) already behaves correctly: IBAN rail for all, QR only when a CZ/SK guest is on the device or stay. Do not change logic.

## 3. Files
`App/app/host_i18n.py`, `App/tests/test_stay_fee_guest_pay_0897.py` (existing test that asserts the old note, find with `grep -n "Czech and Slovak\|qr_note" App/tests/*.py`).

## 4. Steps
1. Replace the three values of `stay_fees.guest_pay.qr_note`:
   en: "Guests from any country see the IBAN. Only Czech and Slovak guests also get a payment QR code."
   cs: "IBAN uvidí hosté z jakékoli země. Platební QR kód dostanou jen čeští a slovenští hosté."
   vi: "Khách từ mọi quốc gia đều thấy IBAN. Chỉ khách Séc và Slovakia còn nhận được mã QR thanh toán."
2. Update any test that asserts the old wording to the new en text, and make the assertion say the IBAN is for all guests.
3. Check the text does not appear elsewhere in host UI/help (`grep -rn "Czech and Slovak" App/app/*.py App/app/templates`); fix only host-side copy about the bank transfer that has the same wrong meaning.

## 5. Do not touch
Guest pages, payment logic, other keys.

## 6. Commands
From App/: `python3 -m pytest tests/test_stay_fee_guest_pay_0897.py tests/test_static_versions.py -q --tb=short -x -p no:cacheprovider 2>&1 | tail -20`; `ruff check app tests tools --select E9,F63,F7,F82,F401,F841`; from repo root `python3 scripts/context_lint.py`.

## 7. Acceptance
Tests pass, 0 skipped; lint clean.

## 8. Stop and ask
If the same wrong claim is in guest-facing copy, stop and report instead of changing it.

## 9. Report
Write `docs/tasks/0962-report.md` (5 lines max) with a Status line; set this brief's Status to review. Commit (message ends with "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>" and "Claude-Session: https://claude.ai/code/session_014N5J8MeH3Hk3RVuTWKDVVn"), push to `claude/zealous-johnson-kjnz4e` only. No PR.
