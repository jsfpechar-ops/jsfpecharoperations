# 0070 report

Status: review | Branch: `task/0070-door-code-host-mails` | PR: #376

Stopped under §8: a test failed twice.

## 1. Files changed

```
 App/app/host_i18n.py                               |  26 +-
 App/app/mail_notify.py                             |  38 ++-
 App/tests/test_door_codes_safeguards.py            |  41 ++-
 docs/tasks/0070-door-code-host-mails-plain-reasons.md | 286 +
```

Implementation matches §3. The brief file was imported and committed as instructed before the steps.

## 2. Commands

**grep** (expect 4):

```
4
```

**Focused door-code tests** (first run):

```
FAILED tests/test_door_codes_safeguards.py::test_the_host_mail_says_why_in_words_and_keeps_the_raw_reason_for_support
1 failed, 51 passed, 1 warning in 1.88s
```

**Same failing test, second run:**

```
>       assert "keeps trying" not in body
E       AssertionError: assert 'keeps trying' not in 'The guests ...this e-mail.'
FAILED ...::test_the_host_mail_says_why_in_words_and_keeps_the_raw_reason_for_support
1 failed, 1 warning in 0.34s
```

**New tests only:**

```
..                                                                       [100%]
2 passed, 1 warning in 0.33s
```

**Full suite:** not run (stopped after second failure).

**context_lint:**

```
WARN  2 commit(s) touched App/ after the last status.md update. Orchestrator: update docs/context/status.md at review.
next free: task 0071 | migration 0010
context lint: OK
```

## 3. Acceptance (§7)

- [x] The grep gives 4.
- [ ] Both new tests and the door-code test files pass. (new tests pass; one pre-existing assert in the same file fails)
- [ ] The full suite passes (not run; stopped under §8).
- [x] `git diff --stat` lists only the files in §3 (plus the brief import).

## 4. Deviations

None in the implementation steps. Steps 1–5 applied as written. Stopped before completing §6 full suite.

## 5. Questions

Step 5 replaces only the reason assert in `test_the_host_mail_says_why_in_words_and_keeps_the_raw_reason_for_support`. The next line still asserts `"keeps trying" not in body`. After step 2, a `transient:-1026` late mail uses the **delayed** variant, which intentionally says “keeps trying”. Should that leftover assert be removed (or flipped), so the suite matches the new copy?

## 6. Owner steps left

1. Decide on the leftover assert (question above); if yes, a one-line follow-up on this PR or a tiny brief.
2. Open PR #376 and check CI once green.
3. Merge with `scripts/merge-pr-on-green.sh 376`.
