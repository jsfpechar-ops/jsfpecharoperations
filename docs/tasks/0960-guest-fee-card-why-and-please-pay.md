# 0960: guest fee card, short "why" and a kind "please pay" (executor: Haiku 5.5, alone)
Status: review

## 1. Objective
On the guest stay page the stay-fee card says, in plain visible text (not hidden in the "?" disclosure), why the fee exists and kindly asks the guest to pay it now. The guest must understand it is required by law.

## 2. Context (research done; do not redo)
Card template: `App/app/templates/guest/_fee_pay.html`. It shows title, rate line, amount, a "?" disclosure (`legal_notice_fee_body`), per-person fold, payment methods, and at the bottom the line `fee_legal_pointer` ("Why this fee applies: see the legal information you confirmed."). Strings: `App/app/i18n.py` (en, cs, de, es, fr) and `App/app/guest_uk_i18n.py` (uk). Do not touch host files or the payment logic. Legal sign-off on the wording is still pending with the owner, so keep claims to what `legal_notice_fee_body` already says.

## 3. Files
`_fee_pay.html`, `App/app/i18n.py`, `App/app/guest_uk_i18n.py`, `App/app/static/guest.css` only if spacing needs it (then bump its `?v=` key and run `tests/test_static_versions.py --write`), `App/tests/test_stay_fee_guest_pay_0897.py`.

## 4. Steps
1. New key `fee_intro` in all six languages, shown right under the `<h2>` as `<p class="g-intro">`, before the rate line. English: "This is a local stay fee required by Czech law (Act No. 565/1990 Coll.). Your host collects it and passes it on to the municipality. Please pay it now with one of the options below. Thank you!" Translate the same warm tone for cs, de, es, fr, uk (a short sentence for each: why, who receives it, kind request).
2. Remove the `fee_legal_pointer` paragraph at the bottom of the card (it is now redundant) and its keys in all languages if nothing else uses them (grep first).
3. Keep the "?" disclosure for the full legal text. Do not hide `fee_intro` inside any `<details>`.
4. Test: a TestClient test that the stay page (card shown) contains the `fee_intro` text in en and cs and no longer contains the old pointer text.

## 5. Do not touch
guest.py logic, host settings, payment methods, QR logic.

## 6. Commands
From App/: `python3 -m pytest tests/test_stay_fee_guest_pay_0897.py tests/test_static_versions.py -q --tb=short -x -p no:cacheprovider 2>&1 | tail -30`; then with `UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium UBYHOST_REQUIRE_BROWSER=1`: `python3 -m pytest tests/test_guest_browser_e2e.py -k fee -q --tb=short -p no:cacheprovider 2>&1 | tail -30`. Take a 390 px screenshot of the card (docs/tasks/screenshots-0960/).

## 7. Acceptance
Tests pass with 0 skipped; the intro text is visible without opening anything; screenshot shows no overflow at 390 px.

## 8. Stop and ask
If a language key is used elsewhere or the card layout breaks, stop and report.

## 9. Report
Write `docs/tasks/0960-report.md` (10 lines max) with a Status line. Commit (message ends with "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>" and "Claude-Session: https://claude.ai/code/session_014N5J8MeH3Hk3RVuTWKDVVn") and push to `claude/zealous-johnson-kjnz4e` only. No PR.
