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
    "Enter the full date as DD.MM.YYYY.": "Zadejte celé datum ve formátu DD.MM.RRRR.",
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
    "Enter the full date as DD.MM.YYYY.": (
        "Date of birth: enter the full date as DD.MM.YYYY."
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
    "Enter the full date as DD.MM.YYYY.": (
        "Datum narození: zadejte celé datum ve formátu DD.MM.RRRR."
    ),
    "Year must be 1900 or later.": "Datum narození: rok musí být 1900 nebo pozdější.",
    "Month must be between 01 and 12.": "Datum narození: měsíc musí být mezi 01 a 12.",
    "Day must be between 01 and 31.": "Datum narození: den musí být mezi 01 a 31.",
    "That date does not exist - please check day and month.": (
        "Datum narození: takové datum neexistuje — zkontrolujte den a měsíc."
    ),
}

# WP26: the guest form in German, Spanish and French. Keyed by the English
# sentence ``validation.py`` writes, like the tables above, and already worded
# the guest's way (the field named as its label names it). Only the guest
# sentences are here: the property banner is host copy and stays EN/CS.
# ``tests/test_guest_languages.py`` checks every guest sentence of the Czech
# table has an entry in each of these, so a changed limit cannot leave one
# language behind.
GUEST_MESSAGES: Dict[str, Dict[str, str]] = {
    "de": {
        "Date of birth is required.": "Das Geburtsdatum ist erforderlich.",
        "Enter the full date as DD.MM.YYYY.": "Geburtsdatum: Geben Sie das vollständige Datum als TT.MM.JJJJ ein.",
        "Year must be 1900 or later.": "Geburtsdatum: Das Jahr muss 1900 oder später sein.",
        "Month must be between 01 and 12.": "Geburtsdatum: Der Monat muss zwischen 01 und 12 liegen.",
        "Day must be between 01 and 31.": "Geburtsdatum: Der Tag muss zwischen 01 und 31 liegen.",
        "That date does not exist - please check day and month.": "Geburtsdatum: Dieses Datum existiert nicht — prüfen Sie Tag und Monat.",
        "Date of birth cannot be after your arrival date.": "Das Geburtsdatum darf nicht nach Ihrem Anreisedatum liegen.",
        "Date of birth cannot be in the future.": "Das Geburtsdatum darf nicht in der Zukunft liegen.",
        "Surname is required.": "Der Nachname ist erforderlich.",
        "Given name looks missing - please check the passport.": "Der Vorname scheint zu fehlen - bitte prüfen Sie den Reisepass.",
        "Nationality is required.": "Wählen Sie Ihre Staatsangehörigkeit.",
        "Travel document number is required.": "Die Nummer des Reisedokuments ist erforderlich.",
        "Street and number are required.": "Straße und Hausnummer sind erforderlich.",
        "City is required.": "Der Ort ist erforderlich.",
        "Country is required.": "Wählen Sie das Land Ihrer Wohnanschrift.",
        "Unknown country code.": "Unbekannter Ländercode.",
        "Unknown purpose-of-stay code.": "Unbekannter Code für den Aufenthaltszweck.",
        "Purpose of stay is required.": "Der Aufenthaltszweck ist erforderlich.",
        "Remove the | character and any line breaks.": "Entfernen Sie das Zeichen | und alle Zeilenumbrüche.",
        "Departure date must be later than the arrival date.": "Das Abreisedatum muss nach dem Anreisedatum liegen.",
        "These dates do not match your booking. Reload this page, or ask your host.": "Diese Daten stimmen nicht mit Ihrer Buchung überein. Laden Sie die Seite neu oder fragen Sie Ihren Gastgeber.",
        "The stay dates on this page are not readable. Reload the page and try again.": "Die Aufenthaltsdaten auf dieser Seite sind nicht lesbar. Laden Sie die Seite neu und versuchen Sie es erneut.",
        "That signature could not be saved. Sign again on the signature pad.": "Die Unterschrift konnte nicht gespeichert werden. Unterschreiben Sie erneut im Unterschriftsfeld.",
        "Type this using Latin letters (A-Z), exactly as printed in the two machine-readable lines at the bottom of your passport.": "Verwenden Sie lateinische Buchstaben (A-Z), genau wie in den beiden maschinenlesbaren Zeilen unten in Ihrem Reisepass.",
        "Surname must be at most 50 characters.": "Der Nachname darf höchstens 50 Zeichen lang sein.",
        "Given name must be at most 24 characters.": "Der Vorname darf höchstens 24 Zeichen lang sein.",
        "Document number must be at least 6 characters.": "Die Dokumentnummer muss mindestens 6 Zeichen lang sein.",
        "Document number must be at most 30 characters.": "Die Dokumentnummer darf höchstens 30 Zeichen lang sein.",
        "Visa number must be at most 15 characters.": "Die Visumnummer darf höchstens 15 Zeichen lang sein.",
        "Street must be at most 42 characters.": "Die Straße darf höchstens 42 Zeichen lang sein.",
        "City must be at most 42 characters.": "Der Ort darf höchstens 42 Zeichen lang sein.",
        "Street cannot consist of digits only.": "Die Straße darf nicht nur aus Ziffern bestehen.",
        "City cannot consist of digits only.": "Der Ort darf nicht nur aus Ziffern bestehen.",
        "Home address is too long.": "Die Wohnanschrift ist zu lang.",
        "Note must be at most 255 characters.": "Die Anmerkung darf höchstens 255 Zeichen lang sein.",
        "For a child recorded in a parent's passport the note must contain the parent's document number.": "Bei einem Kind, das im Reisepass eines Elternteils eingetragen ist, muss die Anmerkung die Dokumentnummer des Elternteils enthalten.",
    },
    "es": {
        "Date of birth is required.": "La fecha de nacimiento es obligatoria.",
        "Enter the full date as DD.MM.YYYY.": "Fecha de nacimiento: introduzca la fecha completa como DD.MM.AAAA.",
        "Year must be 1900 or later.": "Fecha de nacimiento: el año debe ser 1900 o posterior.",
        "Month must be between 01 and 12.": "Fecha de nacimiento: el mes debe estar entre 01 y 12.",
        "Day must be between 01 and 31.": "Fecha de nacimiento: el día debe estar entre 01 y 31.",
        "That date does not exist - please check day and month.": "Fecha de nacimiento: esa fecha no existe — revise el día y el mes.",
        "Date of birth cannot be after your arrival date.": "La fecha de nacimiento no puede ser posterior a su fecha de llegada.",
        "Date of birth cannot be in the future.": "La fecha de nacimiento no puede ser futura.",
        "Surname is required.": "Los apellidos son obligatorios.",
        "Given name looks missing - please check the passport.": "Parece que falta el nombre - revise el pasaporte.",
        "Nationality is required.": "Elija su nacionalidad.",
        "Travel document number is required.": "El número del documento de viaje es obligatorio.",
        "Street and number are required.": "La calle y el número son obligatorios.",
        "City is required.": "La ciudad es obligatoria.",
        "Country is required.": "Elija el país de su domicilio.",
        "Unknown country code.": "Código de país desconocido.",
        "Unknown purpose-of-stay code.": "Código de motivo de la estancia desconocido.",
        "Purpose of stay is required.": "El motivo de la estancia es obligatorio.",
        "Remove the | character and any line breaks.": "Elimine el carácter | y cualquier salto de línea.",
        "Departure date must be later than the arrival date.": "La fecha de salida debe ser posterior a la de llegada.",
        "These dates do not match your booking. Reload this page, or ask your host.": "Estas fechas no coinciden con su reserva. Recargue la página o consulte a su anfitrión.",
        "The stay dates on this page are not readable. Reload the page and try again.": "No se pueden leer las fechas de la estancia en esta página. Recárguela e inténtelo de nuevo.",
        "That signature could not be saved. Sign again on the signature pad.": "No se ha podido guardar la firma. Vuelva a firmar en el recuadro de firma.",
        "Type this using Latin letters (A-Z), exactly as printed in the two machine-readable lines at the bottom of your passport.": "Escríbalo con letras latinas (A-Z), exactamente como aparece en las dos líneas de lectura mecánica de la parte inferior de su pasaporte.",
        "Surname must be at most 50 characters.": "Los apellidos pueden tener como máximo 50 caracteres.",
        "Given name must be at most 24 characters.": "El nombre puede tener como máximo 24 caracteres.",
        "Document number must be at least 6 characters.": "El número de documento debe tener al menos 6 caracteres.",
        "Document number must be at most 30 characters.": "El número de documento puede tener como máximo 30 caracteres.",
        "Visa number must be at most 15 characters.": "El número de visado puede tener como máximo 15 caracteres.",
        "Street must be at most 42 characters.": "La calle puede tener como máximo 42 caracteres.",
        "City must be at most 42 characters.": "La ciudad puede tener como máximo 42 caracteres.",
        "Street cannot consist of digits only.": "La calle no puede contener solo números.",
        "City cannot consist of digits only.": "La ciudad no puede contener solo números.",
        "Home address is too long.": "El domicilio es demasiado largo.",
        "Note must be at most 255 characters.": "La nota puede tener como máximo 255 caracteres.",
        "For a child recorded in a parent's passport the note must contain the parent's document number.": "Para un menor inscrito en el pasaporte de un progenitor, la nota debe contener el número de documento del progenitor.",
    },
    "fr": {
        "Date of birth is required.": "La date de naissance est obligatoire.",
        "Enter the full date as DD.MM.YYYY.": "Date de naissance : saisissez la date complète au format JJ.MM.AAAA.",
        "Year must be 1900 or later.": "Date de naissance : l'année doit être 1900 ou postérieure.",
        "Month must be between 01 and 12.": "Date de naissance : le mois doit être compris entre 01 et 12.",
        "Day must be between 01 and 31.": "Date de naissance : le jour doit être compris entre 01 et 31.",
        "That date does not exist - please check day and month.": "Date de naissance : cette date n'existe pas — vérifiez le jour et le mois.",
        "Date of birth cannot be after your arrival date.": "La date de naissance ne peut pas être postérieure à votre date d'arrivée.",
        "Date of birth cannot be in the future.": "La date de naissance ne peut pas être dans le futur.",
        "Surname is required.": "Le nom est obligatoire.",
        "Given name looks missing - please check the passport.": "Le prénom semble manquer - veuillez vérifier le passeport.",
        "Nationality is required.": "Choisissez votre nationalité.",
        "Travel document number is required.": "Le numéro du document de voyage est obligatoire.",
        "Street and number are required.": "La rue et le numéro sont obligatoires.",
        "City is required.": "La ville est obligatoire.",
        "Country is required.": "Choisissez le pays de votre domicile.",
        "Unknown country code.": "Code pays inconnu.",
        "Unknown purpose-of-stay code.": "Code de motif du séjour inconnu.",
        "Purpose of stay is required.": "Le motif du séjour est obligatoire.",
        "Remove the | character and any line breaks.": "Supprimez le caractère | et tout saut de ligne.",
        "Departure date must be later than the arrival date.": "La date de départ doit être postérieure à la date d'arrivée.",
        "These dates do not match your booking. Reload this page, or ask your host.": "Ces dates ne correspondent pas à votre réservation. Rechargez la page ou demandez à votre hôte.",
        "The stay dates on this page are not readable. Reload the page and try again.": "Les dates de séjour de cette page sont illisibles. Rechargez la page et réessayez.",
        "That signature could not be saved. Sign again on the signature pad.": "La signature n'a pas pu être enregistrée. Signez à nouveau dans le cadre de signature.",
        "Type this using Latin letters (A-Z), exactly as printed in the two machine-readable lines at the bottom of your passport.": "Saisissez-le en lettres latines (A-Z), exactement comme dans les deux lignes lisibles par machine en bas de votre passeport.",
        "Surname must be at most 50 characters.": "Le nom ne doit pas dépasser 50 caractères.",
        "Given name must be at most 24 characters.": "Le prénom ne doit pas dépasser 24 caractères.",
        "Document number must be at least 6 characters.": "Le numéro de document doit comporter au moins 6 caractères.",
        "Document number must be at most 30 characters.": "Le numéro de document ne doit pas dépasser 30 caractères.",
        "Visa number must be at most 15 characters.": "Le numéro de visa ne doit pas dépasser 15 caractères.",
        "Street must be at most 42 characters.": "La rue ne doit pas dépasser 42 caractères.",
        "City must be at most 42 characters.": "La ville ne doit pas dépasser 42 caractères.",
        "Street cannot consist of digits only.": "La rue ne peut pas comporter uniquement des chiffres.",
        "City cannot consist of digits only.": "La ville ne peut pas comporter uniquement des chiffres.",
        "Home address is too long.": "L'adresse de domicile est trop longue.",
        "Note must be at most 255 characters.": "La remarque ne doit pas dépasser 255 caractères.",
        "For a child recorded in a parent's passport the note must contain the parent's document number.": "Pour un enfant inscrit sur le passeport d'un parent, la remarque doit contenir le numéro de document du parent.",
    },
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


def guest_localize(message: str, lang: str = "cs") -> str:
    """The sentence as the guest form should read it, in the guest's language.

    The guest tables win, so a field is named the way its label names it; the
    host table is still the fallback, so a sentence with no guest entry is
    translated rather than left English.
    """
    if not message:
        return message
    if lang in GUEST_MESSAGES:
        # No host table behind these: a sentence with no entry stays English,
        # which is the guest catalog's own fallback.
        return GUEST_MESSAGES[lang].get(message) or GUEST_EN_MESSAGES.get(message) or message
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
