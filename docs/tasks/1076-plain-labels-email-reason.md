# 1076: Plain labels near filing (Q10) and one reason line on the guest e-mail screen (Q16, S9)

Status: review
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
- "Ready to take payments" for "live": dropped (orchestrator, 2026-11-10). `payments.setup.step.live` already reads "Take card payments"; nothing changes.
- Operator label: only `apartment.form.entity.label` changes (orchestrator). `onboarding.entity.title` and `property_create.managed_by` were set on purpose in 0088 and stay.
- "Payment reference (VS)": host keys `stay_fees.metric.vs`, `stay_fees.payment.vs`, `payments.qr.vs` ("Variable symbol"). The guest key `fee_vs_label` (`i18n.py`, also "Variable symbol") is a guest page and stays.

Proposed copy (write the cs and vi lines as drafts; the owner reads them in review):

| Key | en | cs | vi |
|---|---|---|---|
| `apartment.form.ubyport.idub_label` (new) | Police accommodation number (IDUB) | Policejní číslo ubytování (IDUB) | Số cơ sở lưu trú của cảnh sát (IDUB) |
| `apartment.form.readiness.item.idub` | Police accommodation number (IDUB) | Policejní číslo ubytování (IDUB) | Số cơ sở lưu trú của cảnh sát (IDUB) |
| `apartment.form.ubyport.mark_label` | Short name from the police (zkratka) | Krátký název od policie (zkratka) | Tên viết tắt từ cảnh sát (zkratka) |
| `apartment.form.readiness.item.mark` | Short name from the police | Krátký název od policie | Tên viết tắt từ cảnh sát |
| `apartment.form.entity.label` | Who runs the accommodation | Kdo ubytování provozuje | Ai vận hành chỗ lưu trú |
| `stay_fees.metric.vs`, `stay_fees.payment.vs`, `payments.qr.vs` | Payment reference (VS) | Variabilní symbol (VS) | unchanged (`stay_fees.*` already read "Mã VS (variabilní symbol)"; `payments.qr.vs` has no vi line, add none) |
| `apartment.form.ubyport.idub_hint` | 12 to 14 numbers. On the police letter it is the line "IDUB:". Copy it exactly. | 12 až 14 číslic. V dopise od policie je to řádek „IDUB:“. Opište ho přesně. | 12 đến 14 chữ số. Trên thư của cảnh sát, đó là dòng “IDUB:”. Sao chép chính xác. |

The hint loses its first sentence because the new label now says it (rule 9). Keep each language's existing typographic quotes.

Guest e-mail line, new key `claim_email_why`, replacing the hint on the claim screen only (`tw_email_short` stays; `assigned.html:37` still uses it). It keeps "private link": DESIGN.md:673 requires the claim link to be explained at collection and `test_claim_copy.py` guards it. `claim_email_help` is not trimmed (orchestrator), so the claim word budget in that test rises (step 7). Checked: the door code is mailed (`mail_notify.py:1717`, key `mail_door_code_subject`).

| Lang | Text |
|---|---|
| en | We send your private link and receipt here, and it keeps this booking yours. No marketing. |
| cs | Pošleme sem soukromý odkaz a potvrzení a díky e-mailu zůstane tato rezervace vaše. Žádný marketing. |
| de | Hierhin senden wir Ihren privaten Link und die Bestätigung. So bleibt diese Buchung Ihre. Kein Marketing. |
| es | Aquí le enviamos su enlace privado y el justificante. Así esta reserva sigue siendo suya. Sin publicidad. |
| fr | Nous y envoyons votre lien privé et votre récapitulatif. Ainsi, cette réservation reste la vôtre. Pas de marketing. |
| uk | Сюди ми надішлемо ваше особисте посилання і підтвердження, і так це бронювання залишається вашим. Жодної реклами. |

## 3. Files

- `App/app/host_i18n.py`, `App/app/host_vi_i18n.py` (Q10 keys)
- `App/app/templates/_property_editor.html`, `App/app/templates/setup_wizard/police.html` (IDUB label)
- `App/app/i18n.py`, `App/app/guest_uk_i18n.py`, `App/app/templates/guest/claim.html` (Q16)
- Tests that pin the old text: `App/tests/test_property_readiness.py`, `App/tests/test_operator_naming.py`, `App/tests/test_claim_copy.py`, `App/tests/test_claim_mail.py`, `App/tests/test_property_navigation_browser.py`
- `docs/tasks/1076-report.md`, `docs/tasks/screenshots-1076/`

