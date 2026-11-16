"""Stable keys for UbyPort failures (brief A1b P1; Go twin: go/internal/ubyport/faults.go).

``code_for`` names the row of the fault table a failure belongs to. It only picks
copy and the operator's key; behaviour is never chosen from message text.
"""
from __future__ import annotations

from typing import Optional


def code_for(cause: str, detail: str) -> Optional[str]:
    """``http_<status>`` for an HTTP answer that was not a success, else None."""
    if cause in ("http4xx", "redirect") and detail.startswith("HTTP "):
        return f"http_{detail[5:]}"
    return None
