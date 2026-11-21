# 2000: "What needs you" stays quiet about police filing when the property has no UbyPort login

Status: todo
Depends on: none | Base commit: faa13a1fb | Branch: task/2000-needs-you-no-ubyport-quiet
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

The dashboard card "What needs you" stops showing "Police overdue", "Police report failed" and "Police report not sent" lines for stays of a property that has no UbyPort login, because UbyHost files nothing there. Guest-registration lines stay, and the single "Police details missing · Finish setup" line remains the call to action.

## 2. Context

Owner report: a host who has not finished setup sees badge "17", 5 lines and "Show 12 more" on `GET /`, with "Police overdue" lines for stays from 3 Nov (today is 21 Nov). Decision 1171 already says such a property gets no deadline alert; `needs_you` contradicts it.

**Go-first exception:** exception 3 (a wrong police-filing status on a path Python still serves). `GET /` has no Go port yet (docs/plans/go-full-move-remaining.md line 52) and `go/internal/web/hostweb/templates/dashboard.tmpl` is a stub with no needs-you logic, so there is no Go file to change now. **The Go dashboard port must carry the same rule** (no police line for a property without the three UbyPort login fields; Go copy of the rule: `go/internal/calendar/watch.go` `filesWithUbyhostSQL`).

**Follow-up for the Go dashboard port, not this brief (do not implement):** collapse many genuine overdue lines into one summary line ("N stays past the police deadline" with a button to Stays), and a lighter, dimmed calm card.

**Rule 7/10 gate:** no template or CSS change, so the browser gate and screenshots do not apply. **Rule 1:** the stay page and the Stays list still show deadlines; only the dashboard nag goes away for properties UbyHost cannot file for.

Excerpts (verbatim):

`App/app/reporting.py` (the rule, ~line 2888):

```python
# 1171: a property files through UbyHost only when it has the three UbyPort
# login fields (validation.validate_apartment). A property without them files
# no police report from UbyHost, so its stays get no deadline alert and are not
# watched by filing_watchdog. Applied with the apartment alias ``a``. The one
# place for this rule in Python; go/internal/calendar/watch.go
# filesWithUbyhostSQL is the Go copy and must match it.
FILES_WITH_UBYHOST_SQL = (
    "(COALESCE(TRIM(a.uby_idub), '') != '' "
    "AND COALESCE(TRIM(a.uby_ws_user), '') != '' "
    "AND COALESCE(TRIM(a.uby_ws_password_enc), '') != '')"
)
```

`App/app/reporting.py` in `dashboard_rows` (~lines 987-1012):

```python
        if apartment_id not in apartments_by_id:
            apartments_by_id[apartment_id] = access.apartment_for_reservation(
                reservation, owner_user_id
            )
        apartment = apartments_by_id[apartment_id]
        controls = send_controls(reservation, apartment, progress) if apartment else {}
        cell = deadline_cell(progress, check_in)
        if overview:
            if not dashboard_overview_candidate(
                reservation, progress, cell["level"], today, days_ahead
            ):
                continue
        out.append(
            {
                "reservation": reservation,
                "progress": progress,
                "controls": controls,
                "urgency": level,
                "check_in": check_in,
```

`App/app/needs_you.py` `stay_line` (~lines 60-100):

```python
    reservation = row["reservation"]
    status = row["progress"]["status"]
    if status in _FINISHED:
        return None
    stay_id = reservation["id"]
    subject = _stay_name(reservation)
    base = f"/reservations/{stay_id}?return_to=/"
    if status == "failed":
        return _line("stay", "red", subject, t("needs_you.short.failed"), t("needs_you.action.fix"), base + "#guests", stay_id=stay_id)
    if row.get("urgency") == "overdue":
        if status in _SEND:
            return _line("stay", "red", subject, t("needs_you.short.overdue"), t("needs_you.action.send"), base + "#now", stay_id=stay_id)
        return _line("stay", "red", subject, t("needs_you.short.overdue"), t("needs_you.action.open"), base, stay_id=stay_id)
    if demo.is_demo_stay(reservation):
        return None
    if status in _SEND:
        # Automatic and scheduled reporting send by themselves: on track.
        if _get(reservation, "automation_mode", "manual") != "manual":
            return None
        return _line("stay", "amber", subject, t("needs_you.short.ready"), t("needs_you.action.send"), base + "#now", stay_id=stay_id)
    arrival = validation.parse_iso_date(_get(reservation, "date_from", ""))
```

