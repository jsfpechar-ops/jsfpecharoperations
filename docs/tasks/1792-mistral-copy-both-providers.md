# 1792: name both AI providers in the live copy (Haiku brief)

Status: ready, waits for counsel to confirm the **[LR]** lines in [mistral-ai](../privacy/drafts/mistral-ai.md). Do not start before the owner says counsel confirmed.

Goal: every live text that names Anthropic as the AI provider names both Mistral AI SAS (France) and Anthropic, PBC (USA), with the exact wording in section 3 of the draft.

Files (grep `Anthropic` in each, change only AI-provider sentences): `App/app/subprocessors_i18n.py` and the Go register in `go/internal/web/public/catalog.json` (new row, version 1.4); `App/app/routes/legal.py` (DPA recipients, privacy policy transfer sentence, if it holds them); `App/app/guide_i18n.py` terms1, terms6, terms7; `App/app/host_i18n.py` and `host_vi_i18n.py` `leon_page.warn5`; the Go copies `go/internal/web/ai/{leon_i18n,havel_guide}.json`, `go/internal/web/ai/guide/i18n.json`, `go/internal/web/properties/i18n.json`, `go/internal/web/public/catalog_pages.json`. Refresh goldens only with the repo's script, never by hand.
Optional (only if the owner decides): point `MistralURL` at `https://api.eu.mistral.ai/v1/chat/completions` in `go/internal/anthropic/mistral.go` and `App/app/ai.py`.
Tests: test-map rows for i18n, legal pages and Leon; Go parity tests for `catalog*.json`.
Rule: never write "not stored" or "zero retention" for the providers.
