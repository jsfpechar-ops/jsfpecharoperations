"""1095: the lead guest's reduction of the head count, one rule in Python and Go.

The reduction is stored apart from the host's number and from the declared
count. A stay without one must behave, and file, exactly as before; the
feature flag ``UBYHOST_HEADCOUNT_LEAD_LIVE`` is off by default.
"""
from __future__ import annotations

import csv
import io
import json
import re
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import claim, config, db, door_codes, headcount, mail, reporting, stays_export
from app.main import app
from app.routes import guest
from tests import test_guest_navigation as nav
from tests import test_party_count_1092 as p92
from tests.test_stay_missing_guest_rows import TOKEN as HOST_TOKEN
from tests.test_stay_missing_guest_rows import stay as host_stay  # noqa: F401 - pytest fixture

ROOT = Path(__file__).resolve().parents[2]
CASES = json.loads((ROOT / "go/internal/headcount/testdata/cases.json").read_text())
REDUCTION = ("lead_reduced_guests", "lead_reduced_from", "lead_reduced_at")
OLD_STAMP = "2026-01-01T00:00:00+00:00"


@pytest.fixture
def stay():
    token, stay_id, _right = nav._make_apartment_with_stays()
    db.execute("DELETE FROM rate_limit_event")
    db.execute(
        "DELETE FROM audit WHERE action LIKE 'reservation_declared_guests%' "
        "OR action LIKE 'reservation_headcount_%'"
    )
    try:
        yield token, stay_id
    finally:
        nav._cleanup()


def _clock(monkeypatch, stay_id, minutes):
    """Set the cut-off clock to ``minutes`` after (negative: before) the stay's cut-off."""
    row = db.query_one(
        "SELECT r.date_from, a.checkin_hour FROM reservation r "
        "JOIN apartment a ON a.id = r.apartment_id WHERE r.id = ?",
        (stay_id,),
    )
    moment = headcount.lead_cutoff(row["date_from"], row["checkin_hour"]) + timedelta(minutes=minutes)
    monkeypatch.setattr(headcount, "_utcnow", lambda: moment)


@pytest.fixture
def live(stay, monkeypatch):
    """Flag on, one hour before the cut-off."""
    monkeypatch.setattr(config, "HEADCOUNT_LEAD_LIVE", True)
    _clock(monkeypatch, stay[1], -60)


def _lead(browser, token, stay_id, count, shown):
    db.execute("DELETE FROM rate_limit_event")
    return browser.post(
        f"/l/{token}/{stay_id}/count",
        data={"count": str(count), "shown": str(shown)},
        follow_redirects=False,
    )


def _code(response):
    assert response.status_code == 303, response.text
    found = re.search(r"[?&]count=([a-z_]+)$", response.headers["location"])
    assert found, response.headers["location"]
    return found.group(1)


def _host_four(token, stay_id, rows=2):
    """Host count 4, ``rows`` complete people, the lead's phone."""
    browser = p92._browser(token, stay_id, party_size=4)
    for person in range(rows):
        assert p92._save(browser, token, stay_id, person).status_code == 303
    db.update("reservation", stay_id, {"expected_guests_override": 4})
    return browser


def _declared_four(token, stay_id, rows=2):
    """The guest declared 4 (no host count), ``rows`` complete people."""
    browser = p92._browser(token, stay_id, party_size=4)
    for person in range(rows):
        assert p92._save(browser, token, stay_id, person).status_code == 303
    assert p92._count(stay_id) == 4
    return browser


def _reduce(stay_id, to, base, changes=1):
    db.update(
        "reservation",
        stay_id,
        {
            "lead_reduced_guests": to,
            "lead_reduced_from": base,
            "lead_reduced_at": db.utcnow(),
            "lead_reduced_changes": changes,
        },
    )


def _row(stay_id):
    return p92._reservation(stay_id)


def _expected(stay_id):
    return reporting.expected_guest_count(_row(stay_id))


def _no_reduction(stay_id):
    row = _row(stay_id)
    return all(row[key] is None for key in REDUCTION)


def _lead_audit(stay_id, suffix):
    return db.query(
        "SELECT * FROM audit WHERE action = ? AND detail LIKE ?",
        (f"reservation_headcount_{suffix}", f"id={stay_id} %"),
    )


