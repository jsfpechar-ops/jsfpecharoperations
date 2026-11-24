"""Page table for the visual parity run (briefs 2040-2042). Data only.

One row = (name, path template, persona, group). Persona is "host" (user h1) or "admin".
Anonymous pages are out of scope. Placeholders are filled by page_parity_visual.fill():
{apt} {res} {guest} {inv} {hinv} {fee_a} {alfa} {tok}
Groups: A account+admin, B host core, C money, D setup+cleaning+guide (empty states).
Brief 2041 adds EXTRA_CASES (groups E, F, G, populated pages from seed_parity_extra.py).
"""

GUIDE_QUICK_STEPS = ("times", "rules", "access", "kitchen", "comfort")  # from guide_facts.STEPS

CASES = [
    # A: account and admin
    ("home-host", "/", "host", "A"),
    ("2fa-setup", "/account/2fa/setup", "host", "A"),
    ("2fa-setup-moved", "/account/2fa/setup?moved=1", "host", "A"),
    ("admin-home", "/admin", "admin", "A"),
    ("admin-operations", "/admin/operations", "admin", "A"),
    ("admin-ops-alerts", "/admin/operations/alerts", "admin", "A"),
    ("admin-customers", "/admin/customers", "admin", "A"),
    ("admin-customers-overdue", "/admin/customers?state=overdue", "admin", "A"),
    ("admin-customers-trialing", "/admin/customers?state=trialing", "admin", "A"),
    ("admin-customer", "/admin/customers/{alfa}", "admin", "A"),
    ("admin-fakturace", "/admin/fakturace", "admin", "A"),
    ("privacy-requests", "/privacy-requests", "admin", "A"),
    ("dev-ui", "/dev/ui", "admin", "A"),
    # B: host core
    ("menu", "/menu", "host", "B"),
    ("settings", "/settings", "host", "B"),
    ("settings-archived", "/settings/archived", "host", "B"),
    ("predplatne", "/predplatne", "host", "B"),
    ("onboarding", "/onboarding", "host", "B"),
    ("entities", "/entities", "host", "B"),
    ("apartments", "/apartments", "host", "B"),
    ("apartments-new", "/apartments/new", "host", "B"),
    ("apartment-detail", "/apartments/{apt}", "host", "B"),
    ("reservations", "/reservations", "host", "B"),
    ("reservation-detail", "/reservations/{res}", "host", "B"),
    ("guest-form-new", "/reservations/{res}/guests/new", "host", "B"),
    ("guest-detail", "/guests/{guest}", "host", "B"),
    ("housebook", "/housebook", "host", "B"),
    ("submissions", "/submissions", "host", "B"),
    # C: money
    ("stay-fees", "/stay-fees", "host", "C"),
    ("stay-fee-detail", "/stay-fees/{fee_a}", "host", "C"),
    ("invoices", "/invoices", "host", "C"),
    ("invoices-new", "/invoices/new", "host", "C"),
    ("invoice-detail", "/invoices/{hinv}", "host", "C"),
    # D: setup, cleaning, guide (empty states: no data is seeded for these yet)
    ("cleaning", "/cleaning", "host", "D"),
    ("cleaning-new", "/cleaning/new", "host", "D"),
    ("cleaning-properties", "/cleaning/properties", "host", "D"),
    ("cleaning-property", "/cleaning/properties/{apt}", "host", "D"),
    ("cleaning-shares", "/cleaning/shares", "host", "D"),
    ("havel", "/havel", "host", "D"),
    ("guide", "/guide", "host", "D"),
    ("apt-guide", "/apartments/{apt}/guide", "host", "D"),
    ("apt-guide-qr", "/apartments/{apt}/guide/qr", "host", "D"),
    ("apt-guide-questions", "/apartments/{apt}/guide/questions", "host", "D"),
    ("leon-settings", "/apartments/{apt}/leon", "host", "D"),
] + [
    (f"wizard-{s}", f"/apartments/{{apt}}/setup/{s}", "host", "D")
    for s in ("property", "calendar", "door_lock", "automation", "guest_link", "police", "stay_fee", "try_it", "done")
] + [
    (f"leon-setup-{s}", f"/apartments/{{apt}}/leon/setup/{s}", "host", "D")
    for s in ("cards", "import", "try", "switch_on", "done")
]

