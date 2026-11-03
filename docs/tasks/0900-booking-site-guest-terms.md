# 0900: Booking site guest terms (CS + EN page, linked from checkout)

Status: todo
Depends on: 0818 to 0822 merged (#736) | Base commit: tip of origin/main | Branch: `task/0900-booking-site-guest-terms`
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (run steps 1-3, then 4-6)

## 1. Objective

The checkout box on `/p/<slug>` has a "I agree to the booking terms" tickbox but nothing to read. Add a public page `GET /terms/booking` (Czech first, `?lang=cs|en`, no cookie set) with the terms below, and a link to it under the tickbox. Bump `TERMS_VERSION` so open pages must reload.

## 2. Context

- Route file `App/app/routes/property_page.py`; reuse `_page_lang(request)` (line ~64). Declare the new route above `/p/{slug}`-style routes (the path `/terms/booking` does not collide with `/p/...`).
- Template: new `App/app/templates/booking_terms.html`, `{% extends "base.html" %}`, `show_nav` false like `booking_manage.html`, `<meta name="robots" content="noindex">`, include `_pp_booking_css.html`, wrap in `<main class="pp-bk pp-bk-page">`. Body text lives in two partials `_booking_terms_cs.html` and `_booking_terms_en.html` (plain `<h2>`/`<p>`/`<ol>`; no `<style>`, no inline style, no JS). Include one by `lang`. A small CS / EN switch link at the top like the one on `booking_manage.html`.
- Checkout link: in `property_page.html` right after the terms `<label class="ui-check">` (line ~123) add `<p class="pp-bk-note"><a href="/terms/booking?lang={{ lang }}" target="_blank" rel="noopener">{{ t('pp.book.terms_read') }}</a></p>`. Add keys `pp.book.terms_read` to BOTH language blocks of `App/app/host_i18n.py` (EN "Read the booking terms", CS "Přečíst podmínky rezervace"), next to `pp.book.terms`. The link needs a 44 px tap height at 390 px: reuse an existing class from `_pp_booking_css.html` if one fits, otherwise add `min-height:44px;display:inline-flex;align-items:center` to a rule inside `_pp_booking_css.html` only.
- `App/app/booking_site.py`: `TERMS_VERSION = "2026-11-03"`. grep tests for the old value `2026-11-01` and update only literal expectations.
- Rules: light mode, works without JavaScript, copy rule "no tracking cookies" never "no cookies" (the terms say so in section 9). No new dependency.

## 3. Steps

1. Create the two partials from section 5 verbatim (CS and EN), the template and the route (200, `lang` attribute follows the language, `X-Robots-Tag` not needed).
2. Add the checkout link and the two i18n keys; bump `TERMS_VERSION`.
3. Tests, new file `App/tests/test_booking_terms.py`: (a) GET `/terms/booking` 200 contains "Podmínky rezervace" by default; (b) `?lang=en` 200 contains "Booking terms" and sets no `Set-Cookie`; (c) the checkout page of a published site contains `href="/terms/booking?lang=cs"`; (d) the terms mention all three policy names in both languages (Nevratná / Non-refundable, Flexibilní / Flexible, Střední / Moderate). Reuse the fixtures of `tests/test_booking_site.py` for (c).
4. Run from `App/`: `.venv/bin/python -m pytest tests/test_booking_terms.py tests/test_booking_site.py tests/test_host_i18n.py tests/test_flash_literals.py tests/test_static_versions.py -q --tb=short -x 2>&1 | tail -30` (run `test_host_i18n.py` together with `test_booking_site.py`, never alone).
5. Template change, so the browser rule applies: write `App/tests/test_booking_terms_browser.py` (mirror `test_booking_manage_browser.py`): page loads at 390 px, no horizontal scroll, first `<h1>` visible, the CS/EN switch link has height >= 44. Run it, 0 skipped. Save one 390 px screenshot of `/terms/booking` to `docs/tasks/screenshots-0900/terms-390.png`.
6. `python3 scripts/context_lint.py | tail -30`; append to `docs/context/decisions.md` one line `- 2026-11-03 | Booking terms: own text modeled on marketplace guest terms (structure only), CS+EN, /terms/booking, versioned | owner | 0900` (shorten an older line if the lint cap is hit). Write `docs/tasks/0900-report.md` (Status: review, files changed, test tails, deviations). `git add` named files only, never `git add -A`.

## 4. Do not

Touch other templates, CSS files or the checkout logic; add a dependency; copy text from any third-party terms.

## 5. Text (verbatim; HTML structure is yours, wording is not)

### Czech (`_booking_terms_cs.html`)

h1: Podmínky rezervace

Úvod (p): Tyto podmínky platí pro rezervace ubytování zaplacené kartou na stránce ubytovatele provozované přes UbyHost. Prosíme, přečtěte si je před platbou. Verze 3. 11. 2026.

1. **Kdo je kdo.** Smlouvu o ubytování uzavíráte s ubytovatelem, jehož jméno a údaje najdete na faktuře. UbyHost poskytuje jen technický nástroj pro rezervaci a platbu; není stranou smlouvy o ubytování, nevystupuje jako zprostředkovatel ubytování a za samotný pobyt neodpovídá.
2. **Uzavření rezervace.** Rezervace je závazná v okamžiku, kdy platba projde a my vám pošleme potvrzení na uvedený e-mail. Do té doby termín držíme jen krátce; pokud platba neproběhne, rezervace zanikne. Rezervovat může osoba starší 18 let, která uvede pravdivé údaje a počet hostů nepřesahující kapacitu ubytování.
3. **Cena a platba.** Cena v korunách zahrnuje ubytování a jednorázový úklid, jak je uvedeno před platbou. Městský poplatek se neplatí online, hradí se na místě. Platbu kartou zpracovává Stripe; UbyHost údaje o vaší kartě nevidí ani neukládá. Fakturu vystaví ubytovatel a najdete ji na stránce své rezervace; odkaz vám přijde e-mailem.
4. **Storno podmínky.** Platí podmínky, které jste viděli před platbou, jedny z těchto tří: **Nevratná**: po zaplacení se nic nevrací. **Flexibilní**: celá částka se vrací do 24 hodin před příchodem. **Střední**: celá částka se vrací do 5 dnů před příchodem, poté polovina ceny ubytování bez úklidu. Rezervaci zrušíte sami na stránce rezervace. Vrácená částka přijde na kartu, kterou jste platili, obvykle do 5 až 10 pracovních dnů podle banky. Po začátku pobytu už zrušit nelze.
5. **Když zruší ubytovatel nebo se termín překryje.** Zruší-li rezervaci ubytovatel, nebo se ukáže, že je termín již obsazen, vrátíme vám celou zaplacenou částku bez ohledu na storno podmínky.
6. **Změny.** Termín ani počet hostů online změnit nelze. Napište ubytovateli; pokud se dohodnete, zrušte původní rezervaci podle bodu 4 a vytvořte novou, nebo se dohodněte s ubytovatelem přímo.
7. **Příchod, pravidla domu, evidence hostů.** Čas příchodu a pravidla domu stanoví ubytovatel. Ubytovatel je ze zákona povinen evidovat své hosty, cizince hlásit policii a vybírat městský poplatek; proto vás po příchodu požádá o údaje z dokladu totožnosti a vy je poskytnete pravdivě.
8. **Škody a odpovědnost.** Za škodu, kterou na ubytování způsobíte vy nebo vaši hosté, odpovídáte ubytovateli. Odpovědnost žádné strany se nevylučuje v rozsahu, v jakém ji zákon vyloučit nedovoluje. Nikdo neodpovídá za porušení povinností způsobené vyšší mocí.
9. **Odstoupení od smlouvy.** Smlouva o ubytování na určité období je podle občanského zákoníku (§ 1837 písm. j) vyňata z práva spotřebitele odstoupit do 14 dnů. Máte však práva ze storno podmínek v bodě 4 a práva z vadného plnění.
10. **Osobní údaje.** Údaje o vás zpracováváme jen pro rezervaci, platbu, fakturu a zákonné povinnosti ubytovatele, a jen po dobu, kterou zákon nebo služba vyžaduje. Správcem je ubytovatel, UbyHost je jeho zpracovatel; platbu zpracovává Stripe. UbyHost nepoužívá reklamní sledování ani sledovací cookies. Více v zásadách ochrany osobních údajů UbyHost.
11. **Reklamace a spory.** Nejprve se obraťte na ubytovatele (kontakt je ve faktuře a v potvrzení). Pokud se nedohodnete, spotřebitel může využít mimosoudní řešení sporů u České obchodní inspekce (www.coi.cz, adr.coi.cz).
12. **Rozhodné právo.** Právo České republiky. Tyto podmínky se nedotýkají práv, která vám zákon dává jako spotřebiteli.

### English (`_booking_terms_en.html`)

h1: Booking terms

Intro (p): These terms apply to accommodation bookings paid by card on a host's page run through UbyHost. Please read them before you pay. Version 3 Nov 2026.

1. **Who is who.** Your stay contract is with the host whose name and details appear on your invoice. UbyHost only provides the technical tool for booking and payment. It is not a party to the stay contract, does not act as an accommodation agent and is not responsible for the stay itself.
2. **When a booking is made.** A booking is binding once your payment succeeds and we send a confirmation to the e-mail you gave. Until then the dates are held only briefly, and if payment does not complete the booking lapses. You must be at least 18, give true details and not exceed the number of guests the place allows.
3. **Price and payment.** The price in Czech koruna covers the stay and the one-time cleaning fee, as shown before you pay. City tax is not paid online; you pay it on site. Stripe processes the card payment; UbyHost does not see or store your card details. The host issues the invoice and you can open it from your booking page, whose link arrives by e-mail.
4. **Cancellation.** The policy you saw before paying applies, one of these three: **Non-refundable**: nothing is refunded after payment. **Flexible**: full refund until 24 hours before check-in. **Moderate**: full refund until 5 days before check-in, after that half of the accommodation price without the cleaning fee. You cancel yourself on your booking page. The refund goes back to the card you paid with, usually within 5 to 10 working days depending on your bank. You cannot cancel online once the stay has started.
5. **If the host cancels or the dates clash.** If the host cancels, or it turns out the dates were already taken, we refund everything you paid, whatever the cancellation policy says.
6. **Changes.** Dates and guest numbers cannot be changed online. Contact the host; if you agree a change, cancel the original booking under section 4 and make a new one, or arrange it with the host directly.
7. **Check-in, house rules, guest registration.** The host sets check-in times and house rules. The law requires hosts to register guests, report foreign guests to the police and collect city tax, so on arrival the host will ask for details from your ID, which you must give truthfully.
8. **Damage and liability.** You are liable to the host for damage that you or your guests cause to the property. No party's liability is excluded where the law does not allow it. Nobody is liable for a failure caused by events beyond their control.
9. **No 14-day withdrawal.** Under the Czech Civil Code (section 1837(j)) a stay contract for a specific period is exempt from the consumer's 14-day right of withdrawal. You still have the cancellation rights in section 4 and your rights if the service is defective.
10. **Personal data.** We process your data only for the booking, payment, invoice and the host's legal duties, and keep it only as long as the law or the service needs. The host is the controller and UbyHost is its processor; Stripe processes the payment. UbyHost uses no advertising tracking and no tracking cookies. More in the UbyHost privacy policy.
11. **Complaints and disputes.** Contact the host first (details are on the invoice and confirmation). If you cannot agree, a consumer may use out-of-court dispute resolution with the Czech Trade Inspection Authority (www.coi.cz, adr.coi.cz).
12. **Governing law.** Czech law. These terms do not affect any rights the law gives you as a consumer.
