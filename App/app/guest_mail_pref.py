"""Whether the host's confirmation mail carries full guest details (brief 1120).

The switch is ``user_account.guest_details_mail`` of the workspace owner, on by
default. Full details leave only after the owner accepted DPA 1.8 or later, the version that
describes them, so ``full_details`` also reads ``acceptance.accepted``. Other
modules call this function and never read the column.
"""
from __future__ import annotations

from . import acceptance, db

# The first DPA version that describes guest details by e-mail (brief 1123b).
MIN_DPA_VERSION = "1.8"


def _version_tuple(version: str):
    """"1.8" -> (1, 8); None when the text is not dot-separated integers."""
    try:
        return tuple(int(part) for part in str(version).strip().split("."))
    except ValueError:
        return None


def switch_on(owner_user_id: int) -> bool:
    """The stored switch alone, for the settings page."""
    row = db.query_one(
        "SELECT guest_details_mail FROM user_account WHERE id = ?", (owner_user_id,)
    )
    return bool(row) and bool(row["guest_details_mail"])


def dpa_accepted(owner_user_id: int) -> bool:
    """True when the owner has a dpa acceptance row at MIN_DPA_VERSION or above."""
    minimum = _version_tuple(MIN_DPA_VERSION)
    for row in acceptance.accepted(owner_user_id):
        if row["document"] != "dpa":
            continue
        found = _version_tuple(row["version"])
        if found is not None and found >= minimum:
            return True
    return False


def full_details(owner_user_id: int) -> bool:
    """True when the workspace switch is on AND the owner accepted DPA MIN_DPA_VERSION or later."""
    return switch_on(owner_user_id) and dpa_accepted(owner_user_id)


def set_full_details(owner_user_id: int, enabled: bool, *, actor: str) -> None:
    """Store the switch and audit the change (ids only, no guest data)."""
    db.execute(
        "UPDATE user_account SET guest_details_mail = ? WHERE id = ?",
        (1 if enabled else 0, owner_user_id),
    )
    db.audit(
        "guest_details_mail_on" if enabled else "guest_details_mail_off",
        f"user_id={owner_user_id} by={actor}",
        owner_user_id=owner_user_id,
    )