# One case that shows the two-factor prompt modal on purpose in both stacks (PRE_SQL clears the prompt).
MODAL_CASES = [
    ("two-factor-modal", "/reservations", "host", "B"),
]

# Deliberate differences, kept as Go has them. Key = case name without "-cs"/"-en". Reported separately, not failures.
ACCEPTED = {
    "apt-guide": "Go keeps the newer External guide link card (Link (https) / Save link) above the Booking or Airbnb import; Python lacks it. Python import-title spacing differs as a consequence.",
    "dev-ui": "dev_ui is not ported; it is deleted with Python (docs/plans/go-full-move.md). The only diff is a CSS spinner frame.",
}

# Cases with a QR image: its pixels are masked, and its payload text is compared separately.
QR_PAYLOAD_CASES = {
    "2fa-setup": {"mask": ["img.auth-setup-qr"], "texts": ["a.auth-setup-open@href", ".auth-setup-key|#totp-setup-key"]},
    "2fa-setup-moved": {"mask": ["img.auth-setup-qr"], "texts": ["a.auth-setup-open@href", ".auth-setup-key|#totp-setup-key"]},
    "apt-guide-qr": {"mask": ["img.guide-qr"], "texts": [".ui-mono"]},
}

# Brief 2041. Placeholders not produced by seed_parity_extra.py skip their row as SKIPPED.
# Persona "anon_invite": no cookie on either stack (the invite link works signed out).
EXTRA_CASES = [
    # E: populated versions of pages that were empty in 2040
    ("cleaning-full", "/cleaning", "host", "E"),
    ("cleaning-edit", "/cleaning/events/{cleaning_event}/edit", "host", "E"),
    ("cleaning-shares-full", "/cleaning/shares", "host", "E"),
    ("havel-full", "/havel", "host", "E"),
    ("privacy-requests-full", "/privacy-requests", "admin", "E"),
    ("submissions-full", "/submissions", "host", "E"),
    ("submission-draft", "/submissions/{submission_id}", "host", "E"),
    ("submission-sent", "/submissions/{submission_sent}", "host", "E"),
    ("apartments-full", "/apartments", "host", "E"),
    ("property-detail", "/apartments/{property_id}", "host", "E"),
    ("account-accept", "/account/accept?token={invite_token}", "anon_invite", "E"),
    # F: guide, questions, Leon (populated)
    ("apt-guide-full", "/apartments/{apt}/guide", "host", "F"),
    ("guide-item", "/apartments/{apt}/guide/{guide_item}", "host", "F"),
    ("guide-questions-full", "/apartments/{apt}/guide/questions", "host", "F"),
    ("guide-question", "/apartments/{apt}/guide/questions/{question_id}", "host", "F"),
    ("guide-quick-done", "/apartments/{apt}/guide/quick/done", "host", "F"),
    ("leon-settings-full", "/apartments/{apt}/leon", "host", "F"),
    ("leon-setup-cards-full", "/apartments/{apt}/leon/setup/cards", "host", "F"),
] + [
    (f"guide-quick-{s}", f"/apartments/{{apt}}/guide/quick/{s}", "host", "F")
    for s in GUIDE_QUICK_STEPS
] + [
    # G: variants of existing pages (query parameters checked in the routes)
    # "invoices-new-picker" (/invoices/new?step=) and "settings-tab-account" (/settings?tab=) removed: no such variant.
    ("reservations-past", "/reservations?range=past", "host", "G"),
    ("stay-fees-oct", "/stay-fees?month=2026-10", "host", "G"),
]
