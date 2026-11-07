# 0994: Guest stay fee, clear and calm

Status: todo
Depends on: none | Base commit: 915081a3 (origin/main) | Branch: task/0994-guest-stay-fee-clear
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (Step 7, Copy buttons, is optional; if you reach 22 calls, skip it and say so)

## 1. Objective

Replace the small stay-fee estimate card on the guest form Check step, and the dense fee card on the stay page, with one calm "fee box" look: big amount, one plain panel ("You do not pay now." or "Please pay now."), large tap targets, one short "Why do I pay this?" fold. The guest must see at once whether they pay now and how much.

Owner approved the design from static mockups. They are in `docs/tasks/screenshots-0994/`: `mockup.html` (open `?s=hub` for the stay page, `?open=1` for folds open), `mock-check-390.png`, `mock-check-390-open.png`, `mock-hub-390.png`. Read `mockup.html` for exact sizes.

## 2. Context

**Branch from `origin/main`, never from PR 798 / `pr798`.** PR 798 (the earlier fee attempt) carries unrelated #790 commits (8e59e74f, 9cd6b7ee, 6e1a1213, ca0e651f). Do NOT cherry-pick anything from it. Its lock-panel duplicate-button removal, test change, `app2.css` grid tweak and the `guest_form_admin.html` Cancel tap target stay with PR 798 / #790. Its inline `<dl>` estimate inside `#legal-notice`, the "estimate" badge and the `initLegalFeeJump` JS are dropped for good. This brief is the fee only.

