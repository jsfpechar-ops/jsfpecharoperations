# 1076: Plain labels near filing (Q10) and one reason line on the guest e-mail screen (Q16, S9)

Status: todo
Tier: C | Depends on: none | Base commit: ae60568e | Branch: claude/1076-plain-labels-email-reason
Executor: Sonnet, medium effort. Rule: 3 attempts per failing step, then stop and report. Fits one session: 30 tool calls, 60k tokens; command output stays at 150 lines or fewer.

## 1. Objective

Plan [speed-and-ease](../plans/speed-and-ease.md) Q10 (row at line 229), Q16 (line 235) and S9 (line 367). Copy only. Two jobs: (a) host labels near filing say what the thing is in plain words, the legal term stays in brackets; (b) the guest e-mail screen says in one line why we ask. Section 10 and 11 of the plan: the guest form keeps its look (same cards, colours, type, field order); no police field, stored value, form field name, filing payload or UbyPort field changes. No new tracking, no new script, no new stored data.

## 2. Context

Languages in the dicts (verified): host copy `LANGUAGES = ("en", "cs", "vi")` (`App/app/host_i18n.py:17`; Vietnamese lives in `App/app/host_vi_i18n.py`). Guest copy `LANGUAGES = ("en", "cs", "de", "es", "fr", "uk")` (`App/app/i18n.py:28`; Ukrainian lives in `App/app/guest_uk_i18n.py`). Every key below is changed or added in every language of its dict. German, Spanish and French are guest-only; host labels have no de, es, fr.

Copy rules (AGENTS rule 9): one explanation in one place; no sentence the button already says; "no tracking cookies", never "no cookies".

Plan wording vs code today (checked 2026-11-10):
- "Police accommodation number (IDUB)": the label is the hard-coded string `'IDUB'`, not an i18n key.
- "Short name from the police (zkratka)": key `apartment.form.ubyport.mark_label` ("Facility abbreviation (zkratka)").
- "Who runs the accommodation": key `apartment.form.entity.label` ("Property manager / operator").
- "Ready to take payments" for "live": the plan text is out of date. `payments.setup.step.live` already reads "Take card payments". See Question 1; not in the steps.
- "Payment reference (VS)": keys `stay_fees.metric.vs`, `stay_fees.payment.vs`, `payments.qr.vs` ("Variable symbol").

Proposed copy (write the cs and vi lines as drafts; the owner reads them in review):

| Key | en | cs | vi |
|---|---|---|---|
| `apartment.form.ubyport.idub_label` (new) | Police accommodation number (IDUB) | Policejní číslo ubytování (IDUB) | Số cơ sở lưu trú của cảnh sát (IDUB) |
| `apartment.form.readiness.item.idub` | Police accommodation number (IDUB) | Policejní číslo ubytování (IDUB) | Số cơ sở lưu trú của cảnh sát (IDUB) |
| `apartment.form.ubyport.mark_label` | Short name from the police (zkratka) | Krátký název od policie (zkratka) | Tên viết tắt từ cảnh sát (zkratka) |
| `apartment.form.readiness.item.mark` | Short name from the police | Krátký název od policie | Tên viết tắt từ cảnh sát |
| `apartment.form.entity.label` | Who runs the accommodation | Kdo ubytování provozuje | Ai vận hành chỗ lưu trú |
| `stay_fees.metric.vs`, `stay_fees.payment.vs`, `payments.qr.vs` | Payment reference (VS) | Variabilní symbol (VS) | unchanged (already "Mã VS (variabilní symbol)") |
| `apartment.form.ubyport.idub_hint` | 12 to 14 numbers. On the police letter it is the line "IDUB:". Copy it exactly. | 12 až 14 číslic. V dopise od policie je to řádek „IDUB:“. Opište ho přesně. | same idea, drop only the first sentence |

The hint loses its first sentence because the new label now says it (rule 9). Keep each language's existing typographic quotes.

Guest e-mail line, new key `claim_email_why`, replacing the hint on the claim screen (`tw_email_short` stays; `assigned.html:37` still uses it):

| Lang | Text |
|---|---|
| en | We send your door code and receipt here, and it keeps this booking yours. No marketing. |
| cs | Pošleme sem kód ke dveřím a potvrzení a díky e-mailu zůstane tato rezervace vaše. Žádný marketing. |
| de | Hierhin senden wir Ihren Türcode und die Bestätigung. So bleibt diese Buchung Ihre. Kein Marketing. |
| es | Aquí le enviamos el código de la puerta y el justificante. Así esta reserva sigue siendo suya. Sin publicidad. |
| fr | Nous y envoyons votre code de porte et votre récapitulatif. Ainsi, cette réservation reste la vôtre. Pas de marketing. |
| uk | Сюди ми надішлемо код від дверей і підтвердження, і так це бронювання залишається вашим. Жодної реклами. |

