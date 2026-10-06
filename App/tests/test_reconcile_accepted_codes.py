"""K-F13: guests answered with 112 only are in the register, so mark them filed."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from app import db, reporting
from tests.test_send_controls import _seed

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "reconcile_accepted_codes.py"


def _load():
    spec = importlib.util.spec_from_file_location("reconcile_accepted_codes", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _submission(apartment_id, guest_id, record_error):
    return db.insert("submission", {
        "apartment_id": apartment_id,
        "created_at": db.utcnow(),
        "state": "error",
        "guest_ids": json.dumps([guest_id]),
        "record_errors": json.dumps([record_error]),
        "header_errors": "",
    })


def test_a_late_only_guest_is_marked_filed_and_a_refused_one_is_not(capsys):
    script = _load()
    apartment, _r, late = _seed("manual", "tok-kf13-late")
    apartment2, _r2, refused = _seed("manual", "tok-kf13-refused")
    try:
        s1 = _submission(apartment["id"], late, ";112;")
        s2 = _submission(apartment2["id"], refused, ";106;")
        db.update("guest", late, {"submit_state": reporting.ERROR, "submission_id": s1, "submit_attempts": 3})
        db.update("guest", refused, {"submit_state": reporting.ERROR, "submission_id": s2})

        assert script.main([]) == 0
        assert db.query_one("SELECT submit_state FROM guest WHERE id = ?", (late,))["submit_state"] == "error"

        assert script.main(["--apply"]) == 0
        late_row = db.query_one("SELECT * FROM guest WHERE id = ?", (late,))
        assert late_row["submit_state"] == "sent"
        assert late_row["submit_attempts"] == 0
        assert db.query_one("SELECT submit_state FROM guest WHERE id = ?", (refused,))["submit_state"] == "error"

        capsys.readouterr()
        assert script.main(["--apply"]) == 0
        assert "marked filed: 0" in capsys.readouterr().out
    finally:
        for apartment_id in (apartment["id"], apartment2["id"]):
            db.execute("DELETE FROM submission WHERE apartment_id = ?", (apartment_id,))
