# 0037 report: taken door-code period

## Files changed

- `App/app/ttlock.py` — `-1026`/`-3007` kinds, `keyboardPwd/add` allowlist, `add_custom_code`, window-aware `find_code_by_name`
- `App/app/door_codes.py` — period-taken issue path, custom codes, move replaces create+add (no change), guest view omits 24h for custom
- `App/app/mail_notify.py` — skip first-use when empty; support CC on `period_taken` and `moved_not_deleted`
- `App/app/host_i18n.py` — new host mail strings (en/cs); updated `cancelled_deleted` body
- `App/app/templates/guest/stay.html` — conditional first-use paragraph
- `App/tests/test_ttlock.py`, `App/tests/test_door_codes_safeguards.py` — coverage per brief §4 step 11
- `docs/context/known-issues.md` — removed K-D01
- `docs/tasks/0037-door-code-taken-period.md` — Status review, §7 ticked

## Commands (last 5 lines each)

Targeted pytest:

```
  /workspace/App/.venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
120 passed, 1 warning in 2.04s
```

Full pytest:

```
  /workspace/App/tests/test_ubyport_sample_pdf.py:152: DeprecationWarning: Image.Image.getdata is deprecated and will be removed in Pillow 14 (2027-10-15). Use get_flattened_data instead.
    grey_pixels = sum(1 for px in crop.getdata() if px < 235)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
2989 passed, 2 skipped, 7 warnings in 325.44s (0:05:25)
```

Context lint:

```
WARN  App/app/door_codes.py is named by open briefs 0037-door-code-taken-period.md, 0038-custom-code-revoke-until-end.md; say which goes first
WARN  App/tests/test_door_codes_safeguards.py is named by open briefs 0037-door-code-taken-period.md, 0038-custom-code-revoke-until-end.md; say which goes first
next free: task 0039 | migration 0008
context lint: OK
```

## §7 acceptance

- [x] Guest save on `-1026`: no `add`, `last_error` `period_taken:-1026`, one `period_taken` host notice
- [x] Worker `add` → `code_kind` `custom`, no first-use on view/mail
- [x] `-2012` immediate fail; gateway retries then `failed` with support CC
- [x] `find_code_by_name` window match
- [x] Moves use `create_period_code` only; permission on move does not call `add`
- [x] Move delete failure → `moved_not_deleted`
- [x] No `keyboardPwd/change` in `door_codes.py`
- [x] `ttlock.py` logs path/priority/errcode only
- [x] K-D01 removed
- [x] Full pytest and context lint OK

## Deviations

- `test_a_cancelled_stay_does_not_get_the_mail` calls `issue(..., allow_gateway=True)` directly so cancellation/revoke in `reconcile` does not clear the stored PIN; behaviour under test matches the brief (skip guest mail when stay no longer active).

## Accepted limits (review follow-up)

- **Move + gateway:** If a date change hits `-1026` then `add` fails on a busy/offline gateway, `_handle_moves` retries every 15 minutes with no cap. The guest still has the previous code until replace succeeds (K-D02).
- **Move + permission:** A `-2018` (or reauth/config/disabled) on replace sets `last_error` and sends `failed`; later reconciles skip that stay even after TTLock access is restored. Brief 0037 chose this; host must fix access and adjust dates or codes in TTLock (K-D03).

## Questions

None.

## Owner steps

Same as brief § Owner steps (merge on green, deploy staging, hand-add/archive/register cycle with gateway online, optional security re-check, normal stay still shows 24h sentence).
