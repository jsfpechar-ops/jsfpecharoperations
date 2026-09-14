"""Host-facing UI strings in English and Czech."""
from __future__ import annotations

from typing import Dict

from fastapi import Request

from .dpa_i18n import DPA_STRINGS
from .privacy_policy_i18n import PRIVACY_STRINGS
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
        "housebook.legal_import": (
            "Had a paper house book? Use Import to digitise old rows without retyping — download the "
            "import template for the exact column format."
        ),
        "housebook.import_paper": "Import paper records",
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
        "status.ready_immediate": "Verified — auto-send",
        "status.ready_immediate_tip": "Forms complete — UbyPort sends automatically when automation allows.",
        "status.awaiting_verification": "ID not checked",
        "status.awaiting_verification_tip": (
            "Guest forms are complete. Mark ID on each guest below, or send — ID is recorded when you send."
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
        "guide.demo.body": (
            "Load demo data anytime to explore with a sample flat. Demo guests are never sent to the real "
            "police register."
        ),
        "a11y.skip_to_content": "Skip to main content",
        "a11y.breadcrumb": "Breadcrumb",
        "a11y.main_navigation": "Main navigation",
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
        "submission.accepted": "Accepted",
        "submission.partial": "Partly accepted",
        "submission.rejected": "Rejected",
        "submission.not_delivered": "Not delivered",
        "submission.setup_incomplete": "Setup incomplete",
        "submission.in_progress": "In progress",
        "submission.nothing_to_send": "Nothing to send",
        "onboarding.step": "Setup step %(current)s of %(total)s: %(title)s",
        "onboarding.welcome": "Welcome to UbyHost",
        "onboarding.lede": "Let’s get your first property ready for guest reporting. Follow the five steps below.",
        "onboarding.steps": "Setup steps",
        "onboarding.done": "Done",
        "onboarding.continue": "Continue: %(action)s",
        "confirm.cancel": "Cancel",
        "confirm.proceed": "Confirm",
        "confirm.archive_stay": "Archive this stay? It moves to Archive and can be restored later.",
        "confirm.archive_property": "Archive this property? It will disappear from your dashboard and guest links.",
        "confirm.clear_demo": "Clear the built-in demo data?",
        "confirm.purge_expired": "Permanently delete every guest record past the retention period? This cannot be undone.",
        "confirm.delete_entity": "Delete this legal entity? This cannot be undone.",
        "confirm.remove_guest": "Remove this guest record?",
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
        "hint.awaiting_verification": "Check each passport photo and confirm the details before reporting",
        "hint.auto_immediate": "Sends automatically after you verify each guest against their passport",
        "hint.nothing_duty": "Nothing to send: no guest record is subject to the reporting duty",
        "hint.need_signature": "Every foreign guest must sign before reporting to UbyPort",
        "hint.need_verification": "Verify each guest against their passport before reporting",
        "hint.nothing_left": "Nothing left to send for this stay",
        "hint.not_ready": "Complete guest details, signatures, and passport checks before sending",
        "hint.ready_to_send": "Send completed guest records to UbyPort now",
        "hint.ready_id_optional": "Forms complete — send now or mark ID checked first (recorded on send)",
        "hint.demo_preview": "Demo stays are never sent — use a real property to report to UbyPort",
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
        "stays.import.title": "Import stays from CSV",
        "stays.import.lede": "Upload a semicolon-separated file with one stay per row. Download the sample CSV to see the exact format.",
        "stays.import.required": "Required columns: Apartment, Arrival, Departure. Apartment names must match your properties exactly.",
        "stays.import.file": "CSV file",
        "stays.import.submit": "Import stays",
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
        "stay.detail.copy_link": "Copy guest link for this stay",
        "stay.detail.link_copied": "Link copied",
        "stay.detail.cta.send": "Send to UbyPort",
        "stay.detail.cta.fix": "Fix rejection",
        "stay.detail.cta.view_reports": "View reports",
        "stay.detail.cta.verify": "Verify passports",
        "stay.detail.cta.open": "Open stay",
        "stay.detail.cta.add_guest": "Add a guest",
        "stay.detail.ready_count": "%(count)s guest record(s) ready to report.",
        "stay.detail.metric.deadline": "Reporting deadline",
        "stay.detail.metric.deadline_note": "Three working days after check-in ends %(when)s.",
        "stay.detail.metric.guests": "Guest forms",
        "stay.detail.metric.guests_note": "%(sent)s reported · %(reportable)s subject to the duty",
        "stay.detail.metric.reporting": "Reporting",
        "stay.detail.note.verify": "Guest forms are complete. Check each passport photo and confirm the details before reporting.",
        "stay.detail.note.ready_immediate": "All guests verified. UbyPort submission happens automatically after each verification.",
        "stay.detail.note.ready_manual": "Guest forms are complete. Check the details below, then send when ready.",
        "stay.detail.note.ready_scheduled": "Guest forms are complete. They will send %(hours)s h after check-in, or use Send now.",
        "stay.detail.note.automation": "Automation:",
        "stay.detail.note.immediate": "after you verify each passport",
        "stay.detail.note.scheduled": "%(hours)s h after check-in",
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
        "stay.detail.settings.email_hint": "Stored for your reference. UbyHost does not send e-mail yet.",
        "stay.detail.settings.host_only": "(host-only note)",
        "stay.detail.settings.state": "Stay state",
        "stay.detail.settings.state.active": "Active",
        "stay.detail.settings.state.cancelled": "Cancelled",
        "stay.detail.settings.state.ignored": "Not a guest stay",
        "stay.detail.settings.state_hint": "“Not a guest stay” removes this item from daily work but preserves it and sticks across future calendar syncs. You can restore it by choosing Active.",
        "stay.detail.settings.note": "Private note",
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
        "housebook.legal_import": (
            "Vedli jste papírovou domovní knihu? Importem doplníte starší záznamy bez přepisování — "
            "vzor souboru najdete v menu Import a export."
        ),
        "housebook.import_paper": "Importovat papírovou evidenci",
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
        "status.ready_immediate": "Ověřeno — automaticky",
        "status.ready_immediate_tip": "Formuláře hotové — UbyPort odešle automaticky podle režimu.",
        "status.awaiting_verification": "Doklad nezkontrolován",
        "status.awaiting_verification_tip": (
            "Formuláře jsou hotové. Označte kontrolu dokladu u hostů, nebo odešlete — kontrola se zapíše při odeslání."
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
        "guide.demo.body": (
            "Ukázková data lze načíst kdykoli. Na skutečnou policii se nikdy neodešlou."
        ),
        "a11y.skip_to_content": "Přeskočit na hlavní obsah",
        "a11y.breadcrumb": "Drobečková navigace",
        "a11y.main_navigation": "Hlavní navigace",
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
        "submission.accepted": "Přijato",
        "submission.partial": "Částečně přijato",
        "submission.rejected": "Odmítnuto",
        "submission.not_delivered": "Nedoručeno",
        "submission.setup_incomplete": "Nedokončené nastavení",
        "submission.in_progress": "Probíhá",
        "submission.nothing_to_send": "Nic k odeslání",
        "onboarding.step": "Krok nastavení %(current)s z %(total)s: %(title)s",
        "onboarding.welcome": "Vítejte v UbyHostu",
        "onboarding.lede": "Připravme první ubytování pro hlášení hostů. Projděte pět kroků níže.",
        "onboarding.steps": "Kroky nastavení",
        "onboarding.done": "Hotovo",
        "onboarding.continue": "Pokračovat: %(action)s",
        "confirm.cancel": "Zrušit",
        "confirm.proceed": "Potvrdit",
        "confirm.archive_stay": "Archivovat tento pobyt? Přesune se do archivu a později ho můžete obnovit.",
        "confirm.archive_property": "Archivovat toto ubytování? Zmizí z přehledu a odkazů pro hosty.",
        "confirm.clear_demo": "Smazat vestavěná ukázková data?",
        "confirm.purge_expired": "Trvale smazat všechny záznamy hostů po uplynutí zákonné doby uchovávání? Nelze vrátit.",
        "confirm.delete_entity": "Smazat tuto právnickou osobu? Nelze vrátit.",
        "confirm.remove_guest": "Odstranit tento záznam hosta?",
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
        "hint.awaiting_verification": "Zkontrolujte fotografii pasu a potvrďte údaje před hlášením",
        "hint.auto_immediate": "Odešle se automaticky po ověření hosta proti pasu",
        "hint.nothing_duty": "Nic k odeslání: žádný záznam hosta není předmětem hlášení",
        "hint.need_signature": "Každý cizinec se musí podepsat před odesláním do UbyPortu",
        "hint.need_verification": "Ověřte každého hosta proti pasu před hlášením",
        "hint.nothing_left": "Pro tento pobyt už nic k odeslání není",
        "hint.not_ready": "Doplňte údaje hostů, podpisy a kontrolu pasů před odesláním",
        "hint.ready_to_send": "Odeslat hotové záznamy hostů do UbyPortu",
        "hint.ready_id_optional": "Formuláře hotové — odešlete, nebo nejdřív označte kontrolu dokladu (zapíše se při odeslání)",
        "hint.demo_preview": "Ukázkové pobyty se neodesílají — pro hlášení použijte skutečnou nemovitost",
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
        "stays.import.title": "Import pobytů z CSV",
        "stays.import.lede": "Nahrajte soubor oddělený středníky, jeden pobyt na řádek. Stáhněte vzor CSV pro přesný formát.",
        "stays.import.required": "Povinné sloupce: Ubytování, Příjezd, Odjezd. Názvy musí přesně sedět s vašimi ubytováními.",
        "stays.import.file": "Soubor CSV",
        "stays.import.submit": "Importovat pobyty",
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
        "stay.detail.copy_link": "Kopírovat odkaz pro hosty",
        "stay.detail.link_copied": "Odkaz zkopírován",
        "stay.detail.cta.send": "Odeslat do UbyPortu",
        "stay.detail.cta.fix": "Opravit odmítnutí",
        "stay.detail.cta.view_reports": "Zobrazit hlášení",
        "stay.detail.cta.verify": "Ověřit pasy",
        "stay.detail.cta.open": "Otevřít pobyt",
        "stay.detail.cta.add_guest": "Přidat hosta",
        "stay.detail.ready_count": "%(count)s záznam(ů) hostů připraveno k hlášení.",
        "stay.detail.metric.deadline": "Termín hlášení",
        "stay.detail.metric.deadline_note": "Tři pracovní dny po příjezdu končí %(when)s.",
        "stay.detail.metric.guests": "Formuláře hostů",
        "stay.detail.metric.guests_note": "%(sent)s nahlášeno · %(reportable)s podléhá povinnosti",
        "stay.detail.metric.reporting": "Hlášení",
        "stay.detail.note.verify": "Formuláře jsou hotové. Zkontrolujte fotografii pasu a potvrďte údaje před hlášením.",
        "stay.detail.note.ready_immediate": "Všichni hosté ověřeni. Odeslání do UbyPortu proběhne automaticky po každém ověření.",
        "stay.detail.note.ready_manual": "Formuláře jsou hotové. Zkontrolujte údaje níže a odešlete, až budete připraveni.",
        "stay.detail.note.ready_scheduled": "Formuláře jsou hotové. Odešlou se %(hours)s h po příjezdu, nebo použijte Odeslat.",
        "stay.detail.note.automation": "Automatizace:",
        "stay.detail.note.immediate": "po ověření každého pasu",
        "stay.detail.note.scheduled": "%(hours)s h po příjezdu",
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
        "stay.detail.settings.email_hint": "Uloženo pro vaši referenci. UbyHost zatím neposílá e-maily.",
        "stay.detail.settings.host_only": "(pouze pro hostitele)",
        "stay.detail.settings.state": "Stav pobytu",
        "stay.detail.settings.state.active": "Aktivní",
        "stay.detail.settings.state.cancelled": "Zrušený",
        "stay.detail.settings.state.ignored": "Není pobyt hostů",
        "stay.detail.settings.state_hint": "„Není pobyt hostů“ odstraní položku z denní práce, ale zachová ji při synchronizaci kalendáře. Obnovíte výběrem Aktivní.",
        "stay.detail.settings.note": "Soukromá poznámka",
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

for _lang, _terms in TERMS_STRINGS.items():
    STRINGS.setdefault(_lang, {}).update(_terms)

for _lang, _privacy in PRIVACY_STRINGS.items():
    STRINGS.setdefault(_lang, {}).update(_privacy)

for _lang, _dpa in DPA_STRINGS.items():
    STRINGS.setdefault(_lang, {}).update(_dpa)


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
