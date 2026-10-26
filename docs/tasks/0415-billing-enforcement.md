# 0415: Billing enforcement (B7): the plan sets AI limits, TTLock, calendars, read-only

Status: review
Depends on: 0411 | Base commit: the head of `claude/billing-phase1-impl` | Branch: task/0415-billing-enforcement
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Order: after 0414 (both edit nothing in common, but 0414 must merge first).

## 1. Objective

Make the app follow `billing.entitlements(owner)` (from 0411):

| Area | Rule |
|---|---|
| Havel (host assistant) | message limits × `ai_multiplier` |
| Leon (guest bot) | per-conversation cap × `ai_multiplier` |
| TTLock | `entitlements.ttlock` (Max, the TTLock add-on, trials and OG hosts) |
| Calendar import | skipped while `ical_import` is False |
| Paused account | read-only: host form posts are refused, except paying, account and export pages, and filing |

`ai_multiplier` is 0 when paused, 1 for Standard and 3 for Max.

UbyPort reporting is never gated: the sweep does not read billing, and a test pins that. While billing is off, or for an OG host with no billing row, nothing changes.

## 2. Context

The overdue and paused line on host pages comes from 0414 (`_billing_banner.html`); this brief adds no template or CSS.

**Excerpt A**, `App/app/auth.py` (lines 480–490):

```python
_ACCEPTANCE_EXEMPT_PATHS = (
    "/account/accept",
    "/account/2fa/setup",
    "/logout",
    "/terms",
    "/privacy",
    "/dpa",
    "/legal",
    "/subprocessors",
)
```

**Excerpt B**, `App/app/auth.py` (end of `require_login`):

```python
    db.set_current_actor(
        account["id"], account["username"], impersonating=impersonating
    )
    db.set_current_owner(workspace["id"] if workspace else None)
    return None
```

**Excerpt C**, `App/app/ttlock.py` (line 202):

```python
def allowed_for(owner_user_id: Optional[int]) -> bool:
    return enabled() and owner_user_id is not None
```

**Excerpt D**, `App/app/havel.py` (in `limit_state` and `remaining`):

```python
    if rate_limit.blocked("havel_week", key, config.HAVEL_WEEKLY_MESSAGES, _since_week_start(now)):
        return "limit_week"
    if rate_limit.blocked("havel_month", key, config.HAVEL_MONTHLY_MESSAGES, _since_month_start(now)):
        return "limit_month"
```
```python
    week = config.HAVEL_WEEKLY_MESSAGES - rate_limit._count("havel_week", key, _since_week_start(now))
    month = config.HAVEL_MONTHLY_MESSAGES - rate_limit._count("havel_month", key, _since_month_start(now))
```

**Excerpt E**, `App/app/leon.py` (line 169 and line 593):

```python
def door_cap(door: str) -> int:
```
```python
    elif used >= door_cap(str(chat.get("door") or "qr")):
```

**Excerpt F**, `App/app/icalsync.py` (in `sync_all`, line 972):

```python
    for feed in feeds:
        totals["feeds"] += 1
```

If any excerpt is not found verbatim, STOP (§8).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/auth.py` | edit | read-only guard in `require_login` |
| `App/app/ttlock.py` | edit | `allowed_for` asks the plan |
| `App/app/havel.py` | edit | `plan_multiplier`, scaled limits |
| `App/app/leon.py` | edit | `plan_multiplier`, scaled cap |
| `App/app/icalsync.py` | edit | `import_paused`, skip in `sync_all` |
| `App/tests/test_billing_enforcement.py` | create | copy of `docs/plans/billing-0415/test_billing_enforcement.py` |
| `docs/tasks/0415-report.md` | create | the report |

No other file may change.

## 4. Steps

### Step 1. Copy the tests

`cp docs/plans/billing-0415/test_billing_enforcement.py App/tests/test_billing_enforcement.py`

### Step 2. `auth.py`

After Excerpt A add:

```python

