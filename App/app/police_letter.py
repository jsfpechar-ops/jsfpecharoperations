"""Parser for the pasted text of the police web-service letter.

Pure: no storage, no request, no logging, no file and no global state. The
same input always gives the same output.

The parser reads the IDUB and the web-service login. The short name (zkratka)
is only ever derived from the login with ``validation.mark_from_ws_user``; a
printed one is never taken, it can only refuse the derived one.

A value is filled only when it is the single value of its shape in the whole
text and it follows its label. An IDUB or login that shares a line with a
password word is dropped. A password that looks like an IDUB or a login is a
second candidate, so nothing is filled.

1100: the web-service password and the facility name (first line) are read
too, into ``LetterResult.password`` and ``LetterResult.facility``. The
password is taken only after its label and a colon, whole, as one token; it
never goes into a source slice, a label or ``repr()``, and this module never
logs or stores anything. A password that looks like an IDUB or a login fills
nothing.

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
    # Exact slices of the normalised text the value came from: the label up to
    # the value, never a whole line. Only a filled field has them.
    source: tuple[str, ...] = ()


_MISSING = FieldResult()


@dataclass(frozen=True)
class LetterResult:
    status: str
    fields: dict[str, FieldResult] = field(default_factory=dict)
    # 1100: kept out of repr() so a logged result never shows the password.
    password: FieldResult = field(default=_MISSING, repr=False)
    facility: FieldResult = field(default=_MISSING, repr=False)


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

# field -> (label pattern, value pattern). [0-9], never \d. The short name
# has no pattern: a printed one is never taken as the value.
_PATTERNS = {
    "uby_idub": (
        r"(?<![A-Za-z0-9])IDUB(?![A-Za-z0-9])",
        r"[0-9]{12,14}",
    ),
    "uby_ws_user": (
        r"p[rř][ií]hla[sš]ovac[ií]\s+jm[eé]no",
        r"uby-t?ws_?[A-Za-z0-9]{5,6}",
    ),
}
_LABEL_RES = {
    name: re.compile(label, _FLAGS) for name, (label, _v) in _PATTERNS.items()
}
_TAIL_RES = {
    name: re.compile(f"(?:{_GAP_NEXT}|{_GAP_SAME})({value}){_END}", _FLAGS)
    for name, (_l, value) in _PATTERNS.items()
}

# Candidates in the whole text, with or without a label.
_DIGIT_RUN_RE = re.compile(r"[0-9]+")
# A chain: digit groups joined by single separators (one "-", en dash, ".",
# ",", "/" or "_", with or without spaces around it, or a run of spaces or
# tabs). Greedy from its first digit, so it is maximal.
_DIGIT_CHAIN_RE = re.compile(r"[0-9]+(?:(?:[ \t]*[-\u2013.,/_][ \t]*|[ \t]+)[0-9]+)*")
_CHAIN_SEPARATOR_RE = re.compile(r"[-\u2013.,/_ \t]+")
# The data-box barcode at the foot of every letter: never an IDUB.
_DS_BARCODE_RE = re.compile(r"[0-9]{3}\.[0-9]{4}\.[0-9]{7}")
# Any dash, and spaces around it: such a token is never a value, but it is a
# second login.
_LOGIN_TOKEN_RE = re.compile(
    r"uby[ \t]*[-\u2010\u2011\u2012\u2013\u2014\u2212][ \t]*t?ws[_A-Za-z0-9]*", _FLAGS
)
# Before a label, its line may hold only spaces and these noise characters.
_LABEL_PREFIX_RE = re.compile(r"[ \t|_>\u2022*\-]*")
_SOFT_HYPHEN = "\u00ad"
_MAX_SOURCE = 120

# Password words, searched in the lower-cased line without diacritics. The
# stem "hesl" covers heslo, hesla, heslem, hesel.
_PASSWORD_RE = re.compile(r"hesl|password|passwort")
# Any form of "zkratka", searched the same way.
_MARK_WORD = "zkratk"
_WORD_RE = re.compile(r"[^\W_]+")
_LEADING_NOISE_RE = re.compile(r"^[\W_]+")
_TRAILING_NOISE_RE = re.compile(r"[\W_]+$")

# 1100: the password label needs a colon; the value is one printable ASCII
# token that ends its line (no _END: a trailing "." may be part of it).
_PW_LABEL_RE = re.compile(
    r"(?:p[rř][ií]stupov[eé][ \t]+heslo|\bheslo\b|\bpassword\b)[ \t]*:", _FLAGS
)
_PW_VALUE_RE = re.compile(r"[ \t]*(?:\n[ \t]*)?([!-~]{6,64})[ \t]*(?=\n|\Z)")
_IDUB_SHAPE_RE = re.compile(r"\d{12,14}")
_FACILITY_LABEL_RE = re.compile(
    r"^[ \t]*Ubytovac[ií][ \t]+za[rř][ií]zen[ií][ \t]*:", _FLAGS | re.MULTILINE
)
_MAX_FACILITY = 35


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
    """Lower case, without diacritics (for the password and zkratka words)."""
    decomposed = unicodedata.normalize("NFD", line)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower()


def _has_password_word(line: str) -> bool:
    return bool(_PASSWORD_RE.search(_plain(line)))


def _line(lines: list[str], number: int) -> str:
    """Line by 1-based number, "" outside the text."""
    return lines[number - 1] if 1 <= number <= len(lines) else ""


def _candidates(name: str, text: str) -> list[tuple[str, int]]:
    """Every value-shaped token in the whole text: (value, end position)."""
    found = []
    if name == "uby_idub":
        # A separated chain ("2099-8877-6655") is never a value, but it is a
        # second number. Chains are compared as written, with no separator
        # folding: the same digits written with separators are a second one.
        for match in _DIGIT_CHAIN_RE.finditer(text):
            chain = match.group(0)
            joined = _CHAIN_SEPARATOR_RE.sub("", chain)
            if not 12 <= len(joined) <= 14:
                continue
            if _DS_BARCODE_RE.fullmatch(chain):
                continue  # the data-box barcode
            if text[: match.start()].rstrip(" \t").endswith("+"):
                continue  # a phone number
            found.append((chain, match.end()))
        # Every unbroken run of 12 to 14 digits counts too, also inside a
        # longer chain or a phone number, and so does a run of 12 or more
        # digits right after a "+": never a value, but a second number.
        for match in _DIGIT_RUN_RE.finditer(text):
            size = len(match.group(0))
            plus = match.start() > 0 and text[match.start() - 1] == "+"
            if 12 <= size <= 14 or (plus and size >= 12):
                found.append((match.group(0), match.end()))
    else:
        for match in _LOGIN_TOKEN_RE.finditer(text):
            found.append((match.group(0).upper(), match.end()))
    return found


def _wrapped(name: str, next_line: str) -> bool:
    """The line after a value looks like the rest of a wrapped value."""
    rest = _LEADING_NOISE_RE.sub("", next_line)
    if not rest:
        return False
    if name == "uby_idub" and rest[0].isdigit():
        return True
    if name == "uby_ws_user":
        # "UBY-WS_ABCDE" then a line that starts "F": the login may be cut.
        word = _WORD_RE.match(rest)
        if word and 1 <= len(word.group(0)) <= 3:
            return True
    fragment = _TRAILING_NOISE_RE.sub("", rest)
    return 1 <= len(fragment) <= 3 and fragment.isalnum()


def _valid_value(name: str, raw: str) -> str:
    """The value to keep, or "" when it is not a valid one."""
    if not raw.isascii():
        return ""
    if name == "uby_ws_user":
        return raw if _WS_USER_RE.fullmatch(raw) else ""
    return raw


def _parse_field(
    name: str, text: str, starts: list[int], lines: list[str]
) -> FieldResult:
    def line_of(pos: int) -> int:
        return bisect_right(starts, pos)

    # value, value line, label, source
    hits: list[tuple[str, int, str, tuple[str, ...]]] = []
    labels: list[tuple[int, str]] = []  # label line, label
    bad_labels: list[tuple[int, str]] = []
    guarded = False
    tail_re = _TAIL_RES[name]
    for label_match in _LABEL_RES[name].finditer(text):
        if _PROSE_RE.match(text, label_match.end()):
            continue  # "… IDUB." is a sentence, not a label
        label = label_match.group(0)
        label_line = line_of(label_match.start())
        labels.append((label_line, label))
        # The label starts its line: text before it means the field is unsure.
        before = text[starts[label_line - 1] : label_match.start()]
        if not _LABEL_PREFIX_RE.fullmatch(before):
            bad_labels.append((label_line, label))
            continue
        tail = tail_re.match(text, label_match.end())
        value = _valid_value(name, tail.group(1)) if tail else ""
        if not value:
            bad_labels.append((label_line, label))
            continue
        value_line = line_of(tail.start(1))
        # Password guard: every line from the label to the value.
        for number in range(label_line, value_line + 1):
            if _has_password_word(lines[number - 1]):
                guarded = True
        gap = text[label_match.end() : tail.start(1)]
        if "\n" in gap:
            colon = label_match.end() + gap.index(":") + 1
            source = (text[label_match.start() : colon], tail.group(1))
        else:
            source = (text[label_match.start() : tail.end(1)],)
        hits.append(
            (value, value_line, label, tuple(part[:_MAX_SOURCE] for part in source))
        )

    if not labels:
        return _MISSING  # no label: numbers and logins in the text mean nothing

    def unreadable(marked: list[tuple[int, str]]) -> FieldResult:
        return FieldResult(
            state="unreadable",
            line=marked[0][0],
            label=marked[0][1],
            lines=tuple(sorted({number for number, _label in marked})),
        )

    if bad_labels:
        return unreadable(bad_labels)
    # One answer in the whole text, or none.
    candidates = _candidates(name, text)
    distinct = {value for value, _end in candidates}
    if len(distinct) != 1:
        return unreadable(labels)
    only = next(iter(distinct))
    if any(value.upper() != only for value, _line_no, _label, _source in hits):
        return unreadable(labels)
    for _value, end in candidates:
        if _wrapped(name, _line(lines, line_of(end - 1) + 1)):
            return unreadable(labels)
    hit_lines = tuple(sorted({hit[1] for hit in hits}))
    if guarded:
        return FieldResult(state="ambiguous", lines=hit_lines)
    value, value_line, label, source = hits[0]
    return FieldResult(
        state="found",
        value=value,
        line=value_line,
        label=label,
        lines=hit_lines,
        source=source,
    )


def _parse_password(
    text: str, starts: list[int], fields: dict[str, FieldResult]
) -> FieldResult:
    """The web-service password after its label and colon, or nothing."""
    labels = list(_PW_LABEL_RE.finditer(text))
    if not labels:
        return _MISSING
    values = []
    bad = False
    value_line = None
    for label_match in labels:
        tail = _PW_VALUE_RE.match(text, label_match.end())
        if not tail:
            bad = True
            continue
        values.append(tail.group(1))
        value_line = bisect_right(starts, tail.start(1))
    first_line = bisect_right(starts, labels[0].start())
    distinct = set(values)
    if len(distinct) > 1:
        return FieldResult(state="ambiguous", line=first_line)
    if bad or not distinct:
        return FieldResult(state="unreadable", line=first_line)
    value = values[0]
    known = {fields[name].value for name in ("uby_idub", "uby_ws_user")}
    if (
        value in known
        or value.upper() in known
        or _IDUB_SHAPE_RE.fullmatch(value)
        or _WS_USER_RE.fullmatch(value)
        or _WS_USER_RE.fullmatch(value.upper())
    ):
        return FieldResult(state="unreadable", line=first_line)
    return FieldResult(state="found", value=value, line=value_line)


def _parse_facility(text: str, starts: list[int], lines: list[str]) -> FieldResult:
    """The first line of the facility name after "Ubytovací zařízení:"."""
    labels = list(_FACILITY_LABEL_RE.finditer(text))
    if not labels:
        return _MISSING
    label_line = bisect_right(starts, labels[0].start())
    if len(labels) > 1:
        return FieldResult(state="ambiguous", line=label_line)
    rest = text[labels[0].end() : starts[label_line] if label_line < len(starts) else len(text)]
    value, value_line = rest.strip(), label_line
    if not value:
        for number in range(label_line + 1, len(lines) + 1):
            if lines[number - 1].strip():
                value, value_line = lines[number - 1].strip(), number
                break
    if not value or len(value) > _MAX_FACILITY:
        return FieldResult(state="unreadable", line=label_line)
    return FieldResult(state="found", value=value, line=value_line)


def _mark_words(line: str) -> list[str]:
    """Words of 4 to 7 characters that could be a printed short name."""
    return [
        word
        for word in _WORD_RE.findall(line.replace(_SOFT_HYPHEN, ""))
        if 4 <= len(word) <= 7 and _MARK_WORD not in _plain(word)
    ]


def _mark_conflicts(lines: list[str], derived: str) -> list[int]:
    """Lines that print a different short name next to a "zkratka" word.

    A 4 to 7 character word on a zkratka line that differs from the derived
    mark; the "zkratka" word itself does not count. When the zkratka line
    holds no such word, the next line that is not blank is read instead. A
    soft hyphen on a line that is read is a conflict on its own.
    """
    wanted = derived.upper()
    conflicts = []
    for index, line in enumerate(lines):
        if _MARK_WORD not in _plain(line.replace(_SOFT_HYPHEN, "")):
            continue
        number = index + 1
        soft = _SOFT_HYPHEN in line
        words = _mark_words(line)
        if not words:
            for later in range(index + 1, len(lines)):
                if lines[later].strip():
                    words = _mark_words(lines[later])
                    if _SOFT_HYPHEN in lines[later]:
                        soft = True
                    if not soft:
                        number = later + 1
                    break
        if soft or any(word.upper() != wanted for word in words):
            conflicts.append(number)
    return conflicts


def parse_letter(text: str) -> LetterResult:
    """Read the IDUB, the login, the password and the facility name; derive the short name.

    Never raises. The password is returned only in ``result.password`` (never
    in a source slice or repr) and is never logged or stored here.
    """
    if not isinstance(text, str) or not text.strip():
        return LetterResult(status="empty", fields=_all_missing())
    if len(text) > MAX_LETTER_CHARS:
        return LetterResult(status="too_long", fields=_all_missing())

    normalised = _normalise(text)
    starts = _line_starts(normalised)
    lines = normalised.split("\n")
    fields = _all_missing()
    for name in _PATTERNS:
        fields[name] = _parse_field(name, normalised, starts, lines)

    user = fields["uby_ws_user"]
    if user.state == "found":
        derived = mark_from_ws_user(user.value)
        if derived and derived.isascii():
            conflict_lines = _mark_conflicts(lines, derived)
            if conflict_lines:
                both = tuple(
                    sorted({n for n in (user.line, *conflict_lines) if n is not None})
                )
                conflict = FieldResult(state="conflict", lines=both)
                fields["uby_ws_user"] = conflict
                fields["uby_mark"] = conflict
            else:
                fields["uby_mark"] = FieldResult(
                    state="derived",
                    value=derived,
                    line=user.line,
                    label=user.label,
                    lines=user.lines,
                    source=user.source,
                )
    return LetterResult(
        status="ok",
        fields=fields,
        password=_parse_password(normalised, starts, fields),
        facility=_parse_facility(normalised, starts, lines),
    )


def _form_get(form, key: str):
    try:
        return form.get(key)
    except Exception:  # noqa: BLE001 - a forged form must never crash the re-render
        return None


def confirmed_fields(form) -> tuple[list[str], list[str]]:
    """(listed, unconfirmed) from the hidden letter_fields.

    1100: there is no confirm tick any more (owner, reverses 1097); every
    value is its own editable box, so nothing is ever unconfirmed and the
    second list is always empty. The signature stays for the callers. Never
    raises: a missing form or a value that is not a str counts as empty.
    """
    raw = _form_get(form, "letter_fields")
    names = {part.strip() for part in raw.split(",")} if isinstance(raw, str) else set()
    listed = [name for name in FIELDS if name in names]
    return listed, []


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
