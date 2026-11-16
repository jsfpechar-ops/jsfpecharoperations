"""Stable keys for UbyPort failures (brief A1b P1/P2; Go twin: go/internal/ubyport/faults.go).

``code_for`` names the row of the fault table a failure belongs to. It only picks
copy and the operator's key; behaviour is never chosen from message text. The
fault table is the only text compare in this module, and it only picks copy.
"""
from __future__ import annotations

from typing import Optional, Tuple

# (error_code, match in the cleaned fault text, host copy key). Only faults seen
# live are mapped; anything else uses the capped text with no error_code.
FAULT_ROWS: Tuple[Tuple[str, str, str], ...] = (
    (
        "uby_runtime_no_errors",
        "Odpověď neobsahuje záznamy o chybách",
        "ubyport.fault.uby_runtime_no_errors",
    ),
    ("uby_runtime", "Chyba běhu programu", "ubyport.fault.uby_runtime"),
)

FAULT_UNKNOWN_KEY = "ubyport.fault.unknown"
FAULT_DETAIL_CAP = 200


def fault_row(detail: str) -> Optional[Tuple[str, str, str]]:
    """The first row whose ``match`` occurs in ``detail``, compared case-insensitively."""
    folded = (detail or "").casefold()
    for row in FAULT_ROWS:
        if row[1].casefold() in folded:
            return row
    return None


def code_for(cause: str, detail: str) -> Optional[str]:
    """``http_<status>`` for an HTTP answer that was not a success; the fault row
    key for a SOAP fault whose text matches a row; else None (shared fixture, PR 1058)."""
    if cause in ("http4xx", "redirect") and detail.startswith("HTTP "):
        return f"http_{detail[5:]}"
    if cause == "fault":
        row = fault_row(detail)
        return row[0] if row else None
    return None


def host_copy_key(cause: str, detail: str) -> Optional[str]:
    """The host copy key for a SOAP fault, else None. Unknown faults use the capped text."""
    if cause != "fault":
        return None
    row = fault_row(detail)
    return row[2] if row else FAULT_UNKNOWN_KEY


def host_detail(detail: str) -> str:
    """The cleaned fault text, capped for the host. Never an HTTP body."""
    return (detail or "")[:FAULT_DETAIL_CAP]
