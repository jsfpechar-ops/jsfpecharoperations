# 0623: Stripe webhook hardening and account mirror fixes

Status: todo
Depends on: 0622 (uses `payment_links.PAID_EVENTS`) | Base commit: after 0622 merged | Branch: task/0623-stripe-webhook-hardening
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Today an event is marked seen before it is handled, so a handler error makes Stripe's retry a no-op and the payment is lost; a guest paying an expired request triggers exactly that. This brief records events only after handling, lets expired or cancelled requests become paid, dispatches `checkout.session.async_payment_succeeded`, and makes the account mirror write every update and detect disabled accounts.

## 2. Context

- Owner decision 2026-11-01: Stripe gateway work approved; Haiku implements. Audit: thread "Scope Stripe extras links and host booking site".
- Stripe docs: v2 accounts still emit v1 `account.updated` (Connected accounts scope); v1 Account objects have no top-level `disabled`, the reason is `requirements.disabled_reason` (values include `rejected.fraud`, `rejected.other`, `platform_paused`, `under_review`, `listed`, `other`, `requirements.past_due`, `requirements.pending_verification`).
- 0622 added in `App/app/payment_links.py`: `PAID_EVENTS = ("checkout.session.completed", "checkout.session.async_payment_succeeded")` and `on_paid` that ignores `payment_status != "paid"`. If `grep -n PAID_EVENTS App/app/payment_links.py` finds nothing, STOP: 0622 is not merged.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/stripe_connect.py` | edit | steps 1 to 4 |
| `App/app/payment_request.py` | edit | step 5 |
| `App/tests/test_stripe_connect.py` | edit | steps 6 and 7 |
| `docs/tasks/0623-report.md` | create | report |

No other file may change.

## 4. Steps

1. In `App/app/stripe_connect.py`, replace:

```python
_REJECT_CODES = ("rejected", "listed", "fraudulent")
```

with:

```python
_REJECT_CODES = ("rejected", "listed", "fraudulent")

# disabled_reason values that mean Stripe or the platform switched the
# account off for a reason the host cannot fix in onboarding (0623).
_DISABLED_REASONS = ("platform_paused", "under_review", "listed", "other")
```

Command: `cd App && .venv/bin/python -c "import app.stripe_connect" 2>&1 | tail -30` → no output.

2. In `App/app/stripe_connect.py`, replace:

```python
    requirements = account.get("requirements") or {}
    if account.get("disabled"):
        return "disabled"
```

with:

```python
    requirements = account.get("requirements") or {}
    # v1 accounts carry no top-level "disabled"; Stripe says why an account
    # is switched off in requirements.disabled_reason (0623).
    reason = requirements.get("disabled_reason") or ""
    if reason.startswith("rejected"):
        return "rejected"
    if reason in _DISABLED_REASONS:
        return "disabled"
```

Command: `cd App && .venv/bin/python -c "import app.stripe_connect" 2>&1 | tail -30` → no output.

3. In `App/app/stripe_connect.py`, replace:

```python
def _mirror(owner_user_id: int, account: Dict[str, Any]) -> None:
    """Upsert the account state mirror; audit every state transition."""
    row = account_for_owner(owner_user_id)
    if row is None or row["stripe_account_id"] != account.get("id"):
        return
    state = _onboarding_state(account)
    requirements = account.get("requirements") or {}
    changed = db.execute_rowcount(
        "UPDATE stripe_account SET onboarding_state = ?, charges_enabled = ?,"
        " payouts_enabled = ?, requirements_json = ?, updated_at = ?"
        " WHERE owner_user_id = ? AND mode = ? AND onboarding_state != ?",
        (
            state,
            1 if account.get("charges_enabled") else 0,
            1 if account.get("payouts_enabled") else 0,
            _requirements_json(requirements),
            db.utcnow(),
            owner_user_id,
            config.STRIPE_MODE,
            state,
        ),
    )
    if changed:
        db.audit(
            "stripe_account_state",
            f"acct={account.get('id')} state={state}"
            f" charges={1 if account.get('charges_enabled') else 0}"
            f" payouts={1 if account.get('payouts_enabled') else 0}",
            owner_user_id=owner_user_id,
        )
```

with:

```python
def _mirror(owner_user_id: int, account: Dict[str, Any]) -> None:
    """Upsert the account state mirror on every call (requirements and the
    charges/payouts flags can change while the state name stays the same,
    0623); audit only real state transitions."""
    row = account_for_owner(owner_user_id)
    if row is None or row["stripe_account_id"] != account.get("id"):
        return
    state = _onboarding_state(account)
    requirements = account.get("requirements") or {}
    db.execute(
        "UPDATE stripe_account SET onboarding_state = ?, charges_enabled = ?,"
        " payouts_enabled = ?, requirements_json = ?, updated_at = ?"
        " WHERE owner_user_id = ? AND mode = ?",
        (
            state,
            1 if account.get("charges_enabled") else 0,
            1 if account.get("payouts_enabled") else 0,
            _requirements_json(requirements),
            db.utcnow(),
            owner_user_id,
            config.STRIPE_MODE,
        ),
    )
    if row["onboarding_state"] != state:
        db.audit(
            "stripe_account_state",
            f"acct={account.get('id')} state={state}"
            f" charges={1 if account.get('charges_enabled') else 0}"
            f" payouts={1 if account.get('payouts_enabled') else 0}",
            owner_user_id=owner_user_id,
        )
