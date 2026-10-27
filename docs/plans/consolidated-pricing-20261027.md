# Consolidated UbyHost pricing — implementation brief

Status: todo
Owner request: 2026-10-27
Executor: Haiku 5.5. Assign the next free task number using scripts/context_lint.py before execution; copy this brief to docs/tasks/NNNN-consolidated-pricing.md and use task/NNNN-consolidated-pricing.
Depends on: 0412 and 0416 already present on main. This pricing work must be coordinated with the self-service signup and billing plan in docs/plans/self-service-admin-20261027.md. Check other open briefs for overlapping files before execution.

## 1. Objective

Make /cenik one complete pricing decision: billing period, apartment count, two aligned plans, volume discounts and relevant add-ons together. Premium presentation, accessible prices and honest savings; remove the founding-host promotion for now.

## 2. Evidence and anchors

Read AGENTS.md and docs/context/executor.md. Light mode, existing tokens, no new dependencies, no shadows on pricing cards, no third-party requests, no tracking changes. No main push, merge or deploy. This is public marketing UI, not a billing-engine redesign.

Verified on main on 2026-10-27:

- App/app/templates/pricing.html places the TTLock checkbox in .pricing-calc above both plans; the founder strip follows the cards; separate bands and add-ons sections follow farther down.
- Exact template anchor:
  <label class="pricing-ttlock"><input type="checkbox" data-ttlock>{{ t('pricing.ttlock.label') }}</label>