Do not touch: `housebook.py` (the PDF `"IDUB"` at lines 78 and 336), any route, SQL, `ubyport`/`soap` code, mail templates (their "variable symbol" lines go to payers and councils; out of scope), `onboarding.entity.title`, `property_create.managed_by`, `payments.setup.step.*`, `claim_email_help`, `tw_email_short`, `fee_vs_label`, `templates/guest/archive/`, `guest.css`, any other template line.

## 4. Steps

One step, one commit (`1076 step k`). Paths are under `App/`. Find every anchor with `grep -nF`; not found: STOP. Line numbers are those at the base commit and move by one after each added line. A host key matches twice in `host_i18n.py`: the first hit is en, the second cs.

1. Anchor `app/host_i18n.py:4546` `"apartment.form.ubyport.idub_hint": "The police number of your accommodation (12–14 numbers). On the police letter it is the line “IDUB:”. Copy it exactly.",`. Replace the value with the en hint from section 2 and add the line `"apartment.form.ubyport.idub_label": "Police accommodation number (IDUB)",` right above it. Same in cs at `:5390` (`"apartment.form.ubyport.idub_hint": "Policejní číslo vašeho ubytování (12–14 číslic). V dopise od policie je to řádek „IDUB:“. Opište ho přesně.",`). In `host_vi_i18n.py:1908` do the same (key `"apartment.form.ubyport.idub_hint"`).
2. Same files, replace values only (anchors verbatim): `:4531` `"apartment.form.readiness.item.idub": 'IDUB',`; `:4532` `"apartment.form.readiness.item.mark": 'Facility abbreviation',`; `:4550` `"apartment.form.ubyport.mark_label": 'Facility abbreviation (zkratka)',`; `:4437` `"apartment.form.entity.label": 'Property manager / operator',`. cs: `:5375`, `:5376` (`'Zkratka zařízení'`), `:5394` (`'Zkratka ubytovacího zařízení'`), `:5281` (`'Správce objektu / provozovatel'`). vi (`host_vi_i18n.py`): `:1893`, `:1894`, `:1912`, `:1805`. Values from the section 2 table.
3. Same files: `:145` and `:151` `"stay_fees.metric.vs"` / `"stay_fees.payment.vs": "Variable symbol",` and `:1556` `"payments.qr.vs": "Variable symbol",` become "Payment reference (VS)". cs `:2291`, `:2297` (`"Variabilní symbol"`) and `:3694` (anchor `"payments.qr.vs": "Variabiln\u00ed symbol",`, new value `"Variabiln\u00ed symbol (VS)"`) become "Variabilní symbol (VS)". vi stays.
4. `app/templates/_property_editor.html:311` anchor `{{ text_field('uby_idub', 'IDUB', apartment.uby_idub,`: replace `'IDUB'` with `t('apartment.form.ubyport.idub_label')`. Same in `app/templates/setup_wizard/police.html:33` (`{{ text_field('uby_idub', 'IDUB', values.uby_idub,`). Nothing else on those lines changes; `name`/`id` stay `uby_idub`.
5. Guest: add `"claim_email_why"` to `i18n.py` in all five dicts, next to `tw_email_short` (`grep -nF '"tw_email_short"' app/i18n.py` gives five hits in the order en `:138`, cs `:893`, de `:1634`, es `:2165`, fr `:2696`; add the new line right below each), and to `guest_uk_i18n.py` below `:138`. Texts from section 2. Leave every `tw_email_short` line as it is.
6. `app/templates/guest/claim.html:48` anchor `<div class="hint">{{ t('tw_email_short') }}</div>`: replace with `<div class="hint">{{ t('claim_email_why') }}</div>`. Keep the element, class and position. Do not edit `templates/guest/archive/ticket-wallet/claim.html` or `assigned.html`.
7. Update the pinned tests, exact strings only:
   - `tests/test_property_readiness.py`: `:197` and `:234` `"Missing: IDUB"` become `"Missing: Police accommodation number (IDUB)"`; `:198` becomes `"Missing: Short name from the police"`; `:260` `("uby_idub", None, "text"),` becomes `("uby_idub", "apartment.form.ubyport.idub_label", "text"),` (line 276 stays).
   - `tests/test_property_navigation_browser.py:654` and `:778`: `"Missing: IDUB"` becomes `"Missing: Police accommodation number (IDUB)"`.
   - `tests/test_operator_naming.py:78` (`"Who runs the accommodation", "Kdo ubytování provozuje"`) and `:245` (en).
   - `tests/test_claim_mail.py:216`: `"We send your private link and receipt here"`.
   - `tests/test_claim_copy.py`: keep the `tw_email_short` entry of `AUDIT_COPY` and add a `"claim_email_why"` entry with the en and cs texts; in `CLAIM_HINT_KEYS` (`:57`) replace `"tw_email_short"` with `"claim_email_why"`; in the word-budget test change `(("en", 55), ("cs", 50))` to the measured new counts, at most `(("en", 58), ("cs", 55))` (stop and report if more is needed) and add the comment `# 1076: the e-mail line now says why (Q16)`. Line 125 (assigned screen) stays.
   - `tests/test_guest_browser_e2e.py:696` stays: it reads the guest key `fee_vs_label`.
   If a further test pins old text, fix it the same way and list it in the report. A filing test: STOP.
