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
        "language_label": "Language",
        "date_placeholder": "DD/MM/YYYY",
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
        "why_point_passport": (
            "If your host asks for it, you upload a photo of your passport or ID "
            "page so they can verify your details. Only the host sees it; it is deleted "
            "immediately after verification."
        ),
        "why_point_accuracy": (
            "You must enter truthful information that matches your travel document. The host "
            "is legally responsible for accuracy and may refuse accommodation if you will not "
            "show ID or provide correct details."
        ),
        "why_point_sign": (
            "Completing and signing the form is required for adult foreign guests. "
            "Children under 15 do not have to fill and sign personally — a parent or "
            "guardian completes the record."
        ),
        "why_point_nothing_else": (
            "Nothing here is used for marketing, and none of it goes back to the booking "
            "site you booked through."
        ),
        "pick_stay": "Find your stay",
        "pick_stay_help": "Tap your arrival and departure dates to continue.",
        "host_details": "Your host",
        "host_details_help": (
            "If you need anything about this stay, contact your host. "
            "UbyHost does not run the property and cannot change your booking."
        ),
        "host_details_missing": (
            "Use the phone or e-mail in the message that contained this link."
        ),
        "claim_title": "Confirm the number of guests and your e-mail",
        "claim_help": (
            "We e-mail a private link to this address so only you can fill in the forms. "
            "The public link then shows that the stay is assigned to your masked e-mail."
        ),
        "claim_email": "What is your e-mail address?",
        "claim_email_help": "We will send the form link here. Your address is kept private.",
        "claim_submit": "Send me the form link",
        "claim_sent_title": "Check your e-mail",
        "claim_sent_body": (
            "If the address is correct, open the confirmation link we just sent. "
            "On staging, the host can also copy the link from Settings → Guest e-mails."
        ),
        "claim_error_bad_email": "Please enter a valid e-mail address.",
        "claim_error_bad_party": "Please enter how many people are staying (1–60).",
        "claim_error_held": "Someone else is confirming this stay. Try again in a few minutes.",
        "claim_error_already_claimed": "This stay is already assigned to another e-mail address.",
        "claim_error_rate": "Too many attempts. Please wait a few minutes.",
        "assigned_title": "This reservation is already assigned",
        "assigned_body": (
            "This reservation has already been assigned the e-mail %(email)s. "
            "If that is you, we can send the private link again."
        ),
        "assigned_resend_help": "Enter the same e-mail to receive the link again.",
        "assigned_resend": "Send me the link again",
        "claim_confirm_title": "Is this your reservation?",
        "claim_confirm_help": (
            "E-mail scanners open links automatically. Click the button to prove this is you."
        ),
        "claim_confirm_button": "Yes, this is my stay",
        "claim_confirm_failed": "That confirmation link is invalid or has expired.",
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
            "Your host sent a PIN together with the registration link. "
            "Enter it to open the form."
        ),
        "pin_label": "PIN",
        "pin_submit": "Continue",
        "pin_wrong": "That PIN is not correct. Check the message from your host.",
        "pin_recovery": "Can’t find the PIN? Ask your host to resend the registration message.",
        "pin_rate_limited": "Too many incorrect PIN attempts. Wait about 15 minutes and try again.",
        "security_check_failed": "Complete the security check and try again.",
        "start_over": "Start again",
        "nights": "nights",
        "arrive": "Arrival",
        "depart": "Departure",
        "select": "This is my stay",
        "party_question": "How many people are staying?",
        "party_help": "Count everyone, including children. Each person needs their own form.",
        "party_confirm": "Continue",
        "people_progress": "%(done)s of %(total)s people completed",
        "person_progress": "Person %(current)s of %(total)s",
        "form_step_progress": "Step %(current)s of %(total)s",
        "next_step": "Continue",
        "previous_step": "Back",
        "add_person": "Add a person",
        "add_first_person": "Start with your own details",
        "saved_title": "Details saved",
        "saved_body": "Thank you. Please check what you submitted below.",
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
        "checkin_info": "Check-in",
        "checkout_info": "Check-out",
        "still_missing": "Still missing details for %(n)s person(s).",
        "add_another": "Add another person",
        "someone_missing": (
            "Is someone in your group still not registered? Every guest must be reported, "
            "so add them here."
        ),
        "continue_filling": "Continue filling in",
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
        "passport_photo_title": "Passport or ID document",
        "passport_photo_help": (
            "Your host must check your details against your travel document by law. "
            "Take a photo of the ID page, or upload a PDF (for example a registration form "
            "with up to 11 guests). Only your host can see it, and it is deleted as soon as "
            "they confirm the details."
        ),
        "passport_photo_label": "Passport or ID document",
        "passport_photo_take": "Take photo",
        "passport_photo_choose": "Choose file",
        "passport_photo_retake": "Retake or choose another",
        "passport_photo_selected": "Selected: %(name)s",
        "passport_photo_pending_nat": (
            "Choose your nationality above — foreign guests must upload a passport or ID photo here."
        ),
        "passport_photo_not_required": (
            "Czech citizens do not upload a passport photo in this form."
        ),
        "passport_photo_hint": (
            "Photo: JPEG, PNG, or WebP, up to 5 MB. PDF: up to 15 MB "
            "(e.g. a multi-guest registration form)."
        ),
        "passport_photo_too_large_image": "The photo is too large. Use a file under 5 MB.",
        "passport_photo_too_large_pdf": "The PDF is too large. Use a file under 15 MB.",
        "passport_photo_bad_type": (
            "Use a JPEG, PNG, or WebP photo, or a PDF registration form."
        ),
        "passport_photo_missing": "Please upload a photo of your passport or ID card.",
        "legal_notice_title": "Legal information",
        "legal_notice_intro": (
            "Please read this before submitting. Czech accommodation law requires both you "
            "and your host to follow the rules below."
        ),
        "legal_notice_disclaimer": (
            "UbyHost is a software tool and this information does not replace legal advice."
        ),
        "legal_notice_duty_title": "Your legal duty",
        "legal_notice_duty_body": (
            "Every accommodated person must be registered. Foreign nationals are reported to "
            "the Foreign Police within three working days of check-in. Czech citizens are "
            "recorded in the house book only. Providing these details is a statutory "
            "requirement — not optional."
        ),
        "legal_notice_accuracy_title": "Accurate information only",
        "legal_notice_accuracy_body": (
            "All fields must match your passport or national ID card exactly. Your host must "
            "verify them before any police report is sent. False or misleading information can "
            "lead to fines for the host and may affect your stay."
        ),
        "legal_notice_passport_title": "Passport photo (foreign nationals)",
        "legal_notice_passport_body": (
            "Non-Czech guests must upload a clear photo of the ID page or a PDF registration "
            "form. Your host compares it to the details you enter. The file is stored "
            "temporarily, visible only to your host in this app, and deleted as soon as they "
            "confirm the match. It is not kept after verification and is not sent to the police."
        ),
        "legal_notice_reporting_title": "Police reporting and house book",
        "legal_notice_reporting_body": (
            "Verified foreign-guest records are sent electronically to the Police of the Czech "
            "Republic (UbyPort). The same information is kept in the house book (domovní kniha) "
            "for six years and must be shown at a police inspection."
        ),
        "legal_notice_retention_title": "How long data is kept",
        "legal_notice_retention_body": (
            "Registration details and your signature are kept for six years from the last "
            "house-book entry, as required by § 101 of Act No. 326/1999 Coll. Processing is "
            "based on legal obligation (GDPR Article 6(1)(c)), not consent."
        ),
        "legal_notice_refusal_title": "If you refuse",
        "legal_notice_refusal_body": (
            "You must present a valid travel document for verification. If you refuse to "
            "provide accurate details, sign, or allow identity verification, the host may "
            "lawfully refuse accommodation."
        ),
        "legal_ack_label": (
            "I confirm that my details are accurate, I have read the legal information above "
            "and the privacy notice, and I understand my obligations under Czech law."
        ),
        "legal_ack_missing": "Please confirm that you have read the legal information.",
        "submit": "Submit my details",
        "optional": "optional",
        "required": "required",
        "check_in": "Check-in",
        "check_out": "Check-out",
        "privacy": (
            "Your details are used only to meet the host's legal reporting duty towards the "
            "Police of the Czech Republic and are kept for the statutory six years."
        ),
        "skip_to_form": "Skip to the form",
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
        "privacy_passport_photo_title": "Temporary passport photo or PDF",
        "privacy_passport_photo_body": (
            "If you are not a Czech citizen, you may upload a photograph of your passport or ID "
            "page, or a PDF registration form, so the host can verify your details. The file is "
            "processed only for that check, stored on the host's secure system, accessible only "
            "to the host, and deleted immediately after verification. It is not transmitted to "
            "the police and is not kept longer than necessary for the check."
        ),
        "privacy_recipients": "Who receives it",
        "privacy_recipients_body": (
            "The Police of the Czech Republic, Directorate of the Alien Police Service, and "
            "any officer inspecting the house book. The data stays within the EU. It is never "
            "sold, sent to the site you booked through, or used for marketing."
        ),
        "privacy_bot_protection_title": "Protecting the registration link",
        "privacy_bot_protection_body": (
            "If someone repeatedly enters a wrong access PIN, the form may show Cloudflare Turnstile "
            "to block automated abuse. Production pages may also be challenged by Cloudflare Bot Fight "
            "Mode. Those checks may process technical connection data (such as IP address) under "
            "Cloudflare's privacy notice. They are not used for marketing."
        ),
        "privacy_processor": "Who runs this website",
        "privacy_processor_body": (
            "The UbyHost software is operated by Josef Pechar, IČO 24005169, Kubelíkova 697/13, "
            "13000 Praha 3, who processes data only on the accommodation provider's instructions to "
            "run the registration form and store records. For questions about the software itself, "
            "contact the operator; for your personal data rights, contact the accommodation provider above."
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
        "language_label": "Jazyk",
        "date_placeholder": "DD/MM/RRRR",
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
        "why_point_passport": (
            "Pokud nejste občanem ČR, musíte nahrát fotografii stránky pasu nebo průkazu, "
            "aby hostitel mohl ověřit údaje. Vidí ji jen hostitel; po ověření je smazána."
        ),
        "why_point_accuracy": (
            "Musíte uvést pravdivé údaje shodné s cestovním dokladem. Hostitel za správnost "
            "odpovídá a může odmítnout ubytování, pokud doklad neukážete nebo údaje nebudou "
            "správné."
        ),
        "why_point_sign": (
            "Vyplnit a podepsat formulář musí dospělý cizinec. Děti mladší 15 let "
            "formulář osobně vyplňovat a podepisovat nemusí — záznam doplní rodič nebo opatrovník."
        ),
        "why_point_nothing_else": (
            "Údaje se nepoužívají k marketingu a nevracejí se rezervačnímu portálu, přes který "
            "jste rezervovali."
        ),
        "pick_stay": "Najděte svou rezervaci",
        "pick_stay_help": "Klepněte na termín svého pobytu a pokračujte.",
        "host_details": "Váš hostitel",
        "host_details_help": (
            "Pokud k pobytu něco potřebujete, kontaktujte ubytovatele. "
            "UbyHost objekt neprovozuje a rezervaci nemůže měnit."
        ),
        "host_details_missing": (
            "Použijte telefon nebo e-mail ze zprávy, ve které byl tento odkaz."
        ),
        "claim_title": "Potvrďte počet hostů a e-mail",
        "claim_help": (
            "Na tuto adresu pošleme soukromý odkaz, aby formuláře vyplnil jen host. "
            "Veřejný odkaz pak ukáže, že pobyt je přiřazen k vašemu zastřenému e-mailu."
        ),
        "claim_email": "Jaký je váš e-mail?",
        "claim_email_help": "Odkaz na formulář pošleme sem. Adresa zůstane soukromá.",
        "claim_submit": "Pošlete mi odkaz na formulář",
        "claim_sent_title": "Zkontrolujte e-mail",
        "claim_sent_body": (
            "Pokud je adresa správně, otevřete potvrzovací odkaz. "
            "Na stagingu může hostitel odkaz zkopírovat v Nastavení → E-maily hostům."
        ),
        "claim_error_bad_email": "Zadejte platnou e-mailovou adresu.",
        "claim_error_bad_party": "Zadejte počet osob (1–60).",
        "claim_error_held": "Někdo jiný právě potvrzuje tento pobyt. Zkuste to za chvíli.",
        "claim_error_already_claimed": "Tento pobyt už je přiřazen jiné e-mailové adrese.",
        "claim_error_rate": "Příliš mnoho pokusů. Počkejte prosím několik minut.",
        "assigned_title": "Tato rezervace už je přiřazena",
        "assigned_body": (
            "Tato rezervace už byla přiřazena e-mailu %(email)s. "
            "Pokud jste to vy, můžeme soukromý odkaz poslat znovu."
        ),
        "assigned_resend_help": "Zadejte stejný e-mail a odkaz pošleme znovu.",
        "assigned_resend": "Pošlete mi odkaz znovu",
        "claim_confirm_title": "Je to vaše rezervace?",
        "claim_confirm_help": (
            "E-mailové skenery odkazy otevírají samy. Potvrďte tlačítkem, že jste to vy."
        ),
        "claim_confirm_button": "Ano, to je můj pobyt",
        "claim_confirm_failed": "Potvrzovací odkaz je neplatný nebo vypršel.",
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
            "Ubytovatel vám spolu s odkazem poslal PIN. "
            "Zadejte ho pro otevření formuláře."
        ),
        "pin_label": "PIN",
        "pin_submit": "Pokračovat",
        "pin_wrong": "PIN není správný. Zkontrolujte zprávu od ubytovatele.",
        "pin_recovery": "Nemůžete PIN najít? Požádejte ubytovatele o nové zaslání registrační zprávy.",
        "pin_rate_limited": "Příliš mnoho chybných PINů. Počkejte asi 15 minut a zkuste to znovu.",
        "security_check_failed": "Dokončete bezpečnostní kontrolu a zkuste to znovu.",
        "start_over": "Začít znovu",
        "nights": "nocí",
        "arrive": "Příjezd",
        "depart": "Odjezd",
        "select": "To je moje rezervace",
        "party_question": "Kolik osob bude ubytováno?",
        "party_help": "Započítejte všechny včetně dětí. Každá osoba má vlastní formulář.",
        "party_confirm": "Pokračovat",
        "people_progress": "vyplněno %(done)s z %(total)s osob",
        "person_progress": "Osoba %(current)s z %(total)s",
        "form_step_progress": "Krok %(current)s z %(total)s",
        "next_step": "Pokračovat",
        "previous_step": "Zpět",
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
        "checkin_info": "Příjezd",
        "checkout_info": "Odjezd",
        "still_missing": "Chybí ještě údaje %(n)s osob(y).",
        "add_another": "Přidat další osobu",
        "someone_missing": (
            "Chybí ještě někdo z vaší skupiny? Ohlásit se musí každý ubytovaný, "
            "proto ho zde přidejte."
        ),
        "continue_filling": "Pokračovat ve vyplnění",
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
        "passport_photo_title": "Pas nebo průkaz totožnosti",
        "passport_photo_help": (
            "Hostitel musí ze zákona zkontrolovat vaše údaje proti cestovnímu dokladu. "
            "Vyfoťte stránku s údaji nebo nahrajte PDF (např. registrační formulář až pro "
            "11 hostů). Uvidí ho jen hostitel a po ověření bude smazán."
        ),
        "passport_photo_label": "Pas nebo průkaz totožnosti",
        "passport_photo_take": "Vyfotit",
        "passport_photo_choose": "Vybrat soubor",
        "passport_photo_retake": "Vyfotit nebo vybrat jiný",
        "passport_photo_selected": "Vybráno: %(name)s",
        "passport_photo_pending_nat": (
            "Nejprve zvolte státní příslušnost — cizinci zde nahrají fotografii pasu nebo průkazu."
        ),
        "passport_photo_not_required": (
            "Občané ČR v tomto formuláři fotografii pasu nenahrávají."
        ),
        "passport_photo_hint": (
            "Fotografie: JPEG, PNG nebo WebP, max. 5 MB. PDF: max. 15 MB "
            "(např. registrační formulář pro více hostů)."
        ),
        "passport_photo_too_large_image": "Fotografie je příliš velká. Maximálně 5 MB.",
        "passport_photo_too_large_pdf": "PDF je příliš velké. Maximálně 15 MB.",
        "passport_photo_bad_type": (
            "Použijte fotografii JPEG, PNG nebo WebP, nebo PDF registrační formulář."
        ),
        "passport_photo_missing": "Nahrajte prosím fotografii pasu nebo občanského průkazu.",
        "legal_notice_title": "Právní informace",
        "legal_notice_intro": (
            "Před odesláním si prosím přečtěte. Český zákon o ubytování vyžaduje, aby vy i "
            "ubytovatel dodrželi níže uvedená pravidla."
        ),
        "legal_notice_disclaimer": (
            "UbyHost je softwarový nástroj a tyto informace nenahrazují právní poradenství."
        ),
        "legal_notice_duty_title": "Vaše zákonná povinnost",
        "legal_notice_duty_body": (
            "Každá ubytovaná osoba musí být evidována. Cizinci se oznamují cizinecké policii "
            "do tří pracovních dnů od ubytování. Občané ČR se zapisují pouze do domovní knihy. "
            "Poskytnutí údajů je zákonný požadavek — není dobrovolné."
        ),
        "legal_notice_accuracy_title": "Pouze pravdivé údaje",
        "legal_notice_accuracy_body": (
            "Všechna pole musí přesně odpovídat pasu nebo občanskému průkazu. Hostitel je musí "
            "ověřit před odesláním na policii. Nepravdivé údaje mohou vést k pokutám pro "
            "ubytovatele a ovlivnit váš pobyt."
        ),
        "legal_notice_passport_title": "Fotografie pasu (cizinci)",
        "legal_notice_passport_body": (
            "Cizinci musí nahrát čitelnou fotografii stránky s údaji nebo PDF registrační "
            "formulář. Hostitel ho porovná s vyplněnými poli. Soubor je uložen dočasně, vidí "
            "ho jen hostitel v této aplikaci, a po potvrzení shody je smazán. Po ověření se "
            "neuchovává a neposílá se policii."
        ),
        "legal_notice_reporting_title": "Hlášení policii a domovní kniha",
        "legal_notice_reporting_body": (
            "Ověřené záznamy cizinců se elektronicky odesílají Policii ČR (UbyPort). Stejné "
            "údaje se vedou v domovní knize po dobu šesti let a předkládají při kontrole."
        ),
        "legal_notice_retention_title": "Jak dlouho se údaje uchovávají",
        "legal_notice_retention_body": (
            "Registrační údaje a podpis se uchovávají šest let od posledního zápisu v domovní "
            "knize podle § 101 zákona č. 326/1999 Sb. Zpracování je na základě právní povinnosti "
            "(GDPR čl. 6 odst. 1 písm. c), nikoli souhlasu."
        ),
        "legal_notice_refusal_title": "Pokud odmítnete",
        "legal_notice_refusal_body": (
            "Musíte předložit platný cestovní doklad k ověření. Pokud odmítnete poskytnout "
            "správné údaje, podepsat se nebo umožnit ověření totožnosti, může vás ubytovatel "
            "po právu odmítnout."
        ),
        "legal_ack_label": (
            "Potvrzuji, že mé údaje jsou správné, že jsem si přečetl(a) právní informace výše "
            "a informaci o zpracování údajů a rozumím svým povinnostem podle českého práva."
        ),
        "legal_ack_missing": "Potvrďte prosím, že jste si přečetli právní informace.",
        "submit": "Odeslat údaje",
        "optional": "nepovinné",
        "required": "povinné",
        "check_in": "Check-in",
        "check_out": "Check-out",
        "privacy": (
            "Údaje slouží výhradně ke splnění zákonné oznamovací povinnosti ubytovatele vůči "
            "Policii České republiky a uchovávají se zákonných 6 let."
        ),
        "skip_to_form": "Přejít na formulář",
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
        "privacy_passport_photo_title": "Dočasná fotografie pasu nebo PDF",
        "privacy_passport_photo_body": (
            "Pokud nejste občanem ČR, můžete nahrát fotografii stránky pasu nebo průkazu, "
            "nebo PDF registrační formulář, aby hostitel ověřil údaje. Soubor slouží jen k této "
            "kontrole, ukládá se v zabezpečeném systému hostitele, je přístupný pouze hostiteli "
            "a po ověření je okamžitě smazán. Nepředává se policii a neuchovává se déle, než je "
            "nutné pro kontrolu."
        ),
        "privacy_recipients": "Komu se předávají",
        "privacy_recipients_body": (
            "Policii České republiky, Ředitelství služby cizinecké policie, a kontrolnímu "
            "orgánu při nahlédnutí do domovní knihy. Údaje zůstávají v EU. Neprodávají se, "
            "neposílají rezervačnímu portálu ani se nepoužívají k marketingu."
        ),
        "privacy_bot_protection_title": "Ochrana registračního odkazu",
        "privacy_bot_protection_body": (
            "Při opakovaně chybném PIN může formulář zobrazit Cloudflare Turnstile proti "
            "automatizovanému zneužití. Produkční stránky může rovněž prověřit Cloudflare Bot Fight "
            "Mode. Kontroly mohou zpracovat technické údaje o připojení (např. IP) podle zásad "
            "Cloudflare. Nepoužívají se pro marketing."
        ),
        "privacy_processor": "Kdo provozuje tento web",
        "privacy_processor_body": (
            "Software UbyHost provozuje Josef Pechar, IČO 24005169, Kubelíkova 697/13, 13000 Praha 3, "
            "který údaje zpracovává pouze na pokyn poskytovatele ubytování kvůli chodu registračního "
            "formuláře a uložení záznamů. Na software se obracejte na provozovatele; na práva k "
            "osobním údajům na poskytovatele ubytování uvedeného výše."
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
