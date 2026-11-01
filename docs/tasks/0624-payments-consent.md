# 0624: One-time host consent screen before Stripe

Status: in-progress
Depends on: 0622, 0623 (merged) | Base commit: 99c2a0d8 or later main | Branch: task/0624-payments-consent
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Before a host's first trip to Stripe, show one plain-language page "Jak fungují platby" with 7 short points and a tick box; only after the tick does "Open Stripe" continue to Stripe. It protects the owner from liability and tells the host exactly how money, fees, disputes and refunds work (owner decision 2026-11-01).

## 2. Context

- Owner decisions 2026-11-01 (thread "Scope Stripe extras links and host booking site"): 0% platform fee; one-time host consent before Stripe; transparent, hand-held copy; Czech first.
- Evidence pattern: like `door_code_terms_accepted` and `leon_terms_accepted`, the acceptance is an audit row (`payments_terms_accepted`, detail `version=2026-11-01`) that retention never expires (`App/app/retention.py:197`). No schema change: `App/app/migrations/` is frozen at 0033 (`tests/test_migrations.py::test_python_runner_is_frozen`).
- No new personal data (account id, version, time only), so no retention.py field line beyond the exemption in step 2.
- Flow: the existing "Open Stripe" link (`/payments/connect/start`, opens in a new tab) now redirects a host without consent to `/payments/consent`; ticking and submitting records consent and continues to `/payments/connect/start`, which goes on to Stripe as before.
- Page follows MASTER: `host_page.html` page template, `body_kind = 'form'`, only `_ui.html` macros (`ui_check`, `ui_button`), no new classes, one primary button.
- English and Czech must carry the same keys (`tests/test_host_i18n.py::test_english_and_czech_carry_the_same_keys`). Vietnamese falls back to English.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/payments_consent.py` | create | step 1 |
| `App/app/retention.py` | edit | step 2 |
| `App/app/host_i18n.py` | edit | steps 3, 4 |
| `App/app/templates/payments_consent.html` | create | step 5 |
| `App/app/routes/payments.py` | edit | steps 6 to 8 |
| `App/app/routes/stripe_connect.py` | edit | steps 9, 10 |
| `App/tests/test_stripe_connect.py` | edit | steps 11, 12 |
| `App/tests/test_payments_consent.py` | create | step 13 |
| `docs/tasks/screenshots-0624/consent-390.png` | create | by the step 13 test |
| `docs/tasks/0624-report.md` | create | report |

No other file may change.

## 4. Steps

1. Create `App/app/payments_consent.py` with exactly:

```python
"""One-time host consent to the UbyHost payment terms before Stripe (0624).

A host sees the plain-language summary once, before the first trip to
Stripe. Bumping VERSION shows it again to every host. The evidence is an
audit row (action payments_terms_accepted, detail version=...), the same
pattern as the door-code and Leon terms; retention never expires it. Only the
account id, the version and the time are stored: no IP, no user agent.
"""
from __future__ import annotations

from . import db

VERSION = "2026-11-01"
ACTION = "payments_terms_accepted"


def accepted(owner_user_id: int) -> bool:
    """True when this host accepted the current version."""
    return db.query_one(
        "SELECT id FROM audit WHERE owner_user_id = ? AND action = ? AND detail = ?",
        (owner_user_id, ACTION, f"version={VERSION}"),
    ) is not None


def record(owner_user_id: int) -> None:
    """Store the acceptance once (a second call changes nothing)."""
    if accepted(owner_user_id):
        return
    db.audit(ACTION, f"version={VERSION}", owner_user_id=owner_user_id)
```

Command: `cd App && .venv/bin/python -c "import app.main" 2>&1 | tail -30` → no output.

2. In `App/app/retention.py`, replace:

```python
        "at < ? AND action NOT IN ('legal_accepted', 'door_code_terms_accepted', 'leon_terms_accepted') "
