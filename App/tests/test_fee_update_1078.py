"""Brief 1078 (F3): one update mail when the stay-fee total changes after the bill."""
from __future__ import annotations

import json
import pathlib
from datetime import datetime, timedelta, timezone

import threading

import pytest
from fastapi.testclient import TestClient

# Import first: test_db_postgres copies UBYHOST_TEST_DATABASE_URL into the
# application setting, which app.config reads once at import time.
from test_db_postgres import _PG_URL
from app import claim, config, db, fee_update, i18n, mail, mail_notify, reporting
from app.main import app
from app.routes import guest
from tests.conftest import complete_guest_claim
from tests.test_claim_mail import TOKEN, _age_claim, _cleanup, _seed

if _PG_URL:
    from test_db_postgres import pg_runtime  # noqa: F401

FEE_COLUMNS = ("fee_mailed_total", "fee_mailed_at", "fee_pending_total", "fee_pending_since")
NEW_KEYS = (
    "mail_fee_update_subject",
    "mail_fee_update_heading",
    "mail_fee_update_body",
    "mail_fee_update_more",
    "mail_fee_update_less",
    "mail_fee_update_vs",
)
T0 = datetime.now(timezone.utc).replace(microsecond=0)


def _at(minutes: int) -> datetime:
    return T0 + timedelta(minutes=minutes)


class Stay:
    """One claimed stay whose live fee total the test sets directly."""

    def __init__(self, monkeypatch, reservation_id: int, apartment_id: int):
        self.monkeypatch = monkeypatch
        self.id = reservation_id
        self.apartment_id = apartment_id
        self.total = 400

    def reservation(self):
        return db.query_one("SELECT * FROM reservation WHERE id = ?", (self.id,))

    def apartment(self):
        return db.query_one("SELECT * FROM apartment WHERE id = ?", (self.apartment_id,))

    def complete(self):
        claim.maybe_notify_completion(self.reservation(), self.apartment())

    def fee_columns(self):
        row = db.query_one(
            "SELECT fee_mailed_total, fee_mailed_at, fee_pending_total, fee_pending_since "
            "FROM reservation_claim WHERE reservation_id = ?",
            (self.id,),
        )
        return tuple(row[name] for name in FEE_COLUMNS) if row else None

    def outbox(self, kind=None):
        rows = db.query(
            "SELECT * FROM email_outbox WHERE reservation_id = ? ORDER BY id", (self.id,)
        )
        return [row for row in rows if kind is None or row["kind"] == kind]

    def updates(self):
        return self.outbox("completion_update")

    def text(self, row) -> str:
        return json.loads(row["payload"])["text"]


@pytest.fixture
def stay(monkeypatch):
    current, _past, _far, apartment_id = _seed()
    db.execute("DELETE FROM email_outbox WHERE reservation_id = ?", (current,))
    db.update(
        "apartment", apartment_id, {"stay_fee_collect": 1, "stay_fee_guest_rails": "qr,cash"}
    )
    # Since #868 the bank way needs an account on the legal entity.
    entity_id = db.query_one("SELECT legal_entity_id FROM apartment WHERE id = ?", (apartment_id,))[
        "legal_entity_id"
    ]
    old_iban = db.query_one("SELECT iban FROM legal_entity WHERE id = ?", (entity_id,))["iban"]
    db.update("legal_entity", entity_id, {"iban": "CZ6508000000192000145399"})
    monkeypatch.setattr(mail, "backend_name", lambda: "console")
    monkeypatch.setattr(mail, "mail_enabled", lambda: True)
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)
    monkeypatch.setattr(
        claim.reporting,
        "reservation_progress",
        lambda _reservation: {"expected": 1, "filled": 1, "incomplete": []},
    )
    current_stay = Stay(monkeypatch, current, apartment_id)
    # The real ``_completion_fee`` runs (flag, collection, rails); only the
    # charge it reads is set by the test, which stands for a guest being
    # added, removed or edited.
    monkeypatch.setattr(
        claim.stay_fee,
        "charge_for_reservation",
        lambda _apartment, _reservation: {
            "total_czk": current_stay.total,
            "rate_czk": 50,
            "lines": [{"liable_nights": 3, "amount_czk": current_stay.total}],
        },
    )
    browser = TestClient(app)
    browser.cookies.set(guest.LANG_COOKIE, "en")
    complete_guest_claim(browser, TOKEN, current, email="lead@claim.test", party_size=1)
    db.execute("DELETE FROM email_outbox WHERE reservation_id = ?", (current,))
    try:
        yield current_stay
    finally:
        db.execute("DELETE FROM email_outbox WHERE reservation_id = ?", (current,))
        db.execute("DELETE FROM reservation_claim WHERE reservation_id = ?", (current,))
        db.execute("DELETE FROM alert WHERE reservation_id = ?", (current,))
        db.update("legal_entity", entity_id, {"iban": old_iban})
        _cleanup()


