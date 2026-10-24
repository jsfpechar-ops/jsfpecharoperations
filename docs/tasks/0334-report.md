# 0334 report: Mistral as a backup provider

Status: review
Base: 5439abe | Branch: task/0334-ai-mistral-backup

## Files

- App/app/config.py: AI_PROVIDER, MISTRAL_API_KEY, MISTRAL_MODEL, per-provider price defaults (anthropic defaults unchanged)
- App/app/ai.py: enabled() per provider, _mistral_post, _plain, _call_mistral, one branch in call(), limit variable, docstring sentence
- App/tests/test_ai_mistral.py: new, 4 tests with fakes only
- docs/ENVIRONMENT.md: three rows in "Model API"
- docs/tasks/0334-ai-mistral-backup.md: base commit written into header
- docs/tasks/0334-report.md: this file

## Commands

- `cd App && .venv/bin/python -c "from app import config as c; print(c.AI_PROVIDER, c.AI_PRICE_USD_PER_MTOK)"` gives `anthropic {'input': 0.1, 'output': 0.5, 'cache_read': 0.01, 'cache_write': 0.125}`
- `.venv/bin/python -m pytest tests/test_ai_mistral.py tests/test_ai.py tests/test_migrations.py -q --tb=short -x 2>&1 | tail -15` gives `25 passed in 4.06s`
- `grep -rl 'import anthropic' app` gives `app/ai.py` only
- `python3 scripts/context_lint.py | tail -3` gives `context lint: OK`
- Staged diff secret scan: one hit, the brief's own text (line 237, the grep pattern containing `sk-|`). No hit in code.

## Section 7

- [x] No env var set: behaviour unchanged (test_ai.py passes unchanged)
- [x] UBYHOST_AI_PROVIDER=mistral sends json_schema request, records usage, raises the same AIError reasons (tested: api, json, no_text, max_tokens)
- [x] Budget and input caps apply to both providers (budget and input-cap tests). Per-key cap runs before the provider branch; not tested separately.
- [x] ENVIRONMENT.md has the three rows; lint OK; no new dependency

## Deviations

- Section 4 step 4: in App/app/ai.py the `raise AIError("input_too_large")` line has no blank line after it (the next line is `system = ...`). I inserted the three-line branch directly after the raise and added one blank line before `system = ...`.
- Section 4 step 1: anchors matched as written; no change needed.
- Commit includes the brief file, which was untracked in the worktree.
- App/.venv was not staged.

## Owner steps left

- None for this brief. Switching to Mistral is the owner steps list in the brief (key, prices, provider env var, subprocessor register).
