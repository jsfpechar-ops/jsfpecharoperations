# 1791: Havel and Leon run on Mistral Small (config switch, 0.05 USD caps)

Status: todo
Depends on: 0334 (merged: Mistral provider exists in Python `App/app/ai.py` and Go `go/internal/anthropic/mistral.go`) | Branch: task/1791-havel-leon-mistral-small
Executor: Haiku 5.5 | Fits one session: 15 tool calls, 30k tokens
Tier: C (config and docs only, no code change)

## 1. Objective

Owner decision (Josef, 2026-11-15): Havel and Leon use Mistral Small instead of Anthropic, with a monthly cap of 0.05 USD each. The code already supports this through env vars, so this brief only (a) lets the `ubyhost-go` container receive every env var needed, (b) documents the values, (c) records the decision and the legal gate. No Go or Python code changes. **The Mistral key is never written anywhere in the repo**: it is `UBYHOST_MISTRAL_API_KEY` in the server `.env`, added by the owner.

## 2. Files

| File | Change |
|---|---|
| deploy/lightsail/docker-compose.yml | in the `ubyhost-go` environment list (lines ~217-254, alphabetical, `NAME:` pass-through style) add `UBYHOST_AI_MONTHLY_USD_LEON:`, `UBYHOST_AI_KEY_DAILY_USD_HAVEL:`, `UBYHOST_AI_KEY_DAILY_USD_LEON:`, `UBYHOST_MISTRAL_MODEL:` (check with grep that each is missing first) |
| .env.example | next to `UBYHOST_AI_PROVIDER=` (line ~90) add commented lines for the two monthly caps and `UBYHOST_MISTRAL_MODEL`, no values that look like a key |
| docs/ENVIRONMENT.md | in "Model API" (rows near 202 and 290-295) add one short paragraph: to run Havel and Leon on Mistral Small set `UBYHOST_AI_PROVIDER=mistral`, `UBYHOST_MISTRAL_API_KEY` (secret), `UBYHOST_MISTRAL_MODEL=mistral-small-latest`, `UBYHOST_AI_MONTHLY_USD_HAVEL=0.05`, `UBYHOST_AI_MONTHLY_USD_LEON=0.05`; check mistral.ai/pricing and set `UBYHOST_AI_PRICE_*` if it differs from the defaults (0.10 in / 0.30 out per million tokens); the switch is global, one provider for all AI features, rollback = set the provider back to `anthropic` |
| docs/context/decisions.md | append one dated line (match the file's existing format: `tail -5` it first): Havel and Leon move to Mistral Small, 0.05 USD monthly caps, Anthropic stays as fallback by env only |
| docs/privacy/LEON_LEGAL.md | row 9 of the table (line ~106): append "Owner chose Mistral on 2026-11-15; the register row for Mistral AI (France) and the copy changes in rows 2, 6, 7 and 10 must land before Leon is enabled for real hosts." Do not rewrite the legal copy |
| docs/privacy/drafts/havel-ai.md | line ~128 (Mistral backup bullet): append "Decided 2026-11-15: Mistral is now the primary provider for Havel and Leon; the register must list Mistral AI instead of, or besides, Anthropic before Havel is enabled for real hosts." |

## 3. Steps

1. `git status | tail -5`, confirm branch `task/1791-havel-leon-mistral-small`.
2. Make the edits in the table, one file at a time, each with a short grep to find the exact anchor lines (never read a whole file over 350 lines).
3. Verify: `grep -rn 'mstrl_' . --exclude-dir=.git | head` must print nothing. `python3 scripts/context_lint.py 2>&1 | tail -30` passes. `docker compose -f deploy/lightsail/docker-compose.yml config -q 2>&1 | tail -5` if docker exists, otherwise skip and say so.
4. Run only: `cd go && go test ./internal/anthropic/ 2>&1 | tail -30`.
5. Commit `1791 havel leon mistral small config and docs`. Do not push; report the diff stat.

## 4. Out of scope

Rewriting privacy policy, DPA or ROPA text (lawyer review, owner decision); any code change; per-feature provider selection.
