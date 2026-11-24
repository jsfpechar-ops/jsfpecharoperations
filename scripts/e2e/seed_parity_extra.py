"""Synthetic extra data for the visual parity run (brief 2041).

Run from App/ on parity_run, after scripts/e2e/seed.py:
    python ../scripts/e2e/seed_parity_extra.py <owner_user_id> <apartment_id> <reservation_id>

Prints one JSON object of ids on stdout. A block that fails is named on stderr as
{"skipped": "<block>"} and the run goes on. Only synthetic text ("E2E ...", *@e2e.test).
Retired features (booking site, payment requests) are never seeded.
"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.getcwd())
from app import cleaning, db, dsr, guest_guide, havel, leon, lifecycle_mail, auth, login_link  # noqa: E402


def block(name, fn, out):
    try:
        fn(out)
    except Exception as exc:  # one missing helper or table never kills the run
        print(json.dumps({"skipped": name, "reason": str(exc)[:160]}), file=sys.stderr)


def guide(out, owner, apt):
    # Four cards: two with steps or a location (done), two left missing.
    kinds = list(guest_guide.KINDS)[:4]
    for kind in kinds:
        guest_guide.add_kind(apt, kind)
    ids = []
    for kind in kinds:
        row = db.query_one("SELECT id FROM guide_item WHERE apartment_id = ? AND kind = ?", (apt, kind))
        ids.append(row["id"])
    guest_guide.save(apt, ids[0], {"steps": "E2E steps text", "location": ""})
    guest_guide.save(apt, ids[1], {"steps": "", "location": "E2E location text"})
    out["guide_item"] = ids[0]
    out["guide_items"] = ids
    out["custom_item"] = guest_guide.add_custom(apt, "wifi", "E2E custom card")


def questions(out, owner, apt):
    res = db.query_one("SELECT id FROM reservation WHERE apartment_id = ? ORDER BY id LIMIT 1", (apt,))
    chat = leon.stay_chat(apt, res["id"], "en")
    now = db.utcnow()
    m1 = leon._store(chat["id"], "guest", "question", "E2E: is there a late check-in option?")
    m2 = leon._store(chat["id"], "guest", "question", "E2E: the heating is not working and it is freezing")
    leon._store(chat["id"], "leon", "answer", "E2E: I passed this to your host.")
    out["question_open"] = db.insert("guest_question", {
        "chat_id": chat["id"], "message_id": m1, "apartment_id": apt,
        "summary": "E2E question still open", "status": "open", "answer": "",
        "urgent": 0, "triaged": 1, "created_at": now,
    })
    out["question_id"] = db.insert("guest_question", {
        "chat_id": chat["id"], "message_id": m2, "apartment_id": apt,
        "summary": "E2E urgent: no heating", "status": "open", "answer": "",
        "urgent": 1, "triaged": 1, "created_at": now,
    })
    out["question_answered"] = db.insert("guest_question", {
        "chat_id": chat["id"], "message_id": m1, "apartment_id": apt,
        "summary": "E2E question answered", "status": "answered", "answer": "E2E answer text",
        "urgent": 0, "triaged": 1, "created_at": now, "answered_at": now,
    })


def leon_block(out, owner, apt):
    db.execute("UPDATE apartment SET leon_enabled = 1, leon_terms_version = ? WHERE id = ?",
               (leon.LEON_TERMS_VERSION, apt))
    out["leon_enabled"] = 1


def cleaning_block(out, owner, apt):
    today = datetime.date.today()
    first = None
    for i in range(3):
        day = (today + datetime.timedelta(days=i + 1)).isoformat()
        eid = cleaning.save_event(apt, {"scheduled_date": day, "notes": f"E2E cleaning {i + 1}"})
        first = first or eid
    _share_id, token = cleaning.new_share(owner, [apt])
    out["cleaning_event"] = first
    out["share_token"] = token


def havel_block(out, owner, apt):
    for kind in havel.GAP_KINDS:
        havel.record_gap("en", "host", kind, f"E2E question ({kind})")
    for kind in tuple(getattr(havel, "STAT_KINDS", ()))[:3]:
        havel.record_stat(kind)


def privacy(out, owner, apt):
    now = db.utcnow()
    out["dsr_id"] = dsr.create(owner_user_id=owner, received_at=now, channel="email",
                               request_type="access", subject_kind="guest")
    dsr.create(owner_user_id=owner, received_at=now, channel="post",
               request_type="erasure", subject_kind="guest")


def submission(out, owner, apt):
    now = db.utcnow()
    rows = db.query(
        "SELECT r.apartment_id, g.id FROM guest g JOIN reservation r ON r.id = g.reservation_id "
        "JOIN apartment a ON a.id = r.apartment_id WHERE a.owner_user_id = ? "
        "ORDER BY r.apartment_id, g.id", (owner,))
    if not rows:
        raise RuntimeError("no guests for the apartment; not seeded")
    apt = rows[0]["apartment_id"]
    ids = [r["id"] for r in rows if r["apartment_id"] == apt][:2]
    guests = json.dumps(ids)
    endpoint = "https://example.invalid/e2e"
    out["submission_ok"] = db.insert("submission", {
        "apartment_id": apt, "created_at": now, "mode": "completion_immediate", "state": "ok",
        "guest_ids": guests, "endpoint": endpoint, "finished_at": now,
        "pseudo_stamp": "E2E-STAMP-0001", "receipt_pdf": "E2E-RECEIPT", "header_errors": "",
        "record_errors": json.dumps(["" for _ in ids]),
    })
    out["submission_error"] = db.insert("submission", {
        "apartment_id": apt, "created_at": now, "mode": "auto", "state": "error",
        "guest_ids": guests, "endpoint": endpoint, "finished_at": now,
        "pseudo_stamp": "E2E-STAMP-0002", "header_errors": "",
        "record_errors": json.dumps(["E2E record problem"] + ["" for _ in ids[1:]]),
    })
    out["submission_transport"] = db.insert("submission", {
        "apartment_id": apt, "created_at": now, "mode": "completion_immediate",
        "state": "transport_error", "guest_ids": guests, "endpoint": endpoint,
        "finished_at": now, "error_text": "E2E connection refused",
    })
    out["submission_running"] = db.insert("submission", {
        "apartment_id": apt, "created_at": now, "mode": "completion_immediate",
        "state": "running", "guest_ids": guests, "endpoint": endpoint,
    })
    # Legacy row: only the early columns; mode, guest_ids and the rest stay NULL (brief 2051 fix).
    out["submission_legacy"] = db.insert("submission", {
        "apartment_id": apt, "created_at": now, "state": "ok", "finished_at": now,
    })
    out["submission_id"] = out["submission_error"]
    out["submission_sent"] = out["submission_ok"]


def invite(out, owner, apt):
    acct_id = auth.create_account("invitee@e2e.test", "E2E Invitee", role="host")
    row = db.query_one("SELECT * FROM user_account WHERE id = ?", (acct_id,))
    out["invite_token"] = login_link.issue(row, purpose=login_link.INVITE, remember=True)


def property_block(out, owner, apt):
    row = db.query_one(
        "SELECT id FROM apartment WHERE owner_user_id = ? AND id <> ? ORDER BY id LIMIT 1", (owner, apt)
    )
    if not row:
        raise RuntimeError("no second apartment in the seed")
    out["property_id"] = row["id"]


def unsub(out, owner, apt):
    out["unsub_token"] = lifecycle_mail.unsubscribe_token(owner)


def main():
    owner, apt = int(sys.argv[1]), int(sys.argv[2])
    out = {}
    for name, fn in (
        ("guide", guide), ("questions", questions), ("leon", leon_block), ("cleaning", cleaning_block),
        ("havel", havel_block), ("privacy", privacy), ("submission", submission), ("invite", invite),
        ("property", property_block), ("unsub", unsub),
    ):
        block(name, lambda o, f=fn: f(o, owner, apt), out)
    print(json.dumps(out))


main()