def _spy_completion(monkeypatch):
    """Record the three completion calls and the block depth they ran at."""
    calls = []

    def _depth():
        return getattr(db._local, "depth", 0)

    monkeypatch.setattr(
        reporting, "submit_stay_if_complete", lambda *a: calls.append(("submit", _depth()))
    )
    monkeypatch.setattr(
        door_codes, "on_registration_complete", lambda *a: calls.append(("door", _depth()))
    )
    monkeypatch.setattr(
        claim, "maybe_notify_completion", lambda *a, **k: calls.append(("bill", _depth()))
    )
    return calls


# --- the rule ------------------------------------------------------------------


@pytest.mark.parametrize("case", CASES, ids=[case["name"] for case in CASES])
def test_the_shared_table_gives_the_python_rule(case):
    row = {
        "expected_guests_override": case["override"],
        "declared_guests": case["declared"],
        "lead_reduced_guests": case["reduced"],
    }
    assert reporting.expected_guest_count(row) == case["want"]
    # A row from an old SELECT (no such column) is today's rule.
    del row["lead_reduced_guests"]
    assert reporting.expected_guest_count(row) == (case["override"] or case["declared"])


def test_the_shared_table_has_the_twelve_named_rows():
    assert len(CASES) >= 12


def test_every_copy_of_the_rule_agrees_with_the_table(stay):
    _token, stay_id = stay
    for case in CASES:
        db.update(
            "reservation",
            stay_id,
            {
                "expected_guests_override": case["override"],
                "declared_guests": case["declared"],
                "lead_reduced_guests": case["reduced"],
            },
        )
        row = _row(stay_id)
        want = case["want"]
        assert reporting.reservation_progress(row)["expected"] == want, case["name"]
        assert claim._declared_count(row, {"declared_guests": None}) == (want or 1), case["name"]
        export = db.query(
            "SELECT r.*, a.internal_name AS apartment_name FROM reservation r "
            "JOIN apartment a ON a.id = r.apartment_id WHERE r.id = ?",
            (stay_id,),
        )
        text = b"".join(stays_export.iter_export_csv_rows(export)).decode("utf-8-sig")
        line = list(csv.reader(io.StringIO(text), delimiter=";"))[1]
        assert line[3] == (str(want) if want else ""), case["name"]


def test_no_other_copy_of_the_rule_is_left():
    allowed = {"reporting.py", "headcount.py", "db.py", "demo.py", "routes/admin.py"}
    base = ROOT / "App/app"
    hits = set()
    for path in list(base.rglob("*.py")) + list((base / "templates").rglob("*.html")):
        name = path.relative_to(base).as_posix()
        if name.startswith("templates/guest/archive/"):
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if "expected_guests_override" in line and "declared_guests" in line:
                hits.add(name)
    assert hits <= allowed, sorted(hits - allowed)


def test_the_count_route_is_the_only_new_guest_post():
    source = (ROOT / "App/app/routes/guest.py").read_text(encoding="utf-8")
    assert source.count("@router.post") == 10
    assert source.count('@router.post("/l/{token}/{reservation_id}/count")') == 1


# --- flag off: today's behaviour ---------------------------------------------


def test_with_the_flag_off_nothing_new_happens(stay, monkeypatch):
    token, stay_id = stay
    assert config.HEADCOUNT_LEAD_LIVE is False
    cutoffs = []
    monkeypatch.setattr(headcount, "lead_cutoff", lambda *a: cutoffs.append(a))
    browser = _host_four(token, stay_id, rows=1)
    before = dict(_row(stay_id))

    assert headcount.change_by_lead(stay_id, 2, 4, owner_user_id=None) == "feature_off"
    assert _lead(browser, token, stay_id, 2, 4).status_code == 404
    assert dict(_row(stay_id)) == before
    assert not _lead_audit(stay_id, "lowered")

    # The stay arrives today, so the no-hour cut-off has passed: still saved.
    db.update("reservation", stay_id, {"expected_guests_override": None})
    response = p92._party(browser, token, stay_id, 2)
    assert "party_error" not in response.headers["location"]
    assert p92._count(stay_id) == 2
    assert not cutoffs


