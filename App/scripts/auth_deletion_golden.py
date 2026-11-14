"""Records Python's answers to POST /admin/users/{id}/schedule-deletion for go/internal/web/auth (brief 1509).

Run from App/: .venv/bin/python scripts/auth_deletion_golden.py
Writes go/internal/web/auth/testdata/schedule_deletion.json and refreshes the
package's i18n.json from i18n_keys.txt. It reuses auth_routes_golden.py
(brief 1282): the same seed, session and CSRF cookies, the real FastAPI app on
a fresh SQLite database. Only the clock of admin_accounts (datetime.now, which
sets the deletion date) is fixed, to FIXED below, so the date in the row, the
mail key, the audit detail and the flash is the same on every run; the Go test
runs at the same instant. Watched: audit, user_account.deletion_due_at and
email_outbox (no timestamps).
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import auth_routes_golden as base  # noqa: E402  (sets the environment, imports the app)

from app import db  # noqa: E402
from app.routes import admin_accounts  # noqa: E402
import go_host_i18n  # noqa: E402

OUT = base.PKG / "testdata" / "schedule_deletion.json"
FIXED = datetime(2099, 3, 4, 5, 6, 7, 890123, tzinfo=timezone.utc)
ENV = dict(base.ENV, UBYHOST_MAIL_BACKEND="console")

base.TABLES.append("email_outbox")
base.WATCH.clear()
base.WATCH.update({
    "audit": "SELECT action, actor, detail, owner_user_id, actor_user_id, impersonator_user_id FROM audit ORDER BY id",
    "user_account": "SELECT id, deletion_due_at FROM user_account ORDER BY id",
    "email_outbox": (
        "SELECT kind, idempotency_key, owner_user_id, to_email, cc_email, subject, payload, state, attempts "
        "FROM email_outbox ORDER BY id"
    ),
})


class _Fixed(datetime):
    @classmethod
    def now(cls, tz=None):
        return FIXED.astimezone(tz) if tz else FIXED.replace(tzinfo=None)


def seed():
    rows = base.base_seed()
    rows.append(base.account(6, "planned", email="planned@example.test", deletion_due_at=base.OLD))
    rows.append(["legal_entity", {"id": 4, "owner_user_id": 6, "name": "E4", "created_at": base.OLD,
                                  "contact_email": "planned@example.test"}])
    return rows


def cases():
    a = {"uid": 1}
    h = {"uid": 2}
    imp = {"uid": 1, "as": 2, "ast": -60}
    origin = {"origin": "http://testserver"}
    P = "POST"
    path = "/admin/users/{}/schedule-deletion".format
    return [
        {"name": "schedule", "method": P, "path": path(2), "session": a, "form": [["confirm", "host"]]},
        {"name": "schedule_cs_padded", "method": P, "path": path(2), "session": a, "form": [["confirm", "  host \n"]], "lang": "cs"},
        {"name": "schedule_vi", "method": P, "path": path(3), "session": a, "form": [["confirm", "totp"]], "lang": "vi"},
        {"name": "schedule_no_contacts", "method": P, "path": path(4), "session": a, "form": [["confirm", "late"]]},
        {"name": "schedule_inactive", "method": P, "path": path(5), "session": a, "form": [["confirm", "gone"]]},
        {"name": "schedule_again", "method": P, "path": path(6), "session": a, "form": [["confirm", "planned"]]},
        {"name": "schedule_own_account", "method": P, "path": path(1), "session": a, "form": [["confirm", "admin"]]},
        {"name": "schedule_impersonating", "method": P, "path": path(3), "session": imp, "form": [["confirm", "totp"]]},
        {"name": "schedule_last_confirm_wins", "method": P, "path": path(2), "session": a, "form": [["confirm", "x"], ["confirm", "host"]]},
        {"name": "schedule_mail_off", "method": P, "path": path(2), "session": a, "form": [["confirm", "host"]],
         "py_config": {"MAIL_BACKEND": "disabled"}, "env": {"UBYHOST_MAIL_BACKEND": "disabled"}},
        {"name": "confirm_wrong_case", "method": P, "path": path(2), "session": a, "form": [["confirm", "Host"]]},
        {"name": "confirm_missing", "method": P, "path": path(2), "session": a, "lang": "cs"},
        {"name": "confirm_last_wrong", "method": P, "path": path(2), "session": a, "form": [["confirm", "host"], ["confirm", "x"]]},
        {"name": "missing_user", "method": P, "path": path(99), "session": a, "form": [["confirm", "x"]], "lang": "cs"},
        {"name": "bad_id", "method": P, "path": "/admin/users/abc/schedule-deletion", "session": a},
        {"name": "bad_id_signed_out", "method": P, "path": "/admin/users/abc/schedule-deletion"},
        {"name": "host", "method": P, "path": path(2), "session": h, "form": [["confirm", "host"]], "lang": "cs"},
        {"name": "signed_out", "method": P, "path": path(2), "form": [["confirm", "host"]]},
        {"name": "no_csrf_same_site", "method": P, "path": path(2), "session": a, "csrf": False, "headers": origin,
         "form": [["confirm", "host"]]},
        {"name": "no_csrf_cross_site", "method": P, "path": path(2), "session": a, "csrf": False, "form": [["confirm", "host"]]},
    ]


def main() -> int:
    db.init_db()
    rows = seed()
    saved = admin_accounts.datetime
    admin_accounts.datetime = _Fixed
    try:
        recorded = [base.run(case, rows) for case in cases()]
    finally:
        admin_accounts.datetime = saved
    out = {"secret": base.SECRET, "nonce": base.NONCE, "env": ENV, "fixed": FIXED.isoformat(),
           "seed": rows, "cases": recorded}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(base.REPO)}")
    catalog = base.PKG / "i18n.json"
    catalog.write_text(go_host_i18n.render(go_host_i18n.read_keys(base.PKG / "i18n_keys.txt")), encoding="utf-8")
    print(f"wrote {catalog.relative_to(base.REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