8. Payload check, run unedited: the filing row of the test-map (section 6). Nothing in it may need an edit; if one does, STOP.
9. Screenshots at 390, 768 and 1280 of every changed page into `docs/tasks/screenshots-1076/`: property editor police section, setup wizard police step, stay fees list, stay fee detail, payments QR page, guest claim screen. Run the UX gate command (section 6), then `ls -R /tmp/shots | grep -iE "propert|wizard|police|stay-fee|qr|claim" | head -50` and copy the matching files. Write no screenshot code. A page with no file: list it under Deviations as `no screenshot: <page>`; the reviewer takes it. Open each copied file once and write one line per page in the report: what you saw, and for the claim screen how many lines the hint takes at 390 px.

## 5. Do not touch

Layout, CSS, field order, `name` and `id` attributes, validation, stored values, any `uby_*` column, any SQL, any new dependency, any other copy.

## 6. Commands (from `App/`; each ends with `2>&1 | tail -30`)

- Copy: `.venv/bin/python -m pytest tests/test_*_i18n.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py tests/test_flash_literals.py tests/test_flash_next_step.py tests/test_reporting_help_0097.py -q --tb=short -x`
- Filing and claim (whole test-map row): `.venv/bin/python -m pytest tests/test_ubyport_*.py tests/test_soap.py tests/test_worker.py tests/test_submission_*.py tests/test_stale_submission.py tests/test_filed_by_hand.py tests/test_filing_watchdog.py tests/test_police_*.py tests/test_deadline*.py tests/test_claim_*.py tests/test_endtoend.py -q --tb=short -x`
- Guest: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_guest_*.py -q -rs --tb=short -x` (0 skipped)
- Host: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_host_*.py tests/test_design_guardrails_browser.py -q -rs --tb=short -x` (0 skipped; the glob includes `test_host_geometry.py`)
- Properties, stay fee, payments: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_property_*.py tests/test_onboarding*.py tests/test_first_*.py tests/test_operator_naming.py tests/test_stay_fee*.py tests/test_invoice_*.py tests/test_payment_*.py tests/test_payments*.py -q -rs --tb=short -x` (0 skipped)
- UX gate: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -rs --tb=short -x` (0 skipped; shots land in `/tmp/shots/layout-lint`)
- Repo root: `python3 scripts/context_lint.py | tail -5`

## 7. Acceptance

- [ ] Section 2 keys changed in en, cs, vi; `claim_email_why` exists in en, cs, de, es, fr, uk; `git diff origin/main -- App/app | grep -c '^[-+].*\(tw_email_short\|claim_email_help\|fee_vs_label\)'` prints 0.
- [ ] `git diff --stat origin/main` shows only the files in section 3; no `.css`, no route, no SQL.
- [ ] Filing and claim row green, no filing test edited.
- [ ] Guest and host browser and geometry tests green, 0 skipped; layout lint green.
- [ ] Screenshots at 390/768/1280 of each page in step 9 are in `docs/tasks/screenshots-1076/`; the guest claim screen looks the same as before except the hint text.
- [ ] `grep -rn "private link and receipt here" -i App/app/templates | tail -5` finds nothing hard-coded (copy comes from i18n).

## 8. Stop and ask

An anchor not found; a filing test needs an edit; a test outside section 3 fails twice; a geometry or layout-lint finding on a changed page (never silence it, never add an allow-list line).

## 9. Report

`docs/tasks/1076-report.md`, 600 tokens at most: files changed, each command with its last 5 lines, section 7 ticked, one line per page seen, deviations, questions, and a `Follow-ups` list with these three lines: (1) `claim_email_help` also mentions the receipt; a later brief may trim it; (2) the claim line leaves out the door code on purpose (not every property has a smart lock); (3) `stay_fees.payment.vs_hint` still says "this symbol" next to the new label. Tick the [design-system checklist](../design/design-system.md) in the PR (rule 10). Then set `Status: review` and open one PR.

## Owner steps

None for the brief. After merge and deploy, nothing to configure.
