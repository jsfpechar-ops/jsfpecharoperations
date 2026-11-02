# 0834 Onboarding review fixes (follow-up to 0833)

Executor: Haiku 5.5. Alone, no subagents. Branch `claude/project-thread-mb7ww2` (PR #729). Do not push, do not merge.

Status: todo

## 1. Objective

Fix three problems the review of 0833 found, all decided by the owner:

1. The guest link mail sent on manual stay create can under-report guests to UbyPort: with a blank guest count, `claim.start_claim` stores `declared_guests = 1` and the guest is never asked. Send the mail only when the host typed a guest count, and pass that count.
2. 0833 step 2 (default 15:00 / 11:00 on new properties) silently bypasses the `times_missing` gate for TTLock door codes. Revert it completely (`booking_site.py` already falls back to 15 for the booking site).
3. The signup workspace name keeps the `+tag` of the e-mail (`jan+booking@x` gives "jan booking"). Drop everything after the first `+`.

## 2. Context

- `claim.start_claim(reservation, apartment, *, email, party_size, lang, resend=False)` returns `(ok, err, secret)`. It writes `reservation_claim.declared_guests = party_size`, and writes `reservation.declared_guests` only when `expected_guests_override` is empty.
- Other route callers wrap it in `await run_in_threadpool(lambda: claim.start_claim(...))` (see `App/app/routes/guest.py`). `run_in_threadpool` is already imported in `App/app/routes/admin.py` (line 23).
- `admin.py` has no logger today; Step 2 adds one.
- `_form_int(form, key)` in `admin.py` returns `None` for a blank or non-numeric value.
- Quick-create from the calendar posts `calendar=1` with `Accept: application/json` and gets a 201 JSON reply; the variable is `calendar_json`.

## 3. Files

| File | Change |
|---|---|
| `App/app/routes/admin.py` | Step 1 revert, Step 2 logger and claim-mail rule |
| `App/app/booking_site.py` | Step 1 remove `DEFAULT_CHECKOUT_HOUR` |
| `App/tests/test_calmer_forms.py` | Step 1 remove one test, Step 3 tests |
| `App/app/routes/signup.py` | Step 4 plus-tag |
| `App/tests/test_signup.py` | Step 4 tests |
| `docs/tasks/0833-faster-onboarding.md` | Step 5 one line |

## 4. Steps

### Step 1: revert 0833 step 2 (default hours)

1a. `App/app/routes/admin.py`. Anchor: `grep -nF '# 0833: a new property starts at the usual 15:00 / 11:00' App/app/routes/admin.py` (about line 1756). Delete exactly these 5 lines (and nothing else):

```python
    # 0833: a new property starts at the usual 15:00 / 11:00 unless the host typed hours.
    if payload.get("checkin_hour") in (None, ""):
        payload["checkin_hour"] = booking_site.DEFAULT_CHECKIN_HOUR
    if payload.get("checkout_hour") in (None, ""):
        payload["checkout_hour"] = booking_site.DEFAULT_CHECKOUT_HOUR
```

The line before stays `    payload["uby_ws_password_enc"] = db.encrypt_secret(password) if password else None` and the line after stays `    apartment_id = db.insert("apartment", payload)`.

1b. Same file, the import list. `grep -nF '    booking_site,' App/app/routes/admin.py` must show exactly one line (about line 32). Delete that one line. Then `grep -n 'booking_site' App/app/routes/admin.py | tail -30` must print nothing. If it prints anything, STOP.

1c. `App/app/booking_site.py`. Anchor: `grep -nF 'DEFAULT_CHECKOUT_HOUR = 11' App/app/booking_site.py` (about line 31). Delete that one line. Keep `DEFAULT_CHECKIN_HOUR = 15`.

1d. `App/tests/test_calmer_forms.py`. Anchor: `grep -nF 'def test_a_new_property_starts_at_15_and_11(host):' App/tests/test_calmer_forms.py` (about line 195). Delete this whole function and the two blank lines after it:

```python
def test_a_new_property_starts_at_15_and_11(host):
    operator = str(_operator_id())
    response = host.post("/apartments", data=_new_payload(legal_entity_id=operator),
                         follow_redirects=False)
    assert response.status_code == 303
    row = db.query_one(
        "SELECT checkin_hour, checkout_hour FROM apartment WHERE owner_user_id = ? ORDER BY id DESC LIMIT 1",
        (_owner_id(),),
    )
    assert (row["checkin_hour"], row["checkout_hour"]) == (15, 11)
```

1e. Check: `grep -rn 'DEFAULT_CHECKOUT_HOUR' App/app App/tests --include=*.py | tail -30` prints nothing. Commit `0834 step 1`.

### Step 2: claim mail on manual stay create only with a typed guest count

2a. `App/app/routes/admin.py`, add a logger. Anchor: `grep -nF 'import json' App/app/routes/admin.py` (line 12). Insert one new line directly after it:

```python
import logging
```

Then anchor `grep -nF 'router = APIRouter(dependencies=[Depends(security.protect_host_post)])' App/app/routes/admin.py` (about line 85). Insert directly BEFORE that line:

```python
log = logging.getLogger("ubyhost.admin")
```

Before inserting, `grep -nw 'log' App/app/routes/admin.py | tail -30` must show no existing variable or function named `log` (only the comment "activity log" around line 3119). If there is one, STOP.

2b. Same file, in `reservation_create`. Anchor: `grep -nF '# 0833: a guest e-mail typed on this explicit Create sends the same claim mail as "resend".' App/app/routes/admin.py` (about line 3405). Replace the whole block from that comment line down to and including the line `                db.audit("guest_link_sent_on_create", f"reservation={reservation_id}")`. The block you replace is exactly:

```python
    # 0833: a guest e-mail typed on this explicit Create sends the same claim mail as "resend".
    guest_addr = mail.normalise_email(_form_str(form, "guest_email"))
    if guest_addr and mail.mail_enabled():
        reservation = access.reservation(request, reservation_id)
        apartment = access.apartment(request, apartment_id)
        if reservation and apartment:
            lang = "en"
            ok, _err, _secret = claim.start_claim(
                reservation,
                apartment,
                email=guest_addr,
                party_size=_form_int(form, "expected_guests") or 1,
                lang=lang,
            )
            if ok:
                db.audit("guest_link_sent_on_create", f"reservation={reservation_id}")
```

Replace it with exactly:

```python
    # 0834: the claim mail goes out only on the full Create form, only to a valid
    # guest e-mail, and only when the host typed the guest count. That count is
    # the declared party size. A blank count would store 1 guest and the guest
    # would never be asked, so UbyPort would under-report. The calendar
    # quick-create never sends. A failed send never breaks stay creation.
    guest_addr = mail.normalise_email(_form_str(form, "guest_email"))
    party_size = _form_int(form, "expected_guests")
    if not calendar_json and guest_addr and party_size is not None and party_size >= 1 and mail.mail_enabled():
        reservation = access.reservation(request, reservation_id)
        apartment = access.apartment(request, apartment_id)
        if reservation and apartment:
            try:
                ok, _err, _secret = await run_in_threadpool(
                    lambda: claim.start_claim(
                        reservation,
                        apartment,
                        email=guest_addr,
                        party_size=party_size,
                        # The guest's language is not known at this point, so
                        # the mail is English.
                        lang="en",
                    )
                )
            except Exception:
                log.exception("claim mail on stay create failed, reservation=%s", reservation_id)
                ok = False
            if ok:
                db.audit("guest_link_sent_on_create", f"reservation={reservation_id}")
```

The lines after the block stay unchanged: `    if calendar_json:` then the `JSONResponse(...)` 201 reply, then `    return _back(f"/reservations/{reservation_id}", msg=_flash(request, "flash.reservations.created"))`.

Run the Step 3 command after Step 3; commit Steps 2 and 3 together as `0834 step 2-3` once the tests pass.

### Step 3: tests in `App/tests/test_calmer_forms.py`

3a. Anchor: `grep -nF 'def test_manual_stay_with_guest_email_sends_one_claim_mail(host, monkeypatch):' App/tests/test_calmer_forms.py`. Replace this one existing test (from its `def` line to its last line `    assert json.loads(mails[0]["payload"] or "{}").get("reply_to") == "host@example.test"`) with:

```python
def test_manual_stay_with_email_and_guest_count_sends_one_claim_mail(host, monkeypatch):
    monkeypatch.setattr(mail, "mail_enabled", lambda: True)
    monkeypatch.setattr(mail_notify, "_entity_contact_email", lambda _id: "host@example.test")
    apartment_id = _create_property_and_return_id(host)
    response = host.post("/reservations", data=_manual_stay_form(
        apartment_id, guest_email="Guest@Example.test", expected_guests="3"), follow_redirects=False)
    assert response.status_code == 303
    stay = _latest_manual_stay(apartment_id)
    mails = _claim_mails(stay["id"])
    assert len(mails) == 1
    assert mails[0]["to_email"] == "guest@example.test"
    assert json.loads(mails[0]["payload"] or "{}").get("reply_to") == "host@example.test"
    row = db.query_one("SELECT declared_guests FROM reservation_claim WHERE reservation_id = ?",
                       (stay["id"],))
    assert row["declared_guests"] == 3


def test_manual_stay_with_email_but_blank_guest_count_sends_no_claim_mail(host, monkeypatch):
    monkeypatch.setattr(mail, "mail_enabled", lambda: True)
    apartment_id = _create_property_and_return_id(host)
    response = host.post("/reservations", data=_manual_stay_form(
        apartment_id, guest_email="guest@example.test", expected_guests=""), follow_redirects=False)
    assert response.status_code == 303
    stay = _latest_manual_stay(apartment_id)
    assert stay is not None
    assert _claim_mails(stay["id"]) == []
    assert db.query_one("SELECT reservation_id FROM reservation_claim WHERE reservation_id = ?",
                        (stay["id"],)) is None


def test_manual_stay_is_created_when_start_claim_raises(host, monkeypatch):
    monkeypatch.setattr(mail, "mail_enabled", lambda: True)

    def boom(*_args, **_kwargs):
        raise RuntimeError("mail down")

    monkeypatch.setattr(claim, "start_claim", boom)
    apartment_id = _create_property_and_return_id(host)
    response = host.post("/reservations", data=_manual_stay_form(
        apartment_id, guest_email="guest@example.test", expected_guests="2"), follow_redirects=False)
    assert response.status_code == 303
    assert _latest_manual_stay(apartment_id) is not None


def test_calendar_quick_create_sends_no_claim_mail(host, monkeypatch):
    monkeypatch.setattr(mail, "mail_enabled", lambda: True)
    apartment_id = _create_property_and_return_id(host)
    response = host.post(
        "/reservations",
        data=_manual_stay_form(apartment_id, guest_email="guest@example.test",
                               expected_guests="2", calendar="1"),
        headers={"accept": "application/json"},
        follow_redirects=False,
    )
    assert response.status_code == 201
    stay = _latest_manual_stay(apartment_id)
    assert stay is not None
    assert _claim_mails(stay["id"]) == []
```

Keep `test_manual_stay_without_guest_email_sends_no_claim_mail` and `test_manual_stay_with_invalid_guest_email_is_created_without_mail` unchanged.

Command (from `App/`):
`.venv/bin/python -m pytest tests/test_calmer_forms.py tests/test_dashboard_calendar.py -q --tb=short -x 2>&1 | tail -30`

### Step 4: drop the plus-tag from the derived workspace name

4a. `App/app/routes/signup.py`, function `_workspace_from_email`. Anchor: `grep -nF 'name = re.sub(r"[.+_\-]+", " ", name)' App/app/routes/signup.py` (about line 28). The current lines are:

```python
    local, _, domain = email.partition("@")
    name = local
    name = re.sub(r"[.+_\-]+", " ", name)
```

Replace them with:

```python
    local, _, domain = email.partition("@")
    # A plus-tag (anna+airbnb@) is a mailbox filter, not part of the name.
    name = local.split("+", 1)[0]
    name = re.sub(r"[._\-]+", " ", name)
```

Leave the docstring and the two lines after (`name = " ".join(...)` and `return name or domain[...]`) unchanged.

4b. `App/tests/test_signup.py`. Anchor: `grep -nF 'def test_a_blank_workspace_is_named_from_the_email():' App/tests/test_signup.py` (about line 456). In that test change only this line:

```python
    assert _account(f"jan.novak_team-x+booking@{DOMAIN}")["display_name"] == "jan novak team x booking"
```

to:

```python
    assert _account(f"jan.novak_team-x+booking@{DOMAIN}")["display_name"] == "jan novak team x"
```

Keep the `+++@` lines (a local part that is only plus signs still falls back to the domain). Directly after that test function (after its last line `    assert _account(f"+++@{DOMAIN}")["display_name"] == DOMAIN`), add two blank lines and:

```python
def test_a_plus_tag_is_left_out_of_the_workspace_name():
    client = _client()
    _submit(client, f"anna+airbnb+extra@{DOMAIN}", workspace="")
    assert _account(f"anna+airbnb+extra@{DOMAIN}")["display_name"] == "anna"
```

Command (from `App/`):
`.venv/bin/python -m pytest tests/test_signup.py -q --tb=short -x 2>&1 | tail -30`

Commit `0834 step 4`.

### Step 5: mark 0833 as partly superseded

`docs/tasks/0833-faster-onboarding.md`. Anchor: `grep -nF 'Status: review' docs/tasks/0833-faster-onboarding.md` (line 5). Insert one new line directly after it, with no blank line between:

```
Superseded in part by 0834 (step 2 reverted)
```

Change nothing else in that file. From the repo root run `python3 scripts/context_lint.py 2>&1 | tail -30`; it must report no errors. Commit `0834 step 5`.

## 5. Do not touch

`App/app/claim.py`, `App/app/booking_site.py` beyond line 1c, `App/app/templates/`, i18n files, the property editor, `reservation_resend_claim`, the calendar JSON validation block, migrations, `docs/tasks/0833-report.md`. No new mail template, no new i18n key, no new dependency.

## 6. Commands

From `App/`:
- `.venv/bin/python -m pytest tests/test_calmer_forms.py tests/test_dashboard_calendar.py -q --tb=short -x 2>&1 | tail -30`
- `.venv/bin/python -m pytest tests/test_signup.py -q --tb=short -x 2>&1 | tail -30`

From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`

No template or CSS changes, so no browser tests and no screenshots.

## 7. Acceptance

- [ ] `grep -rn 'DEFAULT_CHECKOUT_HOUR' App/app App/tests --include=*.py` and `grep -n 'booking_site' App/app/routes/admin.py` both print nothing.
- [ ] `test_manual_stay_with_email_and_guest_count_sends_one_claim_mail`, `test_manual_stay_with_email_but_blank_guest_count_sends_no_claim_mail`, `test_manual_stay_is_created_when_start_claim_raises`, `test_calendar_quick_create_sends_no_claim_mail` pass.
- [ ] `test_a_blank_workspace_is_named_from_the_email` and `test_a_plus_tag_is_left_out_of_the_workspace_name` pass.
- [ ] Both pytest commands in section 6 pass with 0 failed; the lint reports no errors.

## 8. Stop and ask

- Any `grep -nF` anchor above is not found, or is found more than once where one line is expected.
- `booking_site` is still used in `admin.py` after 1a (other than the import line).
- A name `log` already exists in `admin.py`.
- `test_dashboard_calendar.py` fails after Step 2 (the calendar path must not change).
- Any test fails twice after one fix attempt.
- You think the claim mail should still go out with a blank count, or with a language other than `en`: do not change it, ask.

## 9. Report

Write `docs/tasks/0834-report.md` (600 tokens at most): files changed, each section 6 command with its last 5 lines, section 7 ticked, Deviations, Questions. Then set this brief to `Status: review`. Commits as named in each step. Do not push; the orchestrator updates PR #729.
