"""Original Czech search guides grounded in official public information."""

GUIDES = {
    "hlaseni-cizincu-ubyport": {
        "title": "Hlášení cizinců přes UbyPort: postup pro ubytovatele",
        "updated": "2026-09-19",
        "description": (
            "UbyPort pro hostitele z Airbnb a Booking.com: registrace zařízení, "
            "třídenní lhůta, webová služba, doručenky a kontrola chyb."
        ),
        "eyebrow": "UbyPort pro Airbnb a krátkodobé pronájmy",
        "lede": (
            "Praktický průvodce pro hostitele z Airbnb, Booking.com a dalších "
            "krátkodobých pronájmů: co připravit a jak ověřit, že Policie ČR "
            "hlášení skutečně přijala."
        ),
        "sections": [
            {
                "heading": "Koho a do kdy ubytovatel hlásí",
                "paragraphs": [
                    (
                        "Podle oficiálních informací má ubytovatel oznámit ubytování cizince "
                        "Policii České republiky do tří pracovních dnů po ubytování. Pokud je "
                        "ubytování předmětem podnikatelské činnosti, oznámení se podává přes "
                        "internetovou aplikaci UbyPort."
                    ),
                    (
                        "Povinnost a konkrétní rozsah údajů vždy ověřte podle aktuálních "
                        "pokynů státu. UbyHost je technický nástroj, nikoli právní poradna."
                    ),
                ],
            },
            {
                "heading": "1. Zaregistrujte ubytovací zařízení v UbyPortu",
                "paragraphs": [
                    (
                        "Nejdříve potřebujete registraci konkrétního ubytovacího zařízení. "
                        "UbyPort pracuje s údaji zařízení, jako jsou IDUB, přidělená zkratka, "
                        "název, adresa a kontakt. Tyto údaje musí při elektronickém odeslání "
                        "souhlasit s registrem."
                    ),
                ],
            },
            {
                "heading": "2. Pro automatické odesílání vyžádejte webovou službu",
                "paragraphs": [
                    (
                        "Běžné přihlašovací údaje do portálu nejsou totéž jako přístup pro "
                        "robotické vkládání dat. Pro přímé odesílání z aplikace potřebujete "
                        "samostatné přihlašovací údaje k webové službě UbyPort."
                    ),
                    (
                        "V UbyHostu je zadáte ke konkrétnímu ubytování. Heslo se v přehledu "
                        "nezobrazuje a každé zařízení může mít vlastní registrační údaje."
                    ),
                ],
            },
            {
                "heading": "3. Získejte od hosta úplné a podepsané údaje",
                "paragraphs": [
                    (
                        "Host otevře soukromý formulář před příjezdem na telefonu nebo počítači. "
                        "UbyHost kontroluje povinná pole a podpis a drží formulář u správného "
                        "pobytu. iCal kalendáře z Airbnb a Booking.com dodají termín pobytu, "
                        "nikoli osobní údaje hosta."
                    ),
                ],
            },
            {
                "heading": "4. Zkontrolujte doručenku, ne pouze tlačítko Odeslat",
                "paragraphs": [
                    (
                        "Úspěch znamená, že UbyPort záznam přijal. UbyHost proto uchovává "
                        "odpověď i doručenku u odeslání. Pokud UbyPort záznam odmítne, zobrazí "
                        "přesnou chybu, aby bylo možné opravit údaj zařízení nebo hosta."
                    ),
                    (
                        "Opakované odesílání stejného záznamu bez důvodu není bezpečný způsob "
                        "opravy. Nejdříve ověřte, zda hlášení už nebylo přijato."
                    ),
                ],
            },
        ],
        "checklist": [
            "registrované ubytovací zařízení v UbyPortu",
            "IDUB, zkratka, název a adresa shodné s registrem",
            "samostatný přístup k webové službě pro automatické odesílání",
            "úplné a podepsané údaje cizince",
            "kontrola doručenky nebo konkrétní chyby po odeslání",
        ],
        "official_url": "https://ipc.gov.cz/pro-ubytovatele/obecne-informace-pro-ubytovatele/",
    },
    "online-ubytovaci-kniha": {
        "title": "Online ubytovací kniha: evidence hostů bez papírování",
        "updated": "2026-09-19",
        "description": (
            "Jak funguje online ubytovací a domovní kniha, formulář před příjezdem, "
            "evidence hostů a návaznost na hlášení cizinců přes UbyPort."
        ),
        "eyebrow": "Průvodce pro krátkodobé ubytování",
        "lede": (
            "Dobrá online evidence nezačíná přepisováním pasu na recepci. Začíná rezervací, "
            "soukromým formulářem hosta a jasným přehledem toho, co ještě chybí."
        ),
        "sections": [
            {
                "heading": "Co online ubytovací kniha řeší",
                "paragraphs": [
                    (
                        "Ubytovatel potřebuje propojit pobyt s údaji ubytovaných osob a uchovat "
                        "záznamy přehledně a chronologicky. U cizinců na evidenci navazuje také "
                        "oznámení Policii ČR. Konkrétní zákonné povinnosti se liší podle typu "
                        "ubytování a hosta, proto je ověřujte u příslušných úřadů."
                    ),
                    (
                        "UbyHost soustředí rezervace, formuláře hostů, domovní knihu a odpovědi "
                        "UbyPortu do jednoho pracovního postupu. Neprovádí výpočet místního "
                        "poplatku z pobytu a na veřejné stránce tuto funkci ani neslibuje."
                    ),
                ],
            },
            {
                "heading": "Rezervace se objeví z kalendáře",
                "paragraphs": [
                    (
                        "iCal export z Airbnb, Booking.com nebo jiného rezervačního portálu "
                        "předá datum příjezdu a odjezdu. UbyHost díky tomu ví, že se pobyt blíží. "
                        "Kalendář obvykle nepředává jméno, e-mail ani počet hostů."
                    ),
                ],
            },
            {
                "heading": "Host vyplní údaje před příjezdem",
                "paragraphs": [
                    (
                        "Každé ubytování má stálý soukromý odkaz, který lze vložit do zprávy "
                        "hostům. Host si vybere svůj pobyt, vyplní potřebné údaje a formulář "
                        "podepíše. Ubytovatel tak nemusí údaje znovu přepisovat."
                    ),
                    (
                        "UbyHost nepřijímá nové fotografie pasů. Formulář sbírá textové údaje "
                        "potřebné pro evidenci a hlášení; doklad lze případně ověřit osobně."
                    ),
                ],
            },
            {
                "heading": "Fronta ukáže, čemu věnovat pozornost",
                "paragraphs": [
                    (
                        "Místo procházení tabulek vidíte pobyty, kde formulář chybí, čeká na "
                        "podpis nebo je připravený k odeslání. U hotových hlášení zůstává "
                        "doručenka a technická odpověď UbyPortu."
                    ),
                ],
            },
            {
                "heading": "Na co myslet při výběru systému",
                "paragraphs": [
                    (
                        "Ověřte si, odkud systém získává rezervace, jak hosté opravují údaje, "
                        "zda rozlišuje české a zahraniční hosty, jak chrání přístup k formulářům "
                        "a zda po odeslání uchovává skutečný doklad o přijetí."
                    ),
                ],
            },
        ],
        "checklist": [
            "online formulář použitelný na telefonu",
            "soukromé odkazy a nezbytné cookies místo marketingového sledování",
            "synchronizace iCal kalendářů",
            "chronologická evidence hostů a export",
            "návaznost na UbyPort a uchování doručenek",
        ],
        "official_url": "https://ipc.gov.cz/pro-ubytovatele/obecne-informace-pro-ubytovatele/",
    },
}

