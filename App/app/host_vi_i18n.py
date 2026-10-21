"""Vietnamese for the host app (brief 0196). Host app only.

The guest form, the public pages and the legal texts stay in their own
languages; a key missing here falls back to English through
``host_i18n.lookup``. Public and legal keys are left out on purpose.
"""
from __future__ import annotations

from typing import Dict, Tuple

LOCALE = "vi-VN"

WEEKDAYS: Tuple[str, ...] = ("Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật")

PURPOSES: Dict[str, str] = {
}

# cleaning_i18n.WORDS key -> Vietnamese.
CLEANING_WORDS: Dict[str, str] = {
}

# validation_i18n.CS_MESSAGES key (the English sentence) -> Vietnamese.
VALIDATION: Dict[str, str] = {
}

# The same order as validation_i18n.CS_PATTERNS: one template per pattern.
VALIDATION_PATTERNS: Tuple[str, ...] = ()

STRINGS: Dict[str, str] = {
}
