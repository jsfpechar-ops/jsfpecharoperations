"""Cached UbyPort code lists.

The service is authoritative (DejMiCiselnik) and the cached copy is refreshed
from it whenever working credentials exist. The bundled fallbacks in
`validation` keep the guest form usable before that ever happens.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Dict, List, Optional, Tuple

from . import db, validation
from .ubyport import errors as uby_errors

KIND_COUNTRIES = "staty"
KIND_PURPOSES = "ucely"
KIND_ERRORS = "chyby"

WS_KINDS = {KIND_COUNTRIES: "Staty", KIND_PURPOSES: "UcelyPobytu", KIND_ERRORS: "Chyby"}

CISELNIK_FIELDS = ("Kod3", "Kod2", "TextKratkyCZ", "TextKratkyENG", "TextCZ", "TextENG")

# "112", "0112" or "ERR_CZE_112" - all of these appear as error identifiers.
_CODE_LIKE = re.compile(r"^(?:[A-Z]+_[A-Z]+_)?\d{1,4}$", re.IGNORECASE)


def _code_and_texts(kind: str, row: Dict[str, str]) -> Tuple[str, str, str]:
    """Pull (code, Czech text, English text) out of one CiselnikType entry.

    The country list puts the code in Kod3 and the name in the text columns.
    The error list is laid out the other way round, so for that one the code is
    whichever column actually looks like a code and the description is the
    longest column that does not.
    """
    values = {field: (row.get(field) or "").strip() for field in CISELNIK_FIELDS}
    if kind == KIND_ERRORS:
        code = next((v for v in values.values() if _CODE_LIKE.match(v)), "")
        prose = [v for v in values.values() if v and v != code and not _CODE_LIKE.match(v)]
        text = max(prose, key=len) if prose else ""
        return code, text, text
    code = values["Kod3"] or values["Kod2"]
    return code, values["TextKratkyCZ"] or values["TextCZ"], values["TextKratkyENG"] or values["TextENG"]


def store(kind: str, rows: List[Dict[str, str]]) -> int:
    """Replace the cached copy of one code list."""
    now = db.utcnow()
    written = 0
    with db.cursor() as cur:
        cur.execute("DELETE FROM codelist WHERE kind = ?", (kind,))
        for row in rows:
            code, text_cs, text_en = _code_and_texts(kind, row)
            if not code:
                continue
            cur.execute(
                "INSERT OR REPLACE INTO codelist (kind, code, text_cs, text_en, extra, fetched_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (kind, code, text_cs, text_en, (row.get("Kod2") or "").strip(), now),
            )
            written += 1
    return written


def cached(kind: str) -> List:
    return db.query("SELECT * FROM codelist WHERE kind = ? ORDER BY code", (kind,))


def last_fetched(kind: str) -> Optional[str]:
    row = db.query_one("SELECT MAX(fetched_at) AS t FROM codelist WHERE kind = ?", (kind,))
    return row["t"] if row and row["t"] else None


def error_codebook() -> Dict[str, str]:
    """code -> explanation, used to turn "112" into something readable."""
    return uby_errors.codebook_from_rows(cached(KIND_ERRORS))


# The mock server ships a tiny country sample; the bundled ISO list is complete.
_MIN_CACHED_COUNTRIES = 150

# The nationalities a Czech host actually files, so the guest does not scroll a
# 254-row wheel. Order is the order they are shown in.
_COMMON_COUNTRIES = ("CZE", "SVK", "DEU", "POL", "AUT", "GBR", "USA", "UKR")


def _fold(label: str) -> str:
    """Sort key that reads Czech letters as their plain Latin neighbours.

    ``sorted`` compares code points, which files "Česko" after "Zimbabwe". The
    guest looking under "C" must find it, so the combining marks come off for
    the comparison only; the displayed label keeps its diacritics.
    """
    stripped = unicodedata.normalize("NFD", label)
    plain = "".join(ch for ch in stripped if not unicodedata.combining(ch))
    return plain.casefold()


def _all_countries(lang: str) -> List[Dict[str, str]]:
    """Every country, accent-folded sorted, labelled in ``lang``."""
    rows = cached(KIND_COUNTRIES)
    if len(rows) >= _MIN_CACHED_COUNTRIES:
        options = []
        for row in rows:
            label = (row["text_en"] if lang == "en" else row["text_cs"]) or row["text_cs"] or row["code"]
            options.append({"code": row["code"], "label": label})
        return sorted(options, key=lambda o: _fold(o["label"]))
    return sorted(
        (
            {"code": c["code"], "label": c["en"] if lang == "en" else c["cs"]}
            for c in validation.countries()
        ),
        key=lambda o: _fold(o["label"]),
    )


def nationality_options(lang: str = "en") -> List[Dict[str, str]]:
    """Country choices for the guest form.

    The police code list is preferred when it looks complete; otherwise the
    bundled ISO 3166-1 list keeps every nationality available offline.
    """
    return _all_countries(lang)


def country_groups(lang: str = "en") -> List[Dict[str, object]]:
    """The country list as two optgroups: the usual ones, then the rest.

    ``key`` is an i18n key the template renders as the optgroup label, so the
    group names stay in the guest's language. The common group keeps the order
    of ``_COMMON_COUNTRIES``; a code the code list does not know is skipped
    rather than shown empty.
    """
    options = _all_countries(lang)
    by_code = {option["code"]: option for option in options}
    common = [by_code[code] for code in _COMMON_COUNTRIES if code in by_code]
    return [
        {"key": "countries_common", "options": common},
        {"key": "countries_all", "options": options},
    ]


def purpose_options(lang: str = "en") -> List[Dict[str, str]]:
    by_code = {code: (cs, en) for code, cs, en in validation.PURPOSES}
    rows = cached(KIND_PURPOSES)
    if rows:
        options = []
        for row in rows:
            code = row["extra"] or row["code"]
            cs, en = by_code.get(code, ("", ""))
            if lang == "cs":
                label = row["text_cs"] or (f"{code} - {cs}" if cs else code)
            else:
                label = f"{code} - {en}" if en else (row["text_en"] or row["text_cs"] or code)
            options.append({"code": code, "label": label})
        return options
    return [
        {"code": code, "label": f"{code} - {cs if lang == 'cs' else en}"}
        for code, cs, en in validation.PURPOSES
    ]


def refresh_all(client) -> Dict[str, int]:
    """Pull all three code lists from the service."""
    written: Dict[str, int] = {}
    for kind, ws_kind in WS_KINDS.items():
        rows = client.code_list(ws_kind)
        written[kind] = store(kind, rows)
    return written