Design decisions:

- The new row key is `"files_with_ubyhost": bool`, computed in `dashboard_rows` from the apartment row with the same three-column rule. A missing key defaults to True in `needs_you`, so other callers keep current behaviour. A missing apartment (`None`) gives True (unknown: keep current behaviour).
- `urgency` is not changed; other code uses it.
- Stays that get no line are still counted in `on_track` by `build()`. That is acceptable: for a property UbyHost cannot file for, nothing police-related is pending from the host's side on the card.
- Demo stays: unchanged.
- The dashboard hides setup lines while the onboarding banner shows, so the card then reads "Nothing needs you today." This is intended.
- Tests use `_row` in `App/tests/test_needs_you_0240.py`, which builds a dict with keys `reservation`, `progress`, `urgency`; `TODAY = date(2026, 10, 22)`.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/reporting.py | edit | Add helper `_apartment_files_with_ubyhost` after `FILES_WITH_UBYHOST_SQL`; add key `files_with_ubyhost` to the row dict in `dashboard_rows` |
| App/app/needs_you.py | edit | `stay_line`: no police line when `row.get("files_with_ubyhost", True)` is false |
| App/tests/test_needs_you_0240.py | edit | Three new tests; `_row` gets an optional `files=True` argument |

No other file may change. Go-first: exception 3, Python only (see §2).

## 4. Steps

1. Anchor: `grep -nF '"urgency": level,' App/app/reporting.py` (must be in `dashboard_rows`, ~line 1004). In the `out.append({...})` dict, directly after the line `"urgency": level,` insert:

```python
                "files_with_ubyhost": _apartment_files_with_ubyhost(apartment),
```

2. Anchor: `grep -nF "filesWithUbyhostSQL is the Go copy and must match it." App/app/reporting.py`. Directly after the closing `)` of `FILES_WITH_UBYHOST_SQL` (the `)` that follows the `uby_ws_password_enc` line) insert, with two blank lines before and after as usual:

```python
def _apartment_files_with_ubyhost(apartment: Any) -> bool:
    """Python copy of FILES_WITH_UBYHOST_SQL for one apartment row (2000).

    An unknown apartment counts as filing, so callers keep their old behaviour.
    """
    if not apartment:
        return True
    return all(
        str(apartment[column] or "").strip()
        for column in ("uby_idub", "uby_ws_user", "uby_ws_password_enc")
    )
```

   `Any` is already imported in reporting.py (it is used in `Dict[int, Any]`). Check: `grep -nF "from typing import" App/app/reporting.py | tail -30`. If `Any` is absent, STOP (§8).

3. Command: `cd App && .venv/bin/python -c "import app.reporting" 2>&1 | tail -30` (no output expected). Commit `2000 step 3`.

4. Anchor: `grep -nF 'if status == "failed":' App/app/needs_you.py` (must be inside `stay_line`). Replace exactly this:

```python
    base = f"/reservations/{stay_id}?return_to=/"
    if status == "failed":
        return _line("stay", "red", subject, t("needs_you.short.failed"), t("needs_you.action.fix"), base + "#guests", stay_id=stay_id)
    if row.get("urgency") == "overdue":
```

   with:

```python
    base = f"/reservations/{stay_id}?return_to=/"
    # 2000: no UbyPort login, so UbyHost files nothing here; setup is the call to action.
    files = bool(row.get("files_with_ubyhost", True))
    if files and status == "failed":
        return _line("stay", "red", subject, t("needs_you.short.failed"), t("needs_you.action.fix"), base + "#guests", stay_id=stay_id)
    if files and row.get("urgency") == "overdue":
```

5. In the same function, replace exactly:

```python
    if status in _SEND:
        # Automatic and scheduled reporting send by themselves: on track.
```

   with:

```python
    if status in _SEND:
        if not files:
            return None
        # Automatic and scheduled reporting send by themselves: on track.
```

   Statuses `failed` and `ready`/`awaiting_verification` without login now return None from the `if status in _SEND` branch or fall through; check that a no-login `failed` stay cannot reach the guest-registration branch: `failed` is not in `_GUEST` (`("awaiting_guest", "incomplete")`), so it returns None at the end. An overdue `incomplete` or `awaiting_guest` no-login stay falls through to the guest rule below, which is correct (it shows "Guests not registered" only when arrival is today, tomorrow or past and the stay has not ended).