def test_with_the_flag_off_remove_empty_slot_makes_one_submit_call(host_stay, monkeypatch):  # noqa: F811
    client, reservation = host_stay
    calls = _spy_completion(monkeypatch)
    url = f"/reservations/{reservation['id']}/remove-empty-slot"
    assert client.post(url, data={"expected": "3"}, follow_redirects=False).status_code == 303
    assert _row(reservation["id"])["expected_guests_override"] == 2
    assert [name for name, _depth in calls] == ["submit"]


# --- no reduction means no change ---------------------------------------------


@pytest.mark.parametrize("flag", [False, True])
def test_without_a_reduction_the_party_write_has_todays_two_keys(stay, monkeypatch, flag):
    token, stay_id = stay
    browser = _declared_four(token, stay_id, rows=1)
    monkeypatch.setattr(config, "HEADCOUNT_LEAD_LIVE", flag)
    _clock(monkeypatch, stay_id, -60)
    payloads = []
    real = db.update_in

    def _spy(cur, table, row_id, payload, *args, **kwargs):
        if table == "reservation":
            payloads.append(set(payload))
        return real(cur, table, row_id, payload, *args, **kwargs)

    monkeypatch.setattr(db, "update_in", _spy)
    response = p92._party(browser, token, stay_id, 3)
    assert "party_error" not in response.headers["location"]
    assert payloads == [{"declared_guests", "updated_at"}]
    assert _no_reduction(stay_id)


def test_without_a_reduction_the_flag_changes_no_filing_fact(stay, monkeypatch):
    token, stay_id = stay
    browser = p92._browser(token, stay_id, party_size=2)
    assert p92._save(browser, token, stay_id, 0).status_code == 303
    assert p92._save(browser, token, stay_id, 1).status_code == 303
    stamp = _row(stay_id)["registration_completed_at"]
    assert stamp, "two of two complete people stamp the stay"

    def _facts():
        row = _row(stay_id)
        progress = reporting.reservation_progress(row)
        return (
            reporting.expected_guest_count(row),
            progress["expected"],
            progress["filled"],
            progress["status"],
            sorted(g["id"] for g in progress["guests"]),
            reporting.refresh_registration_completed_at(stay_id),
            [dict(g) for g in db.query("SELECT * FROM guest WHERE reservation_id = ? ORDER BY id", (stay_id,))],
        )

    off = _facts()
    monkeypatch.setattr(config, "HEADCOUNT_LEAD_LIVE", True)
    reporting.submit_stay_if_complete(p92._apartment(token)["id"], stay_id)
    on = _facts()
    assert on == off
    assert on[5] == stamp


def test_a_row_written_without_the_new_columns_reads_empty(stay):
    _token, stay_id = stay
    row = _row(stay_id)
    assert [row[key] for key in REDUCTION] == [None, None, None]
    assert row["lead_reduced_changes"] == 0


# --- lower and restore ----------------------------------------------------------


def test_the_lead_lowers_and_restores_and_the_host_count_never_moves(stay, live):
    token, stay_id = stay
    browser = _host_four(token, stay_id)
    guests = [dict(g) for g in db.query("SELECT * FROM guest WHERE reservation_id = ?", (stay_id,))]

    assert _code(_lead(browser, token, stay_id, 5, 4)) == "above_ceiling"
    assert _code(_lead(browser, token, stay_id, 1, 4)) == "below_floor"
    assert _code(_lead(browser, token, stay_id, 2, 3)) == "stale"
    assert _no_reduction(stay_id) and _row(stay_id)["lead_reduced_changes"] == 0
    assert not _lead_audit(stay_id, "lowered")

    assert _code(_lead(browser, token, stay_id, 2, 4)) == "lowered"
    row = _row(stay_id)
    assert (row["expected_guests_override"], row["declared_guests"]) == (4, 4)
    assert (row["lead_reduced_guests"], row["lead_reduced_from"]) == (2, 4)
    assert row["lead_reduced_at"] and row["lead_reduced_changes"] == 1
    assert _expected(stay_id) == 2
    lowered = _lead_audit(stay_id, "lowered")
    assert len(lowered) == 1 and lowered[0]["actor"] == "guest"
    assert lowered[0]["detail"] == f"id={stay_id} from=4 to=2 source=lead"

    assert _code(_lead(browser, token, stay_id, 4, 2)) == "restored"
    assert _no_reduction(stay_id) and _expected(stay_id) == 4
    assert _row(stay_id)["expected_guests_override"] == 4
    restored = _lead_audit(stay_id, "restored")
    assert len(restored) == 1
    assert restored[0]["detail"] == f"id={stay_id} from=2 to=4 source=lead"
    # A count change writes no guest row and changes none.
    assert guests == [dict(g) for g in db.query("SELECT * FROM guest WHERE reservation_id = ?", (stay_id,))]


