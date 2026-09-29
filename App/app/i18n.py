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
        "date_placeholder": "DD.MM.YYYY",
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
            "If your host requires it, foreign guests upload a photo of their passport or ID "
            "page so the host can check the details. Only your host sees it, and it is deleted "
            "after the check."
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
        "arrival_welcome": "Welcome — guest registration for %(facility)s.",
        "arrival_question": "Which stay is yours?",
        "arrival_help": "Choose your arrival and departure dates to continue.",
        "arrival_cta": "That’s my stay",
        # Ticket Wallet skin (guest-ticket.css)
        "tw_label_access": "Private access",
        "tw_label_stay": "Step 1 · Your stay",
        "tw_label_email": "Step 1 · Your e-mail",
        "tw_label_confirm": "Step 1 · Confirm",
        "tw_label_group": "Step 2 · Your group",
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
        "tw_purpose_other": "Other…",
        "tw_sign_here": "Sign here with your finger",
        "tw_signed": "Signed",
        "tw_done_keep": "Keep this page — it is your confirmation.",
        "stay_ongoing": "Ongoing",
        "stay_arriving_today": "Arriving today",
        "host_details": "Your host",
        "host_details_help": (
            "If there is any problem, feel free to contact your host. "
            "UbyHost does not run the property and cannot change your booking."
        ),
        "host_details_missing": (
            "Use the phone or e-mail in the message that contained this link."
        ),
        "message_from_host": "A message from your host",
        "claim_title": "How many people, and your e-mail",
        "claim_help": (
            "We'll e-mail you a private link so only your group can open the forms."
        ),
        "claim_email": "What is your e-mail address?",
        "claim_email_help": (
            "We send the link here, one reminder the day before arrival if forms are "
            "missing, and a receipt (your host gets a copy). Elsewhere it is shown "
            "masked. No marketing."
        ),
        "claim_cookie_help": (
            "Only necessary cookies: PIN access (7 days), your language and this stay "
            "(60 days)."
        ),
        "claim_submit": "Send me the form link",
        "claim_sent_title": "Check your e-mail",
        "claim_sent_body": (
            "We sent a link to %(email)s. Open it on this phone to continue — it works "
            "for 30 minutes. If it asks for the PIN again, enter the same PIN."
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
        "assigned_body": (
            "This stay is already linked to the e-mail below. "
            "If that's you, we can send the private link again."
        ),
        "assigned_resend_help": "Enter the same e-mail to receive the link again.",
        "assigned_resend": "Send me the link again",
        "assigned_stay_label": "Your selected stay",
        "assigned_private_link": "For your privacy, registration continues through the secure link sent to this address.",
        "assigned_last_sent": "Private link last sent %(date)s",
        "assigned_not_mine": "This is not my reservation",
        "claim_confirm_title": "Is this your reservation?",
        "claim_confirm_help": "One tap to confirm it’s really you.",
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
            "Registration opens a few days before arrival. Come back to this same link then. "
            "Already arrived? Message your host — they can send you a direct link to your stay."
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
        "form_locked_short": "Saved and locked. To change anything, contact your host.",
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
        "saved_title": "Saved — thank you",
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
        "all_done_title": "Thank you — everyone is registered",
        "all_done_body": (
            "There is nothing more you need to do. You can close this page."
        ),
        "all_done_receipt": "We have sent a confirmation to %(email)s.",
        "checkin_info": "Check-in",
        "checkout_info": "Check-out",
        "still_missing": "Still to register: %(n)s",
        "add_another": "Add another person",
        "someone_missing": (
            "Forgot someone? Everyone staying must be registered, including children."
        ),
        "continue_filling": "Continue filling in",
        "surname": "Surname",
        "first_name": "Given name(s)",
        "birth_date": "Date of birth",
        "birth_date_help": "Day, month, year — e.g. 04.07.1990 for 4 July 1990. Dots are added for you.",
        "birth_date_readback": "That is %(date)s.",
        "residence_help": "Your permanent home address, as in your passport or ID card. Required by law.",
        "residence_copied": "Copied from %(name)s — change it if this person lives elsewhere.",
        "nationality": "Nationality",
        "countries_common": "Most common",
        "countries_all": "All countries",
        "doc_number": "Travel document number",
        "doc_number_help": "Passport or ID card number.",
        "invoice_mail_issued_subject": "Invoice %(number)s",
        "invoice_mail_issued_intro": "Your invoice from %(property)s is ready to download.",
        "invoice_mail_issued_button": "Download invoice",
        "mail_invoice_title": "Invoice",
        "mail_invoice_number": "Number",
        "mail_invoice_total": "Total",
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
        "passport_photo_help": (
            "Your host must check your details against your document. Take a photo of the page "
            "with your photo, or upload a PDF. Only your host can see it, and it is deleted after "
            "they check it."
        ),
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
        "legal_notice_intro": "Please read this before you send.",
        "legal_notice_disclaimer": (
            "UbyHost is a software tool and this information does not replace legal advice."
        ),
        "legal_notice_duty_title": "Your legal duty",
        "legal_notice_duty_body": (
            "Everyone staying must be registered. Foreign guests are reported to the Foreign "
            "Police within three working days; Czech citizens only go into the house book. "
            "This is required by law."
        ),
        "legal_notice_accuracy_title": "Accurate information only",
        "legal_notice_accuracy_body": (
            "Enter everything exactly as in your passport or ID card. Your details may be "
            "reported automatically, before your host checks them, and false details can mean "
            "a fine for your host."
        ),
        "legal_notice_passport_title": "Passport photo (foreign nationals)",
        "legal_notice_passport_body": (
            "Foreign guests upload a photo of their passport or ID page (or a PDF). Only your host "
            "sees it, to compare it with what you entered. It is deleted after the check, or "
            "automatically after your stay. It is never sent to the police."
        ),
        "legal_notice_reporting_title": "Police reporting and house book",
        "legal_notice_reporting_body": (
            "Complete records of foreign guests may be sent to the Czech Police automatically — "
            "straight away or after a delay your host chooses. The same details stay in the house "
            "book for six years."
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
            "My details are correct, and I have read the information above and the privacy "
            "notice."
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
        "loading": "Loading…",
        "privacy_link": "How your data is handled",
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
            "House-book registration details and signatures are kept for six years from the last "
            "entry, as § 101 requires. The claim e-mail remains linked while the reservation record "
            "is retained unless the host releases the claim. Completed or failed message-delivery "
            "records are normally deleted after 14 days; limited backup "
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
        "mail_claim_subject": "Confirm your stay at %(property)s (link valid 30 min)",
        "mail_claim_resend_subject": "New link: confirm your stay at %(property)s",
        "mail_claim_preheader": (
            "Tap the button, then fill in each guest — about 2 minutes per person."
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
            "The button works for 30 minutes. After you confirm, this phone or "
            "computer remembers your stay — you won't need the link again on it."
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
            "Everyone is already registered — the link just opens your stay page."
        ),
        "mail_completion_subject": (
            "You're registered for %(property)s — nothing else to do"
        ),
        "mail_completion_preheader": (
            "Everyone on this stay is registered — nothing else to do."
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
    },
    "cs": {
        "title": "Registrace ubytovaného",
        "language_label": "Jazyk",
        "date_placeholder": "DD.MM.RRRR",
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
            "Stejné údaje se zapisují do domovní knihy, kterou hostitel uchovává 6 let a "
            "předkládá při kontrole policie."
        ),
        "why_point_czech": (
            "Občané ČR se policii neoznamují — provede se pouze zápis do domovní knihy."
        ),
        "why_point_passport": (
            "Pokud to hostitel vyžaduje, cizinci nahrají fotku stránky pasu nebo průkazu, "
            "aby mohl údaje zkontrolovat. Vidí ji jen hostitel a po kontrole se smaže."
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
        "arrival_welcome": "Vítejte — registrace ubytovaného pro %(facility)s.",
        "arrival_question": "Který pobyt je váš?",
        "arrival_help": "Vyberte termín příjezdu a odjezdu a pokračujte.",
        "arrival_cta": "To je můj pobyt",
        # Ticket Wallet skin (guest-ticket.css)
        "tw_label_access": "Soukromý přístup",
        "tw_label_stay": "Krok 1 · Váš pobyt",
        "tw_label_email": "Krok 1 · Váš e-mail",
        "tw_label_confirm": "Krok 1 · Potvrzení",
        "tw_label_group": "Krok 2 · Vaše skupina",
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
        "tw_purpose_other": "Jiný…",
        "tw_sign_here": "Podepište se zde prstem",
        "tw_signed": "Podepsáno",
        "tw_done_keep": "Tuto stránku si nechte — je to vaše potvrzení.",
        "stay_ongoing": "Právě probíhá",
        "stay_arriving_today": "Příjezd dnes",
        "host_details": "Váš hostitel",
        "host_details_help": (
            "Pokud máte jakýkoli problém, neváhejte kontaktovat svého hostitele. "
            "UbyHost objekt neprovozuje a rezervaci nemůže měnit."
        ),
        "host_details_missing": (
            "Použijte telefon nebo e-mail ze zprávy, ve které byl tento odkaz."
        ),
        "message_from_host": "Zpráva od vašeho hostitele",
        "claim_title": "Počet osob a váš e-mail",
        "claim_help": (
            "Pošleme vám soukromý odkaz, aby formuláře otevřela jen vaše skupina."
        ),
        "claim_email": "Jaký je váš e-mail?",
        "claim_email_help": (
            "Pošleme sem odkaz, jedno připomenutí den před příjezdem, pokud formuláře "
            "chybí, a potvrzení (kopii dostane i hostitel). Jinde se adresa zobrazuje "
            "zakrytě. Žádný marketing."
        ),
        "claim_cookie_help": (
            "Jen nezbytné cookies: přístup přes PIN (7 dní), jazyk a tento pobyt (60 dní)."
        ),
        "claim_submit": "Pošlete mi odkaz na formulář",
        "claim_sent_title": "Zkontrolujte e-mail",
        "claim_sent_body": (
            "Poslali jsme odkaz na %(email)s. Otevřete ho v tomto telefonu a pokračujte — "
            "platí 30 minut. Pokud se znovu zeptá na PIN, zadejte stejný."
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
        "assigned_body": (
            "Tento pobyt je už propojený s e-mailem níže. "
            "Pokud jste to vy, pošleme vám soukromý odkaz znovu."
        ),
        "assigned_resend_help": "Zadejte stejný e-mail a odkaz pošleme znovu.",
        "assigned_resend": "Pošlete mi odkaz znovu",
        "assigned_stay_label": "Vybraný pobyt",
        "assigned_private_link": "Kvůli ochraně soukromí pokračuje registrace přes zabezpečený odkaz zaslaný na tuto adresu.",
        "assigned_last_sent": "Soukromý odkaz naposledy odeslán %(date)s",
        "assigned_not_mine": "Toto není moje rezervace",
        "claim_confirm_title": "Je to vaše rezervace?",
        "claim_confirm_help": "Jedním klepnutím potvrďte, že jste to opravdu vy.",
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
            "Nic se neuložilo. Počkejte asi 15 minut a zkuste to znovu — pokud se "
            "zaseknete, napište hostiteli."
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
        "pin_help": (
            "Hostitel vám spolu s odkazem poslal PIN. "
            "Zadejte ho pro otevření formuláře."
        ),
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
        "saved_title": "Uloženo — děkujeme",
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
        "all_done_title": "Děkujeme — všichni jsou zaregistrovaní",
        "all_done_body": "Nic dalšího už dělat nemusíte. Stránku můžete zavřít.",
        "all_done_receipt": "Potvrzení jsme poslali na %(email)s.",
        "checkin_info": "Příjezd",
        "checkout_info": "Odjezd",
        "still_missing": "Zbývá zaregistrovat: %(n)s",
        "add_another": "Přidat další osobu",
        "someone_missing": (
            "Zapomněli jste na někoho? Registrovat se musí každý ubytovaný, včetně dětí."
        ),
        "continue_filling": "Pokračovat ve vyplnění",
        "surname": "Příjmení",
        "first_name": "Jméno",
        "birth_date": "Datum narození",
        "birth_date_help": "Den, měsíc, rok — např. 04.07.1990 pro 4. července 1990. Tečky se doplní samy.",
        "birth_date_readback": "Tedy %(date)s.",
        "residence_help": "Adresa trvalého bydliště podle pasu nebo občanského průkazu. Vyžaduje ji zákon.",
        "residence_copied": "Převzato od: %(name)s. Pokud tato osoba bydlí jinde, adresu změňte.",
        "nationality": "Státní občanství",
        "countries_common": "Nejčastější",
        "countries_all": "Všechny státy",
        "doc_number": "Číslo cestovního dokladu",
        "doc_number_help": "Číslo pasu nebo občanského průkazu.",
        "invoice_mail_issued_subject": "Faktura %(number)s",
        "invoice_mail_issued_intro": "Vaše faktura za %(property)s je připravena ke stažení.",
        "invoice_mail_issued_button": "Stáhnout fakturu",
        "mail_invoice_title": "Faktura",
        "mail_invoice_number": "Číslo",
        "mail_invoice_total": "Celkem",
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
        "passport_photo_help": (
            "Hostitel musí vaše údaje porovnat s dokladem. Vyfoťte stránku s fotografií, nebo "
            "nahrajte PDF. Uvidí ji jen hostitel a po kontrole se smaže."
        ),
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
        "legal_notice_intro": "Před odesláním si to prosím přečtěte.",
        "legal_notice_disclaimer": (
            "UbyHost je softwarový nástroj a tyto informace nenahrazují právní poradenství."
        ),
        "legal_notice_duty_title": "Vaše zákonná povinnost",
        "legal_notice_duty_body": (
            "Registrovat se musí každý ubytovaný. Cizince ubytovatel do tří pracovních dnů "
            "ohlásí cizinecké policii, občany ČR jen zapíše do domovní knihy. Vyžaduje to zákon."
        ),
        "legal_notice_accuracy_title": "Pouze pravdivé údaje",
        "legal_notice_accuracy_body": (
            "Vše vyplňte přesně podle pasu nebo občanského průkazu. Údaje se mohou ohlásit "
            "automaticky ještě předtím, než je ubytovatel zkontroluje, a za nepravdivé údaje "
            "hrozí ubytovateli pokuta."
        ),
        "legal_notice_passport_title": "Fotografie pasu (cizinci)",
        "legal_notice_passport_body": (
            "Cizinci nahrají fotku stránky pasu nebo průkazu (nebo PDF). Uvidí ji jen ubytovatel, "
            "aby ji porovnal s vyplněnými údaji. Po kontrole se smaže, jinak automaticky po "
            "skončení pobytu. Policii se nikdy neposílá."
        ),
        "legal_notice_reporting_title": "Hlášení policii a domovní kniha",
        "legal_notice_reporting_body": (
            "Kompletní záznamy cizinců se mohou Policii ČR odeslat automaticky — hned, nebo "
            "s odkladem, který nastaví ubytovatel. Stejné údaje zůstávají šest let v domovní "
            "knize."
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
            "Moje údaje jsou správné a přečetl(a) jsem si informace výše i zásady zpracování "
            "údajů."
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
        "loading": "Načítá se…",
        "privacy_link": "Jak nakládáme s vašimi údaji",
        "privacy_title": "Informace o zpracování osobních údajů",
        "privacy_intro": (
            "Co se děje s údaji, které vyplníte — podle článků 13 a 14 GDPR."
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
            "Registrační údaje domovní knihy a podpisy se uchovávají šest let od posledního zápisu "
            "podle § 101. E-mail k převzetí zůstává spojen s rezervací po dobu jejího uchování, "
            "pokud ubytovatel převzetí neuvolní. Dokončené či neúspěšné záznamy doručení "
            "se běžně mažou po 14 dnech; omezené zálohy mohou zůstat do konce cyklu."
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
    },
}


def translator(lang: str):
    table = STRINGS[host_i18n.normalise_language(lang)]
    fallback = STRINGS[DEFAULT_LANGUAGE]

    def translate(key: str, **kwargs) -> str:
        return host_i18n.lookup(table, fallback, key, **kwargs)

    return translate
