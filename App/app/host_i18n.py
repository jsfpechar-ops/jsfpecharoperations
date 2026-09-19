"""Host-facing UI strings in English and Czech."""
from __future__ import annotations

from typing import Dict

from fastapi import Request

from . import config
from .dpa_i18n import DPA_STRINGS
from .privacy_policy_i18n import PRIVACY_STRINGS
from .terms_i18n import TERMS_STRINGS

LANG_COOKIE = "ubyhost_lang"
LANG_COOKIE_MAX_AGE = 60 * 60 * 24 * 365
LANGUAGES = ("en", "cs")
DEFAULT_LANGUAGE = "en"
# Signed-out pages are what visitors and search engines see first, and UbyHost
# is built for Czech hosts, so they are Czech unless the visitor says otherwise.
PUBLIC_DEFAULT_LANGUAGE = "cs"

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
        "nav.automation": "Automation",
        "nav.guest_links": "Guest links",
        "nav.settings": "Settings",
        "nav.users": "Users",
        "nav.logout": "Log out",
        "nav.support": "Support",
        "nav.administrator": "Administrator",
        "login.page_title": "Log in · UbyHost",
        "login.meta_description": (
            "UbyHost brings calendars, guest forms, the house book and UbyPort reporting "
            "together for Czech short-term hosts. Log in to your account."
        ),
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
        "login.acceptance_before": "By logging in or using UbyHost, you agree to the ",
        "login.acceptance_and": " and ",
        "login.acceptance_between_terms_privacy": ", the ",
        "login.acceptance_between_privacy_legal": ", and the ",
        "login.acceptance_after": (
            ". If you do not agree, do not log in or use the Service."
        ),
        "login.hero_title": "Guest reporting, handled for you.",
        "login.hero_body": (
            "Calendars, guest forms, house book, and UbyPort submissions in one calm workspace — "
            "built for Czech short-term hosts."
        ),
        "onboarding.welcome_title": "Welcome to UbyHost",
        "onboarding.welcome_lede": (
            "Let's get your first property ready for guest reporting. Follow the steps "
            "below — most hosts finish in a few minutes."
        ),
        "onboarding.step_of": "Setup step %(n)s of %(total)s: %(title)s",
        "onboarding.step_done": "Done",
        "onboarding.continue": "Continue: %(action)s",
        "onboarding.entity.title": "Legal entity",
        "onboarding.entity.detail": "The company or sole trader registered in UbyPort.",
        "onboarding.entity.action": "Add legal entity",
        "onboarding.property.title": "Property",
        "onboarding.property.detail": "Each flat or house you rent out.",
        "onboarding.property.action": "Add property",
        "onboarding.calendars.title": "Calendar links",
        "onboarding.calendars.detail": (
            "Airbnb or Booking.com iCal URLs so stays appear automatically."
        ),
        "onboarding.calendars.action": "Connect calendars",
        "onboarding.automation.title": "Automation & UbyPort",
        "onboarding.automation.detail": (
            "Choose immediate-after-completion, delayed automatic, or manual sending; then add "
            "the web-service credentials and registration details exactly. UbyPort rejects a mismatch."
        ),
        "onboarding.automation.action": "Finish automation",
        "onboarding.guest_link.title": "Guest link",
        "onboarding.guest_link.detail": (
            "Review the PIN, optional host message, and e-mail/privacy behavior, "
            "then copy the link into every booking portal's check-in message."
        ),
        "onboarding.guest_link.action": "Copy guest link",
        "demo.load": "Explore with demo data",
        "demo.load_detail": (
            "One sample property with stays and guests. Nothing is sent to the police unless you "
            "submit real data yourself."
        ),
        "demo.clear": "Clear demo data",
        "data.export_csv_title": "Export CSV",
        "data.export_csv_help": "Choose the date range to include in the export.",
        "data.export_csv_download": "Download",
        "data.export_csv_cancel": "Cancel",
        "csv.export_stays": "Export stays (CSV)",
        "csv.download": "Export spreadsheet (CSV)",
        "csv.download_pdfs": "Download PDF bundle (inspection)",
        "reports.download_receipts": "Download Doručenky (ZIP)",
        "reports.download_receipts_hint": "One PDF per successful transmission, built on disk to stay lightweight.",
        "reports.title": "Reports",
        "reports.lede": "Every UbyPort transmission and its Doručenka, retained as proof.",
        "reports.when": "When",
        "reports.property": "Property",
        "reports.mode": "Mode",
        "reports.guests": "Guests",
        "reports.outcome": "Outcome",
        "reports.stamp": "Receipt stamp",
        "reports.open": "Open report %(id)s",
        "reports.receipt": "Doručenka",
        "reports.details": "View details",
        "reports.empty_title": "No reports yet",
        "reports.empty_body": "Completed guest records appear here after they are sent to UbyPort.",
        "reports.empty_action": "Open stays",
        "reports.detail.title": "Report #%(id)s",
        "reports.detail.back": "Back to reports",
        "reports.detail.endpoint": "Endpoint",
        "reports.detail.finished": "Finished",
        "reports.detail.transport_error": "Transport error",
        "reports.detail.header_problems": "Problems with the report header",
        "reports.detail.header_help": "Header errors come from the property settings, not the guest data.",
        "reports.detail.download_receipt": "Download the Doručenka",
        "reports.detail.download_errors": "Download the error report",
        "reports.detail.guests": "Guests in this transmission",
        "reports.detail.guest": "Guest",
        "reports.detail.result": "Result",
        "reports.detail.technical": "Technical details",
        "reports.detail.technical_help": "The exact computer messages exchanged with UbyPort. You normally only need these when support investigates a rejection.",
        "housebook.legal_title": "Your legal duty (house book)",
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
        "housebook.export_menu": "Export",
        "housebook.pdf_export_title": "Download PDF bundle",
        "housebook.pdf_export_help": (
            "Choose the stay dates and property to include. Each guest form is generated on the server "
            "one at a time — large ranges take longer and use more server capacity."
        ),
        "housebook.pdf_hint": (
            "Up to %(limit)s forms per download. Use a narrower date range if you have many entries."
        ),
        "housebook.legal_intro_title": "House book — your legal duty",
        "housebook.legal_intro_ack": "Got it — hide this next time",
        "housebook.legal_intro_skip": "Skip for now",
        "housebook.filter_footer": "Exports use the current filter.",
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
        "host.verify_help": "Optional: record that you checked the guest's document in person.",
        "host.verify_confirm": "I checked this guest's ID against the details above.",
        "host.verify_button": "Mark ID checked",
        "host.verify_pending": "ID not checked",
        "host.verify_view_photo": "View uploaded ID",
        "host.verify_footnote": "UbyHost does not collect a passport image.",
        "host.verify_waiting_photo": "No document check recorded — you can mark an in-person check.",
        "host.verify_done": "ID checked on",
        "host.verify_host_entry": (
            "When you enter a guest by hand you confirm the details against their document in "
            "person. The record is marked verified on save."
        ),
        "housebook.legal_footnote": (
            "You remain the data controller for guest data. Josef Pechar (UbyHost) is the technology "
            "provider only — not your accommodation business, not legal advice, and not liable for "
            "incorrect data you or guests enter or for how you use the software. Keep signed paper you "
            "already hold; a screen alone may not satisfy an inspection."
        ),
        "send.this_stay": "Send this stay",
        "send.all_ready": "Send all ready stays",
        "send.all_ready_hint": "Reports every stay that is complete and waiting for your approval",
        "send.filled_forms": "Send filled forms",
        "send.filled_forms_hint": "Submit every completed guest form on this stay to UbyPort",
        "send.guests_count": "Send %(count)s guest(s) on this stay",
        "status.ready_manual": "Ready — you send",
        "status.ready_manual_tip": "Guest forms are complete. Click Send because this property uses manual reporting.",
        "status.ready_immediate": "Complete — sending now",
        "status.ready_immediate_tip": "All declared forms are complete, so UbyHost sends automatically without waiting for verification.",
        "status.awaiting_verification": "ID not checked",
        "status.awaiting_verification_tip": (
            "Guest forms are complete. You may record an ID check below; automatic reporting does not wait for it."
        ),
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
        "status.ready_scheduled_tip": "Will go out automatically after the delay measured from completion of all declared forms.",
        "status.demo_preview": "Preview only",
        "status.demo_preview_tip": "Demo data is never sent to the police.",
        "dashboard.reporting_modes": "How sending works",
        "dashboard.reporting_modes_body": (
            "Manual waits for your Send click. Delayed automation sends after the chosen number "
            "of hours from completion. Immediate automation sends as soon as all declared forms "
            "are complete. Automatic modes do not wait for passport verification."
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
        "guide.nav.productivity": "Faster everyday work",
        "guide.nav.setup": "First-time setup",
        "guide.nav.stays": "Stays & calendars",
        "guide.nav.guests": "Guest forms",
        "guide.nav.reporting": "Police reporting",
        "guide.nav.housebook": "House book",
        "guide.nav.security": "Security & backups",
        "guide.nav.demo": "Demo data",
        "guide.overview.body": (
            "Overview shows what needs attention now: missing guest forms, stays ready to report, "
            "and deadlines. Stays lists every booking; Reports keeps Doručenka receipts."
        ),
        "guide.overview.caption": "The next-up card shows the most urgent stay and its send button.",
        "guide.productivity.search": (
            "Press Ctrl+K (or Cmd+K on a Mac) to search and jump to a property, stay, guest, or page."
        ),
        "guide.productivity.shortcuts": (
            "Open the ? menu at the bottom of the sidebar for navigation and table keyboard shortcuts."
        ),
        "guide.productivity.views": (
            "On Stays, switch between List and Timeline, set filters, and choose Save view to "
            "keep a useful view for next time."
        ),
        "guide.productivity.quick_edit": (
            "Open a stay for its guest link, Add a guest, reporting controls, and the compact Quick edit panel."
        ),
        "guide.setup.step1_title": "Legal entity",
        "guide.setup.step1": "The company or person registered with the police.",
        "guide.setup.step2_title": "Property",
        "guide.setup.step2": "IDUB, mark, and address must match UbyPort exactly.",
        "guide.setup.step3_title": "Calendars",
        "guide.setup.step3": "Paste Airbnb or Booking.com iCal export links.",
        "guide.setup.step4_title": "UbyPort credentials",
        "guide.setup.step4": (
            "Enter the UBY-WS web-service login from the police letter on the property page. "
            "The annotated sample shows the exact fields; leaving an already-saved password blank keeps it."
        ),
        "guide.setup.step5_title": "Guest link",
        "guide.setup.step5": "Put the permalink in your check-in message on every portal.",
        "guide.stays.body": (
            "Stays arrive from calendars or manual entry. Open a row to add guests, copy the guest link, "
            "or send completed records."
        ),
        "guide.stays.csv": (
            "Use Export stays (CSV) in the filter bar for a spreadsheet copy. House book offers CSV "
            "and an inspection PDF bundle from its Export menu. Exports respect the current filters."
        ),
        "guide.guests.body": (
            "Each stay has a guest link meant for a phone. Guests pick their arrival dates, the lead "
            "guest states how many people are staying, claims the reservation by e-mail, then each "
            "person fills in a short step-by-step form."
        ),
        "guide.guests.step_email": (
            "The e-mail receives the private form link, one reminder if incomplete the day before "
            "check-in, and a completion receipt. The host gets a completion copy; public screens "
            "mask the address. Necessary cookies preserve PIN, language, claim, and device access."
        ),
        "guide.guests.step_party": (
            "Headcount first — everyone in the group, including children, gets a separate form so "
            "nobody sees anyone else's passport details."
        ),
        "guide.guests.step_details": (
            "Each guest types name, birth date, nationality, and document number as printed on the "
            "travel document (no scanning or machine-readable line copying)."
        ),
        "guide.guests.step_photo": (
            "UbyHost does not collect passport or ID images. Any document check is handled in person."
        ),
        "guide.guests.step_czech": (
            "Czech guests are still written to the house book but are not reported to the police."
        ),
        "guide.reporting.body": "Each property chooses how completed guest records reach UbyPort:",
        "guide.reporting.caption": (
            "Passport checking is an optional explicit host action. Automatic reporting follows "
            "the completion timing you choose and does not wait for that check."
        ),
        "guide.reporting.immediate": "Immediately after completion",
        "guide.reporting.immediate_detail": (
            "Sent automatically as soon as every declared guest form is complete, "
            "without waiting for host verification."
        ),
        "guide.legal.verification_title": "Verify every foreign guest",
        "guide.legal.verification_body": (
            "You are legally responsible for accurate police records. Check the travel document "
            "in person when your procedure or the law requires it; UbyHost does not collect an image. "
            "If a guest refuses to show ID, you may "
            "refuse accommodation."
        ),
        "guide.reporting.scheduled": "Scheduled",
        "guide.reporting.scheduled_detail": "Sent automatically after your chosen delay from completion.",
        "guide.reporting.manual": "Manual",
        "guide.reporting.manual_detail": "You click Send on the stay or use Send all ready stays.",
        "guide.reporting.bulk": (
            "Send all ready stays only sends stays that are complete and allowed by the automation mode — "
            "it never forces a partial stay."
        ),
        "guide.housebook.body": (
            "The house book lists every guest — Czech and foreign. Export CSV or download PDFs for "
            "inspections from the Export menu. Import is currently unavailable."
        ),
        "guide.security.two_factor": (
            "Enable two-factor authentication in Settings with an authenticator app, and store the "
            "one-time recovery codes somewhere safe."
        ),
        "guide.security.turnstile": (
            "Production sits behind Cloudflare: Turnstile on sign-in and after repeated guest PIN "
            "failures, Bot Fight Mode, leaked-credential checks on login, HSTS, and client-side "
            "script monitoring. Legitimate visitors may occasionally see a short challenge."
        ),
        "guide.security.passports": (
            "Passport and ID images are not collected by the guest form."
        ),
        "guide.security.backups": (
            "Settings shows backup status. Production creates encrypted database backups; keep an independent "
            "export before closing the service or making major changes."
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
        "legal.security_title": "Security measures",
        "legal.security_body": (
            "Production deployments may require two-factor authentication (authenticator app), Cloudflare "
            "Turnstile on login and guest PIN after abuse, Bot Fight Mode, leaked-credential checks, "
            "HSTS, client-side script monitoring, encrypted storage of integration secrets, rate "
            "limiting, and off-site backups configured by the operator. Details are in the Privacy Policy "
            "and Data Processing Agreement."
        ),
        "legal.disclaimer_title": "Disclaimer",
        "legal.disclaimer_body": (
            "The software is provided without warranty to the extent permitted by law. Liability is limited "
            "to mandatory statutory rules. Nothing here changes who must register guests or keep the house "
            "book — that remains the accommodation provider."
        ),
        "legal.back_login": "Back to login",
        "legal.footer_link": "Legal notice",
        "legal.footer_short": "Legal",
        "legal.footer_nav_label": "Help and legal",
        "legal.use_acceptance": (
            "By logging in or continuing to use UbyHost, you confirm that you have read and agree "
            "to the Terms of Service (including the Data Processing Agreement at /dpa), the Privacy "
            "Policy, and the Legal notice, and that you act on behalf of your accommodation business "
            "(not as a consumer where business terms apply)."
        ),
        "legal.use_acceptance_short": "Use = Terms (incl. DPA), Privacy & Legal.",
        "legal.settings_title": "Software operator",
        "legal.settings_body": (
            "UbyHost is operated by %(name)s, IČO %(ico)s. Guest data controllers are your legal entities "
            "configured per property."
        ),
        "legal.settings_contact_missing": (
            "Set UBYHOST_OPERATOR_EMAIL in the server environment for a public support address."
        ),
        "legal.support_label": "UbyHost support",
        "legal.support_help": (
            "Software questions: support@ubyhost.com. Guests with a stay question should use "
            "the host name, e-mail, and phone shown on the guest form."
        ),
        "guide.demo.body": (
            "Load demo data anytime to explore with a sample flat. Demo guests are never sent to the real "
            "police register."
        ),
        "a11y.skip_to_content": "Skip to main content",
        "a11y.breadcrumb": "Breadcrumb",
        "a11y.main_navigation": "Main navigation",
        "a11y.open_menu": "Open menu",
        "a11y.close_menu": "Close menu",
        "a11y.show_menu": "Show menu",
        "a11y.hide_menu": "Hide menu",
        "a11y.notifications": "Notifications",
        "a11y.dismiss_notification": "Dismiss notification",
        "a11y.dismiss": "Dismiss",
        "env.where_reports_go": "Where reports are sent",
        "env.prod": "Production",
        "env.mock": "MOCK · Nothing sent",
        "env.test": "TEST · Police sandbox",
        "env.staging": "STAGING",
        "env.local": "LOCAL",
        "command.open": "Search or jump to…",
        "command.placeholder": "Search stays, properties, reports, and actions…",
        "command.empty": "No matching destination",
        "command.group.pages": "Pages",
        "command.group.actions": "Actions",
        "command.property": "Property",
        "command.stay": "Stay",
        "command.copy_property_link": "Copy guest link · %(property)s",
        "command.copied": "Guest link copied",
        "shortcuts.open": "Keyboard shortcuts",
        "shortcuts.title": "Keyboard shortcuts",
        "shortcuts.navigation": "Navigation",
        "shortcuts.rows": "Rows",
        "shortcuts.close": "Close",
        "shortcuts.dashboard": "Go to Overview",
        "shortcuts.stays": "Go to Stays",
        "shortcuts.reports": "Go to Reports",
        "shortcuts.housebook": "Go to House book",
        "shortcuts.search": "Open search",
        "shortcuts.next": "Select next row",
        "shortcuts.previous": "Select previous row",
        "shortcuts.open_row": "Open selected row",
        "impersonation.previewing": "Previewing workspace",
        "impersonation.exit": "Exit preview",
        "notification.open_stay": "Open the stay",
        "notification.open_property": "Open the property",
        "common.back": "Back",
        "common.close": "Close",
        "common.apply": "Apply",
        "common.clear": "Clear",
        "common.save": "Save",
        "common.optional": "(optional)",
        "common.actions": "Actions",
        "common.open": "Open",
        "common.restore": "Restore",
        "common.archive": "Archive",
        "common.edit": "Edit",
        "common.from": "From",
        "common.until": "Until",
        "common.auto": "Auto",
        "common.copy": "Copy",
        "common.copied": "Copied",
        "common.copy_link": "Copy link",
        "common.copy_guest_link": "Copy the guest link for this stay",
        "common.more_actions": "More actions",
        "common.undo": "Undo",
        "submission.accepted": "Accepted",
        "submission.partial": "Partly accepted",
        "submission.rejected": "Rejected",
        "submission.not_delivered": "Not delivered",
        "submission.setup_incomplete": "Setup incomplete",
        "submission.in_progress": "In progress",
        "submission.nothing_to_send": "Nothing to send",
        "confirm.cancel": "Cancel",
        "confirm.proceed": "Confirm",
        "confirm.archive_stay": "Archive this stay? It moves to Archive and can be restored later.",
        "confirm.archive_property": "Archive this property? It will disappear from your dashboard and guest links.",
        "confirm.clear_demo": "Clear the built-in demo data?",
        "confirm.purge_expired": "Permanently delete every guest record past the retention period? This cannot be undone.",
        "confirm.delete_entity": "Delete this legal entity? This cannot be undone.",
        "confirm.archive_entity": "Archive this legal entity? You can restore it later.",
        "confirm.remove_guest": "Remove this guest record?",
        "confirm.archive_guest": "Archive this guest? The entry leaves your house book export until you restore it.",
        "confirm.disconnect_feed": "Disconnect this calendar feed? Existing stays are preserved.",
        "confirm.regenerate_link": "Generate a new guest link and PIN? The current link and PIN stop working.",
        "confirm.regenerate_pin": "Generate a new random PIN?",
        "action.failed": "Open the stay, fix the rejection, and send again.",
        "action.ready_immediate": "Guest details are complete — they will send automatically when guests submit.",
        "action.ready": "Guest details are complete. Open the stay and send when ready.",
        "action.incomplete": "Open the stay to finish missing guest details.",
        "action.awaiting_guest": "Share the guest link or add the details yourself.",
        "action.awaiting_verification": "Forms complete — mark ID checked or send from this stay.",
        "action.check_missing": "Open the stay and check what is missing.",
        "hint.awaiting_verification": "Optionally record an in-person document check",
        "hint.awaiting_guest": "Send the check-in link to the guest, or add their details yourself",
        "hint.auto_immediate": "Sends automatically when all declared guest forms are complete",
        "hint.nothing_duty": "Nothing to send: no guest record is subject to the reporting duty",
        "hint.need_signature": "Every foreign guest must sign before reporting to UbyPort",
        "hint.need_verification": "Verify each guest against their passport before reporting",
        "hint.nothing_left": "Nothing left to send for this stay",
        "hint.not_ready": "Complete guest details, signatures, and passport checks before sending",
        "hint.ready_to_send": "Send completed guest records to UbyPort now",
        "hint.ready_id_optional": "Forms complete — send now or mark ID checked first (recorded on send)",
        "hint.demo_preview": "Demo stays are never sent — use a real property to report to UbyPort",
        # Czech needs three forms for "day" (1 / 2-4 / 5+), so every day-based
        # countdown carries .one and .few alongside the base many form.
        "deadline.arrives_days": "arrives in %(n)s days",
        "deadline.arrives_days.one": "arrives in 1 day",
        "deadline.arrives_days.few": "arrives in %(n)s days",
        "deadline.days_left": "%(n)s days left",
        "deadline.days_left.one": "1 day left",
        "deadline.days_left.few": "%(n)s days left",
        "deadline.overdue_days": "overdue by %(n)s days",
        "deadline.overdue_days.one": "overdue by 1 day",
        "deadline.overdue_days.few": "overdue by %(n)s days",
        "deadline.hours_left": "%(n)s h left",
        "deadline.overdue_hours": "overdue by %(n)s h",
        "env.mock_title": "Nothing is being reported to the police",
        "env.mock_body": (
            "This workspace is pointed at the practice server, so records marked "
            "\"Reported\" were never filed. Set UBYHOST_UBYPORT_ENV to test or prod "
            "before you rely on it."
        ),
        "env.mock_production_title": "Live deployment is still on the practice server",
        "env.mock_production_body": (
            "Guests are registering for real but nothing reaches the Foreign Police, so "
            "every stay is running out its three working days unreported. Set "
            "UBYHOST_UBYPORT_ENV=prod now."
        ),
        "status.failed": "Rejected",
        "status.reported": "Reported",
        "status.ready": "Ready to report",
        "status.incomplete": "Incomplete",
        "status.not_required": "Exempt",
        "status.awaiting_guest_short": "Waiting for guest",
        "dashboard.title": "Overview",
        "dashboard.lede": "Your reporting work, ordered by legal urgency and the next action.",
        "dashboard.sync_calendars": "Sync calendars",
        "dashboard.last_synced": "Last synced %(when)s UTC",
        "dashboard.focus.overdue": "Past the deadline",
        "dashboard.focus.urgent": "Due now",
        "dashboard.focus.next_up": "Next up",
        "dashboard.focus.guest_forms": "%(filled)s / %(expected)s guest forms",
        "dashboard.focus.open_stay": "Open the stay",
        "dashboard.focus.add_guest": "Add a guest by hand",
        "dashboard.focus.copy_link": "Copy guest link",
        "dashboard.stats.past_deadline": "Past deadline",
        "dashboard.stats.need_action": "Need action",
        "dashboard.stats.waiting_guest": "Waiting for guest",
        "dashboard.stats.ready": "Ready to report",
        "dashboard.setup.title": "Finish setup",
        "dashboard.setup.lede": "These properties cannot report until their registration details are complete.",
        "dashboard.setup.view_properties": "View properties",
        "dashboard.setup.items": "%(count)s item to fix",
        "dashboard.setup.items_plural": "%(count)s items to fix",
        "dashboard.empty.no_stays": "No stays in the current window. Either the calendars have nothing booked, or they have not been synced yet.",
        "dashboard.empty.sync_now": "Sync calendars now",
        "dashboard.section.needs_action": "Needs action now",
        "dashboard.section.waiting": "Waiting for guests",
        "dashboard.section.upcoming": "Upcoming arrivals",
        "dashboard.section.completed": "Recently completed",
        "dashboard.section.view_stays": "View all stays",
        "dashboard.section.view_reports": "View reports",
        "dashboard.queue.empty.action": "You are caught up. Nothing needs action now.",
        "dashboard.queue.empty.waiting": "No guest forms are currently outstanding.",
        "dashboard.queue.empty.default": "Nothing needs attention here.",
        "dashboard.table.stay": "Stay",
        "dashboard.table.deadline": "Deadline",
        "dashboard.table.guests": "Guests",
        "dashboard.table.reporting": "Reporting",
        "dashboard.table.deadline_by": "by %(when)s",
        "dashboard.row.open_stay": "Open stay",
        "dashboard.row.add_guest": "Add a guest",
        "stays.title": "Stays",
        "stays.lede": "Calendar stays and manual bookings, earliest arrival first.",
        "stays.add_stay": "Add stay",
        "stays.add_panel.title": "Add a stay by hand",
        "stays.add_panel.lede": "For direct bookings, phone reservations, or anything not on a connected calendar.",
        "stays.add_panel.apartment": "Apartment",
        "stays.add_panel.arrival": "Arrival",
        "stays.add_panel.departure": "Departure",
        "stays.add_panel.guests": "Number of guests",
        "stays.add_panel.label": "Label",
        "stays.add_panel.label_ph": "Direct booking – Novák",
        "stays.add_panel.email": "Guest e-mail",
        "stays.add_panel.create": "Create stay",
        "stays.chip.upcoming": "Upcoming & current",
        "stays.chip.past": "Past",
        "stays.chip.all": "All dates",
        "stays.chip.archive": "Archive",
        "stays.archive_note": "Archived stays are hidden from your daily work but kept for reference. Restore any entry you archived by mistake.",
        "stays.filter.apartment": "Apartment",
        "stays.filter.all_apartments": "All",
        "stays.filter.state": "Stay state",
        "stays.filter.state.active": "Active",
        "stays.filter.state.cancelled": "Cancelled",
        "stays.filter.state.ignored": "Ignored",
        "stays.filter.state.all": "All",
        "stays.filter.from": "Staying on or after",
        "stays.filter.to": "Staying on or before",
        "stays.filter.save_view": "Save this view",
        "stays.filter.saved": "View saved",
        "stays.filter.saved_views": "Saved views",
        "stays.view.label": "Stay view",
        "stays.view.list": "List",
        "stays.view.timeline": "Timeline",
        "stays.table.stay": "Stay",
        "stays.table.apartment": "Apartment",
        "stays.table.source": "Source",
        "stays.table.guests": "Guests",
        "stays.table.reporting": "Reporting",
        "stays.table.deadline": "Deadline",
        "stays.table.nights": "%(count)s nights",
        "stays.table.in_house": "In house",
        "stays.table.portal": "portal →",
        "stays.row.open": "Open stay",
        "stays.row.add_guest": "Add a guest",
        "stays.row.restore": "Restore",
        "stays.pagination.showing": "Showing %(from)s–%(to)s of %(total)s stay.",
        "stays.pagination.showing_plural": "Showing %(from)s–%(to)s of %(total)s stays.",
        "stays.pagination.prev": "← Previous",
        "stays.pagination.next": "Next →",
        "stays.pagination.label": "Page %(page)s of %(pages)s",
        "stays.empty.archive": "No archived stays. Archive mistakes from any stay row.",
        "stays.empty.filter": "No stay matches this filter.",
        "stays.empty.show_all": "Show all dates",
        "stays.empty.none": "No stays yet. Connect a calendar to an apartment, or use Add stay above.",
        "stays.empty.go_apartments": "Go to apartments",
        "stays.empty.no_apartments": "There are no apartments yet, so there is nothing to show.",
        "stays.empty.add_first": "Add your first apartment",
        "stay.detail.back": "Back to stays",
        "stay.claim.title": "Guest assignment",
        "stay.claim.unclaimed": "No guest e-mail has claimed this stay yet.",
        "stay.claim.provisional": "A confirmation e-mail is waiting for %(email)s.",
        "stay.claim.claimed": "Assigned to %(email)s.",
        "stay.claim.locked": "Guest forms are locked. Reopen if the guest still needs access.",
        "stay.claim.reopen": "Reopen guest access",
        "stay.claim.release": "Release assignment",
        "stay.claim.release_confirm": "Release this stay so another e-mail can claim it?",
        "stay.detail.copy_link": "Copy guest link for this stay",
        "stay.detail.link_copied": "Link copied",
        "stay.detail.cta.send": "Send to UbyPort",
        "stay.detail.cta.fix": "Fix rejection",
        "stay.detail.cta.view_reports": "View reports",
        "stay.detail.cta.verify": "Verify passports",
        "stay.detail.cta.open": "Open stay",
        "stay.detail.cta.add_guest": "Add a guest",
        "stay.detail.next_step": "Next step",
        "stay.detail.ready_count": "%(count)s guest record(s) ready to report.",
        "stay.detail.metric.deadline": "Reporting deadline",
        "stay.detail.metric.deadline_note": "Three working days after check-in ends %(when)s.",
        "stay.detail.metric.guests": "Guest forms",
        "stay.detail.metric.guests_note": "%(sent)s reported · %(reportable)s subject to the duty",
        "stay.detail.metric.set_expected": "Set expected guests",
        "stay.detail.metric.reporting": "Reporting",
        "stay.detail.note.verify": "Guest forms are complete. You may check the document in person and record the result.",
        "stay.detail.note.ready_immediate": "All declared forms are complete. UbyPort submission starts automatically without verification.",
        "stay.detail.note.ready_manual": "Guest forms are complete. Check the details below, then send when ready.",
        "stay.detail.note.ready_scheduled": "Guest forms are complete. They will send %(hours)s h after completion, or use Send now.",
        "stay.detail.note.automation": "Automation:",
        "stay.detail.note.immediate": "immediately after all declared forms are complete",
        "stay.detail.note.scheduled": "%(hours)s h after all declared forms are complete",
        "stay.detail.note.manual": "manual only",
        "stay.detail.guests.title": "Guests",
        "stay.detail.guests.lead": "lead",
        "stay.detail.guests.reported": "Reported",
        "stay.detail.guests.exempt": "Exempt",
        "stay.detail.guests.rejected": "Rejected",
        "stay.detail.guests.rejected_final": "Rejected, final",
        "stay.detail.guests.incomplete": "Incomplete",
        "stay.detail.guests.verify": "Verify passport",
        "stay.detail.guests.ready": "Ready",
        "stay.detail.guests.edit": "Edit details",
        "stay.detail.guests.pdf": "Registration form PDF",
        "stay.detail.guests.born": "Born",
        "stay.detail.guests.nationality": "Nationality",
        "stay.detail.guests.document": "Document",
        "stay.detail.guests.visa": "visa %(number)s",
        "stay.detail.guests.purpose": "Purpose of stay",
        "stay.detail.guests.residence": "Residence abroad",
        "stay.detail.guests.staying": "Staying",
        "stay.detail.guests.signature": "Signature",
        "stay.detail.guests.signed": "Signed",
        "stay.detail.guests.not_signed": "Not signed",
        "stay.detail.guests.entered_by": "Entered by",
        "stay.detail.guests.note": "Note: %(text)s",
        "stay.detail.guests.empty": "No guest has filled in the form yet.",
        "stay.detail.guests.empty_hint": "Copy the guest link above, or add the details yourself.",
        "stay.detail.reports.title": "Reports sent for this stay",
        "stay.detail.reports.when": "When",
        "stay.detail.reports.outcome": "Outcome",
        "stay.detail.reports.stamp": "Receipt stamp",
        "stay.detail.reports.open": "Open report",
        "stay.detail.settings.title": "Stay settings",
        "stay.detail.settings.lede": "Headcount, stay state, and your private notes. Message templates live under",
        "stay.detail.settings.guest_links": "Guest links",
        "stay.detail.settings.expected": "Expected number of guests",
        "stay.detail.settings.expected_declared": "The lead guest declared %(count)s. Setting a number here overrides that.",
        "stay.detail.settings.expected_blank": "No calendar provides a headcount. Leave blank to let the lead guest declare it.",
        "stay.detail.settings.email": "Guest e-mail",
        "stay.detail.settings.email_hint": "Stored for your reference. Automated guest messages use the e-mail that claims the guest link.",
        "stay.detail.settings.host_only": "(host-only note)",
        "stay.detail.settings.state": "Stay state",
        "stay.detail.settings.state.active": "Active",
        "stay.detail.settings.state.cancelled": "Cancelled",
        "stay.detail.settings.state.ignored": "Not a guest stay",
        "stay.detail.settings.state_hint": "“Not a guest stay” removes this item from daily work but preserves it and sticks across future calendar syncs. You can restore it by choosing Active.",
        "stay.detail.settings.note": "Private note",
        "stay.detail.inline.title": "Edit stay details",
        "stay.detail.inline.label": "Internal label",
        "stay.detail.inline.guests": "Expected guests",
        "stay.detail.inline.saved": "Saved",
        "stay.detail.inline.error": "Could not save. Try again.",
        "stay.detail.menu.restore": "Restore from archive",
        "stay.detail.menu.archive": "Archive stay",
        "stay.detail.menu.guest_links": "Guest links & templates",
        "apartments.title": "Properties",
        "apartments.lede": "Each accommodation facility has its own UbyPort registration, calendars, and guest link.",
        "apartments.entities_link": "Legal entities",
        "apartments.add": "Add a property",
        "apartments.table.property": "Property",
        "apartments.table.entity": "Legal entity",
        "apartments.table.idub": "IDUB",
        "apartments.table.calendars": "Calendars",
        "apartments.table.stays": "Stays",
        "apartments.table.automation": "Automation",
        "apartments.table.setup": "Setup readiness",
        "apartments.inactive": "Inactive",
        "apartments.automation.immediate": "Immediate",
        "apartments.automation.scheduled": "+%(hours)s h",
        "apartments.automation.manual": "Manual",
        "apartments.setup.fix": "%(count)s to fix",
        "apartments.setup.calendar": "Connect calendar",
        "apartments.setup.ready": "Can report",
        "apartments.row.edit": "Edit",
        "apartments.empty.lede": "No properties yet. Add the legal entity that operates them first, then create a property.",
        "apartments.empty.entity": "Add a legal entity",
        "apartments.empty.add": "Add your first property",
        "apartments.archived.title": "Archived",
        "apartments.archived.lede": "These properties are hidden from your dashboard and guest links. Their history is kept.",
        "apartments.archived.when": "Archived",
        "archive.title": "Archive",
        "archive.lede": "Restore archived stays, properties, and house-book entries.",
        "archive.empty": "Nothing archived yet.",
        "archive.chip.all": "All",
        "archive.chip.stays": "Stays",
        "archive.chip.properties": "Properties",
        "archive.chip.guests": "House book",
        "archive.section.stays": "Archived stays",
        "archive.section.properties": "Archived properties",
        "archive.section.guests": "Archived house-book entries",
        "archive.col.when": "Archived",
        "archive.col.stay": "Stay",
        "archive.col.property": "Property",
        "archive.col.guest": "Guest",
        "archive.col.name": "Name",
        "archive.col.stays_count": "Stays",
        "archive.page_lede": "Everything you archived in one place. Restore a mistake or review old records.",
        "archive.retention_note": (
            "Archiving hides items from your daily work but keeps their history. "
            "Only the six-year retention purge in Settings permanently deletes guest records."
        ),
        "archive.stay_moved": "Stay moved to archive.",
        "archive.chip.all_count": "All (%(count)s)",
        "archive.chip.stays_count": "Stays (%(count)s)",
        "archive.chip.properties_count": "Properties (%(count)s)",
        "archive.chip.housebook_count": "House book (%(count)s)",
        "archive.chip.entities_count": "Legal entities (%(count)s)",
        "archive.empty_detailed": (
            "Nothing is archived yet. You can archive stays, properties, house-book entries, "
            "and legal entities from their usual pages."
        ),
        "archive.empty.stays": "No archived stays.",
        "archive.empty.properties": "No archived properties.",
        "archive.empty.housebook": "No archived house-book entries.",
        "archive.empty.entities": "No archived legal entities.",
        "archive.hint.stays": "Hidden from your stay list. Reporting history is kept.",
        "archive.hint.properties": "Hidden from your dashboard and guest links. Their history is kept.",
        "archive.hint.housebook": "Mistaken imports or duplicates can be restored here.",
        "archive.hint.entities": "Hidden from property pickers until restored.",
        "archive.section.entities": "Archived legal entities",
        "settings.archive_hint_extended": (
            "Stays, properties, house-book entries, and legal entities you archived are collected in one place. "
            "Restore anything you hid by mistake. The retention purge below is the only way guest records are permanently deleted."
        ),
        "settings.nav.overview": "Overview",
        "settings.nav.mail": "Guest e-mails",
        "settings.lede": "Advanced system status, security, data protection, and activity log.",
        "settings.nav.retention": "Data protection",
        "settings.nav.archive": "Archive",
        "settings.nav.audit": "Activity log",
        "settings.nav.ubyport": "UbyPort & environment",
        "settings.nav.account": "Your account",
        "settings.nav.legal": "Software operator",
        "settings.nav.version": "Version",
        "settings.archive_link": "Open archive hub",
        "settings.archive_hint": "Restore archived stays, properties, and house-book entries.",
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
        "nav.automation": "Automatizace",
        "nav.guest_links": "Odkazy pro hosty",
        "nav.settings": "Nastavení",
        "nav.users": "Uživatelé",
        "nav.logout": "Odhlásit se",
        "nav.support": "Podpora",
        "nav.administrator": "Správce",
        "login.page_title": "Přihlášení · UbyHost",
        "login.meta_description": (
            "UbyHost spojuje kalendáře, formuláře hostů, domovní knihu a hlášení do UbyPortu "
            "pro krátkodobé pronájmy v Česku. Přihlaste se ke svému účtu."
        ),
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
        "login.acceptance_before": "Přihlášením nebo používáním UbyHostu souhlasíte s ",
        "login.acceptance_and": " a ",
        "login.acceptance_between_terms_privacy": ", ",
        "login.acceptance_between_privacy_legal": " a ",
        "login.acceptance_after": (
            ". Pokud nesouhlasíte, nepřihlašujte se ani Službu nepoužívejte."
        ),
        "login.hero_title": "Hlášení hostů bez zbytečné práce.",
        "login.hero_body": (
            "Kalendáře, formuláře hostů, domovní kniha a odeslání do UbyPortu na jednom místě — "
            "pro krátkodobé pronájmy v Česku."
        ),
        "onboarding.welcome_title": "Vítejte v UbyHostu",
        "onboarding.welcome_lede": (
            "Připravíme vaše první ubytování na hlášení hostů. Projděte kroky níže — "
            "většina hostitelů to zvládne za několik minut."
        ),
        "onboarding.step_of": "Krok nastavení %(n)s z %(total)s: %(title)s",
        "onboarding.step_done": "Hotovo",
        "onboarding.continue": "Pokračovat: %(action)s",
        "onboarding.entity.title": "Právnická osoba",
        "onboarding.entity.detail": (
            "Firma nebo podnikatel registrovaný v UbyPortu."
        ),
        "onboarding.entity.action": "Přidat právnickou osobu",
        "onboarding.property.title": "Ubytování",
        "onboarding.property.detail": "Každý byt nebo dům, který pronajímáte.",
        "onboarding.property.action": "Přidat ubytování",
        "onboarding.calendars.title": "Odkazy na kalendáře",
        "onboarding.calendars.detail": (
            "iCal odkazy z Airbnb nebo Booking.com, aby se pobyty zobrazovaly automaticky."
        ),
        "onboarding.calendars.action": "Připojit kalendáře",
        "onboarding.automation.title": "Automatizace a UbyPort",
        "onboarding.automation.detail": (
            "Zvolte okamžité po dokončení, odložené automatické nebo ruční odesílání; pak přesně "
            "doplňte přístupové a registrační údaje. UbyPort neshodu odmítne."
        ),
        "onboarding.automation.action": "Dokončit automatizaci",
        "onboarding.guest_link.title": "Odkaz pro hosty",
        "onboarding.guest_link.detail": (
            "Zkontrolujte PIN, volitelnou zprávu hostitele a e-mail/soukromí, "
            "pak odkaz zkopírujte do zprávy k příjezdu na každém rezervačním portálu."
        ),
        "onboarding.guest_link.action": "Kopírovat odkaz pro hosty",
        "demo.load": "Prohlédnout s ukázkovými daty",
        "demo.load_detail": (
            "Ukázkové ubytování s pobytem a hosty. Na policii se nic neodešle, dokud sami "
            "neodešlete skutečná data."
        ),
        "demo.clear": "Smazat ukázková data",
        "data.export_csv_title": "Export CSV",
        "data.export_csv_help": "Vyberte rozsah dat, který chcete exportovat.",
        "data.export_csv_download": "Stáhnout",
        "data.export_csv_cancel": "Zrušit",
        "csv.export_stays": "Export pobytů (CSV)",
        "csv.download": "Export tabulky (CSV)",
        "csv.download_pdfs": "Stáhnout balíček PDF (kontrola)",
        "reports.download_receipts": "Stáhnout doručenky (ZIP)",
        "reports.download_receipts_hint": "Jedno PDF za každé úspěšné odeslání, sestavené na disku bez zbytečné paměti.",
        "reports.title": "Hlášení",
        "reports.lede": "Každý přenos do UbyPortu a jeho Doručenka jako doklad.",
        "reports.when": "Kdy",
        "reports.property": "Ubytování",
        "reports.mode": "Režim",
        "reports.guests": "Hosté",
        "reports.outcome": "Výsledek",
        "reports.stamp": "Razítko doručenky",
        "reports.open": "Otevřít hlášení %(id)s",
        "reports.receipt": "Doručenka",
        "reports.details": "Zobrazit detail",
        "reports.empty_title": "Zatím žádná hlášení",
        "reports.empty_body": "Po odeslání do UbyPortu se zde objeví hotové záznamy hostů.",
        "reports.empty_action": "Otevřít pobyty",
        "reports.detail.title": "Hlášení č. %(id)s",
        "reports.detail.back": "Zpět na hlášení",
        "reports.detail.endpoint": "Koncový bod",
        "reports.detail.finished": "Dokončeno",
        "reports.detail.transport_error": "Chyba přenosu",
        "reports.detail.header_problems": "Problémy v záhlaví hlášení",
        "reports.detail.header_help": "Chyby záhlaví pocházejí z nastavení ubytování, nikoli z údajů hosta.",
        "reports.detail.download_receipt": "Stáhnout Doručenku",
        "reports.detail.download_errors": "Stáhnout chybový protokol",
        "reports.detail.guests": "Hosté v tomto přenosu",
        "reports.detail.guest": "Host",
        "reports.detail.result": "Výsledek",
        "reports.detail.technical": "Technické podrobnosti",
        "reports.detail.technical_help": "Přesné zprávy mezi UbyHostem a UbyPortem. Potřebujete je obvykle jen při řešení odmítnutí.",
        "housebook.legal_title": "Vaše zákonná povinnost (domovní kniha)",
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
        "housebook.export_menu": "Export",
        "housebook.pdf_export_title": "Stáhnout balíček PDF",
        "housebook.pdf_export_help": (
            "Vyberte rozsah pobytů a ubytování. Každý formulář hosta se na serveru generuje zvlášť — "
            "velký rozsah trvá déle a zatěžuje server."
        ),
        "housebook.pdf_hint": (
            "Nejvýše %(limit)s formulářů na jedno stažení. Při velkém počtu záznamů zužte datumy."
        ),
        "housebook.legal_intro_title": "Domovní kniha — vaše zákonná povinnost",
        "housebook.legal_intro_ack": "Rozumím — příště skrýt",
        "housebook.legal_intro_skip": "Teď přeskočit",
        "housebook.filter_footer": "Exporty používají aktuální filtr.",
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
        "host.verify_help": "Volitelně zaznamenejte, že jste doklad hosta zkontrolovali osobně.",
        "host.verify_confirm": "Zkontroloval(a) jsem doklad hosta proti údajům výše.",
        "host.verify_button": "Označit doklad zkontrolovaný",
        "host.verify_pending": "Doklad nezkontrolován",
        "host.verify_view_photo": "Zobrazit nahraný doklad",
        "host.verify_footnote": "UbyHost obrázek pasu ani dokladu nesbírá.",
        "host.verify_waiting_photo": "Kontrola dokladu není zaznamenána — osobní kontrolu můžete označit.",
        "host.verify_done": "Doklad zkontrolován",
        "host.verify_host_entry": (
            "Když zadáváte hosta ručně, potvrzujete údaje proti dokladu na místě. Záznam se "
            "označí jako ověřený při uložení."
        ),
        "housebook.legal_footnote": (
            "Zůstáváte správcem údajů hostů. Josef Pechar (UbyHost) je pouze poskytovatel technologie — "
            "ne váš ubytovací podnik, ne právní poradenství a neodpovídá za chybné údaje, které zadáte "
            "vy nebo hosté, ani za způsob použití software. Uchovejte podepsané papíry; obrazovka sama "
            "o sobě nemusí při kontrole stačit."
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
        "status.ready_immediate": "Hotovo — odesílá se",
        "status.ready_immediate_tip": "Všechny nahlášené formuláře jsou hotové, proto UbyHost odešle automaticky bez čekání na ověření.",
        "status.awaiting_verification": "Doklad nezkontrolován",
        "status.awaiting_verification_tip": (
            "Formuláře jsou hotové. Kontrolu dokladu můžete zaznamenat níže; automatické hlášení na ni nečeká."
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
        "status.ready_scheduled_tip": "Odejde automaticky po zvolené prodlevě od dokončení všech nahlášených formulářů.",
        "status.demo_preview": "Jen náhled",
        "status.demo_preview_tip": "Ukázková data se na policii nikdy neodešlou.",
        "dashboard.reporting_modes": "Jak funguje odesílání",
        "dashboard.reporting_modes_body": (
            "Ruční režim čeká na Odeslat. Odložená automatizace odešle po zvoleném počtu hodin "
            "od dokončení. Okamžitá automatizace odešle, jakmile jsou hotové všechny nahlášené "
            "formuláře. Automatické režimy nečekají na ověření pasu."
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
        "guide.nav.productivity": "Rychlejší každodenní práce",
        "guide.nav.setup": "První nastavení",
        "guide.nav.stays": "Pobyty a kalendáře",
        "guide.nav.guests": "Formuláře hostů",
        "guide.nav.reporting": "Hlášení na policii",
        "guide.nav.housebook": "Domovní kniha",
        "guide.nav.security": "Zabezpečení a zálohy",
        "guide.nav.demo": "Ukázková data",
        "guide.overview.body": (
            "Přehled ukazuje, co vyžaduje pozornost: chybějící formuláře, připravená hlášení a termíny. "
            "Pobyty obsahují rezervace; Hlášení uchovává doručenky."
        ),
        "guide.overview.caption": "Karta Další na řadě ukazuje nejnaléhavější pobyt a tlačítko Odeslat.",
        "guide.productivity.search": (
            "Klávesami Ctrl+K (na Macu Cmd+K) otevřete hledání ubytování, pobytu, hosta nebo stránky."
        ),
        "guide.productivity.shortcuts": (
            "V nabídce ? dole v postranním panelu najdete klávesové zkratky pro navigaci a tabulky."
        ),
        "guide.productivity.views": (
            "Na stránce Pobyty přepínejte Seznam a Časovou osu, nastavte filtry a volbou Uložit "
            "pohled si je uchovejte pro příště."
        ),
        "guide.productivity.quick_edit": (
            "V detailu pobytu najdete odkaz pro hosty, Přidat hosta, ovládání hlášení a stručnou Rychlou úpravu."
        ),
        "guide.setup.step1_title": "Právnická osoba",
        "guide.setup.step1": "Firma nebo osoba registrovaná u policie.",
        "guide.setup.step2_title": "Ubytování",
        "guide.setup.step2": "IDUB, značka a adresa musí přesně sedět s UbyPortem.",
        "guide.setup.step3_title": "Kalendáře",
        "guide.setup.step3": "Vložte exportní iCal odkazy z Airbnb nebo Booking.com.",
        "guide.setup.step4_title": "Přihlašovací údaje UbyPort",
        "guide.setup.step4": (
            "Na stránce ubytování zadejte přihlašovací jméno UBY-WS z policejního dopisu. "
            "Anotovaná ukázka přesně ukazuje pole; prázdné již uložené heslo se při uložení zachová."
        ),
        "guide.setup.step5_title": "Odkaz pro hosty",
        "guide.setup.step5": "Permalink vložte do zprávy při příjezdu na všech portálech.",
        "guide.stays.body": (
            "Pobyty přicházejí z kalendářů nebo ručního zadání. Otevřete řádek pro hosty, odkaz nebo odeslání."
        ),
        "guide.stays.csv": (
            "Tlačítkem Export pobytů (CSV) v panelu filtrů získáte tabulku. Domovní kniha nabízí "
            "v nabídce Export CSV a balíček PDF pro kontrolu. Export respektuje aktuální filtry."
        ),
        "guide.guests.body": (
            "Každý pobyt má odkaz pro hosty na telefonu. Vyberou termín pobytu, vedoucí host uvede "
            "počet osob, převezme rezervaci e-mailem a každý pak vyplní vlastní krátký formulář."
        ),
        "guide.guests.step_email": (
            "Na e-mail přijde soukromý odkaz, jedno upozornění při nedokončení den před příjezdem "
            "a potvrzení o dokončení. Ubytovatel dostane kopii potvrzení; veřejné obrazovky adresu "
            "zastřou. Nezbytné cookies uchovají PIN, jazyk, převzetí a přístup zařízení."
        ),
        "guide.guests.step_party": (
            "Nejdřív počet osob — včetně dětí; každý má vlastní formulář, aby nikdo neviděl "
            "údaje z pasu ostatních."
        ),
        "guide.guests.step_details": (
            "Každý host ručně zadá jméno, datum narození, státní občanství a číslo dokladu tak, "
            "jak jsou v cestovním dokladu (bez skenování ani přepisování strojově čitelných řádků)."
        ),
        "guide.guests.step_photo": (
            "UbyHost obrázky pasů ani dokladů nesbírá. Případná kontrola dokladu probíhá osobně."
        ),
        "guide.guests.step_czech": (
            "Občané ČR se zapisují do domovní knihy, policii se neoznamují."
        ),
        "guide.reporting.body": "Každé ubytování volí, jak se hotová hlášení dostanou do UbyPortu:",
        "guide.reporting.caption": (
            "Kontrola pasu je volitelný výslovný úkon ubytovatele. Automatické hlášení se řídí "
            "zvoleným časem od dokončení a na kontrolu nečeká."
        ),
        "guide.reporting.immediate": "Okamžitě po dokončení",
        "guide.reporting.immediate_detail": (
            "Odešle se automaticky, jakmile jsou hotové všechny nahlášené formuláře hostů, "
            "bez čekání na ověření ubytovatelem."
        ),
        "guide.legal.verification_title": "Ověřte každého cizince",
        "guide.legal.verification_body": (
            "Za správnost policejních záznamů odpovídáte vy. Doklad zkontrolujte osobně, pokud to "
            "vyžaduje váš postup nebo zákon; UbyHost jeho obrázek nesbírá. "
            "Odmítne-li host doklad ukázat, můžete odmítnout ubytování."
        ),
        "guide.reporting.scheduled": "Naplánované",
        "guide.reporting.scheduled_detail": "Odešle se automaticky po zvolené prodlevě od dokončení.",
        "guide.reporting.manual": "Ruční",
        "guide.reporting.manual_detail": "Kliknete Odeslat u pobytu nebo Odeslat všechny připravené.",
        "guide.reporting.bulk": (
            "Hromadné odeslání jen u kompletních pobytů povolených režimem — nikdy ne částečných."
        ),
        "guide.housebook.body": (
            "Domovní kniha obsahuje všechny hosty — Čechy i cizince. CSV nebo PDF pro kontroly "
            "stáhnete z nabídky Export. Import nyní není k dispozici."
        ),
        "guide.security.two_factor": (
            "V Nastavení zapněte dvoufázové ověření pomocí autentizační aplikace a jednorázové "
            "obnovovací kódy uložte na bezpečné místo."
        ),
        "guide.security.turnstile": (
            "Produkce je za Cloudflare: Turnstile při přihlášení a po opakovaných chybách PIN, "
            "Bot Fight Mode, kontrola uniklých přihlašovacích údajů, HSTS a monitoring skriptů "
            "v prohlížeči. Návštěvník může občas vidět krátkou výzvu."
        ),
        "guide.security.passports": (
            "Fotografie pasů jsou při čekání na kontrolu šifrované a po ověření se ihned smažou."
        ),
        "guide.security.backups": (
            "Nastavení ukazuje stav záloh. Produkce vytváří šifrované zálohy databáze; před ukončením "
            "služby nebo zásadní změnou si ponechte také vlastní export."
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
        "legal.security_title": "Bezpečnostní opatření",
        "legal.security_body": (
            "V produkci může být vyžadováno dvoufázové ověření (autentizační aplikace), Cloudflare "
            "Turnstile při přihlášení a u PIN hostů po zneužití, Bot Fight Mode, kontrola uniklých "
            "přihlašovacích údajů, HSTS, monitoring skriptů v prohlížeči, šifrované uložení "
            "integračních tajemství, rate limiting a off-site zálohy nastavené provozovatelem. "
            "Podrobnosti jsou v Zásadách ochrany osobních údajů a v DPA."
        ),
        "legal.disclaimer_title": "Vyloučení odpovědnosti",
        "legal.disclaimer_body": (
            "Software je poskytován bez záruky v rozsahu povoleném zákonem. Odpovědnost je omezena "
            "povinnými zákonnými pravidly. Tím se nemění, kdo musí hosty registrovat a vést domovní "
            "knihu — to zůstává na poskytovateli ubytování."
        ),
        "legal.back_login": "Zpět na přihlášení",
        "legal.footer_link": "Právní informace",
        "legal.footer_short": "Právní",
        "legal.footer_nav_label": "Nápověda a právní informace",
        "legal.use_acceptance": (
            "Přihlášením nebo dalším používáním UbyHostu potvrzujete, že jste se seznámili "
            "s Obchodními podmínkami (včetně DPA na /dpa), Zásadami ochrany osobních údajů "
            "a Právními informacemi a že s nimi souhlasíte, a že jednáte za své ubytovací podnikání "
            "(nikoli jako spotřebitel, pokud platí podmínky pro podnikatele)."
        ),
        "legal.use_acceptance_short": "Použití = Podmínky (vč. DPA), Soukromí a Právní info.",
        "legal.settings_title": "Provozovatel software",
        "legal.settings_body": (
            "UbyHost provozuje %(name)s, IČO %(ico)s. Správci údajů hostů jsou vaše právnické osoby "
            "nastavené u jednotlivých ubytování."
        ),
        "legal.settings_contact_missing": (
            "Pro veřejný kontakt nastavte UBYHOST_OPERATOR_EMAIL v prostředí serveru."
        ),
        "legal.support_label": "Podpora UbyHost",
        "legal.support_help": (
            "Dotazy k software: support@ubyhost.com. Hosté s otázkou k pobytu mají použít "
            "jméno, e-mail a telefon ubytovatele na formuláři pro hosty."
        ),
        "guide.demo.body": (
            "Ukázková data lze načíst kdykoli. Na skutečnou policii se nikdy neodešlou."
        ),
        "a11y.skip_to_content": "Přeskočit na hlavní obsah",
        "a11y.breadcrumb": "Drobečková navigace",
        "a11y.main_navigation": "Hlavní navigace",
        "a11y.open_menu": "Otevřít menu",
        "a11y.close_menu": "Zavřít menu",
        "a11y.show_menu": "Zobrazit menu",
        "a11y.hide_menu": "Skrýt menu",
        "a11y.notifications": "Oznámení",
        "a11y.dismiss_notification": "Skrýt oznámení",
        "a11y.dismiss": "Skrýt",
        "env.where_reports_go": "Kam se hlášení odesílají",
        "env.prod": "Produkce",
        "env.mock": "UKÁZKA · Nic se neodesílá",
        "env.test": "TEST · Policejní test",
        "env.staging": "STAGING",
        "env.local": "LOKÁLNÍ",
        "command.open": "Hledat nebo přejít…",
        "command.placeholder": "Hledat pobyty, ubytování, hlášení a akce…",
        "command.empty": "Žádný odpovídající cíl",
        "command.group.pages": "Stránky",
        "command.group.actions": "Akce",
        "command.property": "Ubytování",
        "command.stay": "Pobyt",
        "command.copy_property_link": "Kopírovat odkaz pro hosty · %(property)s",
        "command.copied": "Odkaz pro hosty zkopírován",
        "shortcuts.open": "Klávesové zkratky",
        "shortcuts.title": "Klávesové zkratky",
        "shortcuts.navigation": "Navigace",
        "shortcuts.rows": "Řádky",
        "shortcuts.close": "Zavřít",
        "shortcuts.dashboard": "Přejít na Přehled",
        "shortcuts.stays": "Přejít na Pobyty",
        "shortcuts.reports": "Přejít na Hlášení",
        "shortcuts.housebook": "Přejít na Domovní knihu",
        "shortcuts.search": "Otevřít hledání",
        "shortcuts.next": "Vybrat další řádek",
        "shortcuts.previous": "Vybrat předchozí řádek",
        "shortcuts.open_row": "Otevřít vybraný řádek",
        "impersonation.previewing": "Náhled pracovního prostoru",
        "impersonation.exit": "Ukončit náhled",
        "notification.open_stay": "Otevřít pobyt",
        "notification.open_property": "Otevřít ubytování",
        "common.back": "Zpět",
        "common.close": "Zavřít",
        "common.apply": "Použít",
        "common.clear": "Vymazat",
        "common.save": "Uložit",
        "common.optional": "(volitelné)",
        "common.actions": "Akce",
        "common.open": "Otevřít",
        "common.restore": "Obnovit",
        "common.archive": "Archivovat",
        "common.edit": "Upravit",
        "common.from": "Od",
        "common.until": "Do",
        "common.auto": "Auto",
        "common.copy": "Kopírovat",
        "common.copied": "Zkopírováno",
        "common.copy_link": "Kopírovat odkaz",
        "common.copy_guest_link": "Kopírovat odkaz pro hosty tohoto pobytu",
        "common.more_actions": "Další akce",
        "common.undo": "Vrátit zpět",
        "submission.accepted": "Přijato",
        "submission.partial": "Částečně přijato",
        "submission.rejected": "Odmítnuto",
        "submission.not_delivered": "Nedoručeno",
        "submission.setup_incomplete": "Nedokončené nastavení",
        "submission.in_progress": "Probíhá",
        "submission.nothing_to_send": "Nic k odeslání",
        "confirm.cancel": "Zrušit",
        "confirm.proceed": "Potvrdit",
        "confirm.archive_stay": "Archivovat tento pobyt? Přesune se do archivu a později ho můžete obnovit.",
        "confirm.archive_property": "Archivovat toto ubytování? Zmizí z přehledu a odkazů pro hosty.",
        "confirm.clear_demo": "Smazat vestavěná ukázková data?",
        "confirm.purge_expired": "Trvale smazat všechny záznamy hostů po uplynutí zákonné doby uchovávání? Nelze vrátit.",
        "confirm.delete_entity": "Smazat tuto právnickou osobu? Nelze vrátit.",
        "confirm.archive_entity": "Archivovat tuto právnickou osobu? Později ji můžete obnovit.",
        "confirm.remove_guest": "Odstranit tento záznam hosta?",
        "confirm.archive_guest": "Archivovat tohoto hosta? Záznam zmizí z exportu domovní knihy, dokud ho neobnovíte.",
        "confirm.disconnect_feed": "Odpojit tento kalendář? Existující pobyty zůstanou.",
        "confirm.regenerate_link": "Vygenerovat nový odkaz a PIN? Stávající odkaz a PIN přestanou fungovat.",
        "confirm.regenerate_pin": "Vygenerovat nový náhodný PIN?",
        "action.failed": "Otevřete pobyt, opravte odmítnutí a odešlete znovu.",
        "action.ready_immediate": "Údaje hostů jsou hotové — odešlou se automaticky po vyplnění.",
        "action.ready": "Údaje hostů jsou hotové. Otevřete pobyt a odešlete, až budete připraveni.",
        "action.incomplete": "Otevřete pobyt a doplňte chybějící údaje hostů.",
        "action.awaiting_guest": "Sdílejte odkaz pro hosty nebo údaje zadejte sami.",
        "action.awaiting_verification": "Formuláře hotové — označte kontrolu dokladu nebo odešlete z pobytu.",
        "action.check_missing": "Otevřete pobyt a zkontrolujte, co chybí.",
        "hint.awaiting_verification": "Volitelně zaznamenejte osobní kontrolu dokladu",
        "hint.awaiting_guest": "Pošlete hostovi odkaz pro check-in, nebo jeho údaje přidejte sami",
        "hint.auto_immediate": "Odešle se automaticky po dokončení všech nahlášených formulářů",
        "hint.nothing_duty": "Nic k odeslání: žádný záznam hosta není předmětem hlášení",
        "hint.need_signature": "Každý cizinec se musí podepsat před odesláním do UbyPortu",
        "hint.need_verification": "Ověřte každého hosta proti pasu před hlášením",
        "hint.nothing_left": "Pro tento pobyt už nic k odeslání není",
        "hint.not_ready": "Doplňte údaje hostů, podpisy a kontrolu pasů před odesláním",
        "hint.ready_to_send": "Odeslat hotové záznamy hostů do UbyPortu",
        "hint.ready_id_optional": "Formuláře hotové — odešlete, nebo nejdřív označte kontrolu dokladu (zapíše se při odeslání)",
        "hint.demo_preview": "Ukázkové pobyty se neodesílají — pro hlášení použijte skutečnou nemovitost",
        "deadline.arrives_days": "přijíždí za %(n)s dní",
        "deadline.arrives_days.one": "přijíždí za 1 den",
        "deadline.arrives_days.few": "přijíždí za %(n)s dny",
        "deadline.days_left": "zbývá %(n)s dní",
        "deadline.days_left.one": "zbývá 1 den",
        "deadline.days_left.few": "zbývají %(n)s dny",
        "deadline.overdue_days": "po termínu o %(n)s dní",
        "deadline.overdue_days.one": "po termínu o 1 den",
        "deadline.overdue_days.few": "po termínu o %(n)s dny",
        "deadline.hours_left": "zbývá %(n)s h",
        "deadline.overdue_hours": "po termínu o %(n)s h",
        "env.mock_title": "Policii se nic nehlásí",
        "env.mock_body": (
            "Tento účet je nastavený na cvičný server, takže záznamy označené jako "
            "„Nahlášeno“ nebyly nikdy podány. Než se na to spolehnete, nastavte "
            "UBYHOST_UBYPORT_ENV na test nebo prod."
        ),
        "env.mock_production_title": "Produkční nasazení stále běží na cvičném serveru",
        "env.mock_production_body": (
            "Hosté se registrují doopravdy, ale na cizineckou policii nic nedorazí, takže "
            "u každého pobytu běží tři pracovní dny bez hlášení. Nastavte hned "
            "UBYHOST_UBYPORT_ENV=prod."
        ),
        "status.failed": "Odmítnuto",
        "status.reported": "Nahlášeno",
        "status.ready": "Připraveno k hlášení",
        "status.incomplete": "Neúplné",
        "status.not_required": "Výjimka",
        "status.awaiting_guest_short": "Čeká na hosta",
        "dashboard.title": "Přehled",
        "dashboard.lede": "Vaše hlášení seřazená podle naléhavosti a dalšího kroku.",
        "dashboard.sync_calendars": "Synchronizovat kalendáře",
        "dashboard.last_synced": "Naposledy synchronizováno %(when)s UTC",
        "dashboard.focus.overdue": "Po termínu",
        "dashboard.focus.urgent": "Termín teď",
        "dashboard.focus.next_up": "Další na řadě",
        "dashboard.focus.guest_forms": "%(filled)s / %(expected)s formulářů hostů",
        "dashboard.focus.open_stay": "Otevřít pobyt",
        "dashboard.focus.add_guest": "Přidat hosta ručně",
        "dashboard.focus.copy_link": "Kopírovat odkaz pro hosty",
        "dashboard.stats.past_deadline": "Po termínu",
        "dashboard.stats.need_action": "Vyžaduje akci",
        "dashboard.stats.waiting_guest": "Čeká na hosta",
        "dashboard.stats.ready": "Připraveno k hlášení",
        "dashboard.setup.title": "Dokončit nastavení",
        "dashboard.setup.lede": "Tato ubytování nemohou hlásit, dokud nejsou kompletní registrační údaje.",
        "dashboard.setup.view_properties": "Zobrazit ubytování",
        "dashboard.setup.items": "%(count)s položka k opravě",
        "dashboard.setup.items_plural": "%(count)s položek k opravě",
        "dashboard.empty.no_stays": "V aktuálním okně nejsou pobyty. Kalendáře nemají rezervace, nebo ještě nebyly synchronizovány.",
        "dashboard.empty.sync_now": "Synchronizovat kalendáře",
        "dashboard.section.needs_action": "Vyžaduje akci",
        "dashboard.section.waiting": "Čeká na hosty",
        "dashboard.section.upcoming": "Nadcházející příjezdy",
        "dashboard.section.completed": "Nedávno dokončené",
        "dashboard.section.view_stays": "Všechny pobyty",
        "dashboard.section.view_reports": "Zobrazit hlášení",
        "dashboard.queue.empty.action": "Máte hotovo. Teď nic nevyžaduje akci.",
        "dashboard.queue.empty.waiting": "Žádné nevyřízené formuláře hostů.",
        "dashboard.queue.empty.default": "Tady nic nečeká na pozornost.",
        "dashboard.table.stay": "Pobyt",
        "dashboard.table.deadline": "Termín",
        "dashboard.table.guests": "Hosté",
        "dashboard.table.reporting": "Hlášení",
        "dashboard.table.deadline_by": "do %(when)s",
        "dashboard.row.open_stay": "Otevřít pobyt",
        "dashboard.row.add_guest": "Přidat hosta",
        "stays.title": "Pobyty",
        "stays.lede": "Pobyty z kalendářů a ruční rezervace, nejdříve nejbližší příjezd.",
        "stays.add_stay": "Přidat pobyt",
        "stays.add_panel.title": "Přidat pobyt ručně",
        "stays.add_panel.lede": "Pro přímé rezervace, telefonické objednávky nebo cokoli mimo kalendář.",
        "stays.add_panel.apartment": "Ubytování",
        "stays.add_panel.arrival": "Příjezd",
        "stays.add_panel.departure": "Odjezd",
        "stays.add_panel.guests": "Počet hostů",
        "stays.add_panel.label": "Popisek",
        "stays.add_panel.label_ph": "Přímá rezervace – Novák",
        "stays.add_panel.email": "E-mail hosta",
        "stays.add_panel.create": "Vytvořit pobyt",
        "stays.chip.upcoming": "Aktuální a budoucí",
        "stays.chip.past": "Minulé",
        "stays.chip.all": "Všechna data",
        "stays.chip.archive": "Archiv",
        "stays.archive_note": "Archivované pobyty jsou skryté z denní práce, ale zůstávají k dispozici. Chybné záznamy můžete obnovit.",
        "stays.filter.apartment": "Ubytování",
        "stays.filter.all_apartments": "Vše",
        "stays.filter.state": "Stav pobytu",
        "stays.filter.state.active": "Aktivní",
        "stays.filter.state.cancelled": "Zrušený",
        "stays.filter.state.ignored": "Ignorovaný",
        "stays.filter.state.all": "Vše",
        "stays.filter.from": "Pobyt od",
        "stays.filter.to": "Pobyt do",
        "stays.filter.save_view": "Uložit tento pohled",
        "stays.filter.saved": "Pohled uložen",
        "stays.filter.saved_views": "Uložené pohledy",
        "stays.view.label": "Zobrazení pobytů",
        "stays.view.list": "Seznam",
        "stays.view.timeline": "Časová osa",
        "stays.table.stay": "Pobyt",
        "stays.table.apartment": "Ubytování",
        "stays.table.source": "Zdroj",
        "stays.table.guests": "Hosté",
        "stays.table.reporting": "Hlášení",
        "stays.table.deadline": "Termín",
        "stays.table.nights": "%(count)s nocí",
        "stays.table.in_house": "Ubytováni",
        "stays.table.portal": "portál →",
        "stays.row.open": "Otevřít pobyt",
        "stays.row.add_guest": "Přidat hosta",
        "stays.row.restore": "Obnovit",
        "stays.pagination.showing": "Zobrazen %(from)s–%(to)s z %(total)s pobytu.",
        "stays.pagination.showing_plural": "Zobrazeno %(from)s–%(to)s z %(total)s pobytů.",
        "stays.pagination.prev": "← Předchozí",
        "stays.pagination.next": "Další →",
        "stays.pagination.label": "Strana %(page)s z %(pages)s",
        "stays.empty.archive": "Žádné archivované pobyty. Chyby archivujte z řádku pobytu.",
        "stays.empty.filter": "Žádný pobyt neodpovídá filtru.",
        "stays.empty.show_all": "Zobrazit všechna data",
        "stays.empty.none": "Zatím žádné pobyty. Připojte kalendář k ubytování nebo použijte Přidat pobyt.",
        "stays.empty.go_apartments": "Přejít na ubytování",
        "stays.empty.no_apartments": "Zatím nemáte ubytování, takže není co zobrazit.",
        "stays.empty.add_first": "Přidat první ubytování",
        "stay.detail.back": "Zpět na pobyty",
        "stay.claim.title": "Přiřazení hosta",
        "stay.claim.unclaimed": "Tento pobyt zatím nikdo e-mailem nepřevzal.",
        "stay.claim.provisional": "Čeká se na potvrzení e-mailu %(email)s.",
        "stay.claim.claimed": "Přiřazeno k %(email)s.",
        "stay.claim.locked": "Formuláře hostů jsou uzamčené. Znovu otevřete, pokud host ještě potřebuje přístup.",
        "stay.claim.reopen": "Znovu otevřít přístup hostům",
        "stay.claim.release": "Uvolnit přiřazení",
        "stay.claim.release_confirm": "Uvolnit tento pobyt, aby ho mohl převzít jiný e-mail?",
        "stay.detail.copy_link": "Kopírovat odkaz pro hosty",
        "stay.detail.link_copied": "Odkaz zkopírován",
        "stay.detail.cta.send": "Odeslat do UbyPortu",
        "stay.detail.cta.fix": "Opravit odmítnutí",
        "stay.detail.cta.view_reports": "Zobrazit hlášení",
        "stay.detail.cta.verify": "Ověřit pasy",
        "stay.detail.cta.open": "Otevřít pobyt",
        "stay.detail.cta.add_guest": "Přidat hosta",
        "stay.detail.next_step": "Další krok",
        "stay.detail.ready_count": "%(count)s záznam(ů) hostů připraveno k hlášení.",
        "stay.detail.metric.deadline": "Termín hlášení",
        "stay.detail.metric.deadline_note": "Tři pracovní dny po příjezdu končí %(when)s.",
        "stay.detail.metric.guests": "Formuláře hostů",
        "stay.detail.metric.guests_note": "%(sent)s nahlášeno · %(reportable)s podléhá povinnosti",
        "stay.detail.metric.set_expected": "Nastavit očekávaný počet hostů",
        "stay.detail.metric.reporting": "Hlášení",
        "stay.detail.note.verify": "Formuláře jsou hotové. Doklad můžete zkontrolovat osobně a výsledek zaznamenat.",
        "stay.detail.note.ready_immediate": "Všechny nahlášené formuláře jsou hotové. Odeslání do UbyPortu začne automaticky bez ověření.",
        "stay.detail.note.ready_manual": "Formuláře jsou hotové. Zkontrolujte údaje níže a odešlete, až budete připraveni.",
        "stay.detail.note.ready_scheduled": "Formuláře jsou hotové. Odešlou se %(hours)s h po dokončení, nebo použijte Odeslat.",
        "stay.detail.note.automation": "Automatizace:",
        "stay.detail.note.immediate": "okamžitě po dokončení všech nahlášených formulářů",
        "stay.detail.note.scheduled": "%(hours)s h po dokončení všech nahlášených formulářů",
        "stay.detail.note.manual": "pouze ručně",
        "stay.detail.guests.title": "Hosté",
        "stay.detail.guests.lead": "vedoucí",
        "stay.detail.guests.reported": "Nahlášeno",
        "stay.detail.guests.exempt": "Výjimka",
        "stay.detail.guests.rejected": "Odmítnuto",
        "stay.detail.guests.rejected_final": "Odmítnuto, finální",
        "stay.detail.guests.incomplete": "Neúplné",
        "stay.detail.guests.verify": "Ověřit pas",
        "stay.detail.guests.ready": "Připraveno",
        "stay.detail.guests.edit": "Upravit údaje",
        "stay.detail.guests.pdf": "PDF registračního formuláře",
        "stay.detail.guests.born": "Narozen",
        "stay.detail.guests.nationality": "Národnost",
        "stay.detail.guests.document": "Doklad",
        "stay.detail.guests.visa": "vízum %(number)s",
        "stay.detail.guests.purpose": "Účel pobytu",
        "stay.detail.guests.residence": "Bydliště v zahraničí",
        "stay.detail.guests.staying": "Pobyt",
        "stay.detail.guests.signature": "Podpis",
        "stay.detail.guests.signed": "Podepsáno",
        "stay.detail.guests.not_signed": "Nepodepsáno",
        "stay.detail.guests.entered_by": "Zadal",
        "stay.detail.guests.note": "Poznámka: %(text)s",
        "stay.detail.guests.empty": "Zatím žádný host nevyplnil formulář.",
        "stay.detail.guests.empty_hint": "Zkopírujte odkaz pro hosty výše, nebo údaje zadejte sami.",
        "stay.detail.reports.title": "Hlášení odeslaná pro tento pobyt",
        "stay.detail.reports.when": "Kdy",
        "stay.detail.reports.outcome": "Výsledek",
        "stay.detail.reports.stamp": "Razítko doručenky",
        "stay.detail.reports.open": "Otevřít hlášení",
        "stay.detail.settings.title": "Nastavení pobytu",
        "stay.detail.settings.lede": "Počet hostů, stav pobytu a vaše soukromé poznámky. Šablony zpráv najdete v",
        "stay.detail.settings.guest_links": "Odkazy pro hosty",
        "stay.detail.settings.expected": "Očekávaný počet hostů",
        "stay.detail.settings.expected_declared": "Vedoucí host uvedl %(count)s. Číslo zde přepíše jeho údaj.",
        "stay.detail.settings.expected_blank": "Kalendář neposkytuje počet. Nechte prázdné, aby ho uvedl vedoucí host.",
        "stay.detail.settings.email": "E-mail hosta",
        "stay.detail.settings.email_hint": "Uloženo pro vaši referenci. Automatické zprávy hostům používají e-mail, který převezme odkaz pro hosty.",
        "stay.detail.settings.host_only": "(pouze pro hostitele)",
        "stay.detail.settings.state": "Stav pobytu",
        "stay.detail.settings.state.active": "Aktivní",
        "stay.detail.settings.state.cancelled": "Zrušený",
        "stay.detail.settings.state.ignored": "Není pobyt hostů",
        "stay.detail.settings.state_hint": "„Není pobyt hostů“ odstraní položku z denní práce, ale zachová ji při synchronizaci kalendáře. Obnovíte výběrem Aktivní.",
        "stay.detail.settings.note": "Soukromá poznámka",
        "stay.detail.inline.title": "Upravit údaje pobytu",
        "stay.detail.inline.label": "Interní popisek",
        "stay.detail.inline.guests": "Očekávaní hosté",
        "stay.detail.inline.saved": "Uloženo",
        "stay.detail.inline.error": "Uložení se nepodařilo. Zkuste to znovu.",
        "stay.detail.menu.restore": "Obnovit z archivu",
        "stay.detail.menu.archive": "Archivovat pobyt",
        "stay.detail.menu.guest_links": "Odkazy a šablony pro hosty",
        "apartments.title": "Ubytování",
        "apartments.lede": "Každé ubytovací zařízení má vlastní registraci v UbyPortu, kalendáře a odkaz pro hosty.",
        "apartments.entities_link": "Právnické osoby",
        "apartments.add": "Přidat ubytování",
        "apartments.table.property": "Ubytování",
        "apartments.table.entity": "Právnická osoba",
        "apartments.table.idub": "IDUB",
        "apartments.table.calendars": "Kalendáře",
        "apartments.table.stays": "Pobyty",
        "apartments.table.automation": "Automatizace",
        "apartments.table.setup": "Připravenost",
        "apartments.inactive": "Neaktivní",
        "apartments.automation.immediate": "Okamžitě",
        "apartments.automation.scheduled": "+%(hours)s h",
        "apartments.automation.manual": "Ruční",
        "apartments.setup.fix": "%(count)s k opravě",
        "apartments.setup.calendar": "Připojit kalendář",
        "apartments.setup.ready": "Může hlásit",
        "apartments.row.edit": "Upravit",
        "apartments.empty.lede": "Zatím žádná ubytování. Nejprve přidejte právnickou osobu, pak vytvořte ubytování.",
        "apartments.empty.entity": "Přidat právnickou osobu",
        "apartments.empty.add": "Přidat první ubytování",
        "apartments.archived.title": "Archivované",
        "apartments.archived.lede": "Skryté z přehledu a odkazů pro hosty. Historie zůstává.",
        "apartments.archived.when": "Archivováno",
        "archive.title": "Archiv",
        "archive.lede": "Obnovte archivované pobyty, ubytování a záznamy domovní knihy.",
        "archive.empty": "Zatím nic v archivu.",
        "archive.chip.all": "Vše",
        "archive.chip.stays": "Pobyty",
        "archive.chip.properties": "Ubytování",
        "archive.chip.guests": "Domovní kniha",
        "archive.section.stays": "Archivované pobyty",
        "archive.section.properties": "Archivovaná ubytování",
        "archive.section.guests": "Archivované záznamy knihy",
        "archive.col.when": "Archivováno",
        "archive.col.stay": "Pobyt",
        "archive.col.property": "Ubytování",
        "archive.col.guest": "Host",
        "archive.col.name": "Název",
        "archive.col.stays_count": "Pobyty",
        "archive.page_lede": "Vše, co jste archivovali, na jednom místě. Obnovte chybu nebo projděte staré záznamy.",
        "archive.retention_note": (
            "Archivace skryje položky z každodenní práce, ale historii ponechá. "
            "Trvalé smazání hostů provede pouze šestiletá retence v Nastavení."
        ),
        "archive.stay_moved": "Pobyt přesunut do archivu.",
        "archive.chip.all_count": "Vše (%(count)s)",
        "archive.chip.stays_count": "Pobyty (%(count)s)",
        "archive.chip.properties_count": "Ubytování (%(count)s)",
        "archive.chip.housebook_count": "Domovní kniha (%(count)s)",
        "archive.chip.entities_count": "Právnické osoby (%(count)s)",
        "archive.empty_detailed": (
            "Zatím nic v archivu. Pobyty, ubytování, záznamy knihy a právnické osoby můžete archivovat na jejich stránkách."
        ),
        "archive.empty.stays": "Žádné archivované pobyty.",
        "archive.empty.properties": "Žádná archivovaná ubytování.",
        "archive.empty.housebook": "Žádné archivované záznamy knihy.",
        "archive.empty.entities": "Žádné archivované právnické osoby.",
        "archive.hint.stays": "Skryté ze seznamu pobytů. Historie hlášení zůstává.",
        "archive.hint.properties": "Skryté z přehledu a odkazů pro hosty. Historie zůstává.",
        "archive.hint.housebook": "Chybné importy nebo duplicity obnovíte zde.",
        "archive.hint.entities": "Skryté z výběru u ubytování, dokud je neobnovíte.",
        "archive.section.entities": "Archivované právnické osoby",
        "settings.archive_hint_extended": (
            "Archivované pobyty, ubytování, záznamy knihy a právnické osoby jsou na jednom místě. "
            "Obnovte, co jste skryli omylem. Trvalé smazání hostů provede pouze retence níže."
        ),
        "settings.nav.overview": "Přehled",
        "settings.nav.mail": "E-maily hostům",
        "settings.lede": "Pokročilý stav systému, zabezpečení, ochrana údajů a protokol aktivit.",
        "settings.nav.retention": "Ochrana údajů",
        "settings.nav.archive": "Archiv",
        "settings.nav.audit": "Protokol aktivit",
        "settings.nav.ubyport": "UbyPort a prostředí",
        "settings.nav.account": "Váš účet",
        "settings.nav.legal": "Provozovatel software",
        "settings.nav.version": "Verze",
        "settings.archive_link": "Otevřít archiv",
        "settings.archive_hint": "Obnovte archivované pobyty, ubytování a záznamy domovní knihy.",
    },
}

# Screen-level copy added by the shared interface system. Keeping these keys
# together makes parity review practical while older catalogs are consolidated.
_INTERFACE_STRINGS = {
    "en": {
        "common.all": "All",
        "common.filter": "Filter",
        "housebook.title": "House book",
        "housebook.lede": (
            "Every guest record and stay date. Keep this register for six years after "
            "the last entry and produce it during a police inspection."
        ),
        "housebook.apartment": "Property",
        "housebook.from": "Stays from",
        "housebook.until": "Stays until",
        "housebook.actions": "House book actions",
        "housebook.stay": "Stay",
        "housebook.guest": "Guest",
        "housebook.born": "Born",
        "housebook.nationality": "Nationality",
        "housebook.document": "Document",
        "housebook.residence": "Residence abroad",
        "housebook.purpose": "Purpose",
        "housebook.signed": "Signed",
        "housebook.reported": "Reported",
        "housebook.visa": "visa %(number)s",
        "housebook.signed_yes": "Signed",
        "housebook.signed_no": "Not signed",
        "housebook.not_sent": "Not yet sent",
        "housebook.pdf": "Signed form PDF",
        "housebook.entries": "%(count)s entries.",
        "housebook.empty": "No entries match this filter. The house book fills as guest forms are completed.",
        "housebook.archived_title": "Archived entries",
        "housebook.archived_lede": "Mistaken entries and duplicates can be restored here.",
        "housebook.archived": "Archived",
        "automation.title": "Automation & UbyPort",
        "automation.lede": "Choose when completed guest registrations are sent and manage each property's police web-service credentials.",
        "automation.to_fix": "%(count)s to fix",
        "automation.ready": "Ready",
        "automation.timing_title": "When to send to UbyPort",
        "automation.timing_help": "Immediate sends when all declared forms are complete. Delayed sends after the chosen number of hours from completion, giving you time to review. Both are automatic and do not wait for verification. Rejected records are never silently retried.",
        "automation.timing_label": "Send timing",
        "automation.mode.manual": "Only when I press send",
        "automation.mode.scheduled": "Automatically after a delay from completion",
        "automation.mode.immediate": "Immediately when all forms are complete",
        "automation.hours": "Hours after completion",
        "automation.default_purpose": "Default purpose of stay",
        "automation.credentials_title": "UbyPort web-service credentials",
        "automation.credentials_help": "These are not your normal UbyPort login details. Request UBY-WS access from reguby@pcr.cz.",
        "automation.sample_pdf": "Open annotated sample PDF",
        "automation.or_use": "or use the",
        "automation.full_setup": "full property setup",
        "automation.mark": "Facility abbreviation",
        "automation.facility_name": "Facility name in UbyPort",
        "automation.contact": "Contact at registration",
        "automation.login": "Web-service login",
        "automation.password": "Web-service password",
        "automation.password_saved": "Saved — not shown again.",
        "automation.password_keep": "Leave empty to keep the saved password",
        "automation.password_paste": "Paste from the police letter",
        "automation.password_replace": "Fill this only when replacing the police-issued password. Otherwise leave it empty.",
        "automation.password_new": "Required once; encrypted at rest and never shown again after save.",
        "automation.save": "Save %(property)s",
        "automation.test": "Test connection",
        "automation.refresh": "Refresh code lists",
        "automation.saved_credentials_help": "Connection tests use the last saved credentials. Save first if you changed them.",
        "automation.empty": "No active properties yet. Add a property, then configure reporting here.",
        "apartment.form.active.label": 'Active — sync calendars and report guests for this apartment',
        "apartment.form.addr.house_no": 'House number (č. popisné)',
        "apartment.form.addr.house_no_hint": 'Up to 4 digits. For an evidence number use E123.',
        "apartment.form.addr.obec": 'Municipality (obec)',
        "apartment.form.addr.obec_cast": 'Part of municipality',
        "apartment.form.addr.okres": 'District (okres)',
        "apartment.form.addr.okres_hint": 'In Prague use the city district.',
        "apartment.form.addr.orient_no": 'Orientation number',
        "apartment.form.addr.orient_no_hint": 'Up to 3 digits plus one optional letter.',
        "apartment.form.addr.street": 'Street',
        "apartment.form.addr.zip": 'Postcode',
        "apartment.form.addr.zip_hint": '5 digits.',
        "apartment.form.address.lede_after": ') rather than retyping a one-line address.',
        "apartment.form.address.lede_before": 'UbyPort stores the address as separate parts. Copy them from your registration (',
        "apartment.form.address.lede_form_name": 'Žádost o registraci ubytovacího zařízení',
        "apartment.form.address.title": 'Address of the accommodation facility',
        "apartment.form.archive_help": 'Hide it without deleting records. Useful for duplicate or unused apartments.',
        "apartment.form.archive_title": 'Archive this property',
        "apartment.form.archived_help": 'Hidden from the dashboard and guest links. History is kept.',
        "apartment.form.automation.editing_lede_after": ' page so there is one place to manage reporting for this property.',
        "apartment.form.automation.editing_lede_before": 'Send timing, UbyPort credentials, and the default purpose of stay are configured on the ',
        "apartment.form.automation.hours_hint": 'For example, 24 hours gives you a review window; sending still happens automatically without verification.',
        "apartment.form.automation.mode.scheduled": 'Automatically after a set number of hours from completion',
        "apartment.form.automation.new_lede": 'The operating rules let you pick how much the app does on its own, and require that the choice is yours. Whatever you choose, a rejected record is never silently retried.',
        "apartment.form.automation.open": 'Open automation settings',
        "apartment.form.automation.purpose_hint": 'Pre-selected in the guest form. Tourism fits almost all short-term rentals.',
        "apartment.form.automation.summary.immediate": 'Immediately after all declared forms are complete',
        "apartment.form.automation.summary.manual": 'Only when you press send',
        "apartment.form.back": 'Back to properties',
        "apartment.form.back_list": 'Back to apartments',
        "apartment.form.basics.title": 'Basic details',
        "apartment.form.blocking_title": 'This apartment cannot report to UbyPort yet.',
        "apartment.form.calendars.add_sync": 'Add and sync',
        "apartment.form.calendars.connect_title": 'Connect a calendar',
        "apartment.form.calendars.empty": 'No calendars connected yet.',
        "apartment.form.calendars.lede": 'Airbnb and Booking.com iCal feeds give dates only — no name, no e-mail, no headcount. That is enough to know somebody is arriving, which is all the app needs to start chasing the data.',
        "apartment.form.calendars.own_name_label": 'Your name for it',
        "apartment.form.calendars.own_name_ph": 'Airbnb – Vinohrady',
        "apartment.form.calendars.portal_ph": 'Airbnb / Booking.com / Agoda / Vrbo',
        "apartment.form.calendars.url_hint": 'Airbnb: Calendar → Availability → Connect calendars. Booking.com: Rates & Availability → Sync calendars. Paste the whole link.',
        "apartment.form.calendars.url_label": 'iCal export URL',
        "apartment.form.calendars.url_ph": 'https://www.airbnb.com/calendar/ical/…',
        "apartment.form.city_en.hint": 'Shown to guests next to the registered facility name, e.g. "Prague".',
        "apartment.form.city_en.label": 'City name in English',
        "apartment.form.codelists_bundled": 'Using the bundled country list until the first refresh.',
        "apartment.form.codelists_cached": 'Code lists cached %(date)s.',
        "apartment.form.create": 'Create apartment',
        "apartment.form.credentials_actions_help": 'Both use the saved credentials, so save first.',
        "apartment.form.entity.hint": 'The IČO registered in UbyPort for this address. It is also the data controller named in the privacy notice guests are shown, so it cannot be left empty if you want that notice to be complete.',
        "apartment.form.entity.label": 'Operating legal entity',
        "apartment.form.feed.last_sync": 'Last sync',
        "apartment.form.feed.name": 'Name',
        "apartment.form.feed.portal": 'Portal',
        "apartment.form.feed.status.error": 'Error',
        "apartment.form.feed.status.never": 'Never',
        "apartment.form.feed.status.ok": 'OK',
        "apartment.form.feed.url": 'URL',
        "apartment.form.guest_link.lede": 'There is exactly one link per apartment. The same string goes into every automated arrival message — Airbnb, Booking.com, direct bookings — because the guest picks their own dates when they open it. It never changes, so you set it up once and never touch it again.',
        "apartment.form.guest_link.message_help": 'Paste the same text on Airbnb, Booking.com and in direct-booking e-mails. There is nothing portal-specific to change.',
        "apartment.form.guest_link.new_help": 'A unique guest link and PIN are generated once you save the apartment.',
        "apartment.form.guest_link.pin_hint": 'Six digits (or legacy four) guests enter before the form opens. Change it here, or generate a random one below.',
        "apartment.form.guest_link.pin_ph": '000000',
        "apartment.form.guest_link.regenerate_link": 'Generate a new link',
        "apartment.form.guest_link.regenerate_link_help": 'Only if the old link leaked. This also creates a new PIN — update your portal messages.',
        "apartment.form.guest_link.regenerate_pin_help": 'Keep the same link but change the PIN guests must enter.',
        "apartment.form.guest_link.regenerate_pin_title": 'Generate a new PIN only',
        "apartment.form.guest_link.window_hint": 'Only stays whose check-in date falls in this window are listed on the apartment link. Incomplete past stays remain reachable through their stay-specific link unless you lock guest access.',
        "apartment.form.guest_link.window_label": 'Show stays starting within (days)',
        "apartment.form.guest_message.hint": 'Shown on this property’s guest registration form. Use it for a welcome note or important property-specific guidance; do not include access codes or other secrets.',
        "apartment.form.guest_message.label": 'Custom message for guests',
        "apartment.form.guest_message.placeholder": 'For example: Welcome! Please complete this form before arrival.',
        "apartment.form.passport_policy.label": 'Passport or ID photo from the guest',
        "apartment.form.passport_policy.hint": 'Off means the guest form does not request a document image. Required asks foreign guests for a temporary upload for your optional review; it is never sent to Police.',
        "apartment.form.passport_policy.off": 'Off (default) — host checks the document at arrival',
        "apartment.form.passport_policy.required": 'Required for foreign guests filling the online form',
        "apartment.form.internal_name.hint": 'Only for your own orientation — guests never see it.',
        "apartment.form.internal_name.label": 'Your name for this apartment',
        "apartment.form.lede": 'Complete the sections below so guest registration and UbyPort reporting work reliably.',
        "apartment.form.nav.address": '2. Address',
        "apartment.form.nav.aria": 'Property setup sections',
        "apartment.form.nav.automation": '4. Automation',
        "apartment.form.nav.automation_ubyport": '3. Automation & UbyPort',
        "apartment.form.nav.basics": '1. Property',
        "apartment.form.nav.calendars": '5. Calendars',
        "apartment.form.nav.guest_link": '4. Guest link',
        "apartment.form.nav.guest_link_new": '5. Guest link',
        "apartment.form.nav.ubyport": '3. UbyPort',
        "apartment.form.new_property": 'New property',
        "apartment.form.notes.hint": 'Only you see this — never shown to guests.',
        "apartment.form.notes.label": 'Your notes',
        "apartment.form.notes.title": 'Private notes',
        "apartment.form.refresh_codelists": 'Refresh code lists from UbyPort',
        "apartment.form.test_connection": 'Test the connection',
        "apartment.form.title_new": 'New apartment',
        "apartment.form.ubyport.contact_hint": 'E-mail/phone from original registration or UbyPort portal — not on the WS password letter.',
        "apartment.form.ubyport.idub_hint": 'PDF line “IDUB:” — 12–14 digits, character for character.',
        "apartment.form.ubyport.intro": 'These are not your normal UbyPort portal login (ub…). Use the separate letter titled “Výpis z databáze přihlašovacích údajů” (web-service / robotické vkládání) — usually a PDF whose filename contains your IDUB and UBY-WS.',
        "apartment.form.ubyport.login_hint": 'PDF “Přihlašovací jméno:” — copy exactly (including _ or digits).',
        "apartment.form.ubyport.map.contact": 'E-mail or phone you gave on the original UbyPort accommodation registration — often not printed on the web-service PDF. Same value as in the UbyPort portal profile for this facility. UbyPort may reject reports if this is wrong; leave blank only if you never registered one.',
        "apartment.form.ubyport.map.contact_label": 'Contact (optional here)',
        "apartment.form.ubyport.map.idub": 'Line IDUB: on the web-service PDF.',
        "apartment.form.ubyport.map.login": 'Line Přihlašovací jméno: (e.g. UBY-WS_MLJNO).',
        "apartment.form.ubyport.map.mark": 'Five letters assigned when the facility was registered — not on the cover e-mail. Often the same five letters after UBY-WS_ in the web-service login (e.g. login UBY-WS_MLJNO → zkratka MLJNO). Confirm in the UbyPort portal under facility details or your original registration decision if unsure.',
        "apartment.form.ubyport.map.mark_label": 'Facility abbreviation (zkratka)',
        "apartment.form.ubyport.map.name": 'Line Ubytovací zařízení: on the web-service PDF — copy the first line only (before any bracket with Praha/address). Not your Airbnb title. Max 35 characters; the police register uses the short legal name.',
        "apartment.form.ubyport.map.password": 'Line Přístupové heslo: on the same PDF — enter once, then leave blank on later saves.',
        "apartment.form.ubyport.map_summary": 'Where each UbyHost field comes from (read this once)',
        "apartment.form.ubyport.mark_hint": 'Five letters on file with the police (often = letters after UBY-WS_ in your login).',
        "apartment.form.ubyport.mark_label": 'Facility abbreviation (zkratka)',
        "apartment.form.ubyport.mismatch_help": 'UbyPort compares IDUB, zkratka, name, address, and contact to the register. A typo or an Airbnb listing name fails even when the web-service login works — you often only see that on the first real submission.',
        "apartment.form.ubyport.name_hint": 'PDF “Ubytovací zařízení:” — first line only, not your listing title; max 35 characters.',
        "apartment.form.ubyport.password_edit_hint": 'Only type here if the Foreign Police sent you a new password. Saving the rest of this form without touching this field keeps the password you already stored.',
        "apartment.form.ubyport.password_new_hint": 'Enter it once when you first set up reporting. It is encrypted before it is written to disk and is never displayed again after save.',
        "apartment.form.ubyport.password_saved": 'Saved — UbyHost keeps it encrypted and does not show it again.',
        "apartment.form.ubyport.sample_help": ' — fictional police letter with SAMPLE watermarks; shows every value to copy into UbyHost, including zkratka and contact that real WS PDFs often omit.',
        "common.none": '— none —',
        "common.remove": 'Remove',
        "common.save_changes": 'Save changes',
        "common.select": '— select —',
        "guest.admin.back_to_stay": 'Back to stay',
        "guest.admin.banner.rejected_help": 'Correct the data and save — that puts it back in the queue.',
        "guest.admin.banner.rejected_title": 'UbyPort rejected this record.',
        "guest.admin.banner.sent_help": 'Editing changes the house book only. Sending it again creates a duplicate, which the police count against you, so it needs a deliberate confirmation below.',
        "guest.admin.banner.sent_title": 'Already reported to the Foreign Police.',
        "guest.admin.banner.sent_title_at": 'Already reported to the Foreign Police on %(at)s.',
        "guest.admin.birth_date": 'Date of birth',
        "guest.admin.birth_date_hint": 'Type the 8 digits from the passport — slashes are added automatically. Use 00 for an unknown day or month.',
        "guest.admin.birth_date_ph": 'DD/MM/YYYY',
        "guest.admin.danger.summary": 'Advanced and dangerous actions',
        "guest.admin.document": 'Travel document number',
        "guest.admin.document_hint": "6–30 letters and digits, or INPASS for a child in a parent's passport.",
        "guest.admin.download_pdf": 'Download signed form',
        "guest.admin.given_names": 'Given name(s)',
        "guest.admin.identity.title": 'Identity',
        "guest.admin.nationality_hint": 'Czech nationals are recorded in the house book but never sent to the police.',
        "guest.admin.note": 'Note',
        "guest.admin.note_optional": '(optional, max 255)',
        "guest.admin.passport_pdf_title": 'Passport PDF',
        "guest.admin.passport_photo_alt": 'Passport photo',
        "guest.admin.remove.submit": 'Delete this guest',
        "guest.admin.remove.title": 'Remove',
        "guest.admin.res_city": 'City',
        "guest.admin.res_country": 'Country',
        "guest.admin.res_street": 'Street and number',
        "guest.admin.resend.confirm": 'I understand this may create a duplicate record.',
        "guest.admin.resend.help": 'UbyPort files duplicates under errors that cannot be corrected, and repeatedly sending them without reason can cost you web-service access. Only do this if you have a genuine reason — for example the connection dropped mid-transfer and you are not sure the data arrived.',
        "guest.admin.resend.submit": 'Re-send to UbyPort',
        "guest.admin.resend.title": 'Send this record again',
        "guest.admin.stay.title": 'Stay',
        "guest.admin.stay_from": 'Accommodated from',
        "guest.admin.stay_to": 'Accommodated until',
        "guest.admin.submit_add": 'Add guest',
        "guest.admin.surname": 'Surname',
        "guest.admin.title_add": 'Add guest',
        "guest.admin.title_edit": 'Edit guest',
        "guest.admin.visa": 'Visa number',
        "settings.privacy.add_contact": 'add one',
        "settings.privacy.no_contact_prefix": 'No contact e-mail on:',
        "settings.privacy.no_contact_suffix": ' so guests can exercise their rights.',
        "settings.privacy.no_entity_prefix": 'No legal entity on:',
        "settings.privacy.no_entity_suffix": '— guests cannot be told who controls their data.',
        "settings.version_line": 'UbyHost %(version)s',
        "users.create.lede": 'A secure temporary password is generated for you. Copy it before creating the account.',
        "users.create.name": 'Name',
        "users.create.password_hint": 'They must replace it at first login.',
        "users.create.regenerate": 'Regenerate',
        "users.create.submit": 'Create host',
        "users.create.temporary_password": 'Temporary password',
        "users.create.title": 'Create a host',
        "users.create.username": 'Username',
        "users.create.username_hint": 'Lowercase letters, numbers, dots, dashes, and underscores.',
        "users.credential.choose_on_login": 'They will be asked to choose their own password the first time they sign in.',
        "users.credential.copy_now": 'Copy this now - it is not stored in readable form and cannot be shown again.',
        "users.credential.created_title": 'User created',
        "users.credential.old_password_invalid": 'The old password no longer works.',
        "users.credential.reset_title": 'Password reset',
        "users.credential.temporary_password": 'Temporary password',
        "users.credential.username": 'Username',
        "users.lede": 'Create a private workspace for each host. Passwords are hashed and can be reset, never viewed.',
        "users.menu.aria": 'User actions',
        "users.menu.disable": 'Disable',
        "users.menu.enable": 'Enable',
        "users.menu.open_workspace": 'Open workspace',
        "users.menu.reset_password": 'Reset password',
        "users.reset.lede_after": '. Copy it before saving.',
        "users.reset.lede_before": 'A new temporary password for ',
        "users.reset.save": 'Save password',
        "users.reset.temporary_password": 'Temporary password',
        "users.reset.title": 'Reset password',
        "users.status.active": 'Active',
        "users.status.disabled": 'Disabled',
        "users.status.temporary_password": 'Temporary password',
        "users.table.properties": 'Properties',
        "users.table.role": 'Role',
        "users.table.status": 'Status',
        "users.table.user": 'User',
        "users.title": 'Users',
        "entities.title": "Legal entities",
        "entities.name": "Name",
        "entities.name_placeholder": "As in the commercial or trade register",
        "entities.seat": "Registered seat",
        "entities.seat_placeholder": "Street, number, postcode, city",
        "entities.ico": "Company ID (IČO)",
        "entities.dic": "Tax ID (DIČ)",
        "entities.email": "Contact email for data requests",
        "entities.phone": "Phone",
        "entities.lede": "The company or sole trader that operates a property and controls guest data.",
        "entities.back": "Back to properties",
        "entities.explainer": "This entity holds the UbyPort registration and is named as data controller in the guest privacy notice. Keep its registered seat and contact email current.",
        "entities.edit": "Edit %(name)s",
        "entities.save": "Save changes",
        "entities.contact": "Contact",
        "entities.properties": "Properties",
        "entities.open": "Open %(name)s",
        "entities.missing": "Missing",
        "entities.empty": "No legal entities yet. Add the first one here.",
        "entities.archived": "Archived",
        "entities.archived_lede": "Hidden from property pickers. Restore anything archived by mistake.",
        "entities.delete": "Delete",
        "entities.add": "Add a legal entity",
        "entities.add_action": "Add entity",
        "guest_links.title": "Guest links",
        "guest_links.lede": "One permanent property link for portal messages. Guests choose their stay dates after opening it.",
        "guest_links.setup_items": "%(count)s setup item(s)",
        "guest_links.ready": "Ready",
        "guest_links.facility_missing": "Facility name not set",
        "guest_links.reusable": "Reusable property link",
        "guest_links.pin": "Access PIN",
        "guest_links.pin_help": "Guests enter this before the form opens.",
        "guest_links.message_title": "Suggested portal message",
        "guest_links.message": (
            "Dear guests,\n\nCzech law requires us to register every guest before arrival and "
            "report foreign nationals to the Foreign Police.\n\nPlease fill in one short form "
            "per person, including children:\n%(link)s\n\nAccess PIN: %(pin)s\n\nThe form "
            "explains why the information is required and how it is handled.\n\nThank you."
        ),
        "guest_links.copy_message": "Copy this message",
        "guest_links.message_copied": "Message copied",
        "guest_links.property_setup": "Property setup",
        "guest_links.options": "Link and PIN options",
        "guest_links.set_pin": "Set a specific PIN",
        "guest_links.new_pin": "Generate a new PIN",
        "guest_links.new_link": "Generate a new link",
        "guest_links.empty_title": "No guest links yet",
        "guest_links.empty_body": "Create a property first; its permanent link is generated automatically.",
        "reports.mode.immediate": "sent immediately after completion",
        "reports.mode.scheduled": "sent on schedule",
        "reports.mode.manual": "sent manually",
        "reports.detail.messages": "Messages exchanged",
        "reports.detail.request": "What UbyHost sent",
        "reports.detail.request_help": "Downloads the original data sent to UbyPort. Support may request it when investigating a rejection.",
        "reports.detail.request_about": "About the sent message",
        "reports.detail.response": "What UbyPort replied",
        "reports.detail.response_help": "Downloads UbyPort's exact technical acceptance or rejection response.",
        "reports.detail.response_about": "About the reply",
        "reports.detail.error_codes": "Guest record error codes",
        "reports.detail.error_codes_help": "UbyPort returns one code for each guest it could not accept. The codes identify the exact problem.",
        "reports.detail.error_codes_about": "About guest error codes",
        "account.password.choose": "Choose your password",
        "account.password.choose_lede": "Replace the temporary password before opening your workspace.",
        "account.password.change": "Change password",
        "account.password.change_lede": "Changing it signs out your other sessions.",
        "account.password.current": "Current password",
        "account.password.temporary_ph": "Temporary password…",
        "account.password.new": "New password",
        "account.password.new_ph": "At least 12 characters…",
        "account.password.rules": "Use at least 12 characters, upper- and lower-case letters, and a number.",
        "account.password.repeat": "Repeat new password",
        "account.password.repeat_ph": "Repeat new password…",
        "account.password.save": "Save password",
        "account.2fa.code_title": "Security code",
        "account.2fa.code_lede": "Enter the six-digit code from your authenticator app, or one recovery code.",
        "account.2fa.code_label": "Authentication code",
        "account.2fa.verify": "Verify and sign in",
        "account.2fa.start_over": "Start over",
        "account.2fa.setup_title": "Set up two-factor authentication",
        "account.2fa.setup_lede": "UbyHost contains identity documents, so every host account requires an authenticator app.",
        "account.2fa.setup_scan": "Scan this QR code in your authenticator app, or add a TOTP entry for UbyHost.",
        "account.2fa.setup_key": "Or enter this setup key manually:",
        "account.2fa.setup_enter": "Enter the generated six-digit code below.",
        "account.2fa.six_digit": "Six-digit code",
        "account.2fa.enable": "Enable two-factor authentication",
        "account.2fa.recovery_title": "Save your recovery codes",
        "account.2fa.recovery_lede": "Store these in a password manager or printed copy. Each works once if you lose your authenticator.",
        "account.2fa.recovery_once": "They will not be shown again.",
        "account.2fa.recovery_continue": "I saved them — continue",
        "settings.destination.title": "Where reports go",
        "settings.destination.deployment": "Deployment",
        "settings.destination.target": "UbyPort target",
        "settings.destination.production": "Production",
        "settings.destination.endpoint": "Endpoint",
        "settings.destination.polling": "Calendar polling",
        "settings.destination.sweep": "Submission sweep",
        "settings.destination.every_minutes": "every %(count)s minutes",
        "settings.destination.public_url": "Public base URL",
        "settings.destination.mock_help": "This is the local practice server. Set",
        "settings.destination.restart": "and restart after adding credentials.",
        "settings.destination.help": "The target and public URL come from server environment variables, so they cannot be changed by an accidental click.",
        "settings.mail.title": "Guest e-mails",
        "settings.mail.backend": "Mail backend",
        "settings.mail.help": "Staging uses the console backend: messages are stored here so you can copy claim links. Production stays disabled until SES is signed off.",
        "settings.mail.to": "To",
        "settings.mail.subject": "Subject",
        "settings.access.title": "Guest form access",
        "settings.access.pin": "PIN before the form",
        "settings.access.required": "Required (six digits per property)",
        "settings.access.off": "Off",
        "settings.access.help": "Each property has its own PIN under Guest links. The server setting UBYHOST_GUEST_PIN controls whether PINs are required.",
        "settings.codelists.title": "Cached UbyPort code lists",
        "settings.codelists.countries": "Countries",
        "settings.codelists.purposes": "Purposes of stay",
        "settings.codelists.errors": "Error codes",
        "settings.codelists.bundled": "using the bundled list",
        "settings.codelists.not_fetched": "not fetched yet",
        "settings.codelists.help": "Refresh these from a property's settings. Error codes turn UbyPort numbers into explanations you can act on.",
        "settings.retention.help": "Guest data is kept under GDPR Article 6(1)(c), a legal obligation rather than consent, and §§ 101–103 of Act No. 326/1999 Coll.",
        "settings.retention.period": "Retention",
        "settings.retention.years": "%(count)s years after the stay ends",
        "settings.retention.cutoff": "Delete anything ending before",
        "settings.retention.expired": "Records past that date",
        "settings.retention.delete": "Delete %(count)s expired record(s)",
        "settings.retention.delete_help": "Keeping passport numbers beyond the legal period is itself a breach. Review this annually.",
        "settings.privacy_incomplete": "The guest privacy notice is incomplete.",
        "settings.audit.help": "Important changes, archives, PIN rotations, and police submissions are recorded here. Only the retention purge permanently deletes guest records.",
        "settings.audit.recent": "Recent activity (%(count)s events)",
        "settings.audit.when": "When",
        "settings.audit.who": "Who",
        "settings.audit.action": "Action",
        "settings.audit.detail": "Detail",
        "settings.audit.empty": "Nothing logged yet.",
        "settings.account.2fa": "Two-factor authentication",
        "settings.account.2fa_on": "Your account requires an authenticator code at sign-in.",
        "settings.account.2fa_off": "Add an authenticator code after your password.",
        "settings.account.enabled": "Enabled",
        "settings.account.setup": "Set up",
        "settings.account.users": "User access",
        "settings.account.users_help": "Add users and manage their roles.",
        "settings.account.users_action": "Manage users",
    },
    "cs": {
        "common.all": "Vše",
        "common.filter": "Filtrovat",
        "housebook.title": "Domovní kniha",
        "housebook.lede": (
            "Každý záznam hosta a termín pobytu. Evidenci uchovávejte šest let od "
            "posledního zápisu a předložte ji při policejní kontrole."
        ),
        "housebook.apartment": "Ubytování",
        "housebook.from": "Pobyty od",
        "housebook.until": "Pobyty do",
        "housebook.actions": "Akce domovní knihy",
        "housebook.stay": "Pobyt",
        "housebook.guest": "Host",
        "housebook.born": "Narozen",
        "housebook.nationality": "Národnost",
        "housebook.document": "Doklad",
        "housebook.residence": "Bydliště v zahraničí",
        "housebook.purpose": "Účel",
        "housebook.signed": "Podepsáno",
        "housebook.reported": "Nahlášeno",
        "housebook.visa": "vízum %(number)s",
        "housebook.signed_yes": "Podepsáno",
        "housebook.signed_no": "Bez podpisu",
        "housebook.not_sent": "Dosud neodesláno",
        "housebook.pdf": "PDF podepsaného formuláře",
        "housebook.entries": "Počet záznamů: %(count)s.",
        "housebook.empty": "Filtru neodpovídají žádné záznamy. Kniha se plní po dokončení formulářů hostů.",
        "housebook.archived_title": "Archivované záznamy",
        "housebook.archived_lede": "Chybné záznamy a duplicity zde můžete obnovit.",
        "housebook.archived": "Archivováno",
        "automation.title": "Automatizace a UbyPort",
        "automation.lede": "Nastavte odesílání dokončených registrací hostů a přístupové údaje policejní webové služby pro každé ubytování.",
        "automation.to_fix": "%(count)s k opravě",
        "automation.ready": "Připraveno",
        "automation.timing_title": "Kdy odesílat do UbyPortu",
        "automation.timing_help": "Okamžitý režim odešle po dokončení všech nahlášených formulářů. Odložený odešle po zvoleném počtu hodin od dokončení a dává vám čas na kontrolu. Oba jsou automatické a nečekají na ověření. Odmítnuté záznamy se nikdy tiše neopakují.",
        "automation.timing_label": "Čas odeslání",
        "automation.mode.manual": "Jen po stisknutí Odeslat",
        "automation.mode.scheduled": "Automaticky po prodlevě od dokončení",
        "automation.mode.immediate": "Okamžitě po dokončení všech formulářů",
        "automation.hours": "Hodiny po dokončení",
        "automation.default_purpose": "Výchozí účel pobytu",
        "automation.credentials_title": "Přístupové údaje webové služby UbyPort",
        "automation.credentials_help": "Nejde o běžné přihlášení do UbyPortu. O přístup UBY-WS požádejte na reguby@pcr.cz.",
        "automation.sample_pdf": "Otevřít anotovaný vzor PDF",
        "automation.or_use": "nebo použijte",
        "automation.full_setup": "úplné nastavení ubytování",
        "automation.mark": "Zkratka ubytovacího zařízení",
        "automation.facility_name": "Název zařízení v UbyPortu",
        "automation.contact": "Kontaktní osoba při registraci",
        "automation.login": "Přihlášení webové služby",
        "automation.password": "Heslo webové služby",
        "automation.password_saved": "Uloženo — znovu se nezobrazuje.",
        "automation.password_keep": "Prázdné pole zachová uložené heslo",
        "automation.password_paste": "Vložte heslo z dopisu policie",
        "automation.password_replace": "Vyplňte jen při výměně hesla vydaného policií. Jinak ponechte prázdné.",
        "automation.password_new": "Vyžaduje se jednou; ukládá se šifrovaně a po uložení se nezobrazuje.",
        "automation.save": "Uložit %(property)s",
        "automation.test": "Otestovat spojení",
        "automation.refresh": "Obnovit číselníky",
        "automation.saved_credentials_help": "Test spojení používá naposledy uložené údaje. Po změně je nejprve uložte.",
        "automation.empty": "Zatím nejsou aktivní ubytování. Přidejte ubytování a nastavte hlášení.",
        "apartment.form.active.label": 'Aktivní — synchronizovat kalendáře a hlásit hosty pro toto ubytování',
        "apartment.form.addr.house_no": 'Číslo popisné',
        "apartment.form.addr.house_no_hint": 'Nejvýše 4 číslice. Pro evidenční číslo použijte E123.',
        "apartment.form.addr.obec": 'Obec',
        "apartment.form.addr.obec_cast": 'Část obce',
        "apartment.form.addr.okres": 'Okres',
        "apartment.form.addr.okres_hint": 'V Praze uveďte městskou část.',
        "apartment.form.addr.orient_no": 'Číslo orientační',
        "apartment.form.addr.orient_no_hint": 'Nejvýše 3 číslice a jedno volitelné písmeno.',
        "apartment.form.addr.street": 'Ulice',
        "apartment.form.addr.zip": 'PSČ',
        "apartment.form.addr.zip_hint": '5 číslic.',
        "apartment.form.address.lede_after": ') místo přepisování jedné řádkové adresy.',
        "apartment.form.address.lede_before": 'UbyPort ukládá adresu po částech. Zkopírujte je z registrace (',
        "apartment.form.address.lede_form_name": 'Žádost o registraci ubytovacího zařízení',
        "apartment.form.address.title": 'Adresa ubytovacího zařízení',
        "apartment.form.archive_help": 'Skrýt bez smazání záznamů. Užitečné pro duplicity nebo nevyužité ubytování.',
        "apartment.form.archive_title": 'Archivovat toto ubytování',
        "apartment.form.archived_help": 'Skryté z přehledu a odkazů pro hosty. Historie zůstává.',
        "apartment.form.automation.editing_lede_after": ', aby bylo jedno místo pro správu hlášení tohoto ubytování.',
        "apartment.form.automation.editing_lede_before": 'Čas odeslání, údaje UbyPortu a výchozí účel pobytu nastavíte na stránce ',
        "apartment.form.automation.hours_hint": 'Například 24 hodin vám dá prostor ke kontrole; odeslání proběhne automaticky bez ověření.',
        "apartment.form.automation.mode.scheduled": 'Automaticky po zadaném počtu hodin od dokončení',
        "apartment.form.automation.new_lede": 'Provozní pravidla určují, kolik aplikace udělá sama, a vyžadují váš výsledný souhlas. Odmítnutý záznam se nikdy tiše neopakuje.',
        "apartment.form.automation.open": 'Otevřít nastavení automatizace',
        "apartment.form.automation.purpose_hint": 'Předvybráno ve formuláři hosta. Turistika vyhovuje téměř všem krátkodobým pronájmům.',
        "apartment.form.automation.summary.immediate": 'Okamžitě po dokončení všech nahlášených formulářů',
        "apartment.form.automation.summary.manual": 'Jen když stisknete Odeslat',
        "apartment.form.back": 'Zpět na ubytování',
        "apartment.form.back_list": 'Zpět na seznam ubytování',
        "apartment.form.basics.title": 'Základní údaje',
        "apartment.form.blocking_title": 'Toto ubytování zatím nemůže hlásit do UbyPortu.',
        "apartment.form.calendars.add_sync": 'Přidat a synchronizovat',
        "apartment.form.calendars.connect_title": 'Připojit kalendář',
        "apartment.form.calendars.empty": 'Zatím není připojen žádný kalendář.',
        "apartment.form.calendars.lede": 'iCal z Airbnb a Booking.com dává jen termíny — bez jména, e-mailu a počtu osob. To stačí vědět, že někdo přijede, a aplikace může začít shánět údaje.',
        "apartment.form.calendars.own_name_label": 'Váš název',
        "apartment.form.calendars.own_name_ph": 'Airbnb – Vinohrady',
        "apartment.form.calendars.portal_ph": 'Airbnb / Booking.com / Agoda / Vrbo',
        "apartment.form.calendars.url_hint": 'Airbnb: Kalendář → Dostupnost → Propojit kalendáře. Booking.com: Ceny a dostupnost → Synchronizace. Vložte celý odkaz.',
        "apartment.form.calendars.url_label": 'URL exportu iCal',
        "apartment.form.calendars.url_ph": 'https://www.airbnb.com/calendar/ical/…',
        "apartment.form.city_en.hint": 'Zobrazí se hostům vedle registrovaného názvu zařízení, např. "Prague".',
        "apartment.form.city_en.label": 'Název města anglicky',
        "apartment.form.codelists_bundled": 'Do první obnovy se používá vestavěný seznam států.',
        "apartment.form.codelists_cached": 'Číselníky uloženy %(date)s.',
        "apartment.form.create": 'Vytvořit ubytování',
        "apartment.form.credentials_actions_help": 'Obě akce používají uložené údaje — nejprve uložte.',
        "apartment.form.entity.hint": 'IČO registrované v UbyPortu pro tuto adresu. Je také správcem údajů v informaci pro hosty, proto ji nelze nechat prázdnou, pokud chcete úplné znění.',
        "apartment.form.entity.label": 'Provozující právnická osoba',
        "apartment.form.feed.last_sync": 'Poslední sync',
        "apartment.form.feed.name": 'Název',
        "apartment.form.feed.portal": 'Portál',
        "apartment.form.feed.status.error": 'Chyba',
        "apartment.form.feed.status.never": 'Nikdy',
        "apartment.form.feed.status.ok": 'OK',
        "apartment.form.feed.url": 'URL',
        "apartment.form.guest_link.lede": 'Na ubytování je právě jeden odkaz. Stejný text vložíte do každé automatické zprávy o příjezdu — Airbnb, Booking.com, přímé rezervace — host si po otevření zvolí vlastní termín. Nikdy se nemění, nastavíte jednou.',
        "apartment.form.guest_link.message_help": 'Stejný text vložte na Airbnb, Booking.com a do e-mailů přímých rezervací. Není co měnit podle portálu.',
        "apartment.form.guest_link.new_help": 'Jedinečný odkaz a PIN se vygenerují po uložení ubytování.',
        "apartment.form.guest_link.pin_hint": 'Šest číslic (nebo starší čtyři), které host zadá před formulářem. Změňte zde nebo vygenerujte níže.',
        "apartment.form.guest_link.pin_ph": '000000',
        "apartment.form.guest_link.regenerate_link": 'Vygenerovat nový odkaz',
        "apartment.form.guest_link.regenerate_link_help": 'Jen pokud odkaz unikl. Vytvoří se i nový PIN — aktualizujte zprávy na portálech.',
        "apartment.form.guest_link.regenerate_pin_help": 'Ponechat odkaz, změnit PIN pro hosty.',
        "apartment.form.guest_link.regenerate_pin_title": 'Vygenerovat jen nový PIN',
        "apartment.form.guest_link.window_hint": 'Na odkazu bytu se zobrazí jen pobyty, jejichž datum příjezdu spadá do tohoto okna. Nedokončené minulé pobyty zůstávají dostupné přes odkaz konkrétního pobytu, dokud přístup hostům nezamknete.',
        "apartment.form.guest_link.window_label": 'Zobrazit pobyty začínající do (dní)',
        "apartment.form.guest_message.hint": 'Zobrazí se v registračním formuláři hostů pro toto ubytování. Použijte ji jako uvítání nebo důležitou informaci k objektu; nevkládejte přístupové kódy ani jiná tajná data.',
        "apartment.form.guest_message.label": 'Vlastní zpráva pro hosty',
        "apartment.form.guest_message.placeholder": 'Například: Vítejte! Vyplňte prosím tento formulář před příjezdem.',
        "apartment.form.passport_policy.label": 'Fotografie pasu nebo dokladu od hosta',
        "apartment.form.passport_policy.hint": 'Vypnuto znamená, že formulář obrázek dokladu nevyžaduje. Povinné požádá cizince o dočasné nahrání k vaší volitelné kontrole; policii se neposílá.',
        "apartment.form.passport_policy.off": 'Vypnuto (výchozí) — doklad zkontrolujete při příjezdu',
        "apartment.form.passport_policy.required": 'Povinné pro cizince vyplňující online formulář',
        "apartment.form.internal_name.hint": 'Jen pro vaši orientaci — hosté ho nevidí.',
        "apartment.form.internal_name.label": 'Váš název tohoto ubytování',
        "apartment.form.lede": 'Vyplňte sekce níže, aby registrace hostů a hlášení do UbyPortu fungovaly spolehlivě.',
        "apartment.form.nav.address": '2. Adresa',
        "apartment.form.nav.aria": 'Sekce nastavení ubytování',
        "apartment.form.nav.automation": '4. Automatizace',
        "apartment.form.nav.automation_ubyport": '3. Automatizace a UbyPort',
        "apartment.form.nav.basics": '1. Ubytování',
        "apartment.form.nav.calendars": '5. Kalendáře',
        "apartment.form.nav.guest_link": '4. Odkaz pro hosty',
        "apartment.form.nav.guest_link_new": '5. Odkaz pro hosty',
        "apartment.form.nav.ubyport": '3. UbyPort',
        "apartment.form.new_property": 'Nové ubytování',
        "apartment.form.notes.hint": 'Vidíte jen vy — hostům se nezobrazuje.',
        "apartment.form.notes.label": 'Vaše poznámky',
        "apartment.form.notes.title": 'Soukromé poznámky',
        "apartment.form.refresh_codelists": 'Obnovit číselníky z UbyPortu',
        "apartment.form.test_connection": 'Otestovat spojení',
        "apartment.form.title_new": 'Nové ubytování',
        "apartment.form.ubyport.contact_hint": 'E-mail/telefon z registrace nebo portálu UbyPort — není na dopise s heslem WS.',
        "apartment.form.ubyport.idub_hint": 'Řádek „IDUB:“ v PDF — 12–14 číslic znak po znaku.',
        "apartment.form.ubyport.intro": 'Nejde o běžné přihlášení do portálu UbyPort (ub…). Použijte samostatný dopis „Výpis z databáze přihlašovacích údajů“ (webová služba / robotické vkládání) — obvykle PDF, v jehož názvu je IDUB a UBY-WS.',
        "apartment.form.ubyport.login_hint": '„Přihlašovací jméno:“ v PDF — kopírujte přesně (včetně _ nebo číslic).',
        "apartment.form.ubyport.map.contact": 'E-mail nebo telefon z původní registrace ubytování — často není na PDF webové služby. Stejná hodnota jako v profilu zařízení v UbyPortu. Špatný kontakt může vést k odmítnutí; prázdné jen pokud jste ho nikdy neuváděli.',
        "apartment.form.ubyport.map.contact_label": 'Kontakt (volitelné zde)',
        "apartment.form.ubyport.map.idub": 'Řádek IDUB: na PDF webové služby.',
        "apartment.form.ubyport.map.login": 'Řádek Přihlašovací jméno: (např. UBY-WS_MLJNO).',
        "apartment.form.ubyport.map.mark": 'Pět písmen přidělených při registraci — ne v úvodním e-mailu. Často stejných pět písmen za UBY-WS_ v přihlášení (např. UBY-WS_MLJNO → zkratka MLJNO). Ověřte v portálu UbyPort nebo v rozhodnutí o registraci.',
        "apartment.form.ubyport.map.mark_label": 'Zkratka ubytovacího zařízení',
        "apartment.form.ubyport.map.name": 'Řádek Ubytovací zařízení: na PDF — kopírujte jen první řádek (před závorkou s Prahou/adresou). Ne název na Airbnb. Max. 35 znaků; v registru je krátký právní název.',
        "apartment.form.ubyport.map.password": 'Řádek Přístupové heslo: na stejném PDF — zadejte jednou, při dalších uloženích nechte prázdné.',
        "apartment.form.ubyport.map_summary": 'Odkud se bere každé pole v UbyHostu (přečtěte jednou)',
        "apartment.form.ubyport.mark_hint": 'Pět písmen v evidenci policie (často = písmena za UBY-WS_ v přihlášení).',
        "apartment.form.ubyport.mark_label": 'Zkratka ubytovacího zařízení',
        "apartment.form.ubyport.mismatch_help": 'UbyPort porovnává IDUB, zkratku, název, adresu a kontakt s registrem. Překlep nebo název z Airbnb selže i když přihlášení webové služby funguje — často to vidíte při prvním skutečném odeslání.',
        "apartment.form.ubyport.name_hint": '„Ubytovací zařízení:“ v PDF — jen první řádek, ne název inzerátu; max. 35 znaků.',
        "apartment.form.ubyport.password_edit_hint": 'Pište sem jen pokud policie cizinců poslala nové heslo. Uložení zbytku formuláře bez změny tohoto pole ponechá uložené heslo.',
        "apartment.form.ubyport.password_new_hint": 'Zadejte jednou při prvním nastavení hlášení. Před zápisem na disk se šifruje a po uložení se nezobrazuje.',
        "apartment.form.ubyport.password_saved": 'Uloženo — UbyHost ho drží šifrovaně a znovu nezobrazuje.',
        "apartment.form.ubyport.sample_help": ' — ukázkový dopis policie se vodoznaky SAMPLE; ukazuje každou hodnotu pro UbyHost, včetně zkratky a kontaktu, které reálná PDF často neobsahují.',
        "common.none": '— žádná —',
        "common.remove": 'Odebrat',
        "common.save_changes": 'Uložit změny',
        "common.select": '— vyberte —',
        "guest.admin.back_to_stay": 'Zpět na pobyt',
        "guest.admin.banner.rejected_help": 'Opravte údaje a uložte — záznam se vrátí do fronty.',
        "guest.admin.banner.rejected_title": 'UbyPort tento záznam odmítl.',
        "guest.admin.banner.sent_help": 'Úprava mění jen domovní knihu. Opětovné odeslání vytvoří duplicitu, kterou policie započítává, proto je potřeba potvrzení níže.',
        "guest.admin.banner.sent_title": 'Již nahlášeno cizinecké policii.',
        "guest.admin.banner.sent_title_at": 'Již nahlášeno cizinecké policii %(at)s.',
        "guest.admin.birth_date": 'Datum narození',
        "guest.admin.birth_date_hint": 'Zadejte 8 číslic z pasu — lomítka se doplní sama. Pro neznámý den nebo měsíc použijte 00.',
        "guest.admin.birth_date_ph": 'DD/MM/RRRR',
        "guest.admin.danger.summary": 'Pokročilé a nebezpečné akce',
        "guest.admin.document": 'Číslo cestovního dokladu',
        "guest.admin.document_hint": '6–30 písmen a číslic, nebo INPASS pro dítě v pasu rodiče.',
        "guest.admin.download_pdf": 'Stáhnout podepsaný formulář',
        "guest.admin.given_names": 'Jméno(a)',
        "guest.admin.identity.title": 'Identita',
        "guest.admin.nationality_hint": 'Čeští státní příslušníci jsou v domovní knize, ale policii se neodesílají.',
        "guest.admin.note": 'Poznámka',
        "guest.admin.note_optional": '(volitelné, max. 255)',
        "guest.admin.passport_pdf_title": 'PDF pasu',
        "guest.admin.passport_photo_alt": 'Fotografie pasu',
        "guest.admin.remove.submit": 'Smazat tohoto hosta',
        "guest.admin.remove.title": 'Odstranit',
        "guest.admin.res_city": 'Město',
        "guest.admin.res_country": 'Stát',
        "guest.admin.res_street": 'Ulice a číslo',
        "guest.admin.resend.confirm": 'Beru na vědomí, že může vzniknout duplicitní záznam.',
        "guest.admin.resend.help": 'UbyPort duplicity eviduje jako neopravitelné chyby a opakované odesílání bez důvodu může vést ke ztrátě přístupu k webové službě. Použijte jen s oprávněným důvodem — např. spojení spadlo a nejste si jisti doručením.',
        "guest.admin.resend.submit": 'Znovu odeslat do UbyPortu',
        "guest.admin.resend.title": 'Odeslat záznam znovu',
        "guest.admin.stay.title": 'Pobyt',
        "guest.admin.stay_from": 'Ubytován od',
        "guest.admin.stay_to": 'Ubytován do',
        "guest.admin.submit_add": 'Přidat hosta',
        "guest.admin.surname": 'Příjmení',
        "guest.admin.title_add": 'Přidat hosta',
        "guest.admin.title_edit": 'Upravit hosta',
        "guest.admin.visa": 'Číslo víza',
        "settings.privacy.add_contact": 'doplňte ho',
        "settings.privacy.no_contact_prefix": 'Bez kontaktního e-mailu u:',
        "settings.privacy.no_contact_suffix": ', aby hosti mohli uplatnit svá práva.',
        "settings.privacy.no_entity_prefix": 'Bez právnické osoby u:',
        "settings.privacy.no_entity_suffix": '— hostům nelze sdělit, kdo údaje spravuje.',
        "settings.version_line": 'UbyHost %(version)s',
        "users.create.lede": 'Vygeneruje se bezpečné dočasné heslo. Zkopírujte ho před vytvořením účtu.',
        "users.create.name": 'Jméno',
        "users.create.password_hint": 'Při prvním přihlášení ho musí nahradit.',
        "users.create.regenerate": 'Vygenerovat znovu',
        "users.create.submit": 'Vytvořit hostitele',
        "users.create.temporary_password": 'Dočasné heslo',
        "users.create.title": 'Vytvořit hostitele',
        "users.create.username": 'Uživatelské jméno',
        "users.create.username_hint": 'Malá písmena, číslice, tečky, pomlčky a podtržítka.',
        "users.credential.choose_on_login": 'Při prvním přihlášení si zvolí vlastní heslo.',
        "users.credential.copy_now": 'Zkopírujte hned — v čitelné podobě se neukládá a znovu nezobrazí.',
        "users.credential.created_title": 'Uživatel vytvořen',
        "users.credential.old_password_invalid": 'Původní heslo už neplatí.',
        "users.credential.reset_title": 'Heslo resetováno',
        "users.credential.temporary_password": 'Dočasné heslo',
        "users.credential.username": 'Uživatelské jméno',
        "users.lede": 'Vytvořte soukromý pracovní prostor pro každého hostitele. Hesla jsou hashována, dají se resetovat, nikdy zobrazit.',
        "users.menu.aria": 'Akce uživatele',
        "users.menu.disable": 'Zakázat',
        "users.menu.enable": 'Povolit',
        "users.menu.open_workspace": 'Otevřít pracovní prostor',
        "users.menu.reset_password": 'Resetovat heslo',
        "users.reset.lede_after": '. Zkopírujte ho před uložením.',
        "users.reset.lede_before": 'Nové dočasné heslo pro ',
        "users.reset.save": 'Uložit heslo',
        "users.reset.temporary_password": 'Dočasné heslo',
        "users.reset.title": 'Resetovat heslo',
        "users.status.active": 'Aktivní',
        "users.status.disabled": 'Zakázán',
        "users.status.temporary_password": 'Dočasné heslo',
        "users.table.properties": 'Ubytování',
        "users.table.role": 'Role',
        "users.table.status": 'Stav',
        "users.table.user": 'Uživatel',
        "users.title": 'Uživatelé',
        "entities.title": "Právnické osoby",
        "entities.name": "Název",
        "entities.name_placeholder": "Podle obchodního nebo živnostenského rejstříku",
        "entities.seat": "Sídlo",
        "entities.seat_placeholder": "Ulice, číslo, PSČ, město",
        "entities.ico": "IČO",
        "entities.dic": "DIČ",
        "entities.email": "Kontaktní e-mail pro žádosti o údaje",
        "entities.phone": "Telefon",
        "entities.lede": "Firma nebo podnikatel, který provozuje ubytování a spravuje údaje hostů.",
        "entities.back": "Zpět na ubytování",
        "entities.explainer": "Tato osoba drží registraci v UbyPortu a je správcem údajů uvedeným v informaci pro hosty. Udržujte sídlo a kontaktní e-mail aktuální.",
        "entities.edit": "Upravit %(name)s",
        "entities.save": "Uložit změny",
        "entities.contact": "Kontakt",
        "entities.properties": "Ubytování",
        "entities.open": "Otevřít %(name)s",
        "entities.missing": "Chybí",
        "entities.empty": "Zatím nejsou žádné právnické osoby. Přidejte první.",
        "entities.archived": "Archivované",
        "entities.archived_lede": "Skryté z výběru u ubytování. Omylem archivované položky můžete obnovit.",
        "entities.delete": "Smazat",
        "entities.add": "Přidat právnickou osobu",
        "entities.add_action": "Přidat osobu",
        "guest_links.title": "Odkazy pro hosty",
        "guest_links.lede": "Jeden trvalý odkaz pro každé ubytování do zpráv portálu. Host si po otevření vybere termín.",
        "guest_links.setup_items": "%(count)s položek nastavení",
        "guest_links.ready": "Připraveno",
        "guest_links.facility_missing": "Název zařízení není nastaven",
        "guest_links.reusable": "Trvalý odkaz ubytování",
        "guest_links.pin": "Přístupový PIN",
        "guest_links.pin_help": "Hosté ho zadají před otevřením formuláře.",
        "guest_links.message_title": "Doporučená zpráva pro portál",
        "guest_links.message": (
            "Vážení hosté,\n\nčeský zákon vyžaduje evidenci každého hosta před příjezdem a "
            "oznámení cizinců cizinecké policii.\n\nVyplňte prosím jeden krátký formulář za "
            "každou osobu včetně dětí:\n%(link)s\n\nPřístupový PIN: %(pin)s\n\nFormulář "
            "vysvětluje, proč jsou údaje povinné a jak se s nimi nakládá.\n\nDěkujeme."
        ),
        "guest_links.copy_message": "Kopírovat zprávu",
        "guest_links.message_copied": "Zpráva zkopírována",
        "guest_links.property_setup": "Nastavení ubytování",
        "guest_links.options": "Možnosti odkazu a PIN",
        "guest_links.set_pin": "Nastavit vlastní PIN",
        "guest_links.new_pin": "Vygenerovat nový PIN",
        "guest_links.new_link": "Vygenerovat nový odkaz",
        "guest_links.empty_title": "Zatím žádné odkazy pro hosty",
        "guest_links.empty_body": "Nejprve vytvořte ubytování; trvalý odkaz se vygeneruje automaticky.",
        "reports.mode.immediate": "odesláno okamžitě po dokončení",
        "reports.mode.scheduled": "odesláno podle plánu",
        "reports.mode.manual": "odesláno ručně",
        "reports.detail.messages": "Vyměněné zprávy",
        "reports.detail.request": "Co UbyHost odeslal",
        "reports.detail.request_help": "Stáhne původní data odeslaná do UbyPortu. Podpora je může vyžádat při řešení odmítnutí.",
        "reports.detail.request_about": "O odeslané zprávě",
        "reports.detail.response": "Co odpověděl UbyPort",
        "reports.detail.response_help": "Stáhne přesnou technickou odpověď UbyPortu o přijetí nebo odmítnutí.",
        "reports.detail.response_about": "O odpovědi",
        "reports.detail.error_codes": "Chybové kódy záznamů hostů",
        "reports.detail.error_codes_help": "UbyPort vrací kód pro každého nepřijatého hosta. Kódy určují přesný problém.",
        "reports.detail.error_codes_about": "O chybových kódech hostů",
        "account.password.choose": "Zvolte si heslo",
        "account.password.choose_lede": "Před otevřením pracovního prostoru nahraďte dočasné heslo.",
        "account.password.change": "Změnit heslo",
        "account.password.change_lede": "Změna odhlásí ostatní relace.",
        "account.password.current": "Současné heslo",
        "account.password.temporary_ph": "Dočasné heslo…",
        "account.password.new": "Nové heslo",
        "account.password.new_ph": "Alespoň 12 znaků…",
        "account.password.rules": "Použijte alespoň 12 znaků, malá i velká písmena a číslo.",
        "account.password.repeat": "Zopakujte nové heslo",
        "account.password.repeat_ph": "Zopakujte nové heslo…",
        "account.password.save": "Uložit heslo",
        "account.2fa.code_title": "Bezpečnostní kód",
        "account.2fa.code_lede": "Zadejte šestimístný kód z autentizační aplikace nebo jeden obnovovací kód.",
        "account.2fa.code_label": "Ověřovací kód",
        "account.2fa.verify": "Ověřit a přihlásit",
        "account.2fa.start_over": "Začít znovu",
        "account.2fa.setup_title": "Nastavit dvoufázové ověření",
        "account.2fa.setup_lede": "UbyHost obsahuje doklady totožnosti, proto každý účet hostitele vyžaduje autentizační aplikaci.",
        "account.2fa.setup_scan": "Naskenujte QR kód v autentizační aplikaci nebo přidejte záznam TOTP pro UbyHost.",
        "account.2fa.setup_key": "Nebo ručně zadejte tento klíč:",
        "account.2fa.setup_enter": "Níže zadejte vygenerovaný šestimístný kód.",
        "account.2fa.six_digit": "Šestimístný kód",
        "account.2fa.enable": "Zapnout dvoufázové ověření",
        "account.2fa.recovery_title": "Uložte si obnovovací kódy",
        "account.2fa.recovery_lede": "Uložte je do správce hesel nebo vytiskněte. Každý lze použít jednou při ztrátě autentizátoru.",
        "account.2fa.recovery_once": "Znovu se nezobrazí.",
        "account.2fa.recovery_continue": "Mám je uložené — pokračovat",
        "settings.destination.title": "Kam hlášení směřují",
        "settings.destination.deployment": "Nasazení",
        "settings.destination.target": "Cíl UbyPort",
        "settings.destination.production": "Produkce",
        "settings.destination.endpoint": "Koncový bod",
        "settings.destination.polling": "Načítání kalendářů",
        "settings.destination.sweep": "Kontrola odesílání",
        "settings.destination.every_minutes": "každých %(count)s minut",
        "settings.destination.public_url": "Veřejná základní URL",
        "settings.destination.mock_help": "Jde o místní cvičný server. Nastavte",
        "settings.destination.restart": "a po přidání údajů restartujte.",
        "settings.destination.help": "Cíl a veřejná URL pocházejí z proměnných serveru, takže je nelze změnit náhodným kliknutím.",
        "settings.mail.title": "E-maily hostům",
        "settings.mail.backend": "E-mailový backend",
        "settings.mail.help": "Staging používá konzoli: zprávy se ukládají sem, abyste mohli zkopírovat odkazy na převzetí. Produkce zůstává vypnutá, dokud nebude SES schválené.",
        "settings.mail.to": "Komu",
        "settings.mail.subject": "Předmět",
        "settings.access.title": "Přístup k formuláři hosta",
        "settings.access.pin": "PIN před formulářem",
        "settings.access.required": "Povinný (šest číslic pro každé ubytování)",
        "settings.access.off": "Vypnuto",
        "settings.access.help": "Každé ubytování má vlastní PIN v Odkazech pro hosty. Serverové nastavení UBYHOST_GUEST_PIN určuje, zda je PIN povinný.",
        "settings.codelists.title": "Uložené číselníky UbyPortu",
        "settings.codelists.countries": "Státy",
        "settings.codelists.purposes": "Účely pobytu",
        "settings.codelists.errors": "Chybové kódy",
        "settings.codelists.bundled": "používá se vestavěný seznam",
        "settings.codelists.not_fetched": "dosud nenačteno",
        "settings.codelists.help": "Obnovte je v nastavení ubytování. Chybové kódy mění čísla UbyPortu na srozumitelná vysvětlení.",
        "settings.retention.help": "Údaje hostů se uchovávají podle čl. 6 odst. 1 písm. c) GDPR jako právní povinnost a podle § 101–103 zákona č. 326/1999 Sb.",
        "settings.retention.period": "Doba uchování",
        "settings.retention.years": "%(count)s let po skončení pobytu",
        "settings.retention.cutoff": "Smazat záznamy končící před",
        "settings.retention.expired": "Záznamy po tomto datu",
        "settings.retention.delete": "Smazat %(count)s prošlých záznamů",
        "settings.retention.delete_help": "Uchovávání čísel pasů nad zákonnou dobu je samo porušením. Kontrolujte jednou ročně.",
        "settings.privacy_incomplete": "Informace o zpracování údajů hosta není úplná.",
        "settings.audit.help": "Důležité změny, archivace, změny PIN a policejní hlášení se zapisují zde. Trvale maže pouze retence.",
        "settings.audit.recent": "Nedávná aktivita (%(count)s událostí)",
        "settings.audit.when": "Kdy",
        "settings.audit.who": "Kdo",
        "settings.audit.action": "Akce",
        "settings.audit.detail": "Podrobnost",
        "settings.audit.empty": "Zatím bez záznamů.",
        "settings.account.2fa": "Dvoufázové ověření",
        "settings.account.2fa_on": "Při přihlášení účet vyžaduje kód z autentizační aplikace.",
        "settings.account.2fa_off": "Přidejte po hesle kód z autentizační aplikace.",
        "settings.account.enabled": "Zapnuto",
        "settings.account.setup": "Nastavit",
        "settings.account.users": "Přístup uživatelů",
        "settings.account.users_help": "Přidávejte uživatele a spravujte jejich role.",
        "settings.account.users_action": "Spravovat uživatele",
    },
}
for _lang, _strings in _INTERFACE_STRINGS.items():
    STRINGS[_lang].update(_strings)

for _lang, _terms in TERMS_STRINGS.items():
    STRINGS.setdefault(_lang, {}).update(_terms)

for _lang, _privacy in PRIVACY_STRINGS.items():
    STRINGS.setdefault(_lang, {}).update(_privacy)

for _lang, _dpa in DPA_STRINGS.items():
    STRINGS.setdefault(_lang, {}).update(_dpa)


def normalise_language(value: str | None) -> str:
    value = (value or "").lower()[:2]
    return value if value in LANGUAGES else DEFAULT_LANGUAGE


def supported_language(value: str | None) -> str | None:
    """The language code, or None when we do not speak it."""
    value = (value or "").strip().lower()[:2]
    return value if value in LANGUAGES else None


def _from_accept_header(request: Request) -> str | None:
    """The visitor's preferred language, honouring the q-values they sent."""
    ranked = []
    header = request.headers.get("accept-language", "")
    for position, part in enumerate(header.split(",")):
        tag, _, parameters = part.strip().partition(";")
        quality = 1.0
        for parameter in parameters.split(";"):
            name, _, raw = parameter.partition("=")
            if name.strip().lower() == "q":
                try:
                    quality = float(raw)
                except ValueError:
                    quality = 0.0
        ranked.append((-quality, position, tag))
    for _, _, tag in sorted(ranked):
        spoken = supported_language(tag)
        if spoken:
            return spoken
    return None


def resolve_language(request: Request | None, default: str = DEFAULT_LANGUAGE) -> str:
    """A ?lang= link wins, then the saved choice, then the browser's headers."""
    if request is None:
        return normalise_language(default)
    signals = (
        supported_language(request.query_params.get("lang")),
        supported_language(request.cookies.get(LANG_COOKIE)),
        _from_accept_header(request),
    )
    for signal in signals:
        if signal:
            return signal
    return normalise_language(default)


def lang_from_request(request: Request) -> str:
    chosen = supported_language(getattr(request.state, "lang", None)) if request else None
    return chosen or resolve_language(request)


def remember_language(response, lang: str) -> None:
    """Keep the visitor's language for a year, in the cookie the switcher uses."""
    response.set_cookie(
        LANG_COOKIE,
        normalise_language(lang),
        max_age=LANG_COOKIE_MAX_AGE,
        httponly=False,
        samesite="lax",
        secure=config.PUBLIC_BASE_URL.lower().startswith("https://"),
        path="/",
    )


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
