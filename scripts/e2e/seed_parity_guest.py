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
from app import claim, cleaning, config, db, lifecycle_mail  # noqa: E402

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
    out["res_locked"] = stay(apt, "e2e-guest-locked")
    set_claim(out["res_locked"], state="claimed", claimed_at=now, token_version=1, declared_guests=2,
              token_hash=None, guest_access_locked_at=now, updated_at=now)
    out["res_gone"] = stay(apt, "e2e-guest-gone", status="cancelled")


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


def cookies(out, owner, apt):
    secret = config.secret_key()
    out["claim_cookie"] = URLSafeSerializer(secret, salt="ubyhost-guest-claim").dumps(
        {str(out["res_claimed"]): 1, str(out["res_locked"]): 1})
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