def test_a_double_confirm_is_one_change(stay, live, monkeypatch):
    token, stay_id = stay
    browser = _host_four(token, stay_id)
    calls = _spy_completion(monkeypatch)
    assert _code(_lead(browser, token, stay_id, 2, 4)) == "lowered"
    assert _code(_lead(browser, token, stay_id, 2, 4)) == "unchanged"
    assert len(_lead_audit(stay_id, "lowered")) == 1
    assert calls == [("submit", 0), ("door", 0), ("bill", 0)]
    assert _row(stay_id)["lead_reduced_changes"] == 1


def test_the_cap_refuses_lowering_only(stay, live):
    token, stay_id = stay
    browser = _host_four(token, stay_id)
    steps = [(2, 4, "lowered"), (4, 2, "restored"), (2, 4, "lowered"), (4, 2, "restored"),
             (2, 4, "lowered"), (3, 2, "restored")]
    for count, shown, want in steps:
        assert _code(_lead(browser, token, stay_id, count, shown)) == want
    assert _row(stay_id)["lead_reduced_changes"] == headcount.MAX_LEAD_CHANGES
    before = dict(_row(stay_id))
    assert _code(_lead(browser, token, stay_id, 2, 3)) == "too_many"
    assert dict(_row(stay_id)) == before
    # The undo always works, and a real person can then be registered.
    assert _code(_lead(browser, token, stay_id, 4, 3)) == "restored"
    assert _no_reduction(stay_id)
    assert p92._save(browser, token, stay_id, 2).status_code == 303
    assert p92._live(stay_id) == 3


def test_a_person_is_never_locked_out(stay, live, monkeypatch):
    token, stay_id = stay
    browser = _host_four(token, stay_id)
    _reduce(stay_id, 2, 4, changes=headcount.MAX_LEAD_CHANGES)
    refused = p92._save(browser, token, stay_id, 2)
    assert refused.status_code == 303
    assert refused.headers["location"].split("?")[0].endswith(f"/{stay_id}")
    assert p92._live(stay_id) == 2

    _clock(monkeypatch, stay_id, 24 * 60)  # after the cut-off and at the cap
    assert _code(_lead(browser, token, stay_id, 3, 2)) == "restored"
    assert p92._save(browser, token, stay_id, 2).status_code == 303
    assert p92._live(stay_id) == 3


# --- cut-off --------------------------------------------------------------------


@pytest.mark.parametrize("hour", [14, None])
def test_the_cut_off_refuses_lowering_only(stay, live, monkeypatch, hour):
    token, stay_id = stay
    browser = _host_four(token, stay_id)
    apartment = p92._apartment(token)
    db.update("apartment", apartment["id"], {"checkin_hour": hour})
    cutoff = headcount.lead_cutoff(_row(stay_id)["date_from"], hour)
    assert cutoff.hour == (14 if hour else headcount.NO_HOUR_CUTOFF_HOUR)
    assert cutoff.minute == 0 and cutoff.date().isoformat() == _row(stay_id)["date_from"][:10]
    assert str(cutoff.tzinfo) == "Europe/Prague"

    _clock(monkeypatch, stay_id, -1)
    assert _code(_lead(browser, token, stay_id, 3, 4)) == "lowered"
    _clock(monkeypatch, stay_id, 1)
    assert _code(_lead(browser, token, stay_id, 2, 3)) == "after_cutoff"
    assert _expected(stay_id) == 3
    assert _code(_lead(browser, token, stay_id, 4, 3)) == "restored"


