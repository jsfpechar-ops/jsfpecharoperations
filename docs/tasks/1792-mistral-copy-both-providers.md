# 1792: name both AI providers in the live copy

Status: todo. Blocked until the owner says counsel confirmed the **[LR]** lines in [mistral-ai](../privacy/drafts/mistral-ai.md).

## 1. Objective
Every live text that names Anthropic as the AI provider names both Mistral AI SAS (France) and Anthropic, PBC (USA), using the exact wording in section 3 of the draft.

## 2. Context
[mistral-ai](../privacy/drafts/mistral-ai.md). Never write "not stored" or "zero retention" for the providers.

## 3. Files
`App/app/subprocessors_i18n.py`, Go register `go/internal/web/public/catalog.json` (new row, version 1.4), `App/app/routes/legal.py`, `App/app/guide_i18n.py` (terms1, terms6, terms7), `App/app/host_i18n.py` and `host_vi_i18n.py` (`leon_page.warn5`), `go/internal/web/ai/{leon_i18n,havel_guide}.json`, `go/internal/web/ai/guide/i18n.json`, `go/internal/web/properties/i18n.json`, `go/internal/web/public/catalog_pages.json`.

## 4. Steps
1. Grep `Anthropic` in each file; change only AI-provider sentences.
2. Add the Mistral register row (EN, CS) and bump the register version.
3. Refresh goldens only with the repo script.

## 5. Do not touch
Anything not naming the AI provider; `UBYHOST_MISTRAL_*` code (optional EU endpoint switch only if the owner decides).

## 6. Commands
Test-map rows for i18n, legal pages and Leon; Go parity tests for `catalog*.json`.

## 7. Acceptance
No live text says Anthropic alone; tests green.

## 8. Stop and ask
If a sentence is not in the draft wording.

## 9. Report
Files changed and test output tail.
