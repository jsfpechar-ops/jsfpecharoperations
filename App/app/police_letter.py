"""Parser for the pasted text of the police web-service letter.

Pure: no storage, no request, no logging, no file and no global state. The
same input always gives the same output.

The parser reads the IDUB, the web-service login and, when the letter prints
it, the short name (zkratka). When the short name is not printed it is derived
from the login with ``validation.mark_from_ws_user``.

The password is never read: there is no pattern for it, and a value that
shares a line with a password label is dropped.

A wrong value would file guests under the wrong account, so the rule is: when
in doubt, return nothing for that field. The host then types it.
"""

from __future__ import annotations

import re
import unicodedata
from bisect import bisect_right
from dataclasses import dataclass, field

from .validation import _WS_USER_RE, mark_from_ws_user

MAX_LETTER_CHARS = 20000
FIELDS = ("uby_idub", "uby_ws_user", "uby_mark")
FILLED_STATES = frozenset({"found", "derived"})

_MAX_FORM_LINE = 100000


@dataclass(frozen=True)
class FieldResult:
    state: str = "missing"
    value: str = ""
    line: int | None = None
    label: str = ""
    lines: tuple[int, ...] = ()


@dataclass(frozen=True)
class LetterResult:
    status: str
    fields: dict[str, FieldResult] = field(default_factory=dict)


# Non-ASCII characters that NFC would turn into ASCII (singleton
# decompositions): the Greek question mark (;), the Greek varia (`) and the
# Kelvin sign (K). They are kept as written, so NFC can never repair a value
# into an ASCII one.
_NFC_KEEP = frozenset(";`K")
_NFC_KEEP_RE = re.compile("([;`K])")
_SPACE_TABLE = {0x00A0: " ", 0x202F: " ", 0x2009: " ", 0x09: " "}

# Optional punctuation, then at most one line break. The same language as
# [ \t]*[:.\-–]?[ \t]*(?:\n[ \t]*)? but with one way to match a run of
# spaces, so a long run cannot cost quadratic time.
_GAP = r"[ \t]*(?:[:.\-–][ \t]*)?(?:\n[ \t]*)?"
# The value must end its line.
_END = r"[ \t]*(?:[.,;][ \t]*)?(?=\n|\Z)"

_FLAGS = re.IGNORECASE

# field -> (label pattern, value pattern). [0-9], never \d.
_PATTERNS = {
    "uby_idub": (
        r"(?<![A-Za-z0-9])IDUB(?![A-Za-z0-9])",
        r"([0-9]{12,14})",
    ),
    "uby_ws_user": (
        r"p[rř][ií]hla[sš]ovac[ií]\s+jm[eé]no",
        r"(uby-t?ws_?[A-Za-z0-9]{5,6})",
    ),
    "uby_mark": (
        r"zkratka\s+ubytovac[ií]ho\s+za[rř][ií]zen[ií]",
        r"([A-Za-z0-9]{5,6})",
    ),
}
_LABEL_RES = {name: re.compile(label, _FLAGS) for name, (label, _v) in _PATTERNS.items()}
_TAIL_RES = {
    name: re.compile(_GAP + value + _END, _FLAGS) for name, (_l, value) in _PATTERNS.items()
}

_PASSWORD_WORDS = ("heslo", "password", "passwort")

_MISSING = FieldResult()


def _all_missing() -> dict[str, FieldResult]:
    return {name: _MISSING for name in FIELDS}


def _normalise(text: str) -> str:
    text = "".join(
        part if part in _NFC_KEEP else unicodedata.normalize("NFC", part)
        for part in _NFC_KEEP_RE.split(text)
    )
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text.translate(_SPACE_TABLE)


def _line_starts(text: str) -> list[int]:
    starts = [0]
    pos = text.find("\n")
    while pos != -1:
        starts.append(pos + 1)
        pos = text.find("\n", pos + 1)
    return starts


def _valid_value(name: str, raw: str) -> str:
    """The value to keep, or "" when it is not a valid one."""
    if not raw.isascii():
        return ""
    if name == "uby_ws_user":
        return raw if _WS_USER_RE.fullmatch(raw) else ""
    if name == "uby_mark":
        return raw.upper()
    return raw


