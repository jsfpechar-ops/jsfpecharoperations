"""Host-facing UI strings in English and Czech."""
from __future__ import annotations

from typing import Dict

from fastapi import Request

from .terms_i18n import TERMS_STRINGS

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
        "data.menu": "Import & export",
        "data.export_csv_title": "Export CSV",
        "data.export_csv_help": "Choose the date range to include in the export.",
        "data.export_csv_download": "Download",
        "data.export_csv_cancel": "Cancel",
        "csv.export_stays": "Export stays (CSV)",
        "csv.import_stays": "Import stays (CSV)",
        "csv.sample_stays": "Download sample file",
        "csv.download": "Export spreadsheet (CSV)",
        "csv.import": "Import paper records (CSV)",
        "csv.sample_housebook": "Download import template",
        "csv.download_pdfs": "Download PDF bundle (inspection)",
        "reports.download_receipts": "Download Doručenky (ZIP)",
        "reports.download_receipts_hint": "One PDF per successful transmission, built on disk to stay lightweight.",
        "housebook.legal_title": "Your legal duty — read this",
        "housebook.legal_body": (
            "Under § 101 of Act No. 326/1999 Coll., you must keep a house book (domovní kniha) for "
            "six years after the last entry and present it at a police inspection. A guest's signed "
            "registration form counts as a house-book page."
        ),
        "housebook.legal_paper": (
            "UbyHost helps you maintain the register digitally. It does not replace paper you already "
            "have: keep any original signed forms, ledgers, or binders you used before this app in a "
            "safe place for the full retention period."
        ),
        "housebook.legal_inspection": (
            "At inspection the officer may ask for written records. Export CSV for a spreadsheet view, "
            "or download signed PDFs (one file per guest) and print or store them offline. A screen "
            "alone may not be accepted."
        ),
        "housebook.legal_import": (
            "Had a paper house book? Use Import to digitise old rows without retyping — download the "
            "import template for the exact column format."
        ),
        "housebook.import_paper": "Import paper records",
        "housebook.pdf_hint": (
            "PDF bundle builds one guest form at a time on the server (low memory). Narrow the filter "
            "if you have many entries — max %(limit)s per download."
        ),
        "housebook.filter_footer": "Exports use the current filter.",
        "csv.button": "Import & export",
        "host.signature_title": "Guest signature",
        "host.signature_help": (
            "Required by Czech law (§ 101–103, Act 326/1999 Coll.). The guest must sign, or you must "
            "keep a matching paper form on file. Unsigned records cannot be reported to UbyPort."
        ),
        "host.signature_missing": "Please sign before saving.",
        "host.signature_kept": "Signature saved. Sign again only if you need to change it.",
        "host.signature_clear": "Clear",
        "host.verify_title": "ID check",
        "host.verify_in_person": (
            "You are responsible for accurate records. Compare the travel document when you can; "
            "sending to UbyPort also records your confirmation."
        ),
        "host.verify_help": "Optional: open the guest form to view an uploaded ID photo.",
        "host.verify_confirm": "I checked this guest's ID against the details above.",
        "host.verify_button": "Mark ID checked",
        "host.verify_pending": "ID not checked",
        "host.verify_view_photo": "View uploaded ID",
        "host.verify_footnote": "Uploaded ID photos are deleted when you mark the check.",
        "host.verify_waiting_photo": "No ID photo uploaded — you can still mark the check in person.",
        "host.verify_done": "ID checked on",
        "host.verify_host_entry": (
            "When you enter a guest by hand you confirm the details against their document in "
            "person. The record is marked verified on save."
        ),
        "housebook.legal_footnote": (
            "You remain the data controller. UbyHost is software only — not legal advice, not a "
            "substitute for signed paper you already hold, and not a guarantee the police will accept "
            "a screen instead of written records."
        ),
        "send.this_stay": "Send this stay",
        "send.all_ready": "Send all ready stays",
        "send.all_ready_hint": "Reports every stay that is complete and waiting for your approval",
        "send.filled_forms": "Send filled forms",
        "send.filled_forms_hint": "Submit every completed guest form on this stay to UbyPort",
        "send.guests_count": "Send %(count)s guest(s) on this stay",
        "status.ready_manual": "Ready — you send",
        "status.ready_manual_tip": "Guest forms are complete. Click Send because this property uses manual reporting.",
        "status.ready_immediate": "Verified — auto-send",
        "status.ready_immediate_tip": "Forms complete — UbyPort sends automatically when automation allows.",
        "status.awaiting_verification": "Optional ID check",
        "status.awaiting_verification_tip": "Guest forms are complete. Send when ready, or mark ID checked first.",
        "stay.detail.note.immediate": "after guest forms are complete",
        "legal.footer_short": "Legal",
        "legal.footer_nav_label": "Legal",
        "terms.footer_short": "Terms",
        "privacy.footer_short": "Privacy",
        "dpa.footer_short": "DPA",
        "status.waiting_guest": "Waiting for guest",
        "status.waiting_guest_tip": "Guest forms are not complete yet.",
        "status.waiting_signature": "Waiting for signature",
        "status.waiting_signature_tip": "Guest forms are not signed yet.",
        "status.ready_scheduled": "Ready — scheduled",
        "status.ready_scheduled_tip": "Will go out automatically after the delay set on the property.",
        "status.demo_preview": "Preview only",
        "status.demo_preview_tip": "Demo data is never sent to the police.",
        "dashboard.reporting_modes": "How sending works",
        "dashboard.reporting_modes_body": (
            "You must verify each passport before reporting. Manual waits for your Send click. "
            "Scheduled sends after check-in plus a delay, once verified. Auto-after-verify sends "
            "right after you confirm each guest."
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
        "guide.stays.csv": "Use Import & export in the filter bar to import past stays or export for your records.",
        "guide.stays.caption": "Import & export lives in the bottom-right of the filter panel on Stays and House book.",
        "guide.guests.body": (
            "Each stay gets a link guests open on their phone. They pick their dates, enter passport "
            "details, and sign. Czech guests still go in the house book but are not reported to the police."
        ),
        "guide.reporting.body": "Each property chooses how completed guest records reach UbyPort:",
        "guide.reporting.caption": (
            "Verify passport means you still need to check the ID photo. Nothing is sent to UbyPort "
            "until you confirm the details match the travel document."
        ),
        "guide.reporting.immediate": "After verification",
        "guide.reporting.immediate_detail": (
            "Sent automatically once you verify each guest against their passport. "
            "Never sent blindly from the guest form alone."
        ),
        "guide.legal.verification_title": "Verify every foreign guest",
        "guide.legal.verification_body": (
            "You are legally responsible for accurate police records. Guests upload a passport "
            "photo for your review; compare face and document number before confirming. The photo "
            "is deleted immediately after verification. If a guest refuses to show ID, you may "
            "refuse accommodation."
        ),
        "guide.reporting.scheduled": "Scheduled",
        "guide.reporting.scheduled_detail": "Batched after check-in plus your chosen delay.",
        "guide.reporting.manual": "Manual",
        "guide.reporting.manual_detail": "You click Send on the stay or use Send all ready stays.",
        "guide.reporting.bulk": (
            "Send all ready stays only sends stays that are complete and allowed by the automation mode — "
            "it never forces a partial stay."
        ),
        "guide.housebook.body": (
            "The house book lists every guest — Czech and foreign. Export CSV or download PDFs for "
            "inspections; import older paper records from Import & export in the filters."
        ),
        "guide.nav.legal": "Your legal duties",
        "guide.legal.lede": (
            "UbyHost helps you comply, but the accommodation provider remains legally responsible. "
            "Read this section carefully."
        ),
        "guide.legal.housebook_title": "House book (domovní kniha)",
        "guide.legal.housebook_body": (
            "Under § 101 of Act No. 326/1999 Coll. you must keep a register of accommodated foreigners "
            "with the same data as the registration form, plus stay dates. Entries must be current, "
            "legible, and chronological. Keep them for six years after the last entry."
        ),
        "guide.legal.paper_title": "Paper for police inspection",
        "guide.legal.paper_body": (
            "At inspection you must present the house book in written form. A screen alone is not enough. "
            "Download each guest's signed PDF (or the ZIP from House book) and store or print it. "
            "Signed registration forms count as house-book pages."
        ),
        "guide.legal.signature_title": "Signatures are mandatory",
        "guide.legal.signature_body": (
            "Every guest record needs a signature before it is complete. Prefer the guest link so they "
            "sign themselves. If you type details by hand, sign on the host form. UbyPort will not "
            "send unsigned foreign guests."
        ),
        "guide.legal.reporting_title": "Reporting foreigners to the police",
        "guide.legal.reporting_body": (
            "Report each foreign guest through UbyPort within three working days of check-in (§ 100). "
            "Czech nationals stay in the house book only — they are not reported to the Foreign Police."
        ),
        "guide.legal.retention_title": "Retention and GDPR",
        "guide.legal.retention_body": (
            "Guest data is processed to meet your legal obligation (GDPR Art. 6(1)(c)). Keep records "
            "for six years. After that, delete them unless another law requires longer storage."
        ),
        "guide.legal.disclaimer_title": "About UbyHost (important)",
        "guide.legal.disclaimer_body": (
            "UbyHost is software operated by Josef Pechar, IČO 24005169 (see Legal notice). It is "
            "provided as-is, does not provide legal advice, does not act as your data controller, and "
            "does not guarantee acceptance by the police or UbyPort. You remain responsible for correct "
            "data, timely reporting, signed forms, backups, and presenting records at inspection. "
            "When in doubt, contact the Foreign Police (reguby@pcr.cz) or a qualified adviser."
        ),
        "legal.page_title": "Legal notice",
        "legal.page_lede": "Who operates UbyHost and how that relates to your duties as a host.",
        "legal.operator_title": "Software operator",
        "legal.operator_name": "Name",
        "legal.operator_address": "Registered address",
        "legal.operator_contact": "Contact",
        "legal.operator_registry": "Public register",
        "legal.roles_title": "Two different roles",
        "legal.roles_body": (
            "You (or the legal entity on each property) are the data controller for guest personal data "
            "and the accommodation provider under Czech law. Josef Pechar, IČO 24005169, operates the "
            "UbyHost software only. When you use the hosted service, the operator processes guest data "
            "on your instructions to run the application, store records, and transmit reports to UbyPort."
        ),
        "legal.software_title": "What UbyHost is",
        "legal.software_body": (
            "UbyHost is a technical tool for house books, guest forms, and UbyPort reporting. It is not "
            "legal advice, not a substitute for paper records you must keep, and not a guarantee that the "
            "police will accept any submission. Each host remains responsible for accuracy, deadlines, "
            "signatures, retention, and inspection."
        ),
        "legal.disclaimer_title": "Disclaimer",
        "legal.disclaimer_body": (
            "The software is provided without warranty to the extent permitted by law. Liability is limited "
            "to mandatory statutory rules. Nothing here changes who must register guests or keep the house "
            "book — that remains the accommodation provider."
        ),
        "legal.back_login": "Back to login",
        "legal.footer_link": "Legal notice",
        "legal.settings_title": "Software operator",
        "legal.settings_body": (
            "UbyHost is operated by %(name)s, IČO %(ico)s. Guest data controllers are your legal entities "
            "configured per property."
        ),
        "legal.settings_contact_missing": (
            "Set UBYHOST_OPERATOR_EMAIL in the server environment for a public support address."
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
        "data.menu": "Import a export",
        "data.export_csv_title": "Export CSV",
        "data.export_csv_help": "Vyberte rozsah dat, který chcete exportovat.",
        "data.export_csv_download": "Stáhnout",
        "data.export_csv_cancel": "Zrušit",
        "csv.export_stays": "Export pobytů (CSV)",
        "csv.import_stays": "Import pobytů (CSV)",
        "csv.sample_stays": "Stáhnout vzorový soubor",
        "csv.download": "Export tabulky (CSV)",
        "csv.import": "Import papírové evidence (CSV)",
        "csv.sample_housebook": "Stáhnout vzor pro import",
        "csv.download_pdfs": "Stáhnout balíček PDF (kontrola)",
        "reports.download_receipts": "Stáhnout doručenky (ZIP)",
        "reports.download_receipts_hint": "Jedno PDF za každé úspěšné odeslání, sestavené na disku bez zbytečné paměti.",
        "housebook.legal_title": "Vaše zákonná povinnost — přečtěte",
        "housebook.legal_body": (
            "Podle § 101 zákona č. 326/1999 Sb. musíte vést domovní knihu po dobu šesti let od posledního "
            "zápisu a předložit ji při kontrole. Podepsaný registrační formulář hosta se počítá jako "
            "stránka domovní knihy."
        ),
        "housebook.legal_paper": (
            "UbyHost vám pomáhá vést evidenci digitálně. Nenahrazuje papír, který už máte: uschovejte "
            "původní podepsané formuláře, knihy nebo pořadače z doby před aplikací po celou zákonnou "
            "dobu."
        ),
        "housebook.legal_inspection": (
            "Při kontrole může úředník požadovat písemnou podobu. Exportujte CSV pro přehled v tabulce, "
            "nebo stáhněte podepsaná PDF (jeden soubor na hosta) a uložte či vytiskněte. Samotná "
            "obrazovka nemusí stačit."
        ),
        "housebook.legal_import": (
            "Vedli jste papírovou domovní knihu? Importem doplníte starší záznamy bez přepisování — "
            "vzor souboru najdete v menu Import a export."
        ),
        "housebook.import_paper": "Importovat papírovou evidenci",
        "housebook.pdf_hint": (
            "Balíček PDF se na serveru skládá postupně po jednom hostu (nízká spotřeba paměti). Při "
            "velkém počtu záznamů zužte filtr — max. %(limit)s na jedno stažení."
        ),
        "housebook.filter_footer": "Exporty používají aktuální filtr.",
        "csv.button": "Import a export",
        "host.signature_title": "Podpis hosta",
        "host.signature_help": (
            "Vyžaduje zákon (§ 101–103, zákon č. 326/1999 Sb.). Host se musí podepsat, nebo musíte "
            "mít shodný papírový formulář. Nepodepsané záznamy nelze odeslat do UbyPortu."
        ),
        "host.signature_missing": "Před uložením se prosím podepište.",
        "host.signature_kept": "Podpis je uložený. Podepište znovu jen při změně.",
        "host.signature_clear": "Vymazat",
        "host.verify_title": "Kontrola dokladu",
        "host.verify_in_person": (
            "Za správnost údajů odpovídáte vy. Porovnejte doklad, když můžete; odeslání do UbyPortu "
            "také zaznamená vaše potvrzení."
        ),
        "host.verify_help": "Volitelně otevřete formulář hosta a zobrazte nahranou fotografii dokladu.",
        "host.verify_confirm": "Zkontroloval(a) jsem doklad hosta proti údajům výše.",
        "host.verify_button": "Označit doklad zkontrolovaný",
        "host.verify_pending": "Doklad nezkontrolován",
        "host.verify_view_photo": "Zobrazit nahraný doklad",
        "host.verify_footnote": "Nahrané fotografie dokladu se po označení kontroly smažou.",
        "host.verify_waiting_photo": "Host nenahrál fotografii — kontrolu můžete označit i osobně.",
        "host.verify_done": "Doklad zkontrolován",
        "host.verify_host_entry": (
            "Když zadáváte hosta ručně, potvrzujete údaje proti dokladu na místě. Záznam se "
            "označí jako ověřený při uložení."
        ),
        "housebook.legal_footnote": (
            "Zůstáváte správcem údajů. UbyHost je pouze software — ne právní poradenství, nenahrazuje "
            "papíry, které už máte, a nezaručuje, že policie přijme obrazovku místo listinné evidence."
        ),
        "nav.guide": "Nápověda",
        "send.this_stay": "Odeslat tento pobyt",
        "send.all_ready": "Odeslat všechny připravené",
        "send.all_ready_hint": "Odešle každý pobyt, který je kompletní a čeká na vaše potvrzení",
        "send.filled_forms": "Odeslat vyplněné formuláře",
        "send.filled_forms_hint": "Odešle každý hotový formulář hosta na tomto pobytu do UbyPortu",
        "send.guests_count": "Odeslat %(count)s host(y) na tomto pobytu",
        "status.ready_manual": "Připraveno — ručně",
        "status.ready_manual_tip": "Formuláře jsou hotové. Klikněte na Odeslat, protože ubytování má ruční režim.",
        "status.ready_immediate": "Ověřeno — automaticky",
        "status.ready_immediate_tip": "Formuláře hotové — UbyPort odešle automaticky podle režimu.",
        "status.awaiting_verification": "Volitelná kontrola dokladu",
        "status.awaiting_verification_tip": (
            "Formuláře jsou hotové. Odešlete, až budete připraveni, nebo nejdřív označte kontrolu dokladu."
        ),
        "stay.detail.note.immediate": "po dokončení formulářů hostů",
        "legal.footer_short": "Právní",
        "legal.footer_nav_label": "Právní informace",
        "terms.footer_short": "Podmínky",
        "privacy.footer_short": "Soukromí",
        "dpa.footer_short": "DPA",
        "status.waiting_guest": "Čeká na hosta",
        "status.waiting_guest_tip": "Formuláře hostů ještě nejsou hotové.",
        "status.waiting_signature": "Čeká na podpis",
        "status.waiting_signature_tip": "Formuláře ještě nejsou podepsané.",
        "status.ready_scheduled": "Připraveno — naplánováno",
        "status.ready_scheduled_tip": "Odejde automaticky po zvolené prodlevě od příjezdu.",
        "status.demo_preview": "Jen náhled",
        "status.demo_preview_tip": "Ukázková data se na policii nikdy neodešlou.",
        "dashboard.reporting_modes": "Jak funguje odesílání",
        "dashboard.reporting_modes_body": (
            "Před hlášením musíte ověřit každý pas. Ruční čeká na Odeslat. Naplánované odešle po "
            "prodlevě od příjezdu, až po ověření. Auto po ověření odešle hned po vašem potvrzení."
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
        "guide.stays.csv": "Import a export v panelu filtrů slouží k importu starších pobytů nebo exportu.",
        "guide.stays.caption": "Import a export je vpravo dole v panelu filtrů u Pobytů a Domovní knihy.",
        "guide.guests.body": (
            "Každý pobyt má odkaz pro hosty na telefonu. Vyberou datum, vyplní pas a podepíší se."
        ),
        "guide.reporting.body": "Každé ubytování volí, jak se hotová hlášení dostanou do UbyPortu:",
        "guide.reporting.caption": (
            "Ověřit pas znamená, že ještě musíte zkontrolovat fotografii dokladu. Do UbyPortu se nic "
            "neodešle, dokud nepotvrdíte shodu s cestovním dokladem."
        ),
        "guide.reporting.immediate": "Po ověření",
        "guide.reporting.immediate_detail": (
            "Odešle se automaticky po ověření hosta proti pasu. Nikdy ne slepě z formuláře hosta."
        ),
        "guide.legal.verification_title": "Ověřte každého cizince",
        "guide.legal.verification_body": (
            "Za správnost policejních záznamů odpovídáte vy. Hosté nahrají fotografii pasu ke kontrole; "
            "porovnejte obličej a číslo dokladu před potvrzením. Fotografie se po ověření okamžitě smaže. "
            "Odmítne-li host doklad ukázat, můžete odmítnout ubytování."
        ),
        "guide.reporting.scheduled": "Naplánované",
        "guide.reporting.scheduled_detail": "Dávka po příjezdu a zvolené prodlevě.",
        "guide.reporting.manual": "Ruční",
        "guide.reporting.manual_detail": "Kliknete Odeslat u pobytu nebo Odeslat všechny připravené.",
        "guide.reporting.bulk": (
            "Hromadné odeslání jen u kompletních pobytů povolených režimem — nikdy ne částečných."
        ),
        "guide.housebook.body": (
            "Domovní kniha obsahuje všechny hosty — Čechy i cizince. CSV nebo PDF pro kontroly; "
            "import starších záznamů ve filtrech."
        ),
        "guide.nav.legal": "Vaše právní povinnosti",
        "guide.legal.lede": (
            "UbyHost pomáhá s plněním povinností, ale ubytovatel zůstává právně odpovědný. "
            "Tuto část si pečlivě přečtěte."
        ),
        "guide.legal.housebook_title": "Domovní kniha",
        "guide.legal.housebook_body": (
            "Podle § 101 zákona č. 326/1999 Sb. vedete evidenci ubytovaných cizinců v rozsahu "
            "přihlašovacího tiskopisu a termínů pobytu. Záznamy musí být aktuální, přehledné a "
            "chronologické. Uchovávejte je 6 let od posledního zápisu."
        ),
        "guide.legal.paper_title": "Listinná podoba při kontrole",
        "guide.legal.paper_body": (
            "Při kontrole musíte předložit domovní knihu v listinné podobě. Obrazovka sama o sobě "
            "nestačí. Stáhněte podepsané PDF každého hosta (nebo ZIP z Domovní knihy) a archivujte "
            "nebo vytiskněte. Podepsané tiskopisy nahrazují stránky knihy."
        ),
        "guide.legal.signature_title": "Podpis je povinný",
        "guide.legal.signature_body": (
            "Každý záznam hosta vyžaduje podpis, než je kompletní. Preferujte odkaz pro hosty. "
            "Při ručním zadání podepište na formuláři hostitele. UbyPort neodešle nepodepsané cizince."
        ),
        "guide.legal.reporting_title": "Hlášení cizinců policii",
        "guide.legal.reporting_body": (
            "Každého cizince nahlaste přes UbyPort do tří pracovních dnů od příjezdu (§ 100). "
            "Čeští hosté zůstávají jen v domovní knize — na cizineckou policii se nehlásí."
        ),
        "guide.legal.retention_title": "Uchovávání a GDPR",
        "guide.legal.retention_body": (
            "Údaje zpracováváte pro splnění právní povinnosti (GDPR čl. 6 odst. 1 písm. c). "
            "Uchovávejte 6 let, poté mažte, pokud jiný zákon nevyžaduje déle."
        ),
        "guide.legal.disclaimer_title": "O UbyHostu (důležité)",
        "guide.legal.disclaimer_body": (
            "UbyHost provozuje Josef Pechar, IČO 24005169 (viz Právní informace). Je to technický "
            "nástroj poskytovaný tak, jak je. Neposkytuje právní poradenství, "
            "není správcem údajů a nezaručuje přijetí policií nebo UbyPortem. Odpovídáte za správnost "
            "dat, včasné hlášení, podepsané formuláře, zálohy a předložení evidence při kontrole. "
            "V pochybnostech kontaktujte cizineckou policii (reguby@pcr.cz) nebo odborného poradce."
        ),
        "legal.page_title": "Právní informace",
        "legal.page_lede": "Kdo provozuje UbyHost a jak to souvisí s vaší odpovědností jako ubytovatele.",
        "legal.operator_title": "Provozovatel software",
        "legal.operator_name": "Jméno",
        "legal.operator_address": "Sídlo",
        "legal.operator_contact": "Kontakt",
        "legal.operator_registry": "Veřejný rejstřík",
        "legal.roles_title": "Dvě různé role",
        "legal.roles_body": (
            "Vy (nebo právnická osoba u každého ubytování) jste správcem osobních údajů hostů a "
            "poskytovatelem ubytování podle českého práva. Josef Pechar, IČO 24005169, provozuje "
            "pouze software UbyHost. Při používání hostované služby zpracovává údaje hostů na váš pokyn "
            "kvůli chodu aplikace, uložení záznamů a odeslání hlášení do UbyPortu."
        ),
        "legal.software_title": "Co je UbyHost",
        "legal.software_body": (
            "UbyHost je technický nástroj pro domovní knihu, formuláře hostů a hlášení do UbyPortu. "
            "Není právní poradenství, nenahrazuje papírovou evidenci, kterou musíte uchovávat, a "
            "nezaručuje přijetí hlášení policií. Za správnost, lhůty, podpisy, uchovávání a kontrolu "
            "odpovídá vždy ubytovatel."
        ),
        "legal.disclaimer_title": "Vyloučení odpovědnosti",
        "legal.disclaimer_body": (
            "Software je poskytován bez záruky v rozsahu povoleném zákonem. Odpovědnost je omezena "
            "povinnými zákonnými pravidly. Tím se nemění, kdo musí hosty registrovat a vést domovní "
            "knihu — to zůstává na poskytovateli ubytování."
        ),
        "legal.back_login": "Zpět na přihlášení",
        "legal.footer_link": "Právní informace",
        "legal.settings_title": "Provozovatel software",
        "legal.settings_body": (
            "UbyHost provozuje %(name)s, IČO %(ico)s. Správci údajů hostů jsou vaše právnické osoby "
            "nastavené u jednotlivých ubytování."
        ),
        "legal.settings_contact_missing": (
            "Pro veřejný kontakt nastavte UBYHOST_OPERATOR_EMAIL v prostředí serveru."
        ),
        "guide.demo.body": (
            "Ukázková data lze načíst kdykoli. Na skutečnou policii se nikdy neodešlou."
        ),
    },
}

for _lang, _terms in TERMS_STRINGS.items():
    STRINGS.setdefault(_lang, {}).update(_terms)


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
