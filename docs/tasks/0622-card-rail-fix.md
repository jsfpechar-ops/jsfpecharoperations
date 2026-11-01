# 0622: Card rail fix: connected account in options, one payment per link

Status: in-progress
Depends on: none | Base commit: e925378 | Branch: task/0622-card-rail-fix
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Every card payment link fails today: `payment_links.create` puts `stripe_account` in the request body, so Stripe refuses it (verified 1 Nov with stripe 16.0.1: no `Stripe-Account` header is sent). This brief moves the account into `options`, limits each link to one payment, reuses the live link on resend, names the product in Czech, and only marks a request paid when Stripe says `payment_status == "paid"`.

## 2. Context

- Owner decision 2026-11-01 (thread "Scope Stripe extras links and host booking site"): Stripe gateway work approved; Haiku implements.
- stripe-python 16: `client.v1.payment_links.create(params={...}, options={"stripe_account": "acct_..."})`. `client.payment_links` is deprecated in favour of `client.v1.payment_links`.
- There is no `payment_link.paid` event. Payment finishes as `checkout.session.completed` (object has `payment_link` and `payment_status`); bank-redirect methods finish later with `checkout.session.async_payment_succeeded` (dispatch added in 0623).
- Czech reason labels already exist: `host_i18n.translate("cs", "payments.reason.cleaning")` returns `Úklid` (`App/app/host_i18n.py:3124`).
- Current excerpt to replace (`App/app/payment_links.py`, whole file, 85 lines) starts with:

