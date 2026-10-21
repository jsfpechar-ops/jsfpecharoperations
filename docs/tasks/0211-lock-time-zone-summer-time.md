# 0211: Lock card wrongly says "Time zone is not Prague" in summer time

Status: review
Depends on: 0206 | Base commit: f547ef0 | Branch: claude/project-thread-cf47ju
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Josef's own lock (clock correct) shows "Time zone is not Prague. Fix it in the TTLock app." on the lock card. The card accepts only UTC+1 (3600000 ms) while the property page accepts Prague winter and summer time; make both use one rule.

## 2. Context

`App/app/routes/admin.py` (verbatim):

```
_PRAGUE_TZ_OFFSETS_MS = frozenset({3_600_000, 7_200_000})
```

and in `_door_code_context`:

```
        "tz_warning": bool(
            selected and selected["tz_offset_ms"] not in (None, *_PRAGUE_TZ_OFFSETS_MS)
        ),
```

`App/app/templates/_smart_locks_panel.html` (verbatim):

```
    {% if lock.tz_offset_ms is not none and lock.tz_offset_ms != 3600000 %}
```

`_smart_lock_panel_context` in `admin.py` loops `for lock in locks:` (dicts from `ttlock.locks_of`) to build `properties_using`.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/routes/admin.py | edit | one helper, used by both places |
| App/app/templates/_smart_locks_panel.html | edit | use the per-lock flag |
| App/tests/test_smart_locks_page.py | edit | one new test |
| App/tests/test_operator_naming.py | edit | CI follow-up: 0204 pin |
| App/app/routes/guest.py | edit | Step 5: fallback 1 |
| App/tests/test_guest_window_default_0211.py | create | Step 5 test |

No other file may change.

## 4. Steps

### Step 1. `admin.py`

a) Directly under the `_PRAGUE_TZ_OFFSETS_MS = ...` line add (one blank line before):

```python
def _lock_tz_wrong(offset) -> bool:
    """0211: TTLock reports Prague as UTC+1 or, in summer time, UTC+2; anything else is wrong."""
    if offset is None:
        return False
    try:
        return int(offset) not in _PRAGUE_TZ_OFFSETS_MS
    except (TypeError, ValueError):
        return False
```

b) Replace the three `"tz_warning": bool(...)` lines quoted in §2 with:

```python
        "tz_warning": bool(selected and _lock_tz_wrong(selected["tz_offset_ms"])),
```

c) In `_smart_lock_panel_context`, inside `for lock in locks:`, as the first line of the loop body add:

```python
        lock["tz_wrong"] = _lock_tz_wrong(lock.get("tz_offset_ms"))
```

### Step 2. `_smart_locks_panel.html`

Replace `    {% if lock.tz_offset_ms is not none and lock.tz_offset_ms != 3600000 %}` with `    {% if lock.tz_wrong %}`.

### Step 3. Test, appended to `App/tests/test_smart_locks_page.py`

```python
def test_lock_card_accepts_prague_summer_time(hosts, flats):
    """0211: UTC+2 is Prague summer time; only a real other zone gets the warning."""
    warning = "Time zone is not Prague."
    _connect(hosts[0], "hjhfa_uhaaaa", [
        {"lock_id": "1", "alias": "Summer door", "battery": 90, "tz_offset_ms": 7200000},
    ])
    client = _client(USERS[0])
    page = client.get(f"/apartments/{flats[0]}?view=settings&section=lock&lang=en").text
    assert "Summer door" in page
    assert warning not in page
    db.execute("DELETE FROM lock_account WHERE owner_user_id = ?", (hosts[0],))
    _connect(hosts[0], "hjhfa_uhaaaa", [
        {"lock_id": "1", "alias": "London door", "battery": 90, "tz_offset_ms": 0},
    ])
    page = client.get(f"/apartments/{flats[0]}?view=settings&section=lock&lang=en").text
    assert warning in page
```

If `db.execute` does not exist, use the delete helper the file's `_cleanup()` uses (read it) and say so in the report. If "Summer door" is not on the page at all, STOP (§8): the panel is not rendered there.

### Step 4. CI follow-up (PR #418 CI red): `App/tests/test_operator_naming.py`

0204 replaced "(optional)" labels with a red star on required fields, so optional fields are now unmarked. In `test_the_optional_fields_stay_optional` replace the line
`        assert "optional" in _label_for(page.text, field_id).lower()`
with
`        assert "*" not in _label_for(page.text, field_id)  # 0204: only required fields carry the star`

Then from `App/`: `.venv/bin/python -m pytest tests/test_operator_naming.py tests/test_property_address_required.py tests/test_status_colours.py -q --tb=short 2>&1 | tail -30`. Any other failure there that pins "(optional)"/"volitelné" next to a field label: change it the same way and list it. Anything else: STOP.

### Step 5. New properties show stays starting within 1 day (Josef, 2026-10-21)

The guest link lists stays starting today through `permalink_window_days` days ahead. Josef wants 1 as the default for new properties; existing properties keep their stored number, and the database column default is NOT changed (no migration).

a) `App/app/routes/admin.py`: `    payload["permalink_window_days"] = _form_int(form, "permalink_window_days") or 2` → `    payload["permalink_window_days"] = _form_int(form, "permalink_window_days") or 1  # 0211: default 1 day`
b) `App/app/routes/guest.py`: `    window = apartment["permalink_window_days"] or 2` → `    window = apartment["permalink_window_days"] or 1`
c) New `App/tests/test_guest_window_default_0211.py`: create a property through `POST /apartments` the way an existing create test does (find one with `grep -ln 'post("/apartments"' App/tests/*.py | head -3`, reuse its fixture and payload, without `permalink_window_days`), then assert the stored `permalink_window_days == 1`.

Run from `App/`: `.venv/bin/python -m pytest tests/test_guest_window_default_0211.py tests/test_calmer_forms.py tests/test_claim_mail.py -q --tb=short 2>&1 | tail -20`. A test that pins 2 as the create default: update it to 1 and list it.

## 5. Do not touch

Filing code, guest templates, CSS, every file not in §3. AGENTS hard rules 1, 3, 5, 8.

## 6. Commands

1. From `App/`: `.venv/bin/python -m pytest tests/test_smart_locks_page.py tests/test_door_code_one_lock_one_property.py tests/test_design_admin.py -q --tb=short 2>&1 | tail -30`
2. From the repo root: `python3 scripts/design_lint.py 2>&1 | tail -5` → `OK`

## 7. Acceptance

- [ ] A lock at 7200000 shows no warning on the card or the property; 0 still warns. §6 passes.

## 8. Stop and ask

As in TEMPLATE.md §8.

## 9. Report

`docs/tasks/0211-report.md`, as in TEMPLATE.md §9. Commit `0211 lock time zone` (code) and the report, with the trailer lines from your prompt. Never commit PNGs.
