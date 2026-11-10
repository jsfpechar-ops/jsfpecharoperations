"""Brief 1078 (F3): one update mail when the stay-fee total changes after the bill."""
from __future__ import annotations

import json
import pathlib
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import claim, config, db, fee_update, i18n, mail, mail_notify, reporting
from app.main import app
from app.routes import guest
from tests.conftest import complete_guest_claim
from tests.test_claim_mail import TOKEN, _cleanup, _seed

FEE_COLUMNS = ("fee_mailed_total", "fee_mailed_at", "fee_pending_total", "fee_pending_since")
NEW_KEYS = (
    "mail_fee_update_subject",
    "mail_fee_update_heading",
    "mail_fee_update_body",
    "mail_fee_update_more",
    "mail_fee_update_less",
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
    reservation_before = dict(stay.reservation())
    guests_before = [
        dict(row)
        for row in db.query("SELECT * FROM guest WHERE reservation_id = ? ORDER BY id", (stay.id,))
    ]
    baseline_at = stay.fee_columns()[1]

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
    db.update("apartment", stay.apartment_id, {"stay_fee_guest_rails": "cash"})
    stay.complete()
    stay.total = 250
    fee_update.sweep_fee_updates(now=_at(1))
    assert fee_update.sweep_fee_updates(now=_at(12))["queued"] == 1
    (row,) = stay.updates()
    text = stay.text(row)
    assert "is now 250 CZK. It was 400 CZK." in text
    assert "ask your host about the difference" in text
    assert "remaining difference" not in text
    # No iban rail, so no variable symbol line.
    assert "variable symbol" not in text


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
        values = dict(property="P", total="T", dates="D", old="O", new="N", diff="X")
        assert "%(" not in local(key, **values)
        if lang != "en":
            assert local(key, **values) != english(key, **values), key
    for old_total, new_total, vs in ((400, 550, "77"), (400, 250, ""), (400, 550, "")):
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
        vs_line = local("mail_completion_fee_vs", vs="77")
        assert (vs_line in content["text"]) == bool(vs)
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
