"""Brief 1864 step 1: replace caddy_match in two files. Each old block must occur once."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

PARITY_DOC_OLD = """For each UBYHOST_GO_PATHS entry (Caddy `path` matcher: exact, trailing * = prefix,
other * = glob inside one segment) it finds the Python routes (METHOD /path)
"""
PARITY_DOC_NEW = """For each UBYHOST_GO_PATHS entry (Caddy `path` matcher, see caddy_match: exact,
trailing * = prefix, otherwise Go path.Match) it finds the Python routes (METHOD /path)
"""
PARITY_OLD = """def caddy_match(entry, sample):
    e, s = entry.lower(), sample.lower()
    if "*" not in e:
        return e == s
    if e.endswith("*") and "*" not in e[:-1]:
        return s.startswith(e[:-1])
    pat = re.escape(e).replace(r"\\*", "[^/]*")
    return re.fullmatch(pat, s) is not None
"""
PARITY_NEW = """def _class_char(pattern, i):
    \"\"\"One class character at i (Go path.Match getEsc) and the index after it.\"\"\"
    if i >= len(pattern) or pattern[i] in "-]":
        return None, i
    if pattern[i] == "\\\\":
        i += 1
        if i >= len(pattern):
            return None, i
    return pattern[i], i + 1


def _glob_regex(pattern):
    \"\"\"Go path.Match as a regular expression; None for a pattern Go rejects.

    `*` is any run of characters other than `/`, `?` one such character, `[...]`
    and `[^...]` a class of characters and ranges (a class can match `/`), and a
    backslash escapes the next character.
    \"\"\"
    out, i, n = [], 0, len(pattern)
    while i < n:
        c = pattern[i]
        i += 1
        if c == "*":
            out.append("[^/]*")
        elif c == "?":
            out.append("[^/]")
        elif c == "\\\\":
            if i == n:
                return None
            out.append(re.escape(pattern[i]))
            i += 1
        elif c == "[":
            cls, items = "[", 0
            if i < n and pattern[i] == "^":
                cls, i = "[^", i + 1
            while i == n or pattern[i] != "]" or not items:
                lo, i = _class_char(pattern, i)
                if lo is None:
                    return None
                hi = lo
                if i < n and pattern[i] == "-":
                    hi, i = _class_char(pattern, i + 1)
                    if hi is None or hi < lo:
                        return None
                cls += re.escape(lo) + ("-" + re.escape(hi) if hi != lo else "")
                items += 1
            out.append(cls + "]")
            i += 1
        else:
            out.append(re.escape(c))
    return "".join(out)


def caddy_match(entry, sample):
    \"\"\"Caddy's `path` matcher for one entry (caddyhttp MatchPath; no `%` escapes).

    Case-insensitive. `*` alone matches everything; `*x*`, `*x` and `x*` are
    substring, suffix and prefix matches when those are the only stars; every
    other entry is Go path.Match, so `/reservations/*[0-9]` is one path segment
    ending in a digit. Caddy also cleans the request path (keeping a trailing
    slash); the samples here are already clean.
    \"\"\"
    e, s = entry.lower(), sample.lower()
    if "%" in e:
        raise ValueError(f"{entry}: % escapes are not supported")
    if e == "*":
        return True
    stars = e.count("*")
    if stars == 2 and e.startswith("*") and e.endswith("*"):
        return e[1:-1] in s
    if stars == 1 and e.startswith("*"):
        return s.endswith(e[1:])
    if stars == 1 and e.endswith("*"):
        return s.startswith(e[:-1])
    pat = _glob_regex(e)
    return pat is not None and re.fullmatch(pat, s) is not None
"""

STACK_IMPORT_OLD = """import os
import re
import shutil
"""
STACK_IMPORT_NEW = """import functools
import importlib.util
import os
import re
import shutil
"""
STACK_OLD = """def caddy_match(entry: str, sample: str) -> bool:
    \"\"\"Same rules as scripts/go_parity_check.py and Caddy path matchers.\"\"\"
    e, s = entry.lower(), sample.lower()
    if "*" not in e:
        return e == s
    if e.endswith("*") and "*" not in e[:-1]:
        return s.startswith(e[:-1])
    pat = re.escape(e).replace(r"\\*", "[^/]*")
    return re.fullmatch(pat, s) is not None
"""
STACK_NEW = """@functools.lru_cache(maxsize=None)
def _parity_check():
    \"\"\"scripts/go_parity_check.py, loaded once by path (it is not a package).\"\"\"
    spec = importlib.util.spec_from_file_location(
        "go_parity_check", REPO_ROOT / "scripts" / "go_parity_check.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def caddy_match(entry: str, sample: str) -> bool:
    \"\"\"caddy_match of scripts/go_parity_check.py, so the two can never differ.\"\"\"
    return _parity_check().caddy_match(entry, sample)
"""


def patch(rel, pairs):
    path = ROOT / rel
    text = path.read_text(encoding="utf-8")
    for old, new in pairs:
        if text.count(old) != 1:
            raise SystemExit(f"STOP: {rel}: an old block is found {text.count(old)} times, want 1")
        text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")
    print(f"patched {rel}")


patch("scripts/go_parity_check.py", [(PARITY_DOC_OLD, PARITY_DOC_NEW), (PARITY_OLD, PARITY_NEW)])
patch("App/tests/go_stack.py", [(STACK_IMPORT_OLD, STACK_IMPORT_NEW), (STACK_OLD, STACK_NEW)])
