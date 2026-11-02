# 0814 report: remove the founder plan

Status: review

## Files changed
28 files vs base 47a5dbe (see `git diff --stat 47a5dbe..HEAD`). Code under App/app, App/scripts, App/tests, go/internal/billing, docs/ENVIRONMENT.md, docs/context/status.md. No migration added or changed. `retention.py` changed in its comment only (plus the same line's comment).

## Commands (last lines)
- §6 grep: only `App/app/retention.py:413` (expected) and `go/internal/billing/snapshot_test.go:28` (see Deviations 2).
- `pytest` core, invoices, order, self_service: `59 passed in 3.15s`
- `pytest` tests/test_billing_admin.py: `8 passed in 2.23s`
- `go vet ./internal/billing/`: no output (clean)
- `go test ./internal/billing/`: `ok ... 0.013s` (snapshot test needs Postgres, not run here)
- `scripts/context_lint.py`: `context lint: OK`
- Fixture regen: `fixtures written: 578` (560 quote + 18 monthly)

## Acceptance (§7)
- [x] grep shows only the retention line (plus the snapshot_test column, Deviation 2)
- [x] Billing tests pass; go test passes
- [x] Terms §15 EN and CS end at the 30-day notice sentence
- [x] No migration file added or changed

## Deviations
1. Step 3 was first committed without deleting `founder_offer` (my edit helper re-read the file). Fixed in a second commit with the same message `0814 step 3`.
2. `snapshot_test.go` still names the `founder` column in its billing_account INSERT, with value 0, because §4 step 8 says `0, 0, 0, 0, 0`. Reviewer may prefer dropping the column from that row.
3. `quote_test.go`: removed the bool founder argument from three direct `Quote(...)` calls (not named in §3 by line). The case count assert changed 1120 to 560, since the fixture product lost one factor of 2.
4. `test_billing_order.py`: removed `monkeypatch.setattr(config, "FOUNDER_SLOTS", 10_000)` in `test_cenik_uses_the_billing_price_list`. The brief did not name it; without the removal the test raises AttributeError.
5. Commit trailer: used `Co-Authored-By: Claude Haiku 5.5` (the attribution in this session names Haiku), not Opus 5.5 as the launch message said.

## Not verified
- `tests/test_0412_pricing_browser.py` SKIPPED: `playwright` is not installed in App/.venv. AGENTS rule 7 requires 0 skipped browser tests and a 390 px screenshot for template and CSS changes (`billing_plan.html`, `landing.css`). Not run; not in §6.

## Questions
- Run the browser test and 390 px screenshot on a venv with playwright, or accept without it?

## Owner steps left
1. Before deploy: on the server run `psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM billing_account WHERE founder = 1;"` (expect 0). If not 0, do not deploy.
2. Merge the PR, deploy as usual.
3. Optional: remove `UBYHOST_FOUNDER_SLOTS` from the server `.env` if set.

## Orchestrator review (2026-11-02)

- Diff reviewed: placeholder counts in `place`, analytics and Go snapshot INSERT match.
- Browser tests run with the preinstalled Chromium: `test_0412_pricing_browser.py`, `test_0416_plan_page_browser.py`, `test_0414_billing_banner_browser.py`: 12 passed, 0 skipped.
- No screenshot: the only visible change is the removed founder line, which no account could show.
