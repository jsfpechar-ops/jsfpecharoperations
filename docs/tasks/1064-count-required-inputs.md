# 1064: Script that counts required inputs per flow

Status: review (lint fails only on main's status.md cap; fixed by #854)
Depends on: none | Base commit: 0d851ca4 | Branch: task/1064-required-inputs-count
Executor: Haiku 5.5 (owner override: Sonnet at medium effort) | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Add `scripts/count_required_inputs.py`, a stdlib-only script that reads the Jinja templates and prints, per user flow, the template files, the number of required inputs and the total inputs. The speed-and-ease plan (docs/plans/speed-and-ease.md section 9, row "Fields typed per flow", queue item 0.1) needs it run before and after Wave 1 so "fewer fields typed" is a number.

## 2. Context

- Tier C, scripts only. No change under `App/`, no new dependency (AGENTS.md rule 4), no personal data.
- How the templates mark "required" (found by grep; the script handles all four):
  1. A bare `required` attribute, e.g. `App/app/templates/signup.html:24` `<input type="email" id="email" name="email" required maxlength="254"`.
  2. A conditional one, e.g. `_account_parts.html:9` `{% if account_required %} required{% endif %}` and `_entity_business_fields.html:21`. Counted as required (upper bound).
  3. A macro whose body holds the input and whose call passes `true`: `_property_address_fields.html:8` `address_input(name, label, help, optional, maxlength, inputmode, required, extra)` and `setup_wizard/police.html:4` `text_field(name, label, value, help, optional, maxlength, required)`. Each call counts as one input, required when the 7th argument is `true`.
  4. `aria-required="{{ 'true' if fee_needed else 'false' }}"` in `_stay_fee_fields.html:35,40,51`. Counted as required.
  Not counted: `required` set by JavaScript (`guest/form.html:439`, the passport photo for foreign guests), and Jinja loops are not expanded (`payments_new.html:24` radio group counts as 1 input, 1 required). The script header says so.
- Flows and template paths (all under `App/app/templates/`), from docs/plans/speed-and-ease.md section 4: sign-up (`signup.html`, `signup_verify.html`), setup wizard (`setup_wizard/*.html`), operator (`entities.html`, `_entity_business_fields.html`), property (`_property_create.html` and its includes), calendars (`_property_calendars.html`), police details (`setup_wizard/police.html`), stay fee (`setup_wizard/stay_fee.html` + `_stay_fee_fields.html`), lock (`setup_wizard/door_lock.html`, `_smart_lock_share.html`), invoice (`invoice_form.html`, `_entity_invoice_fields.html`), payment request (`payments_consent.html`, `payments_new.html`), guest steps (`guest/pin.html`, `pick.html`, `claim.html`, `form.html`, `stay.html`). Files pulled in by `{% include %}` are followed automatically. Rows overlap on purpose (the wizard row contains the police, stay fee and lock rows); do not add rows together.
- Known limit: the host property editor (`_property_editor.html`, one page with police, stay fee and lock sections) is not a flow row, because its 15 required inputs cover many sections.
- Unverified plan rows: none apply to this brief (the "guest seconds" row of section 9 is not used).

Expected output on the base commit (the flow, required and total columns must match exactly; the file list column is not shown here):

```
flow                         | required | total
sign-up                      |        2 |     4
setup wizard (first run)     |       21 |    45
operator (entity)            |        4 |    10
property create              |        6 |    10
calendars                    |        2 |     4
police details (wizard step) |        5 |     7
stay fee (wizard step)       |        4 |    17
lock (wizard step)           |        2 |     4
invoice                      |        4 |    40
payment request              |        2 |     7
guest 1 PIN                  |        1 |     1
guest 2 pick stay            |        0 |     0
guest 3 claim                |        2 |     2
guest 4-7 form               |        9 |    16
guest 8 stay hub             |        1 |     1
```

## 3. Files

| Path | Action | What |
|---|---|---|
| `scripts/count_required_inputs.py` | create | The script, full content in step 1 |
| `docs/tasks/1064-report.md` | create | Report (section 9) |

No other file may change. Overlap with other open briefs: none (new file).

## 4. Steps

1. Create `scripts/count_required_inputs.py` with exactly this content.
   Command: `python3 -c "import ast; ast.parse(open('scripts/count_required_inputs.py').read()); print('syntax ok')" 2>&1 | tail -30`
   Expected: `syntax ok`

```python
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
```

2. Run the self-check.
   Command: `python3 scripts/count_required_inputs.py --selftest 2>&1 | tail -30`
   Expected: `selftest: OK`
3. Run the count and compare with the table in section 2.
   Command: `python3 scripts/count_required_inputs.py 2>&1 | cut -c1-120 | head -50`
   Expected: 16 lines (header plus 15 flows); the flow, required and total columns equal the section 2 table. A differing number means a template changed since the base commit: report it, do not edit the script to force a match.
4. Run the context lint.
   Command: `python3 scripts/context_lint.py 2>&1 | tail -30`
   Expected: last line `context lint: OK`. If it warns that this brief overlaps another open brief on a file, say which in the report; the brief only creates a new file, so order does not matter for correctness.
5. Write `docs/tasks/1064-report.md` (section 9) and set `Status: review` in this file.

## 5. Do not touch

`App/` (everything), `docs/context/`, `docs/plans/`, other briefs. AGENTS.md rules 3 and 4: no secrets, no new dependency.

## 6. Commands

Tests: none: scripts only (no row in docs/context/test-map.md covers `scripts/count_required_inputs.py`; the `--selftest` flag is the check). Do not run pytest.

- `python3 scripts/count_required_inputs.py --selftest 2>&1 | tail -30` gives `selftest: OK`.
- `python3 scripts/count_required_inputs.py 2>&1 | head -50` gives the table.
- `python3 scripts/context_lint.py 2>&1 | tail -30` ends `context lint: OK`.

## 7. Acceptance

- [ ] `scripts/count_required_inputs.py` exists and imports only `re`, `sys`, `pathlib`: `grep -n '^import\|^from' scripts/count_required_inputs.py | head -10`.
- [ ] `--selftest` prints `selftest: OK`.
- [ ] The table has 15 flow rows and matches section 2.
- [ ] `git status --short | head -10` shows only the script, this brief and the report; nothing under `App/`.
- [ ] `python3 scripts/context_lint.py` ends `context lint: OK`.
- [ ] No UI change, so no screenshots.

## 8. Stop and ask

Stop, and write the report, if:

- the script fails its syntax check or self-check twice;
- the table differs from section 2 (report both tables);
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`);
- a new dependency seems needed;
- a file outside section 3 needs a change;
- section 5 would be touched;
- a step is unclear.

## 9. Report

Write `docs/tasks/1064-report.md` (600 tokens at most) and set `Status: review`. It has: the files changed (`git diff --stat`), each command with the last 5 lines of output, section 7 ticked, deviations, questions, owner steps left. Paste the full table into the report: it is the Wave 1 "before" baseline.

## Risk list (for the reviewer)

`scripts/count_required_inputs.py` only. Check the flow file lists against docs/plans/speed-and-ease.md section 4 and that the "required" rules in section 2 match the code.

## Owner steps

None needed beyond merge.
