# 1170-cont-1 report

Status: review

## 1. Files changed (`git diff --stat fdb7876`)

```
App/app/subprocessors_i18n.py                |  24 ++-
App/tests/test_legal_contents.py             |  11 +-
docs/privacy/ROPA.md                         |   2 +-
docs/tasks/1170-cont-1.md                    | 301 +++++++++++++++++++++++++++
docs/tasks/1170-hetzner-subprocessor-ropa.md |   4 +-
5 files changed, 331 insertions(+), 11 deletions(-)
```

`docs/tasks/1170-cont-1.md` is the brief itself (already on the branch); this step changed only its `Status:` line. The report commit adds `docs/tasks/1170-cont-1-report.md`.

## 2. Commands (last 5 lines)

Steps 1 to 4 each have their own commit (38b2eb2, 3e21abf, 89397a4, 7b22f7f). Their grep checks printed `2`, `0`, `10` (step 1), `3`, `0` (step 3), `1` (step 4).

Test (from `App/`):

```
....................................................................     [100%]
68 passed in 3.88s
```

Result: 68 passed, 0 failed, 0 skipped (`-rs` added, no skip lines).

Lint (repo root, `python3 scripts/context_lint.py 2>&1 | tail -5`):

```
WARN  6 commit(s) touched App/ after the last status.md update. Orchestrator: update docs/context/status.md at review.
next free: task 1171 | migration 0046
context lint: OK
```

Dash check on added lines: no output.

## 3. Section 7 ticked

- [x] Version 1.3 count 2
- [x] 4 October 2026 / 4. října 2026 count 2
- [x] "outside the EU" / "mimo EU" count 0; ROPA "no transfer outside the EU" count 0
- [x] `grep -c Hetzner docs/privacy/ROPA.md` = 3
- [x] "before this PR merges" count 1
- [x] §6 tests pass, including `test_the_register_lists_hetzner_as_conditional_recovery_host`
- [x] diff stat lists only §3 files

## 4. Deviations

None to the edits. Steps 1 to 4 were applied in fewer tool calls (batched), each with its own commit. The pytest command has `-rs` added.

## 5. Questions

None.

## 6. Owner steps left

1. Sign the Hetzner DPA (Art. 28 GDPR) before this PR merges.
2. Lawyer and owner sign-off. The PR stays a draft; only the owner marks it ready.