6. Tests. In `App/tests/test_needs_you_0240.py` replace the `_row` signature and the `"urgency": urgency,` end of its dict. Exact old text:

```python
def _row(stay_id, status, *, days=0, urgency="future", mode="manual", source="airbnb"):
```

   new text:

```python
def _row(stay_id, status, *, days=0, urgency="future", mode="manual", source="airbnb", files=True):
```

   And exact old text:

```python
        "progress": {"status": status},
        "urgency": urgency,
    }
```

   new text:

```python
        "progress": {"status": status},
        "urgency": urgency,
        "files_with_ubyhost": files,
    }
```

   Append at the end of the file (blank line before):

```python
def test_overdue_stay_without_ubyport_login_gets_no_police_line():
    """2000: UbyHost files nothing for this property, so no police nag."""
    rows = [
        _row(1, "ready", days=-18, urgency="overdue", files=False),
        _row(2, "failed", days=-18, files=False),
        _row(3, "ready", days=2, files=False),
    ]
    built = _build(rows)
    assert built["lines"] == []
    assert built["on_track"] == 3


def test_overdue_stay_with_ubyport_login_still_gets_the_red_line():
    lines = _build([_row(1, "ready", days=-18, urgency="overdue", files=True)])["lines"]
    assert lines[0]["tone"] == "red" and lines[0]["text"] == "Police overdue"
    assert lines[0]["action"] == "Review and send"


def test_stay_without_ubyport_login_still_asks_unregistered_guests():
    lines = _build([_row(1, "awaiting_guest", days=1, files=False)])["lines"]
    assert [line["text"] for line in lines] == ["Guests not registered"]
```

7. Run the §6 command. Commit `2000 step 7`.

## 5. Do not touch

- Everything under `go/`, templates, CSS, and every `App/app/` file except the two in §3.
- `urgency` values, `deadlines.py`, `FILES_WITH_UBYHOST_SQL` itself, the alert path (`check_deadlines`), the stay page and the Stays list.
- Hard rules: 1 (filing correctness), 3 (no guest data in output), 4 (no dependency), 5 (no SQL change), 11 (go-first exception 3, stated in §2).

## 6. Commands

From `App/`:

```
.venv/bin/python -m pytest tests/test_needs_you_0240.py tests/test_needs_you_dashboard_0241.py tests/test_0375_needs_you_and_open.py -q --tb=short -x 2>&1 | tail -30
```

Expected: all pass, no skips, last line like `NN passed`.

From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30` (expected: no findings).

## 7. Acceptance

- [ ] `grep -nF '"files_with_ubyhost": _apartment_files_with_ubyhost(apartment),' App/app/reporting.py` finds one line.
- [ ] `grep -nF 'row.get("files_with_ubyhost", True)' App/app/needs_you.py` finds one line.
- [ ] The three new tests exist and the §6 pytest command passes.
- [ ] `git diff --stat` lists only the three files of §3 (plus the report).
- [ ] No template, CSS or `go/` file changed (rule 7/10 gate not applicable).

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command);
- a row can reach `needs_you` without the apartment's `uby_*` columns (for example a row source other than `dashboard_rows`, or an apartment row that is not a `SELECT *` row so `apartment["uby_idub"]` raises `KeyError`). Do not guess; report it.

## 9. Report

Write `docs/tasks/2000-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `App/app/needs_you.py` `stay_line`: the `files` guard on failed, overdue and ready lines.
- `App/app/reporting.py` `_apartment_files_with_ubyhost` must match `FILES_WITH_UBYHOST_SQL` (same three columns, trimmed, empty or NULL means no login).

## Owner steps

1. Open the pull request when the report says `review`; keep it a draft until you want it live.
2. After the merge and deploy, open the dashboard of a host whose setup is unfinished: the card should say "Nothing needs you today." while the setup banner shows, with no "Police overdue" lines.
3. Open a property that has all three UbyPort login fields and an overdue stay: the red "Police overdue" line should still show.