# 0415: what a paused (read-only) account may still post: the way back to a
# plan, the account and its safety, the data export, and UbyPort filing.
_READ_ONLY_OPEN_PREFIXES = ("/predplatne", "/logout", "/account", "/settings", "/exports")
_READ_ONLY_OPEN_PATHS = re.compile(
    r"^/(reservations/submit-ready|reservations/\d+/submit|guests/\d+/resend)$"
)
```

In Excerpt B, directly before `    db.set_current_actor(` add:

```python
    # 0415: a paused plan is read-only. An impersonating admin is not blocked.
    if (
        request.method == "POST"
        and workspace is not None
        and not impersonating
        and not request.url.path.startswith(_READ_ONLY_OPEN_PREFIXES)
        and not _READ_ONLY_OPEN_PATHS.match(request.url.path)
    ):
        from . import billing

        if billing.entitlements(int(workspace["id"])).read_only:
            return RedirectResponse("/predplatne?paused=1", status_code=303)
```

### Step 3. `ttlock.py`

Replace Excerpt C with:

```python
def allowed_for(owner_user_id: Optional[int]) -> bool:
    if not enabled() or owner_user_id is None:
        return False
    # 0415: the plan decides: Max or the TTLock add-on; trials and OG hosts keep it.
    from . import billing

    return billing.entitlements(int(owner_user_id)).ttlock
```

### Step 4. `havel.py`

Directly before `def limit_state(` add:

```python
def plan_multiplier(user_id: int) -> int:
    """0415: the plan scales the message limits: 0 paused, 1 Standard, 3 Max."""
    from . import billing

    return billing.entitlements(int(user_id)).ai_multiplier


```

In both functions of Excerpt D, add `    scale = plan_multiplier(user_id)` as the first line after `key = str(user_id)`, and replace each `config.HAVEL_WEEKLY_MESSAGES` with `config.HAVEL_WEEKLY_MESSAGES * scale` and each `config.HAVEL_MONTHLY_MESSAGES` with `config.HAVEL_MONTHLY_MESSAGES * scale` (four replacements in total).

### Step 5. `leon.py`

Directly before `def door_cap(door: str) -> int:` add:

```python
def plan_multiplier(apartment_id: int) -> int:
    """0415: the host's plan scales the cap: 0 paused, 1 Standard, 3 Max."""
    from . import billing

    row = db.query_one("SELECT owner_user_id FROM apartment WHERE id = ?", (apartment_id,))
    if not row or row["owner_user_id"] is None:
        return 1
    return billing.entitlements(int(row["owner_user_id"])).ai_multiplier


```

Replace the second line of Excerpt E with:

```python
    elif used >= door_cap(str(chat.get("door") or "qr")) * plan_multiplier(apartment_id):
```

### Step 6. `icalsync.py`

Directly before `def sync_all(` add:

```python
def import_paused(apartment_id: int, seen: Dict[int, bool]) -> bool:
    """0415: a paused plan stops calendar import; reporting goes on."""
    from . import billing

    if not billing.enabled():
        return False
    if apartment_id not in seen:
        row = db.query_one("SELECT owner_user_id FROM apartment WHERE id = ?", (apartment_id,))
        owner = row["owner_user_id"] if row else None
        seen[apartment_id] = owner is not None and not billing.entitlements(int(owner)).ical_import
    return seen[apartment_id]


```

Replace Excerpt F with:

```python
    paused: Dict[int, bool] = {}
    for feed in feeds:
        if import_paused(int(feed["apartment_id"]), paused):
            continue
        totals["feeds"] += 1
```

### Step 7. Run §6, write the report, `Status: review`, commit.

## 5. Do not touch

`reporting.py`, `submit_state.py`, `ubyport/`, `scheduler.py`, `door_codes.py`, `cleaning_codes.py`, `billing.py`, templates, CSS.

## 6. Commands

From `App/`:

1. `.venv/bin/python -m pytest tests/test_billing_enforcement.py tests/test_billing_core.py -q --tb=short -x 2>&1 | tail -30`
2. `.venv/bin/python -m pytest tests/test_ttlock.py tests/test_ttlock_host_provider.py tests/test_door_codes_safeguards.py tests/test_havel_support.py tests/test_icalsync.py -q --tb=short -x 2>&1 | tail -30`
3. `ls tests | grep -E '^test_(leon|havel)' | tail -30`, then run those files the same way.
4. `.venv/bin/python -m pytest tests/test_legal_acceptance.py tests/test_login_acceptance.py tests/test_impersonation_config.py tests/test_auth_forms_no_js.py -q --tb=short -x 2>&1 | tail -30`

From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`

## 7. Acceptance

- [ ] All commands pass.
- [ ] `git diff --stat` shows only the §3 files.
- [ ] `grep -n billing App/app/reporting.py` prints nothing.

## 8. Stop and ask

- An excerpt is not found, or a step's replacement count differs (step 4 must replace exactly four names).
- An existing test fails because it expected TTLock or Havel limits without a billing row: report it; do not edit it.
- A copied test fails twice: report the assertion and the last 30 lines.

## 9. Report

`docs/tasks/0415-report.md`: files changed, the last 5 lines of each command, §7 ticked, Deviations, Questions.

## Risk list (for the reviewer)

- While paused, door codes are not issued for new stays (spec: TTLock off when paused). Codes already on the lock stay.
- A paused host's dashboard drag-and-drop gets a redirect instead of JSON; the page shows its generic error.