## 3. Files

- `App/app/host_i18n.py`, `App/app/host_vi_i18n.py` (Q10 keys)
- `App/app/templates/_property_editor.html`, `App/app/templates/setup_wizard/police.html` (IDUB label)
- `App/app/i18n.py`, `App/app/guest_uk_i18n.py`, `App/app/templates/guest/claim.html` (Q16)
- Tests that pin the old text: `App/tests/test_property_readiness.py`, `App/tests/test_operator_naming.py`, `App/tests/test_claim_copy.py`, `App/tests/test_claim_mail.py`, `App/tests/test_guest_browser_e2e.py`
- `docs/tasks/1076-report.md`, `docs/tasks/screenshots-1076/`

Do not touch: `housebook.py` (the PDF `"IDUB"` at lines 78 and 336), any route, SQL, `ubyport`/`soap` code, mail templates (their "variable symbol" lines go to payers and councils; out of scope), `onboarding.entity.title`, `property_create.managed_by`, `payments.setup.step.*`, `guest.css`, any other template line.

## 4. Steps

One step, one commit (`1076 step k`). Find every anchor with `grep -nF`; not found: STOP.

1. Anchor `app/host_i18n.py:4546` `"apartment.form.ubyport.idub_hint": "The police number of your accommodation (12–14 numbers). On the police letter it is the line “IDUB:”. Copy it exactly.",`. Replace the value with the en hint from section 2 and add the line `"apartment.form.ubyport.idub_label": "Police accommodation number (IDUB)",` right above it. Same in cs at `:5390` (`"apartment.form.ubyport.idub_hint": "Policejní číslo vašeho ubytování (12–14 číslic). V dopise od policie je to řádek „IDUB:“. Opište ho přesně.",`). In `host_vi_i18n.py:1908` do the same (key `"apartment.form.ubyport.idub_hint"`).
2. Same files, replace values only (anchors verbatim): `:4531` `"apartment.form.readiness.item.idub": 'IDUB',`; `:4532` `"apartment.form.readiness.item.mark": 'Facility abbreviation',`; `:4550` `"apartment.form.ubyport.mark_label": 'Facility abbreviation (zkratka)',`; `:4437` `"apartment.form.entity.label": 'Property manager / operator',`. cs: `:5375`, `:5376` (`'Zkratka zařízení'`), `:5394` (`'Zkratka ubytovacího zařízení'`), `:5281` (`'Správce objektu / provozovatel'`). vi (`host_vi_i18n.py`): `:1893`, `:1894`, `:1912`, `:1805`. Values from the section 2 table.
3. Same files: `:145` and `:151` `"stay_fees.metric.vs"` / `"stay_fees.payment.vs": "Variable symbol",` and `:1556` `"payments.qr.vs": "Variable symbol",` become "Payment reference (VS)". cs `:2291`, `:2297` (`"Variabilní symbol"`) and `:3694` (`"Variabilní symbol"`, keep the escape style) become "Variabilní symbol (VS)". vi stays.
4. `app/templates/_property_editor.html:311` anchor `{{ text_field('uby_idub', 'IDUB', apartment.uby_idub,`: replace `'IDUB'` with `t('apartment.form.ubyport.idub_label')`. Same in `app/templates/setup_wizard/police.html:33` (`{{ text_field('uby_idub', 'IDUB', values.uby_idub,`). Nothing else on those lines changes; `name`/`id` stay `uby_idub`.
5. Guest: add `"claim_email_why"` to `i18n.py` in all five dicts, next to `tw_email_short` (anchors `:138` en, `:893` cs, `:1634` de, `:2165` es, `:2696` fr, all `"tw_email_short": "..."`), and to `guest_uk_i18n.py` next to `:138`. Texts from section 2.
6. `app/templates/guest/claim.html:48` anchor `<div class="hint">{{ t('tw_email_short') }}</div>`: replace with `<div class="hint">{{ t('claim_email_why') }}</div>`. Keep the element, class and position. Before this step, run `grep -rn "door_code" app/claim.py app/mail*.py | tail -30` and confirm the claim mail or finish mail carries the door code; if it does not, STOP (Question 4).
7. Update the pinned tests, exact strings only: `test_property_readiness.py:197-198` (`Missing: Police accommodation number (IDUB)`, `Missing: Short name from the police`; line 276 uses the key, and `"IDUB"` there becomes the new key); `test_operator_naming.py:78` and `:245` (new operator label, en and cs); `test_claim_mail.py:216` (`"We send your door code and receipt here"`); `test_claim_copy.py:36-39` stays (the key still exists) and gains a `claim_email_why` entry with the en and cs texts; `test_guest_browser_e2e.py:696` (`"Variable symbol"` to `"Payment reference (VS)"`). If a further test pins old text, fix it the same way and list it in the report.
8. Payload check, run unedited: the filing row of the test-map (section 6). Nothing in it may need an edit; if one does, STOP.
9. Screenshots (390, 768, 1280) of every changed page into `docs/tasks/screenshots-1076/`: property editor police section, setup wizard police step, stay fee page, stay fee detail, payments QR page, guest claim (e-mail) screen. Use the layout-lint shots if the page is in `tests/test_layout_lint_browser.py` (`grep -n` the page names); otherwise take them with the existing browser test helper and say so. Open each once and write one line per page in the report.

