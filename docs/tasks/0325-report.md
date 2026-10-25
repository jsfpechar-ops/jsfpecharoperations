# 0325 report: Havel (AI) Vietnamese copy

Status: review
Base: origin/main 37ca614 (brief base 92646d3 differs; this is the current one)

## Files changed
- App/app/host_vi_i18n.py: 83 `havel.*` keys inserted after `stay_fees.pay.add_account`. Nothing else changed.

## Steps
1. Branch: already on task/0325-havel-copy-vi (worktree); `git checkout -b` skipped as instructed. Check `grep -c '"havel.name"' App/app/host_i18n.py` = 2 (en, cs). OK.
2. Copy: committed as `0325 step 2` (0022800).
3. Parity: `83 83 [] []`. `havel.send` = "Gửi", `havel.card.nights` (n=2) = "2 đêm". No em dashes in the file.

## Tests (from App/)
`pytest tests/test_host_i18n.py tests/test_no_em_dashes.py tests/test_havel_page.py -q -rs --tb=short`
Last lines: `3 failed, 22 passed, 1 warning`. The 3 failures are the known local-only "no such table: apartment" issue when test_host_i18n.py runs alone; ignored as instructed.
Lint: `python3 scripts/context_lint.py`: `context lint: OK` (WARN lines are pre-existing shared-file notes).

## Deviations
- Base commit differs (see above); recorded the current one.
- Step 1 `git checkout -b` skipped (orchestrator instruction; worktree already on branch).
- 0313 not merged, so the optional `havel.topic.support_body` line was not added.

## Questions
- None. No PR opened, nothing pushed.
