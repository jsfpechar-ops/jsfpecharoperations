"""Guest-facing strings in English, Czech, German, Spanish and French.

Guests are by definition foreigners, so English is the catalog a missing key
falls back to, and the language the form speaks when the guest's browser asks
for nothing we speak. Only the guest side has more than two languages; the host
app stays English and Czech (``host_i18n.LANGUAGES``).

WP26: the guest's language is chosen in this order, privacy first -- no IP
lookup, no outside service, nothing new stored about the guest:

1. what the guest chose (``?lang=`` or the switcher's existing cookie),
2. the best match in the browser's ``Accept-Language`` header, q-values
   honoured (``de-AT`` -> de, ``es-MX`` -> es, ``fr-CA`` -> fr, ``sk`` -> cs),
3. English.

WP33: ``UBYHOST_GUEST_LANGS`` decides which of the catalogs guests are offered.
English and Czech are always on. German, Spanish and French stay off until a
native speaker has read the catalog, because a mistranslated sentence on a form
that asks for passport details costs the host the guest's trust.
"""
from __future__ import annotations

import os
from typing import Dict, Optional, Tuple

from . import host_i18n

LANGUAGES = ("en", "cs", "de", "es", "fr")
DEFAULT_LANGUAGE = "en"
ALWAYS_ON = ("en", "cs")
DEFAULT_GUEST_LANGS = "en,cs"


def enabled_languages() -> Tuple[str, ...]:
    """The guest languages switched on, in catalog order.

    Read on every call, so the owner can turn a language on by editing ``.env``
    and restarting, and a test can set it with ``monkeypatch.setenv``.
    """
    raw = os.environ.get("UBYHOST_GUEST_LANGS", DEFAULT_GUEST_LANGS)
    wanted = {code.strip().lower() for code in raw.split(",") if code.strip()}
    return tuple(code for code in LANGUAGES if code in ALWAYS_ON or code in wanted)

# The switcher's labels: each language in its own name, which a foreigner can
# read when the page is in a language they do not.
ENDONYMS: Dict[str, str] = {
    "en": "English",
    "cs": "Čeština",
    "de": "Deutsch",
    "es": "Español",
    "fr": "Français",
}

# Browser language prefixes that map onto a catalog we have. Slovak readers
# get Czech, which they read without effort; the rest map onto themselves.
_ACCEPT_ALIASES: Dict[str, str] = {"sk": "cs"}


def supported_language(value: Optional[str]) -> Optional[str]:
    """The guest language code for ``value``, or None when we do not speak it."""
    code = (value or "").strip().lower().replace("_", "-").split("-")[0]
    code = _ACCEPT_ALIASES.get(code, code)
    return code if code in enabled_languages() else None


def normalise_language(value: Optional[str]) -> str:
    """A guest language we speak, English when the value names none."""
    return supported_language(value) or DEFAULT_LANGUAGE


def accept_language_match(header: Optional[str]) -> Optional[str]:
    """The best guest language for an ``Accept-Language`` header, or None.

    Tags are ranked by q-value (default 1, ``q=0`` means "not this one"); on a
    tie the header's own order wins, which is how browsers express preference.
    The wildcard ``*`` names no language, so it never decides on its own. Only
    the header is read: nothing about the visitor is looked up or stored.
    """
    ranked = []
    for position, part in enumerate((header or "").split(",")):
        pieces = [piece.strip() for piece in part.split(";")]
        tag = pieces[0].lower()
        if not tag or tag == "*":
            continue
        quality = 1.0
        for param in pieces[1:]:
            name, _, value = param.partition("=")
            if name.strip().lower() == "q":
                try:
                    quality = float(value.strip())
                except ValueError:
                    quality = 0.0
        if quality <= 0:
            continue
        ranked.append((-quality, position, tag))
    for _quality, _position, tag in sorted(ranked):
        code = supported_language(tag)
        if code:
            return code
    return None

