"""Host-facing UI strings in English and Czech."""
from __future__ import annotations

from typing import Dict

from fastapi import Request

LANG_COOKIE = "ubyhost_lang"
LANGUAGES = ("en", "cs")
DEFAULT_LANGUAGE = "en"

STRINGS: Dict[str, Dict[str, str]] = {
    "en": {
        "lang.en": "EN",
        "lang.cs": "CZ",
        "lang.switch": "Language",
        "nav.guide": "Help",
        "nav.operations": "Operations",
        "nav.records": "Records",
        "nav.setup": "Setup",
        "nav.overview": "Overview",
        "nav.stays": "Stays",
        "nav.reports": "Reports",
        "nav.housebook": "House book",
        "nav.properties": "Properties",
        "nav.entities": "Legal entities",
        "nav.settings": "Settings",
        "nav.users": "Users",
        "nav.logout": "Log out",
        "nav.administrator": "Administrator",
        "login.title": "Your guest reporting workspace.",
        "login.lede": "Log in to your UbyHost account",
        "login.username": "Username",
        "login.password": "Password",
        "login.username_ph": "Enter your username…",
        "login.password_ph": "Enter your password…",
        "login.remember": "Remember me for 30 days",
        "login.submit": "Continue",
        "login.footnote": (
            "No public sign-up. UbyHost is invite-only — ask your administrator for an account."
        ),
        "login.hero_title": "Guest reporting, handled for you.",
        "login.hero_body": (
            "Calendars, guest forms, house book, and UbyPort submissions in one calm workspace — "
            "built for Czech short-term hosts."
        ),
        "demo.load": "Explore with demo data",
        "demo.load_detail": (
            "One sample property with stays and guests. Nothing is sent to the police unless you "
            "submit real data yourself."
        ),
        "demo.clear": "Clear demo data",
        "csv.export_stays": "Export stays",
        "csv.import_stays": "Import stays",
        "csv.sample_stays": "Sample CSV",
        "csv.download": "Download CSV",
        "csv.import": "Import CSV",
        "csv.sample_housebook": "Sample CSV",
        "csv.button": "CSV",
        "send.this_stay": "Send this stay",
        "send.all_ready": "Send all ready stays",
        "send.all_ready_hint": "Reports every stay that is complete and waiting for your approval",
        "send.filled_forms": "Send filled forms",
        "send.filled_forms_hint": "Submit every completed guest form on this stay to UbyPort",
        "status.ready_manual": "Ready — you send",
        "status.ready_manual_tip": "Guest forms are complete. Click Send because this property uses manual reporting.",
        "status.ready_immediate": "Forms complete — auto-send",
        "status.ready_immediate_tip": "Guest forms are done. UbyPort submission happens automatically.",
        "status.waiting_signature": "Waiting for signature",
        "status.waiting_signature_tip": "Guest forms are not signed yet. Sends automatically once each guest signs.",
        "status.ready_scheduled": "Ready — scheduled",
        "status.ready_scheduled_tip": "Will go out automatically after the delay set on the property.",
        "status.demo_preview": "Preview only",
        "status.demo_preview_tip": "Demo data is never sent to the police.",
        "dashboard.reporting_modes": "How sending works",
        "dashboard.reporting_modes_body": (
            "Immediate sends when a guest signs. Scheduled waits a few hours after check-in. "
            "Manual waits for you — use Send on the stay or Send all ready stays above the list."
        ),
        "dashboard.minutes_saved": "~%(minutes)s min saved vs manual UbyPort entry",
        "celebration.title": "Well done!",
        "celebration.body": (
            "You have reported %(count)s guests through UbyHost — a %(milestone)s-guest milestone. "
            "Thank you for keeping everything in order."
        ),
        "celebration.dismiss": "Thanks!",
        "guide.title": "Help & guide",
        "guide.lede": "Everything you need to run guest reporting calmly, from setup to the house book.",
        "guide.nav.overview": "Overview",
        "guide.nav.setup": "First-time setup",
        "guide.nav.stays": "Stays & calendars",
        "guide.nav.guests": "Guest forms",
        "guide.nav.reporting": "Police reporting",
        "guide.nav.housebook": "House book",
        "guide.nav.demo": "Demo data",
        "guide.overview.body": (
            "Overview shows what needs attention now: missing guest forms, stays ready to report, "
            "and deadlines. Stays lists every booking; Reports keeps Doručenka receipts."
        ),
        "guide.overview.caption": "The next-up card shows the most urgent stay and its send button.",
        "guide.setup.step1_title": "Legal entity",
        "guide.setup.step1": "The company or person registered with the police.",
        "guide.setup.step2_title": "Property",
        "guide.setup.step2": "IDUB, mark, and address must match UbyPort exactly.",
        "guide.setup.step3_title": "Calendars",
        "guide.setup.step3": "Paste Airbnb or Booking.com iCal export links.",
        "guide.setup.step4_title": "UbyPort credentials",
        "guide.setup.step4": "Enter your UBY-WS web-service login on the property page.",
        "guide.setup.step5_title": "Guest link",
        "guide.setup.step5": "Put the permalink in your check-in message on every portal.",
        "guide.stays.body": (
            "Stays arrive from calendars or manual entry. Open a row to add guests, copy the guest link, "
            "or send completed records."
        ),
        "guide.stays.csv": "Use CSV in the filter bar to import past stays or export for your records.",
        "guide.stays.caption": "CSV lives in the bottom-right of the filter panel on Stays and House book.",
        "guide.guests.body": (
            "Each stay gets a link guests open on their phone. They pick their dates, enter passport "
            "details, and sign. Czech guests still go in the house book but are not reported to the police."
        ),
        "guide.reporting.body": "Each property chooses how completed guest records reach UbyPort:",
        "guide.reporting.caption": (
            "Waiting for signature means guests still need to sign. Forms complete — auto-send means "
            "everything is filled in and UbyPort submission happens automatically."
        ),
        "guide.reporting.immediate": "Immediate",
        "guide.reporting.immediate_detail": "Sent as soon as the guest signs.",
        "guide.reporting.scheduled": "Scheduled",
        "guide.reporting.scheduled_detail": "Batched after check-in plus your chosen delay.",
        "guide.reporting.manual": "Manual",
        "guide.reporting.manual_detail": "You click Send on the stay or use Send all ready stays.",
        "guide.reporting.bulk": (
            "Send all ready stays only sends stays that are complete and allowed by the automation mode — "
            "it never forces a partial stay."
        ),
        "guide.housebook.body": (
            "The house book lists every guest. Export CSV for inspections; import older paper records "
            "from the CSV menu in the filters."
        ),
        "guide.demo.body": (
            "Load demo data anytime to explore with a sample flat. Demo guests are never sent to the real "
            "police register."
        ),
    },
    "cs": {
        "lang.en": "EN",
        "lang.cs": "CZ",
        "lang.switch": "Jazyk",
        "nav.operations": "Provoz",
        "nav.records": "Evidence",
        "nav.setup": "Nastavení účtu",
        "nav.overview": "Přehled",
        "nav.stays": "Pobyty",
        "nav.reports": "Hlášení",
        "nav.housebook": "Domovní kniha",
        "nav.properties": "Ubytování",
        "nav.entities": "Právnické osoby",
        "nav.settings": "Nastavení",
        "nav.users": "Uživatelé",
        "nav.logout": "Odhlásit se",
        "nav.administrator": "Správce",
        "login.title": "Váš pracovní prostor pro hlášení hostů.",
        "login.lede": "Přihlaste se do UbyHost",
        "login.username": "Uživatelské jméno",
        "login.password": "Heslo",
        "login.username_ph": "Zadejte uživatelské jméno…",
        "login.password_ph": "Zadejte heslo…",
        "login.remember": "Zapamatovat na 30 dní",
        "login.submit": "Pokračovat",
        "login.footnote": (
            "Veřejná registrace není k dispozici. UbyHost je pouze na pozvání — účet vám vytvoří správce."
        ),
        "login.hero_title": "Hlášení hostů bez zbytečné práce.",
        "login.hero_body": (
            "Kalendáře, formuláře hostů, domovní kniha a odeslání do UbyPortu na jednom místě — "
            "pro krátkodobé pronájmy v Česku."
        ),
        "demo.load": "Prohlédnout s ukázkovými daty",
        "demo.load_detail": (
            "Ukázkové ubytování s pobytem a hosty. Na policii se nic neodešle, dokud sami "
            "neodešlete skutečná data."
        ),
        "demo.clear": "Smazat ukázková data",
        "csv.export_stays": "Export pobytů",
        "csv.import_stays": "Import pobytů",
        "csv.sample_stays": "Vzorové CSV",
        "csv.download": "Stáhnout CSV",
        "csv.import": "Importovat CSV",
        "csv.sample_housebook": "Vzorové CSV",
        "csv.button": "CSV",
        "nav.guide": "Nápověda",
        "send.this_stay": "Odeslat tento pobyt",
        "send.all_ready": "Odeslat všechny připravené",
        "send.all_ready_hint": "Odešle každý pobyt, který je kompletní a čeká na vaše potvrzení",
        "send.filled_forms": "Odeslat vyplněné formuláře",
        "send.filled_forms_hint": "Odešle každý hotový formulář hosta na tomto pobytu do UbyPortu",
        "status.ready_manual": "Připraveno — ručně",
        "status.ready_manual_tip": "Formuláře jsou hotové. Klikněte na Odeslat, protože ubytování má ruční režim.",
        "status.ready_immediate": "Formuláře hotové — automaticky",
        "status.ready_immediate_tip": "Formuláře jsou vyplněné. Odeslání do UbyPortu proběhne automaticky.",
        "status.waiting_signature": "Čeká na podpis",
        "status.waiting_signature_tip": "Formuláře ještě nejsou podepsané. Po podpisu hosta se odešle automaticky.",
        "status.ready_scheduled": "Připraveno — naplánováno",
        "status.ready_scheduled_tip": "Odejde automaticky po zvolené prodlevě od příjezdu.",
        "status.demo_preview": "Jen náhled",
        "status.demo_preview_tip": "Ukázková data se na policii nikdy neodešlou.",
        "dashboard.reporting_modes": "Jak funguje odesílání",
        "dashboard.reporting_modes_body": (
            "Okamžité odešle po podpisu hosta. Naplánované počká po příjezdu. Ruční čeká na vás — "
            "použijte Odeslat u pobytu nebo Odeslat všechny připravené nad seznamem."
        ),
        "dashboard.minutes_saved": "~%(minutes)s min ušetřeno oproti ručnímu UbyPortu",
        "celebration.title": "Výborně!",
        "celebration.body": (
            "Přes UbyHost jste nahlásili %(count)s hostů — milník %(milestone)s hostů. "
            "Díky, že máte vše v pořádku."
        ),
        "celebration.dismiss": "Díky!",
        "guide.title": "Nápověda a průvodce",
        "guide.lede": "Vše pro klidné hlášení hostů — od nastavení po domovní knihu.",
        "guide.nav.overview": "Přehled",
        "guide.nav.setup": "První nastavení",
        "guide.nav.stays": "Pobyty a kalendáře",
        "guide.nav.guests": "Formuláře hostů",
        "guide.nav.reporting": "Hlášení na policii",
        "guide.nav.housebook": "Domovní kniha",
        "guide.nav.demo": "Ukázková data",
        "guide.overview.body": (
            "Přehled ukazuje, co vyžaduje pozornost: chybějící formuláře, připravená hlášení a termíny. "
            "Pobyty obsahují rezervace; Hlášení uchovává doručenky."
        ),
        "guide.overview.caption": "Karta Další na řadě ukazuje nejnaléhavější pobyt a tlačítko Odeslat.",
        "guide.setup.step1_title": "Právnická osoba",
        "guide.setup.step1": "Firma nebo osoba registrovaná u policie.",
        "guide.setup.step2_title": "Ubytování",
        "guide.setup.step2": "IDUB, značka a adresa musí přesně sedět s UbyPortem.",
        "guide.setup.step3_title": "Kalendáře",
        "guide.setup.step3": "Vložte exportní iCal odkazy z Airbnb nebo Booking.com.",
        "guide.setup.step4_title": "Přihlašovací údaje UbyPort",
        "guide.setup.step4": "Na stránce ubytování zadejte UBY-WS webovou službu.",
        "guide.setup.step5_title": "Odkaz pro hosty",
        "guide.setup.step5": "Permalink vložte do zprávy při příjezdu na všech portálech.",
        "guide.stays.body": (
            "Pobyty přicházejí z kalendářů nebo ručního zadání. Otevřete řádek pro hosty, odkaz nebo odeslání."
        ),
        "guide.stays.csv": "CSV v panelu filtrů slouží k importu starších pobytů nebo exportu.",
        "guide.stays.caption": "CSV je vpravo dole v panelu filtrů u Pobytů a Domovní knihy.",
        "guide.guests.body": (
            "Každý pobyt má odkaz pro hosty na telefonu. Vyberou datum, vyplní pas a podepíší se."
        ),
        "guide.reporting.body": "Každé ubytování volí, jak se hotová hlášení dostanou do UbyPortu:",
        "guide.reporting.caption": (
            "Čeká na podpis znamená, že host ještě nepodepsal. Formuláře hotové — automaticky znamená, "
            "že je vše vyplněné a odeslání do UbyPortu proběhne samo."
        ),
        "guide.reporting.immediate": "Okamžité",
        "guide.reporting.immediate_detail": "Odešle se hned po podpisu hosta.",
        "guide.reporting.scheduled": "Naplánované",
        "guide.reporting.scheduled_detail": "Dávka po příjezdu a zvolené prodlevě.",
        "guide.reporting.manual": "Ruční",
        "guide.reporting.manual_detail": "Kliknete Odeslat u pobytu nebo Odeslat všechny připravené.",
        "guide.reporting.bulk": (
            "Hromadné odeslání jen u kompletních pobytů povolených režimem — nikdy ne částečných."
        ),
        "guide.housebook.body": (
            "Domovní kniha obsahuje všechny hosty. CSV export pro kontroly; import starších záznamů ve filtrech."
        ),
        "guide.demo.body": (
            "Ukázková data lze načíst kdykoli. Na skutečnou policii se nikdy neodešlou."
        ),
    },
}


def normalise_language(value: str | None) -> str:
    value = (value or "").lower()[:2]
    return value if value in LANGUAGES else DEFAULT_LANGUAGE


def lang_from_request(request: Request) -> str:
    return normalise_language(request.cookies.get(LANG_COOKIE))


def translate(lang: str, key: str, **kwargs) -> str:
    table = STRINGS.get(normalise_language(lang), STRINGS[DEFAULT_LANGUAGE])
    fallback = STRINGS[DEFAULT_LANGUAGE]
    text = table.get(key, fallback.get(key, key))
    if not kwargs:
        return text
    try:
        return text % kwargs
    except (KeyError, TypeError, ValueError):
        return text