def test_a_cut_off_that_cannot_be_worked_out_refuses_lowering(stay, live, monkeypatch):
    token, stay_id = stay
    assert headcount.lead_cutoff("bad", 14) is None
    assert headcount.lead_cutoff("2026-11-10", "noon") is None
    browser = _host_four(token, stay_id)
    _reduce(stay_id, 3, 4)
    monkeypatch.setattr(headcount, "lead_cutoff", lambda *a: None)
    assert _code(_lead(browser, token, stay_id, 2, 3)) == "after_cutoff"
    assert _code(_lead(browser, token, stay_id, 4, 3)) == "restored"


def test_the_cut_off_also_stops_a_party_lowering_but_no_raise_and_no_first_count(stay, live, monkeypatch):
    token, stay_id = stay
    browser = _declared_four(token, stay_id)
    _clock(monkeypatch, stay_id, 1)
    response = p92._party(browser, token, stay_id, 3)
    assert "party_error=1" in response.headers["location"]
    assert p92._count(stay_id) == 4
    assert not p92._audit(stay_id, "refused")

    response = p92._party(browser, token, stay_id, 5)
    assert "party_error" not in response.headers["location"]
    assert p92._count(stay_id) == 5

    db.update("reservation", stay_id, {"declared_guests": None})
    with db.immediate() as cur:
        code, old = headcount.apply_declared_in(cur, stay_id, 2)
    assert (code, old) == (headcount.SAVED, None)
    assert headcount.AFTER_CUTOFF not in headcount.ACCEPTED


# --- who may change it --------------------------------------------------------


def test_a_member_without_the_claim_is_sent_back_and_changes_nothing(stay, live):
    token, stay_id = stay
    _host_four(token, stay_id)
    member = TestClient(app)
    member.cookies.set(guest.LANG_COOKIE, "en")
    response = _lead(member, token, stay_id, 2, 4)
    assert response.status_code == 303
    assert "count=" not in response.headers["location"]
    assert _no_reduction(stay_id) and _expected(stay_id) == 4


def test_with_mail_off_there_is_no_lead(stay, live, monkeypatch):
    token, stay_id = stay
    browser = _host_four(token, stay_id)
    monkeypatch.setattr(mail, "mail_enabled", lambda: False)
    assert _lead(browser, token, stay_id, 2, 4).status_code == 404
    assert _no_reduction(stay_id)


def test_a_host_on_the_guest_page_is_not_the_lead(host_stay, monkeypatch):  # noqa: F811
    client, reservation = host_stay
    monkeypatch.setattr(config, "HEADCOUNT_LEAD_LIVE", True)
    response = _lead(client, HOST_TOKEN, reservation["id"], 2, 3)
    assert response.status_code == 403, response.headers.get("location")
    assert _no_reduction(reservation["id"])


# --- two phones -----------------------------------------------------------------


def test_a_lowering_and_a_new_person_cannot_both_be_written(stay, live, monkeypatch):
    token, stay_id = stay
    taken = []
    real = db.lock_key

    def _spy(cur, name, key):
        taken.append((name, int(key)))
        return real(cur, name, key)

    phone_a = _host_four(token, stay_id)
    # The second phone of the same claim (claiming again would take it from A).
    phone_b = TestClient(app)
    phone_b.cookies.update(phone_a.cookies)
    monkeypatch.setattr(db, "lock_key", _spy)

    # A first: B's third person meets a full group.
    assert _code(_lead(phone_a, token, stay_id, 2, 4)) == "lowered"
    assert taken == [("reservation", stay_id)]
    late = p92._save(phone_b, token, stay_id, 2)
    assert late.headers["location"].split("?")[0].endswith(f"/{stay_id}")
    assert p92._live(stay_id) == 2 == _expected(stay_id)

    # B first: A's lowering meets the floor.
    assert _code(_lead(phone_a, token, stay_id, 4, 2)) == "restored"
    assert p92._save(phone_b, token, stay_id, 2).status_code == 303
    assert p92._live(stay_id) == 3
    assert _code(_lead(phone_a, token, stay_id, 2, 4)) == "below_floor"
    assert _expected(stay_id) == 4


# --- filing ---------------------------------------------------------------------


