# 0038 report: custom code revoke until end

## Files changed

- `App/app/door_codes.py` — `_revoke_one`: custom + gateway kinds stay `revoke_pending` (1/15/60 then hourly); mail once at attempt 3; past `valid_to` → `revoke_failed`. Random codes unchanged.
- `App/tests/test_door_codes_safeguards.py` — `test_a_custom_code_delete_keeps_trying`, `test_a_custom_code_delete_stops_after_the_end`
- `docs/tasks/0038-custom-code-revoke-until-end.md` — Status review, §7 ticked

## Commands (last 5 lines each)

Targeted pytest (`test_door_codes_safeguards.py` + `test_door_code_handover.py`):

```
  /workspace/App/.venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
33 passed, 1 warning in 1.17s
```

Full pytest:

```
  /workspace/App/tests/test_ubyport_sample_pdf.py:152: DeprecationWarning: Image.Image.getdata is deprecated and will be removed in Pillow 14 (2027-10-15). Use get_flattened_data instead.
    grey_pixels = sum(1 for px in crop.getdata() if px < 235)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
3000 passed, 2 skipped, 7 warnings in 328.22s (0:05:28)
```

Context lint:

```
WARN  1 commit(s) touched App/ after the last status.md update. Orchestrator: update docs/context/status.md at review.
next free: task 0040 | migration 0009
context lint: OK
```

## §7 acceptance

- [x] A cancelled custom code is retried hourly until `valid_to`, with one host mail after the third failure.
- [x] A random code's revoke is unchanged.
- [x] Full pytest and context lint pass.

## Deviations

- `test_a_custom_code_delete_stops_after_the_end` seeds `revoke_pending` with a past `valid_to`. `_handle_cancellations` only moves `issued` → `revoke_pending` when `valid_to` is still in the future, so an already-ended issued row would never enter revoke.

## Questions

None.

## Owner steps

1. Merge with `scripts/merge-pr-on-green.sh` after the tests are green. Deploy staging.
2. On a lock with a gateway: give a stay a custom code (0037 owner step 3), unplug the gateway, archive the stay. After about 80 minutes you get "delete a door code in the TTLock app". Plug the gateway back in. Within an hour, typing that code no longer opens the door.
