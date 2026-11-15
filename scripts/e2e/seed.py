"""Seed the shared e2e template database (run from App/ with the app venv).

Creates: admin, host h1 (no 2FA), host h2 (TOTP on, known secret), one apartment
and one reservation for h1. Prints JSON: session cookies, TOTP secret,
recovery codes, one login-link secret per user (the hash sits in the template,
so each cloned database can spend its own copy once).
"""
import json
import os
import sys

sys.path.insert(0, os.getcwd())
from app import acceptance, auth, db, login_link  # noqa: E402


def main():
    db.apply_postgresql_schema()
    out = {}
    # Realistic billing data: the billing_admin golden fixture (12 users, plans, ~70
    # invoices incl. a voided invoice with its storno, overdue and paid ones).
    sys.path.insert(0, os.path.join(os.getcwd(), "scripts"))
    import billing_admin_golden as G  # noqa: E402

    G._seed(db)
    for t in G.SEED:
        if "id" in t["columns"]:
            
            db.query(f"SELECT setval(pg_get_serial_sequence('{t['table']}', 'id'), (SELECT COALESCE(MAX(id), 1) FROM {t['table']}))")
    seeded_ids = [r[0] for r in G.USERS]
    for uid in seeded_ids:
        acceptance.record(uid, acceptance.DOCUMENTS, "backfill")
    for name, uid in (("alfa", 2), ("cenek", 4), ("admin", 1)):
        acct = db.query_one("SELECT * FROM user_account WHERE id = ?", (uid,))
        out[name] = {"id": uid, "username": acct["username"], "session": auth.issue_session(uid, acct["session_version"]),
                     "link": login_link.issue(acct, remember=False)}
    h1 = auth.create_account("h1@e2e.test", "Host One", username="host-one")
    h2 = auth.create_account("h2@e2e.test", "Host Two", username="host-two")
    secret = auth.new_totp_secret()
    codes = auth.new_recovery_codes()
    auth.enable_totp(h2, secret, codes)
    for uid in (h1, h2):
        acceptance.record(uid, acceptance.DOCUMENTS, "backfill")
    for name, uid in (("h1", h1), ("h2", h2)):
        acct = db.query_one("SELECT * FROM user_account WHERE id = ?", (uid,))
        out[name] = {
            "id": uid,
            "username": acct["username"],
            "session": auth.issue_session(uid, acct["session_version"]),
            "link": login_link.issue(acct, remember=False),
        }
    # Real invoices (stored PDF, snapshot with items) for host h1, issued by the app itself.
    from datetime import date, timedelta

    from app import billing, billing_invoices, config

    config.BILLING_ENABLED = True
    config.BILLING_IBAN = "CZ6503000000000123456789"
    db.insert("apartment", {"internal_name": "E2E 1", "owner_user_id": h1, "created_at": db.utcnow(), "permalink_pin": auth.new_permalink_pin()})
    billing.ensure_account(h1)
    today = date.today()
    db.execute(
        "UPDATE billing_account SET status = 'active', plan = 'standard', billing_interval = 'month', "
        "apartments_billed = 1, period_start = ?, period_end = ?, buyer_name = 'E2E Penzion', "
        "buyer_street = 'Hlavni 3', buyer_city = 'Brno', buyer_zip = '60200', buyer_ico = '27074358' "
        "WHERE owner_user_id = ?",
        (today.isoformat(), (today + timedelta(days=29)).isoformat(), h1),
    )
    db.execute("INSERT INTO platform_invoice_sequence (year, last_no) VALUES (?, ?) "
               "ON CONFLICT(year) DO UPDATE SET last_no = EXCLUDED.last_no",
               (today.year, int(db.query_one("SELECT COALESCE(MAX(seq_no), 0) AS n FROM platform_invoice WHERE seq_year = ?", (today.year,))["n"])))
    ids = []
    for k in range(3):
        start = today + timedelta(days=30 * k)
        ids.append(billing_invoices.issue_for_period(h1, start.isoformat(), (start + timedelta(days=29)).isoformat(), today=today))
    out["invoices"] = ids
    # Host (guest) invoices for h1 with a legal entity, issued by the app itself.
    from app import invoice_links, invoices

    ent = db.insert("legal_entity", {"name": "E2E Penzion s.r.o.", "seat": "Praha", "ico": "04656679", "registry_entry": "ZR",
                                     "vat_status": "non_payer", "invoice_due_days": 14, "owner_user_id": h1, "contact_email": "desk@e2e.test", "created_at": db.utcnow()})

    def draft(total, label):
        return {"legal_entity_id": ent, "apartment_id": None, "reservation_id": None, "owner_user_id": h1, "kind": "invoice", "lang": "cs",
                "vat_status": "non_payer", "issue_date": today.isoformat(), "duzp": None, "due_date": None, "paid_on": None, "paid_via": None,
                "seller": {"name": "E2E Penzion s.r.o.", "seat": "Praha", "ico": "04656679", "dic": "", "registry": "ZR", "bank_account": "",
                          "iban": "", "bic": "", "email": "", "phone": ""},
                "buyer": {"name": "Buyer " + label, "street": "", "city": "", "zip": "", "country": "CZE", "ico": "", "dic": "", "email": ""},
                "stay_from": (today - timedelta(days=5)).isoformat(), "stay_to": (today - timedelta(days=2)).isoformat(), "stay_label": "Flat",
                "items": [{"kind": "accommodation", "description": "Ubytovani " + label, "quantity": 1, "unit": "pobyt", "vat_rate": None,
                           "base_haler": None, "vat_haler": None, "gross_haler": total}],
                "total_base_haler": None, "total_vat_haler": None, "total_haler": total}

    hids = [invoices.issue(draft(t, l), actor_user_id=h1) for t, l in ((400000, "A"), (250000, "B"), (99900, "C"))]
    out["host_invoices"] = hids
    row = db.query_one("SELECT pdf_sha256 FROM invoice WHERE id = ?", (hids[2],))
    # Stays: two ended yesterday (host invoices), and October stay-fee apartments (one clean, one with an unsigned guest).
    import secrets as _sec
    SIG = "data:image/png;base64,AAAA"
    now = db.utcnow()

    def apt(name, **kw):
        return db.insert("apartment", dict({"internal_name": name, "owner_user_id": h1, "legal_entity_id": ent, "permalink_token": _sec.token_urlsafe(12),
                                            "permalink_pin": auth.new_permalink_pin(), "automation_mode": "manual", "default_purpose": "10",
                                            "active": 1, "created_at": now}, **kw))

    def stay(apartment_id, d_from, d_to, uid):
        return db.insert("reservation", {"apartment_id": apartment_id, "source": "manual", "uid": uid, "date_from": d_from, "date_to": d_to,
                                         "status": "active", "created_at": now, "updated_at": now})

    inv_apt = apt("Chata")
    out["stays"] = [stay(inv_apt, (today - timedelta(days=4)).isoformat(), (today - timedelta(days=1)).isoformat(), f"e2e-inv-{k}") for k in range(3)]
    fee = dict(addr_obec="Praha 3", stay_fee_rate_czk=50, stay_fee_cadence="monthly", stay_fee_vs="123456", stay_fee_authority_name="Mestsky urad",
               stay_fee_council_account="19-2000781379/0800", stay_fee_council_iban="CZ3008000000192000781379")
    fee_a, fee_b = apt("Fee Flat A", **fee), apt("Fee Flat B", **fee)
    ra = stay(fee_a, "2026-10-10", "2026-10-14", "e2e-fee-a")
    rb = stay(fee_b, "2026-10-12", "2026-10-15", "e2e-fee-b")

    def guest(rid, first, birth, sig):
        return db.insert("guest", {"reservation_id": rid, "first_name": first, "surname": "Demo", "birth_date": birth, "nationality": "DEU",
                                   "signature_png": sig, "created_at": now, "updated_at": now})

    ga = [guest(ra, "Ada", "01011990", SIG), guest(ra, "Bob", "01012016", SIG)]
    guest(rb, "Cyd", "01011985", None)  # unsigned: blocks sealing
    out["fee"] = {"a": fee_a, "b": fee_b, "month": "2026-10", "guests_a": ga}
    out["host_invoice_token"] = invoice_links.download_token(hids[2], row["pdf_sha256"])
    h3 = auth.create_account("h3@e2e.test", "Host Three", username="host-three")
    secret3 = auth.new_totp_secret()
    auth.enable_totp(h3, secret3, auth.new_recovery_codes())
    acceptance.record(h3, acceptance.DOCUMENTS, "backfill")
    acct3 = db.query_one("SELECT * FROM user_account WHERE id = ?", (h3,))
    out["h3"] = {"id": h3, "username": "host-three", "session": auth.issue_session(h3, acct3["session_version"]),
                 "link": login_link.issue(acct3, remember=False), "totp_secret": secret3}
    out["h2"]["totp_secret"] = secret
    out["h2"]["recovery_codes"] = codes
    json.dump(out, sys.stdout)


main()
