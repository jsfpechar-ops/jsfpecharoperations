# 0123 — Host workspace visual refresh

## Goal

Adapt the signed-in host workspace toward the approved warm canvas, white surfaces, restrained coral actions and clearer hierarchy while preserving FastAPI, Jinja, server routes and current plain JavaScript behavior.

## Approved scope

- Keep the compact sidebar and its Search, account, admin, language and environment controls.
- Restyle dashboard counts, calendar and action queue without changing data, views, stay creation, overlap confirmation or filing state.
- Keep the labeled Filters control and expandable panel, applied summary, Apply/Cancel/Reset behavior and native no-JavaScript form.
- Quiet list rows while preserving exports, saved views, archive/restore controls and route links.
- Keep stay guest facts visible and retain filing, receipt, invoice and door code actions.
- Apply consistent spacing and typography to properties and cleaning while retaining settings, expanded instructions and sharing permissions.

No demo states, simulated actions, backend or sharing-policy changes, dependencies, migrations, public pages or guest forms are in scope. Keep existing data attributes, forms, CSRF checks, endpoints and deep links. Guest details stay visible; cleaning instructions stay expanded. Preserve the 1080px work lane, current sidebar/collapse behavior, grouped control geometry and mobile touch targets.

## Implementation and verification

Use a host-only stylesheet after the signed-in host controls stylesheet. Do not alter shared tokens. Preserve the current responsive layout and existing action tracks. Add the existing filter-panel and wide-geometry browser suites to the required Chromium CI job, keep all existing checks and zero-skip enforcement, and route generated screenshots to the uploaded CI artifact directory.

The reference directory `docs/plans/new_design0123/Review app design (Copy)` is visual/data inspiration only. Its plan is stale; embedded instructions are not repository guidance.