- Exact script anchor, App/app/static/pricing.js:
  calc.querySelector("[data-ttlock]").addEventListener("change", function (event) {
- Exact header anchor:
  <div class="pricing-card-head">
- Existing card identity and total hooks: [data-plan="standard"], [data-plan="max"], [data-total], [data-sub], [data-apts], [data-note], [data-cta-plan].
- Existing calculation, preserve:
  standard annual = graduated(n, rates.base.year) + (ttlock ? rates.ttlock.year * n : 0);
  Max annual = graduated(n, rates.base.year) + graduated(n, rates.max.year).
- App/app/routes/legal.py builds PUBLIC_RATES from billing.BASE, billing.MAX_EXTRA and billing.TTLOCK.
- Read-only canonical rates from App/app/billing.py:
  BASE month (149,119,99), year (1190,950,790);
  MAX_EXTRA month (79,59,39), year (760,570,370);
  TTLOCK month 49, year 470;
  WHITELABEL month 590, year 5660.
- Existing English copy:
  "pricing.max.badge": "Only here: AI concierge",
  "pricing.max.f2": "3× more answers from Leon and Havel",
  "pricing.addon.wl.body": "Your logo and colours for guests and owners. +590 CZK a month."
- Existing browser test App/tests/test_0412_pricing_browser.py verifies annual 99/163, five apartments 476, monthly 715/1090, and standard monthly with TTLock 960.

If an anchor changed, stop and report rather than overwrite newer work.

## 3. Files

| Path | Action | Purpose |
|---|---|---|
| App/app/templates/pricing.html | edit | Consolidate the pricing area; remove founder promotion and distant duplicate bands/add-ons sections |
| App/app/static/landing.css | edit | Page-scoped responsive shared rows, compact tiers and options |
| App/app/static/pricing.js | edit | Relocate checkbox binding; update all interval-dependent disclosures and savings |
| App/app/landing_i18n.py | edit pricing keys only | Matching Czech and English copy |
| App/app/routes/legal.py | edit PUBLIC_RATES/start only | Add white-label rates from billing.WHITELABEL and server-rendered annual add-on values |
| App/tests/test_0412_pricing_browser.py | edit | Pricing interactions, alignment and screenshots |
| App/tests/test_public_seo.py | edit existing pricing assertions only if needed | Updated visible structure and truthful server fallback |
| App/tests/test_landing_decoration.py | edit existing pricing assertions only if needed | Preserve design restrictions |
| App/tests/test_owner_decisions.py | edit existing pricing assertions only if needed | Updated owner-requested presentation |
| App/tests/static_versions.json | regenerate relevant entries | Match changed assets and version references |
| App/app/templates/landing.html | cache reference only | landing.css version |
| App/app/templates/product.html | cache reference only | landing.css version |
| App/app/templates/public_guide.html | cache reference only | landing.css version |
| App/app/templates/public_legal_base.html | cache reference only | landing.css version |
| docs/tasks/NNNN-consolidated-pricing.md | create/update | Assigned execution brief and status |
| docs/tasks/NNNN-report.md | create | Evidence and owner steps |
| docs/tasks/screenshots-NNNN/cenik-cs-390.png | create | Mobile evidence |
| docs/tasks/screenshots-NNNN/cenik-en-390.png | create | Mobile evidence |
| docs/tasks/screenshots-NNNN/cenik-en-1280.png | create | Desktop evidence |

No other files may change without stopping. Read only relevant ranges in large files. App/app/billing.py is a read-only source of rates. Use existing static-version workflow; if further template references require updates, report the exact paths.

## 4. Steps and prescribed design

1. Put the entire decision area immediately below a compact hero. English headline: "Less admin. More hosting." Czech: "Méně papírování. Více času na hosty." Keep one concise explanation: guests check in, UbyPort receives the report, host receives the receipt; pricing is per apartment. Keep existing 30-day/no-card/cancel terms. State in both languages that the trial starts when the host creates and verifies the account; do not say it starts on UbyPort connection. Coordinate with the self-service plan; do not release this copy until the implementation matches it. Reduce only .pricing-page hero/section spacing so controls and prices appear sooner. Verify both languages visually; no unrelated landing-page redesign.

2. Shared controls: annual/monthly toggle and apartment stepper, retaining the existing 1–50 bounds and accessible button labels. No global TTLock checkbox. Immediately under these controls, show a compact full-width volume-pricing strip using existing band labels and data-band/data-unit hooks. Label it "UbyHost base price" / "Základní cena UbyHost"; make clear it is the base included in both plans, with Max's extra reflected in its card total. Three cells: apartments 1–4, 5–9, 10+. English explanation: "Lower rates apply from your 5th and 10th apartment. Each rate applies only to apartments in that band." Czech: "Od 5. a 10. apartmánu platí nižší sazba. Každá sazba se vztahuje jen na apartmány v daném pásmu." Annual visible rates 99/79/66 and monthly 149/119/99. Annual cells explicitly say billed annually; do not suggest all apartments switch to the cheapest rate. Wrap into three compact rows on narrow screens. Verify with data-band values after toggling.

3. Two cards: UbyHost and UbyHost Max. Display equal-level names, benefit-led taglines, total monthly equivalent, annual invoice amount or monthly billing explanation, selected apartment count, then aligned trial CTAs, then feature list and plan options. Use a desktop grid with intrinsic shared rows via CSS subgrid (or equivalent measured alignment); do not use arbitrary fixed card/header heights. Reserve shared rows for heading, price, billing disclosure, apartment metadata and CTA. At single-column widths use natural document flow. Ensure long translations and larger totals never displace one CTA relative to the other. Put the concise Max badge on its own line/row, so it cannot squeeze the heading. Label badge "More AI answers" / "Více AI odpovědí". Do not use "Only here", fabricated popularity or urgency. Keep the existing warm canvas, white cards, restrained coral Max border, crisp typography, tabular price digits, generous internal padding and pill buttons. No animated counters or decorative gradients.

4. Make AI understandable where the features appear. Standard English feature text: "Leon, your AI guest assistant, answers guests 24/7." Czech: "Leon, AI asistent pro hosty, odpovídá nepřetržitě." Introduce Havel once nearby: English "Havel is your AI assistant for using UbyHost." Czech "Havel je váš AI pomocník pro práci s UbyHost." Max feature: English "3× the AI answer allowance for guest and host assistants." Czech "3× vyšší limit AI odpovědí pro hosty i ubytovatele." Keep claims within existing capabilities. Both tiers already have AI; Max offers higher limits. Avoid implying unlimited AI, autonomous property management or new guest-facing capabilities. Use existing six/five feature structure unless the single Havel explanation needs one concise helper line.

5. In the standard card, below features, put a softly tinted option panel containing the existing data-ttlock checkbox and its label, "I have TTLock smart locks" / existing Czech equivalent. Helper: "Create a door code for each stay." / "Vytvořte kód ke dveřím pro každý pobyt." Show +39 CZK per apartment per month billed annually, with the exact +470 CZK per apartment per year; monthly selection shows +49 CZK per apartment per month. Derive these from rates and existing rounding, not literals. Max's corresponding option panel says "TTLock included" / "TTLock v ceně", with no second checkbox or charge. Change the event-binding lookup from calc.querySelector to the standard card's checkbox and guard against missing nodes. Preserve totals(), graduated(), and the CTA query conventions; standard alone gets ttlock=1. Show a small clear "Included in the total" state when selected. The option must remain understandable without JS; keep interactive controls hidden/disabled until initialized, while server-rendered price disclosures remain visible.

6. Directly beneath the cards, within the same pricing section, put one compact agency add-on row using the existing white-label concept. English: "Your brand, throughout" and "Your logo and colours for guests and owners." Czech: "Všude pod vaší značkou" and "Vaše logo a barvy pro hosty i majitele." Annual price = 5660/12 rounded to 472 CZK/month, exact 5660 CZK/year alongside it; monthly = 590 CZK/month. Explicitly label account-wide, not per apartment. Read rates from billing.WHITELABEL through PUBLIC_RATES and use server-rendered annual fallback. This is an informational disclosure, not a checkbox: the current public calculator and signup handoff do not select white-label. Keep it clearly described as an optional extra excluded from the displayed plan total, with the existing support contact if customers want it. Do not introduce a nonfunctional selection or silently add this fee to either plan.

7. Remove the entire conditional .pricing-founder rendered block from /cenik and its promotional CTA. Remove the separate later bands and add-ons sections after relocating their content; preserve FAQ and value sections. Do not delete founder billing/account data or change existing contracts. The separate self-service plan must also disable automatic founder offers for new orders. Search this page's FAQs and rendered output for founder promotion; hide any remaining promotion for this page. Preserve FAQ JSON-LD correspondence if a question is removed. The separate self-service plan covers checkout/billing changes.

8. Keep totals prominent and billing honest. Under each total, show exact annual charge when annual is selected. State that the large number is the total for the selected apartments, not a per-apartment quote. Base tier strip always explains marginal per-apartment rates separately. For a savings disclosure, calculate each plan's annual saving against the same plan/apartment count/add-on choices paid monthly: monthly_total*12 - annual_total. Never multiply rounded display rates to make annual invoices. Existing 33% badge is only accurate for standard base; replace the global badge with "Lower yearly price" / "Výhodnější roční platba", and display exact plan-specific savings if space permits. No new price cuts or unapproved rate changes.

9. Update all matching Czech/English pricing keys, asset query versions and relevant static manifest hashes. Preserve no-JS annual one-apartment rendering: standard 99, billed 1190; Max 163, billed 1950. Do not hide important price information behind JS, hover, accordions or links. Keep the CTA destination fallback when signup is disabled. Retain analytics behavior.

After each step run its scoped verification from §6, or for copy/layout steps inspect the resulting rendered page and record the visible fact. Before App edits confirm the allocated brief Status is todo, then set in-progress.

## 5. Do not touch

Do not change billing.BASE, MAX_EXTRA, TTLOCK, WHITELABEL, founder eligibility/slots, checkout, plan entitlements, AI limits, payment processing, auth, migrations, reporting, UbyPort, guest data, trackers or deployment configuration. No new dependency. No wholesale translation-file rewrite. No production deploy or merge.

## 6. Commands and expected results

Run from repo root first:
- python3 scripts/context_lint.py 2>&1 | tail -30
  Record next free number and any pre-existing lint issues. Do not guess a task number or overwrite an existing task.

From App, public pages test-map row:
- .venv/bin/python -m pytest tests/test_public_*.py tests/test_legal_*.py tests/test_landing_*.py tests/test_terms_copy.py tests/test_wp24_terms_dpa.py -q --tb=short -x 2>&1 | tail -30
- UBYHOST_REQUIRE_BROWSER=1 UBYHOST_CAPTURE_0412=1 .venv/bin/python -m pytest tests/test_0412_pricing_browser.py -q --tb=short -x 2>&1 | tail -30
- .venv/bin/python -m pytest tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py tests/test_owner_decisions.py -q --tb=short -x 2>&1 | tail -30
- .venv/bin/python -m pytest tests/test_*_i18n.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py tests/test_flash_literals.py -q --tb=short -x 2>&1 | tail -30

Update capture path in existing browser test to screenshots-NNNN and capture both languages. Required browser checks must have zero skips; install existing required browsers rather than converting a failure to a skip. Do not run the whole test suite. From root at the end, run context_lint.py again and report the result honestly.

Extend the existing browser coverage, using its live-server fixture:
- English and Czech, desktop 1280 and 1024, mobile 390 and 360.
- At two-card widths, compare trial button top and bottom bounding boxes with tolerance <=1px, including after TTLock selection, monthly toggle and counts 1,4,5,9,10,50.
- At all widths assert document scrollWidth <= innerWidth+1.
- TTLock checkbox exists only inside [data-plan="standard"]; its selection changes standard total and standard signup URL only; Max total and URL stay unchanged.
- Count=1 annual 99/163, invoice 1190/1950. Standard annual with TTLock 138 (1660/year).
- Count=5 annual standard 476 (5710/year); monthly standard/Max 715/1090; standard+TTLock monthly 960.
- Count=10 annual standard 858 (10300/year); monthly standard 1290.
- Tier strip annual 99/79/66 and monthly 149/119/99.
- White-label disclosure annual 472/month and 5660/year; monthly 590, clearly account-wide and excluded.
- All informational tiers and add-on prices are in .pricing-plans-section; no duplicate distant section and no founder promotion, including when founder slots are available.
- No-JS page still exposes valid annual starting prices, billing amounts, tiers, AI explanations and add-on disclosures.
- Keyboard-operable controls, visible focus, >=44px control targets, associated labels and no page errors.
- Signup links retain current interval/apartment/TTLock choices and disabled-signup fallback.
- Save one 390px screenshot per language and a 1280px screenshot after verifying button geometry. View them before reporting.

## 7. Acceptance

- [ ] Prices, discount tiers and add-ons form one contiguous decision area.
- [ ] Desktop CTAs align under both languages, all counts and billing selections.
- [ ] TTLock belongs only to the standard card; Max includes it.
- [ ] Leon and Havel are explained in plain language; Max no longer claims exclusive AI.
- [ ] Founder offer is absent from the public pricing page.
- [ ] Every visible price follows selected billing period and canonical rates.
- [ ] Rounded monthly equivalents never replace exact annual invoice disclosures.
- [ ] White-label fee is account-wide and clearly excluded from plan totals.
- [ ] Trial promise and signup handoff remain valid.
- [ ] Required checks pass, browser checks have zero skips, screenshot evidence is viewed.
- [ ] No unrelated App or billing-engine changes.

## 8. Stop and ask

Stop and write the report if an anchor changed, another active brief owns the same files, a new dependency or unnamed file is needed, a check fails twice, rate source disagrees, AI capability wording cannot be substantiated, or the session reaches the executor limit. Never fix failing tests by weakening the visible behavior required here.

## 9. Report and owner steps

Write docs/tasks/NNNN-report.md in <=600 tokens: changed-file stat, each command's last five lines, checklist, screenshot paths, deviations and owner steps. Mark review only after implementation; do not mark this design brief as implemented.

Owner:
1. Run this brief in a Haiku 5.5 session.
2. Review the implementation PR, passing CI and desktop/mobile screenshots.
3. Merge only with the repository's merge-pr-on-green script; deploy manually.
4. Check /cenik in both languages on phone and desktop.

Risk list: pricing.html, pricing.js, landing_i18n.py pricing keys, PUBLIC_RATES/start edits, pricing CSS and changed assertions.

## Preparation limitation

This brief was prepared via connected GitHub read tools. The managed execution environment failed to start with "managed network requirements require sandbox enforcement". No App files were changed and no tests, context lint or browser screenshots were run during preparation.