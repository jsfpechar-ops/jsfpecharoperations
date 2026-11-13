# 1199 report

Status: review
Done: steps 1 to 7. Left: step 8 (context lint), owner decision on token caps.

## 1. Files changed
- App/tests/test_sm_registry.py (new, 3 tests)
- docs/context/rules.md (+ `## State machines` section, 10 `##` headings)
- AGENTS.md (+1 routing row)
- docs/context/test-map.md (+1 row)
- docs/context/decisions.md (+1 line, 2026-11-13 [workflow] 1199)
- docs/tasks/1199-sm-standing-rule-and-catchall.md (Status: blocked)
- docs/tasks/1199-report.md (new)

## 2. Commands
- `cd App && .venv/bin/python -m pytest tests/test_sm_go_parity.py -q` (step 1): `14 passed`. venv created.
- `pytest tests/test_sm_registry.py -q` (step 2): `3 passed`.
- Sabotage (step 3): removed reservation.status line; failure message named `docs/context/rules.md#state-machines`. Line restored; `grep -c reservation.status` = 1; rerun `3 passed`.
- `pytest tests/test_sm_registry.py tests/test_sm_go_parity.py -q -rs` (step 8): `17 passed`, 0 skipped.
- `python3 scripts/context_lint.py` (step 8): FAIL, 3 errors (only ones caused by this change):
  - AGENTS.md: ~1525 tokens > cap 1500
  - docs/context/decisions.md: ~2221 tokens > cap 2200
  - docs/context/test-map.md: ~1229 tokens > cap 1200

## 3. Acceptance (section 7)
- [x] registry tests pass (17 with parity)
- [x] sabotage message checked, line restored
- [x] anchors grep shows AGENTS.md row and rules anchor
- [x] git status lists only section 3 files
- [ ] context lint clean (3 token-cap errors)

## 4. Deviations
- Lint errors are token caps that the new lines pushed over. Fixing them needs compaction of existing text, which the brief does not name, so stopped.
- Status set to blocked, not review (executor rule for lint failure).
- Commit trailer uses Claude Opus 5.5 as given in the owner's instruction.

## 5. Questions
- Compact AGENTS.md, decisions.md and test-map.md (see docs/context/workflow.md#compaction), or raise the caps?

## 6. Owner steps left
- Decide the compaction, then run `python3 scripts/context_lint.py` to confirm clean.

## Orchestrator follow-up (lint unblock)

- Compacted to pass the token caps: test-map wording; AGENTS.md routing merged into the Database row, executor line and close-chat line shortened, retired-executor list left to workflow.md; the expired 2026-11-09 "Owner asleep" decision moved to docs/archive/decisions-2026.md.
- `context_lint.py`: OK. `test_sm_registry.py` + `test_sm_go_parity.py`: 17 passed.
- Reviewer: the EXEMPT reasons for billing_month_snapshot, ical_feed, invoice, legal_entity, lock_account, push_outbox.last_status, guest.manual_prev_state, guide_item were partly inferred; check them.

- Renumbered 1171 -> 1172 -> 1180 -> 1199: both lower numbers were taken by parallel PRs (#958, #954). No status.md line, to avoid further conflicts.
