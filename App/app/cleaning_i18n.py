"""English and Czech cleaning copy, kept together for key parity."""
from __future__ import annotations

WORDS = {
    "test_schedule": ["Test schedule", "Zkušební rozpis"],
    "language": ["Language", "Jazyk"],
    "title": [
        "Cleaning",
        "Úklid"
    ],
    "subtitle": [
        "Upcoming turnovers, door codes and property instructions in one place.",
        "Nadcházející úklidy, kódy ke dveřím a pokyny na jednom místě."
    ],
    "schedule": [
        "Cleaning calendar",
        "Kalendář úklidů"
    ],
    "list": [
        "Cleaning dates",
        "Termíny úklidů"
    ],
    "add": [
        "Add cleaning",
        "Přidat úklid"
    ],
    "edit": [
        "Edit cleaning",
        "Upravit úklid"
    ],
    "settings": [
        "Property instructions & codes",
        "Pokyny a kódy ubytování"
    ],
    "share": [
        "Share schedule",
        "Sdílet rozpis"
    ],
    "back": [
        "Back to cleaning",
        "Zpět na úklidy"
    ],
    "skip": [
        "Skip to cleaning list",
        "Přejít na seznam úklidů"
    ],
    "property": [
        "Property / unit",
        "Ubytování / jednotka"
    ],
    "all": [
        "All properties",
        "Všechna ubytování"
    ],
    "date": [
        "Cleaning date",
        "Datum úklidu"
    ],
    "start": [
        "Start time (optional)",
        "Čas zahájení (nepovinné)"
    ],
    "end": [
        "End time (optional)",
        "Čas ukončení (nepovinné)"
    ],
    "notes": [
        "Cleaning notes",
        "Poznámky k úklidu"
    ],
    "notes_hint": [
        "Only cleaning instructions. Everything written here is visible to teams with your shared link.",
        "Pouze pokyny k úklidu. Vše zde uvedené uvidí tým se sdíleným odkazem."
    ],
    "instructions": [
        "Property instructions",
        "Pokyny pro ubytování"
    ],
    "steps": [
        "Instructions & steps",
        "Pokyny a postup"
    ],
    "no_instructions": [
        "No property instructions added.",
        "Pokyny pro ubytování nejsou vyplněné."
    ],
    "save": [
        "Save",
        "Uložit"
    ],
    "cancel": [
        "Cancel",
        "Zrušit"
    ],
    "delete": [
        "Remove cleaning",
        "Odstranit úklid"
    ],
    "delete_hint": [
        "Remove this cleaning from the schedule? The reservation stays unchanged.",
        "Odstranit tento úklid z rozpisu? Rezervace se nezmění."
    ],
    "automatic": [
        "After checkout",
        "Po odjezdu"
    ],
    "manual": [
        "Extra cleaning",
        "Mimořádný úklid"
    ],
    "moved": [
        "Rescheduled by host",
        "Termín upravil host"
    ],
    "checkout": [
        "Checkout",
        "Odjezd"
    ],
    "arrival": [
        "Next check-in",
        "Další příjezd"
    ],
    "no_arrival": [
        "Next arrival not scheduled",
        "Další příjezd není naplánovaný"
    ],
    "time_missing": [
        "Time not set",
        "Čas není nastaven"
    ],
    "anytime": [
        "Time to be arranged",
        "Čas dle domluvy"
    ],
    "window": [
        "Turnover window",
        "Čas mezi pobyty"
    ],
    "code": [
        "Door access code",
        "Kód ke dveřím"
    ],
    "no_code": [
        "Door code not set. Contact the host.",
        "Kód ke dveřím není nastavený. Kontaktujte hostitele."
    ],
    "manual_code": [
        "Saved manual code",
        "Ručně uložený kód"
    ],
    "permanent_code": [
        "Permanent TTLock code",
        "Trvalý kód TTLock"
    ],
    "create_code": [
        "Create permanent TTLock code",
        "Vytvořit trvalý kód TTLock"
    ],
    "code_hint": [
        "A permanent code stays valid until removed from the lock. Use a code dedicated to cleaning.",
        "Trvalý kód platí až do odstranění ze zámku. Použijte kód určený pouze pro úklid."
    ],
    "manual_hint": [
        "Enter an existing static door code. Saving it does not program the lock.",
        "Zadejte existující stálý kód. Uložení kód do zámku nenahraje."
    ],
    "code_pending": [
        "TTLock code is being prepared. The current code stays available.",
        "Kód TTLock se připravuje. Současný kód zůstává dostupný."
    ],
    "code_failed": [
        "TTLock could not confirm the code. Retry or save a manual code.",
        "TTLock vytvoření kódu nepotvrdil. Zkuste to znovu nebo uložte ruční kód."
    ],
    "remove_code": [
        "Remove saved code",
        "Odstranit uložený kód"
    ],
    "remove_code_hint": [
        "Hide this code and revoke it through TTLock if managed by UbyHost? A manual code must be removed from the lock separately.",
        "Skrýt kód a zrušit ho přes TTLock, pokud jej spravuje UbyHost? Ruční kód je třeba ze zámku odstranit zvlášť."
    ],
    "revocation_failed": [
        "A previous TTLock code could not be revoked. Check it in the TTLock app.",
        "Předchozí kód TTLock se nepodařilo zrušit. Zkontrolujte jej v aplikaci TTLock."
    ],
    "lock_setup": [
        "Connect an authorized TTLock lock in property settings first.",
        "Nejprve připojte autorizovaný zámek TTLock v nastavení ubytování."
    ],
    "lock_link": [
        "Open lock settings",
        "Otevřít nastavení zámku"
    ],
    "conflict": [
        "This cleaning conflicts with the booking window. Check the dates and times.",
        "Úklid koliduje s termínem pobytu. Zkontrolujte datum a čas."
    ],
    "booking": [
        "Reservation",
        "Rezervace"
    ],
    "empty": [
        "No cleanings in this period.",
        "V tomto období nejsou žádné úklidy."
    ],
    "no_properties": [
        "Add a property to start scheduling cleanings.",
        "Pro plánování úklidů nejprve přidejte ubytování."
    ],
    "from": [
        "From",
        "Od"
    ],
    "to": [
        "Until (exclusive)",
        "Do (bez tohoto dne)"
    ],
    "filter": [
        "Show dates",
        "Zobrazit termíny"
    ],
    "reset": [
        "Next 30 days",
        "Příštích 30 dní"
    ],
    "saved": [
        "Saved.",
        "Uloženo."
    ],
    "removed": [
        "Cleaning removed. The reservation is unchanged.",
        "Úklid odstraněn. Rezervace se nezměnila."
    ],
    "dates": [
        "Enter valid dates, no more than 370 days apart.",
        "Zadejte platná data, nejvýše 370 dní od sebe."
    ],
    "times": [
        "Enter both times, with the end later than the start.",
        "Vyplňte oba časy. Konec musí být později než začátek."
    ],
    "notes_error": [
        "The instructions are too long.",
        "Pokyny jsou příliš dlouhé."
    ],
    "property_error": [
        "Choose an available property.",
        "Vyberte dostupné ubytování."
    ],
    "code_error": [
        "Use 1–32 letters, digits, #, * or hyphens.",
        "Použijte 1–32 písmen, číslic nebo znaků #, * a -."
    ],
    "changed": [
        "This cleaning changed. Reload it before saving.",
        "Tento úklid se změnil. Před uložením jej znovu načtěte."
    ],
    "pending": [
        "A lock operation is running. Please try again shortly.",
        "Probíhá operace se zámkem. Za chvíli to zkuste znovu."
    ],
    "login_required": [
        "Turn off staging no-login mode before using TTLock or sharing door codes.",
        "Před použitím TTLock nebo sdílením kódů vypněte režim stagingu bez přihlášení."
    ],
    "share_intro": [
        "Choose properties for a read-only link. Teams see the next 30 days, including door codes. The link expires after 30 days.",
        "Vyberte ubytování pro odkaz pouze ke čtení. Tým uvidí příštích 30 dní včetně kódů ke dveřím. Odkaz vyprší za 30 dní."
    ],
    "create_share": [
        "Create sharing link",
        "Vytvořit odkaz"
    ],
    "share_ready": [
        "Your cleaning link",
        "Odkaz na rozpis úklidů"
    ],
    "share_once": [
        "Copy this link now. It is only shown once.",
        "Odkaz si nyní zkopírujte. Zobrazí se pouze jednou."
    ],
    "share_caution": [
        "Anyone with this link can read these properties' door codes. Revoking the link does not change a code already shared.",
        "Kdokoli s odkazem může číst kódy těchto ubytování. Zrušení odkazu nezmění již sdílený kód."
    ],
    "share_number": [
        "Link",
        "Odkaz"
    ],
    "expires": [
        "Expires",
        "Vyprší"
    ],
    "revoke": [
        "Revoke link",
        "Zrušit odkaz"
    ],
    "shared_title": [
        "Cleaning schedule",
        "Rozpis úklidů"
    ],
    "read_only": [
        "Read-only · next 30 days",
        "Pouze ke čtení · příštích 30 dní"
    ],
    "refresh": [
        "Refresh schedule",
        "Obnovit rozpis"
    ],
    "copy": [
        "Copy code",
        "Kopírovat kód"
    ],
    "load_error": [
        "The schedule could not be refreshed. The dates below may be outdated. Try again.",
        "Rozpis se nepodařilo obnovit. Níže uvedené termíny mohou být zastaralé. Zkuste to znovu."
    ],
    "cleaning_time": [
        "Cleaning time",
        "Čas úklidu"
    ],
    "auto_help": [
        "Checkout changes update automatic cleanings. A date you change stays as you set it.",
        "Změna odjezdu upraví automatický úklid. Vámi upravený termín zůstane zachovaný."
    ]
}

def translator(lang: str):
    index = 1 if lang == "cs" else 0
    return lambda key: WORDS.get(key, (key, key))[index]
