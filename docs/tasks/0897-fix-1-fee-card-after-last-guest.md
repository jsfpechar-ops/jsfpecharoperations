# 0897-fix-1: show the stay-fee card after the last guest, including the demo stay

Status: review
Depends on: none. This brief goes first. Do not start 0897-fix-2 until this brief's report is `Status: review`.
Base: branch `cursor/guest-pay-operator-preview-237c` at `18903f8e`. Stay on this branch. Do not create a branch. Do not push. Do not open a PR.
Executor: Haiku | Report: docs/tasks/0897-fix-1-report.md

## 1. Objective

On Render the owner submits the last guest and the payment methods do not appear. Seeded browser tests insert a signed guest into a normal stay, so they never hit this. The guest card uses `charge_for_reservation`, and that query drops every stay with `source = 'demo'`. The setup-guide stay the owner opens on staging is a demo stay, so the total is 0 and `_fee_pay_panel` returns None. A real stay whose guest is liable still works. Fix the demo exclusion for the guest card only, and prove it with a form POST, not a seeded guest row.

## 2. Context

Council filings must keep excluding demo stays. `property_period` has its own SQL. Do not change that. Only the guest card opts in.

Anchor in `App/app/stay_fee.py` (verbatim):

```
    "AND COALESCE(r.source, '') != 'demo' "
    "ORDER BY COALESCE(g.stay_from, r.date_from), g.id"
)


def charge_for_reservation(apartment, reservation) -> Optional[Dict[str, Any]]:
    """Live amount for one reservation over its whole stay (guest panel and register share this)."""
    if not is_active(apartment) or not config.STAY_FEE_GUEST_PAY:
        return None
    rate = int(apartment["stay_fee_rate_czk"])
    lines: List[Dict[str, Any]] = []
    for row in db.query(_GUESTS_FOR_RES_SQL, (apartment["id"], reservation["id"])):
```

Anchor in `App/app/routes/guest.py` inside `_fee_pay_panel`:

```
    charge = stay_fee.charge_for_reservation(apartment, reservation)
```

A guest who lives in the property's municipality, a minor, or a stay over 60 nights still has a zero total. The card stays hidden in those cases. That is the law, not this bug. The new test uses an adult in Brno so the total is above zero. A second case uses Praha on a Praha property and asserts the card is absent.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/stay_fee.py` | edit | `include_demo` flag on `charge_for_reservation` only |
| `App/app/routes/guest.py` | edit | guest card passes `include_demo=True` |
| `App/tests/test_stay_fee_obec_0898.py` | edit | demo stay is empty by default and non-empty with the flag |
| `App/tests/test_stay_fee_guest_pay_0897.py` | edit | real form POST: one guest, two guests, demo stay, local resident |
| `docs/tasks/0897-fix-1-report.md` | create | report |

No other file may change.

## 4. Steps

1. In `App/app/stay_fee.py`, `grep -nF "def charge_for_reservation" App/app/stay_fee.py`. Replace the anchor in section 2 with:

```
    "{demo_filter}"
    "ORDER BY COALESCE(g.stay_from, r.date_from), g.id"
)


def charge_for_reservation(apartment, reservation, *, include_demo: bool = False) -> Optional[Dict[str, Any]]:
    """Live amount for one reservation over its whole stay.

    The guest card passes include_demo=True so the host can preview payment on
    the setup-guide stay. Council totals keep the default and still skip demo.
    """
    if not is_active(apartment) or not config.STAY_FEE_GUEST_PAY:
        return None
    rate = int(apartment["stay_fee_rate_czk"])
    lines: List[Dict[str, Any]] = []
    demo_filter = "" if include_demo else "AND COALESCE(r.source, '') != 'demo' "
    for row in db.query(_GUESTS_FOR_RES_SQL.format(demo_filter=demo_filter), (apartment["id"], reservation["id"])):
```

Leave the rest of the function unchanged. Command: `cd App && .venv/bin/python -c "import app.stay_fee" 2>&1 | tail -30` (no output). Commit `0897-fix-1 step 1`.

2. In `App/app/routes/guest.py`, `grep -nF "charge = stay_fee.charge_for_reservation" App/app/routes/guest.py`. Expect one hit. Replace that line with:

```
    charge = stay_fee.charge_for_reservation(apartment, reservation, include_demo=True)
```

