"""Czech wording for the validation sentences the guest form and the host app show.

``validation.py`` writes its messages in English, because that is the language
the code reads in. The person who then sees them is a Czech guest filling in a
form, or a Czech host reading the property banner and the guest cards — and
until now the host got the English sentence verbatim.

The table is keyed by the English sentence on purpose: a message with no entry
stays visibly English instead of turning blank, which is how a gap gets noticed.
"""
from __future__ import annotations

import re
from typing import Dict, List, Tuple

from . import validation

CS_MESSAGES: Dict[str, str] = {
    # Guest form: identity
    "Date of birth is required.": "Datum narození je povinné.",
    "Enter the full date as DD/MM/YYYY.": "Zadejte celé datum ve formátu DD/MM/RRRR.",
    "Year must be 1900 or later.": "Rok musí být 1900 nebo pozdější.",
    "Month must be between 01 and 12.": "Měsíc musí být mezi 01 a 12.",
    "Day must be between 01 and 31.": "Den musí být mezi 01 a 31.",
    "That date does not exist - please check day and month.": "Toto datum neexistuje – zkontrolujte den a měsíc.",
    "Date of birth cannot be after your arrival date.": "Datum narození nemůže být po datu příjezdu.",
    "Date of birth cannot be in the future.": "Datum narození nemůže být v budoucnosti.",
    "Surname is required.": "Příjmení je povinné.",
    "Given name looks missing - please check the passport.": "Křestní jméno zřejmě chybí – zkontrolujte pas.",
    "Nationality is required.": "Státní příslušnost je povinná.",
    "Travel document number is required.": "Číslo cestovního dokladu je povinné.",
    "Street and number are required.": "Ulice a číslo jsou povinné.",
    "City is required.": "Město je povinné.",
    "Country is required.": "Země je povinná.",
    "Unknown country code.": "Neznámý kód země.",
    "Unknown purpose-of-stay code.": "Neznámý účel pobytu.",
    "Purpose of stay is required.": "Účel pobytu je povinný.",
    "Remove the | character and any line breaks.": (
        "Odstraňte znak | a všechny konce řádků."
    ),
    "Departure date must be later than the arrival date.": "Datum odjezdu musí být po datu příjezdu.",
    validation.STAY_OUTSIDE_BOOKING_MESSAGE: (
        "Tyto termíny neodpovídají vaší rezervaci. Načtěte stránku znovu nebo se "
        "obraťte na hostitele."
    ),
    validation.STAY_DATE_UNREADABLE_MESSAGE: (
        "Termíny pobytu na této stránce nejsou čitelné. Načtěte stránku znovu."
    ),
    validation.SIGNATURE_INVALID_MESSAGE: (
        "Tento podpis se nepodařilo uložit. Podepište se znovu do podpisového pole."
    ),
    validation.NON_LATIN_MESSAGE: (
        "Zapište latinkou (A–Z) přesně tak, jak je to vytištěno ve dvou strojově "
        "čitelných řádcích na konci vašeho pasu."
    ),
    # Built from the same constants as the English text so the two cannot drift
    # apart when a field limit changes.
    f"Surname must be at most {validation.MAX_SURNAME} characters.": (
        f"Příjmení může mít nejvýše {validation.MAX_SURNAME} znaků. Zkraťte ho, "
        "prosím, podle pasu."
    ),
    f"Given name must be at most {validation.MAX_FIRST_NAME} characters.": (
        f"Jméno může mít nejvýše {validation.MAX_FIRST_NAME} znaků. Uveďte, prosím, "
        "jen první jména z pasu."
    ),
    f"Document number must be at least {validation.MIN_DOC} characters.": (
        f"Číslo dokladu musí mít alespoň {validation.MIN_DOC} znaků."
    ),
    f"Document number must be at most {validation.MAX_DOC} characters.": (
        f"Číslo dokladu může mít nejvýše {validation.MAX_DOC} znaků."
    ),
    f"Visa number must be at most {validation.MAX_VISA} characters.": (
        f"Číslo víza může mít nejvýše {validation.MAX_VISA} znaků."
    ),
    f"Street must be at most {validation.MAX_RESIDENCE_PART} characters.": (
        f"Ulice může mít nejvýše {validation.MAX_RESIDENCE_PART} znaků."
    ),
    f"City must be at most {validation.MAX_RESIDENCE_PART} characters.": (
        f"Město může mít nejvýše {validation.MAX_RESIDENCE_PART} znaků."
    ),
    "Street cannot consist of digits only.": "Ulice nemůže obsahovat jen číslice.",
    "City cannot consist of digits only.": "Město nemůže obsahovat jen číslice.",
    "Home address is too long.": "Adresa bydliště je příliš dlouhá.",
    f"Note must be at most {validation.MAX_NOTE} characters.": (
        f"Poznámka může mít nejvýše {validation.MAX_NOTE} znaků."
    ),
    "For a child recorded in a parent's passport the note must contain "
    "the parent's document number.": (
        "U dítěte zapsaného v pasu rodiče musí poznámka obsahovat číslo dokladu rodiče."
    ),
    # Property form: what the host still has to fill in before anything can be
    # reported. The host reads these in the banner above the form.
    "IDUB is required before anything can be reported.": "Bez IDUB nelze nic nahlásit.",
    "IDUB must be 12-14 letters or digits.": "IDUB má 12–14 písmen nebo číslic.",
    "The facility abbreviation (zkratka) is required.": "Vyplňte zkratku zařízení.",
    "The abbreviation is exactly five letters, e.g. AAKLI.": (
        "Zkratka má přesně pět písmen, např. AAKLI."
    ),
    "Accommodation facility name is required.": "Vyplňte název ubytovacího zařízení.",
    "Facility name must be at most 35 characters.": (
        "Název zařízení může mít nejvýše 35 znaků."
    ),
    "House number is required.": "Vyplňte číslo popisné.",
    "House number is up to 4 digits, optionally with E for an evidence number.": (
        "Číslo popisné má nejvýše 4 číslice, případně s E pro číslo evidenční."
    ),
    "Orientation number is up to 3 digits plus one optional letter.": (
        "Orientační číslo má nejvýše 3 číslice a jedno volitelné písmeno."
    ),
    "Postcode is required.": "Vyplňte PSČ.",
    "Postcode must be exactly 5 digits.": "PSČ má přesně 5 číslic.",
    "Municipality is required.": "Vyplňte obec.",
    "UbyPort web-service login is required for automatic reporting.": (
        "Pro automatické hlášení je potřeba přihlašovací jméno k webové službě UbyPort."
    ),
    "Web-service logins look like UBY-WS123abc (production) or uby-tws1ab45 (test). "
    "The ub1234567 login is for the web form and will not work here.": (
        "Přihlašovací jméno k webové službě vypadá jako UBY-WS123abc (ostrý provoz) "
        "nebo uby-tws1ab45 (test). Přihlášení ub1234567 je pro webový formulář a tady "
        "fungovat nebude."
    ),
    "UbyPort web-service password is required.": (
        "Pro automatické hlášení je potřeba heslo k webové službě UbyPort."
    ),
    "No property manager is attached, so guests have no named contact "
    "for questions about their stay.": (
        "Není přiřazen správce ubytování, takže hosté nemají uvedený kontakt pro "
        "dotazy k pobytu."
    ),
    "No property manager is attached, so guests have no named contact "
    "for questions about their stay. The privacy notice also cannot name who "
    "controls their data.": (
        "Není přiřazen správce ubytování, takže hosté nemají uvedený kontakt pro "
        "dotazy k pobytu. Ani v zásadách ochrany osobních údajů nelze uvést, kdo "
        "jejich údaje zpracovává."
    ),
}