```

Command: `cd App && .venv/bin/python -c "import app.stripe_connect" 2>&1 | tail -30` → no output.

4. In `App/app/stripe_connect.py`, replace:

```python
def process_event(event: Dict[str, Any]) -> None:
    """Dedupe by event id, then dispatch. Only account.updated is handled in
    0428; the card/QR rail events arrive in later briefs and are recorded."""
    if not _record_event(event):
        return
    etype = event.get("type")
    if etype == "account.updated":
        mirror_by_account_id(dict(event["data"]["object"]), config.STRIPE_MODE)
    elif etype in ("payment_link.paid", "checkout.session.completed"):
        from . import payment_links
        payment_links.on_paid(event)
```

with:

```python
def process_event(event: Dict[str, Any]) -> None:
    """Skip a replay, dispatch, then record the event id (0623).

    The id is recorded only after the handler returned, so a handler that
    raises leaves the event unrecorded and Stripe's retry runs it again.
    Both handlers are idempotent (mirror upserts; on_paid skips paid rows),
    so a concurrent duplicate delivery is harmless.
    """
    if event_seen(str(event.get("id"))):
        return
    from . import payment_links

    etype = event.get("type")
    if etype == "account.updated":
        mirror_by_account_id(dict(event["data"]["object"]), config.STRIPE_MODE)
    elif etype in payment_links.PAID_EVENTS:
        payment_links.on_paid(event)
    _record_event(event)
```

Command: `cd App && .venv/bin/python -c "import app.stripe_connect" 2>&1 | tail -30` → no output.

5. In `App/app/payment_request.py`, replace:

```python
    "expired": set(),
    "cancelled": set(),
```

with:

```python
    # A guest can still pay an old link after expiry or cancel; the money
    # has arrived, so paid is the truth (0623). The host refunds if needed.
    "expired": {"paid"},
    "cancelled": {"paid"},
```

Command: `cd App && .venv/bin/python -m pytest tests/test_payment_request_model.py -q --tb=short -x 2>&1 | tail -30` → all passed.

6. In `App/tests/test_stripe_connect.py`, replace:

```python
            "disabled_reason": None,
            "errors": errors or [],
```

with:

```python
            "disabled_reason": "platform_paused" if disabled else None,
            "errors": errors or [],
```

Command: none (step 7 runs the tests).

7. In `App/tests/test_stripe_connect.py`, directly after the end of `test_process_event_records_unknown_types` (after its line `    assert rows and rows[0]["event_type"] == "checkout.session.completed"`), insert:

```python
def test_mirror_updates_requirements_when_state_unchanged(fake_stripe):
    oid = _owner_id()
    stripe_connect.create_or_get_account(oid)
    first = _account_dict(charges=False, payouts=False, due=["individual.id_number"])
    stripe_connect._mirror(oid, first)
    second = _account_dict(charges=False, payouts=False, due=["individual.dob.day"])
    stripe_connect._mirror(oid, second)
    row = stripe_connect.account_for_owner(oid)
    assert row["onboarding_state"] == "action_required"
    assert json.loads(row["requirements_json"])["currently_due"] == ["individual.dob.day"]


def test_process_event_failure_leaves_event_unrecorded(fake_stripe, monkeypatch):
    def boom(account, mode):
        raise RuntimeError("handler failed")

    monkeypatch.setattr(stripe_connect, "mirror_by_account_id", boom)
    event = _account_updated_event(_account_dict(charges=True, payouts=True, due=[]))
    event["id"] = "evt_test_fail"
    with pytest.raises(RuntimeError):
        stripe_connect.process_event(event)
    assert not stripe_connect.event_seen(event["id"])
```

Command: `cd App && .venv/bin/python -m pytest tests/test_stripe_connect.py -q --tb=short -x 2>&1 | tail -30` → all passed.

## 5. Do not touch

`App/app/payment_links.py`, routes, templates, migrations, `go/` (the Go sweep only expires rows; unchanged). Hard rules 2, 3, 5, 8 of AGENTS.md.

## 6. Commands

From `App/`:

- `.venv/bin/python -m pytest tests/test_payments_dashboard.py tests/test_payment_request_model.py tests/test_stripe_connect.py tests/test_payment_rails.py tests/test_booking_widget.py -q --tb=short -x 2>&1 | tail -30` → all passed, 0 failed.
- From repo root: `python3 scripts/context_lint.py 2>&1 | tail -30` → no errors.

## 7. Acceptance

- [ ] `grep -n "_record_event(event)" App/app/stripe_connect.py` shows it as the last line of `process_event`.
- [ ] `grep -n 'account.get("disabled")' App/app/stripe_connect.py` → nothing.
- [ ] `grep -n '"expired": {"paid"}' App/app/payment_request.py` → one line.
- [ ] The §6 test command passes.

## 8. Stop and ask

Stop and write the report if: an excerpt is not found; a test fails twice; you reach 25 tool calls or about 50k tokens (report `blocked`); a file outside §3 needs a change; a step is unclear; you need push, merge, secrets or deploy.

## 9. Report

`docs/tasks/0623-report.md` (600 tokens at most): files changed, each command with its last 5 lines, §7 ticked, deviations, questions, owner steps left. Set `Status: review`, open one PR.

## Risk list (for the reviewer)

`App/app/stripe_connect.py` (`process_event`, `_mirror`).

## Owner steps

1. Merge when CI is green (`scripts/merge-pr-on-green.sh <pr>`).
2. Stripe Dashboard (test mode) → Developers → Webhooks → your `/webhooks/stripe` endpoint. Check that "Listen to" is **Events on Connected accounts** and these events are selected: `account.updated`, `checkout.session.completed`, `checkout.session.async_payment_succeeded`. Add any missing one and save.
3. Deploy, then run the test payment from 0622's owner step 2.
