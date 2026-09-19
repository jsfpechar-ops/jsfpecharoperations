"""Original Czech search guides grounded in official public information."""

GUIDES = {
    "hlaseni-cizincu-ubyport": {
        "title": "Hlášení cizinců přes UbyPort: postup pro ubytovatele",
        "description": (
            "Praktický postup pro hlášení ubytovaných cizinců přes UbyPort: registrace "
            "zařízení, lhůta, webová služba, doručenky a kontrola chyb."
        ),
        "eyebrow": "Průvodce pro ubytovatele",
        "lede": (
            "Co je potřeba připravit, jak se liší běžný účet od přístupu k webové službě "
            "a jak si pohlídat, že Policie ČR hlášení skutečně přijala."
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