```

with:

```python
        "at < ? AND action NOT IN ('legal_accepted', 'door_code_terms_accepted', 'leon_terms_accepted',"
        " 'payments_terms_accepted') "
```

Command: `cd App && .venv/bin/python -c "import app.main" 2>&1 | tail -30` → no output.

3. In `App/app/host_i18n.py`, directly after the line `        "payments.connect.open_stripe": "Open Stripe",` (English block, it occurs once), insert these lines:

```python
        "payments.consent.title": "How payments work",
        "payments.consent.lead": "Guest money goes straight to you. UbyHost never holds it.",
        "payments.consent.p1": "Payments go to your own Stripe account. You are the seller. Stripe sends the money to your bank, usually within 7 days.",
        "payments.consent.p2": "UbyHost takes no commission. You pay only Stripe's fee, which Stripe takes from each payment and does not return on refunds.",
        "payments.consent.p3": "You are responsible for your accommodation. You make the contract with the guest, set the price and the cancellation terms, and handle complaints. UbyHost only provides the technology.",
        "payments.consent.p4": "Disputed payments are between you and Stripe. If a guest disputes a payment with their bank, Stripe may take it back from your account. Your booking confirmation and guest register help you prove the stay happened.",
        "payments.consent.p5": "Double bookings are refunded automatically. If another site sold the same dates, the guest gets the full amount back and you get a notice.",
        "payments.consent.p6": "Taxes and fees are yours. You declare the income, and you collect the local tourist fee from guests on site.",
        "payments.consent.p7": "Stripe checks your identity. It asks for an ID and your bank account. Only Stripe sees them; UbyHost does not store them.",
        "payments.consent.need": "You will need an ID card or passport, your bank account number and your phone. It takes about 5 minutes.",
        "payments.consent.agree": "I agree to the UbyHost payment terms above.",
        "payments.consent.stripe_link": "Stripe Connected Account Agreement",
        "payments.consent.continue": "Continue to Stripe",
        "payments.err.consent": "Tick the box to continue.",
```

4. In `App/app/host_i18n.py`, directly after the line `        "payments.connect.open_stripe": "Otevřít Stripe",` (Czech block, it occurs once), insert these lines:

```python
        "payments.consent.title": "Jak fungují platby",
        "payments.consent.lead": "Peníze od hostů jdou přímo k vám. UbyHost je nikdy nedrží.",
        "payments.consent.p1": "Platby jdou na váš vlastní účet Stripe. Vy jste prodejce. Stripe vám pošle peníze na bankovní účet, obvykle do 7 dnů.",
        "payments.consent.p2": "UbyHost si nebere žádnou provizi. Platíte jen poplatek Stripe, který Stripe strhává z každé platby a při refundaci ho nevrací.",
        "payments.consent.p3": "Za své ubytování odpovídáte vy. Smlouvu s hostem uzavíráte vy, určujete cenu i storno podmínky a řešíte reklamace. UbyHost dodává jen technologii.",
        "payments.consent.p4": "Sporné platby řešíte se Stripe. Když host platbu rozporuje u banky, Stripe ji může stáhnout z vašeho účtu. Potvrzení rezervace a evidence hostů vám pomohou prokázat, že pobyt proběhl.",
        "payments.consent.p5": "Při dvojí rezervaci vracíme hostovi vše automaticky. Když termín mezitím prodal jiný web, host dostane celou částku zpět a vy upozornění.",
        "payments.consent.p6": "Daně a poplatky jsou vaše. Příjmy přiznáváte vy a místní poplatek z pobytu vybíráte od hostů na místě.",
        "payments.consent.p7": "Stripe ověří vaši totožnost. Vyžádá si doklad a bankovní účet. Tyto údaje vidí jen Stripe, UbyHost je neukládá.",
        "payments.consent.need": "Budete potřebovat občanský průkaz nebo pas, číslo bankovního účtu a telefon. Zabere to asi 5 minut.",
        "payments.consent.agree": "Souhlasím s podmínkami plateb UbyHost uvedenými výše.",
        "payments.consent.stripe_link": "Smlouva o službách Stripe",
        "payments.consent.continue": "Pokračovat na Stripe",
        "payments.err.consent": "Pro pokračování zaškrtněte souhlas.",