def test_a_lowering_that_completes_the_stay_files_once_outside_the_block(stay, live, monkeypatch):
    token, stay_id = stay
    browser = _host_four(token, stay_id)
    db.update("reservation", stay_id, {"expected_guests_override": 3})
    apartment_id = p92._apartment(token)["id"]
    db.update("apartment", apartment_id, {"automation_mode": "immediate"})
    calls = []
    monkeypatch.setattr(
        reporting,
        "submit_stay_if_complete",
        lambda a, r: calls.append((a, r, getattr(db._local, "depth", 0))),
    )
    assert _code(_lead(browser, token, stay_id, 2, 3)) == "lowered"
    assert calls == [(apartment_id, stay_id, 0)]
    progress = reporting.reservation_progress(_row(stay_id))
    assert (progress["filled"], progress["expected"]) == (2, 2)


def test_a_sent_row_and_a_stored_stamp_survive_a_lower_and_a_restore(stay, live):
    token, stay_id = stay
    browser = _host_four(token, stay_id)
    first = db.query("SELECT id FROM guest WHERE reservation_id = ? ORDER BY id", (stay_id,))[0]["id"]
    db.execute(
        "UPDATE guest SET submit_state = ?, manual_filed_at = ? WHERE id = ?",
        (reporting.SENT, OLD_STAMP, first),
    )
    db.update("reservation", stay_id, {"registration_completed_at": OLD_STAMP})

    def _sent():
        return dict(db.query_one("SELECT * FROM guest WHERE id = ?", (first,)))

    def _batches():
        return db.query_one("SELECT COUNT(*) AS n FROM submission")["n"]

    sent, batches = _sent(), _batches()
    assert _code(_lead(browser, token, stay_id, 2, 4)) == "lowered"
    assert _row(stay_id)["registration_completed_at"] == OLD_STAMP
    assert _code(_lead(browser, token, stay_id, 4, 2)) == "restored"
    assert _row(stay_id)["registration_completed_at"] == OLD_STAMP
    assert _sent() == sent
    assert _batches() == batches


def test_the_quiet_path_stamp_stays_and_the_bill_goes_once_after_a_lowering(stay, live, monkeypatch):
    token, stay_id = stay
    browser = _host_four(token, stay_id)
    apartment = p92._apartment(token)
    nav._backdate_forms(stay_id, reporting.HEADCOUNT_QUIET_HOURS + 1)
    stamp = reporting.refresh_registration_completed_at(stay_id)
    assert stamp, "quiet-complete: two settled forms of four"
    claim.maybe_notify_completion(_row(stay_id), apartment)
    held = db.query_one("SELECT * FROM reservation_claim WHERE reservation_id = ?", (stay_id,))
    assert not held["completion_notified_at"], "no bill while the count is above the rows"

    bills = []
    real = claim.maybe_notify_completion

    def _spy(reservation, apartment_row, **kwargs):
        progress = reporting.reservation_progress(reservation)
        if progress["expected"] is not None and progress["filled"] >= progress["expected"]:
            bills.append(reservation["id"])
        return real(reservation, apartment_row, **kwargs)

    monkeypatch.setattr(claim, "maybe_notify_completion", _spy)
    assert _code(_lead(browser, token, stay_id, 2, 4)) == "lowered"
    assert bills == [stay_id]
    assert _row(stay_id)["registration_completed_at"] == stamp
    assert _code(_lead(browser, token, stay_id, 2, 4)) == "unchanged"
    assert bills == [stay_id]


# --- host -----------------------------------------------------------------------


@pytest.mark.parametrize("path", ["", "/quick-edit"])
def test_a_host_edit_clears_the_reduction_and_a_resave_keeps_it(host_stay, path):  # noqa: F811
    client, reservation = host_stay
    stay_id = reservation["id"]
    _reduce(stay_id, 2, 3, changes=3)
    url = f"/reservations/{stay_id}{path}"

    client.post(url, data={"expected_guests_override": "2"}, follow_redirects=False)
    row = _row(stay_id)
    assert (row["expected_guests_override"], row["lead_reduced_guests"], row["lead_reduced_from"]) == (3, 2, 3)

    client.post(url, data={"expected_guests_override": "5"}, follow_redirects=False)
    row = _row(stay_id)
    assert row["expected_guests_override"] == 5
    assert _no_reduction(stay_id) and row["lead_reduced_changes"] == 3