# a ---------------------------------------------------------------------------


def test_completion_with_a_fee_records_the_mailed_total(stay):
    stay.complete()
    total, mailed_at, pending_total, pending_since = stay.fee_columns()
    assert total == 400 and mailed_at
    assert pending_total is None and pending_since is None
    (row,) = stay.outbox()
    assert row["kind"] == "completion"
    assert "400 CZK" in stay.text(row)


@pytest.mark.parametrize("off", ["flag", "collection"])
def test_without_a_fee_the_completion_path_is_as_on_main(stay, monkeypatch, off):
    if off == "flag":
        monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", False)
    else:
        db.update("apartment", stay.apartment_id, {"stay_fee_collect": 0})
    stay.complete()
    assert stay.fee_columns() == (None, None, None, None)
    (row,) = stay.outbox()
    assert row["kind"] == "completion"
    assert row["idempotency_key"] == f"completion:{stay.id}:1"
    assert row["subject"] == i18n.translator("en")(
        "mail_completion_subject", property="Claim flat"
    )
    # Even with the fee back on and changed, a stay without a baseline never mails.
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)
    db.update("apartment", stay.apartment_id, {"stay_fee_collect": 1})
    stay.total = 550
    assert fee_update.sweep_fee_updates(now=_at(1)) == {"queued": 0, "pending": 0}
    assert fee_update.sweep_fee_updates(now=_at(30)) == {"queued": 0, "pending": 0}
    assert len(stay.outbox()) == 1
    assert stay.fee_columns() == (None, None, None, None)


# b, i ------------------------------------------------------------------------


def test_a_changed_total_mails_once_after_ten_quiet_minutes(stay, monkeypatch):
    def boom(*_args, **_kwargs):
        raise AssertionError("the fee sweep must never reach the filing")

    monkeypatch.setattr(reporting, "submit_stay_if_complete", boom)
    stay.complete()
    now = db.utcnow()
    db.insert(
        "guest",
        {
            "reservation_id": stay.id,
            "surname": "Guest",
            "first_name": "Lead",
            "birth_date": "01011990",
            "nationality": "DEU",
            "doc_number": "C1234567",
            "res_street": "Street 1",
            "res_city": "Berlin",
            "res_country": "DEU",
            "purpose": "10",
            "is_lead": 1,
            "entered_by": "guest",
            "submit_state": reporting.PENDING,
            "created_at": now,
            "updated_at": now,
        },
    )
    reservation_before = dict(stay.reservation())
    guests_before = [
        dict(row)
        for row in db.query("SELECT * FROM guest WHERE reservation_id = ? ORDER BY id", (stay.id,))
    ]
    baseline_at = stay.fee_columns()[1]
    assert len(guests_before) == 1
    assert guests_before[0]["submit_state"] == reporting.PENDING

    stay.total = 550
    assert fee_update.sweep_fee_updates(now=_at(1)) == {"queued": 0, "pending": 1}
    assert stay.updates() == []
    assert stay.fee_columns() == (400, baseline_at, 550, _at(1).isoformat())
    # Still inside the window: nothing yet.
    assert fee_update.sweep_fee_updates(now=_at(5)) == {"queued": 0, "pending": 1}
    assert stay.updates() == []

    assert fee_update.sweep_fee_updates(now=_at(12)) == {"queued": 1, "pending": 0}
    (row,) = stay.updates()
    assert row["idempotency_key"] == f"completion_update:{stay.id}:{baseline_at}:550"
    assert row["to_email"] == "lead@claim.test"
    assert row["cc_email"] == "host@claim.test"
    assert row["subject"] == "Stay fee for Claim flat changed: now 550 CZK"
    text = stay.text(row)
    assert "is now 550 CZK. It was 400 CZK." in text
    assert "the remaining difference is 150 CZK" in text
    assert f"variable symbol {stay.id}." in text
    assert stay.fee_columns() == (550, _at(12).isoformat(), None, None)

    # The scheduler runs it again, twice: no further row.
    assert fee_update.sweep_fee_updates(now=_at(13)) == {"queued": 0, "pending": 0}
    assert fee_update.sweep_fee_updates(now=_at(40)) == {"queued": 0, "pending": 0}
    assert len(stay.updates()) == 1

    # i: the filing is untouched, every reservation column and every guest row.
    assert dict(stay.reservation()) == reservation_before
    assert [
        dict(row)
        for row in db.query("SELECT * FROM guest WHERE reservation_id = ? ORDER BY id", (stay.id,))
    ] == guests_before


