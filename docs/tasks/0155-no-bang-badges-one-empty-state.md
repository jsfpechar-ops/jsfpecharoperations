# 0155: Overdue badges without "!", one compact empty state on the dashboard

Status: done
Depends on: 0154 | Base commit: 6c51d3f | Branch: claude/project-thread-5hw8cf
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

Owner request (Josef, 2026-10-19, phone screenshots): drop the "!" in front of "overdue by 4 days" and the other red badges; the dashboard of a host with no stays shows two big empty states ("You are caught up" and "No stays yet ...") that do not fit the phone screen. Commit once at the end as `0155 step 7`. Never push, never open a PR.

## 1. Objective

1. Overdue badges keep their 1 px coral border and their word, but lose the "!" prefix everywhere (`ui_badge`, `progress_pill`, `submission_pill`, deadline cell). MASTER is updated to match.
2. Dashboard: when the host has no stays at all (`rows` is empty), the "Needs action now" section is not rendered, so only the one "No stays yet / Connect a calendar" empty state shows. Empty states get less padding (32 px top/bottom instead of 48) and a 16 px title on phone.

## 2. Context

Anchors (verbatim, current code):

- A. `App/app/templates/_ui.html` line 23: `{#- 7.5 badge. kind: action | attention | done | neutral. overdue prefixes "!" and a border. -#}`
- B. `App/app/templates/_ui.html` line 25: `<span class="ui-badge ui-badge-{{ kind }}{{ ' ui-badge-overdue' if overdue }}">{% if overdue %}! {% endif %}{{ label }}</span>`
- C. `App/app/templates/_components.html` contains exactly these three fragments, once each: `{% if tone == 'red' %}! {% endif %}`, `{% if stone == 'red' %}! {% endif %}`, `{% if cell.level == 'overdue' %}! {% endif %}`
- D. `App/app/templates/dashboard.html`, the line `  {% call ui_section(t('dashboard.section.needs_action', count=counts.attention), actions='<a href="/reservations">' ~ t('dashboard.section.view_stays') ~ '</a>', id='needs-action') %}` and, four lines below it, the line `  {% endcall %}` (the first `{% endcall %}` after anchor D).
- E. `App/app/static/host2.css`: `.host-workspace .ui-empty { text-align: center; padding: var(--space-12) var(--space-6); color: var(--ink-2); }`
- F. `App/tests/test_design_ui_macros.py` line 39: `    assert "ui-badge-overdue\">! Late" in _r('{{ ui_badge("action", "Late", true) }}')`
- G. `App/tests/test_design_shared_macros.py` line 15: `    cases = {"failed": ("action", "red", "! "), "incomplete": ("action", "amber", ""), "ready": ("action", "blue", ""),`
- H. `docs/design/MASTER.md`: line 13 contains `overdue adds "!".`; line 223 contains `` `overdue=true` prefixes "!" and uses a 1 px `--status-action-dot` border.``; line 349 contains `overdue has "!";`

## 3. Files

| Path | Action |
|---|---|
| `App/app/templates/_ui.html` | edit (A, B) |
| `App/app/templates/_components.html` | edit (C) |
| `App/app/templates/dashboard.html` | edit (D) |
| `App/app/static/host2.css` | edit (E) and append |
| `App/app/templates/base.html` | host2.css key |
| `App/tests/static_versions.json` | regenerate |
| `App/tests/test_design_ui_macros.py`, `App/tests/test_design_shared_macros.py` | edit (F, G) |
| `App/tests/test_design_no_bang.py` | create |
| `docs/design/MASTER.md` | edit (H) |

No other file may change.

## 4. Steps

1. Templates, from the repo root:

```
python3 - <<'EOF'
import pathlib
def patch(path, pairs):
    p = pathlib.Path(path); s = p.read_text(encoding="utf-8")
    for old, new in pairs:
        assert s.count(old) == 1, (path, old[:70], s.count(old)); s = s.replace(old, new)
    p.write_text(s, encoding="utf-8")
patch("App/app/templates/_ui.html", [
 ('overdue prefixes "!" and a border.', 'overdue adds a border (the word says late; no "!").'),
 ("{% if overdue %}! {% endif %}{{ label }}", "{{ label }}"),
])
patch("App/app/templates/_components.html", [
 ("{% if tone == 'red' %}! {% endif %}", ""),
 ("{% if stone == 'red' %}! {% endif %}", ""),
 ("{% if cell.level == 'overdue' %}! {% endif %}", ""),
])
d = pathlib.Path("App/app/templates/dashboard.html"); s = d.read_text(encoding="utf-8")
head = "  {% call ui_section(t('dashboard.section.needs_action', count=counts.attention),"
i = s.index(head); assert s.count(head) == 1
j = s.index("  {% endcall %}", i) + len("  {% endcall %}")
s = s[:i] + "  {% if rows %}\n" + s[i:j] + "\n  {% endif %}" + s[j:]
d.write_text(s, encoding="utf-8")
print("ok")
EOF
```

   Expected: `ok`. Then `grep -c '! {% endif %}' App/app/templates/_ui.html App/app/templates/_components.html` expected `0` for both.