Rules: [rules: guest pages](../context/rules.md#guest-pages), [rules: copy](../context/rules.md#copy), DESIGN Arrival lane (one coral button per screen; legal info in a grey box; the acknowledgement in a coral-edged box above Submit). Light mode only. No JS needed for the form box or the folds.

Facts on main (verified at base commit):
- `App/app/templates/guest/form.html` line ~312: `{% if fee_estimate %}{% include "guest/_fee_estimate.html" %}{% endif %}` and line ~313: `{% if fee_panel %}{% include "guest/_fee_pay.html" %}{% endif %}`. Find where `_legal_notice.html` is included in the same file (`grep -n "_legal_notice" ...`).
- `_fee_estimate.html` is `<div class="g-card g-fee-estimate" id="fee-estimate">` with `fee_estimate_title`, `fee_estimate_body`, and a `<details class="g-fee-what">` with a "?" summary. It uses `fee_estimate.amount`, `.days`, `.rate`.
- `_fee_pay.html` is `<div class="g-card g-fee" id="fee-pay">` with `fee_title`, `fee_intro`, `fee_rate_line`, `.g-fee-amount`, the same `?` fold, a `g-summary` fold `fee_per_person` over `fee_panel.persons` (`days`, `amount`), then `fee_choose` and one `<details class="g-summary">` per `fee_panel.rails` (`iban` with `qr`/`iban`, `revolut` with `link`, `cash` with `note`), plus `fee_panel.payee`, `.vs`, `.total`, `.rate`. Route builder: `_fee_pay_panel` in `App/app/routes/guest.py` (~2175). **Do not change the route.**
- `legal_notice_fee_body` and `legal_notice_fee_link` stay used by `_legal_notice.html` (`#legal-fee-section`). The legal notice is not touched.
- `guest.css` has no `.g-fee-what*` rule on main (grep returned none). The only dead selector after this brief is `.g-fee-estimate dd` on `guest.css` line ~1599.
- Existing tests: `App/tests/test_guest_browser_e2e.py` line ~660 (`test_fee_card_shows_with_qr_rail_open_and_enabled_rails`, asserts `#fee-pay`, `details.g-summary` with `.g-fee-rail` count 3, `.g-fee-qr-img`, summary `summary.g-summary-fold`) and line ~809 (`#fee-estimate` count 1 and visible). Keep the classes those tests use (`g-summary`, `g-summary-fold`, `g-fee-rail`, `g-fee-qr-img`) on the pay options, so they keep passing.
- Cache keys now: `guest.css?v=20261106-0977`, `guest-enhancements.js?v=20261003a` (in `App/app/templates/guest/base.html`).

**Out of scope, note in the report:** the case where the liable nights differ from the stay nights (no copy approved); any payment confirmation or paid status.

### Copy (exact; new keys in `App/app/i18n.py` for en, cs, de, es, fr; uk in `App/app/guest_uk_i18n.py`)

| Key | EN | CS |
|---|---|---|
| `fee_box_you` | Local stay fee for you | Místní poplatek za pobyt pro vás |
| `fee_box_group` | Local stay fee for your group | Místní poplatek za pobyt pro vaši skupinu |
| `fee_calc_you` | %(days)s nights × %(rate)s CZK | %(days)s nocí × %(rate)s Kč |
| `fee_calc_group` | %(guests)s guests · %(days)s nights × %(rate)s CZK each | %(guests)s hostů · %(days)s nocí × %(rate)s Kč za každého |
| `fee_later_title` | You do not pay now. | Teď neplatíte. |
| `fee_later_body` | When everyone in your group has registered, you choose how to pay. | Až se zaregistruje celá vaše skupina, vyberete si, jak zaplatit. |
| `fee_now_title` | Please pay now. | Zaplaťte prosím teď. |
| `fee_now_body` | Choose one way below. You only pay once for the whole group. | Vyberte jednu možnost níže. Platíte jen jednou za celou skupinu. |
| `fee_why` | Why do I pay this? | Proč to platím? |
| `fee_why_body` | Czech towns charge a small fee for each night you stay. Your host collects it and pays it to the town. | Česká města vybírají malý poplatek za každou noc pobytu. Váš hostitel ho vybírá a předává městu. |
| `fee_law_link` | Read the law (Act 565/1990) | Přečíst zákon (č. 565/1990 Sb.) |
| `fee_copy` / `fee_copied` | Copy / Copied | Kopírovat / Zkopírováno |
| `fee_per_person` (existing key, new text) | See the amount for each guest | Zobrazit částku za každého hosta |

DE: Örtliche Aufenthaltsabgabe für Sie · Örtliche Aufenthaltsabgabe für Ihre Gruppe · %(days)s Nächte × %(rate)s CZK · %(guests)s Gäste · %(days)s Nächte × %(rate)s CZK pro Person (write "pro Person") · Sie zahlen jetzt nichts. · Sobald Ihre ganze Gruppe registriert ist, wählen Sie, wie Sie zahlen. · Bitte jetzt zahlen. · Wählen Sie unten eine Möglichkeit. Sie zahlen nur einmal für die ganze Gruppe. · Warum zahle ich das? · Tschechische Städte erheben für jede Übernachtung eine kleine Abgabe. Ihr Gastgeber zieht sie ein und leitet sie an die Stadt weiter. · Gesetz lesen (Nr. 565/1990) · Kopieren / Kopiert · Betrag für jeden Gast anzeigen
ES: Tasa turística local para usted · Tasa turística local para su grupo · %(days)s noches × %(rate)s CZK · %(guests)s huéspedes · %(days)s noches × %(rate)s CZK cada uno · Ahora no paga nada. · Cuando todo su grupo esté registrado, elegirá cómo pagar. · Pague ahora, por favor. · Elija una forma abajo. Solo paga una vez por todo el grupo. · ¿Por qué pago esto? · Las ciudades checas cobran una pequeña tasa por cada noche de estancia. Su anfitrión la cobra y se la entrega a la ciudad. · Leer la ley (n.º 565/1990) · Copiar / Copiado · Ver el importe de cada huésped
FR: Taxe de séjour locale pour vous · Taxe de séjour locale pour votre groupe · %(days)s nuits × %(rate)s CZK · %(guests)s voyageurs · %(days)s nuits × %(rate)s CZK chacun · Vous ne payez rien maintenant. · Quand tout votre groupe sera enregistré, vous choisirez comment payer. · Merci de payer maintenant. · Choisissez un moyen ci-dessous. Vous ne payez qu'une fois pour tout le groupe. · Pourquoi je paie cela ? · Les villes tchèques perçoivent une petite taxe pour chaque nuit passée. Votre hôte la collecte et la reverse à la ville. · Lire la loi (n° 565/1990) · Copier / Copié · Voir le montant pour chaque voyageur
UK: Місцевий збір за проживання для вас · Місцевий збір за проживання для вашої групи · %(days)s ночей × %(rate)s CZK · %(guests)s гостей · %(days)s ночей × %(rate)s CZK з кожного · Зараз платити не потрібно. · Коли зареєструється вся ваша група, ви оберете, як заплатити. · Будь ласка, сплатіть зараз. · Оберіть один спосіб нижче. Ви платите лише раз за всю групу. · Чому я це плачу? · Чеські міста беруть невеликий збір за кожну ніч проживання. Ваш господар збирає його й передає місту. · Прочитати закон (№ 565/1990) · Копіювати / Скопійовано · Показати суму для кожного гостя

No em dashes. German nouns capitalised. Same key order in every language block; put the new keys right after `fee_no_rails`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/guest/_fee_estimate.html` | rewrite | new `g-fee-box` (Screen 1) |
| `App/app/templates/guest/_fee_pay.html` | rewrite | new `g-fee-box` + option folds (Screen 2) |
| `App/app/templates/guest/_fee_why.html` | create | shared "Why do I pay this?" fold (Step 3) |
| `App/app/templates/guest/form.html` | edit | move the estimate include to just before the legal notice include |
| `App/app/static/guest.css` | edit | add fee-box rules, drop `.g-fee-estimate dd` |
| `App/app/static/guest-enhancements.js` | edit (Step 7 only) | Copy buttons |
| `App/app/i18n.py`, `App/app/guest_uk_i18n.py` | edit | copy table above; remove dead keys |
| `App/app/templates/guest/base.html`, `App/tests/static_versions.json` | edit | bump `?v=` for changed CSS/JS |
| `App/tests/test_guest_browser_e2e.py` | edit | the two fee tests |

No other file may change. Read the files only at the named lines.

## 4. Steps

1. **Branch.** `git fetch origin && git checkout -b task/0994-guest-stay-fee-clear origin/main 2>&1 | tail -30`. Expected: branch created from main. Do not touch `pr798`.
2. **Tokens and CSS.** `grep -n -- "--info\|--blue-bg" App/app/static/tokens.css | tail -30`. Use `--g-surface-2`/existing tokens if a soft grey-blue exists; otherwise define in `guest.css` on `.g-fee-box`: `--fee-bg:#f3f4f8; --fee-line:#d9dbe5;` (mockup values). Add to `guest.css` (end of the fee block near line ~1598), sized as in `mockup.html`: `.g-fee-box` (bg, 1px border, radius 16px, padding 20px, margin-bottom 16px, no coral); `.g-fee-box h3` 19px; `.g-fee-amt` 34px/800/ink; `.g-fee-calc` 17px ink (not muted, no text-transform); `.g-fee-panel` (flex, gap 12px, white, radius 12px, padding 14px; `.g-fee-panel--pay` border 2px ink); `.g-fee-fold` (border-top, `summary` list-style none, min-height 48px, flex, 700, `::-webkit-details-marker` none, `summary::before` 26px ring with CSS-drawn + via two linear-gradients, open state drops the vertical bar, see mockup lines 40-42); `.g-fee-opt` (white, 2px border, radius 14px; `summary` min-height 60px, 18px/800, `.g-fee-radio` 24px ring, open state 7px ink border); `.g-fee-iban span{white-space:nowrap}`; `.g-fee-copy` min-height 44px. All body text at least 17px. Delete `.g-fee-estimate dd` from the line-1599 rule (keep `.g-fee dd`; if `.g-fee` is no longer used in templates after Step 4, replace with `.g-fee-box dd`). Delete `.g-fee-amount` only after `grep -rn "g-fee-amount" App/app` shows no use.
3. **Screen 1 template.** Replace the whole of `_fee_estimate.html` with:
   `<section class="g-fee-box" id="fee-estimate" aria-labelledby="fee-estimate-h">` containing `<h3 id="fee-estimate-h">{{ t('fee_box_you') }}</h3>`, `<p class="g-fee-amt">{{ t('fee_amount', amount=fee_estimate.amount) }}</p>`, `<p class="g-fee-calc">{{ t('fee_calc_you', days=fee_estimate.days, rate=fee_estimate.rate) }}</p>`, then `<div class="g-fee-panel">` with an inline 24px SVG green check (`aria-hidden="true"`, from mockup line ~86) and `<span><b>{{ t('fee_later_title') }}</b> {{ t('fee_later_body') }}</span>`, then the fold `<details class="g-fee-fold"><summary>{{ t('fee_why') }}</summary><p>{{ t('fee_why_body') }}</p><p><a href="https://www.e-sbirka.cz/sb/1990/565" rel="noopener" target="_blank">{{ t('fee_law_link') }}</a></p></details></section>`. To avoid duplicate markup, put the fold in `guest/_fee_why.html` (new file, add to §3 list) and `{% include %}` it from both templates.
4. **form.html.** Move line ~312 so the estimate include sits directly above `{% include "guest/_legal_notice.html" %}` (after the review rows). Leave the `fee_panel` include where it is. Check: `grep -n "_fee_estimate\|_legal_notice\|_fee_pay" App/app/templates/guest/form.html`: estimate line number is lower than legal notice line number.
5. **Screen 2 template.** Rewrite `_fee_pay.html`, keeping `id="fee-pay"` but on `<section class="g-fee-box" ...>` (drop `g-card`): h3 `fee_box_group`; `.g-fee-amt` = `fee_total`; calc line: `{% set nights = fee_panel.persons|map(attribute='days')|unique|list %}` and if `fee_panel.persons|length > 1 and nights|length == 1` show `t('fee_calc_group', guests=fee_panel.persons|length, days=nights[0], rate=fee_panel.rate)`, else show the existing `t('fee_rate_line', rate=fee_panel.rate)`. No route change. Then `.g-fee-panel.g-fee-panel--pay` with a dark "!" SVG (aria-hidden) and `fee_now_title` / `fee_now_body`. Then each rail as `<details class="g-fee-opt g-summary"{% if loop.first %} open{% endif %}><summary class="g-summary-fold"><span class="g-fee-radio" aria-hidden="true"></span>...label...</summary>` with the existing body (`g-summary-body g-fee-rail`, QR `g-fee-qr` + `g-fee-qr-img`, payee/IBAN/amount/VS `<dl>`, Revolut link, cash note) unchanged except: wrap the IBAN as `<span>` groups of 4 (`{% for g in rail.iban.split() %}<span>{{ g }}</span> {% endfor %}`; if `rail.iban` has no spaces, group it with Jinja slicing `rail.iban|batch(4)`), and remove `.g-summary-fold::after` clash (set `.g-fee-opt > summary::after{display:none}`, check against guest.css line ~1345). Keep `fee_no_rails` branch. Remove the `fee_choose` paragraph and the `fee_intro` paragraph. After the rails: fold `fee_per_person` with the existing persons `<dl>` (class `g-fee-fold`), then `{% include "guest/_fee_why.html" %}`. Revolut button: `grep -n "g-btn" App/app/templates/guest/stay.html App/app/templates/guest/_*.html | head`; if another coral `g-btn` shows on the same hub screen, give the Revolut link the existing secondary button class (`grep -n "g-btn-secondary\|g-btn--" App/app/static/guest.css`); else leave it.
6. **i18n.** Add the table keys to all six language blocks. Remove `fee_intro`, `fee_what_is_this`, `fee_estimate_title`, `fee_estimate_body`, `fee_choose` from all blocks, each only after `grep -rn "<key>" App/app App/tests` shows no remaining use outside i18n files. Keep `fee_title` and `fee_rate_line` if still used (grep). Command: `cd App && .venv/bin/python -m pytest tests/test_*_i18n.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py tests/test_flash_literals.py -q --tb=short -x 2>&1 | tail -30`.
7. **Copy buttons (optional, progressive enhancement).** In `guest-enhancements.js` add at most 30 lines: for each `#fee-pay [data-copy]` element (add `data-copy="{{ value }}"` on the IBAN `<dd>` and VS `<dd>` in the template, plain digits/letters without spaces), append a `<button type="button" class="g-fee-copy">` labelled from `data-copy-label` (`t('fee_copy')`), on click `navigator.clipboard.writeText(value)` then set a `<span role="status" aria-live="polite" class="g-sr">` text to `data-copied` (`t('fee_copied')`) for 2 s. Without JS the value stays selectable text. If `.g-sr` (or the existing visually-hidden class) is not found with `grep -n "sr-only\|g-sr\|visually" App/app/static/guest.css`, STOP this step and skip it. No new dependency, no network.
8. **Cache keys.** Bump `guest.css?v=` (and `guest-enhancements.js?v=` if Step 7 ran) in `App/app/templates/guest/base.html` to `20261107-0994`, and mirror in `App/tests/static_versions.json` (`grep -n "guest" App/tests/static_versions.json`).
9. **Tests.** In `test_guest_browser_e2e.py` (a) fee-estimate test (~809): assert `page.locator("#legal-notice #fee-estimate").count() == 0`; assert `page.evaluate("() => document.getElementById('fee-estimate').compareDocumentPosition(document.getElementById('legal-notice')) & Node.DOCUMENT_POSITION_FOLLOWING")` is truthy; assert `page.get_by_text("You do not pay now.").is_visible()`; (b) hub test (~678): add `assert card.get_by_text("Please pay now.").is_visible()` and `assert card.locator("details.g-fee-fold").count() == 2`. Keep the existing assertions (count 3 `g-summary` rails). Then run section 6.
10. **Screenshots.** Use the existing `_shot_0958` outputs (`form-estimate-390.png`, `guest-hub-fee-card-390.png`); take 768 as well. Open each once, compare with `mock-check-390.png` / `mock-hub-390.png`, and write one line per page on what you saw (amount alone, panel, fold icons, no horizontal scroll, one coral button).

## 5. Do not touch

`App/app/routes/guest.py` and every route; `_legal_notice.html` (the legal text and acknowledgement stay complete); everything from PR 798 / #790 listed in §2; `signature.js`; host templates; `docs/tasks/screenshots-0994/`. No new dependency, no third-party script, no new stored data. Light mode only. No coral inside the fee box.

## 6. Commands

- `cd App && .venv/bin/python -m pytest tests/test_*_i18n.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py tests/test_flash_literals.py -q --tb=short -x 2>&1 | tail -30` (all pass).
- `cd App && .venv/bin/python -m pytest tests/test_guest_*.py -q --tb=short -x 2>&1 | tail -30` (all pass).
- `cd App && .venv/bin/python -m pytest tests/test_guest_browser_e2e.py tests/test_host_geometry.py -q -rs --tb=short -x 2>&1 | tail -30` (pass, 0 skipped).
- From repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance

- [ ] `#fee-estimate` is a `section.g-fee-box`, outside `#legal-notice`, before it in DOM order; text "You do not pay now." visible.
- [ ] `#fee-pay` shows the amount alone on a line, "Please pay now." panel, rails as large folds (first open), then the per-guest fold and "Why do I pay this?".
- [ ] No "?" toggle, no badge, no `text-transform`, no JS needed for either box (Step 7 optional).
- [ ] i18n parity EN/CS and all six blocks; removed keys have no remaining use (grep output in report).
- [ ] `grep -rn "initLegalFeeJump\|_fee_estimate_inline" App` returns nothing.
- [ ] Cache keys bumped in `base.html` and `static_versions.json`.
- [ ] Section 6 commands green, browser tests 0 skipped.
- [ ] 390 and 768 px screenshots of the form Check step and the hub fee card, one line each on what you saw vs the mockup.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt or anchor is not found (`_fee_estimate.html`, `_fee_pay.html`, the include lines in `form.html`);
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (report `blocked`, see executor.md);
- a new dependency, a route change, or a file outside §3 seems needed;
- the fee_panel data does not allow the group line without computing in the route (then keep `fee_rate_line`, do not stop);
- you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0994-report.md` (600 tokens at most), `Status: review`, then open one PR. Include: files changed, last 5 lines per command, §7 ticked, Deviations, Questions (list "liable nights differ from stay nights: copy not decided" and "paid status: out of scope"), owner steps left.

## Risk list (for the reviewer)

`_fee_pay.html` (rails, QR, IBAN grouping), `form.html` include order, `guest.css` summary `::after` clash, the two browser tests.

## Owner steps

1. Open the PR when the executor reports. 2. Wait for green CI. 3. Tell the orchestrator to run the UX gate. 4. Merge with `scripts/merge-pr-on-green.sh <PR number>`. 5. Close or rebase PR 798 so it only carries what #790 needs.
