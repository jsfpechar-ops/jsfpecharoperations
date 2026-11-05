# 0897-fix-3: estimate sentence and a legal question mark beside the amount

Status: replaced by 0958
Depends on: none. Do not run. The estimate copy and the legal question mark are already on `claude/zealous-johnson-kjnz4e` in brief 0958.
Base: branch `cursor/guest-pay-operator-preview-237c`. Stay on it. Do not push. Do not open a PR.
Executor: Haiku | Report: docs/tasks/0897-fix-3-report.md

## 1. Objective

The form estimate drops the word that means "about" in all six guest languages. The amount on the estimate card and on the hub fee card gets a question mark that shows the existing legal fee text and the statute link. One explanation, so the old one-line pointer under the hub card goes away.

## 2. Context

The legal text already exists. Do not write a new explanation. Keys: `legal_notice_fee_body`, `legal_notice_fee_link`, `legal_notice_fee_title`. The link is `https://www.e-sbirka.cz/sb/1990/565`. The hub card today ends with `{{ t('fee_legal_pointer') }}` in `App/app/templates/guest/_fee_pay.html`. The estimate is `App/app/templates/guest/_fee_estimate.html`.

Current English estimate (`App/app/i18n.py`):

```
"fee_estimate_body": "About %(amount)s for you (%(days)s counted nights × %(rate)s CZK). You will choose how to pay once everyone is registered.",
```

The form estimate is computed from what the guest has typed. It cannot know a later host exemption. The hub total is the one that counts. Keep that second sentence in every language.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/i18n.py` | edit | `fee_estimate_body` in en, cs, de, es, fr |
| `App/app/guest_uk_i18n.py` | edit | `fee_estimate_body` in uk |
| `App/app/templates/guest/_fee_pay.html` | edit | question mark beside the amount; remove the pointer line |
| `App/app/templates/guest/_fee_estimate.html` | edit | the same question mark beside the amount |
| `App/app/static/guest.css` | edit | the question-mark control |
| `App/app/templates/guest/base.html` | edit | `guest.css?v=20261105-gp4` |
| `App/app/templates/guest/archive/ticket-wallet/base.html` | edit | same query string, only if the version test requires it |
| `App/tests/static_versions.json` | edit | via `--write` |
| `App/tests/test_guest_browser_e2e.py` | edit | estimate text has no "About"; the question mark is present |
| `docs/tasks/0897-fix-3-report.md` | create | report |
| `docs/tasks/screenshots-0897/guest-fee-390.png` | create | hub at 390 px |
| `docs/tasks/screenshots-0897/guest-estimate-390.png` | create | form estimate at 390 px |

## 4. Steps

1. Replace `fee_estimate_body` in each language. Keep the placeholders `%(amount)s`, `%(days)s`, `%(rate)s`.

- en: `%(amount)s for you (%(days)s counted nights × %(rate)s CZK). You will choose how to pay once everyone is registered.`
- cs: `%(amount)s pro vás (%(days)s započitatelných nocí × %(rate)s Kč). Způsob platby si vyberete, až budou zaregistrovaní všichni hosté.`
- de: `%(amount)s für Sie (%(days)s angerechnete Nächte × %(rate)s CZK). Die Zahlungsart wählen Sie, sobald alle Gäste registriert sind.`
- es: `%(amount)s para usted (%(days)s noches computables × %(rate)s CZK). Elegirá cómo pagar cuando todos estén registrados.`
- fr: `%(amount)s pour vous (%(days)s nuits comptées × %(rate)s CZK). Vous choisirez comment payer quand tous les invités seront enregistrés.`
- uk in `App/app/guest_uk_i18n.py`: `%(amount)s для вас (%(days)s врахованих ночей × %(rate)s CZK). Спосіб оплати оберете, коли зареєструються всі гості.`

Do not add a key. Command: `cd App && .venv/bin/python -m pytest tests/test_no_em_dashes.py -q --tb=short -p no:cacheprovider 2>&1 | tail -30`. Commit `0897-fix-3 step 1`.

2. In both guest templates, beside the amount, add this block. On the hub the amount is `fee_total`. On the estimate the amount is already inside `fee_estimate_body`; put the control immediately after the `<h2>`, still inside the card, so it sits on the same row as the heading's amount line. Use one markup in both files:

```html
<details class="g-fee-why">
  <summary>{{ t('legal_notice_fee_title') }}</summary>
  <p>{{ t('legal_notice_fee_body') }}</p>
  <p><a href="https://www.e-sbirka.cz/sb/1990/565" rel="noopener" target="_blank">{{ t('legal_notice_fee_link') }}</a></p>