def test_fee_update_module_never_names_the_filing():
    source = pathlib.Path(fee_update.__file__).read_text(encoding="utf-8")
    assert "submit" not in source


# c ---------------------------------------------------------------------------


def test_two_changes_inside_the_window_restart_the_wait(stay):
    stay.complete()
    stay.total = 550
    assert fee_update.sweep_fee_updates(now=_at(1))["pending"] == 1
    stay.total = 700
    assert fee_update.sweep_fee_updates(now=_at(8)) == {"queued": 0, "pending": 1}
    # Ten minutes after the first change, but only four after the second.
    assert fee_update.sweep_fee_updates(now=_at(12)) == {"queued": 0, "pending": 1}
    assert stay.updates() == []
    assert fee_update.sweep_fee_updates(now=_at(19)) == {"queued": 1, "pending": 0}
    (row,) = stay.updates()
    text = stay.text(row)
    assert "is now 700 CZK. It was 400 CZK." in text
    assert "550" not in text


# d ---------------------------------------------------------------------------


def test_a_lower_total_gets_the_less_line(stay):
    # The iban rail is on, and still nothing more is owed: no variable symbol.
    stay.complete()
    stay.total = 250
    fee_update.sweep_fee_updates(now=_at(1))
    assert fee_update.sweep_fee_updates(now=_at(12))["queued"] == 1
    (row,) = stay.updates()
    text = stay.text(row)
    assert "is now 250 CZK. It was 400 CZK." in text
    assert "ask your host about the difference" in text
    assert "remaining difference" not in text
    assert "variable symbol" not in text


def test_a_higher_total_without_the_iban_rail_has_no_variable_symbol(stay):
    db.update("apartment", stay.apartment_id, {"stay_fee_guest_rails": "cash"})
    stay.complete()
    stay.total = 550
    fee_update.sweep_fee_updates(now=_at(1))
    assert fee_update.sweep_fee_updates(now=_at(12))["queued"] == 1
    (row,) = stay.updates()
    assert "remaining difference is 150 CZK" in stay.text(row)
    assert "variable symbol" not in stay.text(row)


def test_a_fee_that_becomes_none_sends_nothing_and_keeps_the_baseline(stay):
    stay.complete()
    baseline = stay.fee_columns()
    stay.total = 550
    fee_update.sweep_fee_updates(now=_at(1))
    assert stay.fee_columns()[2] == 550

    db.update("apartment", stay.apartment_id, {"stay_fee_collect": 0})
    assert fee_update.sweep_fee_updates(now=_at(2)) == {"queued": 0, "pending": 0}
    assert fee_update.sweep_fee_updates(now=_at(30)) == {"queued": 0, "pending": 0}
    assert stay.updates() == []
    assert stay.fee_columns() == baseline

    db.update("apartment", stay.apartment_id, {"stay_fee_collect": 1})
    stay.total = 600
    assert fee_update.sweep_fee_updates(now=_at(31))["pending"] == 1
    assert fee_update.sweep_fee_updates(now=_at(42))["queued"] == 1
    (row,) = stay.updates()
    assert "is now 600 CZK. It was 400 CZK." in stay.text(row)


# e ---------------------------------------------------------------------------


def test_a_change_undone_inside_the_window_sends_nothing(stay):
    stay.complete()
    baseline = stay.fee_columns()
    stay.total = 550
    fee_update.sweep_fee_updates(now=_at(1))
    stay.total = 400
    assert fee_update.sweep_fee_updates(now=_at(5)) == {"queued": 0, "pending": 0}
    assert fee_update.sweep_fee_updates(now=_at(30)) == {"queued": 0, "pending": 0}
    assert stay.updates() == []
    assert stay.fee_columns() == baseline


def test_back_and_forth_totals_each_mail_with_their_own_key(stay):
    stay.complete()
    minute = 0
    for total in (550, 400, 550):
        stay.total = total
        minute += 1
        assert fee_update.sweep_fee_updates(now=_at(minute))["pending"] == 1
        minute += 11
        assert fee_update.sweep_fee_updates(now=_at(minute))["queued"] == 1
    rows = stay.updates()
    assert len(rows) == 3
    assert len({row["idempotency_key"] for row in rows}) == 3
    assert [stay.text(row).splitlines()[0].split(") ")[1] for row in rows] == [
        "is now 550 CZK. It was 400 CZK.",
        "is now 400 CZK. It was 550 CZK.",
        "is now 550 CZK. It was 400 CZK.",
    ]