```

Command: `cd App && .venv/bin/python -m pytest tests/test_host_i18n.py -k same_keys -q --tb=short -x 2>&1 | tail -30` → all passed (English and Czech carry the same keys).

5. Create `App/app/templates/payments_consent.html` with exactly:

```html
{% extends "host_page.html" %}
{% set nav = 'payments' %}
{% set how_key = 'payments' %}
{% set body_kind = 'form' %}
{% from "_ui.html" import ui_button, ui_check with context %}
{% block title %}{{ t('payments.consent.title') }}{% endblock %}
{% block primary_action %}{% endblock %}
{% block tabs %}{% endblock %}
{% block toolbar %}{% endblock %}
{% block body %}
<div class="ui-section">
  <p>{{ t('payments.consent.lead') }}</p>
  <ol>
    {% for n in range(1, 8) %}<li>{{ t('payments.consent.p' ~ n) }}</li>{% endfor %}
  </ol>
  <p>{{ t('payments.consent.need') }}</p>
  <form method="post" action="/payments/consent" class="ui-form">
    {{ ui_check('pay-consent-agree', t('payments.consent.agree'), name='agree') }}
    <p><a href="https://stripe.com/cz/legal/connect-account" target="_blank" rel="noopener">{{ t('payments.consent.stripe_link') }}</a></p>
    {{ ui_button(t('payments.consent.continue'), 'primary', type='submit') }}
  </form>
</div>
{% endblock %}
```

6. In `App/app/routes/payments.py`, replace:

```python
from fastapi.responses import Response
```

with:

```python
from fastapi.responses import RedirectResponse, Response
```

Command: none.

7. In `App/app/routes/payments.py`, replace:

```python
from .. import access, auth, config, db, host_i18n, i18n, mail, payment_links, payment_request, security, stripe_connect
```

with:

```python
from .. import access, auth, config, db, host_i18n, i18n, mail, payment_links, payment_request, payments_consent, security, stripe_connect
```

Command: none.

8. Append to the very end of `App/app/routes/payments.py` (after the last line `    return _back(f"/apartments/{apartment_id}/page", msg=_flash(request, "payments.page.saved"))`):

```python
# --- one-time payments consent (0624) ------------------------------------------


@router.get("/payments/consent")
def payments_consent_page(request: Request):
    """The plain-language summary a host accepts once before Stripe."""
    guard = auth.require_login(request)
    if guard:
        return guard
    if _off():
        return Response(status_code=404)
    return render(request, "payments_consent.html", {"nav": "payments", "how_key": "payments"})


@router.post("/payments/consent")
async def payments_consent_accept(request: Request):
    """Record the tick, then go straight on to Stripe onboarding."""
    guard = auth.require_login(request)
    if guard:
        return guard
    if _off():
        return Response(status_code=404)
    workspace = auth.workspace_user(request)
    if not workspace:
        return RedirectResponse("/", status_code=303)
    form = await request.form()
    if str(form.get("agree") or "") != "1":
        return _back("/payments/consent", err=_flash(request, "payments.err.consent"))
    payments_consent.record(int(workspace["id"]))
    return RedirectResponse("/payments/connect/start", status_code=303)
```

Command: `cd App && .venv/bin/python -c "import app.main" 2>&1 | tail -30` → no output.

9. In `App/app/routes/stripe_connect.py`, replace:

```python
from .. import auth, config, rate_limit, security, stripe_connect
```

with:

```python
from .. import auth, config, payments_consent, rate_limit, security, stripe_connect
```

Command: none.

10. In `App/app/routes/stripe_connect.py`, replace:

```python
    owner_id = _workspace(request)
    if owner_id is None:
        return RedirectResponse("/", status_code=303)
    try:
        # Deterministic https base (config.app_base_url(): the env-configured