Command: `cd App && .venv/bin/python -c "import app.routes.guest" 2>&1 | tail -30` (no output). Commit `0897-fix-1 step 2`.

3. In `App/tests/test_stay_fee_obec_0898.py`, find `assert stay_fee.charge_for_reservation(_apt(aid), {"id": demo})["lines"] == []` and add the next two lines immediately after it:

```
    shown = stay_fee.charge_for_reservation(_apt(aid), {"id": demo}, include_demo=True)
    assert shown["lines"] and shown["total_czk"] > 0
```

Command: `cd App && .venv/bin/python -m pytest tests/test_stay_fee_obec_0898.py::test_charge_excludes_demo_unsigned_and_respects_the_kill_switch -q --tb=short -p no:cacheprovider 2>&1 | tail -30`. Expect pass. Commit `0897-fix-1 step 3`.

4. Append the tests below to `App/tests/test_stay_fee_guest_pay_0897.py`. Add the imports next to the existing ones: `from datetime import timedelta` and `from app import claim, mail` and `from tests.conftest import complete_guest_claim` and `from tests.test_endtoend import SIGNATURE`. `login_as` is already imported from `tests.conftest`; do not import it twice.

```python
def _drop_stays(apartment_id):
    db.execute(
        "DELETE FROM reservation_claim WHERE reservation_id IN "
        "(SELECT id FROM reservation WHERE apartment_id = ?)",
        (apartment_id,),
    )
    db.execute(
        "DELETE FROM guest WHERE reservation_id IN "
        "(SELECT id FROM reservation WHERE apartment_id = ?)",
        (apartment_id,),
    )
    db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apartment_id,))


def _enable_collect(client, apartment_id):
    saved = _save(client, apartment_id, guest={
        "stay_fee_collect": "1",
        "stay_fee_guest_rails": ["qr", "iban", "revolut", "cash"],
        "stay_fee_guest_revolut_link": GOOD_LINK,
        "stay_fee_guest_cash_note": "At reception",
    })
    assert saved.status_code == 303, saved.text


def _new_stay(apartment_id, *, source=""):
    today = claim.prague_today()
    now = db.utcnow()
    return db.insert("reservation", {
        "apartment_id": apartment_id,
        "uid": f"fee-{apartment_id}-{source or 'real'}-{today.isoformat()}-{now}",
        "date_from": today.isoformat(),
        "date_to": (today + timedelta(days=3)).isoformat(),
        "status": "active",
        "source": source or None,
        "created_at": now,
        "updated_at": now,
    })


def _guest_post(client, token, rid, *, city, country, surname):
    page = client.get(f"/l/{token}/{rid}/new?lang=en")
    data = {
        "surname": surname,
        "first_name": "Jan",
        "birth_date": "1.1.1990",
        "nationality": country,
        "doc_number": "123456789",
        "res_street": "Main 1",
        "res_city": city,
        "res_country": country,
        "purpose": "10",
        "signature": SIGNATURE,
        "legal_ack": "1",
    }
    if 'name="csrf-token"' in page.text:
        data["_csrf"] = page.text.split('name="csrf-token" content="')[1].split('"')[0]
    return client.post(f"/l/{token}/{rid}/save?lang=en", data=data, follow_redirects=False)


def test_form_save_shows_payment_after_the_last_guest_and_not_before(host, monkeypatch):
    """Claim and POST the real form. One of two guests: no card. Both: card and #fee-pay."""
    client, apartment_id = host
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)
    _enable_collect(client, apartment_id)
    apt = db.query_one("SELECT permalink_token FROM apartment WHERE id = ?", (apartment_id,))
    token = apt["permalink_token"]
    rid = _new_stay(apartment_id)
    guest = TestClient(app)
    try:
        complete_guest_claim(guest, token, rid, party_size=2)
        first = _guest_post(guest, token, rid, city="Brno", country="CZE", surname="First")
        assert first.status_code == 303, first.text[:500]
        assert "#fee-pay" not in first.headers["location"]
        hub = guest.get(first.headers["location"].split("#")[0], follow_redirects=True)
        assert 'id="fee-pay"' not in hub.text
        second = _guest_post(guest, token, rid, city="Brno", country="CZE", surname="Second")
        assert second.status_code == 303, second.text[:500]
        assert "#fee-pay" in second.headers["location"]
        done = guest.get(second.headers["location"].split("#")[0], follow_redirects=True)
        assert 'id="fee-pay"' in done.text
        assert "Revolut" in done.text
    finally:
        _drop_stays(apartment_id)


def test_form_save_on_a_demo_stay_still_shows_payment(host, monkeypatch):
    client, apartment_id = host
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)
    _enable_collect(client, apartment_id)
    apt = db.query_one("SELECT permalink_token FROM apartment WHERE id = ?", (apartment_id,))
    rid = _new_stay(apartment_id, source="demo")
    db.update("reservation", rid, {"declared_guests": 1})
    try:
        saved = _guest_post(client, apt["permalink_token"], rid, city="Brno", country="CZE", surname="Demo")
        assert saved.status_code == 303, saved.text[:500]
        assert "#fee-pay" in saved.headers["location"]
        hub = client.get(saved.headers["location"].split("#")[0], follow_redirects=True)
        assert 'id="fee-pay"' in hub.text
    finally:
        _drop_stays(apartment_id)


def test_a_guest_from_the_same_municipality_sees_no_fee_card(host, monkeypatch):
    client, apartment_id = host
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)
    _enable_collect(client, apartment_id)
    apt = db.query_one("SELECT permalink_token FROM apartment WHERE id = ?", (apartment_id,))
    token = apt["permalink_token"]
    rid = _new_stay(apartment_id)
    guest = TestClient(app)
    try:
        complete_guest_claim(guest, token, rid, party_size=1)
        saved = _guest_post(guest, token, rid, city="Praha", country="CZE", surname="Local")
        assert saved.status_code == 303, saved.text[:500]
        assert "#fee-pay" not in saved.headers["location"]
        hub = guest.get(saved.headers["location"].split("#")[0], follow_redirects=True)
        assert 'id="fee-pay"' not in hub.text
        assert "Local" in hub.text or "LOCAL" in hub.text
    finally:
        _drop_stays(apartment_id)
```