# f ---------------------------------------------------------------------------


def test_a_crash_between_enqueue_and_record_does_not_mail_twice(stay, monkeypatch):
    stay.complete()
    stay.total = 550
    fee_update.sweep_fee_updates(now=_at(1))
    real = fee_update._record_sent
    calls = []

    def crash_once(*args):
        calls.append(args)
        if len(calls) == 1:
            raise RuntimeError("process died after the enqueue")
        return real(*args)

    monkeypatch.setattr(fee_update, "_record_sent", crash_once)
    assert fee_update.sweep_fee_updates(now=_at(12)) == {"queued": 0, "pending": 0}
    assert len(stay.updates()) == 1
    assert stay.fee_columns()[0] == 400

    assert fee_update.sweep_fee_updates(now=_at(13)) == {"queued": 1, "pending": 0}
    assert len(stay.updates()) == 1
    assert stay.fee_columns() == (550, _at(13).isoformat(), None, None)
    assert fee_update.sweep_fee_updates(now=_at(30)) == {"queued": 0, "pending": 0}
    assert len(stay.updates()) == 1


def test_a_second_worker_with_the_old_state_reuses_the_same_row(stay):
    stay.complete()
    stay.total = 550
    fee_update.sweep_fee_updates(now=_at(1))
    before = stay.fee_columns()
    assert fee_update.sweep_fee_updates(now=_at(12))["queued"] == 1
    assert len(stay.updates()) == 1

    # What a worker that read the row before the send still believes.
    db.execute(
        "UPDATE reservation_claim SET fee_mailed_total = ?, fee_mailed_at = ?, "
        "fee_pending_total = ?, fee_pending_since = ? WHERE reservation_id = ?",
        (*before, stay.id),
    )
    fee_update.sweep_fee_updates(now=_at(12))
    assert len(stay.updates()) == 1
    assert stay.fee_columns()[0] == 550


# g ---------------------------------------------------------------------------


def _baseline_null(stay):
    db.execute(
        "UPDATE reservation_claim SET fee_mailed_total = NULL, fee_mailed_at = NULL "
        "WHERE reservation_id = ?",
        (stay.id,),
    )


def _claim_released(stay):
    db.execute(
        "UPDATE reservation_claim SET state = 'unclaimed' WHERE reservation_id = ?", (stay.id,)
    )


def _email_minimised(stay):
    db.execute("UPDATE reservation_claim SET email = NULL WHERE reservation_id = ?", (stay.id,))


def _cancelled(stay):
    db.execute("UPDATE reservation SET status = 'cancelled' WHERE id = ?", (stay.id,))


def _archived(stay):
    db.execute("UPDATE reservation SET archived_at = ? WHERE id = ?", (db.utcnow(), stay.id))


def _departed(stay):
    today = claim.prague_today()
    db.execute(
        "UPDATE reservation SET date_from = ?, date_to = ? WHERE id = ?",
        (
            (today - timedelta(days=4)).isoformat(),
            (today - timedelta(days=1)).isoformat(),
            stay.id,
        ),
    )


@pytest.mark.parametrize(
    "block",
    [_baseline_null, _claim_released, _email_minimised, _cancelled, _archived, _departed],
)
def test_no_mail_and_no_write_when_the_stay_dropped_out(stay, block):
    stay.complete()
    stay.total = 550
    block(stay)
    before = stay.fee_columns()
    assert fee_update.sweep_fee_updates(now=_at(1)) == {"queued": 0, "pending": 0}
    assert fee_update.sweep_fee_updates(now=_at(30)) == {"queued": 0, "pending": 0}
    assert stay.updates() == []
    assert stay.fee_columns() == before


def test_a_deleted_reservation_never_mails(stay):
    stay.complete()
    stay.total = 550
    before = stay.fee_columns()
    db.execute("DELETE FROM reservation WHERE id = ?", (stay.id,))
    assert fee_update.sweep_fee_updates(now=_at(1)) == {"queued": 0, "pending": 0}
    assert fee_update.sweep_fee_updates(now=_at(30)) == {"queued": 0, "pending": 0}
    assert db.query("SELECT id FROM email_outbox WHERE kind = 'completion_update'") == []
    assert stay.fee_columns() in (None, before)


