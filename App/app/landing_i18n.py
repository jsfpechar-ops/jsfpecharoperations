"""Public landing-page copy in Czech and English."""

LANDING_STRINGS = {
    "en": {
        "landing.page_title": "UbyHost: UbyPort reporting and online guest book",
        "landing.meta_description": (
            "Connect Airbnb and Booking.com calendars, collect guest details online, "
            "keep the guest book, and report foreign guests directly to UbyPort."
        ),
        "landing.nav.how": "How it works",
        "landing.nav.pricing": "Pricing",
        "landing.nav.guides": "Guides",
        "landing.nav.login": "Log in",
        "landing.nav.menu": "Menu",
        "landing.eyebrow": "From Airbnb booking to UbyPort receipt",
        "landing.title": "Guests fill in their details. UbyHost reports them to UbyPort.",
        "landing.lede": (
            "For Airbnb and Booking.com hosts in Czechia: guests fill in and sign a "
            "private online form, and UbyHost sends foreign-guest reports to UbyPort "
            "and keeps the guest book."
        ),
        "landing.cta": "Try UbyHost",
        "landing.cta.note": "Or write to support@ubyhost.com. We reply with next steps.",
        "landing.contact": "How it works",
        "landing.independent": "UbyHost is an independent private service. It is not operated or endorsed by the Czech Police or UbyPort.",
        "landing.demo.label": "A quick tour of UbyHost",
        "landing.demo.play": "Play demo",
        "landing.demo.pause": "Pause demo",
        "landing.demo.replay": "Replay demo",
        "landing.demo.scene.calendar": "A reservation arrives",
        "landing.demo.scene.form": "The guest fills in the details",
        "landing.demo.scene.queue": "Everything is ready to report",
        "landing.demo.scene.receipt": "UbyPort accepts the report",
        "landing.demo.calendar.month": "September",
        "landing.demo.calendar.booking": "Airbnb · Anna K.",
        "landing.demo.form.title": "Guest check-in",
        "landing.demo.form.name": "Anna Kowalska",
        "landing.demo.form.document": "Travel document",
        "landing.demo.form.signed": "Signed by guest",
        "landing.demo.queue.title": "Arrivals",
        "landing.demo.queue.missing": "Missing details",
        "landing.demo.queue.ready": "Ready",
        "landing.demo.receipt.sending": "Sending securely…",
        "landing.demo.receipt.accepted": "Accepted by UbyPort",
        "landing.demo.receipt.saved": "Delivery receipt saved with the stay",
        "landing.demo.example": "Example",
        "landing.demo.weekdays": "M,T,W,T,F,S,S",
        "landing.benefits.eyebrow": "One simple flow",
        "landing.benefits.title": "Less chasing. Less copying. More certainty.",
        "landing.benefit.calendar.title": "Guest records start with bookings",
        "landing.benefit.calendar.body": "Connect Airbnb and Booking.com calendars.",
        "landing.benefit.guest.title": "Guests do the typing",
        "landing.benefit.guest.body": "Guests fill in and sign their details through one private link.",
        "landing.benefit.ubyport.title": "UbyPort gets the report",
        "landing.benefit.ubyport.body": "Send it and keep the real delivery receipt.",
        # WP27: privacy first. Every claim here is true for the code; see
        # tests/test_privacy_first.py and notes WP27 before changing one.
        "privacy_first.eyebrow": "Privacy first",
        "privacy_first.title": "Only what the law asks for. Nothing extra.",
        "privacy_first.lede": "We store as little as we can, and say exactly what and for how long.",
        "privacy_first.link": "Privacy policy",
        "privacy_first.law.title": "Only the fields Czech law asks for",
        "privacy_first.law.body": (
            "The guest form asks for the guest-book and stay-fee details, plus an e-mail "
            "for the guest's private link."
        ),
        "privacy_first.cookies.title": "No tracking cookies",
        "privacy_first.cookies.body": "Only the cookies that keep you signed in and protect your forms.",
        "privacy_first.trackers.title": "No trackers in the app",
        "privacy_first.trackers.body": (
            "No ad or analytics scripts in the app or on guest pages. Website statistics "
            "run on public pages only, with PostHog Cloud EU."
        ),
        "privacy_first.photos.title": "Passport photos deleted after check-in",
        "privacy_first.photos.body": (
            "Optional and off by default. Deleted as soon as you verify the guest, otherwise "
            "automatically 7 days after check-in."
        ),
        "privacy_first.line": (
            "UbyHost collects only what Czech law and the service itself need, and does not "
            "use tracking cookies."
        ),
        "landing.steps.title": "From booking to reported in three moves.",
        "landing.steps.1": "Connect your calendar",
        "landing.steps.2": "Share the guest link",
        "landing.steps.3": "Keep the UbyPort receipt",
        "landing.final.title": "Guest reporting, handled for you.",
        "landing.final.body": "See every stay, form, and UbyPort response in one place.",
        "landing.details.link": "How it works",
        "product.page_title": "UbyPort for Airbnb and Booking.com hosts · UbyHost",
        "product.meta_description": (
            "See how UbyHost connects Airbnb and Booking.com calendars, online guest "
            "forms, the guest book, and direct reporting to UbyPort."
        ),
        "product.eyebrow": "UbyPort reporting, without the repetitive admin",
        "product.title": "One flow from Airbnb booking to UbyPort receipt.",
        "product.lede": (
            "Connect the calendar once. Guests provide their own details. UbyHost keeps "
            "the guest book and the exact response from UbyPort together."
        ),
        "product.features.title": "The whole reporting path in one place",
        "product.features.lede": "Four connected steps, no copying into spreadsheets.",
        "product.faq.title": "Common UbyPort questions",
        "product.guides.title": "Practical guides for Czech hosts",
        "product.cta.title": "Ready to simplify guest reporting?",
        "pricing.page_title": "UbyHost pricing: guest reporting from 99 CZK a month",
        "pricing.meta_description": (
            "Automatic UbyPort reporting with receipts, guest book and stay fee. "
            "No guest limits. 30 days free."
        ),
        "pricing.eyebrow": "No guest limits · No paperwork · No fines",
        "pricing.title": "Less admin. More hosting.",
        "pricing.lede": "Guests register themselves, UbyPort gets the report, you get the receipt. You pay per apartment, not per guest.",
        "pricing.chips": "30 days free · No card · Cancel anytime",
        "pricing.total_label": "Total for the selected apartments",
        "pricing.havel": "Two AIs: Leon answers your guests' questions, Havel helps you run UbyHost.",
        "pricing.ttlock.help": "Create a door code for each stay.",
        "pricing.ttlock.month": "+%(price)s CZK / apartment / month",
        "pricing.ttlock.selected": "Included in the total",
        "pricing.calc.label": "Price calculator",
        "pricing.toggle.label": "Billing",
        "pricing.toggle.year": "Yearly",
        "pricing.toggle.year_badge": "Lower yearly price",
        "pricing.toggle.month": "Monthly",
        "pricing.count.label": "Apartments",
        "pricing.count.dec": "Remove an apartment",
        "pricing.count.inc": "Add an apartment",
        "pricing.ttlock.label": "I have TTLock smart locks",
        "pricing.currency": "CZK",
        "pricing.per_month": "/ month",
        "pricing.billed_year": "Billed %(amount)s CZK once a year",
        "pricing.month_hint": "Billed monthly",
        "pricing.apts.one": "%(count)s apartment",
        "pricing.apts.few": "%(count)s apartments",
        "pricing.apts": "%(count)s apartments",
        "pricing.std.name": "UbyHost",
        "pricing.std.tagline": "Everything for worry-free reporting",
        "pricing.std.f1": "Automatic UbyPort reports with receipts",
        "pricing.std.f2": "Online check-in, 6-year guest book",
        "pricing.std.f3": "Duplicate protection",
        "pricing.std.f4": "Stay fee report and QR payment",
        "pricing.std.f5": "Leon Lite AI for guests · Havel AI for you",
        "pricing.std.f6": "Unlimited guests, stays and teammates",
        "pricing.std.f7": "Leon Lite AI for guests, limited usage",
        "pricing.std.note": "no guest limits",
        "pricing.std.note_ttlock": "incl. TTLock",
        "pricing.max.name": "UbyHost Max",
        "pricing.max.badge": "5× AI usage",
        "pricing.max.tagline": "For hosts who want calm even in high season",
        "pricing.max.f1": "Everything in UbyHost",
        "pricing.max.f2": "Full-power Leon AI concierge for guests, 24/7",
        "pricing.max.f3": "Full-power Havel AI, 24/7",
        "pricing.max.f4": "TTLock smart locks included",
        "pricing.max.f5": "Priority support",
        "pricing.max.f6": "Document scanning (OCR): coming soon, not yet available.",
        "pricing.cta": "Try free for 30 days",
        "pricing.cta_note": "The 30-day trial starts when you verify your email address.",
        "pricing.prices_final": "Prices are final.",
        "pricing.bands.eyebrow": "Graduated pricing",
        "pricing.bands.title": "UbyHost apartment rates",
        "pricing.bands.body": "Each rate applies only to apartments in that band, not your whole portfolio. Max adds its plan supplement; the cards show your total.",
        "pricing.bands.b1": "1–4",
        "pricing.bands.b2": "5–9",
        "pricing.bands.b3": "10+",
        "pricing.bands.unit_year": "per apartment a month, billed yearly",
        "pricing.bands.unit_month": "per apartment a month",
        "pricing.founder.heading": "Founding hosts: 74 CZK a month",
        "pricing.founder.body": "890 CZK a year per apartment, price locked for 2 years. %(n)s of 100 places left.",
        "pricing.founder.cta": "Claim a place",
        "pricing.addons.eyebrow": "Optional",
        "pricing.addons.title": "Add-ons",
        "pricing.addon.ttlock.title": "TTLock smart locks",
        "pricing.addon.ttlock.body": "A code for every stay. +40 CZK per apartment a month, free in Max.",
        "pricing.anchor.eyebrow": "Why it pays off",
        "pricing.anchor.title": "Cheaper than one mistake",
        "pricing.anchor.body": "A year of UbyHost costs 1,190 CZK. An unreported guest can cost up to 50,000 CZK.",
        "pricing.faq.title": "Questions and answers",
        "pricing.faq.1.q": "When does the trial start?",
        "pricing.faq.1.a": "Your 30-day trial starts when you verify your email address and activate your account. You can connect UbyPort during the trial.",
        "pricing.faq.2.q": "What counts as an apartment?",
        "pricing.faq.2.a": "Every listing with its own calendar. Guests, stays and teammates are unlimited.",
        "pricing.faq.3.q": "Do I need a card?",
        "pricing.faq.3.a": "No. You pay by bank transfer on an invoice we send after the trial.",
        "pricing.faq.4.q": "What if I add an apartment?",
        "pricing.faq.4.a": (
            "The price adjusts automatically and you pay only the remaining part. "
            "When you remove an apartment, the lower price applies from the next period."
        ),
        "pricing.faq.5.q": "Can I cancel anytime?",
        "pricing.faq.5.a": (
            "Yes. The service runs until the end of the paid period and you can download "
            "the guest book at any time."
        ),
        "pricing.faq.6.q": "Can I get an invoice for my company?",
        "pricing.faq.6.a": "Yes, with your company ID and VAT ID. We fill in the details from the ARES register.",
        "pricing.faq.7.q": "What if I pay late?",
        "pricing.faq.7.a": (
            "We send a reminder. Everything keeps running for 30 days after the due date, "
            "and we never stop reporting guests who are already registered."
        ),
        "pricing.faq.8.q": "How do I pay?",
        "pricing.faq.8.a": (
            "By bank transfer on the invoice: scan the QR code in your banking app. "
            "We match the payment ourselves. Card payments are coming soon."
        ),
        "pricing.faq.9.q": "What about eTurista?",
        "pricing.faq.9.a": (
            "It is not law yet and the state has not published its interface. Once it does, "
            "we connect to it and move your data over with no retyping."
        ),
        "pricing.final.title": "Start today, pay in 30 days",
        "pricing.final.large": "10 or more apartments?",
        "pricing.final.write": "Write to us.",
        "pricing.final.subject": "UbyHost for 10 or more apartments",
        "landing.mock.today": "Today",
        "landing.mock.guest_form": "Guest form",
        "landing.features.eyebrow": "Everything in one workflow",
        "landing.features.title": "From a reservation to a delivery receipt",
        "landing.features.lede": (
            "Collect the required details once. UbyHost keeps the stay, signed guest form, "
            "house-book entry, and UbyPort response together."
        ),
        "landing.feature.calendar.icon": "01 / Sync",
        "landing.feature.calendar.title": "Airbnb and Booking.com calendars",
        "landing.feature.calendar.body": (
            "Connect iCal feeds so upcoming stays appear automatically and you know which "
            "guest forms are still missing."
        ),
        "landing.feature.form.icon": "02 / Collect",
        "landing.feature.form.title": "Online guest check-in form",
        "landing.feature.form.body": (
            "Share one stable link. Guests enter and sign their details on a phone or "
            "computer before arrival."
        ),
        "landing.feature.book.icon": "03 / Keep",
        "landing.feature.book.title": "Online guest book",
        "landing.feature.book.body": (
            "Keep a chronological record of guests and export the records you need for "
            "your accommodation files."
        ),
        "landing.feature.ubyport.icon": "04 / Report",
        "landing.feature.ubyport.title": "Direct UbyPort reporting",
        "landing.feature.ubyport.body": (
            "Send completed foreign-guest records through the UbyPort web service and "
            "retain the delivery receipt or exact rejection."
        ),

        "landing.faq.eyebrow": "Common questions",
        "landing.faq.title": "What Czech hosts need to know",
        "landing.faq.1.q": "Who must report foreign guests?",
        "landing.faq.1.a": (
            "Accommodation providers in Czechia generally have to report accommodated "
            "foreign nationals to the Police of the Czech Republic. Business accommodation "
            "providers use the UbyPort internet application."
        ),
        "landing.faq.2.q": "How soon must a foreign guest be reported?",
        "landing.faq.2.a": (
            "The public authorities state a deadline of three working days after accommodation. "
            "Always follow the current official guidance for your situation."
        ),
        "landing.faq.3.q": "Does UbyHost replace UbyPort registration?",
        "landing.faq.3.a": (
            "No. First register the accommodation with UbyPort and request separate web-service "
            "credentials. UbyHost then uses those credentials to transmit records."
        ),
        "landing.faq.4.q": "Does UbyHost import Airbnb and Booking.com reservations?",
        "landing.faq.4.a": (
            "Yes. Their iCal feeds provide dates and availability. Guests provide the personal "
            "details through the private form."
        ),
        "landing.official": "Official information for accommodation providers",
        "landing.disclaimer": "UbyHost is a technical tool, not legal advice. Check current duties with the Czech authorities.",
        "landing.footer.login": "Host login",
        "landing.footer.guestbook": "Guest book",
        "landing.guide.ubyport.kicker": "UbyPort",
        "landing.guide.ubyport.title": "Reporting foreign guests through UbyPort: a host’s guide",
        "landing.guide.ubyport.meta": "Registration, access, deadlines, and receipts",
        "landing.guide.book.kicker": "Guest records",
        "landing.guide.book.title": "Online guest book without paperwork",
        "landing.guide.book.meta": "Calendars, forms, and the house book",
        "guide.breadcrumb": "Guides",
        "guide.breadcrumb_nav": "Breadcrumbs",
        "guide.updated": "Last checked against official sources: %(date)s",
        "guide.checklist": "Checklist",
        "guide.official_title": "Check current rules at the official source",
        "guide.more": "Further reading",
        "guide.more_nav": "More guides",
    },
    "cs": {
        "landing.page_title": "UbyHost: UbyPort · Online ubytovací kniha",
        "landing.meta_description": (
            "Propojte Airbnb a Booking.com, sbírejte údaje hostů online, veďte ubytovací "
            "knihu a hlaste cizince přímo do UbyPortu."
        ),
        "landing.nav.how": "Jak to funguje",
        "landing.nav.pricing": "Ceník",
        "landing.nav.guides": "Průvodce",
        "landing.nav.login": "Přihlásit se",
        "landing.nav.menu": "Menu",
        "landing.eyebrow": "Od rezervace z Airbnb až po doručenku z UbyPortu",
        "landing.title": "Hosté vyplní údaje. UbyHost je nahlásí do UbyPortu.",
        "landing.lede": (
            "Pro hostitele z Airbnb a Booking.com v Česku: hosté vyplní a podepíší "
            "soukromý online formulář, UbyHost nahlásí cizince do UbyPortu a povede "
            "ubytovací knihu."
        ),
        "landing.cta": "Vyzkoušet UbyHost",
        "landing.cta.note": "Nebo napište na support@ubyhost.com. Ozveme se s dalším postupem.",
        "landing.contact": "Jak to funguje",
        "landing.independent": "UbyHost je nezávislá soukromá služba. Neprovozuje ji ani nedoporučuje Policie ČR ani UbyPort.",
        "landing.demo.label": "Rychlá ukázka UbyHostu",
        "landing.demo.play": "Spustit ukázku",
        "landing.demo.pause": "Pozastavit ukázku",
        "landing.demo.replay": "Přehrát znovu",
        "landing.demo.scene.calendar": "Přijde rezervace",
        "landing.demo.scene.form": "Host vyplní své údaje",
        "landing.demo.scene.queue": "Vše je připravené k hlášení",
        "landing.demo.scene.receipt": "UbyPort hlášení přijme",
        "landing.demo.calendar.month": "Září",
        "landing.demo.calendar.booking": "Airbnb · Anna K.",
        "landing.demo.form.title": "Online check-in",
        "landing.demo.form.name": "Anna Kowalska",
        "landing.demo.form.document": "Cestovní doklad",
        "landing.demo.form.signed": "Podepsáno hostem",
        "landing.demo.queue.title": "Příjezdy",
        "landing.demo.queue.missing": "Chybí údaje",
        "landing.demo.queue.ready": "Připraveno",
        "landing.demo.receipt.sending": "Bezpečně odesíláme…",
        "landing.demo.receipt.accepted": "Přijato systémem UbyPort",
        "landing.demo.receipt.saved": "Doručenka uložena u pobytu",
        "landing.demo.example": "Ukázka",
        "landing.demo.weekdays": "Po,Út,St,Čt,Pá,So,Ne",
        "landing.benefits.eyebrow": "Jeden jednoduchý postup",
        "landing.benefits.title": "Méně urgování. Méně přepisování. Více jistoty.",
        "landing.benefit.calendar.title": "Rezervace se objeví",
        "landing.benefit.calendar.body": "Propojte kalendáře Airbnb a Booking.com.",
        "landing.benefit.guest.title": "Hosté údaje vyplní",
        "landing.benefit.guest.body": "Hosté vše vyplní a podepíší přes jeden soukromý odkaz.",
        "landing.benefit.ubyport.title": "UbyPort dostane hlášení",
        "landing.benefit.ubyport.body": "Odešlete ho a uchovejte skutečnou doručenku.",
        "privacy_first.eyebrow": "Soukromí na prvním místě",
        "privacy_first.title": "Jen to, co žádá zákon. Nic navíc.",
        "privacy_first.lede": "Ukládáme co nejméně a přesně říkáme co a jak dlouho.",
        "privacy_first.link": "Zásady ochrany osobních údajů",
        "privacy_first.law.title": "Jen údaje, které žádá český zákon",
        "privacy_first.law.body": (
            "Formulář pro hosty chce jen údaje do domovní knihy a k poplatku z pobytu, "
            "k tomu e-mail pro soukromý odkaz hosta."
        ),
        "privacy_first.cookies.title": "Žádné sledovací cookies",
        "privacy_first.cookies.body": "Jen cookies, které vás udrží přihlášené a chrání formuláře.",
        "privacy_first.trackers.title": "V aplikaci nic nesleduje",
        "privacy_first.trackers.body": (
            "V aplikaci ani na stránkách pro hosty nejsou reklamní ani analytické skripty. "
            "Návštěvnost webu měříme jen na veřejných stránkách, s PostHog Cloud EU."
        ),
        "privacy_first.photos.title": "Fotky dokladů se po příjezdu mažou",
        "privacy_first.photos.body": (
            "Nepovinné a ve výchozím stavu vypnuté. Smažou se, jakmile hosta ověříte, "
            "jinak automaticky 7 dní po příjezdu."
        ),
        "privacy_first.line": (
            "UbyHost shromažďuje jen to, co vyžaduje český zákon a samotná služba, "
            "a nepoužívá sledovací cookies."
        ),
        "landing.steps.title": "Od rezervace k hlášení ve třech krocích.",
        "landing.steps.1": "Propojte kalendář",
        "landing.steps.2": "Sdílejte odkaz pro hosty",
        "landing.steps.3": "Uložte doručenku z UbyPortu",
        "landing.final.title": "Hlášení hostů vyřídíme za vás.",
        "landing.final.body": "Každý pobyt, formulář a odpověď UbyPortu na jednom místě.",
        "landing.details.link": "Jak to funguje",
        "product.page_title": "UbyPort pro hostitele z Airbnb a Booking.com · UbyHost",
        "product.meta_description": (
            "Jak UbyHost propojí Airbnb a Booking.com, online formuláře hostů, ubytovací "
            "knihu a přímé hlášení cizinců do UbyPortu."
        ),
        "product.eyebrow": "Hlášení do UbyPortu bez opakované administrativy",
        "product.title": "Jeden postup od rezervace z Airbnb po doručenku z UbyPortu.",
        "product.lede": (
            "Kalendář propojíte jednou. Hosté vyplní své údaje sami. UbyHost uchová "
            "ubytovací knihu i přesnou odpověď z UbyPortu pohromadě."
        ),
        "product.features.title": "Celá cesta hlášení na jednom místě",
        "product.features.lede": "Čtyři navazující kroky, žádné přepisování do tabulek.",
        "product.faq.title": "Nejčastější otázky k UbyPortu",
        "product.guides.title": "Praktické průvodce pro české ubytovatele",
        "product.cta.title": "Chcete si zjednodušit hlášení hostů?",
        "pricing.page_title": "Ceník UbyHostu: hlášení cizinců od 99 Kč měsíčně",
        "pricing.meta_description": (
            "Automatické hlášení do UbyPortu s doručenkou, ubytovací kniha a poplatek "
            "z pobytu. Bez limitu hostů. 30 dní zdarma."
        ),
        "pricing.eyebrow": "Bez limitu hostů · Bez papírování · Bez pokut",
        "pricing.title": "Méně papírování. Více času na hosty.",
        "pricing.lede": "Host se zapíše sám, UbyPort dostane hlášení, vy doručenku. Platíte za apartmán, ne za hosty.",
        "pricing.chips": "30 dní zdarma · Bez platební karty · Zrušíte kdykoli",
        "pricing.total_label": "Celkem za vybrané apartmány",
        "pricing.havel": "Dvě AI: Leon odpovídá hostům na otázky, Havel vám pomůže s UbyHostem.",
        "pricing.ttlock.help": "Vytvořte kód ke dveřím pro každý pobyt.",
        "pricing.ttlock.month": "+%(price)s Kč / apartmán / měsíc",
        "pricing.ttlock.selected": "Zahrnuto v celkové ceně",
        "pricing.calc.label": "Kalkulačka ceny",
        "pricing.toggle.label": "Fakturace",
        "pricing.toggle.year": "Ročně",
        "pricing.toggle.year_badge": "Výhodnější roční platba",
        "pricing.toggle.month": "Měsíčně",
        "pricing.count.label": "Počet apartmánů",
        "pricing.count.dec": "Ubrat apartmán",
        "pricing.count.inc": "Přidat apartmán",
        "pricing.ttlock.label": "Mám chytré zámky TTLock",
        "pricing.currency": "Kč",
        "pricing.per_month": "/ měsíc",
        "pricing.billed_year": "Platíte %(amount)s Kč jednou ročně",
        "pricing.month_hint": "Platíte měsíčně",
        "pricing.apts.one": "%(count)s apartmán",
        "pricing.apts.few": "%(count)s apartmány",
        "pricing.apts": "%(count)s apartmánů",
        "pricing.std.name": "UbyHost",
        "pricing.std.tagline": "Vše pro bezstarostné hlášení",
        "pricing.std.f1": "Automatické hlášení do UbyPortu s doručenkou",
        "pricing.std.f2": "Online check-in, ubytovací kniha na 6 let",
        "pricing.std.f3": "Ochrana proti duplicitám",
        "pricing.std.f4": "Poplatek z pobytu a QR platba",
        "pricing.std.f5": "AI Leon Lite pro hosty · AI Havel pro vás",
        "pricing.std.f6": "Neomezeně hostů, pobytů i kolegů",
        "pricing.std.f7": "AI Leon Lite pro hosty, s limitem",
        "pricing.std.note": "bez limitu hostů",
        "pricing.std.note_ttlock": "vč. TTLock",
        "pricing.max.name": "UbyHost Max",
        "pricing.max.badge": "5× využití AI",
        "pricing.max.tagline": "Pro hostitele, kteří chtějí klid i v sezóně",
        "pricing.max.f1": "Vše z UbyHostu",
        "pricing.max.f2": "AI concierge Leon pro hosty naplno, 24/7",
        "pricing.max.f3": "AI Havel naplno, 24/7",
        "pricing.max.f4": "Chytré zámky TTLock v ceně",
        "pricing.max.f5": "Přednostní podpora",
        "pricing.max.f6": "Skenování dokladů (OCR): připravujeme, zatím nedostupné.",
        "pricing.cta": "Vyzkoušet 30 dní zdarma",
        "pricing.cta_note": "Zkušební doba 30 dní začne ověřením vaší e-mailové adresy.",
        "pricing.prices_final": "Ceny jsou konečné.",
        "pricing.bands.eyebrow": "Postupná sleva",
        "pricing.bands.title": "Sazby UbyHost za apartmán",
        "pricing.bands.body": "Sazba platí jen pro apartmány v daném pásmu, ne pro celé portfolio. Max přidává příplatek za plán; karty ukazují celkovou cenu.",
        "pricing.bands.b1": "1–4",
        "pricing.bands.b2": "5–9",
        "pricing.bands.b3": "10+",
        "pricing.bands.unit_year": "za apartmán měsíčně, placeno ročně",
        "pricing.bands.unit_month": "za apartmán měsíčně",
        "pricing.founder.heading": "Zakládající hostitelé: 74 Kč měsíčně",
        "pricing.founder.body": "890 Kč ročně za apartmán, cena zamčená na 2 roky. Zbývá %(n)s ze 100 míst.",
        "pricing.founder.cta": "Získat místo",
        "pricing.addons.eyebrow": "Na přání",
        "pricing.addons.title": "Doplňky",
        "pricing.addon.ttlock.title": "Chytré zámky TTLock",
        "pricing.addon.ttlock.body": "Kód pro každý pobyt. +40 Kč za apartmán měsíčně, v Max zdarma.",
        "pricing.anchor.eyebrow": "Proč se to vyplatí",
        "pricing.anchor.title": "Levnější než jedna chyba",
        "pricing.anchor.body": "Rok UbyHostu stojí 1 190 Kč. Za nenahlášeného hosta hrozí pokuta až 50 000 Kč.",
        "pricing.faq.title": "Časté dotazy",
        "pricing.faq.1.q": "Kdy začne zkušební doba?",
        "pricing.faq.1.a": "Zkušební doba 30 dní začne, když ověříte svou e-mailovou adresu a aktivujete účet. UbyPort můžete propojit během zkušební doby.",
        "pricing.faq.2.q": "Co se počítá jako apartmán?",
        "pricing.faq.2.a": "Každá nabídka s vlastním kalendářem. Hostů, pobytů a kolegů je neomezeně.",
        "pricing.faq.3.q": "Musím zadávat kartu?",
        "pricing.faq.3.a": "Ne. Platíte převodem na fakturu, kterou pošleme až po zkušební době.",
        "pricing.faq.4.q": "Co když přidám apartmán?",
        "pricing.faq.4.a": (
            "Cena se upraví automaticky, doplatíte jen poměrnou část. Když apartmán "
            "odeberete, nižší cena platí od dalšího období."
        ),
        "pricing.faq.5.q": "Můžu zrušit kdykoli?",
        "pricing.faq.5.a": (
            "Ano. Služba běží do konce zaplaceného období a ubytovací knihu si můžete "
            "kdykoli stáhnout."
        ),
        "pricing.faq.6.q": "Dostanu fakturu na firmu?",
        "pricing.faq.6.a": "Ano, s IČO a DIČ. Údaje doplníme z ARES.",
        "pricing.faq.7.q": "Co když fakturu nestihnu zaplatit?",
        "pricing.faq.7.a": (
            "Připomeneme se. Ještě 30 dní po splatnosti běží vše dál a hlášení už "
            "registrovaných hostů nikdy nezastavíme."
        ),
        "pricing.faq.8.q": "Jak platit?",
        "pricing.faq.8.a": (
            "Převodem na fakturu, stačí naskenovat QR kód v bankovní aplikaci. "
            "Platbu spárujeme sami. Platba kartou přibude brzy."
        ),
        "pricing.faq.9.q": "Co eTurista?",
        "pricing.faq.9.a": (
            "Zákon zatím neplatí a stát nezveřejnil rozhraní. Jakmile ho zveřejní, "
            "napojíme se a vaše data převedeme bez přepisování."
        ),
        "pricing.final.title": "Začněte dnes, platit budete až za 30 dní",
        "pricing.final.large": "10 a více apartmánů?",
        "pricing.final.write": "Napište nám.",
        "pricing.final.subject": "UbyHost pro 10 a více apartmánů",
        "landing.mock.today": "Dnes",
        "landing.mock.guest_form": "Formulář hosta",
        "landing.features.eyebrow": "Celý postup na jednom místě",
        "landing.features.title": "Od rezervace až po doručenku",
        "landing.features.lede": (
            "Údaje získáte jednou. UbyHost drží pobyt, podepsaný formulář, zápis v domovní "
            "knize i odpověď UbyPortu pohromadě."
        ),
        "landing.feature.calendar.icon": "01 / Napojení",
        "landing.feature.calendar.title": "Kalendáře Airbnb a Booking.com",
        "landing.feature.calendar.body": (
            "Připojte iCal kalendáře. Budoucí pobyty se objeví automaticky a hned vidíte, "
            "které formuláře ještě chybí."
        ),
        "landing.feature.form.icon": "02 / Sběr",
        "landing.feature.form.title": "Online check-in formulář",
        "landing.feature.form.body": (
            "Sdílejte jeden stálý odkaz. Hosté vyplní a podepíší údaje na telefonu nebo "
            "počítači ještě před příjezdem."
        ),
        "landing.feature.book.icon": "03 / Evidence",
        "landing.feature.book.title": "Online ubytovací kniha",
        "landing.feature.book.body": (
            "Veďte chronologickou evidenci ubytovaných hostů a exportujte záznamy potřebné "
            "pro dokumentaci ubytování."
        ),
        "landing.feature.ubyport.icon": "04 / Hlášení",
        "landing.feature.ubyport.title": "Přímé hlášení do UbyPortu",
        "landing.feature.ubyport.body": (
            "Odesílejte hotové záznamy cizinců přes webovou službu UbyPort a uchovejte "
            "doručenku nebo přesné znění odmítnutí."
        ),

        "landing.faq.eyebrow": "Časté otázky",
        "landing.faq.title": "Co potřebuje český ubytovatel vědět",
        "landing.faq.1.q": "Kdo musí hlásit ubytované cizince?",
        "landing.faq.1.a": (
            "Ubytovatelé v Česku mají obecně povinnost oznámit ubytování cizince Policii ČR. "
            "Podnikatelé poskytující ubytování používají internetovou aplikaci UbyPort."
        ),
        "landing.faq.2.q": "Do kdy je potřeba cizince nahlásit?",
        "landing.faq.2.a": (
            "Veřejné orgány uvádějí lhůtu tří pracovních dnů po ubytování cizince. "
            "Pro svou situaci se vždy řiďte aktuálními oficiálními pokyny."
        ),
        "landing.faq.3.q": "Nahradí UbyHost registraci v UbyPortu?",
        "landing.faq.3.a": (
            "Ne. Ubytovací zařízení nejprve zaregistrujete v UbyPortu a požádáte o samostatný "
            "přístup k webové službě. UbyHost pak tímto přístupem odesílá záznamy."
        ),
        "landing.faq.4.q": "Načte UbyHost rezervace z Airbnb a Booking.com?",
        "landing.faq.4.a": (
            "Ano. Jejich iCal kalendáře předají termíny a dostupnost. Osobní údaje pro domovní "
            "knihu a hlášení cizince vyplní host v soukromém formuláři."
        ),
        "landing.official": "Oficiální informace pro ubytovatele",
        "landing.disclaimer": "UbyHost je technický nástroj, nikoli právní poradenství. Aktuální povinnosti ověřte u českých úřadů.",
        "landing.footer.login": "Přihlášení pro ubytovatele",
        "landing.footer.guestbook": "Ubytovací kniha",
        "landing.guide.ubyport.kicker": "UbyPort",
        "landing.guide.ubyport.title": "Hlášení cizinců přes UbyPort: postup pro ubytovatele",
        "landing.guide.ubyport.meta": "Registrace, přístup, lhůta a doručenky",
        "landing.guide.book.kicker": "Evidence hostů",
        "landing.guide.book.title": "Online ubytovací kniha bez papírování",
        "landing.guide.book.meta": "Kalendáře, formuláře a domovní kniha",
        "guide.breadcrumb": "Průvodce",
        "guide.breadcrumb_nav": "Drobečková navigace",
        "guide.updated": "Naposledy ověřeno podle oficiálních zdrojů: %(date)s",
        "guide.checklist": "Kontrolní seznam",
        "guide.official_title": "Ověřte aktuální pravidla u oficiálního zdroje",
        "guide.more": "Další čtení",
        "guide.more_nav": "Další průvodce",
    },
}