`mail` is imported for the claim path the helper already uses; if the import is unused, do not add a dummy use, drop `mail` from the import. Command: `cd App && .venv/bin/python -m pytest tests/test_stay_fee_guest_pay_0897.py::test_form_save_shows_payment_after_the_last_guest_and_not_before tests/test_stay_fee_guest_pay_0897.py::test_form_save_on_a_demo_stay_still_shows_payment tests/test_stay_fee_guest_pay_0897.py::test_a_guest_from_the_same_municipality_sees_no_fee_card -q --tb=short -p no:cacheprovider 2>&1 | tail -30`. Expect 3 passed. If a POST returns 422, STOP and paste the response text (first 500 characters) into the report. Do not invent extra form fields. Commit `0897-fix-1 step 4`.

5. Write `docs/tasks/0897-fix-1-report.md` (600 tokens at most). Set this brief's `Status: review` in the same commit. Commit `0897-fix-1 step 5`. Do not push. Do not open a PR. `gh` is read-only here.

## 5. Do not touch

Guest templates, CSS, host copy, `property_period`, migrations, `docs/context/*`. No new dependency. Do not change the default of `include_demo` to True.

## 6. Commands

The commands in section 4, then from the repo root: `python3 scripts/context_lint.py 2>&1 | tail -5`.

## 7. Acceptance

- [ ] `charge_for_reservation` without the flag still returns no lines for a demo stay.
- [ ] With `include_demo=True` the same stay has a total above zero.
- [ ] A real form POST of guest 1 of 2 has no `#fee-pay`. Guest 2 redirects to `#fee-pay` and the hub HTML contains `id="fee-pay"` and `Revolut`.
- [ ] The same POST on a demo stay shows the card.
- [ ] A Czech guest whose city is Praha, on a Praha property, gets no card, and the hub still shows that guest.
- [ ] No file outside section 3 changed.

## 8. Stop and ask

An anchor in section 2 is not found verbatim. A POST returns 422 or any status other than 303. The hub for the Brno guest has no fee card after both guests are saved. A test fails a second time. `context_lint.py` prints ERROR.

## 9. Report

`docs/tasks/0897-fix-1-report.md`: files changed, each command's last 5 lines, section 7 ticked, Deviations, Questions. Owner steps: none for this brief. Render still needs the branch and `UBYHOST_STAY_FEE_GUEST_PAY=on`; say that in one sentence and do not invent click paths.

## Risk list (reviewer)

`stay_fee.charge_for_reservation` default stays demo-free. Guest card is the only caller that opts in.