# The guest form's own wording, in both languages. ``validation.py`` writes for
# the host app, where a field is named by its column ("Country", "Nationality").
# The guest form labels the same fields "Stát" / "Country" and "Státní
# občanství" / "Nationality", and the birth-date sentences sit under a field
# the guest knows as "Datum narození" / "Date of birth" — so the summary has to
# name what the label names. Only the guest route reads these tables; the host
# copy in ``validation.py`` is untouched.
GUEST_EN_MESSAGES: Dict[str, str] = {
    "Nationality is required.": "Choose your nationality.",
    "Country is required.": "Choose the country of your home address.",
    "Enter the full date as DD/MM/YYYY.": (
        "Date of birth: enter the full date as DD/MM/YYYY."
    ),
    "Year must be 1900 or later.": "Date of birth: year must be 1900 or later.",
    "Month must be between 01 and 12.": "Date of birth: month must be between 01 and 12.",
    "Day must be between 01 and 31.": "Date of birth: day must be between 01 and 31.",
    "That date does not exist - please check day and month.": (
        "Date of birth: that date does not exist — check the day and month."
    ),
}

GUEST_CS_MESSAGES: Dict[str, str] = {
    "Nationality is required.": "Vyberte státní občanství.",
    "Country is required.": "Vyberte stát trvalého bydliště.",
    "Enter the full date as DD/MM/YYYY.": (
        "Datum narození: zadejte celé datum ve formátu DD/MM/RRRR."
    ),
    "Year must be 1900 or later.": "Datum narození: rok musí být 1900 nebo pozdější.",
    "Month must be between 01 and 12.": "Datum narození: měsíc musí být mezi 01 a 12.",
    "Day must be between 01 and 31.": "Datum narození: den musí být mezi 01 a 31.",
    "That date does not exist - please check day and month.": (
        "Datum narození: takové datum neexistuje — zkontrolujte den a měsíc."
    ),
}

# Sentences that embed a value the host typed, so they cannot be dictionary keys.
CS_PATTERNS: Tuple[Tuple[re.Pattern, str], ...] = (
    (
        re.compile(r"^'(?P<code>.*)' is not a valid three-letter country code\.$"),
        "„{code}“ není platný třímístný kód země (např. GBR, USA, DEU).",
    ),
    (
        re.compile(r"^Must be at most (?P<limit>\d+) characters\.$"),
        "Nejvýše {limit} znaků.",
    ),
)


def localize(message: str, lang: str = "cs") -> str:
    """The message in the reader's language, or the message itself."""
    if lang != "cs" or not message:
        return message
    translated = CS_MESSAGES.get(message)
    if translated:
        return translated
    for pattern, template in CS_PATTERNS:
        match = pattern.match(message)
        if match:
            return template.format(**match.groupdict())
    return message


def localize_issues(issues: List[validation.Issue], lang: str = "cs") -> List[validation.Issue]:
    """The same issues, with their sentences in the reader's language."""
    if lang != "cs":
        return issues
    return [
        validation.Issue(issue.field, localize(issue.message, lang), issue.severity)
        for issue in issues
    ]


def guest_localize(message: str, lang: str = "cs") -> str:
    """The sentence as the guest form should read it, in the guest's language.

    The guest tables win, so a field is named the way its label names it; the
    host table is still the fallback, so a sentence with no guest entry is
    translated rather than left English.
    """
    if not message:
        return message
    table = GUEST_EN_MESSAGES if lang != "cs" else GUEST_CS_MESSAGES
    return table.get(message) or localize(message, lang)


def guest_localize_issues(
    issues: List[validation.Issue], lang: str = "cs"
) -> List[validation.Issue]:
    """The same issues, worded for the guest form."""
    return [
        validation.Issue(issue.field, guest_localize(issue.message, lang), issue.severity)
        for issue in issues
    ]
