"""Synthetic guest-persona rows for the visual parity run (brief 2042).

Run from App/ on parity_run, after scripts/e2e/seed.py:
    python ../scripts/e2e/seed_parity_guest.py <owner_user_id> <apartment_id>

Prints one JSON object on stdout: reservation ids per guest state, guest row ids,
the claim and owned cookie values (signed with the audit env secret), share and
unsubscribe tokens. A block that fails is named on stderr as {"skipped": "<block>"}.
Only synthetic data ("Parity Guest", *@e2e.test). Retired features are never seeded.
"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.getcwd())
from itsdangerous import URLSafeSerializer  # noqa: E402
from app import auth, claim, cleaning, config, db, lifecycle_mail  # noqa: E402

SECRET = "e2e-claim-secret"
SIG = "data:image/png;base64,iVBORw0KGgo="


def block(name, fn, out):
    try:
        fn(out)
    except Exception as exc:  # one missing helper never kills the run
        print(json.dumps({"skipped": name, "reason": str(exc)[:160]}), file=sys.stderr)


def stay(apt, uid, status="active"):
    today = datetime.date.today()
    d_from = (today + datetime.timedelta(days=10)).isoformat()
    d_to = (today + datetime.timedelta(days=13)).isoformat()
    now = db.utcnow()
    return db.insert("reservation", {
        "apartment_id": apt, "source": "manual", "uid": uid, "date_from": d_from, "date_to": d_to,
        "status": status, "created_at": now, "updated_at": now,
    })


def set_claim(rid, **cols):
    claim.ensure_row(rid)
    sets = ", ".join(f"{k} = ?" for k in cols)
    db.execute(f"UPDATE reservation_claim SET {sets} WHERE reservation_id = ?", (*cols.values(), rid))


def states(out, owner, apt):
    out["res_unclaimed"] = stay(apt, "e2e-guest-unclaimed")
    claim.ensure_row(out["res_unclaimed"])
    out["res_provisional"] = stay(apt, "e2e-guest-provisional")
    set_claim(
        out["res_provisional"], state="provisional", email="parity@e2e.test", email_masked="p***@e2e.test",
        token_hash=claim.token_hash(SECRET), token_version=1, lang="en",
        provisional_until=(datetime.datetime.utcnow() + datetime.timedelta(hours=6)).replace(microsecond=0).isoformat(),
        updated_at=db.utcnow(),
    )
    out["res_claimed"] = stay(apt, "e2e-guest-claimed")
    now = db.utcnow()
    set_claim(out["res_claimed"], state="claimed", claimed_at=now, token_version=1, declared_guests=2,
              token_hash=None, updated_at=now)
    # 2064: claimed stay in its own apartment with the stay-fee box (fee flags set only here).
    ent = db.query_one("SELECT legal_entity_id FROM apartment WHERE id = ?", (apt,))["legal_entity_id"]
    db.execute("UPDATE legal_entity SET iban = 'CZ6508000000192000145399' WHERE id = ? AND (iban IS NULL OR iban = '')", (ent,))
    fee_apt = db.insert("apartment", {
        "internal_name": "Parity Fee Flat", "owner_user_id": owner, "legal_entity_id": ent,
        "permalink_token": os.urandom(9).hex(), "permalink_pin": auth.new_permalink_pin(),
        "automation_mode": "manual", "default_purpose": "10", "active": 1, "created_at": db.utcnow(),
        "stay_fee_collect": 1, "stay_fee_rate_czk": 50, "stay_fee_guest_rails": "qr,iban",
    })
    out["res_fee"] = stay(fee_apt, "e2e-guest-fee")
    now = db.utcnow()
    set_claim(out["res_fee"], state="claimed", claimed_at=now, token_version=1, declared_guests=1,
              token_hash=None, updated_at=now)
    db.execute("UPDATE reservation SET declared_guests = 1 WHERE id = ?", (out["res_fee"],))
    out["res_locked"] = stay(apt, "e2e-guest-locked")
    set_claim(out["res_locked"], state="claimed", claimed_at=now, token_version=1, declared_guests=2,
              token_hash=None, guest_access_locked_at=now, updated_at=now)
    out["res_gone"] = stay(apt, "e2e-guest-gone", status="cancelled")
    issued(out, owner, apt)


def guests(out, owner, apt):
    now = db.utcnow()
    out["guest_complete"] = db.insert("guest", {
        "reservation_id": out["res_claimed"], "first_name": "Parity", "surname": "Guest",
        "birth_date": "01011990", "nationality": "DEU", "signature_png": SIG,
        "created_at": now, "updated_at": now,
    })
    out["guest_partial"] = db.insert("guest", {
        "reservation_id": out["res_claimed"], "first_name": "Parity", "surname": None,
        "birth_date": None, "nationality": None, "signature_png": None,
        "created_at": now, "updated_at": now,
    })


    out["guest_fee"] = db.insert("guest", {
        "reservation_id": out["res_fee"], "first_name": "Parity", "surname": "Fee",
        "birth_date": "01011990", "nationality": "CZE", "signature_png": SIG,
        "created_at": now, "updated_at": now,
    })


def sig_png():
    """A small real PNG signature (synthetic stroke), so the stored record validates."""
    import base64
    import struct
    import zlib
    w, h = 240, 80
    rows = []
    for y in range(h):
        line = bytearray(b"\x00")
        for x in range(w):
            on = 20 < x < w - 20 and abs(y - (h // 2 + (x - w // 2) // 6)) <= 1
            line += b"\x00\x00\x00" if on else b"\xff\xff\xff"
        rows.append(bytes(line))

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(b"".join(rows))) + chunk(b"IEND", b""))
    return "data:image/png;base64," + base64.b64encode(png).decode()


def issued(out, owner, apt):
    """Claimed stay, all declared guests complete, one ISSUED door code (brief 2057 priority 2)."""
    now = db.utcnow()
    out["res_issued"] = stay(apt, "e2e-guest-issued")
    set_claim(out["res_issued"], state="claimed", claimed_at=now, token_version=1, declared_guests=1,
              token_hash=None, updated_at=now)
    db.execute("UPDATE reservation SET declared_guests = 1 WHERE id = ?", (out["res_issued"],))
    db.insert("guest", {
        "reservation_id": out["res_issued"], "first_name": "Parity", "surname": "Issued",
        "birth_date": "01011990", "nationality": "DEU", "signature_png": SIG,
        "created_at": now, "updated_at": now,
    })
    out["door_code_issued"] = db.insert("door_code", {
        "reservation_id": out["res_issued"], "apartment_id": apt, "lock_id": "e2e-lock-parity",
        "code_kind": "random", "state": "issued", "attempts": 0, "issued_at": now,
        "pin_enc": db.encrypt_field("246810"),
        "valid_from": now, "valid_to": now, "next_attempt_at": now, "created_at": now, "updated_at": now,
    })

    out["res_issued_done"] = stay(apt, "e2e-guest-issued-done")
    set_claim(out["res_issued_done"], state="claimed", claimed_at=now, token_version=1, declared_guests=1,
              token_hash=None, updated_at=now)
    db.execute("UPDATE apartment SET lock_provider = 'ttlock', checkin_hour = 14, checkout_hour = 11 WHERE id = ?", (apt,))
    db.execute("UPDATE reservation SET registration_completed_at = ?, declared_guests = 1 WHERE id = ?", (now, out["res_issued_done"]))
    gid = db.insert("guest", {
        "reservation_id": out["res_issued_done"], "first_name": "Parity", "surname": "Done",
        "birth_date": "01011990", "nationality": "DEU", "signature_png": sig_png(),
        "doc_number": "E2E000000", "res_street": "Parity Street 1", "res_city": "Prague",
        "res_country": "CZE", "purpose": "99",
        "created_at": now, "updated_at": now,
    })
    today = datetime.date.today()
    d_from = (today + datetime.timedelta(days=10)).isoformat()
    d_to = (today + datetime.timedelta(days=13)).isoformat()
    db.insert("door_code", {
        "reservation_id": out["res_issued_done"], "apartment_id": apt, "lock_id": "e2e-lock-parity",
        "code_kind": "random", "state": "issued", "attempts": 0, "issued_at": now, "pin_enc": db.encrypt_field("246810"),
        "valid_from": f"{d_from}T14:00:00", "valid_to": f"{d_to}T11:00:00",
        "next_attempt_at": now, "created_at": now, "updated_at": now,
    })
    from app import reporting  # debug: lists what still blocks the guest (no guest data printed)
    row = db.query_one("SELECT * FROM guest WHERE id = ?", (gid,))
    res = db.query_one("SELECT * FROM reservation WHERE id = ?", (out["res_issued_done"],))
    print(json.dumps({"issued_done_issues": [str(i)[:80] for i in reporting.guest_issues(row, res)]}), file=sys.stderr)
    # door card diagnostics: states and counts only, no guest data
    from app import door_codes
    apt_row = db.query_one("SELECT * FROM apartment WHERE id = ?", (apt,))
    door_row = db.query_one("SELECT state FROM door_code WHERE reservation_id = ?", (out["res_issued_done"],))
    try:
        shown = door_codes.view(res, apt_row)
        view_state = shown.get("state", "shown") if shown else "none"
    except Exception as exc:
        view_state = f"error:{type(exc).__name__}"
    print(json.dumps({
        "lock_provider": apt_row["lock_provider"] if apt_row else None,
        "checkin_hour": apt_row["checkin_hour"] if apt_row else None,
        "door_code_state": door_row["state"] if door_row else "none",
        "view_state": view_state,
    }), file=sys.stderr)


def cookies(out, owner, apt):
    secret = config.secret_key()
    out["claim_cookie"] = URLSafeSerializer(secret, salt="ubyhost-guest-claim").dumps(
        {str(out["res_claimed"]): 1, str(out["res_locked"]): 1, str(out["res_issued"]): 1, str(out["res_issued_done"]): 1, str(out["res_fee"]): 1})
    out["owned_cookie"] = URLSafeSerializer(secret, salt="ubyhost-guest-owned").dumps(
        [out["guest_complete"], out["guest_partial"]])


def tokens(out, owner, apt):
    _, out["share_token"] = cleaning.new_share(owner, [apt])
    out["unsub_token"] = lifecycle_mail.unsubscribe_token(owner)


def main():
    owner, apt = int(sys.argv[1]), int(sys.argv[2])
    out = {}
    for name, fn in (("states", states), ("guests", guests), ("cookies", cookies), ("tokens", tokens)):
        block(name, lambda o, f=fn: f(o, owner, apt), out)
    print(json.dumps(out))


main()
