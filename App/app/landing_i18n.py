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
        "landing.cta.note": "Or write to support@ubyhost.com — we reply with next steps.",
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
            "run on public pages only."
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
        "pricing.page_title": "UbyHost pricing: tailored for your accommodation",
        "pricing.meta_description": (
            "Ask for UbyHost pricing tailored to your number of properties, reservation "
            "volume, and UbyPort reporting workflow."
        ),
        "pricing.eyebrow": "One plan, priced for your properties",
        "pricing.title": "Pricing that fits your accommodation.",
        "pricing.lede": (
            "Tell us how you host. We will agree on a clear setup for your properties, "
            "guest volume, and UbyPort workflow."
        ),
        "pricing.card.kicker": "What you get",
        "pricing.card.price": "By agreement",
        "pricing.card.summary": (
            "One plan with everything below. The monthly price depends on how many "
            "properties you run — write to us and we reply with a quote."
        ),
        "pricing.card.note": "Priced for what you actually run.",
        "pricing.card.cta": "Request access and a price",
        "pricing.cta.subject": "UbyHost pricing",
        "pricing.includes.title": "The complete guest-reporting workflow",
        "pricing.includes.1": "Airbnb and Booking.com calendar connections",
        "pricing.includes.2": "Private online forms for guests",
        "pricing.includes.3": "Online guest book",
        "pricing.includes.4": "Direct UbyPort reporting and saved receipts",
        "pricing.factors.eyebrow": "What we agree on",
        "pricing.factors.title": "Three things shape the setup.",
        "pricing.factor.properties.title": "Your properties",
        "pricing.factor.properties.body": "How many apartments or accommodation facilities you manage.",
        "pricing.factor.volume.title": "Your guest volume",
        "pricing.factor.volume.body": "How many stays and foreign-guest reports pass through each month.",
        "pricing.factor.workflow.title": "Your workflow",
        "pricing.factor.workflow.body": "The reporting timing, onboarding, and support your team needs.",
        "pricing.final.title": "Tell us what you run.",
        "pricing.final.body": "A short email is enough to start the conversation.",
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
        "landing.cta.note": "Nebo napište na support@ubyhost.com — ozveme se s dalším postupem.",
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
            "Návštěvnost webu měříme jen na veřejných stránkách."
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
        "pricing.page_title": "Ceník UbyHostu: cena dle domluvy",
        "pricing.meta_description": (
            "Zeptejte se na cenu UbyHostu podle počtu ubytování, objemu rezervací "
            "a způsobu hlášení hostů do UbyPortu."
        ),
        "pricing.eyebrow": "Jeden tarif, cena podle vašeho ubytování",
        "pricing.title": "Cena, která sedí vašemu ubytování.",
        "pricing.lede": (
            "Napište nám, jak ubytováváte. Domluvíme jasné řešení podle počtu "
            "ubytování, hostů a způsobu práce s UbyPortem."
        ),
        "pricing.card.kicker": "Co dostanete",
        "pricing.card.price": "Dle domluvy",
        "pricing.card.summary": (
            "Jeden tarif se vším níže. Měsíční cena závisí na počtu vašich ubytování "
            "— napište nám a pošleme nabídku."
        ),
        "pricing.card.note": "Cenu nastavíme podle toho, co skutečně provozujete.",
        "pricing.card.cta": "Požádat o přístup a cenu",
        "pricing.cta.subject": "Cena UbyHostu",
        "pricing.includes.title": "Kompletní postup evidence a hlášení hostů",
        "pricing.includes.1": "Napojení kalendářů Airbnb a Booking.com",
        "pricing.includes.2": "Soukromé online formuláře pro hosty",
        "pricing.includes.3": "Online ubytovací kniha",
        "pricing.includes.4": "Přímé hlášení do UbyPortu a uložené doručenky",
        "pricing.factors.eyebrow": "Na čem se domluvíme",
        "pricing.factors.title": "Nastavení určují tři věci.",
        "pricing.factor.properties.title": "Vaše ubytování",
        "pricing.factor.properties.body": "Kolik apartmánů nebo ubytovacích zařízení spravujete.",
        "pricing.factor.volume.title": "Objem hostů",
        "pricing.factor.volume.body": "Kolik pobytů a hlášení cizinců zpracujete za měsíc.",
        "pricing.factor.workflow.title": "Váš postup",
        "pricing.factor.workflow.body": "Časování hlášení, zavedení systému a potřebná podpora.",
        "pricing.final.title": "Napište nám, co provozujete.",
        "pricing.final.body": "Pro začátek stačí krátký e-mail.",
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
