# Integration: AI model APIs (Anthropic; Mistral optional)

| Item | Value | Source |
|---|---|---|
| Gateway | `App/app/ai.py` — the only module that imports the SDK (per its docstring) | `App/app/ai.py:1-10` |
| Provider | `UBYHOST_AI_PROVIDER`: `anthropic` (default) or `mistral` | `App/app/config.py:355-356` |
| Anthropic SDK | `anthropic` 2.3.0; client `timeout=20.0`, `max_retries=1` | `App/requirements.txt`, `App/app/ai.py:131` |
| Anthropic model | `UBYHOST_AI_MODEL`, default `claude-haiku-5-5` | `App/app/config.py:352` |
| Mistral | `UBYHOST_MISTRAL_API_KEY`; model default `mistral-small-latest`; `api.mistral.ai` | `App/app/config.py:358-359` |
| Auth | `UBYHOST_ANTHROPIC_API_KEY` (env) | `App/app/config.py:351` |
| Limits | `UBYHOST_AI_MAX_TOKENS` 4000; input cap 60000 tokens with hard cap | `App/app/config.py:366-371` |
| Budgets | per-feature monthly USD (`UBYHOST_AI_MONTHLY_USD_<FEATURE>`), per-key daily USD, usage ledger table (migration `0015_ai_usage.sql`) | `App/app/config.py:391-397` |
| Feature gate | `UBYHOST_AI_FEATURES` (comma list); `UBYHOST_AI_TEST_EMAILS` | `App/app/config.py:343-349` |
| Retry | `max_retries=1` in SDK; no app-level retry loop located in this pass | `App/app/ai.py` |
| Personal data | `⚠️ UNKNOWN — needs human input`: which guest or host data is sent to the model vendor and whether a DPA/subprocessor entry covers it (see [compliance](../compliance.md)) | — |

AI is used for the guest guide (translation, import) and Leon guest chat per
migrations `0013`–`0022`. The model vendor is a subprocessor — check
`App/app/subprocessors_i18n.py` (named in code; not read in this pass).

## Official references

- Official docs: Anthropic https://platform.claude.com/docs/en/api/http/beta/messages/create ; Mistral `⚠️ UNKNOWN` (see [REFERENCES](REFERENCES.md)).