ENGLISH_GUIDES = {
    "hlaseni-cizincu-ubyport": {
        "title": "Reporting foreign guests through UbyPort: a host’s guide",
        "updated": "2026-09-19",
        "description": (
            "UbyPort for Airbnb and Booking.com hosts in Czechia: property registration, "
            "the three-working-day deadline, web-service access, receipts, and errors."
        ),
        "eyebrow": "UbyPort for Airbnb and short-term rentals",
        "lede": (
            "A practical guide for Airbnb, Booking.com, and short-term-rental hosts: "
            "what to prepare and how to verify that the Czech Police accepted a report."
        ),
        "sections": [
            {
                "heading": "Who accommodation providers report and when",
                "paragraphs": [
                    (
                        "According to official guidance, an accommodation provider must notify "
                        "the Police of the Czech Republic of a foreign national’s accommodation "
                        "within three working days. Businesses providing accommodation submit "
                        "the notification through the UbyPort internet application."
                    ),
                    (
                        "Always check the current government guidance for the duty and exact "
                        "data required in your situation. UbyHost is a technical tool, not "
                        "legal advice."
                    ),
                ],
            },
            {
                "heading": "1. Register the accommodation facility in UbyPort",
                "paragraphs": [
                    (
                        "First, register the specific accommodation facility. UbyPort works "
                        "with facility details such as IDUB, the assigned code, name, address, "
                        "and contact. These details must match the register when a report is sent."
                    ),
                ],
            },
            {
                "heading": "2. Request web-service access for automatic reporting",
                "paragraphs": [
                    (
                        "The credentials used to sign in to the portal are not the same as the "
                        "credentials for automated data entry. Direct reporting from an "
                        "application requires separate UbyPort web-service credentials."
                    ),
                    (
                        "Enter them for the relevant property in UbyHost. The password is not "
                        "shown in the workspace, and each facility can have its own registration."
                    ),
                ],
            },
            {
                "heading": "3. Collect complete, signed guest details",
                "paragraphs": [
                    (
                        "Before arrival, the guest opens a private form on a phone or computer. "
                        "UbyHost checks required fields and the signature and keeps the form with "
                        "the correct stay. Airbnb and Booking.com iCal calendars provide stay "
                        "dates, not the guest’s personal details."
                    ),
                ],
            },
            {
                "heading": "4. Check the receipt, not only the Send button",
                "paragraphs": [
                    (
                        "Success means UbyPort accepted the record. UbyHost therefore keeps the "
                        "response and delivery receipt with each submission. If UbyPort rejects "
                        "a record, the exact error remains available so the facility or guest "
                        "details can be corrected."
                    ),
                    (
                        "Repeatedly sending the same record is not a safe way to correct it. "
                        "First verify whether the report was already accepted."
                    ),
                ],
            },
        ],
        "checklist": [
            "an accommodation facility registered in UbyPort",
            "IDUB, code, name, and address matching the register",
            "separate web-service access for automatic reporting",
            "complete and signed foreign-guest details",
            "the delivery receipt or exact error checked after submission",
        ],
        "official_url": "https://ipc.gov.cz/en/accommodation-providers/general-information-for-accommodation-providers/",
    },
    "online-ubytovaci-kniha": {
        "title": "Online guest book: accommodation records without paperwork",
        "updated": "2026-09-19",
        "description": (
            "How an online guest and house book, pre-arrival form, accommodation records, "
            "and foreign-guest reporting through UbyPort work together."
        ),
        "eyebrow": "Guide for short-term accommodation",
        "lede": (
            "Good online records do not begin by copying a passport at reception. They begin "
            "with a reservation, a private guest form, and a clear view of what is still missing."
        ),
        "sections": [
            {
                "heading": "What an online guest book handles",
                "paragraphs": [
                    (
                        "Accommodation providers need to connect each stay with the accommodated "
                        "people and keep records clearly and chronologically. Foreign guests also "
                        "have to be reported to the Czech Police. Exact duties vary by the type "
                        "of accommodation and guest, so verify them with the relevant authorities."
                    ),
                    (
                        "UbyHost brings reservations, guest forms, the house book, and UbyPort "
                        "responses into one workflow. It does not calculate the local accommodation "
                        "fee and does not advertise that unsupported feature."
                    ),
                ],
            },
            {
                "heading": "The stay appears from a booking calendar",
                "paragraphs": [
                    (
                        "An iCal export from Airbnb, Booking.com, or another booking platform "
                        "provides arrival and departure dates. UbyHost can then see that a stay "
                        "is approaching. The calendar normally provides no name, email address, "
                        "or guest count."
                    ),
                ],
            },
            {
                "heading": "The guest provides details before arrival",
                "paragraphs": [
                    (
                        "Each property has one stable private link that can be included in guest "
                        "messages. The guest selects their stay, completes the required details, "
                        "and signs the form, so the provider does not have to copy everything again."
                    ),
                    (
                        "UbyHost does not accept new passport photographs. The form collects the "
                        "text details needed for records and reporting; the document can be checked "
                        "in person when appropriate."
                    ),
                ],
            },
            {
                "heading": "A queue shows what needs attention",
                "paragraphs": [
                    (
                        "Instead of searching spreadsheets, providers see stays where a form is "
                        "missing, waiting for a signature, or ready to report. Completed reports "
                        "retain the UbyPort delivery receipt and technical response."
                    ),
                ],
            },
            {
                "heading": "What to consider when choosing a system",
                "paragraphs": [
                    (
                        "Check where reservations come from, how guests correct details, whether "
                        "the system distinguishes Czech and foreign guests, how private forms are "
                        "protected, and whether it retains real proof of acceptance after reporting."
                    ),
                ],
            },
        ],
        "checklist": [
            "a mobile-friendly online form",
            "private links and necessary cookies instead of marketing tracking",
            "iCal calendar synchronization",
            "chronological guest records and exports",
            "UbyPort integration and retained delivery receipts",
        ],
        "official_url": "https://ipc.gov.cz/en/accommodation-providers/general-information-for-accommodation-providers/",
    },
}

GUIDE_TRANSLATIONS = {"cs": GUIDES, "en": ENGLISH_GUIDES}