def _parse_field(name: str, text: str, starts: list[int], lines: list[str]) -> FieldResult:
    def line_of(pos: int) -> int:
        return bisect_right(starts, pos)

    hits: list[tuple[str, int, str]] = []  # value, value line, label
    unreadable: list[tuple[int, str]] = []  # label line, label
    guarded = False
    tail_re = _TAIL_RES[name]
    for label_match in _LABEL_RES[name].finditer(text):
        label = label_match.group(0)
        label_line = line_of(label_match.start())
        tail = tail_re.match(text, label_match.end())
        value = _valid_value(name, tail.group(1)) if tail else ""
        if not value:
            unreadable.append((label_line, label))
            continue
        value_line = line_of(tail.start(1))
        # Password guard: every line from the label to the value.
        for number in range(label_line, value_line + 1):
            lowered = lines[number - 1].lower()
            if any(word in lowered for word in _PASSWORD_WORDS):
                guarded = True
        hits.append((value, value_line, label))

    if unreadable:
        return FieldResult(
            state="unreadable",
            line=unreadable[0][0],
            label=unreadable[0][1],
            lines=tuple(sorted({number for number, _label in unreadable})),
        )
    if not hits:
        return _MISSING
    hit_lines = tuple(sorted({number for _value, number, _label in hits}))
    if name == "uby_idub":
        distinct = {value for value, _line, _label in hits}
    else:
        distinct = {value.upper() for value, _line, _label in hits}
    if guarded or len(distinct) != 1:
        return FieldResult(state="ambiguous", lines=hit_lines)
    value, value_line, label = hits[0]
    return FieldResult(state="found", value=value, line=value_line, label=label, lines=hit_lines)


def parse_letter(text: str) -> LetterResult:
    """Read the IDUB, the login and the short name from the pasted letter.

    Never raises. The password is never read.
    """
    if not isinstance(text, str) or not text.strip():
        return LetterResult(status="empty", fields=_all_missing())
    if len(text) > MAX_LETTER_CHARS:
        return LetterResult(status="too_long", fields=_all_missing())

    normalised = _normalise(text)
    starts = _line_starts(normalised)
    lines = normalised.split("\n")
    fields = {name: _parse_field(name, normalised, starts, lines) for name in FIELDS}

    user = fields["uby_ws_user"]
    mark = fields["uby_mark"]
    if user.state == "found":
        derived = mark_from_ws_user(user.value)
        if derived and derived.isascii():
            if mark.state == "missing":
                fields["uby_mark"] = FieldResult(
                    state="derived",
                    value=derived,
                    line=user.line,
                    label=user.label,
                    lines=user.lines,
                )
            elif mark.state == "found" and mark.value.upper() != derived.upper():
                both = tuple(sorted({n for n in (user.line, mark.line) if n is not None}))
                conflict = FieldResult(state="conflict", lines=both)
                fields["uby_ws_user"] = conflict
                fields["uby_mark"] = conflict
    return LetterResult(status="ok", fields=fields)


def _form_get(form, key: str):
    try:
        return form.get(key)
    except Exception:
        return None


def confirmed_fields(form) -> tuple[list[str], list[str]]:
    """(listed, unconfirmed) from the hidden letter_fields and the ticks.

    Never raises: a missing form or a value that is not a str counts as empty
    or unconfirmed.
    """
    raw = _form_get(form, "letter_fields")
    names = {part.strip() for part in raw.split(",")} if isinstance(raw, str) else set()
    listed = [name for name in FIELDS if name in names]
    unconfirmed = []
    for name in listed:
        tick = _form_get(form, f"letter_ok_{name}")
        if not (isinstance(tick, str) and tick == "1"):
            unconfirmed.append(name)
    return listed, unconfirmed


def line_from_form(form, name: str) -> int | None:
    """letter_line_<name> as an int from 1 to 100000, else None. Never raises."""
    raw = _form_get(form, f"letter_line_{name}")
    if not isinstance(raw, str) or not raw or len(raw) > 6:
        return None
    if not (raw.isascii() and raw.isdigit()):
        return None
    number = int(raw)
    if 1 <= number <= _MAX_FORM_LINE:
        return number
    return None
