"""Guest-facing strings in English and Czech.

Guests are by definition foreigners, so English is the catalog a missing key
falls back to, and the language the form speaks until the guest chooses. The
*page* default is the signed-out public default, which the host pages share --
see ``host_i18n.PUBLIC_DEFAULT_LANGUAGE``.
"""
from __future__ import annotations

from typing import Dict

from . import host_i18n

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
        "arrival_kicker": "Guest registration",
        "arrival_welcome": "Welcome — guest registration for %(facility)s.",
        "arrival_question": "Which stay is yours?",
        "arrival_help": "Choose your arrival and departure dates to continue.",
        "arrival_cta": "That’s my stay",
        "stay_ongoing": "Ongoing",
        "host_details": "Your host",
        "host_details_help": (
            "If there is any problem, feel free to contact your host. "
            "UbyHost does not run the property and cannot change your booking."
        ),
        "host_details_missing": (
            "Use the phone or e-mail in the message that contained this link."
        ),
        "message_from_host": "A message from your host",
        "claim_title": "Confirm the number of guests and your e-mail",
        "claim_help": (
            "We e-mail a private link to this address so only you can fill in the forms. "
            "The public link then shows that the stay is assigned to your masked e-mail."
        ),
        "claim_email": "What is your e-mail address?",
        "claim_email_help": (
            "We use this address to secure this reservation, send the private form link, "
            "one reminder if the forms are incomplete the day before check-in, and a completion "
            "receipt. The property manager receives the completion copy and authorised host users "
            "can see the address; public guest screens show only a masked version. No marketing."
        ),
        "claim_cookie_help": (
            "Strictly necessary cookies remember PIN access for up to 7 days and language, the "
            "confirmed stay, and forms submitted on this device for up to 60 days. UbyHost uses "
            "no advertising or analytics cookies."
        ),
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
        "claim_error_rate": "Too many link requests. Please try again in a little while.",
        "claim_error_cooldown": "We just sent a link to this address. Please wait a minute before asking again.",
        "claim_error_recipient_rate": "This e-mail has received too many registration links. Try again later.",
        "claim_error_bot": "Please complete the security check and try again.",
        "assigned_title": "This reservation is already assigned",
        "assigned_body": (
            "This reservation has already been assigned the e-mail %(email)s. "
            "If that is you, we can send the private link again."
        ),
        "assigned_resend_help": "Enter the same e-mail to receive the link again.",
        "assigned_resend": "Send me the link again",
        "assigned_stay_label": "Your selected stay",
        "assigned_private_link": "For your privacy, registration continues through the secure link sent to this address.",
        "assigned_last_sent": "Private link last sent %(date)s",
        "assigned_not_mine": "This is not my reservation",
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
            "The apartment link only lists stays that start in the next few days. If your "
            "arrival has already passed, open the stay-specific link from your host or "
            "confirmation e-mail, or message your host."
        ),
        "bad_link_title": "This guest link is not valid",
        "bad_link_help": "It may be incomplete or may have been replaced. Please ask your host for a new link.",
        "stay_gone_title": "That stay is no longer open for registration",
        "stay_gone_help": (
            "The dates may have changed, the booking may have been cancelled, or your host "
            "may have closed registration for this stay. Please message your host."
        ),
        "form_expired_title": "This form timed out",
        "form_expired_help": (
            "Nothing was saved. Reload the page, or start again from the link below."
        ),
        "rate_limited_title": "Too many attempts from your connection",
        "rate_limited_help": (
            "Nothing was saved. Wait about 15 minutes and try again — if you are stuck, "
            "message your host."
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
        "pin_locked_out": (
            "Too many incorrect PIN attempts, so this link is paused for a day. "
            "Ask your host to send a new PIN."
        ),
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
        "signature_missing": "Please sign in the box before you continue.",
        "signature_kept": "Signature already saved. Sign again only if you need to change it.",
        "passport_photo_title": "Passport or ID document",
        "passport_photo_help": (
            "Your host must check your details against your travel document by law. "
            "Take a photo of the ID page, or upload a PDF (for example a registration form "
            "with up to 11 guests). Access in the app is restricted to authorised host users. "
            "It is deleted when they confirm the details; a scheduled stale-file sweep is the backstop."
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
            "All fields must match your passport or national ID card exactly. The host remains "
            "responsible for accuracy and may check your document, but automatic reporting can "
            "occur without an in-app verification step. False or misleading information can lead "
            "to fines for the host and may affect your stay."
        ),
        "legal_notice_passport_title": "Passport photo (foreign nationals)",
        "legal_notice_passport_body": (
            "Non-Czech guests must upload a clear photo of the ID page or a PDF registration "
            "form. Your host compares it to the details you enter. The file is stored "
            "temporarily with access restricted to authorised host users in this app, and deleted "
            "when they confirm the match. If it is not verified, a scheduled sweep removes stale "
            "files after the stay. It is not sent to the police."
        ),
        "legal_notice_reporting_title": "Police reporting and house book",
        "legal_notice_reporting_body": (
            "Complete foreign-guest records may be sent electronically and automatically to the "
            "Police of the Czech Republic (UbyPort), immediately or after the delay selected by "
            "the host, without waiting for in-app identity verification. The same information is "
            "kept in the house book for six years and must be shown at a police inspection."
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
        "privacy_controller": "Your data controller",
        "privacy_controller_body": (
            "This legal entity determines why and how your guest data is used and is responsible "
            "for your GDPR rights. A different name for the stay contact below does not change this role."
        ),
        "privacy_controller_missing": (
            "Your host must identify the business responsible for your data. Ask your host "
            "for its registered name and address if they are missing here."
        ),
        "privacy_stay_contact": "Questions about your stay",
        "privacy_stay_contact_body": (
            "The property manager is your practical contact for arrival, accommodation, and booking "
            "questions. Contact the data controller above for access, correction, deletion, or objection requests."
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
            "start and end of your stay, signature, declared party size, and the e-mail address "
            "used to claim the reservation. Party size is used to determine whether every expected "
            "guest form is complete and is retained with the stay record."
        ),
        "privacy_data_body_no_email": (
            "Given name and surname, date of birth, nationality, travel document number, visa "
            "number where one was issued, permanent home address abroad, purpose of stay, the "
            "start and end of your stay, signature, and declared party size. This version of the "
            "form does not collect your e-mail address. Party size is used to determine whether every "
            "expected guest form is complete and is retained with the stay record."
        ),
        "privacy_email_title": "E-mail messages and masking",
        "privacy_email_body": (
            "Your e-mail secures the reservation and is used to send the private form link, one "
            "day-before reminder if the declared forms remain incomplete, and a completion receipt. "
            "The property manager receives a copy of the completion receipt. The full address "
            "is available to the configured data controller and to the delivery provider "
            "where enabled; public guest screens display only a masked address. It is not used for marketing."
        ),
        "privacy_cookies_title": "Necessary cookies",
        "privacy_cookies_body": (
            "UbyHost uses only necessary guest cookies: PIN access for up to 7 days, and language "
            "and forms submitted on this device for up to 60 days. When e-mail claims are enabled, "
            "confirmed-reservation access is also remembered for up to 60 days. "
            "They prevent another guest from seeing or changing your form and keep the workflow usable. "
            "Cloudflare may set security identifiers when Turnstile or bot protection is triggered. "
            "There are no advertising or analytics cookies."
        ),
        "privacy_passport_photo_title": "Temporary passport photo or PDF",
        "privacy_passport_photo_body": (
            "If you are not a Czech citizen, you may upload a photograph of your passport or ID "
            "page, or a PDF registration form, so the host can verify your details. The file is "
            "processed only for that check and access in the app is restricted to authorised host "
            "users. It is deleted after verification; if it remains unverified, a scheduled sweep "
            "removes it after the stay. Restricted operator or infrastructure access may be required "
            "to operate and secure the service. It is not transmitted to the police."
        ),
        "privacy_recipients": "Who receives it",
        "privacy_recipients_body": (
            "The Police of the Czech Republic, Directorate of the Alien Police Service, and "
            "any officer inspecting the house book; your accommodation provider; UbyHost as its "
            "processor; and an e-mail delivery provider where messaging is enabled. The data is "
            "never sold, sent back to the booking site, or used for marketing."
        ),
        "privacy_recipients_body_no_email": (
            "The Police of the Czech Republic, Directorate of the Alien Police Service, any officer "
            "inspecting the house book, your accommodation provider, and UbyHost as its processor. "
            "The data is never sold, sent back to the booking site, or used for marketing."
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
            "The UbyHost software is operated by %(name)s, IČO %(ico)s, %(address)s, "
            "who processes data only on the configured controller's instructions to "
            "run the registration form, transactional messages, and stored records. Software support "
            "is %(email)s; questions about your stay go to your host, while personal-data "
            "rights requests go to the controller named above."
        ),
        "privacy_retention": "How long it is kept",
        "privacy_retention_body": (
            "House-book registration details and signatures are kept for six years from the last "
            "entry, as § 101 requires. The claim e-mail remains linked while the reservation record "
            "is retained unless the host releases the claim. Completed or failed message-delivery "
            "records and staging console copies are normally deleted after 14 days; limited backup "
            "copies may persist until their retention cycle expires."
        ),
        "privacy_retention_body_no_email": (
            "House-book registration details and signatures are kept for six years from the last "
            "entry, as § 101 requires. Limited backup copies may persist until their retention cycle expires."
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
        # E-mail the app sends to a guest. The plain-text and the HTML part are
        # both built from these keys, so the two cannot drift apart.
        "mail_claim_subject": "Continue your Prague guest registration",
        "mail_claim_heading": "Confirm your stay",
        "mail_claim_intro": (
            "Confirm your stay at %(property)s (%(dates)s) by opening the link below."
        ),
        "mail_claim_action": "Confirm my stay",
        "mail_link_fallback": (
            "If the button does not work, copy this address into your browser:"
        ),
        "mail_claim_expiry": (
            "The link is valid for 30 minutes and stops working as soon as you "
            "confirm the stay."
        ),
        "mail_claim_expiry_resend": (
            "This is a new link and the previous one has stopped working. It is "
            "valid for 30 minutes and stops working as soon as you confirm the stay."
        ),
        "mail_claim_next_label": "What happens next",
        "mail_claim_next_body": (
            "You will enter the details of every guest of this stay and then sign. "
            "It takes about two minutes per guest and works on a phone."
        ),
        "mail_completion_subject": "Guest registration received",
        "mail_completion_heading": "Registration received",
        "mail_completion_intro": (
            "Thank you. We have received the details for your stay at %(property)s "
            "(%(dates)s)."
        ),
        "mail_completion_action": "Open my stay",
        "mail_completion_note_label": "Please note",
        "mail_completion_note": (
            "This receipt is not proof of police reporting. Depending on your host's "
            "settings, complete foreign-guest records may be sent to UbyPort "
            "automatically."
        ),
        "mail_reminder_guest_subject": "Please finish your guest registration",
        "mail_reminder_guest_heading": "Your stay starts tomorrow",
        "mail_reminder_guest_intro": (
            "Your stay at %(property)s starts tomorrow and the guest registration is "
            "not complete yet."
        ),
        "mail_reminder_guest_action": "Finish the registration",
        "mail_reminder_guest_note_label": "One reminder only",
        "mail_reminder_guest_note": (
            "This is the only incomplete-registration reminder we will send."
        ),
        "mail_reminder_guest_help": (
            "If you have already sent everything, you can ignore this message."
        ),
        # The footer. Guests are told to reach the host, never UbyHost support:
        # the same rule the guest pages follow.
        "mail_guest_footer_why": (
            "You received this e-mail because your stay at %(property)s is registered "
            "with this address."
        ),
        "mail_guest_footer_host_label": "Your host",
        "mail_guest_footer_help": "Reply to this e-mail to reach your host.",
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
        "arrival_kicker": "Registrace ubytovaného",
        "arrival_welcome": "Vítejte — registrace ubytovaného pro %(facility)s.",
        "arrival_question": "Který pobyt je váš?",
        "arrival_help": "Vyberte termín příjezdu a odjezdu a pokračujte.",
        "arrival_cta": "To je můj pobyt",
        "stay_ongoing": "Právě probíhá",
        "host_details": "Váš hostitel",
        "host_details_help": (
            "Pokud máte jakýkoli problém, neváhejte kontaktovat svého hostitele. "
            "UbyHost objekt neprovozuje a rezervaci nemůže měnit."
        ),
        "host_details_missing": (
            "Použijte telefon nebo e-mail ze zprávy, ve které byl tento odkaz."
        ),
        "message_from_host": "Zpráva od vašeho ubytovatele",
        "claim_title": "Potvrďte počet hostů a e-mail",
        "claim_help": (
            "Na tuto adresu pošleme soukromý odkaz, aby formuláře vyplnil jen host. "
            "Veřejný odkaz pak ukáže, že pobyt je přiřazen k vašemu zastřenému e-mailu."
        ),
        "claim_email": "Jaký je váš e-mail?",
        "claim_email_help": (
            "Adresu používáme k zabezpečení této rezervace, zaslání soukromého odkazu, "
            "jednoho upozornění při nedokončení den před příjezdem a potvrzení o dokončení. "
            "Správce objektu obdrží kopii potvrzení a oprávnění uživatelé ubytovatele mohou adresu "
            "vidět; veřejné obrazovky pro hosty zobrazují jen zastřenou podobu. Žádný marketing."
        ),
        "claim_cookie_help": (
            "Nezbytné cookies si pamatují přístup přes PIN nejvýše 7 dní a jazyk, potvrzený pobyt "
            "a formuláře odeslané z tohoto zařízení nejvýše 60 dní. UbyHost nepoužívá reklamní "
            "ani analytické cookies."
        ),
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
        "claim_error_rate": "Příliš mnoho žádostí o odkaz. Zkuste to prosím za chvíli.",
        "claim_error_cooldown": "Na tuto adresu jsme odkaz právě poslali. Počkejte prosím minutu a zkuste to znovu.",
        "claim_error_recipient_rate": "Na tento e-mail bylo odesláno příliš mnoho odkazů. Zkuste to později.",
        "claim_error_bot": "Dokončete prosím bezpečnostní kontrolu a zkuste to znovu.",
        "assigned_title": "Tato rezervace už je přiřazena",
        "assigned_body": (
            "Tato rezervace už byla přiřazena e-mailu %(email)s. "
            "Pokud jste to vy, můžeme soukromý odkaz poslat znovu."
        ),
        "assigned_resend_help": "Zadejte stejný e-mail a odkaz pošleme znovu.",
        "assigned_resend": "Pošlete mi odkaz znovu",
        "assigned_stay_label": "Vybraný pobyt",
        "assigned_private_link": "Kvůli ochraně soukromí pokračuje registrace přes zabezpečený odkaz zaslaný na tuto adresu.",
        "assigned_last_sent": "Soukromý odkaz naposledy odeslán %(date)s",
        "assigned_not_mine": "Toto není moje rezervace",
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
            "Odkaz bytu zobrazuje jen pobyty začínající v nejbližších dnech. Pokud už "
            "příjezd proběhl, otevřete odkaz konkrétního pobytu z e-mailu nebo od "
            "ubytovatele, nebo ubytovateli napište."
        ),
        "bad_link_title": "Tento odkaz není platný",
        "bad_link_help": "Odkaz může být neúplný nebo byl nahrazen. Požádejte ubytovatele o nový odkaz.",
        "stay_gone_title": "Tento pobyt už není otevřený k registraci",
        "stay_gone_help": (
            "Termín se mohl změnit, rezervace mohla být zrušena, nebo ubytovatel registraci "
            "pro tento pobyt uzavřel. Napište prosím ubytovateli."
        ),
        "form_expired_title": "Tomuto formuláři vypršela platnost",
        "form_expired_help": (
            "Nic se neuložilo. Načtěte stránku znovu nebo začněte znovu přes odkaz níže."
        ),
        "rate_limited_title": "Příliš mnoho pokusů z vašeho připojení",
        "rate_limited_help": (
            "Nic se neuložilo. Počkejte asi 15 minut a zkuste to znovu — pokud se "
            "zaseknete, napište ubytovateli."
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
        "pin_locked_out": (
            "Příliš mnoho chybných pokusů o PIN, proto je tento odkaz na den pozastaven. "
            "Požádejte ubytovatele o nový PIN."
        ),
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
        "signature_missing": "Než budete pokračovat, podepište se prosím do rámečku.",
        "signature_kept": "Podpis je uložený. Podepište se znovu jen pokud ho chcete změnit.",
        "passport_photo_title": "Pas nebo průkaz totožnosti",
        "passport_photo_help": (
            "Hostitel musí ze zákona zkontrolovat vaše údaje proti cestovnímu dokladu. "
            "Vyfoťte stránku s údaji nebo nahrajte PDF (např. registrační formulář až pro "
            "11 hostů). Přístup v aplikaci mají jen oprávnění uživatelé ubytovatele. Po ověření "
            "se soubor smaže; pojistkou je plánované mazání starých souborů."
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
            "Všechna pole musí přesně odpovídat pasu nebo občanskému průkazu. Ubytovatel nadále "
            "odpovídá za správnost a může doklad zkontrolovat, automatické hlášení však může "
            "proběhnout bez ověření v aplikaci. Nepravdivé údaje mohou vést k pokutám pro "
            "ubytovatele a ovlivnit váš pobyt."
        ),
        "legal_notice_passport_title": "Fotografie pasu (cizinci)",
        "legal_notice_passport_body": (
            "Cizinci musí nahrát čitelnou fotografii stránky s údaji nebo PDF registrační "
            "formulář. Hostitel ho porovná s vyplněnými poli. Soubor je uložen dočasně a přístup "
            "v aplikaci mají jen oprávnění uživatelé ubytovatele. Po potvrzení shody se smaže; "
            "pokud ověřen není, plánovaná úloha odstraní starý soubor po pobytu. Policii se neposílá."
        ),
        "legal_notice_reporting_title": "Hlášení policii a domovní kniha",
        "legal_notice_reporting_body": (
            "Kompletní záznamy cizinců mohou být elektronicky a automaticky odeslány Policii ČR "
            "(UbyPort), okamžitě nebo po prodlevě zvolené ubytovatelem, bez čekání na ověření "
            "totožnosti v aplikaci. Stejné údaje se vedou v domovní knize šest let."
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
        "privacy_controller": "Správce vašich osobních údajů",
        "privacy_controller_body": (
            "Tento právní subjekt určuje, proč a jak se údaje hostů používají, a odpovídá za vaše "
            "práva podle GDPR. Jiný kontakt pro pobyt uvedený níže tuto roli nemění."
        ),
        "privacy_controller_missing": (
            "Ubytovatel musí uvést subjekt odpovědný za vaše údaje. Pokud zde jeho údaje chybí, "
            "požádejte ubytovatele o název a sídlo."
        ),
        "privacy_stay_contact": "Dotazy k pobytu",
        "privacy_stay_contact_body": (
            "Správce/provozovatel ubytování je praktickým kontaktem pro příjezd, ubytování a rezervaci. "
            "Žádosti o přístup, opravu, výmaz nebo námitku směřujte správci údajů uvedenému výše."
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
            "konec pobytu, podpis, nahlášený počet hostů a e-mail použitý k převzetí rezervace. "
            "Počet osob slouží ke kontrole, zda jsou hotové všechny očekávané formuláře, a uchovává "
            "se se záznamem pobytu."
        ),
        "privacy_data_body_no_email": (
            "Jméno a příjmení, datum narození, státní občanství, číslo cestovního dokladu, "
            "číslo víza (bylo-li vydáno), trvalé bydliště v zahraničí, účel pobytu, počátek a "
            "konec pobytu, podpis a nahlášený počet hostů. Tato verze formuláře e-mail nesbírá. "
            "Počet osob slouží ke kontrole, zda jsou hotové všechny očekávané formuláře, a uchovává "
            "se se záznamem pobytu."
        ),
        "privacy_email_title": "E-mailové zprávy a zastření adresy",
        "privacy_email_body": (
            "E-mail zabezpečuje rezervaci a používá se k zaslání soukromého odkazu, jednoho "
            "upozornění den před příjezdem, pokud formuláře zůstávají neúplné, a potvrzení o "
            "dokončení. Správce objektu obdrží kopii potvrzení. Plná adresa je dostupná "
            "nastavenému správci osobních údajů a případně poskytovateli doručení e-mailu; "
            "veřejné obrazovky pro hosty zobrazují jen zastřenou adresu. K marketingu se nepoužívá."
        ),
        "privacy_cookies_title": "Nezbytné cookies",
        "privacy_cookies_body": (
            "UbyHost používá jen nezbytné cookies pro hosty: přístup přes PIN nejvýše 7 dní a "
            "jazyk a formuláře odeslané z tohoto zařízení nejvýše 60 dní. Při zapnutém převzetí "
            "e-mailem se nejvýše 60 dní pamatuje i přístup k potvrzené rezervaci. Brání jinému "
            "hostovi vidět nebo měnit váš formulář a zachovávají funkčnost. "
            "Cloudflare může nastavit bezpečnostní identifikátory při aktivaci Turnstile nebo ochrany "
            "proti botům. Reklamní ani analytické cookies se nepoužívají."
        ),
        "privacy_passport_photo_title": "Dočasná fotografie pasu nebo PDF",
        "privacy_passport_photo_body": (
            "Pokud nejste občanem ČR, můžete nahrát fotografii stránky pasu nebo průkazu, "
            "nebo PDF registrační formulář, aby hostitel ověřil údaje. Soubor slouží jen k této "
            "kontrole a přístup v aplikaci mají jen oprávnění uživatelé ubytovatele. Po ověření "
            "se smaže; zůstane-li neověřený, plánovaná úloha jej odstraní po pobytu. Omezený přístup "
            "provozovatele nebo infrastruktury může být nutný k provozu a zabezpečení služby. "
            "Policii se neposílá."
        ),
        "privacy_recipients": "Komu se předávají",
        "privacy_recipients_body": (
            "Policii České republiky, Ředitelství služby cizinecké policie, a kontrolnímu "
            "orgánu při nahlédnutí do domovní knihy; poskytovateli ubytování; UbyHostu jako "
            "zpracovateli a při zapnutých zprávách poskytovateli doručení e-mailu. Údaje se "
            "neprodávají, neposílají zpět rezervačnímu portálu ani nepoužívají k marketingu."
        ),
        "privacy_recipients_body_no_email": (
            "Policii České republiky, Ředitelství služby cizinecké policie, kontrolnímu orgánu "
            "při nahlédnutí do domovní knihy, poskytovateli ubytování a UbyHostu jako jeho "
            "zpracovateli. Údaje se neprodávají, neposílají zpět rezervačnímu portálu ani "
            "nepoužívají k marketingu."
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
            "Software UbyHost provozuje %(name)s, IČO %(ico)s, %(address)s. Údaje zpracovává pouze "
            "na pokyn nastaveného správce údajů kvůli chodu registračního "
            "formuláře, transakčním zprávám a uložení záznamů. Podpora software je "
            "%(email)s; dotazy k pobytu směřujte na hostitele a žádosti o práva k osobním "
            "údajům na správce uvedeného výše."
        ),
        "privacy_retention": "Jak dlouho se uchovávají",
        "privacy_retention_body": (
            "Registrační údaje domovní knihy a podpisy se uchovávají šest let od posledního zápisu "
            "podle § 101. E-mail k převzetí zůstává spojen s rezervací po dobu jejího uchování, "
            "pokud ubytovatel převzetí neuvolní. Dokončené či neúspěšné záznamy doručení a konzolové "
            "kopie ve stagingu se běžně mažou po 14 dnech; omezené zálohy mohou zůstat do konce cyklu."
        ),
        "privacy_retention_body_no_email": (
            "Registrační údaje domovní knihy a podpisy se uchovávají šest let od posledního zápisu "
            "podle § 101. Omezené zálohy mohou zůstat do konce svého retenčního cyklu."
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
        # E-mail, který aplikace posílá hostovi. Textová i HTML část se skládá
        # z těchto klíčů, takže se nemohou rozejít.
        "mail_claim_subject": "Pokračujte v registraci hostů",
        "mail_claim_heading": "Potvrďte svůj pobyt",
        "mail_claim_intro": (
            "Potvrďte pobyt v %(property)s (%(dates)s) otevřením odkazu níže."
        ),
        "mail_claim_action": "Potvrdit pobyt",
        "mail_link_fallback": (
            "Pokud tlačítko nefunguje, zkopírujte tuto adresu do prohlížeče:"
        ),
        "mail_claim_expiry": (
            "Odkaz platí 30 minut a přestane fungovat ve chvíli, kdy pobyt potvrdíte."
        ),
        "mail_claim_expiry_resend": (
            "Toto je nový odkaz, předchozí už nefunguje. Platí 30 minut a přestane "
            "fungovat ve chvíli, kdy pobyt potvrdíte."
        ),
        "mail_claim_next_label": "Co bude následovat",
        "mail_claim_next_body": (
            "Vyplníte údaje ke každému hostovi tohoto pobytu a poté je podepíšete. "
            "Zabere to přibližně dvě minuty na hosta a funguje to i na telefonu."
        ),
        "mail_completion_subject": "Registrace hostů byla přijata",
        "mail_completion_heading": "Registrace byla přijata",
        "mail_completion_intro": (
            "Děkujeme. Obdrželi jsme údaje k vašemu pobytu v %(property)s (%(dates)s)."
        ),
        "mail_completion_action": "Otevřít můj pobyt",
        "mail_completion_note_label": "Upozornění",
        "mail_completion_note": (
            "Toto potvrzení není důkazem hlášení policii. Podle nastavení ubytovatele "
            "mohou být kompletní záznamy cizinců odeslány do UbyPortu automaticky."
        ),
        "mail_reminder_guest_subject": "Dokončete prosím registraci hostů",
        "mail_reminder_guest_heading": "Váš pobyt začíná zítra",
        "mail_reminder_guest_intro": (
            "Váš pobyt v %(property)s začíná zítra a registrace hostů zatím není "
            "dokončená."
        ),
        "mail_reminder_guest_action": "Dokončit registraci",
        "mail_reminder_guest_note_label": "Pouze jedno upozornění",
        "mail_reminder_guest_note": (
            "Toto je jediné upozornění na nedokončenou registraci, které vám pošleme."
        ),
        "mail_reminder_guest_help": (
            "Pokud jste už vše odeslali, můžete tuto zprávu ignorovat."
        ),
        # Patička. Hosté se obracejí na ubytovatele, nikdy na podporu UbyHostu:
        # stejné pravidlo jako na stránkách pro hosty.
        "mail_guest_footer_why": (
            "Tento e-mail dostáváte, protože je s touto adresou veden váš pobyt "
            "v %(property)s."
        ),
        "mail_guest_footer_host_label": "Váš hostitel",
        "mail_guest_footer_help": "Odpovězte na tento e-mail a spojíte se s hostitelem.",
    },
}


def translator(lang: str):
    table = STRINGS[host_i18n.normalise_language(lang)]
    fallback = STRINGS[DEFAULT_LANGUAGE]

    def translate(key: str, **kwargs) -> str:
        return host_i18n.lookup(table, fallback, key, **kwargs)

    return translate
