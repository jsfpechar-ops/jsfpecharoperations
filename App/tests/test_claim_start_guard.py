"""Brief 1115: start_claim writes only over the claim row it read.

``start_claim`` reads the claim row, decides, then writes. These tests run a
second writer between that read and the write, by patching ``claim.ensure_row``
(the read ``start_claim`` uses) so the other writer commits right after it.
No threads, no sleeps: the order is fixed.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app import claim, db
from tests.test_claim_mail import TOKEN, _cleanup, _seed


def _age_hold_past_takeover(reservation_id: int) -> None:
    """Keep the hold active but older than the takeover window."""
    started = datetime.now(timezone.utc) - timedelta(
        seconds=claim.HOLD_TAKEOVER_SECONDS + 5
    )
    until = (started + timedelta(minutes=claim.HOLD_MINUTES)).replace(
        microsecond=0
    ).isoformat()
    db.execute(
        "UPDATE reservation_claim SET provisional_until = ? WHERE reservation_id = ?",
        (until, reservation_id),
    )


def _fixtures(current):
    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (current,))
    apartment = db.query_one("SELECT * FROM apartment WHERE permalink_token = ?", (TOKEN,))
    return reservation, apartment


def _clear_mail():
    db.execute("DELETE FROM email_outbox")
    db.execute("DELETE FROM console_mail_log")
    db.execute("DELETE FROM rate_limit_event")


def test_confirm_between_read_and_write_keeps_the_claim(monkeypatch):
    """A confirm that commits after start_claim's read must win.

    Before 1115 the takeover write had no state condition, so it put the
    claimed row back to provisional and replaced the confirmed address.
    """
    current, _past, _far, _apartment_id = _seed()
    try:
        reservation, apartment = _fixtures(current)
        ok, err, first_secret = claim.start_claim(
            reservation, apartment, email="first@claim.test", party_size=2, lang="en"
        )
        assert ok, err
        _age_hold_past_takeover(current)

        real_ensure_row = claim.ensure_row
        reads = []

        def read_then_confirm(reservation_id):
            row = real_ensure_row(reservation_id)
            reads.append(reservation_id)
            if len(reads) == 1:
                assert claim.confirm(reservation, first_secret)
            return row

        monkeypatch.setattr(claim, "ensure_row", read_then_confirm)
        result = claim.start_claim(
            reservation, apartment, email="second@claim.test", party_size=2, lang="en"
        )
        monkeypatch.undo()

        row = claim.ensure_row(current)
        assert row["state"] == "claimed"
        assert row["email"] == "first@claim.test"
        assert row["token_hash"] is None
        assert result == (False, "already_claimed", None)
    finally:
        _clear_mail()
        _cleanup()


def test_takeover_between_read_and_write_is_not_overwritten(monkeypatch):
    """Two takeovers on one hold: the one that wrote first keeps the hold.

    Both read the same row and the same token_version; without the
    token_version condition the second write replaced the first one's address
    and secret under the same version number.
    """
    current, _past, _far, _apartment_id = _seed()
    try:
        reservation, apartment = _fixtures(current)
        ok, err, _secret = claim.start_claim(
            reservation, apartment, email="first@claim.test", party_size=2, lang="en"
        )
        assert ok, err
        _age_hold_past_takeover(current)

        real_ensure_row = claim.ensure_row
        reads = []
        other = {}

        def read_then_other_takeover(reservation_id):
            row = real_ensure_row(reservation_id)
            reads.append(reservation_id)
            if len(reads) == 1:
                other["result"] = claim.start_claim(
                    reservation, apartment, email="third@claim.test", party_size=2, lang="en"
                )
            return row

        monkeypatch.setattr(claim, "ensure_row", read_then_other_takeover)
        result = claim.start_claim(
            reservation, apartment, email="second@claim.test", party_size=2, lang="en"
        )
        monkeypatch.undo()

        assert other["result"][0] is True, other["result"]
        third_secret = other["result"][2]
        row = claim.ensure_row(current)
        assert row["state"] == "provisional"
        assert row["email"] == "third@claim.test"
        assert row["token_hash"] == claim.token_hash(third_secret)
        assert result == (False, "held", None)
    finally:
        _clear_mail()
        _cleanup()
