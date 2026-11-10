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

from .validation import _MARK_RE, _WS_USER_RE, mark_from_ws_user

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

# Between a label and a value on the same line: optional ":" or a dash. A
# "." is not allowed: sentence punctuation after a label means prose.
_GAP_SAME = r"[ \t]*(?:[:\-–][ \t]*)?"
# A value on the next line needs the colon: "IDUB:" then the value.
_GAP_NEXT = r"[ \t]*:[ \t]*\n[ \t]*"
# The value must end its line.
_END = r"[ \t]*(?:[.,;][ \t]*)?(?=\n|\Z)"
# Sentence punctuation right after a label: prose, not a label.
_PROSE_RE = re.compile(r"[ \t]*[.,;!?…]")

_FLAGS = re.IGNORECASE

# field -> (label pattern, value pattern, value may sit on the next line).
# [0-9], never \d.
_PATTERNS = {
    "uby_idub": (
        r"(?<![A-Za-z0-9])IDUB(?![A-Za-z0-9])",
        r"[0-9]{12,14}",
        True,
    ),
    "uby_ws_user": (
        r"p[rř][ií]hla[sš]ovac[ií]\s+jm[eé]no",
        r"uby-t?ws_?[A-Za-z0-9]{5,6}",
        True,
    ),
    "uby_mark": (
        r"zkratka\s+ubytovac[ií]ho\s+za[rř][ií]zen[ií]",
        r"[A-Za-z0-9]{5,6}",
        False,
    ),
}
_LABEL_RES = {name: re.compile(label, _FLAGS) for name, (label, _v, _n) in _PATTERNS.items()}
_VALUE_RES = {name: re.compile(value, _FLAGS) for name, (_l, value, _n) in _PATTERNS.items()}
_TAIL_RES = {
    name: re.compile(
        (f"(?:{_GAP_NEXT}|{_GAP_SAME})" if next_line else _GAP_SAME) + f"({value})" + _END,
        _FLAGS,
    )
    for name, (_l, value, next_line) in _PATTERNS.items()
}
# A bare "Zkratka" is not a label and never fills the mark. It is read only to
# refuse a login whose derived mark differs from it.
_BARE_MARK_RE = re.compile(r"(?<![A-Za-z0-9])zkratka(?![A-Za-z0-9])(?!\s+ubytovac)", _FLAGS)
_BARE_MARK_TAIL_RE = re.compile(_GAP_SAME + r"([A-Za-z0-9]{5,6})" + _END, _FLAGS)

# Password words, searched in the lower-cased line without diacritics. The
# stem "hesl" covers heslo, hesla, heslem, hesel.
_PASSWORD_RE = re.compile(r"hesl|password|passwort")
# A password label with no value on its own line.
_OPEN_PASSWORD_RE = re.compile(r"(?:hesl\w*|password|passwort)[ \t]*:?[ \t]*$")
# Any "Word…:" line start counts as a label line.
_GENERIC_LABEL_RE = re.compile(r"[^\W\d_][^:\n]{2,}:")
_NOISE = " \t|_"

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


def _plain(line: str) -> str:
    """Lower case, without diacritics (for the password words only)."""
    decomposed = unicodedata.normalize("NFD", line)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower()


def _has_password_word(line: str) -> bool:
    return bool(_PASSWORD_RE.search(_plain(line)))


def _is_label_line(line: str) -> bool:
    if _GENERIC_LABEL_RE.match(line.lstrip(_NOISE)):
        return True
    if _has_password_word(line) or _BARE_MARK_RE.search(line):
        return True
    return any(label_re.search(line) for label_re in _LABEL_RES.values())


def _line(lines: list[str], number: int) -> str:
    """Line by 1-based number, "" outside the text."""
    return lines[number - 1] if 1 <= number <= len(lines) else ""


