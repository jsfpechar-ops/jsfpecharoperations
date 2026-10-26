# 0411: Fix the host "Resend guest form link" action (PR #525 review)

Status: done
Depends on: none | Base commit: 1f8a8f6 | Branch: vibe/resend-claim-link-446f76 (PR #525, commit on it directly)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

PR #525 adds a host button that re-sends the guest form link. CI fails (`test_flash_literals`: the flash key is built at runtime), some error codes have no copy, the help tip says the old link keeps working (it does not: the token rotates), the POST route skips the demo-stay guard, and the detail view runs an unused query.

## 2. Context

- `test_flash_literals.py` reads every `_flash(request, "<literal>")` call and requires the key in EN and CS. A computed key like `"flash.error.claim_resend_" + err` is read as `flash.error.claim_resend_`, which does not exist. Keys looked up from a dict are not scanned, so the new test in step 7 checks them.
- `claim.start_claim(..., resend=True)` can return these error codes: `bad_email`, `bad_party`, `stay_gone`, `locked`, `already_claimed`, `cooldown`, `recipient_rate`, `rate`. `resend_to_verified_email` adds `not_claimed`. Only `not_claimed`, `locked`, `cooldown` and `recipient_rate` have their own copy; every other code gets the new generic `flash.error.claim_resend_failed`.
- `start_claim` writes a new `token_hash` and `token_version`, so earlier e-mailed links stop working.
- Hard rules: copy in en, cs and vi; no em dashes; light mode only; no new dependency.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/routes/admin.py | edit | error-key dict, demo guard, drop stale comment, drop unused query |
| App/app/host_i18n.py | edit | add `claim_resend_failed` (en, cs); fix `resend_help` (en, cs) |
| App/app/host_vi_i18n.py | edit | add `claim_resend_failed`; fix `resend_help` |
| App/tests/test_claim_host_resend.py | create | key-map test |

No other file may change.

## 4. Steps

1. `App/app/routes/admin.py`, find:
```python
    return render(
        request,
        "reservation_detail.html",
```
Replace with:
```python
    stay_claim = claim.ensure_row(reservation_id)
    return render(
        request,
        "reservation_detail.html",
```
Check: `grep -n 'stay_claim = claim.ensure_row(reservation_id)' App/app/routes/admin.py` prints one line.

2. Same file, find:
```python
            "stay_claim": claim.ensure_row(reservation_id),
            "claim_resend": {
                "enabled": bool(
                    mail.mail_enabled()
                    and not demo.is_demo_stay(reservation)
                    and claim.ensure_row(reservation_id)["state"] == claim.CLAIMED
                    and not claim.ensure_row(reservation_id)["guest_access_locked_at"]
                ),
                "last_sent_at": (
                    db.query_one(
                        "SELECT MAX(sent_at) AS sent_at FROM email_outbox "
                        "WHERE reservation_id = ? AND kind IN ('claim', 'claim_resend') "
                        "AND sent_at IS NOT NULL",
                        (reservation_id,),
                    )["sent_at"]
                    or ""
                ),
            },
```
Replace with:
```python
            "stay_claim": stay_claim,
            "claim_resend": {
                "enabled": bool(
                    mail.mail_enabled()
                    and not demo.is_demo_stay(reservation)
                    and stay_claim["state"] == claim.CLAIMED
                    and not stay_claim["guest_access_locked_at"]
                ),
            },
```
Check: `grep -n 'last_sent_at' App/app/routes/admin.py` prints nothing.

3. Same file, find:
```python
@router.post("/reservations/{reservation_id}/resend-claim")
```
Replace with:
```python
# The resend errors that have their own copy; any other code from start_claim
# gets the generic line, so the host never sees a raw key.
CLAIM_RESEND_ERRORS = {
    "not_claimed": "flash.error.claim_resend_not_claimed",
    "locked": "flash.error.claim_resend_locked",
    "cooldown": "flash.error.claim_resend_cooldown",
    "recipient_rate": "flash.error.claim_resend_recipient_rate",
}
CLAIM_RESEND_FAILED = "flash.error.claim_resend_failed"


@router.post("/reservations/{reservation_id}/resend-claim")
```

4. Same file, find:
```python
    # back() appends ?msg= to this path, so the #guests anchor must come after
    # the query or the browser would treat the message as part of the fragment.
    back = f"/reservations/{reservation_id}"
    if not mail.mail_enabled():
        return _back(back, err=_flash(request, "flash.error.claim_resend_mail_off"))
```
Replace with:
```python
    back = f"/reservations/{reservation_id}"
    if not mail.mail_enabled():
        return _back(back, err=_flash(request, "flash.error.claim_resend_mail_off"))
    if demo.is_demo_stay(reservation):
        return _back(back, err=_flash(request, CLAIM_RESEND_FAILED))
```

5. Same file, find:
```python
        return _back(back, err=_flash(request, "flash.error.claim_resend_" + (err or "failed")))
```
Replace with:
```python
        return _back(back, err=_flash(request, CLAIM_RESEND_ERRORS.get(err, CLAIM_RESEND_FAILED)))
```
Check: `grep -n 'claim_resend_" +' App/app/routes/admin.py` prints nothing.

6. Copy. In `App/app/host_i18n.py`:
   - EN, after the line `"flash.error.claim_resend_mail_off": "E-mail is not set up on this UbyHost, so the link cannot be sent.",` add
     `        "flash.error.claim_resend_failed": "The link could not be sent. Try again later.",`
   - CS, after the line `"flash.error.claim_resend_mail_off": "E-mail není na tomto UbyHostu nastavený, odkaz proto nelze poslat.",` add
     `        "flash.error.claim_resend_failed": "Odkaz se nepodařilo odeslat. Zkuste to později.",`
   - EN, replace `The old link keeps working; a new one arrives in the guest's inbox.` with `A new link arrives in the guest's inbox; earlier links stop working.`
   - CS, replace `Starý odkaz dál funguje; nový dorazí do schránky hosta.` with `Nový odkaz dorazí do schránky hosta; dřívější odkazy přestanou fungovat.`

   In `App/app/host_vi_i18n.py`:
   - after the line `"flash.error.claim_resend_mail_off": "Email chưa được thiết lập trên UbyHost này nên không thể gửi liên kết.",` add
     `    "flash.error.claim_resend_failed": "Không thể gửi liên kết. Thử lại sau.",`
   - replace `Liên kết cũ vẫn hoạt động; liên kết mới sẽ đến hộp thư của khách.` with `Liên kết mới sẽ đến hộp thư của khách; các liên kết trước sẽ ngừng hoạt động.`

   Check: `grep -c 'claim_resend_failed' App/app/host_i18n.py App/app/host_vi_i18n.py` prints 2 and 1; `grep -rn 'old link keeps working\|Starý odkaz dál\|Liên kết cũ vẫn' App/app` prints nothing.

7. Create `App/tests/test_claim_host_resend.py`:
```python
"""The host resend button maps every claim error to copy that exists (0411)."""
from __future__ import annotations

from app import host_i18n
from app.host_vi_i18n import STRINGS as VI
from app.routes import admin


def _keys():
    return set(admin.CLAIM_RESEND_ERRORS.values()) | {admin.CLAIM_RESEND_FAILED}


def test_every_resend_error_key_exists_in_all_host_languages():
    for key in _keys():
        assert key in host_i18n.STRINGS["en"], key
        assert key in host_i18n.STRINGS["cs"], key
        assert key in VI, key


def test_unmapped_codes_fall_back_to_the_generic_copy():
    for code in ("rate", "stay_gone", "bad_party", "bad_email", "already_claimed", "", None):
        assert admin.CLAIM_RESEND_ERRORS.get(code, admin.CLAIM_RESEND_FAILED) == (
            "flash.error.claim_resend_failed"
        )
```
If `from app.host_vi_i18n import STRINGS` fails, run `grep -n '^[A-Z_]* = {' App/app/host_vi_i18n.py | head -3` and use that dict name; record it as a deviation.

## 5. Do not touch

`App/app/claim.py`, the template, every other file. Hard rules: no em dashes, no new dependency, never push to `main`.

## 6. Commands

From `App/`:
```
.venv/bin/python -m pytest tests/test_claim_host_resend.py tests/test_flash_literals.py tests/test_host_i18n.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py tests/test_design_stay_detail.py tests/test_claim_mail.py tests/test_claim_resend_complete.py -q --tb=short -x 2>&1 | tail -30
```
Expected: all pass. From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance

- [ ] The test command above passes, 0 failed.
- [ ] `grep -n 'claim_resend_" +\|last_sent_at\|#guests anchor' App/app/routes/admin.py` prints nothing.
- [ ] `git diff --stat` lists only the four files in §3 (plus this brief and its report).

## 8. Stop and ask

Stop and write the report if an excerpt is not found, a test fails twice, you reach 25 tool calls, or a file outside §3 needs a change. Do not push; the orchestrator pushes.

## 9. Report

Write `docs/tasks/0411-report.md` (600 tokens at most), set `Status: review`, and commit everything on the current branch with message `0411: resend link fixes from the #525 review`.

## Risk list (for the reviewer)

App/app/routes/admin.py (the route and the detail dict).

## Owner steps

None; the orchestrator merges with `scripts/merge-pr-on-green.sh 525` once CI is green.