</details>
```

The summary text is the existing title, not a bare `?` character with no name, so a screen reader gets the title. Style the summary as a 44 px round control whose visible glyph is `?` (the title stays in `aria` via the text, visually hidden except the mark). Delete the `<p class="g-intro g-fee-legal">{{ t('fee_legal_pointer') }}</p>` line from `_fee_pay.html`. Do not delete the `fee_legal_pointer` strings from `i18n.py`.

Append to `App/app/static/guest.css` (do not read the whole file; it is long):

```css
/* 0897 legal help beside the stay-fee amount */
.g-fee-why { margin: 8px 0 0; }
.g-fee-why > summary {
  display: inline-flex; align-items: center; justify-content: center;
  width: 44px; height: 44px; border-radius: 22px;
  border: 1px solid currentColor; cursor: pointer; list-style: none;
}
.g-fee-why > summary::-webkit-details-marker { display: none; }
.g-fee-why > summary { font-size: 0; }
.g-fee-why > summary::before { content: "?"; font-size: 18px; font-weight: 700; }
.g-fee-why[open] > p { margin: 8px 0 0; }
```

`font-size: 0` hides the title text visually; the `?` is the `::before`. The summary's accessible name remains the title text. Bump `guest.css?v=` to `20261105-gp4` in `App/app/templates/guest/base.html`. Run `cd App && .venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -30` and commit any template it rewrites. Commit `0897-fix-3 step 2`.

3. In `App/tests/test_guest_browser_e2e.py` `test_form_estimate_line_shows_when_the_estimate_is_above_zero`, assert the estimate text does not contain `About` and does contain `counted nights`, and that `#fee-estimate .g-fee-why` is visible. On the CZE hub test, assert `#fee-pay .g-fee-why` is visible and `fee_legal_pointer`'s English sentence `Why this fee applies` is absent. Open the details and assert the hub contains `565/1990` or the link href. Command, in tmux: `cd App && UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_guest_browser_e2e.py -k fee -q --tb=short -p no:cacheprovider 2>&1 | tail -30`. Expect pass. Commit `0897-fix-3 step 3`.

4. Screenshots at 390 px. Reuse the fee browser seed only through the existing test, or a short Playwright script under `/tmp` that logs in the way `test_fee_card_shows_with_qr_rail_open_and_enabled_rails` does and saves:
- `docs/tasks/screenshots-0897/guest-fee-390.png` (hub, `#fee-pay` in view, question mark visible)
- `docs/tasks/screenshots-0897/guest-estimate-390.png` (form estimate)
Open both files and write one sentence each in the report: what is on screen, whether the amount and the `?` sit on the card, whether anything is cut off. Do not retake. Commit `0897-fix-3 step 4`.

5. Report. Set this brief `Status: review`. From `App/`: `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q --tb=short -p no:cacheprovider -k "not test_the_finish_card_passes_the_lint" 2>&1 | tail -30`. The excluded test fails because `/mnt/project-files` is not writable. Any other failure: STOP. Commit `0897-fix-3 step 5`. Do not push.

## 5. Do not touch

Host settings, `stay_fees.py`, `guest.py`, rail logic, migrations. Do not rewrite `legal_notice_fee_body`.

## 6. Commands

Section 4, then `python3 scripts/context_lint.py 2>&1 | tail -5` from the repo root.

## 7. Acceptance

- [ ] None of the six `fee_estimate_body` strings start with About, přibližně, etwa, unos, environ or приблизно.
- [ ] Hub and estimate show `.g-fee-why`. The hub does not show the old pointer sentence.
- [ ] The open help contains `legal_notice_fee_body` and the link `https://www.e-sbirka.cz/sb/1990/565`.
- [ ] Fee browser tests pass. Layout lint passes except the known unwritable finish-card test.
- [ ] Two 390 px screenshots exist and are described in the report.

## 8. Stop and ask

A language key is missing. Layout lint fails for a reason other than `/mnt/project-files`. The question mark overlaps the amount so the amount cannot be read. A test fails twice.

## 9. Report

`docs/tasks/0897-fix-3-report.md`, including the two screenshot sentences. Owner steps: none. The flag stays off in production until the owner says otherwise.

## Risk list (reviewer)

Guest copy in six languages. The summary must keep an accessible name.