```

with:

```python
    owner_id = _workspace(request)
    if owner_id is None:
        return RedirectResponse("/", status_code=303)
    if not payments_consent.accepted(owner_id):
        # 0624: the one-time plain-language consent comes before Stripe.
        return RedirectResponse("/payments/consent", status_code=303)
    try:
        # Deterministic https base (config.app_base_url(): the env-configured
```

Command: `cd App && .venv/bin/python -c "import app.main" 2>&1 | tail -30` → no output.

11. In `App/tests/test_stripe_connect.py`, replace:

```python
from app import auth, config, db, stripe_connect
```

with:

```python
from app import auth, config, db, payments_consent, stripe_connect
```

Command: none.

12. In `App/tests/test_stripe_connect.py`, replace:

```python
    response = login_as(client, OWNER, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    return client


def test_routes_hidden_when_mode_off
```

with:

```python
    response = login_as(client, OWNER, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    payments_consent.record(_owner_id())  # 0624: consent comes before Stripe
    return client


def test_routes_hidden_when_mode_off
```

Command: `cd App && .venv/bin/python -m pytest tests/test_stripe_connect.py -q --tb=short -x 2>&1 | tail -30` → all passed.

13. Create `App/tests/test_payments_consent.py` with exactly:

```python
"""0624: one-time host consent before Stripe onboarding."""
from __future__ import annotations

import os
import socket
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from fastapi.testclient import TestClient

from app import auth, config, db, payments_consent
from app.main import app
from tests.browser_support import chromium_launch_kwargs
from tests.conftest import login_as

OWNER = "payconsent"
SHOTS = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0624"


def _cleanup():
    row = db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))
    if not row:
        return
    oid = row["id"]
    db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM user_account WHERE id = ?", (oid,))


@pytest.fixture
def owner():
    db.init_db()
    _cleanup()
    auth.create_account(f"{OWNER}@example.test", "Consent Host", username=OWNER)
    oid = db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))["id"]
    db.insert("legal_entity", {"owner_user_id": oid, "name": "Consent s.r.o.",
                               "contact_email": f"{OWNER}@example.test",
                               "created_at": db.utcnow()})
    try:
        yield oid
    finally:
        _cleanup()


@pytest.fixture
def stripe_env(monkeypatch):
    monkeypatch.setattr(config, "STRIPE_MODE", "test")
    monkeypatch.setattr(config, "STRIPE_SECRET_KEY", "sk_test_local")