def test_a_claim_revoked_between_the_read_and_the_lock_never_mails(stay, monkeypatch):
    """The re-read under the lock decides, not the candidate list."""
    stay.complete()
    stay.total = 550
    fee_update.sweep_fee_updates(now=_at(1))
    before = stay.fee_columns()
    real = claim._completion_fee

    def revoke_then_fee(apartment, reservation):
        _claim_released(stay)
        return real(apartment, reservation)

    monkeypatch.setattr(claim, "_completion_fee", revoke_then_fee)
    assert fee_update.sweep_fee_updates(now=_at(12)) == {"queued": 0, "pending": 0}
    assert stay.updates() == []
    assert stay.fee_columns() == before


def test_mail_disabled_keeps_the_old_baseline(stay, monkeypatch):
    stay.complete()
    baseline = stay.fee_columns()
    stay.total = 550
    monkeypatch.setattr(mail, "mail_enabled", lambda: False)
    fee_update.sweep_fee_updates(now=_at(1))
    assert fee_update.sweep_fee_updates(now=_at(12))["queued"] == 0
    assert fee_update.sweep_fee_updates(now=_at(30))["queued"] == 0
    assert stay.updates() == []
    assert stay.fee_columns()[:2] == baseline[:2]


# h ---------------------------------------------------------------------------


@pytest.mark.parametrize("lang", i18n.LANGUAGES)
def test_update_mail_copy_in_six_languages(lang):
    host = {"name": "Claim Mail", "email": "host@claim.test", "phone": "+420111222333"}
    english = i18n.translator("en")
    local = i18n.translator(lang)
    for key in NEW_KEYS:
        values = dict(property="P", total="T", dates="D", old="O", new="N", diff="X", vs="V")
        assert "%(" not in local(key, **values)
        if lang != "en":
            assert local(key, **values) != english(key, **values), key
    for old_total, new_total, vs in (
        (400, 550, "77"),
        (400, 250, "77"),
        (400, 250, ""),
        (400, 550, ""),
    ):
        content = mail_notify.build_fee_update(
            lang=lang,
            property_name="Claim flat",
            dates="1.–4. 12. 2026",
            host=host,
            old_total=old_total,
            new_total=new_total,
            vs=vs,
        )
        assert set(content) == {"subject", "text", "html"}
        assert "qr_spayd" not in content
        for part in content.values():
            assert "%(" not in part
        # The branded shell every guest mail shares carries the UbyHost logo;
        # the message itself adds no image and no other remote source.
        assert content["html"].count("<img") == 1
        assert content["html"].count("src=") == 1
        assert "ubyhost-logo" in content["html"]
        assert "data:image" not in content["html"]
        assert "<a href=\"http" not in content["html"]
        amount = local("fee_amount", amount=new_total)
        assert amount in content["subject"] and amount in content["text"]
        assert local("fee_amount", amount=old_total) in content["text"]
        vs_line = local("mail_fee_update_vs", vs="77")
        assert (vs_line in content["text"]) == (bool(vs) and new_total > old_total)
        more = local("mail_fee_update_more", diff=local("fee_amount", amount=150))
        less = local("mail_fee_update_less")
        assert (more in content["text"]) == (new_total > old_total)
        assert (less in content["text"]) == (new_total < old_total)
        if lang == "en":
            # The shared guest footer ("You received this e-mail because ...")
            # is about the message, not the fee; the rule covers the copy above it.
            body = content["text"].split("\n--\n")[0]
            lowered = (content["subject"] + body).lower()
            for word in ("paid", "received", "settled"):
                assert word not in lowered


# Review round 2 --------------------------------------------------------------


