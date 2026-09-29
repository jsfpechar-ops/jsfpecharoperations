"""Keep guest-supplied text from running as a spreadsheet formula."""
from __future__ import annotations

from typing import Any

_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def csv_safe(value: Any) -> Any:
    """Prefix a text cell that Excel would evaluate with an apostrophe.

    Numbers and dates are left alone; only strings are touched. A value such
    as "+420 777 …" will show with a leading apostrophe, which is accepted.
    """
    if isinstance(value, str) and value.lstrip(" ").startswith(_FORMULA_PREFIXES):
        return "'" + value
    return value
