#!/usr/bin/env python3
"""Count form inputs per user flow from the Jinja templates (stdlib only).

Usage (repo root):  python3 scripts/count_required_inputs.py
                    python3 scripts/count_required_inputs.py --selftest

It is a static count, not a render: Jinja loops are not expanded and
conditional `required` attributes count as required (an upper bound).
Run it before and after a change and compare the two tables.

An input is `<input>`, `<select>` or `<textarea>`; hidden, submit, button
and image inputs are skipped. It is required when its tag has a bare
`required` attribute, or `aria-required="true"` (also the stay fee form's
`aria-required="{{ 'true' if ... }}"`). Two macros hide their input
inside the macro body, so each call counts as one input, required when
its 7th argument (or `required=`) is `true`: `address_input(` and
`text_field(`. `{% include "x.html" %}` files are followed once per flow.
"""
import re
import sys
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parent.parent / "App" / "app" / "templates"

FLOWS = [
    ("sign-up", ["signup.html", "signup_verify.html"]),
    ("setup wizard (first run)", [
        "setup_wizard/_layout.html", "setup_wizard/property.html",
        "setup_wizard/calendar.html", "setup_wizard/police.html",
        "setup_wizard/stay_fee.html", "setup_wizard/door_lock.html",
        "setup_wizard/automation.html", "setup_wizard/guest_link.html",
        "setup_wizard/try_it.html", "setup_wizard/done.html",
        "_smart_lock_share.html"]),
    ("operator (entity)", ["entities.html", "_entity_business_fields.html"]),
    ("property create", ["_property_create.html"]),
    ("calendars", ["_property_calendars.html"]),
    ("police details (wizard step)", ["setup_wizard/police.html"]),
    ("stay fee (wizard step)", ["setup_wizard/stay_fee.html"]),
    ("lock (wizard step)", ["setup_wizard/door_lock.html", "_smart_lock_share.html"]),
    ("invoice", ["invoice_form.html", "_entity_invoice_fields.html"]),
    ("payment request", ["payments_consent.html", "payments_new.html"]),
    ("guest 1 PIN", ["guest/pin.html"]),
    ("guest 2 pick stay", ["guest/pick.html"]),
    ("guest 3 claim", ["guest/claim.html"]),
    ("guest 4-7 form", ["guest/form.html"]),
    ("guest 8 stay hub", ["guest/stay.html"]),
]

MACROS = ("address_input", "text_field")
TAG = re.compile(r"<(input|select|textarea)\b((?:[^>\"']|\"[^\"]*\"|'[^']*')*)>", re.I)
SKIP_TYPES = ("hidden", "submit", "button", "image")


def _split_args(text):
    """Split call arguments on top-level commas (quotes and parens aware)."""
    args, depth, quote, cur = [], 0, "", ""
    for ch in text:
        if quote:
            cur += ch
            quote = "" if ch == quote else quote
        elif ch in "'\"":
            quote = ch
            cur += ch
        elif ch in "([{":
            depth += 1
            cur += ch
        elif ch in ")]}":
            depth -= 1
            cur += ch
        elif ch == "," and depth == 0:
            args.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        args.append(cur.strip())
    return args


def count_text(src):
    """Return (required, total) for one template's text."""
    src = re.sub(r"\{#.*?#\}", "", src, flags=re.S)
    required = total = 0
    for name in MACROS:
        src = re.sub(r"\{%-?\s*macro\s+" + name + r"\b.*?\{%-?\s*endmacro\s*-?%\}", "", src, flags=re.S)
        for m in re.finditer(r"\{\{-?\s*" + name + r"\((.*?)\)\s*-?\}\}", src, flags=re.S):
            args = _split_args(m.group(1))
            total += 1
            flag = any(a.replace(" ", "").lower() == "required=true" for a in args)
            flag = flag or (len(args) > 6 and "=" not in args[6].split("'")[0] and args[6].lower() == "true")
            required += 1 if flag else 0
    src = re.sub(r"aria-required=\"\{\{[^}]*'true'[^}]*\}\}\"", 'aria-required="true"', src)
    src = re.sub(r"\{%.*?%\}", " ", src, flags=re.S)
    src = re.sub(r"\{\{.*?\}\}", "x", src, flags=re.S)
    for m in TAG.finditer(src):
        attrs = m.group(2)
        kind = re.search(r"\btype=\"?'?(\w+)", attrs)
        if m.group(1).lower() == "input" and kind and kind.group(1).lower() in SKIP_TYPES:
            continue
        total += 1
        if re.search(r"(?<![\w-])required(?![\w-])", attrs) or 'aria-required="true"' in attrs:
            required += 1
    return required, total


def flow_files(roots):
    """Roots plus every file they include, each once, in order."""
    seen, queue = [], list(roots)
    while queue:
        rel = queue.pop(0)
        if rel in seen:
            continue
        seen.append(rel)
        text = (TEMPLATES / rel).read_text(encoding="utf-8")
        queue += re.findall(r"\{%-?\s*include\s+[\"']([^\"']+)[\"']", text)
    return seen


def selftest():
    assert count_text('<input name="a" required><input name="b">') == (1, 2)
    assert count_text('<input type="hidden" name="c"><select required></select>') == (1, 1)
    assert count_text('<input {%- if x %} required{% endif %}>') == (1, 1)
    assert count_text('<input data-guest-required="x" aria-describedby="r">') == (0, 1)
    assert count_text("{{ address_input('a', t('x'), '', false, 5, '', true) }}"
                      "{{ address_input('b', t('y'), '', true, 4) }}") == (1, 2)
    assert count_text("{#<input required>#}") == (0, 0)
    print("selftest: OK")


def main():
    if "--selftest" in sys.argv:
        selftest()
        return
    rows = []
    for flow, roots in FLOWS:
        files = flow_files(roots)
        req = tot = 0
        for rel in files:
            r, t = count_text((TEMPLATES / rel).read_text(encoding="utf-8"))
            req += r
            tot += t
        rows.append((flow, " ".join(files), str(req), str(tot)))
    head = ("flow", "template files", "required", "total")
    w0 = max(len(r[0]) for r in rows + [head])
    print(f"{head[0]:<{w0}} | {head[2]:>8} | {head[3]:>5} | {head[1]}")
    for flow, files, req, tot in rows:
        print(f"{flow:<{w0}} | {req:>8} | {tot:>5} | {files}")


if __name__ == "__main__":
    main()
