# 2042 report: parity guest and token pages, gate command

Status: blocked (partial: tool-call cap reached at step 5 of 10)
Executor: Haiku 5.5. Brief §8: 25 tool calls used, stop, commit, report the missing parts.

## Done

- Step 1, environment: `source scripts/e2e/parity_env.sh` ran (log `/var/tmp/parity_env.log`, empty tail). `scripts/e2e/parity_cases.py` (EXTRA_CASES present), `scripts/e2e/page_parity_visual.py`, `scripts/e2e/seed_parity_extra.py` exist.
- Step 2, `App/scripts/go_page_parity_screenshots.py`: `extra_cookies` added to `capture_png` and `run_case` (both capture calls). `cd App && .venv/bin/python -m pytest tests/test_go_page_parity_screenshots.py -q --tb=short -x`: 2 passed, 1 skipped (the skip is not explained by this change; not investigated).
- Step 3, routes read: hub `pick_stay` (guest.py:1407), claim landing (guest.py:~1612), `_owned_ids` (list of guest ids in cookie `ubyhost_owned`), `_claim_serializer` salt `ubyhost-guest-claim`, `start_claim` (claim.py:248), `token_hash` (claim.py:65).
- Step 4, `scripts/e2e/seed_parity_guest.py` written. `py_compile` ok. NOT run against parity_run. Creates 5 guest-state reservations, 2 guest rows, claim and owned cookie values, share and unsubscribe tokens; each block wrapped in try/except.

## Missing (not done)

- Step 5: `GUEST_CASES` / `PIN_CASES` not appended to `scripts/e2e/parity_cases.py`. 0 of 25 rows.
- Step 6: `scripts/e2e/page_parity_visual.py` not edited. Found a mismatch with the brief: the harness does not call `shots.run_case`; it uses its own `run_case2` and `_capture` (page_parity_visual.py:115, :161), which only add the `ubyhost_session` cookie. So the `extra_cookies` added in step 2 does not reach the harness yet. `_capture` needs an extra-cookie parameter too. `PARITY_PIN` / `audit.start_*` env wiring and `--gate` mode also not done.
- Step 7: no guest run, no PNG inspection, no verdicts.
- Step 8: `scripts/e2e/parity_gate.sh` not created. Its wiring is unproven.
- Step 9: `docs/tasks/2042-report.md` is this partial report; no verdict table, no visible causes.
- Step 10: `context_lint` not run.

## Open points for the next run

- Verify the claim cookie shape `{"<reservation_id>": token_version}` against `_claimed_claims` in guest.py before the run. Not verified.
- Verify `fill()` in page_parity_visual.py resolves `{tok}`, `{res_*}`, `{guest_*}`, `{share_token}`, `{unsub_token}`.
- Seed: confirm `reservation_claim` accepts `lang`, `provisional_until`, `guest_access_locked_at`, `declared_guests` columns (taken from claim.py UPDATEs, not from a live DB).

## Owner steps left

- None yet. The gate command is not yet in the repo.
