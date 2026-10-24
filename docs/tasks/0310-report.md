# 0310 report: ai.py, the one door to the model API

Status: review | Base commit: de76c71 | Branch: task/0310-ai-core | Executor: Haiku 5.5

## Files
- App/requirements.txt (+ `anthropic==2.3.0`), App/requirements.lock (regenerated, hashes)
- App/app/migrations/0013_ai_usage.sql (new: ai_usage, havel_stats)
- App/app/config.py (AI settings block after SIGNUP_NOTIFY_EMAIL)
- App/app/ai.py (new), App/tests/ai_fake.py (new), App/tests/test_ai.py (new)
- docs/ENVIRONMENT.md, docs/context/architecture.md, docs/context/test-map.md
- docs/context/decisions.md (6 lines moved, 1 added), docs/archive/decisions-2026.md (new)

## Commands (last lines)
- step 1 `pip index versions anthropic`: `anthropic (2.3.0)`, list contains 2.3.0
- step 1 `pip install --require-hashes -r requirements.lock`: `Requirement already satisfied: websockets==17.1 ...`; `grep -c 'anthropic=='` = 1; `import anthropic` = 2.3.0
- step 2 `test_migrations.py`: `13 passed in 1.66s`
- step 3 config check: `[] claude-haiku-5-5 10.0 0.0`
- step 4 `import app.ai`: `False`
- step 5 `test_ai.py test_migrations.py`: `21 passed in 1.71s`
- step 6 grep counts: `1`, `1`, `1`
- step 7 compaction: `moved 6 added 1`; lint: `context lint: OK`
- section 6 `test_ai test_migrations test_db_*`: `26 passed in 3.22s`

## Acceptance (section 7)
- [x] anthropic==2.3.0 in requirements.txt; lock regenerated with hashes; require-hashes install ran
- [x] only App/app/ai.py contains `import anthropic`
- [x] test_ai.py passes (21 tests with migrations)
- [x] migration applies; test_migrations.py passes (number: see Questions)
- [x] ENVIRONMENT section, architecture row, test-map row, decision line; lint OK

## Pinned and package list
anthropic 2.3.0. New top-level packages in the lock: anthropic, docstring-parser, httpcore2, httpx2, jiter, opentelemetry-api, sniffio, truststore.

## Deviations
- Lock bumps (accepted per orchestrator answer 1): fastapi 0.141.1 to 0.142.2, boto3 1.43.103 to 1.43.108, botocore 1.43.104 to 1.43.118. Header regenerated under Python 3.13 with the command from requirements.txt (old header said 3.12 and the older command).
- Migration number: the lint printed `next free: migration 0013`, not 0015, so 0013 is used. The brief reserves 0013 and 0014 for the guest plan (0291-0309). See Questions.
- decisions.md line: the plan is not on main (docs/plans/havel-support-assistant.md is missing), and the lint rejects both a markdown link and a backticked path to it. The line names the plan in plain text.
- ENVIRONMENT.md "Plans:" link points to the same missing file; the lint does not check it.
- Compaction script was run from the session scratchpad, not /tmp.
- Secret grep: the only matches are pattern words inside docs/tasks/0310-ai-core.md (the brief's own grep text). No keys.

## Questions
1. Migration number: keep 0013_ai_usage.sql (lint), or rename to 0015_ai_usage.sql to avoid the guest plan's 0013 and 0014? Recommend 0015 before merge.
2. The plan file is not on main. Should the links in ENVIRONMENT.md and the decision line point to it once it lands?

## Owner steps
1. Read the decision line in docs/context/decisions.md and the package list above.
2. In the Anthropic Console, create an API key for a workspace with a 10 USD monthly limit.
3. On Render (staging) add UBYHOST_ANTHROPIC_API_KEY. Leave UBYHOST_AI_FEATURES unset until 0313 is on staging.