```python
"""Card rail (brief 0435, payments P1.3): Stripe Payment Links per request.
```

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/payment_links.py` | replace whole file | new content in step 1 |
| `App/tests/test_payment_rails.py` | edit | steps 2 to 5 |
| `docs/tasks/0622-report.md` | create | report |

No other file may change.

## 4. Steps

1. Replace the whole content of `App/app/payment_links.py` with exactly:

```python
"""Card rail (brief 0435, payments P1.3; hardened in 0622): Stripe Payment
Links per request.

ubyhost never touches funds: the link is created on the host's connected
account (application fee 0, merchant of record = the host) and Stripe's
receipt is automatic. Every Stripe call goes through stripe_connect._api(),
so the shared monthly cap applies. The connected account goes in the request
options (the Stripe-Account header), never in params: in params Stripe reads
it as an unknown body field and refuses the call (0622). Each link accepts
exactly one completed payment and carries the request id in metadata.
Webhook events arrive at the connected-accounts endpoint (0428).
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict

from . import db, host_i18n, stripe_connect

# Checkout events that can mean "money arrived". completed fires for every
# finished checkout, but bank-redirect methods finish unpaid and settle later
# via async_payment_succeeded; only payment_status == "paid" counts.
PAID_EVENTS = ("checkout.session.completed", "checkout.session.async_payment_succeeded")


def _request_or_none(request_id: int) -> Dict[str, Any] | None:
    row = db.query_one("SELECT * FROM payment_request WHERE id = ?", (request_id,))
    return dict(row) if row else None


def product_name(row: Dict[str, Any]) -> str:
    """What the guest sees on Stripe Checkout and the receipt (Czech)."""
    reason = host_i18n.translate("cs", f"payments.reason.{row['reason']}")
    return f"{reason} (žádost č. {row['id']})"


def _existing_url(api, link_id: str, stripe_account: str) -> str | None:
    """The URL of a still-active link from an earlier send, else None."""
    link = api.v1.payment_links.retrieve(link_id, options={"stripe_account": stripe_account})
    if link.get("active"):
        return str(link["url"])
    return None


def send(request_id: int) -> str | None:
    """Create (or reuse) the Payment Link for a card-rail request.

    Returns the link URL, or None when the host's Stripe account cannot take
    payments yet (the caller shows the calm connect-first copy). A resend
    returns the same active link, so a guest can never hold two live links
    for one request.
    """
    row = _request_or_none(request_id)
    if row is None:
        return None
    if row["rail"] != "card":
        raise ValueError("card rail only")
    account = stripe_connect.account_for_owner(int(row["owner_user_id"]))
    if account is None or account["onboarding_state"] != "complete":
        return None
    stripe_account = account["stripe_account_id"]
    api = stripe_connect._api()
    if row.get("stripe_payment_link_id"):
        url = _existing_url(api, row["stripe_payment_link_id"], stripe_account)
        if url:
            return url
    link = api.v1.payment_links.create(
        params={
            "line_items": [
                {
                    "quantity": 1,
                    "price_data": {
                        "currency": "czk",
                        "unit_amount": int(row["amount_czk"]) * 100,
                        "product_data": {"name": product_name(row)},
                    },
                }
            ],
            "restrictions": {"completed_sessions": {"limit": 1}},
            "metadata": {"payment_request_id": str(row["id"])},
            "payment_intent_data": {"metadata": {"payment_request_id": str(row["id"])}},
        },
        options={"stripe_account": stripe_account},
    )
    db.execute(
        "UPDATE payment_request SET stripe_payment_link_id = ?, updated_at = ?"
        " WHERE id = ?",
        (link["id"], db.utcnow(), request_id),
    )
    db.audit(
        "payment_link_created",
        f"id={request_id} link={link['id']}",
        owner_user_id=int(row["owner_user_id"]),
    )
    return str(link["url"])


def on_paid(event: Dict[str, Any]) -> None:
    """Webhook: a checkout for one of our links finished. Flip the request
    to paid only when Stripe says the money is there."""
    obj = event.get("data", {}).get("object", {}) or {}
    if obj.get("payment_status") != "paid":
        return
    link_id = obj.get("payment_link")
    if not link_id:
        return
    row = db.query_one(
        "SELECT id, status, owner_user_id FROM payment_request"
        " WHERE stripe_payment_link_id = ?",
        (link_id,),
    )
    if row is None or row["status"] == "paid":
        return
    from . import payment_request as model

    # The webhook can beat the host's own Send click (or arrive while the row
    # is still a draft): paid is a legal jump from draft/sent/awaiting alike,
    # so walk through sent when the row has not been sent yet. Expired and
    # cancelled rows may also be paid late (0623): money received is the truth.
    if row["status"] == "draft":
        model.set_status(int(row["id"]), "sent", today=date.today())
    model.mark_paid(int(row["id"]), today=date.today(), via="stripe_webhook")
```

Command: `cd App && .venv/bin/python -c "import app.payment_links as p; print(p.PAID_EVENTS)" 2>&1 | tail -30` → prints the two event names.

2. In `App/tests/test_payment_rails.py`, replace this block (anchor `class _FakePaymentLink:`):

```python
class _FakePaymentLink:
    """Strict SDK-16 shape: params dict only."""

    def __init__(self) -> None:
        self.created: List[Dict[str, Any]] = []

    def create(self, params=None, options=None):
        assert params is not None, "payment_links.create must pass params="
        self.created.append(params)
        return {"id": "plink_test_1", "url": "https://buy.stripe.com/test_1"}


@pytest.fixture
def fake_link(monkeypatch, stripe_env):
    link = _FakePaymentLink()

    class _Client:
        payment_links = link

    monkeypatch.setattr(stripe_connect, "_client", lambda: _Client())
    return link
```

with:

```python
class _FakePaymentLink:
    """Strict SDK-16 shape: params dict, connected account in options (0622)."""

    def __init__(self) -> None:
        self.created: List[Dict[str, Any]] = []
        self.options: List[Dict[str, Any]] = []
        self.retrieved: List[str] = []
        self.active = True

    def create(self, params=None, options=None):
        assert params is not None, "payment_links.create must pass params="
        assert "stripe_account" not in params, "stripe_account belongs in options="
        assert options and options.get("stripe_account"), "connected account missing"
        self.created.append(params)
        self.options.append(options)
        return {"id": "plink_test_1", "url": "https://buy.stripe.com/test_1"}

    def retrieve(self, link_id, options=None):
        assert options and options.get("stripe_account"), "connected account missing"
        self.retrieved.append(link_id)
        return {"id": link_id, "url": "https://buy.stripe.com/test_1", "active": self.active}


@pytest.fixture
def fake_link(monkeypatch, stripe_env):
    link = _FakePaymentLink()

    class _V1:
        payment_links = link

    class _Client:
        v1 = _V1()

    monkeypatch.setattr(stripe_connect, "_client", lambda: _Client())
    return link
```

Command: `grep -n "class _V1" App/tests/test_payment_rails.py 2>&1 | tail -30` → one line.

3. In the same file, in `test_send_creates_payment_link_on_connected_account`, replace:

```python
    assert params["stripe_account"] == "acct_rails"
    row = payment_request.get(rid)
    assert row["stripe_payment_link_id"] == "plink_test_1"
```

with:

```python
    assert fake_link.options[0] == {"stripe_account": "acct_rails"}
    assert params["restrictions"] == {"completed_sessions": {"limit": 1}}
    assert params["metadata"] == {"payment_request_id": str(rid)}
    assert item["price_data"]["product_data"]["name"] == f"Úklid (žádost č. {rid})"
    row = payment_request.get(rid)
    assert row["stripe_payment_link_id"] == "plink_test_1"


def test_resend_reuses_the_active_link(owner, fake_link):
    _complete_account(owner)
    rid = _draft(owner, rail="card")
    first = payment_links.send(rid)
    second = payment_links.send(rid)
    assert first == second
    assert len(fake_link.created) == 1
    assert fake_link.retrieved == ["plink_test_1"]


def test_resend_creates_new_link_when_old_inactive(owner, fake_link):
    _complete_account(owner)
    rid = _draft(owner, rail="card")
    payment_links.send(rid)
    fake_link.active = False
    payment_links.send(rid)
    assert len(fake_link.created) == 2
```

4. In the same file, in `test_webhook_paid_flips_request`, replace:

```python
        "type": "payment_link.paid",
        "data": {"object": {"payment_link": "plink_test_1"}},
```

with:

```python
        "type": "checkout.session.completed",
        "data": {"object": {"payment_link": "plink_test_1", "payment_status": "paid"}},
```

5. In the same file, directly after the end of `test_webhook_paid_flips_request` (after its line `    assert row is not None`), insert:

```python
def test_webhook_unpaid_checkout_does_not_flip(owner, stripe_env, fake_link):
    _complete_account(owner)
    rid = _draft(owner, rail="card")
    payment_links.send(rid)
    stripe_connect.process_event({
        "id": "evt_rail_unpaid",
        "type": "checkout.session.completed",
        "data": {"object": {"payment_link": "plink_test_1", "payment_status": "unpaid"}},
    })
    assert payment_request.get(rid)["status"] == "draft"
```

Command for steps 3 to 5: `cd App && .venv/bin/python -m pytest tests/test_payment_rails.py -q --tb=short -x 2>&1 | tail -30` → all passed.

## 5. Do not touch

`App/app/stripe_connect.py`, `App/app/payment_request.py`, `App/app/routes/`, templates, migrations, `go/`. Hard rules 2, 3, 4, 8 of AGENTS.md.

## 6. Commands

From `App/`:

- `.venv/bin/python -m pytest tests/test_payments_dashboard.py tests/test_payment_request_model.py tests/test_stripe_connect.py tests/test_payment_rails.py -q --tb=short -x 2>&1 | tail -30` → all passed, 0 failed.
- From repo root: `python3 scripts/context_lint.py 2>&1 | tail -30` → no errors.

## 7. Acceptance

- [ ] `grep -n '"stripe_account":' App/app/payment_links.py` shows it only inside `options=` dicts.
- [ ] `grep -n "completed_sessions" App/app/payment_links.py` → one line.
- [ ] `grep -n "payment_link.paid" App/app/payment_links.py App/tests/test_payment_rails.py` → nothing.
- [ ] The §6 test command passes.

## 8. Stop and ask

Stop and write the report if: an excerpt is not found; a test fails twice; you reach 25 tool calls or about 50k tokens (report `blocked`); a file outside §3 needs a change; a step is unclear; you need push, merge, secrets or deploy.

## 9. Report

`docs/tasks/0622-report.md` (600 tokens at most): files changed, each command with its last 5 lines, §7 ticked, deviations, questions, owner steps left. Set `Status: review`, open one PR.

## Risk list (for the reviewer)

`App/app/payment_links.py`.

## Owner steps

1. Merge the PR when CI is green (`scripts/merge-pr-on-green.sh <pr>`).
2. After 0623 is merged too, deploy, then in Stripe test mode send one card payment request to your own email and pay it with card 4242 4242 4242 4242. The request should turn "Zaplaceno".