## 5. Do not touch

Layout, CSS, field order, `name` and `id` attributes, validation, stored values, any `uby_*` column, any SQL, any new dependency, any other copy.

## 6. Commands (from `App/`; each ends with `2>&1 | tail -30`)

- Copy: `.venv/bin/python -m pytest tests/test_*_i18n.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py tests/test_flash_literals.py -q --tb=short -x`
- Filing and claim: `.venv/bin/python -m pytest tests/test_ubyport_*.py tests/test_soap.py tests/test_submission_*.py tests/test_police_*.py tests/test_claim_*.py -q --tb=short -x`
- Guest: `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_guest_*.py tests/test_guest_browser_e2e.py -q -rs --tb=short -x` (0 skipped)
- Host: `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_host_*.py tests/test_host_geometry.py tests/test_design_guardrails_browser.py -q -rs --tb=short -x` (0 skipped)
- Rows also changed: `tests/test_property_*.py tests/test_onboarding*.py tests/test_first_*.py tests/test_operator_naming.py`, `tests/test_stay_fee*.py tests/test_invoice_*.py`, `tests/test_payment_qr.py tests/test_payments_dashboard.py`
- UX gate: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -rs -x`, then copy the shots of the changed pages
- Repo root: `python3 scripts/context_lint.py | tail -5`

## 7. Acceptance

- [ ] Section 2 keys changed in en, cs, vi; `claim_email_why` exists in en, cs, de, es, fr, uk.
- [ ] `git diff --stat origin/main` shows only the files in section 3; no `.css`, no route, no SQL.
- [ ] Filing and claim row green, no filing test edited.
- [ ] Guest and host browser and geometry tests green, 0 skipped; layout lint green.
- [ ] Screenshots at 390/768/1280 of each page in step 9 are in `docs/tasks/screenshots-1076/`; the guest claim screen looks the same as before except the hint text.
- [ ] `grep -rn "we send your door code" -i App/app/templates | tail -5` finds nothing hard-coded (copy comes from i18n).

## 8. Stop and ask

An anchor not found; a filing test needs an edit; a test outside section 3 fails twice; the door code is not mailed (step 6); the new hint wraps to a third line at 390 px.

## 9. Report

`docs/tasks/1076-report.md`, 600 tokens at most: files changed, each command with its last 5 lines, section 7 ticked, one line per page seen, deviations, questions. Then set `Status: review` and open one PR.

## Questions for the owner (not decided here)

1. Q10 says "Ready to take payments" for "live". `payments.setup.step.live` already says "Take card payments", and the other "live" labels are `bsite.list.live` ("Live", booking site) and `ops.ttlock.live`. Should "Take card payments" become "Ready to take payments", should a different "live" label change, or should this item be dropped?
2. The operator label: change only the property form (`apartment.form.entity.label`, as in this brief), or also `onboarding.entity.title` ("Operator") and `property_create.managed_by` ("Managed by")? Today's "Property manager / operator" was set on purpose in 0088 and is pinned by `test_operator_naming.py`.
3. The e-mail line keeps "No marketing." from the old hint. After this change `claim_email_help` (inside the "?" fold) also mentions the receipt; trim that sentence in a later brief?

## Owner steps

None for the brief. After merge and deploy, nothing to configure.
