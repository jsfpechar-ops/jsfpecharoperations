"""Guest-facing strings in English and Czech.

Guests are by definition foreigners, so English is the default, but the form
also stands in for a Czech legal document and hosts asked for a Czech view.
"""
from __future__ import annotations

from typing import Dict

LANGUAGES = ("en", "cs")
DEFAULT_LANGUAGE = "en"

STRINGS: Dict[str, Dict[str, str]] = {
    "en": {
        "title": "Guest registration",
        "legal_intro": (
            "Czech law treats every rented apartment as an accommodation facility. Your host "
            "must write each guest into a house book and report every foreign guest to the "
            "Foreign Police within three working days of arrival. This form is how that is "
            "done — one form per person, including children."
        ),
        "why_title": "Why you are filling this in",
        "why_law": (
            "Act No. 326/1999 Coll., on the Residence of Foreign Nationals, §§ 101–103."
        ),
        "why_more": "What happens with what you enter",
        "why_point_report": (
            "Foreign nationals are reported electronically to the Police of the Czech "
            "Republic, Directorate of the Alien Police Service."
        ),
        "why_point_book": (
            "The same details go into the house book (domovní kniha), which the host must "
            "keep for six years and produce at a police inspection."
        ),
        "why_point_czech": (
            "Czech citizens are not reported to the police — only the house-book entry is made."
        ),
        "why_point_sign": (
            "Completing and signing the form is the guest's own legal duty, which is why a "
            "signature is required."
        ),
        "why_point_nothing_else": (
            "Nothing here is used for marketing, and none of it goes back to the booking "
            "site you booked through."
        ),
        "pick_stay": "Find your stay",
        "pick_stay_help": "Tap your arrival and departure dates to continue.",
        "back_to_stays": "Choose different dates",
        "wrong_dates": "Not your dates?",
        "your_stay_badge": "A form was submitted from this device",
        "stay_not_started": "Select these dates",
        "error_no_stay": "Please select your stay dates.",
        "error_party_size": "Please enter how many people are staying (1–60).",
        "no_stays": "There are no upcoming stays to fill in right now.",
        "no_stays_help": (
            "The link only shows stays that start in the next few days. If you have just "
            "booked, try again closer to your arrival date, or message your host."
        ),
        "bad_link_title": "This guest link is not valid",
        "bad_link_help": "It may be incomplete or may have been replaced. Please ask your host for a new link.",
        "stay_gone_title": "That stay is no longer open for registration",
        "stay_gone_help": (
            "The dates may have changed, the booking may have been cancelled, or the stay is "
            "already over. Please message your host."
        ),
        "not_yours_title": "This form cannot be opened on this device",
        "not_yours_help": (
            "So that one guest never sees another guest's passport details, a form can only "
            "be reopened on the device that filled it in. If you need a correction, message "
            "your host."
        ),
        "already_filed_title": "These details have already been reported",
        "already_filed_help": (
            "For legal accuracy, a reported record cannot be changed from this form. "
            "Please message your host if anything needs correcting."
        ),
        "form_locked_title": "This form is locked",
        "form_locked_help": (
            "Your details were saved and signed. To protect your information, the form "
            "cannot be changed from this link. Please message your host if anything needs "
            "correcting."
        ),
        "form_locked_short": "Saved and locked — contact your host to change anything.",
        "pin_title": "Enter the access PIN",
        "pin_help": (
            "Your host sent a four-digit PIN together with the registration link. "
            "Enter it to open the form."
        ),
        "pin_label": "PIN",
        "pin_submit": "Continue",
        "pin_wrong": "That PIN is not correct. Check the message from your host.",
        "start_over": "Start again",
        "nights": "nights",
        "arrive": "Arrival",
        "depart": "Departure",
        "select": "This is my stay",
        "party_question": "How many people are staying?",
        "party_help": "Count everyone, including children. Each person needs their own form.",
        "party_confirm": "Continue",
        "people_progress": "%(done)s of %(total)s people completed",
        "add_person": "Add a person",
        "add_first_person": "Start with your own details",
        "saved_title": "Details saved",
        "saved_body": "Thank you. Please review what you submitted below.",
        "reported_title": "Details submitted and reported",
        "reported_body": (
            "Thank you. Your host has already reported this record. Contact your host if "
            "anything below needs correcting."
        ),
        "summary_title": "Your submission",
        "your_details": "Your details",
        "person": "Person",
        "you": "you",
        "completed": "completed",
        "not_filled": "not filled in",
        "edit": "Edit",
        "all_done_title": "Thank you, everything is complete",
        "all_done_body": (
            "All guest details for this stay have been submitted. There is nothing more you "
            "need to do."
        ),
        "still_missing": "Still missing details for %(n)s person(s).",
        "add_another": "Add another person",
        "continue_filling": "Continue filling in",
        "mrz_title": "Fast fill from your passport",
        "mrz_help": (
            "Type the two long lines of letters and << symbols printed at the very bottom of "
            "your passport photo page (or the back of your ID card). We will fill in the form "
            "for you and check it for typos."
        ),
        "mrz_button": "Fill in from these lines",
        "mrz_or": "or fill in the form manually below",
        "mrz_failed": "Could not read those lines. Please fill in the form manually.",
        "mrz_filled": "Filled in from your document. Please check every field before signing.",
        "surname": "Surname",
        "first_name": "Given name(s)",
        "birth_date": "Date of birth",
        "birth_date_help": "Type the 8 digits from your passport — slashes are added automatically.",
        "residence_help": "Your permanent home address abroad, as shown in your passport. Required for the police report.",
        "nationality": "Nationality",
        "doc_number": "Travel document number",
        "doc_number_help": "Passport or ID card number.",
        "visa_number": "Visa number",
        "visa_help": "Only if a Czech or Schengen visa was issued to you.",
        "residence_title": "Permanent home address",
        "res_street": "Street and number",
        "res_city": "City",
        "res_country": "Country",
        "purpose": "Purpose of stay",
        "stay_dates": "Your dates",
        "child_title": "This person is a child travelling on a parent's passport",
        "child_help": (
            "Tick this only if the child has no passport of their own. We will then need the "
            "parent's document number."
        ),
        "parent_doc": "Parent's document number",
        "note": "Note",
        "signature": "Signature",
        "signature_help": "Sign with your finger or mouse. This is required by Czech law.",
        "signature_clear": "Clear",
        "signature_missing": "Please sign before submitting.",
        "signature_kept": "Signature already saved. Sign again only if you need to change it.",
        "submit": "Submit my details",
        "optional": "optional",
        "required": "required",
        "check_in": "Check-in",
        "check_out": "Check-out",
        "privacy": (
            "Your details are used only to meet the host's legal reporting duty towards the "
            "Police of the Czech Republic and are kept for the statutory six years."
        ),
        "privacy_link": "How your data is handled",
        "privacy_title": "Privacy notice",
        "privacy_intro": (
            "What happens to the details you enter, as required by Articles 13 and 14 of the "
            "GDPR."
        ),
        "privacy_controller": "Who is responsible",
        "privacy_controller_missing": (
            "The business operating this accommodation is the controller of your data. Ask "
            "your host for its registered name and address if you need them in writing."
        ),
        "privacy_purpose": "Why the data is collected",
        "privacy_purpose_body": (
            "To meet two legal duties of an accommodation provider in Czechia: reporting "
            "accommodated foreign nationals to the Foreign Police, and keeping a house book "
            "(domovní kniha). It is not used for any other purpose."
        ),
        "privacy_basis": "Legal basis",
        "privacy_basis_body": (
            "Article 6(1)(c) GDPR — compliance with a legal obligation, namely §§ 101–103 of "
            "Act No. 326/1999 Coll., on the Residence of Foreign Nationals. Your consent is "
            "not asked for, because the duty applies whether or not you agree to it."
        ),
        "privacy_data": "What is collected",
        "privacy_data_body": (
            "Given name and surname, date of birth, nationality, travel document number, visa "
            "number where one was issued, permanent home address abroad, purpose of stay, the "
            "start and end of your stay, and your signature."
        ),
        "privacy_recipients": "Who receives it",
        "privacy_recipients_body": (
            "The Police of the Czech Republic, Directorate of the Alien Police Service, and "
            "any officer inspecting the house book. The data stays within the EU. It is never "
            "sold, sent to the site you booked through, or used for marketing."
        ),
        "privacy_retention": "How long it is kept",
        "privacy_retention_body": (
            "Six years from the last entry in the house book, which is the period § 101 "
            "requires. After that it is deleted."
        ),
        "privacy_rights": "Your rights",
        "privacy_rights_body": (
            "You can ask for a copy of your data, have anything inaccurate corrected, and ask "
            "how it is being processed. Erasure and objection are limited for as long as the "
            "legal duty to keep the record lasts. There is no automated decision-making and "
            "no profiling."
        ),
        "privacy_complaint": (
            "If you believe your data is being handled wrongly, you can complain to the Czech "
            "data protection authority: Úřad pro ochranu osobních údajů, Pplk. Sochora 27, "
            "170 00 Praha 7, uoou.gov.cz."
        ),
        "privacy_required": (
            "Providing these details is a statutory requirement, not the host's own idea. "
            "Without them the host cannot lawfully accommodate you."
        ),
        "privacy_contact": "Contact",
        "fix_errors": "Please correct the following:",
        "back": "Back",
    },
    "cs": {
        "title": "Registrace ubytovaného",
        "legal_intro": (
            "Podle českého práva je pronajímaný apartmán ubytovacím zařízením. Ubytovatel musí "
            "každého hosta zapsat do domovní knihy a každého ubytovaného cizince oznámit "
            "cizinecké policii do 3 pracovních dnů od ubytování. K tomu slouží tento formulář — "
            "jeden za každou osobu včetně dětí."
        ),
        "why_title": "Proč tento formulář vyplňujete",
        "why_law": "Zákon č. 326/1999 Sb., o pobytu cizinců na území ČR, § 101–103.",
        "why_more": "Co se s údaji stane",
        "why_point_report": (
            "Cizinci se elektronicky oznamují Policii České republiky, Ředitelství služby "
            "cizinecké policie."
        ),
        "why_point_book": (
            "Stejné údaje se zapisují do domovní knihy, kterou ubytovatel uchovává 6 let a "
            "předkládá při kontrole policie."
        ),
        "why_point_czech": (
            "Občané ČR se policii neoznamují — provede se pouze zápis do domovní knihy."
        ),
        "why_point_sign": (
            "Vyplnit a podepsat formulář je zákonnou povinností ubytovaného, proto je podpis "
            "povinný."
        ),
        "why_point_nothing_else": (
            "Údaje se nepoužívají k marketingu a nevracejí se rezervačnímu portálu, přes který "
            "jste rezervovali."
        ),
        "pick_stay": "Najděte svou rezervaci",
        "pick_stay_help": "Klepněte na termín svého pobytu a pokračujte.",
        "back_to_stays": "Vybrat jiný termín",
        "wrong_dates": "Nesedí termín?",
        "your_stay_badge": "Z tohoto zařízení byl odeslán formulář",
        "stay_not_started": "Vybrat tento termín",
        "error_no_stay": "Vyberte prosím termín svého pobytu.",
        "error_party_size": "Zadejte počet osob (1–60).",
        "no_stays": "Momentálně tu není žádná rezervace k vyplnění.",
        "no_stays_help": (
            "Odkaz zobrazuje jen pobyty začínající v nejbližších dnech. Pokud jste právě "
            "rezervovali, zkuste to blíže k datu příjezdu, nebo napište ubytovateli."
        ),
        "bad_link_title": "Tento odkaz není platný",
        "bad_link_help": "Odkaz může být neúplný nebo byl nahrazen. Požádejte ubytovatele o nový odkaz.",
        "stay_gone_title": "Tento pobyt už není otevřený k registraci",
        "stay_gone_help": (
            "Termín se mohl změnit, rezervace mohla být zrušena, nebo už pobyt skončil. "
            "Napište prosím ubytovateli."
        ),
        "not_yours_title": "Tento formulář nelze na tomto zařízení otevřít",
        "not_yours_help": (
            "Aby jeden host neviděl údaje z pasu druhého, lze formulář znovu otevřít pouze na "
            "zařízení, ze kterého byl vyplněn. Potřebujete-li opravu, napište ubytovateli."
        ),
        "already_filed_title": "Tyto údaje již byly oznámeny",
        "already_filed_help": (
            "Kvůli správnosti zákonného záznamu nelze oznámené údaje v tomto formuláři měnit. "
            "Potřebujete-li opravu, napište ubytovateli."
        ),
        "form_locked_title": "Formulář je uzamčen",
        "form_locked_help": (
            "Vaše údaje byly uloženy a podepsány. Abychom chránili vaše informace, "
            "formulář už z tohoto odkazu nelze měnit. Potřebujete-li opravu, napište ubytovateli."
        ),
        "form_locked_short": "Uloženo a uzamčeno — pro změnu kontaktujte ubytovatele.",
        "pin_title": "Zadejte přístupový PIN",
        "pin_help": (
            "Ubytovatel vám spolu s odkazem poslal čtyřmístný PIN. "
            "Zadejte ho pro otevření formuláře."
        ),
        "pin_label": "PIN",
        "pin_submit": "Pokračovat",
        "pin_wrong": "PIN není správný. Zkontrolujte zprávu od ubytovatele.",
        "start_over": "Začít znovu",
        "nights": "nocí",
        "arrive": "Příjezd",
        "depart": "Odjezd",
        "select": "To je moje rezervace",
        "party_question": "Kolik osob bude ubytováno?",
        "party_help": "Započítejte všechny včetně dětí. Každá osoba má vlastní formulář.",
        "party_confirm": "Pokračovat",
        "people_progress": "vyplněno %(done)s z %(total)s osob",
        "add_person": "Přidat osobu",
        "add_first_person": "Začněte svými údaji",
        "saved_title": "Údaje uloženy",
        "saved_body": "Děkujeme. Níže si prosím zkontrolujte odeslané údaje.",
        "reported_title": "Údaje byly odeslány a oznámeny",
        "reported_body": (
            "Děkujeme. Ubytovatel již tento záznam oznámil. Pokud je třeba něco opravit, "
            "kontaktujte ubytovatele."
        ),
        "summary_title": "Vaše údaje",
        "your_details": "Vaše údaje",
        "person": "Osoba",
        "you": "vy",
        "completed": "vyplněno",
        "not_filled": "nevyplněno",
        "edit": "Upravit",
        "all_done_title": "Děkujeme, vše je vyplněno",
        "all_done_body": "Údaje všech ubytovaných jsou odeslány. Nic dalšího už není potřeba.",
        "still_missing": "Chybí ještě údaje %(n)s osob(y).",
        "add_another": "Přidat další osobu",
        "continue_filling": "Pokračovat ve vyplnění",
        "mrz_title": "Rychlé vyplnění z pasu",
        "mrz_help": (
            "Přepište dva dlouhé řádky se znaky << ze spodní části stránky s fotografií v pasu "
            "(nebo ze zadní strany občanského průkazu). Formulář vyplníme za vás a "
            "zkontrolujeme případné překlepy."
        ),
        "mrz_button": "Vyplnit z těchto řádků",
        "mrz_or": "nebo vyplňte formulář ručně níže",
        "mrz_failed": "Řádky se nepodařilo přečíst. Vyplňte prosím formulář ručně.",
        "mrz_filled": "Vyplněno z dokladu. Před podpisem prosím zkontrolujte všechna pole.",
        "surname": "Příjmení",
        "first_name": "Jméno",
        "birth_date": "Datum narození",
        "birth_date_help": "Zadejte 8 číslic z pasu — lomítka se doplní automaticky.",
        "residence_help": "Trvalé bydliště v zahraničí podle pasu. Povinné pro oznámení policii.",
        "nationality": "Státní občanství",
        "doc_number": "Číslo cestovního dokladu",
        "doc_number_help": "Číslo pasu nebo občanského průkazu.",
        "visa_number": "Číslo víza",
        "visa_help": "Pouze pokud vám bylo vydáno české nebo schengenské vízum.",
        "residence_title": "Trvalé bydliště",
        "res_street": "Ulice a číslo",
        "res_city": "Město",
        "res_country": "Stát",
        "purpose": "Účel pobytu",
        "stay_dates": "Vaše termíny",
        "child_title": "Jde o dítě zapsané v pasu rodiče",
        "child_help": (
            "Zaškrtněte jen tehdy, pokud dítě nemá vlastní pas. Budeme potřebovat číslo "
            "dokladu rodiče."
        ),
        "parent_doc": "Číslo dokladu rodiče",
        "note": "Poznámka",
        "signature": "Podpis",
        "signature_help": "Podepište se prstem nebo myší. Podpis vyžaduje český zákon.",
        "signature_clear": "Vymazat",
        "signature_missing": "Před odesláním se prosím podepište.",
        "signature_kept": "Podpis je uložený. Podepište se znovu jen pokud ho chcete změnit.",
        "submit": "Odeslat údaje",
        "optional": "nepovinné",
        "required": "povinné",
        "check_in": "Check-in",
        "check_out": "Check-out",
        "privacy": (
            "Údaje slouží výhradně ke splnění zákonné oznamovací povinnosti ubytovatele vůči "
            "Policii České republiky a uchovávají se zákonných 6 let."
        ),
        "privacy_link": "Jak nakládáme s vašimi údaji",
        "privacy_title": "Informace o zpracování osobních údajů",
        "privacy_intro": (
            "Co se děje s údaji, které vyplníte — podle článků 13 a 14 GDPR."
        ),
        "privacy_controller": "Kdo za údaje odpovídá",
        "privacy_controller_missing": (
            "Správcem údajů je podnikatel provozující toto ubytování. O jeho název a sídlo "
            "písemně požádejte ubytovatele."
        ),
        "privacy_purpose": "Proč údaje sbíráme",
        "privacy_purpose_body": (
            "Ke splnění dvou zákonných povinností ubytovatele: oznámit ubytované cizince "
            "cizinecké policii a vést domovní knihu. K ničemu jinému se údaje nepoužívají."
        ),
        "privacy_basis": "Právní základ",
        "privacy_basis_body": (
            "Čl. 6 odst. 1 písm. c) GDPR — splnění právní povinnosti, konkrétně § 101–103 "
            "zákona č. 326/1999 Sb., o pobytu cizinců. Souhlas se nevyžaduje, protože "
            "povinnost platí bez ohledu na něj."
        ),
        "privacy_data": "Jaké údaje se sbírají",
        "privacy_data_body": (
            "Jméno a příjmení, datum narození, státní občanství, číslo cestovního dokladu, "
            "číslo víza (bylo-li vydáno), trvalé bydliště v zahraničí, účel pobytu, počátek a "
            "konec pobytu a podpis."
        ),
        "privacy_recipients": "Komu se předávají",
        "privacy_recipients_body": (
            "Policii České republiky, Ředitelství služby cizinecké policie, a kontrolnímu "
            "orgánu při nahlédnutí do domovní knihy. Údaje zůstávají v EU. Neprodávají se, "
            "neposílají rezervačnímu portálu ani se nepoužívají k marketingu."
        ),
        "privacy_retention": "Jak dlouho se uchovávají",
        "privacy_retention_body": (
            "Šest let od posledního zápisu v domovní knize, jak vyžaduje § 101. Poté se mažou."
        ),
        "privacy_rights": "Vaše práva",
        "privacy_rights_body": (
            "Můžete požádat o kopii svých údajů, o opravu nepřesností a o informaci o "
            "zpracování. Výmaz a námitka jsou omezené po dobu trvání zákonné povinnosti "
            "údaje uchovávat. Nedochází k automatizovanému rozhodování ani profilování."
        ),
        "privacy_complaint": (
            "Domníváte-li se, že se s údaji nakládá nesprávně, můžete podat stížnost u Úřadu "
            "pro ochranu osobních údajů, Pplk. Sochora 27, 170 00 Praha 7, uoou.gov.cz."
        ),
        "privacy_required": (
            "Poskytnutí údajů je zákonný požadavek, nikoli nápad ubytovatele. Bez nich vás "
            "ubytovatel nemůže po právu ubytovat."
        ),
        "privacy_contact": "Kontakt",
        "fix_errors": "Opravte prosím následující:",
        "back": "Zpět",
    },
}


def normalise_language(value: str) -> str:
    value = (value or "").lower()[:2]
    return value if value in LANGUAGES else DEFAULT_LANGUAGE


def translator(lang: str):
    lang = normalise_language(lang)
    table = STRINGS[lang]
    fallback = STRINGS[DEFAULT_LANGUAGE]

    def translate(key: str, **kwargs) -> str:
        text = table.get(key, fallback.get(key, key))
        return text % kwargs if kwargs else text

    return translate
