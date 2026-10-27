"""Untrusted pricing preferences, never a subscription order or a billed count."""
from __future__ import annotations

import json
import re
from typing import Any

from . import db

FIELDS = ("plan", "interval", "apartments", "ttlock")


def clean(params: Any) -> dict[str, str]:
    """Allow only bounded choices. Discard everything else, including prices/URLs."""
    result = {}
    for field, choices in (("plan", ("standard", "max")),
                           ("interval", ("month", "year")), ("ttlock", ("0", "1"))):
        value = params.get(field)
        if value in choices:
            result[field] = value
    count = params.get("apartments")
    if isinstance(count, str) and re.fullmatch(r"[1-9][0-9]?", count):
        if int(count) <= 50:
            result["apartments"] = str(int(count))
    return result


def for_owner(owner_user_id: int) -> dict[str, str]:
    row = db.query_one("SELECT signup_selection_json FROM user_account WHERE id = ?",
                       (owner_user_id,))
    try:
        values = json.loads(row["signup_selection_json"] or "{}") if row else {}
    except (ValueError, TypeError):
        return {}
    return clean(values) if isinstance(values, dict) else {}