def test_a_lost_record_followed_by_a_return_to_the_old_total_is_corrected(stay, monkeypatch):
    """Enqueue A to B, crash before the record, then the total goes back to A.

    The guest holds a mail that says B, so B becomes the baseline and the
    return to A is mailed as a change of its own.
    """
    stay.complete()
    stay.total = 550
    fee_update.sweep_fee_updates(now=_at(1))

    def crash(*_args):
        raise RuntimeError("process died after the enqueue")

    with monkeypatch.context() as patch:
        patch.setattr(fee_update, "_record_sent", crash)
        assert fee_update.sweep_fee_updates(now=_at(12)) == {"queued": 0, "pending": 0}
    assert len(stay.updates()) == 1
    assert stay.fee_columns()[0] == 400

    stay.total = 400
    assert fee_update.sweep_fee_updates(now=_at(13)) == {"queued": 0, "pending": 0}
    assert stay.fee_columns() == (550, _at(13).isoformat(), None, None)
    assert fee_update.sweep_fee_updates(now=_at(14)) == {"queued": 0, "pending": 1}
    assert len(stay.updates()) == 1
    assert fee_update.sweep_fee_updates(now=_at(25)) == {"queued": 1, "pending": 0}
    first, second = stay.updates()
    assert "is now 550 CZK. It was 400 CZK." in stay.text(first)
    assert "is now 400 CZK. It was 550 CZK." in stay.text(second)
    assert stay.fee_columns() == (400, _at(25).isoformat(), None, None)
    assert fee_update.sweep_fee_updates(now=_at(50)) == {"queued": 0, "pending": 0}
    assert len(stay.updates()) == 2


def test_fee_writes_do_not_restart_the_claim_link_resend_cooldown(stay):
    def updated_at():
        return db.query_one(
            "SELECT updated_at FROM reservation_claim WHERE reservation_id = ?", (stay.id,)
        )["updated_at"]

    _age_claim(stay.id, 600)
    aged = updated_at()
    stay.complete()  # completion itself stamps the row, as on main
    _age_claim(stay.id, 600)
    aged = updated_at()
    fee_update.record_baseline(stay.id, 400)
    stay.total = 550
    assert fee_update.sweep_fee_updates(now=_at(1))["pending"] == 1  # pending set
    stay.total = 400
    fee_update.sweep_fee_updates(now=_at(2))  # pending cleared
    stay.total = 550
    fee_update.sweep_fee_updates(now=_at(3))
    assert fee_update.sweep_fee_updates(now=_at(14))["queued"] == 1  # send recorded
    assert updated_at() == aged
    assert not claim._resend_too_soon(claim._row(stay.id))
    ok, err, _secret = claim.start_claim(
        stay.reservation(),
        stay.apartment(),
        email="lead@claim.test",
        party_size=1,
        lang="en",
        resend=True,
    )
    assert ok, err


def test_an_unchanged_total_opens_no_transaction(stay, monkeypatch):
    stay.complete()

    def no_transaction(*_args, **_kwargs):
        raise AssertionError("nothing changed: the sweep must not take the write lock")

    monkeypatch.setattr(fee_update, "_decide", no_transaction)
    assert fee_update.sweep_fee_updates(now=_at(1)) == {"queued": 0, "pending": 0}
    db.update("apartment", stay.apartment_id, {"stay_fee_collect": 0})
    assert fee_update.sweep_fee_updates(now=_at(2)) == {"queued": 0, "pending": 0}


needs_postgres = pytest.mark.skipif(
    not _PG_URL,
    reason=(
        "the two-connection fee sweep test needs UBYHOST_DATABASE_URL (or "
        "UBYHOST_TEST_DATABASE_URL) for a disposable PostgreSQL target; this "
        "pytest process runs the SQLite row"
    ),
)


@needs_postgres
def test_two_workers_on_two_connections_mail_exactly_once(stay, monkeypatch):
    """Both workers find the change due at the same moment; one row leaves."""
    assert config.DB_BACKEND == "postgresql"
    stay.complete()
    stay.total = 550
    assert fee_update.sweep_fee_updates(now=_at(1))["pending"] == 1

    both_due = threading.Barrier(2)
    real_build = mail_notify.build_fee_update
    composed = []
    backends = []

    def build_when_both_are_due(**kwargs):
        # Called after the locked decision and before the enqueue: holding
        # both workers here means neither has recorded its send yet.
        both_due.wait(timeout=20)
        composed.append(kwargs["new_total"])
        return real_build(**kwargs)

    monkeypatch.setattr(mail_notify, "build_fee_update", build_when_both_are_due)
    results = []

    def worker():
        try:
            backends.append(db.query_one("SELECT pg_backend_pid() AS pid")["pid"])
            results.append(fee_update.sweep_fee_updates(now=_at(12)))
        finally:
            db.close_connections()

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert not any(thread.is_alive() for thread in threads)

    assert len(set(backends)) == 2, "the workers must use two connections"
    assert composed == [550, 550], "both workers must have found the change due"
    assert len(results) == 2
    assert len(stay.updates()) == 1
    assert stay.fee_columns() == (550, _at(12).isoformat(), None, None)
    assert fee_update.sweep_fee_updates(now=_at(30)) == {"queued": 0, "pending": 0}
    assert len(stay.updates()) == 1