def test_remove_empty_slot_reads_the_reduced_number_and_runs_the_three_calls(host_stay, monkeypatch):  # noqa: F811
    client, reservation = host_stay
    stay_id = reservation["id"]
    monkeypatch.setattr(config, "HEADCOUNT_LEAD_LIVE", True)
    _reduce(stay_id, 2, 3)
    calls = _spy_completion(monkeypatch)
    url = f"/reservations/{stay_id}/remove-empty-slot"

    client.post(url, data={"expected": "3"}, follow_redirects=False)  # the host's own number is stale
    assert _row(stay_id)["lead_reduced_guests"] == 2 and not calls

    assert client.post(url, data={"expected": "2"}, follow_redirects=False).status_code == 303
    assert _row(stay_id)["expected_guests_override"] == 1
    assert _no_reduction(stay_id)
    assert [name for name, _depth in calls] == ["submit", "door", "bill"]


# --- new phone, add another person ------------------------------------------------


@pytest.mark.parametrize("host_set", [True, False])
def test_a_new_phone_sees_and_keeps_the_reduction(stay, live, host_set):
    token, stay_id = stay
    (_host_four if host_set else _declared_four)(token, stay_id)
    _reduce(stay_id, 2, 4)
    claim.release(stay_id)
    before = _row(stay_id)

    newcomer = TestClient(app)
    newcomer.cookies.set(guest.LANG_COOKIE, "en")
    page = newcomer.get(f"/l/{token}/{stay_id}?lang=en", follow_redirects=True)
    assert page.status_code == 200
    field = re.search(r'<input[^>]*name="party_size"[^>]*>', page.text, re.S)
    assert field and re.search(r'value="2"', field.group(0)), field and field.group(0)

    secret = p92._start(token, stay_id, 2, email="second@example.test")
    confirmed = newcomer.post(
        f"/l/{token}/{stay_id}/claim/confirm", data={"secret": secret}, follow_redirects=False
    )
    assert confirmed.status_code == 303
    after = _row(stay_id)
    for key in ("expected_guests_override", "declared_guests", "lead_reduced_guests", "lead_reduced_from"):
        assert after[key] == before[key], key
    assert _expected(stay_id) == 2


def test_add_another_person_raises_a_declared_count_and_leaves_a_host_count(stay, live):
    token, stay_id = stay
    browser = _declared_four(token, stay_id)
    _reduce(stay_id, 2, 4)
    db.execute("DELETE FROM rate_limit_event")
    assert browser.post(f"/l/{token}/{stay_id}/another", follow_redirects=False).status_code == 303
    assert _expected(stay_id) == 3 == p92._count(stay_id)
    assert _no_reduction(stay_id)

    db.update("reservation", stay_id, {"expected_guests_override": 4})
    _reduce(stay_id, 2, 4)
    db.execute("DELETE FROM rate_limit_event")
    assert browser.post(f"/l/{token}/{stay_id}/another", follow_redirects=False).status_code == 303
    row = _row(stay_id)
    assert (row["expected_guests_override"], row["lead_reduced_guests"]) == (4, 2)
    assert _expected(stay_id) == 2


# --- 1092 pins: the floors never read the flag --------------------------------


@pytest.mark.parametrize("flag", [False, True])
def test_the_1092_floors_hold_with_the_flag_off_and_on(stay, monkeypatch, flag):
    token, stay_id = stay
    monkeypatch.setattr(config, "HEADCOUNT_LEAD_LIVE", flag)
    _clock(monkeypatch, stay_id, -60)
    browser = p92._three_rows(token, stay_id)
    db.update("reservation", stay_id, {"declared_guests": 4})
    response = p92._party(browser, token, stay_id, 2)
    assert "party_error=1" in response.headers["location"]
    assert p92._count(stay_id) == 4
    assert len(p92._audit(stay_id, "refused")) == 1

    before = dict(_row(stay_id))
    apartment = p92._apartment(token)
    claim.start_claim(
        _row(stay_id), apartment, email="other@example.test", party_size=1, lang="en", resend=False
    )
    assert dict(_row(stay_id)) == before