2. CSS. In `App/app/static/host2.css` replace anchor E with `.host-workspace .ui-empty { text-align: center; padding: var(--space-8) var(--space-4); color: var(--ink-2); }` and append to the end of the file:

```
/* 0155: compact empty-state title on phone */
@media (max-width: 1023px) { .host-workspace .ui-empty h2 { font-size: var(--size-16); } }
```

   Command: `python3 scripts/design_lint.py 2>&1 | tail -3`. Expected: OK.

3. MASTER (anchor H): `overdue adds "!".` → `overdue adds a coral border.`; `` `overdue=true` prefixes "!" and uses`` → `` `overdue=true` uses``; `overdue has "!";` → `overdue has a coral border, no "!";`. Command: `grep -c '"!"' docs/design/MASTER.md`. Expected: `1` (the line-349 wording).

4. Tests. F → `    assert "ui-badge-overdue\">Late" in _r('{{ ui_badge("action", "Late", true) }}')`. G: change `("action", "red", "! ")` to `("action", "red", "")`. Create `App/tests/test_design_no_bang.py`:

```python
"""0155: no "!" prefix on any badge template; one empty state on an empty dashboard."""
from pathlib import Path

T = Path(__file__).resolve().parents[1] / "app" / "templates"


def test_no_bang_prefix_in_badge_macros():
    for name in ("_ui.html", "_components.html"):
        assert "! {% endif %}" not in (T / name).read_text(encoding="utf-8"), name


def test_needs_action_section_is_guarded_by_rows():
    text = (T / "dashboard.html").read_text(encoding="utf-8")
    assert "{% if rows %}\n  {% call ui_section(t('dashboard.section.needs_action'" in text
```

5. Version key: `grep -rn "/static/host2.css?v=" App/app/templates` (expect only base.html, key `20261019-0154`); change it to `20261019-0155`. Then `cd App && .venv/bin/python tests/test_static_versions.py --write && .venv/bin/python -m pytest tests/test_static_versions.py -q 2>&1 | tail -3`. Expected: passed.

6. Tests: `cd App && .venv/bin/python -m pytest tests/test_design_no_bang.py tests/test_design_ui_macros.py tests/test_design_shared_macros.py tests/test_dashboard_empty.py tests/test_design_dashboard*.py tests/test_design_lint.py -q --tb=short 2>&1 | tail -15`. Expected: passed. Then grep the other tests for the old prefix: `grep -rln '">! \|"! overdue\|>! ' App/tests | head`; if a listed test asserts the "!" on a badge, it fails now: run it, and if it fails only because of the "!" change that one assertion (drop the "! ") and list it in the report as a deviation. Browser: `cd App && UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome .venv/bin/python -m pytest tests/test_dashboard_phone_browser.py tests/test_host_quiet_dashboard_browser.py tests/test_shell_lane_browser.py -q -rs --tb=short 2>&1 | tail -10`. Expected: passed, 0 skipped.

7. Commit: `git add App/app/templates/_ui.html App/app/templates/_components.html App/app/templates/dashboard.html App/app/static/host2.css App/app/templates/base.html App/tests docs/design/MASTER.md docs/tasks/0155-* && git commit -m "0155 step 7: no ! on badges, one empty state on the dashboard"`.

## 5. Do not touch

Badge kinds and colours, routes, copy keys; other briefs' files in docs/tasks; hard rules 1, 3, 8.

## 6. Commands

Steps 1 to 6 as written.

## 7. Acceptance

- [ ] No "!" prefix rendered by any badge macro; overdue border kept.
- [ ] Empty dashboard shows one empty state; host2.css key `20261019-0155`.
- [ ] Step 6 passes, 0 skipped.

## 8. Stop and ask

An anchor not found, a count differs, a test fails twice, a file outside section 3, or 25 tool calls: stop and write the report.

## 9. Report

`docs/tasks/0155-report.md`, 600 tokens at most, `Status: review`.