def _password_above(lines: list[str], label_line: int) -> bool:
    """A password label above this label may still be waiting for its value.

    True when a password word sits on the line above, or two lines above
    unless that line is an open password label and the line between is its
    value (not blank, not a label).
    """
    above = _line(lines, label_line - 1)
    if _has_password_word(above):
        return True
    two_above = _line(lines, label_line - 2)
    if not _has_password_word(two_above):
        return False
    is_open = bool(_OPEN_PASSWORD_RE.search(_plain(two_above).rstrip()))
    took_value = bool(above.strip(_NOISE)) and not _is_label_line(above)
    return not (is_open and took_value)


def _valid_value(name: str, raw: str) -> str:
    """The value to keep, or "" when it is not a valid one."""
    if not raw.isascii():
        return ""
    if name == "uby_ws_user":
        return raw if _WS_USER_RE.fullmatch(raw) else ""
    if name == "uby_mark":
        return raw.upper() if _MARK_RE.fullmatch(raw) else ""
    return raw


def _parse_field(name: str, text: str, starts: list[int], lines: list[str]) -> FieldResult:
    def line_of(pos: int) -> int:
        return bisect_right(starts, pos)

    hits: list[tuple[str, int, str]] = []  # value, value line, label
    unreadable: list[tuple[int, str]] = []  # label line, label
    guarded = False
    tail_re = _TAIL_RES[name]
    value_re = _VALUE_RES[name]
    for label_match in _LABEL_RES[name].finditer(text):
        if _PROSE_RE.match(text, label_match.end()):
            continue  # "… IDUB." is a sentence, not a label
        label = label_match.group(0)
        label_line = line_of(label_match.start())
        label_end_line = line_of(label_match.end() - 1)
        tail = tail_re.match(text, label_match.end())
        value = _valid_value(name, tail.group(1)) if tail else ""
        if not value:
            unreadable.append((label_line, label))
            continue
        value_line = line_of(tail.start(1))
        on_next_line = value_line != label_end_line
        if on_next_line and _password_above(lines, label_line):
            # The line below the label may be the password.
            unreadable.append((label_line, label))
            continue
        after = _line(lines, value_line + 1).strip(_NOISE)
        if after:
            if on_next_line and value_re.fullmatch(after.rstrip(" \t.,;")):
                guarded = True  # two value lines under one label
            elif after[0].isalnum() and not _is_label_line(after):
                # The value may be wrapped: "…655" then "66".
                unreadable.append((label_line, label))
                continue
        # Password guard: every line from the label to the value.
        for number in range(label_line, value_line + 1):
            if _has_password_word(lines[number - 1]):
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
        distinct = {value for value, _line_no, _label in hits}
    else:
        distinct = {value.upper() for value, _line_no, _label in hits}
    if guarded or len(distinct) != 1:
        return FieldResult(state="ambiguous", lines=hit_lines)
    value, value_line, label = hits[0]
    return FieldResult(state="found", value=value, line=value_line, label=label, lines=hit_lines)


def _bare_mark_conflicts(text: str, starts: list[int], derived: str) -> list[int]:
    """Lines of a bare "Zkratka: XXXXX" whose value differs from the derived mark."""
    found_lines = []
    for match in _BARE_MARK_RE.finditer(text):
        tail = _BARE_MARK_TAIL_RE.match(text, match.end())
        if not tail:
            continue
        value = _valid_value("uby_mark", tail.group(1))
        if value and value != derived.upper():
            found_lines.append(bisect_right(starts, tail.start(1)))
    return found_lines


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
            conflict_lines = _bare_mark_conflicts(normalised, starts, derived)
            if mark.state == "found" and mark.value.upper() != derived.upper():
                conflict_lines.append(mark.line)
            if conflict_lines:
                both = tuple(sorted({n for n in (user.line, *conflict_lines) if n is not None}))
                conflict = FieldResult(state="conflict", lines=both)
                fields["uby_ws_user"] = conflict
                if mark.state in ("found", "missing"):
                    fields["uby_mark"] = conflict
            elif mark.state == "missing":
                fields["uby_mark"] = FieldResult(
                    state="derived",
                    value=derived,
                    line=user.line,
                    label=user.label,
                    lines=user.lines,
                )
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
