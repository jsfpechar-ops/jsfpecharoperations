# 0070 report

Status: review | Branch: `task/0070-door-code-host-mails` | PR: #376

## 1. Files changed

```
 App/app/host_i18n.py                    |  26 +-
 App/app/mail_notify.py                  |  38 ++-
 App/tests/test_door_codes_safeguards.py |  43 ++-
 docs/tasks/0070-*.md                    | brief + report
```

Implementation matches §3. Brief imported as instructed.

## 2. Commands

**grep** (expect 4): `4`

**Focused door-code tests after CI fix:**

```
19 passed, 1 warning in 1.03s
```

**CI (#376, commit 06783f1):** failed once on leftover `"keeps trying" not in body`. Flipped that assert to match the delayed mail; also assert `"will not try again" not in body`.

**context_lint:** OK (status.md WARN for orchestrator).

## 3. Acceptance (§7)

- [x] The grep gives 4.
- [x] Both new tests and the door-code test files pass.
- [ ] Full suite: CI re-run after the assert flip decides.
- [x] Diff limited to §3 files (plus brief/report).

## 4. Deviations

Brief step 5 left `"keeps trying" not in body`. CI proved that conflicts with the delayed variant. Assert flipped after the CI failure notification (not in the original brief steps).

## 5. Questions

None.

## 6. Owner steps left

1. Confirm CI green on PR #376.
2. Merge with `scripts/merge-pr-on-green.sh 376`.