STRINGS: Dict[str, Dict[str, str]] = {
    "en": {
        "title": "Guest registration",
        "language_label": "Language",
        "date_placeholder": "DD.MM.YYYY",
        "legal_intro": "Czech law requires your host to register every guest, including children, and report foreign guests to the police.",
        "why_title": "Why you are filling this in",
        "why_law": (
            "Act No. 326/1999 Coll., on the Residence of Foreign Nationals, §§ 101–103."
        ),
        "why_point_accuracy": (
            "You must enter truthful information that matches your travel document. The host "
            "is legally responsible for accuracy and may refuse accommodation if you will not "
            "show ID or provide correct details."
        ),
        "pick_stay": "Find your stay",
        "pick_stay_help": "Tap your arrival and departure dates to continue.",
        "arrival_question": "Which stay is yours?",
        "arrival_cta": "That’s my stay",
        # Ticket Wallet skin (guest-ticket.css)
        "tw_label_access": "Private access",
        "tw_label_stay": "Your stay",
        "tw_label_email": "Your group and e-mail",
        "tw_label_confirm": "Confirm your stay",
        "tw_label_group": "Your group",
        "tw_label_saved": "Saved",
        "tw_label_done": "All set",
        "tw_label_notice": "Notice",
        "tw_stay_n": "Stay %(n)s of %(total)s",
        "tw_property": "Property",
        "tw_registered": "Registered",
        "tw_guest": "Guest",
        "tw_fewer": "One person fewer",
        "tw_more": "One person more",
        "tw_document_title": "Travel document",
        "tw_email_short": "We send your private link here. No marketing.",
        "tw_email_more": "What we use your e-mail for",
        "tw_step_details": "Details",
        "tw_step_document": "Document",
        "tw_step_home": "Home",
        "tw_step_photo": "Photo",
        "tw_step_sign": "Sign",
        "tw_step_check": "Check",
        "tw_dob_day": "Day",
        "tw_dob_month": "Month",
        "tw_dob_year": "Year",
        "tw_country_search": "Start typing a country",
        "tw_country_none": "No country matches",
        "tw_country_required": "Please choose a country.",
        "tw_purpose_other": "Other…",
        "tw_sign_here": "Sign here with your finger",
        "tw_signed": "Signed",
        "tw_guest_n_of": "Guest %(current)s of %(total)s",
        "tw_guest_n": "Guest %(current)s",
        "tw_next_guest": "Register guest %(current)s of %(total)s",
        "stay_ongoing": "Ongoing",
        "stay_arriving_today": "Arriving today",
        "host_details": "Your host",
        "host_details_help": "Questions? Contact your host.",
        "host_details_missing": (
            "Use the phone or e-mail in the message that contained this link."
        ),
        "message_from_host": "A message from your host",
        "claim_title": "How many people, and your e-mail",
        "claim_help": "Only your group can open the forms.",
        "claim_email": "What is your e-mail address?",
        "claim_email_help": "Also one reminder the day before arrival if forms are missing, and a receipt (your host gets a copy). Shown masked elsewhere.",
        "claim_cookie_help": (
            "Only necessary cookies: PIN access (7 days), your language and this stay "
            "(60 days)."
        ),
        "claim_submit": "Send me the form link",
        "claim_sent_title": "Check your e-mail",
        "claim_sent_body": (
            "We sent a link to %(email)s. Open it on this phone to continue. It works for 30 minutes. If it asks for the PIN again, enter the same PIN."
        ),
        "claim_sent_retry": (
            "No e-mail after a few minutes? Check spam, or send it again"
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
        "assigned_body": "This stay is already linked to the e-mail below. If that's you, enter it and we'll send the private link again.",
        "assigned_resend": "Send me the link again",
        "assigned_stay_label": "Your selected stay",
        "assigned_last_sent": "Private link last sent %(date)s",
        "assigned_not_mine": "This is not my reservation",
        "claim_confirm_title": "Is this your reservation?",
        "claim_confirm_button": "Yes, this is my stay",
        "claim_confirm_failed": "That confirmation link is invalid or has expired.",
        "back_to_stays": "Choose different dates",
        "wrong_dates": "Not your dates?",
        "your_stay_badge": "A form was submitted from this device",
        "stay_not_started": "Not started yet",
        "error_no_stay": "Please select your stay dates.",
        "error_party_size": "Please enter how many people are staying (1–60).",
        "no_stays": "There's nothing to register yet",
        "no_stays_help": (
            "Registration opens a few days before arrival. Come back to this same link then. Already arrived? Message your host. They can send you a direct link to your stay."
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
            "Nothing was saved. Start again from the link below."
        ),
        "rate_limited_title": "Too many attempts from your connection",
        "rate_limited_help": (
            "Nothing was saved. Wait about 15 minutes and try again. If you are stuck, message your host."
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
        "form_locked_short": "Saved and locked. To change anything, contact your host.",
        "pin_title": "Enter the access PIN",
        "pin_help": "The PIN is in your host's message.",
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
        "night_one": "%(n)s night",
        "nights_few": "%(n)s nights",
        "nights_many": "%(n)s nights",
        "arrive": "Arrival",
        "depart": "Departure",
        "select": "This is my stay",
        "party_question": "How many people are staying?",
        "party_help": "Count everyone, including children. Each person needs their own form.",
        "party_confirm": "Continue",
        "people_progress": "Registered: %(done)s of %(total)s",
        "person_progress": "Person %(current)s of %(total)s",
        "stay_label": "Your stay",
        "steps_label": "Check-in progress",
        "step_done": "Done",
        "form_step_progress": "Step %(current)s of %(total)s",
        "form_step_progress_title": "%(progress)s · %(title)s",
        "next_step": "Continue",
        "previous_step": "Back",
        "add_person": "Add a person",
        "add_first_person": "Start with your own details",
        "saved_title": "Saved, thank you",
        "saved_body": (
            "Your details are saved. Next, add the next person in your group."
        ),
        "reported_title": "Details submitted and reported",
        "reported_body": (
            "Thank you. Your host has already reported this record. Contact your host if "
            "anything below needs correcting."
        ),
        "summary_title": "Your submission",
        "summary_fold_saved": "saved ✓",
        "your_details": "Your details",
        "person": "Person",
        "you": "you",
        "completed": "completed",
        "not_filled": "not filled in",
        "edit": "Edit",
        "all_done_title": "Thank you. Everyone is registered",
        "all_done_body": (
            "There is nothing more you need to do. You can close this page."
        ),
        "all_done_receipt": "We have sent a confirmation to %(email)s.",
        "checkin_info": "Check-in",
        "checkout_info": "Check-out",
        "still_missing": "Still to register: %(n)s",
        "add_another": "Add another person",
        "someone_missing": "Forgot someone? Children must be registered too.",
        "continue_filling": "Continue filling in",
        "surname": "Surname",
        "first_name": "Given name(s)",
        "birth_date": "Date of birth",
        "birth_date_readback": "That is %(date)s.",
        "residence_help": "Your permanent home address, as in your passport or ID card.",
        "residence_copied": "Copied from %(name)s. Change it if this person lives elsewhere.",
        "nationality": "Nationality",
        "countries_common": "Most common",
        "countries_all": "All countries",
        "doc_number": "Travel document number",
        "doc_number_help": "Passport number, or ID card number for EU citizens only.",
        "invoice_mail_issued_subject": "Invoice %(number)s",
        "invoice_mail_issued_subject_stay": "Invoice %(number)s – %(stay_property)s",
        "invoice_mail_issued_intro": "Your invoice from %(property)s is ready to download.",
        "invoice_mail_issued_button": "Download invoice",
        "mail_invoice_title": "Invoice",
        "mail_invoice_number": "Number",
        "mail_invoice_total": "Total",
        "mail_invoice_property": "Accommodation",
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
        "signature_kept": "Your signature is saved. Sign again only if you want to change it.",
        "passport_photo_title": "Passport or ID document",
        "passport_photo_help": "Take a photo of the page with your photo, or upload a PDF. Only your host can see it, and it is deleted after they check it.",
        "passport_photo_label": "Passport or ID document",
        "passport_photo_take": "Take photo",
        "passport_photo_choose": "Choose file",
        "passport_photo_retake": "Retake or choose another",
        "passport_photo_selected": "Selected: %(name)s",
        "passport_photo_pending_nat": (
            "Choose your nationality in step 1 first."
        ),
        "passport_photo_not_required": (
            "Czech citizens do not upload a passport photo in this form."
        ),
        "passport_photo_hint": (
            "A JPEG, PNG or WebP photo up to 5 MB, or a PDF up to 15 MB."
        ),
        "passport_photo_too_large_image": "The photo is too large. Use a file under 5 MB.",
        "passport_photo_too_large_pdf": "The PDF is too large. Use a file under 15 MB.",
        "passport_photo_bad_type": (
            "Use a JPEG, PNG, or WebP photo, or a PDF registration form."
        ),
        "passport_photo_missing": "Please upload a photo of your passport or ID card.",
        "review_title": "Check before you send",
        "review_help": (
            "After you send, these details are locked and only your host can change them."
        ),
        "review_edit": "Change",
        "legal_notice_title": "Legal information",
        "legal_notice_duty_title": "Your legal duty",
        "legal_notice_duty_body": "Everyone staying must be registered. Foreign guests are reported to the Foreign Police; Czech citizens only go into the house book.",
        "legal_notice_accuracy_title": "Accurate information only",
        "legal_notice_accuracy_body": (
            "Enter everything exactly as in your passport or ID card. Your details may be "
            "reported automatically, before your host checks them, and false details can mean "
            "a fine for your host."
        ),
        "legal_notice_passport_title": "Passport photo (foreign nationals)",
        "legal_notice_passport_body": (
            "Foreign guests upload a photo of their passport or ID page (or a PDF). Only your host "
            "sees it, to compare it with what you entered. It is deleted after the check, "
            "otherwise 7 days after check-in, and never later than 30 days after upload. It is "
            "never sent to the police."
        ),
        "legal_notice_reporting_title": "Police reporting and house book",
        "legal_notice_reporting_body": "Your host reports the details of foreign guests to the Foreign Police within three working days of arrival, straight away or a little later. Complete records may be sent automatically. The same details stay in the house book for six years.",
        "legal_notice_retention_title": "How long data is kept",
        "legal_notice_retention_body": (
            "Registration details and your signature are kept for six years after the end of "
            "your stay, as required by § 101(4) of Act No. 326/1999 Coll., and then deleted. "
            "Processing is based on legal obligation (GDPR Article 6(1)(c)), not consent."
        ),
        "legal_notice_refusal_title": "If you refuse",
        "legal_notice_refusal_body": (
            "You must present a valid travel document for verification. If you refuse to "
            "provide accurate details, sign, or allow identity verification, the host may "
            "lawfully refuse accommodation."
        ),
        "legal_ack_label": (
            "My details are correct, and I have read the information above and the privacy "
            "notice."
        ),
        "legal_ack_missing": "Please confirm that you have read the legal information.",
        "submit": "Submit my details",
        "optional": "optional",
        "required": "required",
        "check_in": "Check-in",
        "check_out": "Check-out",
        "privacy": "Used only for your host's legal reporting to the Czech Police, and kept for six years.",
        "skip_to_form": "Skip to the form",
        "loading": "Loading…",
        "privacy_link": "How your data is handled",
        # WP27: privacy first, shown in the guest footer.
        "privacy_first_line": (
            "UbyHost collects only what Czech law and your registration need, and does "
            "not use tracking cookies."
        ),
        "privacy_title": "Privacy notice",
        "privacy_intro": (
            "What happens to the details you enter, as required by Articles 13 and 14 of the "
            "GDPR."
        ),
        "notice_version": "Privacy notice version %(version)s",
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
            "Article 6(1)(c) GDPR: compliance with a legal obligation, namely §§ 101–103 of Act No. 326/1999 Coll., on the Residence of Foreign Nationals. Your consent is not asked for, because the duty applies whether or not you agree to it."
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
        "privacy.cookies.table_intro": "The table below lists every cookie and item of local storage the service sets.",
        "cookies.table.name": "Name",
        "cookies.table.party": "Set by",
        "cookies.table.purpose": "Purpose",
        "cookies.table.lifetime": "Lifetime",
        "cookies.party.first": "UbyHost",
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
            "users. It is deleted after verification; if it remains unverified, it is deleted 7 "
            "days after check-in, and never later than 30 days after upload. Restricted operator or infrastructure access may be required "
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
            "to block automated abuse. Production pages may also be protected by Cloudflare against "
            "automated abuse. Those checks may process technical connection data (such as IP address) "
            "under Cloudflare's privacy notice. They are not used for marketing."
        ),
        "privacy_processor": "Who runs this website",
        "privacy_processor_body": (
            "The UbyHost software is operated by %(name)s, IČO %(ico)s, %(address)s, "
            "who processes data only on the configured controller's instructions to "
            "run the registration form, transactional messages, and stored records. "
            "Questions about your stay go to your host, while personal-data "
            "rights requests go to the controller named above."
        ),
        "privacy_retention": "How long it is kept",
        "privacy_retention_body": (
            "House-book registration details and signatures are kept for six years after the end "
            "of the stay, as § 101 requires, and then deleted. The claim e-mail remains linked while the reservation record "
            "is retained unless the host releases the claim. Completed or failed message-delivery "
            "records are normally deleted after 14 days; limited backup "
            "copies may persist until their retention cycle expires."
        ),
        "privacy_retention_body_no_email": (
            "House-book registration details and signatures are kept for six years after the end "
            "of the stay, as § 101 requires, and then deleted. Limited backup copies may persist until their retention cycle expires."
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
        "mail_claim_subject": "Confirm your stay at %(property)s (link valid 30 min)",
        "mail_claim_resend_subject": "New link: confirm your stay at %(property)s",
        "mail_claim_preheader": (
            "Tap the button, then fill in each guest (about 2 minutes per person)."
        ),
        "mail_claim_resend_preheader": (
            "Your previous link has stopped working. Here is a new one."
        ),
        "mail_claim_heading": "Confirm your stay",
        "mail_claim_resend_heading": "Here is your new link",
        "mail_claim_intro": (
            "Confirm your stay at %(property)s (%(dates)s) by opening the link below."
        ),
        "mail_claim_action": "Confirm my stay",
        "mail_link_fallback": (
            "If the button does not work, copy this address into your browser:"
        ),
        "mail_claim_expiry": (
            "The button works for 30 minutes. After you confirm, this phone or computer remembers your stay. You won't need the link again on it."
        ),
        "mail_claim_expiry_resend": (
            "This new link replaces the previous one and works for 30 minutes."
        ),
        "mail_claim_next_label": "What happens next",
        "mail_claim_next_body": (
            "You will enter the details of every guest of this stay and then sign. "
            "It takes about two minutes per guest and works on a phone. If you're "
            "asked for a PIN, use the one from your host's message."
        ),
        "mail_claim_next_done": (
            "Everyone is already registered. The link just opens your stay page."
        ),
        "mail_completion_subject": (
            "You're registered for %(property)s: nothing else to do"
        ),
        "mail_completion_preheader": (
            "Everyone on this stay is registered. Nothing else to do."
        ),
        "mail_completion_heading": "You're all set",
        "mail_completion_intro": (
            "Everyone for %(property)s (%(dates)s) is registered. "
            "There is nothing else you need to do."
        ),
        "mail_completion_action": "See your stay page",
        "mail_completion_note": (
            "Your host takes care of the official registration with the authorities. "
            "This e-mail is your receipt, not an official confirmation."
        ),
        "mail_reminder_guest_subject": (
            "Tomorrow at %(property)s: %(filled)s of %(expected)s guests registered"
        ),
        # Used when the stay has no declared party size yet, so there is no
        # count to quote.
        "mail_reminder_guest_subject_no_count": (
            "Tomorrow at %(property)s: the guest registration is not finished"
        ),
        "mail_reminder_guest_preheader": (
            "Your stay starts tomorrow and the registration is not complete."
        ),
        "mail_reminder_guest_heading": "Your stay starts tomorrow",
        "mail_reminder_guest_intro": (
            "%(missing)s more guest(s) still need to fill in the form before you "
            "arrive."
        ),
        "mail_reminder_guest_intro_no_count": (
            "Your stay at %(property)s starts tomorrow and the guest registration is "
            "not complete yet."
        ),
        "mail_reminder_guest_action": "Finish the registration",
        "mail_reminder_guest_note_label": "One reminder only",
        "mail_reminder_guest_note": (
            "This is the only incomplete-registration reminder we will send."
        ),
        # The stay page only opens without friction on the device that claimed
        # the stay; say so here instead of letting the guest meet the PIN.
        "mail_reminder_guest_device": (
            "Open it on the phone or computer where you started. On another device "
            "you'll be asked for your host's PIN."
        ),
        # The footer. Guests are told to reach the host, never UbyHost support:
        # the same rule the guest pages follow.
        # The first line said "UbyHost" and nothing else: a guest has never
        # heard of the brand, so it said nothing (audit E-17 [UX-131]).
        "mail_guest_footer_about": (
            "UbyHost is the guest-registration service your host uses."
        ),
        "mail_guest_footer_why": (
            "You received this e-mail because your stay at %(property)s is registered "
            "with this address."
        ),
        # Stand-in for a property that has no name of its own. It takes the
        # place of a property name, so it must never read as the host.
        "mail_property_fallback": "your accommodation",
        "mail_guest_footer_host_label": "Your host",
        "mail_guest_footer_help": "Reply to this e-mail to reach your host.",
        "server_error_title": "Something went wrong on our side",
        "server_error_help": "Your details that were already saved are safe. Wait a moment, then reload the page or open your link again.",
        "door_code_title": "Your door code",
        "door_code_times": "Check-in from %(checkin)s. Check-out by %(checkout)s.",
        "door_code_first_use": "The code works from check-in to check-out. If you have not used it by %(deadline)s, it stops working. Then ask your host for a new code.",
        "door_code_sent": "We have also sent it to %(email)s.",
        "door_code_preparing": "You will receive your door code by e-mail.",
        "door_code_failed": "Your host will send you the door code.",
        "mail_door_code_subject": "Your door code for %(property)s",
        "privacy_door_code_title": "Door code",
        "privacy_door_code_body": "This property gives you a door code once every guest is registered, so you can enter during your stay. The code is created through TTLock, a service of Hangzhou Sciener Intelligent Control Technology Co., Ltd. (China), which receives the lock, the code, its validity times and a reference number, but not your name or contact details. The code is shown on your stay page and sent to the e-mail address you registered with, with a copy to the host. It is stored encrypted and deleted one day after it expires. The legal basis is your accommodation contract (Art. 6(1)(b) GDPR). The lock records when the code is used, and the host sees that in their TTLock app.",
    },
    "cs": {
        "title": "Registrace ubytovaného",
        "language_label": "Jazyk",
        "date_placeholder": "DD.MM.RRRR",
        "legal_intro": "Podle zákona musí ubytovatel zaregistrovat každého hosta včetně dětí a cizince ohlásit policii.",
        "why_title": "Proč tento formulář vyplňujete",
        "why_law": "Zákon č. 326/1999 Sb., o pobytu cizinců na území ČR, § 101–103.",
        "why_point_accuracy": (
            "Musíte uvést pravdivé údaje shodné s cestovním dokladem. Hostitel za správnost "
            "odpovídá a může odmítnout ubytování, pokud doklad neukážete nebo údaje nebudou "
            "správné."
        ),
        "pick_stay": "Najděte svou rezervaci",
        "pick_stay_help": "Klepněte na termín svého pobytu a pokračujte.",
        "arrival_question": "Který pobyt je váš?",
        "arrival_cta": "To je můj pobyt",
        # Ticket Wallet skin (guest-ticket.css)
        "tw_label_access": "Soukromý přístup",
        "tw_label_stay": "Váš pobyt",
        "tw_label_email": "Vaše skupina a e-mail",
        "tw_label_confirm": "Potvrzení pobytu",
        "tw_label_group": "Vaše skupina",
        "tw_label_saved": "Uloženo",
        "tw_label_done": "Hotovo",
        "tw_label_notice": "Upozornění",
        "tw_stay_n": "Pobyt %(n)s z %(total)s",
        "tw_property": "Ubytování",
        "tw_registered": "Zaregistrováno",
        "tw_guest": "Host",
        "tw_fewer": "O jednu osobu méně",
        "tw_more": "O jednu osobu více",
        "tw_document_title": "Cestovní doklad",
        "tw_email_short": "Pošleme sem váš soukromý odkaz. Žádný marketing.",
        "tw_email_more": "K čemu váš e-mail použijeme",
        "tw_step_details": "Údaje",
        "tw_step_document": "Doklad",
        "tw_step_home": "Bydliště",
        "tw_step_photo": "Foto",
        "tw_step_sign": "Podpis",
        "tw_step_check": "Kontrola",
        "tw_dob_day": "Den",
        "tw_dob_month": "Měsíc",
        "tw_dob_year": "Rok",
        "tw_country_search": "Začněte psát zemi",
        "tw_country_none": "Žádná země neodpovídá",
        "tw_country_required": "Vyberte prosím zemi.",
        "tw_purpose_other": "Jiný…",
        "tw_sign_here": "Podepište se zde prstem",
        "tw_signed": "Podepsáno",
        "tw_guest_n_of": "Host %(current)s z %(total)s",
        "tw_guest_n": "Host %(current)s",
        "tw_next_guest": "Registrovat hosta %(current)s z %(total)s",
        "stay_ongoing": "Právě probíhá",
        "stay_arriving_today": "Příjezd dnes",
        "host_details": "Váš hostitel",
        "host_details_help": "Máte dotaz? Kontaktujte hostitele.",
        "host_details_missing": (
            "Použijte telefon nebo e-mail ze zprávy, ve které byl tento odkaz."
        ),
        "message_from_host": "Zpráva od vašeho hostitele",
        "claim_title": "Počet osob a váš e-mail",
        "claim_help": "Formuláře otevře jen vaše skupina.",
        "claim_email": "Jaký je váš e-mail?",
        "claim_email_help": "Dále jedno připomenutí den před příjezdem, pokud formuláře chybí, a potvrzení (kopii dostane i hostitel). Jinde se adresa zobrazuje zakrytě.",
        "claim_cookie_help": (
            "Jen nezbytné cookies: přístup přes PIN (7 dní), jazyk a tento pobyt (60 dní)."
        ),
        "claim_submit": "Pošlete mi odkaz na formulář",
        "claim_sent_title": "Zkontrolujte e-mail",
        "claim_sent_body": (
            "Poslali jsme odkaz na %(email)s. Otevřete ho v tomto telefonu a pokračujte. Platí 30 minut. Pokud se znovu zeptá na PIN, zadejte stejný."
        ),
        "claim_sent_retry": (
            "E-mail ani po pár minutách nepřišel? Zkontrolujte spam, nebo ho pošlete znovu"
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
        "assigned_body": "Tento pobyt je už propojený s e-mailem níže. Pokud jste to vy, zadejte ho a soukromý odkaz pošleme znovu.",
        "assigned_resend": "Pošlete mi odkaz znovu",
        "assigned_stay_label": "Vybraný pobyt",
        "assigned_last_sent": "Soukromý odkaz naposledy odeslán %(date)s",
        "assigned_not_mine": "Toto není moje rezervace",
        "claim_confirm_title": "Je to vaše rezervace?",
        "claim_confirm_button": "Ano, to je můj pobyt",
        "claim_confirm_failed": "Potvrzovací odkaz je neplatný nebo vypršel.",
        "back_to_stays": "Vybrat jiný termín",
        "wrong_dates": "Nesedí termín?",
        "your_stay_badge": "Z tohoto zařízení byl odeslán formulář",
        "stay_not_started": "Zatím nezačato",
        "error_no_stay": "Vyberte prosím termín svého pobytu.",
        "error_party_size": "Zadejte počet osob (1–60).",
        "no_stays": "Zatím tu není co vyplnit",
        "no_stays_help": (
            "Registrace se otevírá pár dní před příjezdem. Pak se vraťte na tento odkaz. "
            "Už jste na místě? Napište hostiteli, pošle vám přímý odkaz na váš pobyt."
        ),
        "bad_link_title": "Tento odkaz není platný",
        "bad_link_help": "Odkaz může být neúplný nebo byl nahrazen. Požádejte hostitele o nový odkaz.",
        "stay_gone_title": "Tento pobyt už není otevřený k registraci",
        "stay_gone_help": (
            "Termín se mohl změnit, rezervace mohla být zrušena, nebo hostitel registraci "
            "pro tento pobyt uzavřel. Napište prosím hostiteli."
        ),
        "form_expired_title": "Tomuto formuláři vypršela platnost",
        "form_expired_help": (
            "Nic se neuložilo. Začněte znovu přes odkaz níže."
        ),
        "rate_limited_title": "Příliš mnoho pokusů z vašeho připojení",
        "rate_limited_help": (
            "Nic se neuložilo. Počkejte asi 15 minut a zkuste to znovu. Pokud se zaseknete, napište hostiteli."
        ),
        "not_yours_title": "Tento formulář nelze na tomto zařízení otevřít",
        "not_yours_help": (
            "Aby jeden host neviděl údaje z pasu druhého, lze formulář znovu otevřít pouze na "
            "zařízení, ze kterého byl vyplněn. Potřebujete-li opravu, napište hostiteli."
        ),
        "already_filed_title": "Tyto údaje již byly oznámeny",
        "already_filed_help": (
            "Kvůli správnosti zákonného záznamu nelze oznámené údaje v tomto formuláři měnit. "
            "Potřebujete-li opravu, napište hostiteli."
        ),
        "form_locked_title": "Formulář je uzamčen",
        "form_locked_help": (
            "Vaše údaje byly uloženy a podepsány. Abychom chránili vaše informace, "
            "formulář už z tohoto odkazu nelze měnit. Potřebujete-li opravu, napište hostiteli."
        ),
        "form_locked_short": "Uloženo a uzamčeno. Pro změnu kontaktujte hostitele.",
        "pin_title": "Zadejte přístupový PIN",
        "pin_help": "PIN najdete ve zprávě od hostitele.",
        "pin_label": "PIN",
        "pin_submit": "Pokračovat",
        "pin_wrong": "PIN není správný. Zkontrolujte zprávu od hostitele.",
        "pin_recovery": "Nemůžete PIN najít? Požádejte hostitele o nové zaslání registrační zprávy.",
        "pin_rate_limited": "Příliš mnoho chybných PINů. Počkejte asi 15 minut a zkuste to znovu.",
        "pin_locked_out": (
            "Příliš mnoho chybných pokusů o PIN, proto je tento odkaz na den pozastaven. "
            "Požádejte hostitele o nový PIN."
        ),
        "security_check_failed": "Dokončete bezpečnostní kontrolu a zkuste to znovu.",
        "start_over": "Začít znovu",
        "night_one": "%(n)s noc",
        "nights_few": "%(n)s noci",
        "nights_many": "%(n)s nocí",
        "arrive": "Příjezd",
        "depart": "Odjezd",
        "select": "To je moje rezervace",
        "party_question": "Kolik osob bude ubytováno?",
        "party_help": "Započítejte všechny včetně dětí. Každá osoba má vlastní formulář.",
        "party_confirm": "Pokračovat",
        "people_progress": "Zaregistrováno: %(done)s z %(total)s",
        "person_progress": "Osoba %(current)s z %(total)s",
        "stay_label": "Váš pobyt",
        "steps_label": "Průběh registrace",
        "step_done": "Hotovo",
        "form_step_progress": "Krok %(current)s z %(total)s",
        "form_step_progress_title": "%(progress)s · %(title)s",
        "next_step": "Pokračovat",
        "previous_step": "Zpět",
        "add_person": "Přidat osobu",
        "add_first_person": "Začněte svými údaji",
        "saved_title": "Uloženo, děkujeme",
        "saved_body": (
            "Vaše údaje jsou uložené. Teď přidejte další osobu ze skupiny."
        ),
        "reported_title": "Údaje byly odeslány a oznámeny",
        "reported_body": (
            "Děkujeme. Hostitel již tento záznam oznámil. Pokud je třeba něco opravit, "
            "kontaktujte hostitele."
        ),
        "summary_title": "Vaše údaje",
        "summary_fold_saved": "uloženo ✓",
        "your_details": "Vaše údaje",
        "person": "Osoba",
        "you": "vy",
        "completed": "vyplněno",
        "not_filled": "nevyplněno",
        "edit": "Upravit",
        "all_done_title": "Děkujeme. Všichni jsou zaregistrovaní",
        "all_done_body": "Nic dalšího už dělat nemusíte. Stránku můžete zavřít.",
        "all_done_receipt": "Potvrzení jsme poslali na %(email)s.",
        "checkin_info": "Příjezd",
        "checkout_info": "Odjezd",
        "still_missing": "Zbývá zaregistrovat: %(n)s",
        "add_another": "Přidat další osobu",
        "someone_missing": "Zapomněli jste na někoho? Registrují se i děti.",
        "continue_filling": "Pokračovat ve vyplnění",
        "surname": "Příjmení",
        "first_name": "Jméno",
        "birth_date": "Datum narození",
        "birth_date_readback": "Tedy %(date)s.",
        "residence_help": "Adresa trvalého bydliště podle pasu nebo občanského průkazu.",
        "residence_copied": "Převzato od: %(name)s. Pokud tato osoba bydlí jinde, adresu změňte.",
        "nationality": "Státní občanství",
        "countries_common": "Nejčastější",
        "countries_all": "Všechny státy",
        "doc_number": "Číslo cestovního dokladu",
        "doc_number_help": "Číslo pasu, nebo číslo občanského průkazu pouze pro občany EU.",
        "invoice_mail_issued_subject": "Faktura %(number)s",
        "invoice_mail_issued_subject_stay": "Faktura %(number)s – %(stay_property)s",
        "invoice_mail_issued_intro": "Vaše faktura za %(property)s je připravena ke stažení.",
        "invoice_mail_issued_button": "Stáhnout fakturu",
        "mail_invoice_title": "Faktura",
        "mail_invoice_number": "Číslo",
        "mail_invoice_total": "Celkem",
        "mail_invoice_property": "Ubytování",
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
        "signature_kept": "Podpis máme uložený. Znovu se podepište, jen pokud ho chcete změnit.",
        "passport_photo_title": "Pas nebo průkaz totožnosti",
        "passport_photo_help": "Vyfoťte stránku s fotografií, nebo nahrajte PDF. Uvidí ji jen hostitel a po kontrole se smaže.",
        "passport_photo_label": "Pas nebo průkaz totožnosti",
        "passport_photo_take": "Vyfotit",
        "passport_photo_choose": "Vybrat soubor",
        "passport_photo_retake": "Vyfotit nebo vybrat jiný",
        "passport_photo_selected": "Vybráno: %(name)s",
        "passport_photo_pending_nat": (
            "Nejdřív v kroku 1 vyberte státní občanství."
        ),
        "passport_photo_not_required": (
            "Občané ČR v tomto formuláři fotografii pasu nenahrávají."
        ),
        "passport_photo_hint": (
            "Fotka JPEG, PNG nebo WebP do 5 MB, nebo PDF do 15 MB."
        ),
        "passport_photo_too_large_image": "Fotografie je příliš velká. Maximálně 5 MB.",
        "passport_photo_too_large_pdf": "PDF je příliš velké. Maximálně 15 MB.",
        "passport_photo_bad_type": (
            "Použijte fotografii JPEG, PNG nebo WebP, nebo PDF registrační formulář."
        ),
        "passport_photo_missing": "Nahrajte prosím fotografii pasu nebo občanského průkazu.",
        "review_title": "Před odesláním zkontrolujte",
        "review_help": (
            "Po odeslání se údaje uzamknou a změnit je může už jen hostitel."
        ),
        "review_edit": "Změnit",
        "legal_notice_title": "Právní informace",
        "legal_notice_duty_title": "Vaše zákonná povinnost",
        "legal_notice_duty_body": "Registrovat se musí každý ubytovaný. Cizince ubytovatel ohlásí cizinecké policii, občany ČR jen zapíše do domovní knihy.",
        "legal_notice_accuracy_title": "Pouze pravdivé údaje",
        "legal_notice_accuracy_body": (
            "Vše vyplňte přesně podle pasu nebo občanského průkazu. Údaje se mohou ohlásit "
            "automaticky ještě předtím, než je ubytovatel zkontroluje, a za nepravdivé údaje "
            "hrozí ubytovateli pokuta."
        ),
        "legal_notice_passport_title": "Fotografie pasu (cizinci)",
        "legal_notice_passport_body": (
            "Cizinci nahrají fotku stránky pasu nebo průkazu (nebo PDF). Uvidí ji jen ubytovatel, "
            "aby ji porovnal s vyplněnými údaji. Po kontrole se smaže, jinak do 7 dnů od "
            "příjezdu, nejpozději 30 dní od nahrání. Policii se nikdy neposílá."
        ),
        "legal_notice_reporting_title": "Hlášení policii a domovní kniha",
        "legal_notice_reporting_body": "Ubytovatel údaje cizinců ohlásí cizinecké policii do tří pracovních dnů od příjezdu, hned, nebo o něco později. Kompletní záznamy se mohou odeslat automaticky. Stejné údaje zůstávají šest let v domovní knize.",
        "legal_notice_retention_title": "Jak dlouho se údaje uchovávají",
        "legal_notice_retention_body": (
            "Registrační údaje a podpis se uchovávají šest let od konce pobytu podle § 101 "
            "odst. 4 zákona č. 326/1999 Sb. a poté se smažou. Zpracování je na základě právní povinnosti "
            "(GDPR čl. 6 odst. 1 písm. c), nikoli souhlasu."
        ),
        "legal_notice_refusal_title": "Pokud odmítnete",
        "legal_notice_refusal_body": (
            "Musíte předložit platný cestovní doklad k ověření. Pokud odmítnete poskytnout "
            "správné údaje, podepsat se nebo umožnit ověření totožnosti, může vás ubytovatel "
            "po právu odmítnout."
        ),
        "legal_ack_label": (
            "Moje údaje jsou správné a přečetl(a) jsem si informace výše i zásady zpracování "
            "údajů."
        ),
        "legal_ack_missing": "Potvrďte prosím, že jste si přečetli právní informace.",
        "submit": "Odeslat údaje",
        "optional": "nepovinné",
        "required": "povinné",
        "check_in": "Příjezd",
        "check_out": "Odjezd",
        "privacy": "Údaje slouží jen k zákonnému hlášení ubytovatele Policii ČR a uchovávají se 6 let.",
        "skip_to_form": "Přejít na formulář",
        "loading": "Načítá se…",
        "privacy_link": "Jak nakládáme s vašimi údaji",
        "privacy_first_line": (
            "UbyHost shromažďuje jen to, co vyžaduje český zákon a vaše registrace, "
            "a nepoužívá sledovací cookies."
        ),
        "privacy_title": "Informace o zpracování osobních údajů",
        "privacy_intro": (
            "Co se děje s údaji, které vyplníte (podle článků 13 a 14 GDPR)."
        ),
        "notice_version": "Verze oznámení o ochraně osobních údajů %(version)s",
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
            "Čl. 6 odst. 1 písm. c) GDPR: splnění právní povinnosti, konkrétně § 101–103 zákona č. 326/1999 Sb., o pobytu cizinců. Souhlas se nevyžaduje, protože povinnost platí bez ohledu na něj."
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
        "privacy.cookies.table_intro": "Tabulka níže uvádí všechny soubory cookie a položky místního úložiště, které služba nastavuje.",
        "cookies.table.name": "Název",
        "cookies.table.party": "Nastavuje",
        "cookies.table.purpose": "Účel",
        "cookies.table.lifetime": "Doba platnosti",
        "cookies.party.first": "UbyHost",
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
            "se smaže; zůstane-li neověřený, smaže se do 7 dnů od příjezdu, nejpozději 30 dní od "
            "nahrání. Omezený přístup "
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
            "automatizovanému zneužití. Produkční stránky může Cloudflare rovněž chránit proti "
            "automatizovanému zneužití. Kontroly mohou zpracovat technické údaje o připojení (např. IP) "
            "podle zásad Cloudflare. Nepoužívají se pro marketing."
        ),
        "privacy_processor": "Kdo provozuje tento web",
        "privacy_processor_body": (
            "Software UbyHost provozuje %(name)s, IČO %(ico)s, %(address)s. Údaje zpracovává pouze "
            "na pokyn nastaveného správce údajů kvůli chodu registračního "
            "formuláře, transakčním zprávám a uložení záznamů. "
            "Dotazy k pobytu směřujte na hostitele a žádosti o práva k osobním "
            "údajům na správce uvedeného výše."
        ),
        "privacy_retention": "Jak dlouho se uchovávají",
        "privacy_retention_body": (
            "Registrační údaje domovní knihy a podpisy se uchovávají šest let od konce pobytu "
            "podle § 101 a poté se smažou. E-mail k převzetí zůstává spojen s rezervací po dobu jejího uchování, "
            "pokud ubytovatel převzetí neuvolní. Dokončené či neúspěšné záznamy doručení "
            "se běžně mažou po 14 dnech; omezené zálohy mohou zůstat do konce cyklu."
        ),
        "privacy_retention_body_no_email": (
            "Registrační údaje domovní knihy a podpisy se uchovávají šest let od konce pobytu "
            "podle § 101 a poté se smažou. Omezené zálohy mohou zůstat do konce svého retenčního cyklu."
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
        "mail_claim_subject": (
            "Potvrďte svůj pobyt – %(property)s (odkaz platí 30 minut)"
        ),
        "mail_claim_resend_subject": "Nový odkaz: potvrďte svůj pobyt – %(property)s",
        "mail_claim_preheader": (
            "Klepněte na tlačítko a vyplňte údaje hostů – asi 2 minuty na osobu."
        ),
        "mail_claim_resend_preheader": (
            "Předchozí odkaz už nefunguje. Tady je nový."
        ),
        "mail_claim_heading": "Potvrďte svůj pobyt",
        "mail_claim_resend_heading": "Tady je váš nový odkaz",
        "mail_claim_intro": (
            "Potvrďte svůj pobyt: %(property)s, %(dates)s. Stačí otevřít odkaz níže."
        ),
        "mail_claim_action": "Potvrdit můj pobyt",
        "mail_link_fallback": (
            "Pokud tlačítko nefunguje, zkopírujte tuto adresu do prohlížeče:"
        ),
        "mail_claim_expiry": (
            "Tlačítko funguje 30 minut. Po potvrzení si váš pobyt zapamatuje tento "
            "telefon nebo počítač – odkaz už na něm znovu potřebovat nebudete."
        ),
        "mail_claim_expiry_resend": (
            "Tento nový odkaz nahrazuje předchozí a funguje 30 minut."
        ),
        "mail_claim_next_label": "Co bude následovat",
        "mail_claim_next_body": (
            "Vyplníte údaje ke každému hostovi tohoto pobytu a poté je podepíšete. "
            "Zabere to přibližně dvě minuty na hosta a funguje to i na telefonu. "
            "Pokud se stránka zeptá na PIN, použijte ten ze zprávy od hostitele."
        ),
        "mail_claim_next_done": (
            "Všichni už jsou zaregistrovaní – odkaz jen otevře stránku vašeho pobytu."
        ),
        "mail_completion_subject": (
            "Registrace hotová – %(property)s. Nic dalšího nemusíte dělat"
        ),
        "mail_completion_preheader": (
            "Všichni na tomto pobytu jsou zaregistrovaní – nic dalšího není potřeba."
        ),
        "mail_completion_heading": "Hotovo",
        "mail_completion_intro": (
            "Všichni hosté pro %(property)s (%(dates)s) jsou zaregistrovaní. "
            "Nic dalšího dělat nemusíte."
        ),
        "mail_completion_action": "Zobrazit stránku pobytu",
        "mail_completion_note": (
            "Úřední hlášení vyřizuje váš hostitel. Tento e-mail je potvrzení pro vás, "
            "nikoli úřední doklad."
        ),
        "mail_reminder_guest_subject": (
            "Zítra přijíždíte (%(property)s): zaregistrováno %(filled)s z %(expected)s "
            "hostů"
        ),
        "mail_reminder_guest_subject_no_count": (
            "Zítra přijíždíte (%(property)s): registrace hostů není dokončená"
        ),
        "mail_reminder_guest_preheader": (
            "Pobyt začíná zítra a registrace není dokončená."
        ),
        "mail_reminder_guest_heading": "Váš pobyt začíná zítra",
        "mail_reminder_guest_intro": (
            "Před příjezdem ještě musí formulář vyplnit další hosté: %(missing)s."
        ),
        "mail_reminder_guest_intro_no_count": (
            "Váš pobyt začíná zítra – %(property)s. Registrace hostů zatím není "
            "dokončená."
        ),
        "mail_reminder_guest_action": "Dokončit registraci",
        "mail_reminder_guest_note_label": "Pouze jedno upozornění",
        "mail_reminder_guest_note": (
            "Toto je jediné upozornění na nedokončenou registraci, které vám pošleme."
        ),
        "mail_reminder_guest_device": (
            "Otevřete ho na telefonu nebo počítači, kde jste začali. Na jiném "
            "zařízení budete potřebovat PIN od hostitele."
        ),
        # Patička. Hosté se obracejí na ubytovatele, nikdy na podporu UbyHostu:
        # stejné pravidlo jako na stránkách pro hosty.
        "mail_guest_footer_about": (
            "UbyHost je služba pro registraci hostů, kterou váš hostitel používá."
        ),
        "mail_guest_footer_why": (
            "Tento e-mail dostáváte, protože jste touto adresou potvrdili pobyt: "
            "%(property)s."
        ),
        "mail_property_fallback": "vaše ubytování",
        "mail_guest_footer_host_label": "Váš hostitel",
        "mail_guest_footer_help": "Odpovězte na tento e-mail a spojíte se s hostitelem.",
        "server_error_title": "Na naší straně se něco pokazilo",
        "server_error_help": "Údaje, které už jste uložili, jsou v bezpečí. Chvíli počkejte a pak stránku načtěte znovu nebo znovu otevřete svůj odkaz.",
        "door_code_title": "Váš kód ke dveřím",
        "door_code_times": "Příjezd od %(checkin)s. Odjezd do %(checkout)s.",
        "door_code_first_use": "Kód funguje od příjezdu do odjezdu. Pokud ho nepoužijete do %(deadline)s, přestane fungovat. Pak požádejte hostitele o nový kód.",
        "door_code_sent": "Poslali jsme ho také na %(email)s.",
        "door_code_preparing": "Kód ke dveřím vám přijde e-mailem.",
        "door_code_failed": "Kód ke dveřím vám pošle hostitel.",
        "mail_door_code_subject": "Váš kód ke dveřím pro %(property)s",
        "privacy_door_code_title": "Kód ke dveřím",
        "privacy_door_code_body": "Toto ubytování vám po registraci všech hostů pošle kód ke dveřím, abyste mohli během pobytu vstoupit. Kód vzniká přes TTLock, službu společnosti Hangzhou Sciener Intelligent Control Technology Co., Ltd. (Čína), která dostane zámek, kód, dobu jeho platnosti a referenční číslo, nikoli vaše jméno ani kontakty. Kód se zobrazí na stránce pobytu a pošle se na e-mail, kterým jste se registrovali, s kopií hostiteli. Ukládá se šifrovaně a maže se den po skončení platnosti. Právním základem je vaše smlouva o ubytování (čl. 6 odst. 1 písm. b) GDPR). Zámek zaznamenává použití kódu a hostitel to vidí ve své aplikaci TTLock.",

    },
    # WP26: German. Machine-assisted; a native speaker should review it,
    # the legal notice and privacy keys first (see notes/WP26-guest-languages.md).
    "de": {
        "title": "Gästeregistrierung",
        "language_label": "Sprache",
        "date_placeholder": "TT.MM.JJJJ",
        "legal_intro": "Nach tschechischem Recht muss Ihr Gastgeber jeden Gast registrieren, auch Kinder, und ausländische Gäste der Polizei melden.",
        "why_title": "Warum Sie dies ausfüllen",
        "why_law": "Gesetz Nr. 326/1999 Slg. über den Aufenthalt von Ausländern, §§ 101–103.",
        "why_point_accuracy": "Sie müssen wahrheitsgemäße Angaben machen, die mit Ihrem Reisedokument übereinstimmen. Der Gastgeber ist gesetzlich für die Richtigkeit verantwortlich und kann die Unterbringung verweigern, wenn Sie sich nicht ausweisen oder keine korrekten Angaben machen.",
        "pick_stay": "Ihren Aufenthalt finden",
        "pick_stay_help": "Tippen Sie auf Ihr An- und Abreisedatum, um fortzufahren.",
        "arrival_question": "Welcher Aufenthalt ist Ihrer?",
        "arrival_cta": "Das ist mein Aufenthalt",
        "tw_label_access": "Privater Zugang",
        "tw_label_stay": "Ihr Aufenthalt",
        "tw_label_email": "Gruppe und E-Mail",
        "tw_label_confirm": "Aufenthalt bestätigen",
        "tw_label_group": "Ihre Gruppe",
        "tw_label_saved": "Gespeichert",
        "tw_label_done": "Alles erledigt",
        "tw_label_notice": "Hinweis",
        "tw_stay_n": "Aufenthalt %(n)s von %(total)s",
        "tw_property": "Unterkunft",
        "tw_registered": "Registriert",
        "tw_guest": "Gast",
        "tw_fewer": "Eine Person weniger",
        "tw_more": "Eine Person mehr",
        "tw_document_title": "Reisedokument",
        "tw_email_short": "Wir senden Ihren privaten Link hierhin. Kein Marketing.",
        "tw_email_more": "Wofür wir Ihre E-Mail nutzen",
        "tw_step_details": "Angaben",
        "tw_step_document": "Dokument",
        "tw_step_home": "Wohnort",
        "tw_step_photo": "Foto",
        "tw_step_sign": "Signatur",
        "tw_step_check": "Prüfen",
        "tw_dob_day": "Tag",
        "tw_dob_month": "Monat",
        "tw_dob_year": "Jahr",
        "tw_country_search": "Land eingeben",
        "tw_country_none": "Kein passendes Land",
        "tw_country_required": "Bitte wählen Sie ein Land.",
        "tw_purpose_other": "Sonstiges…",
        "tw_sign_here": "Hier mit dem Finger unterschreiben",
        "tw_signed": "Unterschrieben",
        "tw_guest_n_of": "Gast %(current)s von %(total)s",
        "tw_guest_n": "Gast %(current)s",
        "tw_next_guest": "Gast %(current)s von %(total)s registrieren",
        "stay_ongoing": "Laufend",
        "stay_arriving_today": "Anreise heute",
        "host_details": "Ihr Gastgeber",
        "host_details_help": "Fragen? Wenden Sie sich an Ihren Gastgeber.",
        "host_details_missing": "Nutzen Sie die Telefonnummer oder E-Mail aus der Nachricht, die diesen Link enthielt.",
        "message_from_host": "Eine Nachricht Ihres Gastgebers",
        "claim_title": "Personenzahl und Ihre E-Mail",
        "claim_help": "Nur Ihre Gruppe kann die Formulare öffnen.",
        "claim_email": "Wie lautet Ihre E-Mail-Adresse?",
        "claim_email_help": "Außerdem eine Erinnerung am Tag vor der Anreise, falls Formulare fehlen, und eine Bestätigung (Ihr Gastgeber erhält eine Kopie). An anderer Stelle wird sie maskiert angezeigt.",
        "claim_cookie_help": "Nur notwendige Cookies: PIN-Zugang (7 Tage), Ihre Sprache und dieser Aufenthalt (60 Tage).",
        "claim_submit": "Formular-Link senden",
        "claim_sent_title": "Prüfen Sie Ihre E-Mails",
        "claim_sent_body": "Wir haben einen Link an %(email)s gesendet. Öffnen Sie ihn auf diesem Telefon, um fortzufahren. Er gilt 30 Minuten. Wenn erneut nach der PIN gefragt wird, geben Sie dieselbe PIN ein.",
        "claim_sent_retry": "Nach ein paar Minuten keine E-Mail? Prüfen Sie den Spam-Ordner oder senden Sie sie erneut",
        "claim_error_bad_email": "Bitte geben Sie eine gültige E-Mail-Adresse ein.",
        "claim_error_bad_party": "Bitte geben Sie an, wie viele Personen übernachten (1–60).",
        "claim_error_held": "Jemand anderes bestätigt gerade diesen Aufenthalt. Versuchen Sie es in ein paar Minuten erneut.",
        "claim_error_already_claimed": "Dieser Aufenthalt ist bereits einer anderen E-Mail-Adresse zugeordnet.",
        "claim_error_rate": "Zu viele Link-Anfragen. Bitte versuchen Sie es etwas später erneut.",
        "claim_error_cooldown": "Wir haben gerade einen Link an diese Adresse gesendet. Bitte warten Sie eine Minute, bevor Sie es erneut versuchen.",
        "claim_error_recipient_rate": "An diese E-Mail wurden zu viele Registrierungslinks gesendet. Versuchen Sie es später erneut.",
        "claim_error_bot": "Bitte schließen Sie die Sicherheitsprüfung ab und versuchen Sie es erneut.",
        "assigned_title": "Diese Reservierung ist bereits zugeordnet",
        "assigned_body": "Dieser Aufenthalt ist bereits mit der unten stehenden E-Mail verknüpft. Wenn das Sie sind, geben Sie sie ein, und wir senden den privaten Link erneut.",
        "assigned_resend": "Link erneut senden",
        "assigned_stay_label": "Ihr gewählter Aufenthalt",
        "assigned_last_sent": "Privater Link zuletzt gesendet am %(date)s",
        "assigned_not_mine": "Das ist nicht meine Reservierung",
        "claim_confirm_title": "Ist das Ihre Reservierung?",
        "claim_confirm_button": "Ja, das ist mein Aufenthalt",
        "claim_confirm_failed": "Dieser Bestätigungslink ist ungültig oder abgelaufen.",
        "back_to_stays": "Anderen Zeitraum wählen",
        "wrong_dates": "Nicht Ihr Zeitraum?",
        "your_stay_badge": "Von diesem Gerät wurde ein Formular gesendet",
        "stay_not_started": "Noch nicht begonnen",
        "error_no_stay": "Bitte wählen Sie Ihren Aufenthaltszeitraum.",
        "error_party_size": "Bitte geben Sie an, wie viele Personen übernachten (1–60).",
        "no_stays": "Noch nichts zu registrieren",
        "no_stays_help": "Die Registrierung öffnet einige Tage vor der Anreise. Kommen Sie dann über denselben Link zurück. Schon angekommen? Schreiben Sie Ihrem Gastgeber. Er kann Ihnen einen direkten Link zu Ihrem Aufenthalt senden.",
        "bad_link_title": "Dieser Gast-Link ist ungültig",
        "bad_link_help": "Er ist möglicherweise unvollständig oder wurde ersetzt. Bitte fragen Sie Ihren Gastgeber nach einem neuen Link.",
        "stay_gone_title": "Für diesen Aufenthalt ist keine Registrierung mehr möglich",
        "stay_gone_help": "Möglicherweise haben sich die Daten geändert, die Buchung wurde storniert oder Ihr Gastgeber hat die Registrierung für diesen Aufenthalt geschlossen. Bitte schreiben Sie Ihrem Gastgeber.",
        "form_expired_title": "Zeit für dieses Formular abgelaufen",
        "form_expired_help": "Es wurde nichts gespeichert. Beginnen Sie erneut über den Link unten.",
        "rate_limited_title": "Zu viele Versuche von Ihrer Verbindung",
        "rate_limited_help": "Es wurde nichts gespeichert. Warten Sie etwa 15 Minuten und versuchen Sie es erneut. Wenn es nicht weitergeht, schreiben Sie Ihrem Gastgeber.",
        "not_yours_title": "Dieses Formular kann auf diesem Gerät nicht geöffnet werden",
        "not_yours_help": "Damit kein Gast die Passdaten eines anderen Gastes sieht, kann ein Formular nur auf dem Gerät erneut geöffnet werden, auf dem es ausgefüllt wurde. Für eine Korrektur schreiben Sie Ihrem Gastgeber.",
        "already_filed_title": "Diese Angaben wurden bereits gemeldet",
        "already_filed_help": "Aus Gründen der rechtlichen Richtigkeit kann ein gemeldeter Eintrag nicht über dieses Formular geändert werden. Bitte schreiben Sie Ihrem Gastgeber, falls etwas korrigiert werden muss.",
        "form_locked_title": "Dieses Formular ist gesperrt",
        "form_locked_help": "Ihre Angaben wurden gespeichert und unterschrieben. Zum Schutz Ihrer Daten kann das Formular über diesen Link nicht geändert werden. Bitte schreiben Sie Ihrem Gastgeber, falls etwas korrigiert werden muss.",
        "form_locked_short": "Gespeichert und gesperrt. Für Änderungen wenden Sie sich an Ihren Gastgeber.",
        "pin_title": "Zugangs-PIN eingeben",
        "pin_help": "Die PIN steht in der Nachricht Ihres Gastgebers.",
        "pin_label": "PIN",
        "pin_submit": "Weiter",
        "pin_wrong": "Diese PIN ist nicht korrekt. Prüfen Sie die Nachricht Ihres Gastgebers.",
        "pin_recovery": "PIN nicht gefunden? Bitten Sie Ihren Gastgeber, die Registrierungsnachricht erneut zu senden.",
        "pin_rate_limited": "Zu viele falsche PIN-Eingaben. Warten Sie etwa 15 Minuten und versuchen Sie es erneut.",
        "pin_locked_out": "Zu viele falsche PIN-Eingaben, daher ist dieser Link für einen Tag gesperrt. Bitten Sie Ihren Gastgeber um eine neue PIN.",
        "security_check_failed": "Schließen Sie die Sicherheitsprüfung ab und versuchen Sie es erneut.",
        "start_over": "Neu beginnen",
        "night_one": "%(n)s Nacht",
        "nights_few": "%(n)s Nächte",
        "nights_many": "%(n)s Nächte",
        "arrive": "Anreise",
        "depart": "Abreise",
        "select": "Das ist mein Aufenthalt",
        "party_question": "Wie viele Personen übernachten?",
        "party_help": "Zählen Sie alle mit, auch Kinder. Jede Person braucht ein eigenes Formular.",
        "party_confirm": "Weiter",
        "people_progress": "Registriert: %(done)s von %(total)s",
        "person_progress": "Person %(current)s von %(total)s",
        "stay_label": "Ihr Aufenthalt",
        "steps_label": "Check-in-Fortschritt",
        "step_done": "Erledigt",
        "form_step_progress": "Schritt %(current)s von %(total)s",
        "form_step_progress_title": "%(progress)s · %(title)s",
        "next_step": "Weiter",
        "previous_step": "Zurück",
        "add_person": "Person hinzufügen",
        "add_first_person": "Beginnen Sie mit Ihren eigenen Angaben",
        "saved_title": "Gespeichert, vielen Dank",
        "saved_body": "Ihre Angaben sind gespeichert. Fügen Sie nun die nächste Person Ihrer Gruppe hinzu.",
        "reported_title": "Angaben gesendet und gemeldet",
        "reported_body": "Vielen Dank. Ihr Gastgeber hat diesen Eintrag bereits gemeldet. Wenden Sie sich an Ihren Gastgeber, falls unten etwas korrigiert werden muss.",
        "summary_title": "Ihre Angaben",
        "summary_fold_saved": "gespeichert ✓",
        "your_details": "Ihre Angaben",
        "person": "Person",
        "you": "Sie",
        "completed": "ausgefüllt",
        "not_filled": "nicht ausgefüllt",
        "edit": "Bearbeiten",
        "all_done_title": "Vielen Dank. Alle sind registriert",
        "all_done_body": "Sie müssen nichts weiter tun. Sie können diese Seite schließen.",
        "all_done_receipt": "Wir haben eine Bestätigung an %(email)s gesendet.",
        "checkin_info": "Check-in",
        "checkout_info": "Check-out",
        "still_missing": "Noch zu registrieren: %(n)s",
        "add_another": "Weitere Person hinzufügen",
        "someone_missing": "Jemanden vergessen? Auch Kinder müssen registriert werden.",
        "continue_filling": "Weiter ausfüllen",
        "surname": "Nachname",
        "first_name": "Vorname(n)",
        "birth_date": "Geburtsdatum",
        "birth_date_readback": "Das ist der %(date)s.",
        "residence_help": "Ihre ständige Wohnanschrift wie in Ihrem Reisepass oder Personalausweis.",
        "residence_copied": "Von %(name)s übernommen. Ändern Sie sie, falls diese Person woanders wohnt.",
        "nationality": "Staatsangehörigkeit",
        "countries_common": "Häufigste",
        "countries_all": "Alle Länder",
        "doc_number": "Nummer des Reisedokuments",
        "doc_number_help": "Reisepassnummer oder, nur für EU-Bürger, Personalausweisnummer.",
        "invoice_mail_issued_subject": "Rechnung %(number)s",
        "invoice_mail_issued_subject_stay": "Rechnung %(number)s – %(stay_property)s",
        "invoice_mail_issued_intro": "Ihre Rechnung von %(property)s steht zum Download bereit.",
        "invoice_mail_issued_button": "Rechnung herunterladen",
        "mail_invoice_title": "Rechnung",
        "mail_invoice_number": "Nummer",
        "mail_invoice_total": "Gesamt",
        "mail_invoice_property": "Unterkunft",
        "visa_number": "Visumnummer",
        "visa_help": "Nur wenn Ihnen ein tschechisches oder Schengen-Visum erteilt wurde.",
        "residence_title": "Ständige Wohnanschrift",
        "res_street": "Straße und Hausnummer",
        "res_city": "Ort",
        "res_country": "Land",
        "purpose": "Aufenthaltszweck",
        "stay_dates": "Ihre Reisedaten",
        "child_title": "Diese Person ist ein Kind, das mit dem Reisepass eines Elternteils reist",
        "child_help": "Kreuzen Sie dies nur an, wenn das Kind keinen eigenen Reisepass hat. Wir benötigen dann die Dokumentnummer des Elternteils.",
        "parent_doc": "Dokumentnummer des Elternteils",
        "note": "Anmerkung",
        "signature": "Unterschrift",
        "signature_help": "Unterschreiben Sie mit dem Finger oder der Maus. Dies ist nach tschechischem Recht vorgeschrieben.",
        "signature_clear": "Löschen",
        "signature_missing": "Bitte unterschreiben Sie im Feld, bevor Sie fortfahren.",
        "signature_kept": "Ihre Unterschrift ist gespeichert. Unterschreiben Sie nur erneut, wenn Sie sie ändern möchten.",
        "passport_photo_title": "Reisepass oder Ausweis",
        "passport_photo_help": "Fotografieren Sie die Seite mit Ihrem Foto oder laden Sie ein PDF hoch. Nur Ihr Gastgeber kann es sehen, und es wird nach der Prüfung gelöscht.",
        "passport_photo_label": "Reisepass oder Ausweis",
        "passport_photo_take": "Foto aufnehmen",
        "passport_photo_choose": "Datei wählen",
        "passport_photo_retake": "Neu aufnehmen oder andere wählen",
        "passport_photo_selected": "Ausgewählt: %(name)s",
        "passport_photo_pending_nat": "Wählen Sie zuerst in Schritt 1 Ihre Staatsangehörigkeit.",
        "passport_photo_not_required": "Tschechische Staatsbürger laden in diesem Formular kein Passfoto hoch.",
        "passport_photo_hint": "Ein JPEG-, PNG- oder WebP-Foto bis 5 MB oder ein PDF bis 15 MB.",
        "passport_photo_too_large_image": "Das Foto ist zu groß. Verwenden Sie eine Datei unter 5 MB.",
        "passport_photo_too_large_pdf": "Das PDF ist zu groß. Verwenden Sie eine Datei unter 15 MB.",
        "passport_photo_bad_type": "Verwenden Sie ein JPEG-, PNG- oder WebP-Foto oder ein PDF-Meldeformular.",
        "passport_photo_missing": "Bitte laden Sie ein Foto Ihres Reisepasses oder Personalausweises hoch.",
        "review_title": "Vor dem Senden prüfen",
        "review_help": "Nach dem Senden sind diese Angaben gesperrt und nur Ihr Gastgeber kann sie ändern.",
        "review_edit": "Ändern",
        "legal_notice_title": "Rechtliche Hinweise",
        "legal_notice_duty_title": "Ihre gesetzliche Pflicht",
        "legal_notice_duty_body": "Alle Übernachtenden müssen registriert werden. Ausländische Gäste werden der Fremdenpolizei gemeldet; tschechische Staatsbürger werden nur ins Hausbuch eingetragen.",
        "legal_notice_accuracy_title": "Nur korrekte Angaben",
        "legal_notice_accuracy_body": "Geben Sie alles genau wie in Ihrem Reisepass oder Personalausweis ein. Ihre Angaben können automatisch gemeldet werden, bevor Ihr Gastgeber sie prüft, und falsche Angaben können für Ihren Gastgeber ein Bußgeld bedeuten.",
        "legal_notice_passport_title": "Passfoto (ausländische Staatsangehörige)",
        "legal_notice_passport_body": "Ausländische Gäste laden ein Foto ihrer Reisepass- oder Ausweisseite (oder ein PDF) hoch. Nur Ihr Gastgeber sieht es, um es mit Ihren Angaben zu vergleichen. Es wird nach der Prüfung gelöscht, andernfalls 7 Tage nach dem Check-in, und niemals später als 30 Tage nach dem Hochladen. Es wird niemals an die Polizei gesendet.",
        "legal_notice_reporting_title": "Polizeimeldung und Hausbuch",
        "legal_notice_reporting_body": "Ihr Gastgeber meldet die Angaben ausländischer Gäste innerhalb von drei Arbeitstagen nach der Ankunft der Fremdenpolizei, sofort oder etwas später. Vollständige Einträge können automatisch gesendet werden. Dieselben Angaben bleiben sechs Jahre lang im Hausbuch.",
        "legal_notice_retention_title": "Wie lange Daten gespeichert werden",
        "legal_notice_retention_body": "Registrierungsangaben und Ihre Unterschrift werden sechs Jahre nach Ende Ihres Aufenthalts aufbewahrt, wie es § 101 Abs. 4 des Gesetzes Nr. 326/1999 Slg. vorschreibt, und anschließend gelöscht. Die Verarbeitung beruht auf einer rechtlichen Verpflichtung (Art. 6 Abs. 1 lit. c DSGVO), nicht auf einer Einwilligung.",
        "legal_notice_refusal_title": "Wenn Sie ablehnen",
        "legal_notice_refusal_body": "Sie müssen ein gültiges Reisedokument zur Prüfung vorlegen. Wenn Sie sich weigern, korrekte Angaben zu machen, zu unterschreiben oder eine Identitätsprüfung zuzulassen, darf der Gastgeber die Unterbringung rechtmäßig verweigern.",
        "legal_ack_label": "Meine Angaben sind korrekt, und ich habe die obigen Informationen und die Datenschutzhinweise gelesen.",
        "legal_ack_missing": "Bitte bestätigen Sie, dass Sie die rechtlichen Hinweise gelesen haben.",
        "submit": "Angaben senden",
        "optional": "optional",
        "required": "Pflichtfeld",
        "check_in": "Check-in",
        "check_out": "Check-out",
        "privacy": "Ausschließlich für die gesetzliche Meldung Ihres Gastgebers an die tschechische Polizei verwendet und sechs Jahre lang aufbewahrt.",
        "skip_to_form": "Zum Formular springen",
        "loading": "Wird geladen…",
        "privacy_link": "Umgang mit Ihren Daten",
        "privacy_first_line": "UbyHost erhebt nur, was das tschechische Recht und Ihre Anmeldung erfordern, und verwendet keine Tracking-Cookies.",
        "privacy_title": "Datenschutzhinweise",
        "privacy_intro": "Was mit Ihren Angaben geschieht, gemäß Art. 13 und 14 DSGVO.",
        "notice_version": "Datenschutzhinweise, Version %(version)s",
        "privacy_controller": "Ihr Verantwortlicher",
        "privacy_controller_body": "Diese juristische Person entscheidet, warum und wie Ihre Gastdaten verwendet werden, und ist für Ihre Rechte nach der DSGVO zuständig. Ein abweichender Name beim unten genannten Ansprechpartner für den Aufenthalt ändert an dieser Rolle nichts.",
        "privacy_controller_missing": "Ihr Gastgeber muss das für Ihre Daten verantwortliche Unternehmen angeben. Fragen Sie Ihren Gastgeber nach dessen eingetragenem Namen und Anschrift, falls diese hier fehlen.",
        "privacy_stay_contact": "Fragen zu Ihrem Aufenthalt",
        "privacy_stay_contact_body": "Der Unterkunftsverwalter ist Ihr praktischer Ansprechpartner für Fragen zu Anreise, Unterkunft und Buchung. Wenden Sie sich für Anträge auf Auskunft, Berichtigung, Löschung oder Widerspruch an den oben genannten Verantwortlichen.",
        "privacy_purpose": "Warum die Daten erhoben werden",
        "privacy_purpose_body": "Zur Erfüllung zweier gesetzlicher Pflichten eines Beherbergungsbetriebs in Tschechien: der Meldung beherbergter ausländischer Staatsangehöriger an die Fremdenpolizei und der Führung eines Hausbuchs (domovní kniha). Sie werden für keinen anderen Zweck verwendet.",
        "privacy_basis": "Rechtsgrundlage",
        "privacy_basis_body": "Art. 6 Abs. 1 lit. c DSGVO: erfüllung einer rechtlichen Verpflichtung, nämlich §§ 101–103 des Gesetzes Nr. 326/1999 Slg. über den Aufenthalt von Ausländern. Ihre Einwilligung wird nicht eingeholt, da die Pflicht unabhängig davon gilt, ob Sie zustimmen.",
        "privacy_data": "Was erhoben wird",
        "privacy_data_body": "Vor- und Nachname, Geburtsdatum, Staatsangehörigkeit, Nummer des Reisedokuments, Visumnummer (falls erteilt), ständige Wohnanschrift im Ausland, Aufenthaltszweck, Beginn und Ende Ihres Aufenthalts, Unterschrift, angegebene Personenzahl und die E-Mail-Adresse, mit der die Reservierung beansprucht wurde. Die Personenzahl dient dazu festzustellen, ob alle erwarteten Gastformulare vollständig sind, und wird mit dem Aufenthaltseintrag aufbewahrt.",
        "privacy_data_body_no_email": "Vor- und Nachname, Geburtsdatum, Staatsangehörigkeit, Nummer des Reisedokuments, Visumnummer (falls erteilt), ständige Wohnanschrift im Ausland, Aufenthaltszweck, Beginn und Ende Ihres Aufenthalts, Unterschrift und angegebene Personenzahl. Diese Version des Formulars erhebt Ihre E-Mail-Adresse nicht. Die Personenzahl dient dazu festzustellen, ob alle erwarteten Gastformulare vollständig sind, und wird mit dem Aufenthaltseintrag aufbewahrt.",
        "privacy_email_title": "E-Mails und Maskierung",
        "privacy_email_body": "Ihre E-Mail sichert die Reservierung und wird verwendet, um den privaten Formular-Link, eine Erinnerung am Vortag, falls die angegebenen Formulare unvollständig bleiben, und eine Abschlussbestätigung zu senden. Der Unterkunftsverwalter erhält eine Kopie der Abschlussbestätigung. Die vollständige Adresse ist für den eingerichteten Verantwortlichen und, sofern aktiviert, für den Zustelldienstleister zugänglich; öffentliche Gastseiten zeigen nur eine maskierte Adresse. Sie wird nicht für Marketing verwendet.",
        "privacy_cookies_title": "Notwendige Cookies",
        "privacy.cookies.table_intro": "Die folgende Tabelle listet alle Cookies und lokal gespeicherten Einträge auf, die der Dienst setzt.",
        "cookies.table.name": "Name",
        "cookies.table.party": "Gesetzt von",
        "cookies.table.purpose": "Zweck",
        "cookies.table.lifetime": "Speicherdauer",
        "cookies.party.first": "UbyHost",
        "privacy_cookies_body": "UbyHost verwendet nur notwendige Gast-Cookies: PIN-Zugang für bis zu 7 Tage sowie Sprache und auf diesem Gerät gesendete Formulare für bis zu 60 Tage. Wenn die Bestätigung per E-Mail aktiviert ist, wird auch der Zugang zur bestätigten Reservierung bis zu 60 Tage gespeichert. Sie verhindern, dass ein anderer Gast Ihr Formular sieht oder ändert, und halten den Ablauf nutzbar. Cloudflare kann Sicherheitskennungen setzen, wenn Turnstile oder der Bot-Schutz ausgelöst wird. Es gibt keine Werbe- oder Analyse-Cookies.",
        "privacy_passport_photo_title": "Vorübergehendes Passfoto oder PDF",
        "privacy_passport_photo_body": "Wenn Sie kein tschechischer Staatsbürger sind, können Sie ein Foto Ihrer Reisepass- oder Ausweisseite oder ein PDF-Meldeformular hochladen, damit der Gastgeber Ihre Angaben prüfen kann. Die Datei wird nur für diese Prüfung verarbeitet, und der Zugriff in der App ist auf berechtigte Nutzer des Gastgebers beschränkt. Sie wird nach der Prüfung gelöscht; bleibt sie ungeprüft, wird sie 7 Tage nach dem Check-in gelöscht, und niemals später als 30 Tage nach dem Hochladen. Für Betrieb und Sicherheit des Dienstes kann ein eingeschränkter Zugriff durch den Betreiber oder die Infrastruktur erforderlich sein. Sie wird nicht an die Polizei übermittelt.",
        "privacy_recipients": "Wer die Daten erhält",
        "privacy_recipients_body": "Die Polizei der Tschechischen Republik, Direktion der Fremdenpolizei, und jeder Beamte, der das Hausbuch kontrolliert; Ihr Beherbergungsbetrieb; UbyHost als dessen Auftragsverarbeiter; sowie ein E-Mail-Zustelldienstleister, sofern Nachrichten aktiviert sind. Die Daten werden niemals verkauft, an die Buchungsplattform zurückgesendet oder für Marketing verwendet.",
        "privacy_recipients_body_no_email": "Die Polizei der Tschechischen Republik, Direktion der Fremdenpolizei, jeder Beamte, der das Hausbuch kontrolliert, Ihr Beherbergungsbetrieb und UbyHost als dessen Auftragsverarbeiter. Die Daten werden niemals verkauft, an die Buchungsplattform zurückgesendet oder für Marketing verwendet.",
        "privacy_bot_protection_title": "Schutz des Registrierungslinks",
        "privacy_bot_protection_body": "Wenn jemand wiederholt eine falsche Zugangs-PIN eingibt, kann das Formular Cloudflare Turnstile anzeigen, um automatisierten Missbrauch zu verhindern. Produktivseiten können zudem durch Cloudflare vor automatisiertem Missbrauch geschützt sein. Bei diesen Prüfungen können technische Verbindungsdaten (etwa die IP-Adresse) gemäß der Datenschutzerklärung von Cloudflare verarbeitet werden. Sie werden nicht für Marketing verwendet.",
        "privacy_processor": "Wer diese Website betreibt",
        "privacy_processor_body": "Die Software UbyHost wird betrieben von %(name)s, IČO %(ico)s, %(address)s, der Daten ausschließlich auf Weisung des eingerichteten Verantwortlichen verarbeitet, um das Registrierungsformular, Transaktionsnachrichten und gespeicherte Einträge bereitzustellen. Fragen zu Ihrem Aufenthalt richten Sie an Ihren Gastgeber, Anträge zu Ihren Datenschutzrechten an den oben genannten Verantwortlichen.",
        "privacy_retention": "Wie lange sie gespeichert werden",
        "privacy_retention_body": "Hausbuch-Registrierungsangaben und Unterschriften werden sechs Jahre nach Ende des Aufenthalts aufbewahrt, wie es § 101 vorschreibt, und anschließend gelöscht. Die Bestätigungs-E-Mail bleibt verknüpft, solange der Reservierungseintrag aufbewahrt wird, sofern der Gastgeber die Zuordnung nicht aufhebt. Abgeschlossene oder fehlgeschlagene Zustellprotokolle werden in der Regel nach 14 Tagen gelöscht; begrenzte Sicherungskopien können bis zum Ablauf ihres Aufbewahrungszyklus bestehen bleiben.",
        "privacy_retention_body_no_email": "Hausbuch-Registrierungsangaben und Unterschriften werden sechs Jahre nach Ende des Aufenthalts aufbewahrt, wie es § 101 vorschreibt, und anschließend gelöscht. Begrenzte Sicherungskopien können bis zum Ablauf ihres Aufbewahrungszyklus bestehen bleiben.",
        "privacy_rights": "Ihre Rechte",
        "privacy_rights_body": "Sie können eine Kopie Ihrer Daten verlangen, unrichtige Angaben berichtigen lassen und Auskunft über die Verarbeitung verlangen. Löschung und Widerspruch sind eingeschränkt, solange die gesetzliche Aufbewahrungspflicht besteht. Es findet keine automatisierte Entscheidungsfindung und kein Profiling statt.",
        "privacy_complaint": "Wenn Sie der Meinung sind, dass Ihre Daten unrechtmäßig verarbeitet werden, können Sie sich bei der tschechischen Datenschutzbehörde beschweren: Úřad pro ochranu osobních údajů, Pplk. Sochora 27, 170 00 Praha 7, uoou.gov.cz.",
        "privacy_required": "Die Angabe dieser Daten ist gesetzlich vorgeschrieben und keine eigene Idee des Gastgebers. Ohne sie darf der Gastgeber Sie nicht rechtmäßig beherbergen.",
        "privacy_contact": "Kontakt",
        "fix_errors": "Bitte korrigieren Sie Folgendes:",
        "back": "Zurück",
        "mail_claim_subject": "Bestätigen Sie Ihren Aufenthalt in %(property)s (Link 30 Min. gültig)",
        "mail_claim_resend_subject": "Neuer Link: Bestätigen Sie Ihren Aufenthalt in %(property)s",
        "mail_claim_preheader": "Tippen Sie auf die Schaltfläche und erfassen Sie dann jeden Gast (etwa 2 Minuten pro Person).",
        "mail_claim_resend_preheader": "Ihr vorheriger Link funktioniert nicht mehr. Hier ist ein neuer.",
        "mail_claim_heading": "Aufenthalt bestätigen",
        "mail_claim_resend_heading": "Hier ist Ihr neuer Link",
        "mail_claim_intro": "Bestätigen Sie Ihren Aufenthalt in %(property)s (%(dates)s), indem Sie den Link unten öffnen.",
        "mail_claim_action": "Aufenthalt bestätigen",
        "mail_link_fallback": "Falls die Schaltfläche nicht funktioniert, kopieren Sie diese Adresse in Ihren Browser:",
        "mail_claim_expiry": "Die Schaltfläche funktioniert 30 Minuten lang. Nach der Bestätigung merkt sich dieses Telefon oder dieser Computer Ihren Aufenthalt. Sie brauchen den Link dort nicht mehr.",
        "mail_claim_expiry_resend": "Dieser neue Link ersetzt den vorherigen und funktioniert 30 Minuten lang.",
        "mail_claim_next_label": "Wie es weitergeht",
        "mail_claim_next_body": "Sie geben die Angaben aller Gäste dieses Aufenthalts ein und unterschreiben dann. Das dauert etwa zwei Minuten pro Gast und funktioniert auf dem Telefon. Wenn nach einer PIN gefragt wird, verwenden Sie die aus der Nachricht Ihres Gastgebers.",
        "mail_claim_next_done": "Alle sind bereits registriert. Der Link öffnet nur Ihre Aufenthaltsseite.",
        "mail_completion_subject": "Sie sind für %(property)s registriert: nichts weiter zu tun",
        "mail_completion_preheader": "Alle Gäste dieses Aufenthalts sind registriert. Nichts weiter zu tun.",
        "mail_completion_heading": "Alles erledigt",
        "mail_completion_intro": "Alle Gäste für %(property)s (%(dates)s) sind registriert. Sie müssen nichts weiter tun.",
        "mail_completion_action": "Zur Aufenthaltsseite",
        "mail_completion_note": "Ihr Gastgeber kümmert sich um die offizielle Meldung bei den Behörden. Diese E-Mail ist Ihre Quittung, keine amtliche Bestätigung.",
        "mail_reminder_guest_subject": "Morgen in %(property)s: %(filled)s von %(expected)s Gästen registriert",
        "mail_reminder_guest_subject_no_count": "Morgen in %(property)s: Die Gästeregistrierung ist nicht abgeschlossen",
        "mail_reminder_guest_preheader": "Ihr Aufenthalt beginnt morgen und die Registrierung ist nicht vollständig.",
        "mail_reminder_guest_heading": "Ihr Aufenthalt beginnt morgen",
        "mail_reminder_guest_intro": "Noch %(missing)s Gast/Gäste müssen vor Ihrer Anreise das Formular ausfüllen.",
        "mail_reminder_guest_intro_no_count": "Ihr Aufenthalt in %(property)s beginnt morgen und die Gästeregistrierung ist noch nicht vollständig.",
        "mail_reminder_guest_action": "Registrierung abschließen",
        "mail_reminder_guest_note_label": "Nur eine Erinnerung",
        "mail_reminder_guest_note": "Dies ist die einzige Erinnerung an eine unvollständige Registrierung, die wir senden.",
        "mail_reminder_guest_device": "Öffnen Sie den Link auf dem Telefon oder Computer, auf dem Sie begonnen haben. Auf einem anderen Gerät werden Sie nach der PIN Ihres Gastgebers gefragt.",
        "mail_guest_footer_about": "UbyHost ist der Gästeregistrierungsdienst, den Ihr Gastgeber nutzt.",
        "mail_guest_footer_why": "Sie erhalten diese E-Mail, weil Ihr Aufenthalt in %(property)s mit dieser Adresse registriert ist.",
        "mail_property_fallback": "Ihre Unterkunft",
        "mail_guest_footer_host_label": "Ihr Gastgeber",
        "mail_guest_footer_help": "Antworten Sie auf diese E-Mail, um Ihren Gastgeber zu erreichen.",
        "server_error_title": "Bei uns ist ein Fehler aufgetreten",
        "server_error_help": "Bereits gespeicherte Angaben sind sicher. Warten Sie kurz und laden Sie die Seite neu oder öffnen Sie Ihren Link erneut.",
        "door_code_title": "Ihr Türcode",
        "door_code_times": "Check-in ab %(checkin)s. Check-out bis %(checkout)s.",
        "door_code_first_use": "Der Code funktioniert vom Check-in bis zum Check-out. Wenn Sie ihn bis %(deadline)s nicht verwendet haben, funktioniert er nicht mehr. Bitten Sie dann Ihren Gastgeber um einen neuen Code.",
        "door_code_sent": "Wir haben ihn auch an %(email)s gesendet.",
        "door_code_preparing": "Ihren Türcode erhalten Sie per E-Mail.",
        "door_code_failed": "Ihr Gastgeber schickt Ihnen den Türcode.",
        "mail_door_code_subject": "Ihr Türcode für %(property)s",
        "privacy_door_code_title": "Türcode",
        "privacy_door_code_body": "Diese Unterkunft gibt Ihnen einen Türcode, sobald alle Gäste registriert sind, damit Sie während Ihres Aufenthalts eintreten können. Der Code wird über TTLock erstellt, einen Dienst der Hangzhou Sciener Intelligent Control Technology Co., Ltd. (China), die das Schloss, den Code, seine Gültigkeitszeiten und eine Referenznummer erhält, aber nicht Ihren Namen oder Ihre Kontaktdaten. Der Code wird auf Ihrer Aufenthaltsseite angezeigt und an die E-Mail-Adresse gesendet, mit der Sie sich registriert haben, mit einer Kopie an den Gastgeber. Er wird verschlüsselt gespeichert und einen Tag nach Ablauf gelöscht. Rechtsgrundlage ist Ihr Beherbergungsvertrag (Art. 6 Abs. 1 lit. b DSGVO). Das Schloss zeichnet auf, wann der Code verwendet wird, und der Gastgeber sieht das in seiner TTLock-App.",

    },
    # WP26: Spanish. Machine-assisted; a native speaker should review it,
    # the legal notice and privacy keys first (see notes/WP26-guest-languages.md).
    "es": {
        "title": "Registro de huéspedes",
        "language_label": "Idioma",
        "date_placeholder": "DD.MM.AAAA",
        "legal_intro": "La ley checa exige que su anfitrión registre a cada huésped, incluidos los niños, y comunique los huéspedes extranjeros a la policía.",
        "why_title": "Por qué rellena este formulario",
        "why_law": "Ley n.º 326/1999 Recop., sobre la residencia de extranjeros, §§ 101–103.",
        "why_point_accuracy": "Debe introducir información veraz que coincida con su documento de viaje. El anfitrión es legalmente responsable de su exactitud y puede negarle el alojamiento si no muestra su documento de identidad o no facilita datos correctos.",
        "pick_stay": "Busque su estancia",
        "pick_stay_help": "Toque sus fechas de llegada y salida para continuar.",
        "arrival_question": "¿Cuál es su estancia?",
        "arrival_cta": "Esa es mi estancia",
        "tw_label_access": "Acceso privado",
        "tw_label_stay": "Su estancia",
        "tw_label_email": "Su grupo y su e-mail",
        "tw_label_confirm": "Confirme su estancia",
        "tw_label_group": "Su grupo",
        "tw_label_saved": "Guardado",
        "tw_label_done": "Todo listo",
        "tw_label_notice": "Aviso",
        "tw_stay_n": "Estancia %(n)s de %(total)s",
        "tw_property": "Alojamiento",
        "tw_registered": "Registrados",
        "tw_guest": "Huésped",
        "tw_fewer": "Una persona menos",
        "tw_more": "Una persona más",
        "tw_document_title": "Documento de viaje",
        "tw_email_short": "Aquí le enviamos su enlace privado. Sin publicidad.",
        "tw_email_more": "Para qué usamos su e-mail",
        "tw_step_details": "Datos",
        "tw_step_document": "Documento",
        "tw_step_home": "Domicilio",
        "tw_step_photo": "Foto",
        "tw_step_sign": "Firma",
        "tw_step_check": "Revisión",
        "tw_dob_day": "Día",
        "tw_dob_month": "Mes",
        "tw_dob_year": "Año",
        "tw_country_search": "Empiece a escribir un país",
        "tw_country_none": "Ningún país coincide",
        "tw_country_required": "Elija un país.",
        "tw_purpose_other": "Otro…",
        "tw_sign_here": "Firme aquí con el dedo",
        "tw_signed": "Firmado",
        "tw_guest_n_of": "Huésped %(current)s de %(total)s",
        "tw_guest_n": "Huésped %(current)s",
        "tw_next_guest": "Registrar huésped %(current)s de %(total)s",
        "stay_ongoing": "En curso",
        "stay_arriving_today": "Llegada hoy",
        "host_details": "Su anfitrión",
        "host_details_help": "¿Tiene preguntas? Contacte con su anfitrión.",
        "host_details_missing": "Utilice el teléfono o el e-mail del mensaje que contenía este enlace.",
        "message_from_host": "Un mensaje de su anfitrión",
        "claim_title": "Cuántas personas y su e-mail",
        "claim_help": "Solo su grupo puede abrir los formularios.",
        "claim_email": "¿Cuál es su dirección de e-mail?",
        "claim_email_help": "Además, un recordatorio el día antes de la llegada si faltan formularios y un justificante (su anfitrión recibe una copia). En otros lugares se muestra enmascarada.",
        "claim_cookie_help": "Solo cookies necesarias: acceso con PIN (7 días), su idioma y esta estancia (60 días).",
        "claim_submit": "Enviarme el enlace",
        "claim_sent_title": "Revise su e-mail",
        "claim_sent_body": "Hemos enviado un enlace a %(email)s. Ábralo en este teléfono para continuar. Funciona durante 30 minutos. Si se le vuelve a pedir el PIN, introduzca el mismo.",
        "claim_sent_retry": "¿No ha recibido el e-mail tras unos minutos? Revise el spam o envíelo de nuevo",
        "claim_error_bad_email": "Introduzca una dirección de e-mail válida.",
        "claim_error_bad_party": "Indique cuántas personas se alojan (1–60).",
        "claim_error_held": "Otra persona está confirmando esta estancia. Inténtelo de nuevo en unos minutos.",
        "claim_error_already_claimed": "Esta estancia ya está asignada a otra dirección de e-mail.",
        "claim_error_rate": "Demasiadas solicitudes de enlace. Inténtelo de nuevo dentro de un rato.",
        "claim_error_cooldown": "Acabamos de enviar un enlace a esta dirección. Espere un minuto antes de volver a pedirlo.",
        "claim_error_recipient_rate": "Esta dirección ha recibido demasiados enlaces de registro. Inténtelo más tarde.",
        "claim_error_bot": "Complete la verificación de seguridad e inténtelo de nuevo.",
        "assigned_title": "Esta reserva ya está asignada",
        "assigned_body": "Esta estancia ya está vinculada al e-mail de abajo. Si es usted, introdúzcalo y le enviaremos de nuevo el enlace privado.",
        "assigned_resend": "Enviarme el enlace de nuevo",
        "assigned_stay_label": "Su estancia seleccionada",
        "assigned_last_sent": "Último envío del enlace privado: %(date)s",
        "assigned_not_mine": "Esta no es mi reserva",
        "claim_confirm_title": "¿Es esta su reserva?",
        "claim_confirm_button": "Sí, es mi estancia",
        "claim_confirm_failed": "Ese enlace de confirmación no es válido o ha caducado.",
        "back_to_stays": "Elegir otras fechas",
        "wrong_dates": "¿No son sus fechas?",
        "your_stay_badge": "Se envió un formulario desde este dispositivo",
        "stay_not_started": "Aún no iniciado",
        "error_no_stay": "Seleccione las fechas de su estancia.",
        "error_party_size": "Indique cuántas personas se alojan (1–60).",
        "no_stays": "Todavía no hay nada que registrar",
        "no_stays_help": "El registro se abre unos días antes de la llegada. Vuelva entonces a este mismo enlace. ¿Ya ha llegado? Escriba a su anfitrión. Puede enviarle un enlace directo a su estancia.",
        "bad_link_title": "Este enlace de huésped no es válido",
        "bad_link_help": "Puede estar incompleto o haber sido sustituido. Pida a su anfitrión un enlace nuevo.",
        "stay_gone_title": "Esa estancia ya no está abierta al registro",
        "stay_gone_help": "Puede que las fechas hayan cambiado, que la reserva se haya cancelado o que su anfitrión haya cerrado el registro de esta estancia. Escriba a su anfitrión.",
        "form_expired_title": "El formulario ha caducado",
        "form_expired_help": "No se ha guardado nada. Vuelva a empezar desde el enlace de abajo.",
        "rate_limited_title": "Demasiados intentos desde su conexión",
        "rate_limited_help": "No se ha guardado nada. Espere unos 15 minutos e inténtelo de nuevo. Si no puede continuar, escriba a su anfitrión.",
        "not_yours_title": "Este formulario no se puede abrir en este dispositivo",
        "not_yours_help": "Para que ningún huésped vea los datos del pasaporte de otro, un formulario solo puede volver a abrirse en el dispositivo en el que se rellenó. Si necesita una corrección, escriba a su anfitrión.",
        "already_filed_title": "Estos datos ya se han comunicado",
        "already_filed_help": "Por exactitud legal, un registro ya comunicado no puede modificarse desde este formulario. Escriba a su anfitrión si hay algo que corregir.",
        "form_locked_title": "Este formulario está bloqueado",
        "form_locked_help": "Sus datos se han guardado y firmado. Para proteger su información, el formulario no puede modificarse desde este enlace. Escriba a su anfitrión si hay algo que corregir.",
        "form_locked_short": "Guardado y bloqueado. Para cualquier cambio, contacte con su anfitrión.",
        "pin_title": "Introduzca el PIN de acceso",
        "pin_help": "El PIN está en el mensaje de su anfitrión.",
        "pin_label": "PIN",
        "pin_submit": "Continuar",
        "pin_wrong": "El PIN no es correcto. Revise el mensaje de su anfitrión.",
        "pin_recovery": "¿No encuentra el PIN? Pida a su anfitrión que le reenvíe el mensaje de registro.",
        "pin_rate_limited": "Demasiados intentos de PIN incorrectos. Espere unos 15 minutos e inténtelo de nuevo.",
        "pin_locked_out": "Demasiados intentos de PIN incorrectos; este enlace queda en pausa durante un día. Pida a su anfitrión un PIN nuevo.",
        "security_check_failed": "Complete la verificación de seguridad e inténtelo de nuevo.",
        "start_over": "Empezar de nuevo",
        "night_one": "%(n)s noche",
        "nights_few": "%(n)s noches",
        "nights_many": "%(n)s noches",
        "arrive": "Llegada",
        "depart": "Salida",
        "select": "Es mi estancia",
        "party_question": "¿Cuántas personas se alojan?",
        "party_help": "Cuente a todos, incluidos los niños. Cada persona necesita su propio formulario.",
        "party_confirm": "Continuar",
        "people_progress": "Registrados: %(done)s de %(total)s",
        "person_progress": "Persona %(current)s de %(total)s",
        "stay_label": "Su estancia",
        "steps_label": "Progreso del check-in",
        "step_done": "Hecho",
        "form_step_progress": "Paso %(current)s de %(total)s",
        "form_step_progress_title": "%(progress)s · %(title)s",
        "next_step": "Continuar",
        "previous_step": "Atrás",
        "add_person": "Añadir persona",
        "add_first_person": "Empiece con sus propios datos",
        "saved_title": "Guardado, gracias",
        "saved_body": "Sus datos se han guardado. Ahora añada a la siguiente persona de su grupo.",
        "reported_title": "Datos enviados y comunicados",
        "reported_body": "Gracias. Su anfitrión ya ha comunicado este registro. Contacte con su anfitrión si hay algo que corregir a continuación.",
        "summary_title": "Sus datos enviados",
        "summary_fold_saved": "guardado ✓",
        "your_details": "Sus datos",
        "person": "Persona",
        "you": "usted",
        "completed": "completado",
        "not_filled": "sin rellenar",
        "edit": "Editar",
        "all_done_title": "Gracias. Todos están registrados",
        "all_done_body": "No necesita hacer nada más. Puede cerrar esta página.",
        "all_done_receipt": "Hemos enviado una confirmación a %(email)s.",
        "checkin_info": "Check-in",
        "checkout_info": "Check-out",
        "still_missing": "Quedan por registrar: %(n)s",
        "add_another": "Añadir otra persona",
        "someone_missing": "¿Ha olvidado a alguien? Los niños también deben registrarse.",
        "continue_filling": "Seguir rellenando",
        "surname": "Apellidos",
        "first_name": "Nombre(s)",
        "birth_date": "Fecha de nacimiento",
        "birth_date_readback": "Es decir, %(date)s.",
        "residence_help": "Su domicilio permanente, tal como figura en su pasaporte o documento de identidad.",
        "residence_copied": "Copiado de %(name)s. Cámbielo si esta persona vive en otro lugar.",
        "nationality": "Nacionalidad",
        "countries_common": "Más frecuentes",
        "countries_all": "Todos los países",
        "doc_number": "Número del documento de viaje",
        "doc_number_help": "Número de pasaporte, o número del documento de identidad solo para ciudadanos de la UE.",
        "invoice_mail_issued_subject": "Factura %(number)s",
        "invoice_mail_issued_subject_stay": "Factura %(number)s – %(stay_property)s",
        "invoice_mail_issued_intro": "Su factura de %(property)s está lista para descargar.",
        "invoice_mail_issued_button": "Descargar factura",
        "mail_invoice_title": "Factura",
        "mail_invoice_number": "Número",
        "mail_invoice_total": "Total",
        "mail_invoice_property": "Alojamiento",
        "visa_number": "Número de visado",
        "visa_help": "Solo si se le expidió un visado checo o Schengen.",
        "residence_title": "Domicilio permanente",
        "res_street": "Calle y número",
        "res_city": "Ciudad",
        "res_country": "País",
        "purpose": "Motivo de la estancia",
        "stay_dates": "Sus fechas",
        "child_title": "Esta persona es un menor que viaja con el pasaporte de un progenitor",
        "child_help": "Marque esta casilla solo si el menor no tiene pasaporte propio. En ese caso necesitaremos el número de documento del progenitor.",
        "parent_doc": "N.º de documento del progenitor",
        "note": "Nota",
        "signature": "Firma",
        "signature_help": "Firme con el dedo o el ratón. Lo exige la ley checa.",
        "signature_clear": "Borrar",
        "signature_missing": "Firme en el recuadro antes de continuar.",
        "signature_kept": "Su firma está guardada. Vuelva a firmar solo si desea cambiarla.",
        "passport_photo_title": "Pasaporte o documento de identidad",
        "passport_photo_help": "Haga una foto de la página con su fotografía o suba un PDF. Solo su anfitrión puede verlo y se elimina después de la comprobación.",
        "passport_photo_label": "Pasaporte o documento de identidad",
        "passport_photo_take": "Hacer foto",
        "passport_photo_choose": "Elegir archivo",
        "passport_photo_retake": "Repetir o elegir otro",
        "passport_photo_selected": "Seleccionado: %(name)s",
        "passport_photo_pending_nat": "Primero elija su nacionalidad en el paso 1.",
        "passport_photo_not_required": "Los ciudadanos checos no suben foto del pasaporte en este formulario.",
        "passport_photo_hint": "Una foto JPEG, PNG o WebP de hasta 5 MB, o un PDF de hasta 15 MB.",
        "passport_photo_too_large_image": "La foto es demasiado grande. Use un archivo de menos de 5 MB.",
        "passport_photo_too_large_pdf": "El PDF es demasiado grande. Use un archivo de menos de 15 MB.",
        "passport_photo_bad_type": "Use una foto JPEG, PNG o WebP, o un formulario de registro en PDF.",
        "passport_photo_missing": "Suba una foto de su pasaporte o documento de identidad.",
        "review_title": "Revise antes de enviar",
        "review_help": "Tras el envío, estos datos quedan bloqueados y solo su anfitrión puede modificarlos.",
        "review_edit": "Cambiar",
        "legal_notice_title": "Información legal",
        "legal_notice_duty_title": "Su obligación legal",
        "legal_notice_duty_body": "Todas las personas alojadas deben registrarse. Los huéspedes extranjeros se comunican a la Policía de Extranjería; los ciudadanos checos solo se anotan en el libro de registro.",
        "legal_notice_accuracy_title": "Solo información exacta",
        "legal_notice_accuracy_body": "Introduzca todo exactamente como figura en su pasaporte o documento de identidad. Sus datos pueden comunicarse automáticamente, antes de que su anfitrión los revise, y los datos falsos pueden suponer una multa para su anfitrión.",
        "legal_notice_passport_title": "Foto del pasaporte (extranjeros)",
        "legal_notice_passport_body": "Los huéspedes extranjeros suben una foto de la página de datos de su pasaporte o documento de identidad (o un PDF). Solo su anfitrión la ve, para compararla con lo que usted introdujo. Se elimina tras la comprobación o, en su defecto, 7 días después del check-in, y nunca más tarde de 30 días después de subirla. Nunca se envía a la policía.",
        "legal_notice_reporting_title": "Comunicación a la policía y libro de registro",
        "legal_notice_reporting_body": "Su anfitrión comunica los datos de los huéspedes extranjeros a la Policía de Extranjería en un plazo de tres días hábiles desde la llegada, de inmediato o un poco más tarde. Los registros completos pueden enviarse automáticamente. Los mismos datos permanecen en el libro de registro durante seis años.",
        "legal_notice_retention_title": "Cuánto tiempo se conservan los datos",
        "legal_notice_retention_body": "Los datos de registro y su firma se conservan durante seis años tras el final de su estancia, según exige el § 101, apdo. 4, de la Ley n.º 326/1999 Recop., y después se eliminan. El tratamiento se basa en una obligación legal (artículo 6, apartado 1, letra c, del RGPD), no en el consentimiento.",
        "legal_notice_refusal_title": "Si se niega",
        "legal_notice_refusal_body": "Debe presentar un documento de viaje válido para su verificación. Si se niega a facilitar datos exactos, a firmar o a permitir la verificación de su identidad, el anfitrión puede negarle legalmente el alojamiento.",
        "legal_ack_label": "Mis datos son correctos y he leído la información anterior y el aviso de privacidad.",
        "legal_ack_missing": "Confirme que ha leído la información legal.",
        "submit": "Enviar mis datos",
        "optional": "opcional",
        "required": "obligatorio",
        "check_in": "Check-in",
        "check_out": "Check-out",
        "privacy": "Se utilizan únicamente para la comunicación legal de su anfitrión a la Policía checa y se conservan durante seis años.",
        "skip_to_form": "Ir al formulario",
        "loading": "Cargando…",
        "privacy_link": "Cómo se tratan sus datos",
        "privacy_first_line": "UbyHost solo recoge lo que exigen la ley checa y su registro, y no utiliza cookies de seguimiento.",
        "privacy_title": "Aviso de privacidad",
        "privacy_intro": "Qué ocurre con los datos que introduce, conforme a los artículos 13 y 14 del RGPD.",
        "notice_version": "Versión del aviso de privacidad %(version)s",
        "privacy_controller": "Su responsable del tratamiento",
        "privacy_controller_body": "Esta persona jurídica determina para qué y cómo se utilizan sus datos de huésped y es responsable de sus derechos conforme al RGPD. Que el contacto para la estancia indicado abajo tenga otro nombre no cambia esta función.",
        "privacy_controller_missing": "Su anfitrión debe identificar a la empresa responsable de sus datos. Si aquí faltan, pida a su anfitrión su denominación social y su domicilio.",
        "privacy_stay_contact": "Preguntas sobre su estancia",
        "privacy_stay_contact_body": "El gestor del alojamiento es su contacto práctico para cuestiones de llegada, alojamiento y reserva. Para solicitudes de acceso, rectificación, supresión u oposición, contacte con el responsable del tratamiento indicado arriba.",
        "privacy_purpose": "Por qué se recogen los datos",
        "privacy_purpose_body": "Para cumplir dos obligaciones legales de un proveedor de alojamiento en Chequia: comunicar los extranjeros alojados a la Policía de Extranjería y llevar un libro de registro (domovní kniha). No se utilizan para ningún otro fin.",
        "privacy_basis": "Base jurídica",
        "privacy_basis_body": "Artículo 6, apartado 1, letra c, del RGPD: cumplimiento de una obligación legal, en concreto los §§ 101–103 de la Ley n.º 326/1999 Recop., sobre la residencia de extranjeros. No se le pide su consentimiento, porque la obligación se aplica tanto si está de acuerdo como si no.",
        "privacy_data": "Qué datos se recogen",
        "privacy_data_body": "Nombre y apellidos, fecha de nacimiento, nacionalidad, número del documento de viaje, número de visado si se expidió, domicilio permanente en el extranjero, motivo de la estancia, inicio y fin de la estancia, firma, número de personas declarado y la dirección de e-mail utilizada para reclamar la reserva. El número de personas se utiliza para determinar si están completos todos los formularios de huéspedes esperados y se conserva con el registro de la estancia.",
        "privacy_data_body_no_email": "Nombre y apellidos, fecha de nacimiento, nacionalidad, número del documento de viaje, número de visado si se expidió, domicilio permanente en el extranjero, motivo de la estancia, inicio y fin de la estancia, firma y número de personas declarado. Esta versión del formulario no recoge su dirección de e-mail. El número de personas se utiliza para determinar si están completos todos los formularios de huéspedes esperados y se conserva con el registro de la estancia.",
        "privacy_email_title": "Mensajes de e-mail y enmascaramiento",
        "privacy_email_body": "Su e-mail asegura la reserva y se utiliza para enviar el enlace privado al formulario, un recordatorio el día antes si los formularios declarados siguen incompletos y un justificante de finalización. El gestor del alojamiento recibe una copia del justificante de finalización. La dirección completa está disponible para el responsable del tratamiento configurado y, cuando está activado, para el proveedor de envío de e-mails; las pantallas públicas para huéspedes solo muestran una dirección enmascarada. No se utiliza con fines de marketing.",
        "privacy_cookies_title": "Cookies necesarias",
        "privacy.cookies.table_intro": "La siguiente tabla enumera todas las cookies y elementos de almacenamiento local que establece el servicio.",
        "cookies.table.name": "Nombre",
        "cookies.table.party": "Establecida por",
        "cookies.table.purpose": "Finalidad",
        "cookies.table.lifetime": "Duración",
        "cookies.party.first": "UbyHost",
        "privacy_cookies_body": "UbyHost utiliza solo cookies de huésped necesarias: acceso con PIN durante un máximo de 7 días, e idioma y formularios enviados desde este dispositivo durante un máximo de 60 días. Cuando la reclamación por e-mail está activada, el acceso a la reserva confirmada también se recuerda durante un máximo de 60 días. Impiden que otro huésped vea o modifique su formulario y mantienen el proceso utilizable. Cloudflare puede establecer identificadores de seguridad cuando se activa Turnstile o la protección contra bots. No hay cookies publicitarias ni analíticas.",
        "privacy_passport_photo_title": "Foto o PDF temporal del pasaporte",
        "privacy_passport_photo_body": "Si no es ciudadano checo, puede subir una fotografía de la página de datos de su pasaporte o documento de identidad, o un formulario de registro en PDF, para que el anfitrión verifique sus datos. El archivo se trata únicamente para esa comprobación y el acceso en la aplicación está restringido a usuarios autorizados del anfitrión. Se elimina tras la verificación; si no se verifica, se elimina 7 días después del check-in, y nunca más tarde de 30 días después de subirlo. Puede ser necesario un acceso restringido del operador o de la infraestructura para operar y proteger el servicio. No se transmite a la policía.",
        "privacy_recipients": "Quién los recibe",
        "privacy_recipients_body": "La Policía de la República Checa, Dirección del Servicio de Policía de Extranjería, y cualquier agente que inspeccione el libro de registro; su proveedor de alojamiento; UbyHost como su encargado del tratamiento; y un proveedor de envío de e-mails cuando la mensajería está activada. Los datos nunca se venden, no se envían al sitio de reservas ni se utilizan con fines de marketing.",
        "privacy_recipients_body_no_email": "La Policía de la República Checa, Dirección del Servicio de Policía de Extranjería, cualquier agente que inspeccione el libro de registro, su proveedor de alojamiento y UbyHost como su encargado del tratamiento. Los datos nunca se venden, no se envían al sitio de reservas ni se utilizan con fines de marketing.",
        "privacy_bot_protection_title": "Protección del enlace de registro",
        "privacy_bot_protection_body": "Si alguien introduce repetidamente un PIN de acceso incorrecto, el formulario puede mostrar Cloudflare Turnstile para bloquear abusos automatizados. Las páginas de producción también pueden estar protegidas por Cloudflare contra abusos automatizados. Estas comprobaciones pueden tratar datos técnicos de conexión (como la dirección IP) conforme al aviso de privacidad de Cloudflare. No se utilizan con fines de marketing.",
        "privacy_processor": "Quién gestiona este sitio web",
        "privacy_processor_body": "El software UbyHost lo opera %(name)s, IČO %(ico)s, %(address)s, que trata los datos únicamente según las instrucciones del responsable del tratamiento configurado para gestionar el formulario de registro, los mensajes transaccionales y los registros almacenados. Las preguntas sobre su estancia deben dirigirse a su anfitrión; las solicitudes de ejercicio de derechos sobre datos personales, al responsable indicado arriba.",
        "privacy_retention": "Cuánto tiempo se conservan",
        "privacy_retention_body": "Los datos de registro del libro de registro y las firmas se conservan durante seis años tras el final de la estancia, según exige el § 101, y después se eliminan. El e-mail de reclamación permanece vinculado mientras se conserve el registro de la reserva, salvo que el anfitrión libere la reclamación. Los registros de envío de mensajes completados o fallidos se eliminan normalmente a los 14 días; copias de seguridad limitadas pueden persistir hasta que venza su ciclo de conservación.",
        "privacy_retention_body_no_email": "Los datos de registro del libro de registro y las firmas se conservan durante seis años tras el final de la estancia, según exige el § 101, y después se eliminan. Copias de seguridad limitadas pueden persistir hasta que venza su ciclo de conservación.",
        "privacy_rights": "Sus derechos",
        "privacy_rights_body": "Puede solicitar una copia de sus datos, la rectificación de cualquier dato inexacto y saber cómo se están tratando. La supresión y la oposición están limitadas mientras dure la obligación legal de conservar el registro. No hay decisiones automatizadas ni elaboración de perfiles.",
        "privacy_complaint": "Si considera que sus datos se tratan de forma indebida, puede presentar una reclamación ante la autoridad checa de protección de datos: Úřad pro ochranu osobních údajů, Pplk. Sochora 27, 170 00 Praha 7, uoou.gov.cz.",
        "privacy_required": "Facilitar estos datos es un requisito legal, no una decisión propia del anfitrión. Sin ellos, el anfitrión no puede alojarle legalmente.",
        "privacy_contact": "Contacto",
        "fix_errors": "Corrija lo siguiente:",
        "back": "Atrás",
        "mail_claim_subject": "Confirme su estancia en %(property)s (enlace válido 30 min)",
        "mail_claim_resend_subject": "Nuevo enlace: confirme su estancia en %(property)s",
        "mail_claim_preheader": "Toque el botón y rellene los datos de cada huésped (unos 2 minutos por persona).",
        "mail_claim_resend_preheader": "Su enlace anterior ha dejado de funcionar. Aquí tiene uno nuevo.",
        "mail_claim_heading": "Confirme su estancia",
        "mail_claim_resend_heading": "Aquí tiene su nuevo enlace",
        "mail_claim_intro": "Confirme su estancia en %(property)s (%(dates)s) abriendo el enlace de abajo.",
        "mail_claim_action": "Confirmar mi estancia",
        "mail_link_fallback": "Si el botón no funciona, copie esta dirección en su navegador:",
        "mail_claim_expiry": "El botón funciona durante 30 minutos. Tras confirmar, este teléfono u ordenador recordará su estancia. No volverá a necesitar el enlace en él.",
        "mail_claim_expiry_resend": "Este nuevo enlace sustituye al anterior y funciona durante 30 minutos.",
        "mail_claim_next_label": "Qué ocurre a continuación",
        "mail_claim_next_body": "Introducirá los datos de cada huésped de esta estancia y después firmará. Se tarda unos dos minutos por huésped y funciona en el teléfono. Si se le pide un PIN, use el del mensaje de su anfitrión.",
        "mail_claim_next_done": "Todos ya están registrados. El enlace solo abre la página de su estancia.",
        "mail_completion_subject": "Registro completado para %(property)s: no tiene que hacer nada más",
        "mail_completion_preheader": "Todos los huéspedes de esta estancia están registrados. No tiene que hacer nada más.",
        "mail_completion_heading": "Todo listo",
        "mail_completion_intro": "Todos los huéspedes de %(property)s (%(dates)s) están registrados. No necesita hacer nada más.",
        "mail_completion_action": "Ver la página de su estancia",
        "mail_completion_note": "Su anfitrión se encarga del registro oficial ante las autoridades. Este e-mail es su justificante, no una confirmación oficial.",
        "mail_reminder_guest_subject": "Mañana en %(property)s: %(filled)s de %(expected)s huéspedes registrados",
        "mail_reminder_guest_subject_no_count": "Mañana en %(property)s: el registro de huéspedes no está terminado",
        "mail_reminder_guest_preheader": "Su estancia empieza mañana y el registro no está completo.",
        "mail_reminder_guest_heading": "Su estancia empieza mañana",
        "mail_reminder_guest_intro": "%(missing)s huésped(es) más aún debe(n) rellenar el formulario antes de su llegada.",
        "mail_reminder_guest_intro_no_count": "Su estancia en %(property)s empieza mañana y el registro de huéspedes aún no está completo.",
        "mail_reminder_guest_action": "Completar el registro",
        "mail_reminder_guest_note_label": "Un único recordatorio",
        "mail_reminder_guest_note": "Este es el único recordatorio de registro incompleto que le enviaremos.",
        "mail_reminder_guest_device": "Ábralo en el teléfono u ordenador en el que empezó. En otro dispositivo se le pedirá el PIN de su anfitrión.",
        "mail_guest_footer_about": "UbyHost es el servicio de registro de huéspedes que utiliza su anfitrión.",
        "mail_guest_footer_why": "Ha recibido este e-mail porque su estancia en %(property)s está registrada con esta dirección.",
        "mail_property_fallback": "su alojamiento",
        "mail_guest_footer_host_label": "Su anfitrión",
        "mail_guest_footer_help": "Responda a este e-mail para contactar con su anfitrión.",
        "server_error_title": "Algo ha fallado por nuestra parte",
        "server_error_help": "Los datos que ya guardó están a salvo. Espere un momento y vuelva a cargar la página o abra de nuevo su enlace.",
        "door_code_title": "Su código de la puerta",
        "door_code_times": "Entrada desde %(checkin)s. Salida hasta %(checkout)s.",
        "door_code_first_use": "El código funciona desde el check-in hasta el check-out. Si no lo ha usado antes del %(deadline)s, dejará de funcionar. Entonces pida a su anfitrión un código nuevo.",
        "door_code_sent": "También lo hemos enviado a %(email)s.",
        "door_code_preparing": "Recibirá su código de la puerta por correo electrónico.",
        "door_code_failed": "Su anfitrión le enviará el código de la puerta.",
        "mail_door_code_subject": "Su código de la puerta para %(property)s",
        "privacy_door_code_title": "Código de la puerta",
        "privacy_door_code_body": "Este alojamiento le da un código de la puerta cuando todos los huéspedes se han registrado, para que pueda entrar durante su estancia. El código se crea a través de TTLock, un servicio de Hangzhou Sciener Intelligent Control Technology Co., Ltd. (China), que recibe la cerradura, el código, sus horas de validez y un número de referencia, pero no su nombre ni sus datos de contacto. El código se muestra en la página de su estancia y se envía a la dirección de correo con la que se registró, con copia al anfitrión. Se guarda cifrado y se elimina un día después de que caduque. La base jurídica es su contrato de alojamiento (art. 6, apdo. 1, letra b, del RGPD). La cerradura registra cuándo se usa el código y el anfitrión lo ve en su aplicación TTLock.",

    },
    # WP26: French. Machine-assisted; a native speaker should review it,
    # the legal notice and privacy keys first (see notes/WP26-guest-languages.md).
    "fr": {
        "title": "Enregistrement des voyageurs",
        "language_label": "Langue",
        "date_placeholder": "JJ.MM.AAAA",
        "legal_intro": "La loi tchèque impose à votre hôte d'enregistrer chaque voyageur, enfants compris, et de déclarer les voyageurs étrangers à la police.",
        "why_title": "Pourquoi remplir ce formulaire",
        "why_law": "Loi n° 326/1999 Rec. relative au séjour des étrangers, §§ 101–103.",
        "why_point_accuracy": "Vous devez saisir des informations exactes, conformes à votre document de voyage. L'hôte est légalement responsable de leur exactitude et peut refuser l'hébergement si vous ne présentez pas de pièce d'identité ou ne fournissez pas d'informations correctes.",
        "pick_stay": "Trouvez votre séjour",
        "pick_stay_help": "Touchez vos dates d'arrivée et de départ pour continuer.",
        "arrival_question": "Quel est votre séjour ?",
        "arrival_cta": "C'est mon séjour",
        "tw_label_access": "Accès privé",
        "tw_label_stay": "Votre séjour",
        "tw_label_email": "Groupe et e-mail",
        "tw_label_confirm": "Confirmez votre séjour",
        "tw_label_group": "Votre groupe",
        "tw_label_saved": "Enregistré",
        "tw_label_done": "C'est terminé",
        "tw_label_notice": "Information",
        "tw_stay_n": "Séjour %(n)s sur %(total)s",
        "tw_property": "Logement",
        "tw_registered": "Enregistré",
        "tw_guest": "Voyageur",
        "tw_fewer": "Une personne de moins",
        "tw_more": "Une personne de plus",
        "tw_document_title": "Document de voyage",
        "tw_email_short": "Nous y envoyons votre lien privé. Pas de marketing.",
        "tw_email_more": "À quoi sert votre e-mail",
        "tw_step_details": "Identité",
        "tw_step_document": "Document",
        "tw_step_home": "Domicile",
        "tw_step_photo": "Photo",
        "tw_step_sign": "Signature",
        "tw_step_check": "Contrôle",
        "tw_dob_day": "Jour",
        "tw_dob_month": "Mois",
        "tw_dob_year": "Année",
        "tw_country_search": "Saisissez un pays",
        "tw_country_none": "Aucun pays trouvé",
        "tw_country_required": "Veuillez choisir un pays.",
        "tw_purpose_other": "Autre…",
        "tw_sign_here": "Signez ici avec le doigt",
        "tw_signed": "Signé",
        "tw_guest_n_of": "Voyageur %(current)s sur %(total)s",
        "tw_guest_n": "Voyageur %(current)s",
        "tw_next_guest": "Enregistrer le voyageur %(current)s sur %(total)s",
        "stay_ongoing": "En cours",
        "stay_arriving_today": "Arrivée aujourd'hui",
        "host_details": "Votre hôte",
        "host_details_help": "Des questions ? Contactez votre hôte.",
        "host_details_missing": "Utilisez le téléphone ou l'e-mail indiqué dans le message contenant ce lien.",
        "message_from_host": "Un message de votre hôte",
        "claim_title": "Nombre de personnes et votre e-mail",
        "claim_help": "Seul votre groupe peut ouvrir les formulaires.",
        "claim_email": "Quelle est votre adresse e-mail ?",
        "claim_email_help": "Également un rappel la veille de l'arrivée si des formulaires manquent, et un récapitulatif (votre hôte en reçoit une copie). Ailleurs, elle est masquée.",
        "claim_cookie_help": "Uniquement des cookies nécessaires : accès par PIN (7 jours), votre langue et ce séjour (60 jours).",
        "claim_submit": "M'envoyer le lien",
        "claim_sent_title": "Consultez vos e-mails",
        "claim_sent_body": "Nous avons envoyé un lien à %(email)s. Ouvrez-le sur ce téléphone pour continuer. Il est valable 30 minutes. Si le PIN vous est redemandé, saisissez le même.",
        "claim_sent_retry": "Pas d'e-mail après quelques minutes ? Vérifiez vos spams ou renvoyez-le",
        "claim_error_bad_email": "Veuillez saisir une adresse e-mail valide.",
        "claim_error_bad_party": "Veuillez indiquer le nombre de personnes (1–60).",
        "claim_error_held": "Quelqu'un d'autre est en train de confirmer ce séjour. Réessayez dans quelques minutes.",
        "claim_error_already_claimed": "Ce séjour est déjà associé à une autre adresse e-mail.",
        "claim_error_rate": "Trop de demandes de lien. Veuillez réessayer un peu plus tard.",
        "claim_error_cooldown": "Nous venons d'envoyer un lien à cette adresse. Veuillez patienter une minute avant de redemander.",
        "claim_error_recipient_rate": "Cette adresse a reçu trop de liens d'enregistrement. Réessayez plus tard.",
        "claim_error_bot": "Veuillez effectuer la vérification de sécurité et réessayer.",
        "assigned_title": "Cette réservation est déjà attribuée",
        "assigned_body": "Ce séjour est déjà associé à l'e-mail ci-dessous. Si c'est le vôtre, saisissez-le et nous renverrons le lien privé.",
        "assigned_resend": "Renvoyer le lien",
        "assigned_stay_label": "Séjour sélectionné",
        "assigned_last_sent": "Dernier envoi du lien privé : %(date)s",
        "assigned_not_mine": "Ce n'est pas ma réservation",
        "claim_confirm_title": "Est-ce votre réservation ?",
        "claim_confirm_button": "Oui, c'est mon séjour",
        "claim_confirm_failed": "Ce lien de confirmation est invalide ou a expiré.",
        "back_to_stays": "Choisir d'autres dates",
        "wrong_dates": "Ce ne sont pas vos dates ?",
        "your_stay_badge": "Un formulaire a été envoyé depuis cet appareil",
        "stay_not_started": "Pas encore commencé",
        "error_no_stay": "Veuillez sélectionner les dates de votre séjour.",
        "error_party_size": "Veuillez indiquer le nombre de personnes (1–60).",
        "no_stays": "Rien à enregistrer pour l'instant",
        "no_stays_help": "L'enregistrement ouvre quelques jours avant l'arrivée. Revenez alors sur ce même lien. Déjà arrivé ? Écrivez à votre hôte. Il peut vous envoyer un lien direct vers votre séjour.",
        "bad_link_title": "Ce lien n'est pas valide",
        "bad_link_help": "Il est peut-être incomplet ou a été remplacé. Veuillez demander un nouveau lien à votre hôte.",
        "stay_gone_title": "Ce séjour n'est plus ouvert à l'enregistrement",
        "stay_gone_help": "Les dates ont peut-être changé, la réservation a pu être annulée, ou votre hôte a clôturé l'enregistrement pour ce séjour. Veuillez écrire à votre hôte.",
        "form_expired_title": "Ce formulaire a expiré",
        "form_expired_help": "Rien n'a été enregistré. Recommencez à partir du lien ci-dessous.",
        "rate_limited_title": "Trop de tentatives depuis votre connexion",
        "rate_limited_help": "Rien n'a été enregistré. Patientez environ 15 minutes et réessayez. En cas de blocage, écrivez à votre hôte.",
        "not_yours_title": "Ce formulaire ne peut pas être ouvert sur cet appareil",
        "not_yours_help": "Pour qu'aucun voyageur ne voie les données de passeport d'un autre, un formulaire ne peut être rouvert que sur l'appareil qui l'a rempli. Pour une correction, écrivez à votre hôte.",
        "already_filed_title": "Ces informations ont déjà été déclarées",
        "already_filed_help": "Pour des raisons d'exactitude juridique, une fiche déclarée ne peut pas être modifiée depuis ce formulaire. Écrivez à votre hôte si une correction est nécessaire.",
        "form_locked_title": "Ce formulaire est verrouillé",
        "form_locked_help": "Vos informations ont été enregistrées et signées. Pour les protéger, le formulaire ne peut pas être modifié depuis ce lien. Écrivez à votre hôte si une correction est nécessaire.",
        "form_locked_short": "Enregistré et verrouillé. Pour toute modification, contactez votre hôte.",
        "pin_title": "Saisissez le PIN d'accès",
        "pin_help": "Le PIN figure dans le message de votre hôte.",
        "pin_label": "PIN",
        "pin_submit": "Continuer",
        "pin_wrong": "Ce PIN est incorrect. Vérifiez le message de votre hôte.",
        "pin_recovery": "PIN introuvable ? Demandez à votre hôte de renvoyer le message d'enregistrement.",
        "pin_rate_limited": "Trop de PIN incorrects. Patientez environ 15 minutes et réessayez.",
        "pin_locked_out": "Trop de PIN incorrects : ce lien est suspendu pendant une journée. Demandez un nouveau PIN à votre hôte.",
        "security_check_failed": "Effectuez la vérification de sécurité et réessayez.",
        "start_over": "Recommencer",
        "night_one": "%(n)s nuit",
        "nights_few": "%(n)s nuits",
        "nights_many": "%(n)s nuits",
        "arrive": "Arrivée",
        "depart": "Départ",
        "select": "C'est mon séjour",
        "party_question": "Combien de personnes séjournent ?",
        "party_help": "Comptez tout le monde, enfants compris. Chaque personne a besoin de son propre formulaire.",
        "party_confirm": "Continuer",
        "people_progress": "Enregistrés : %(done)s sur %(total)s",
        "person_progress": "Personne %(current)s sur %(total)s",
        "stay_label": "Votre séjour",
        "steps_label": "Progression de l'enregistrement",
        "step_done": "Terminé",
        "form_step_progress": "Étape %(current)s sur %(total)s",
        "form_step_progress_title": "%(progress)s · %(title)s",
        "next_step": "Continuer",
        "previous_step": "Retour",
        "add_person": "Ajouter une personne",
        "add_first_person": "Commencez par vos propres informations",
        "saved_title": "Enregistré, merci",
        "saved_body": "Vos informations sont enregistrées. Ajoutez maintenant la personne suivante de votre groupe.",
        "reported_title": "Informations envoyées et déclarées",
        "reported_body": "Merci. Votre hôte a déjà déclaré cette fiche. Contactez-le si une information ci-dessous doit être corrigée.",
        "summary_title": "Votre envoi",
        "summary_fold_saved": "enregistré ✓",
        "your_details": "Vos informations",
        "person": "Personne",
        "you": "vous",
        "completed": "rempli",
        "not_filled": "non rempli",
        "edit": "Modifier",
        "all_done_title": "Merci. Tout le monde est enregistré",
        "all_done_body": "Vous n'avez plus rien à faire. Vous pouvez fermer cette page.",
        "all_done_receipt": "Nous avons envoyé une confirmation à %(email)s.",
        "checkin_info": "Arrivée",
        "checkout_info": "Départ",
        "still_missing": "Reste à enregistrer : %(n)s",
        "add_another": "Ajouter une autre personne",
        "someone_missing": "Vous avez oublié quelqu'un ? Les enfants doivent aussi être enregistrés.",
        "continue_filling": "Continuer à remplir",
        "surname": "Nom",
        "first_name": "Prénom(s)",
        "birth_date": "Date de naissance",
        "birth_date_readback": "Soit le %(date)s.",
        "residence_help": "Votre adresse de domicile permanent, comme sur votre passeport ou carte d'identité.",
        "residence_copied": "Copiée depuis %(name)s. Modifiez-la si cette personne habite ailleurs.",
        "nationality": "Nationalité",
        "countries_common": "Les plus courants",
        "countries_all": "Tous les pays",
        "doc_number": "N° du document de voyage",
        "doc_number_help": "Numéro de passeport, ou de carte d'identité pour les citoyens de l'UE uniquement.",
        "invoice_mail_issued_subject": "Facture %(number)s",
        "invoice_mail_issued_subject_stay": "Facture %(number)s – %(stay_property)s",
        "invoice_mail_issued_intro": "Votre facture de %(property)s est prête à être téléchargée.",
        "invoice_mail_issued_button": "Télécharger la facture",
        "mail_invoice_title": "Facture",
        "mail_invoice_number": "Numéro",
        "mail_invoice_total": "Total",
        "mail_invoice_property": "Hébergement",
        "visa_number": "Numéro de visa",
        "visa_help": "Uniquement si un visa tchèque ou Schengen vous a été délivré.",
        "residence_title": "Adresse de domicile permanent",
        "res_street": "Rue et numéro",
        "res_city": "Ville",
        "res_country": "Pays",
        "purpose": "Motif du séjour",
        "stay_dates": "Vos dates",
        "child_title": "Cette personne est un enfant inscrit sur le passeport d'un parent",
        "child_help": "Cochez uniquement si l'enfant n'a pas son propre passeport. Nous aurons alors besoin du numéro de document du parent.",
        "parent_doc": "N° de document du parent",
        "note": "Remarque",
        "signature": "Signature",
        "signature_help": "Signez avec le doigt ou la souris. La loi tchèque l'exige.",
        "signature_clear": "Effacer",
        "signature_missing": "Veuillez signer dans le cadre avant de continuer.",
        "signature_kept": "Votre signature est enregistrée. Ne signez à nouveau que si vous souhaitez la modifier.",
        "passport_photo_title": "Passeport ou pièce d'identité",
        "passport_photo_help": "Photographiez la page comportant votre photo, ou téléversez un PDF. Seul votre hôte peut le voir, et il est supprimé après sa vérification.",
        "passport_photo_label": "Passeport ou pièce d'identité",
        "passport_photo_take": "Prendre une photo",
        "passport_photo_choose": "Choisir un fichier",
        "passport_photo_retake": "Reprendre ou en choisir un autre",
        "passport_photo_selected": "Sélectionné : %(name)s",
        "passport_photo_pending_nat": "Choisissez d'abord votre nationalité à l'étape 1.",
        "passport_photo_not_required": "Les citoyens tchèques ne téléversent pas de photo de passeport dans ce formulaire.",
        "passport_photo_hint": "Une photo JPEG, PNG ou WebP jusqu'à 5 Mo, ou un PDF jusqu'à 15 Mo.",
        "passport_photo_too_large_image": "La photo est trop volumineuse. Utilisez un fichier de moins de 5 Mo.",
        "passport_photo_too_large_pdf": "Le PDF est trop volumineux. Utilisez un fichier de moins de 15 Mo.",
        "passport_photo_bad_type": "Utilisez une photo JPEG, PNG ou WebP, ou un formulaire d'enregistrement en PDF.",
        "passport_photo_missing": "Veuillez téléverser une photo de votre passeport ou de votre carte d'identité.",
        "review_title": "Vérifiez avant d'envoyer",
        "review_help": "Après l'envoi, ces informations sont verrouillées et seul votre hôte peut les modifier.",
        "review_edit": "Modifier",
        "legal_notice_title": "Informations légales",
        "legal_notice_duty_title": "Votre obligation légale",
        "legal_notice_duty_body": "Toutes les personnes qui séjournent doivent être enregistrées. Les voyageurs étrangers sont déclarés à la police des étrangers ; les citoyens tchèques sont seulement inscrits au registre d'hébergement.",
        "legal_notice_accuracy_title": "Informations exactes uniquement",
        "legal_notice_accuracy_body": "Saisissez tout exactement comme sur votre passeport ou votre carte d'identité. Vos informations peuvent être déclarées automatiquement, avant que votre hôte ne les vérifie, et des informations fausses peuvent valoir une amende à votre hôte.",
        "legal_notice_passport_title": "Photo du passeport (ressortissants étrangers)",
        "legal_notice_passport_body": "Les voyageurs étrangers téléversent une photo de la page d'identité de leur passeport ou de leur carte d'identité (ou un PDF). Seul votre hôte la voit, pour la comparer avec ce que vous avez saisi. Elle est supprimée après la vérification, sinon 7 jours après l'arrivée, et jamais plus de 30 jours après le téléversement. Elle n'est jamais transmise à la police.",
        "legal_notice_reporting_title": "Déclaration à la police et registre",
        "legal_notice_reporting_body": "Votre hôte déclare les informations des voyageurs étrangers à la police des étrangers dans un délai de trois jours ouvrables suivant l'arrivée, immédiatement ou un peu plus tard. Les fiches complètes peuvent être transmises automatiquement. Les mêmes informations restent dans le registre d'hébergement pendant six ans.",
        "legal_notice_retention_title": "Durée de conservation des données",
        "legal_notice_retention_body": "Les informations d'enregistrement et votre signature sont conservées pendant six ans après la fin de votre séjour, conformément au § 101, al. 4, de la loi n° 326/1999 Rec., puis supprimées. Le traitement repose sur une obligation légale (article 6, paragraphe 1, point c), du RGPD), et non sur le consentement.",
        "legal_notice_refusal_title": "En cas de refus",
        "legal_notice_refusal_body": "Vous devez présenter un document de voyage valide pour vérification. Si vous refusez de fournir des informations exactes, de signer ou de permettre la vérification de votre identité, l'hôte peut légalement refuser l'hébergement.",
        "legal_ack_label": "Mes informations sont exactes et j'ai lu les informations ci-dessus ainsi que la politique de confidentialité.",
        "legal_ack_missing": "Veuillez confirmer avoir lu les informations légales.",
        "submit": "Envoyer mes informations",
        "optional": "facultatif",
        "required": "obligatoire",
        "check_in": "Arrivée",
        "check_out": "Départ",
        "privacy": "Utilisées uniquement pour la déclaration légale de votre hôte à la police tchèque, et conservées pendant six ans.",
        "skip_to_form": "Aller au formulaire",
        "loading": "Chargement…",
        "privacy_link": "Traitement de vos données",
        "privacy_first_line": "UbyHost ne collecte que ce qu'exigent la loi tchèque et votre enregistrement, et n'utilise pas de cookies de suivi.",
        "privacy_title": "Politique de confidentialité",
        "privacy_intro": "Ce que deviennent les informations que vous saisissez, conformément aux articles 13 et 14 du RGPD.",
        "notice_version": "Politique de confidentialité, version %(version)s",
        "privacy_controller": "Votre responsable du traitement",
        "privacy_controller_body": "Cette personne morale détermine les finalités et les moyens du traitement de vos données de voyageur et répond de vos droits au titre du RGPD. Un nom différent pour le contact de séjour ci-dessous ne modifie pas ce rôle.",
        "privacy_controller_missing": "Votre hôte doit identifier l'entreprise responsable de vos données. Si elles manquent ici, demandez-lui sa dénomination sociale et son adresse.",
        "privacy_stay_contact": "Questions sur votre séjour",
        "privacy_stay_contact_body": "Le gestionnaire du logement est votre interlocuteur pratique pour l'arrivée, l'hébergement et la réservation. Pour les demandes d'accès, de rectification, d'effacement ou d'opposition, contactez le responsable du traitement ci-dessus.",
        "privacy_purpose": "Pourquoi les données sont collectées",
        "privacy_purpose_body": "Pour remplir deux obligations légales d'un hébergeur en Tchéquie : déclarer les ressortissants étrangers hébergés à la police des étrangers et tenir un registre d'hébergement (domovní kniha). Elles ne sont utilisées à aucune autre fin.",
        "privacy_basis": "Base juridique",
        "privacy_basis_body": "Article 6, paragraphe 1, point c), du RGPD : respect d'une obligation légale, à savoir les §§ 101–103 de la loi n° 326/1999 Rec. relative au séjour des étrangers. Votre consentement n'est pas demandé, car l'obligation s'applique que vous l'acceptiez ou non.",
        "privacy_data": "Données collectées",
        "privacy_data_body": "Prénom et nom, date de naissance, nationalité, numéro du document de voyage, numéro de visa s'il en a été délivré un, adresse de domicile permanent à l'étranger, motif du séjour, début et fin de votre séjour, signature, nombre de personnes déclaré et adresse e-mail utilisée pour revendiquer la réservation. Le nombre de personnes sert à déterminer si tous les formulaires attendus sont complets et est conservé avec la fiche du séjour.",
        "privacy_data_body_no_email": "Prénom et nom, date de naissance, nationalité, numéro du document de voyage, numéro de visa s'il en a été délivré un, adresse de domicile permanent à l'étranger, motif du séjour, début et fin de votre séjour, signature et nombre de personnes déclaré. Cette version du formulaire ne collecte pas votre adresse e-mail. Le nombre de personnes sert à déterminer si tous les formulaires attendus sont complets et est conservé avec la fiche du séjour.",
        "privacy_email_title": "E-mails et masquage",
        "privacy_email_body": "Votre e-mail sécurise la réservation et sert à envoyer le lien privé vers le formulaire, un rappel la veille si les formulaires déclarés restent incomplets, et un récapitulatif une fois l'enregistrement terminé. Le gestionnaire du logement reçoit une copie de ce récapitulatif. L'adresse complète est accessible au responsable du traitement configuré et, le cas échéant, au prestataire d'envoi ; les écrans publics destinés aux voyageurs n'affichent qu'une adresse masquée. Elle n'est pas utilisée à des fins marketing.",
        "privacy_cookies_title": "Cookies nécessaires",
        "privacy.cookies.table_intro": "Le tableau ci-dessous liste chaque cookie et chaque élément de stockage local que le service définit.",
        "cookies.table.name": "Nom",
        "cookies.table.party": "Défini par",
        "cookies.table.purpose": "Finalité",
        "cookies.table.lifetime": "Durée",
        "cookies.party.first": "UbyHost",
        "privacy_cookies_body": "UbyHost n'utilise que des cookies nécessaires pour les voyageurs : accès par PIN pendant 7 jours maximum, ainsi que la langue et les formulaires envoyés depuis cet appareil pendant 60 jours maximum. Lorsque la revendication par e-mail est activée, l'accès à la réservation confirmée est également mémorisé pendant 60 jours maximum. Ils empêchent un autre voyageur de voir ou de modifier votre formulaire et assurent le bon fonctionnement du parcours. Cloudflare peut définir des identifiants de sécurité lorsque Turnstile ou la protection anti-bots est déclenché. Il n'y a aucun cookie publicitaire ni de mesure d'audience.",
        "privacy_passport_photo_title": "Photo ou PDF temporaire du passeport",
        "privacy_passport_photo_body": "Si vous n'êtes pas citoyen tchèque, vous pouvez téléverser une photo de la page d'identité de votre passeport ou de votre carte d'identité, ou un formulaire d'enregistrement en PDF, afin que l'hôte puisse vérifier vos informations. Le fichier est traité uniquement pour cette vérification et l'accès dans l'application est limité aux utilisateurs autorisés de l'hôte. Il est supprimé après la vérification ; s'il n'est pas vérifié, il est supprimé 7 jours après l'arrivée, et jamais plus de 30 jours après le téléversement. Un accès restreint de l'opérateur ou de l'infrastructure peut être nécessaire pour faire fonctionner et sécuriser le service. Il n'est pas transmis à la police.",
        "privacy_recipients": "Destinataires",
        "privacy_recipients_body": "La Police de la République tchèque, Direction de la police des étrangers, et tout agent contrôlant le registre d'hébergement ; votre hébergeur ; UbyHost en tant que sous-traitant ; et un prestataire d'envoi d'e-mails lorsque la messagerie est activée. Les données ne sont jamais vendues, renvoyées au site de réservation ni utilisées à des fins marketing.",
        "privacy_recipients_body_no_email": "La Police de la République tchèque, Direction de la police des étrangers, tout agent contrôlant le registre d'hébergement, votre hébergeur et UbyHost en tant que sous-traitant. Les données ne sont jamais vendues, renvoyées au site de réservation ni utilisées à des fins marketing.",
        "privacy_bot_protection_title": "Protection du lien d'enregistrement",
        "privacy_bot_protection_body": "Si quelqu'un saisit à plusieurs reprises un PIN d'accès erroné, le formulaire peut afficher Cloudflare Turnstile pour bloquer les abus automatisés. Les pages de production peuvent également être protégées par Cloudflare contre les abus automatisés. Ces contrôles peuvent traiter des données techniques de connexion (comme l'adresse IP) conformément à la politique de confidentialité de Cloudflare. Ils ne sont pas utilisés à des fins marketing.",
        "privacy_processor": "Qui exploite ce site",
        "privacy_processor_body": "Le logiciel UbyHost est exploité par %(name)s, IČO %(ico)s, %(address)s, qui traite les données uniquement sur instruction du responsable du traitement configuré, pour faire fonctionner le formulaire d'enregistrement, les messages transactionnels et les fiches conservées. Les questions sur votre séjour s'adressent à votre hôte, tandis que les demandes relatives à vos droits sur vos données personnelles s'adressent au responsable du traitement indiqué ci-dessus.",
        "privacy_retention": "Durée de conservation",
        "privacy_retention_body": "Les informations d'enregistrement du registre d'hébergement et les signatures sont conservées pendant six ans après la fin du séjour, comme l'exige le § 101, puis supprimées. L'e-mail de revendication reste associé tant que la fiche de réservation est conservée, sauf si l'hôte libère la revendication. Les journaux d'envoi des messages, réussis ou échoués, sont normalement supprimés après 14 jours ; des copies de sauvegarde limitées peuvent subsister jusqu'à la fin de leur cycle de conservation.",
        "privacy_retention_body_no_email": "Les informations d'enregistrement du registre d'hébergement et les signatures sont conservées pendant six ans après la fin du séjour, comme l'exige le § 101, puis supprimées. Des copies de sauvegarde limitées peuvent subsister jusqu'à la fin de leur cycle de conservation.",
        "privacy_rights": "Vos droits",
        "privacy_rights_body": "Vous pouvez demander une copie de vos données, faire rectifier toute donnée inexacte et demander comment elles sont traitées. L'effacement et l'opposition sont limités tant que dure l'obligation légale de conserver la fiche. Il n'y a ni prise de décision automatisée ni profilage.",
        "privacy_complaint": "Si vous estimez que vos données sont traitées de manière incorrecte, vous pouvez introduire une réclamation auprès de l'autorité tchèque de protection des données : Úřad pro ochranu osobních údajů, Pplk. Sochora 27, 170 00 Praha 7, uoou.gov.cz.",
        "privacy_required": "La fourniture de ces informations est une exigence légale, et non une initiative de l'hôte. Sans elles, l'hôte ne peut pas légalement vous héberger.",
        "privacy_contact": "Contact",
        "fix_errors": "Veuillez corriger les points suivants :",
        "back": "Retour",
        "mail_claim_subject": "Confirmez votre séjour à %(property)s (lien valable 30 min)",
        "mail_claim_resend_subject": "Nouveau lien : confirmez votre séjour à %(property)s",
        "mail_claim_preheader": "Touchez le bouton, puis remplissez chaque voyageur (environ 2 minutes par personne).",
        "mail_claim_resend_preheader": "Votre lien précédent ne fonctionne plus. En voici un nouveau.",
        "mail_claim_heading": "Confirmez votre séjour",
        "mail_claim_resend_heading": "Voici votre nouveau lien",
        "mail_claim_intro": "Confirmez votre séjour à %(property)s (%(dates)s) en ouvrant le lien ci-dessous.",
        "mail_claim_action": "Confirmer mon séjour",
        "mail_link_fallback": "Si le bouton ne fonctionne pas, copiez cette adresse dans votre navigateur :",
        "mail_claim_expiry": "Le bouton fonctionne pendant 30 minutes. Après confirmation, ce téléphone ou cet ordinateur mémorise votre séjour. Vous n'aurez plus besoin du lien sur cet appareil.",
        "mail_claim_expiry_resend": "Ce nouveau lien remplace le précédent et fonctionne pendant 30 minutes.",
        "mail_claim_next_label": "La suite",
        "mail_claim_next_body": "Vous saisirez les informations de chaque voyageur de ce séjour, puis signerez. Cela prend environ deux minutes par voyageur et fonctionne sur téléphone. Si un PIN vous est demandé, utilisez celui du message de votre hôte.",
        "mail_claim_next_done": "Tout le monde est déjà enregistré. Le lien ouvre simplement la page de votre séjour.",
        "mail_completion_subject": "Vous êtes enregistré pour %(property)s : rien d'autre à faire",
        "mail_completion_preheader": "Tous les voyageurs de ce séjour sont enregistrés. Rien d'autre à faire.",
        "mail_completion_heading": "Tout est en ordre",
        "mail_completion_intro": "Tous les voyageurs pour %(property)s (%(dates)s) sont enregistrés. Vous n'avez plus rien à faire.",
        "mail_completion_action": "Voir la page du séjour",
        "mail_completion_note": "Votre hôte se charge de la déclaration officielle auprès des autorités. Cet e-mail est votre récapitulatif, et non une confirmation officielle.",
        "mail_reminder_guest_subject": "Demain à %(property)s : %(filled)s voyageurs sur %(expected)s enregistrés",
        "mail_reminder_guest_subject_no_count": "Demain à %(property)s : l'enregistrement des voyageurs n'est pas terminé",
        "mail_reminder_guest_preheader": "Votre séjour commence demain et l'enregistrement n'est pas complet.",
        "mail_reminder_guest_heading": "Votre séjour commence demain",
        "mail_reminder_guest_intro": "Encore %(missing)s voyageur(s) doivent remplir le formulaire avant votre arrivée.",
        "mail_reminder_guest_intro_no_count": "Votre séjour à %(property)s commence demain et l'enregistrement des voyageurs n'est pas encore complet.",
        "mail_reminder_guest_action": "Terminer l'enregistrement",
        "mail_reminder_guest_note_label": "Un seul rappel",
        "mail_reminder_guest_note": "C'est le seul rappel d'enregistrement incomplet que nous enverrons.",
        "mail_reminder_guest_device": "Ouvrez-le sur le téléphone ou l'ordinateur où vous avez commencé. Sur un autre appareil, le PIN de votre hôte vous sera demandé.",
        "mail_guest_footer_about": "UbyHost est le service d'enregistrement des voyageurs utilisé par votre hôte.",
        "mail_guest_footer_why": "Vous recevez cet e-mail car votre séjour à %(property)s est enregistré avec cette adresse.",
        "mail_property_fallback": "votre hébergement",
        "mail_guest_footer_host_label": "Votre hôte",
        "mail_guest_footer_help": "Répondez à cet e-mail pour joindre votre hôte.",
        "server_error_title": "Une erreur s'est produite de notre côté",
        "server_error_help": "Les informations déjà enregistrées sont en sécurité. Patientez un instant, puis rechargez la page ou rouvrez votre lien.",
        "door_code_title": "Votre code de porte",
        "door_code_times": "Arrivée à partir de %(checkin)s. Départ avant %(checkout)s.",
        "door_code_first_use": "Le code fonctionne de l'arrivée au départ. Si vous ne l'avez pas utilisé avant le %(deadline)s, il ne fonctionnera plus. Demandez alors un nouveau code à votre hôte.",
        "door_code_sent": "Nous l'avons aussi envoyé à %(email)s.",
        "door_code_preparing": "Vous recevrez votre code de porte par e-mail.",
        "door_code_failed": "Votre hôte vous enverra le code de porte.",
        "mail_door_code_subject": "Votre code de porte pour %(property)s",
        "privacy_door_code_title": "Code de porte",
        "privacy_door_code_body": "Cet hébergement vous donne un code de porte dès que tous les voyageurs sont enregistrés, pour que vous puissiez entrer pendant votre séjour. Le code est créé via TTLock, un service de Hangzhou Sciener Intelligent Control Technology Co., Ltd. (Chine), qui reçoit la serrure, le code, ses horaires de validité et un numéro de référence, mais ni votre nom ni vos coordonnées. Le code s'affiche sur la page de votre séjour et est envoyé à l'adresse e-mail utilisée pour l'enregistrement, avec une copie à l'hôte. Il est conservé chiffré et supprimé un jour après son expiration. La base légale est votre contrat d'hébergement (art. 6, paragraphe 1, point b, du RGPD). La serrure enregistre l'utilisation du code et l'hôte le voit dans son application TTLock.",

    },
}


def translator(lang: str):
    table = STRINGS[normalise_language(lang)]
    fallback = STRINGS[DEFAULT_LANGUAGE]

    def translate(key: str, **kwargs) -> str:
        return host_i18n.lookup(table, fallback, key, **kwargs)

    return translate