@pytest.fixture
def client(owner, stripe_env):
    client = TestClient(app)
    response = login_as(client, OWNER, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    return client


def test_connect_start_sends_a_new_host_to_consent_first(client, owner):
    response = client.get("/payments/connect/start", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/payments/consent"


def test_consent_page_lists_the_seven_points(client):
    response = client.get("/payments/consent")
    assert response.status_code == 200
    assert "How payments work" in response.text
    assert response.text.count("<li>") >= 7
    assert 'name="agree"' in response.text


def test_post_without_tick_stays_on_consent(client, owner):
    response = client.post("/payments/consent", data={}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].startswith("/payments/consent")
    assert not payments_consent.accepted(owner)


def test_post_with_tick_records_and_continues_to_stripe(client, owner):
    response = client.post("/payments/consent", data={"agree": "1"}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/payments/connect/start"
    assert payments_consent.accepted(owner)
    payments_consent.record(owner)  # idempotent
    rows = db.query(
        "SELECT id FROM audit WHERE owner_user_id = ? AND action = ?",
        (owner, payments_consent.ACTION),
    )
    assert len(rows) == 1


def test_consent_hidden_when_payments_off(client, monkeypatch):
    monkeypatch.setattr(config, "STRIPE_MODE", "off")
    assert client.get("/payments/consent").status_code == 404


# --- browser: 390 px geometry + screenshot (rule 7) ----------------------------

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_consent_page_fits_a_phone(owner, stripe_env):
    if REQUIRE_BROWSER:
        import playwright.sync_api as sync_api
    else:
        sync_api = pytest.importorskip("playwright.sync_api")
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 15
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    try:
        login = TestClient(app)
        login_as(login, OWNER, url="/login?lang=cs", follow_redirects=False)
        token = login.cookies.get(auth.SESSION_COOKIE)
        with sync_api.sync_playwright() as pw:
            browser = pw.chromium.launch(**chromium_launch_kwargs())
            context = browser.new_context(viewport={"width": 390, "height": 844})
            context.add_cookies([{"name": auth.SESSION_COOKIE, "value": token,
                                  "url": f"http://127.0.0.1:{port}"}])
            page = context.new_page()
            page.goto(f"http://127.0.0.1:{port}/payments/consent?lang=cs")
            overflow = page.evaluate(
                "document.documentElement.scrollWidth - document.documentElement.clientWidth")
            assert overflow <= 0
            SHOTS.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(SHOTS / "consent-390.png"), full_page=True)
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=5)
```

Command: `cd App && UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium .venv/bin/python -m pytest tests/test_payments_consent.py -q --tb=short -x -rs 2>&1 | tail -30` → 6 passed, 0 skipped, and `docs/tasks/screenshots-0624/consent-390.png` exists. Open the screenshot once: the seven points, the checkbox and the coral "Pokračovat na Stripe" button are visible with no text cut off.

## 5. Do not touch

`App/app/stripe_connect.py`, `App/app/payment_links.py`, `App/app/templates/payments.html`, migrations, `go/`, other templates and CSS. Hard rules 2, 3, 4, 5, 6, 7, 8 of AGENTS.md.

## 6. Commands

From `App/`:

- `.venv/bin/python -m pytest tests/test_payments_dashboard.py tests/test_payment_request_model.py tests/test_stripe_connect.py tests/test_payment_rails.py tests/test_migrations.py -q --tb=short -x 2>&1 | tail -30` → all passed.
- `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium .venv/bin/python -m pytest tests/test_payments_consent.py tests/test_design_guardrails_browser.py -q --tb=short -x -rs 2>&1 | tail -30` → all passed, 0 skipped.
- `.venv/bin/python ../scripts/design_lint.py 2>&1 | tail -15` → OK.
- From repo root: `python3 scripts/context_lint.py 2>&1 | tail -5` → context lint: OK.

## 7. Acceptance

- [ ] A host without consent who opens `/payments/connect/start` lands on `/payments/consent` (test).
- [ ] Ticking and submitting records one `payments_terms_accepted` audit row and continues to `/payments/connect/start` (test).
- [ ] `docs/tasks/screenshots-0624/consent-390.png` shows the Czech page at 390 px with no horizontal overflow.
- [ ] All §6 commands pass, 0 skipped.

## 8. Stop and ask

Stop and write the report if: an excerpt is not found; a test fails twice; you reach 25 tool calls or about 50k tokens (report `blocked`); a file outside §3 needs a change; `design_lint.py` flags the new template; a step is unclear; you need push, merge, secrets or deploy.

## 9. Report

`docs/tasks/0624-report.md` (600 tokens at most): files changed, each command with its last 5 lines, §7 ticked, deviations, questions, owner steps left. Set `Status: review`.

## Risk list (for the reviewer)

`App/app/routes/stripe_connect.py` (gate), `App/app/routes/payments.py` (new routes), `App/app/templates/payments_consent.html`.

## Owner steps

1. Merge when CI is green (`scripts/merge-pr-on-green.sh <pr>`), deploy.
2. On the Platby page click "Otevřít Stripe": you should see "Jak fungují platby" first; tick the box and continue to Stripe.
