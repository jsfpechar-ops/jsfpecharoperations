"""Page table for the visual parity run (briefs 2040-2042). Data only.

One row = (name, path template, persona, group). Persona is "host" (user h1) or "admin".
Anonymous pages are out of scope. Placeholders are filled by page_parity_visual.fill():
{apt} {res} {guest} {inv} {hinv} {fee_a} {alfa} {tok}
Groups: A account+admin, B host core, C money, D setup+cleaning+guide (empty states).
"""

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
    ("payments", "/payments", "host", "C"),
    ("payments-new", "/payments/new", "host", "C"),
    ("payments-consent", "/payments/consent", "host", "C"),
    ("booking-sites", "/booking-sites", "host", "C"),
    ("booking-site-setup", "/apartments/{apt}/booking-site", "host", "C"),
    ("property-page-review", "/apartments/{apt}/page", "host", "C"),
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
