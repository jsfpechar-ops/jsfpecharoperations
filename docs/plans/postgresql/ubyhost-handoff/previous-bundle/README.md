> Incomplete snapshot: PostgreSQL draft patches are unreviewed. Older bundled copies and changes.patch are stale. Start with [the current handoff](POSTGRESQL-HANDOFF.md).

# UbyHost corrections: review and delivery contract

Status: corrected plans complete locally; guest implementation blocked on mismatched source anchors; analytics readiness is stated in task 0452. No application implementation is claimed.
Baseline: 8b5317d0 (local main matched cached origin/main on 2026-10-30).

## Read this first

This folder is the portable delivery bundle. The two supplied handoffs are preserved as inputs, not current-source evidence. Application patches may be applied only against their recorded base. Read MANIFEST.md and the individual reports before execution. Do not paste a markdown plan into a Python file.

## Critical review

1. Guest navigation and legal disclosure are separate defects. Fix the navigation state contract and keep acknowledgement visible; do not change legal wording to solve disclosure structure.
2. Completion of guest registration must not imply successful police filing. Preserve the existing reporting state machine, validation and side-effect guards.
3. Creating and editing require different labels and redirect destinations. A zero-capacity new form is a capacity state, not simply another final guest.
4. Post-save progress must come from authoritative saved state. Unknown headcount, simultaneous saves and duplicate requests need evidence from the existing guards; do not invent a new mechanism without a demonstrated defect.
5. Field-purpose explanations require approved sources. Formatting instructions and errors stay visible. Missing approved wording is a named gap, not permission to improvise legal text.
6. Host UX work needs a demonstrated task failure. Do not recreate severity sorting that the producer already supplies. Preserve warning severity, recovery actions, phone navigation and no-JS forms.
7. Stylesheet consolidation is incremental, tied to affected components. A file-count target does not justify deleting working styles or postponing useful page changes.
8. Prefetch, animation and partial mutations are separate pilots. Define cache/security, reduced-motion and uncertain-result behavior before building them.
9. Billing status totals are not cash reconciliation. Current quotes are not historical MRR. Missing history is unavailable, not zero.
10. Annual normalization can produce fractional minor units. Use exact arithmetic and round at a documented display boundary, not at each account before aggregation.
11. Invoice credits, voids, replacements and cancellation effective dates must be source-verified before an extract is specified.
12. Infrastructure follows metric correctness. SQLite remains production; analytics copies still create load and operational risk. Neither free hosting nor zero risk is established.

## Brief order and independent work

A. Correct planning documents and binding UX guidance.
B. Verify current PR #583 source and prepare the smallest exact navigation/disclosure brief.
C. Implement and test B with Luna; review the complete high-risk diff.
D. Source-approved contextual help, as a separate brief with a localization matrix.
E. One demonstrated host UX improvement with before/after task evidence.
F. Verified billing contract, then one minimal read-only extraction brief.
G. Optional performance pilots and analytics infrastructure only after their own gates.

B/C do not depend on analytics infrastructure. E does not depend on global stylesheet consolidation. Infrastructure does not block useful guest fixes.

## Required guest acceptance matrix

| Scenario | Expected behavior |
|---|---|
| One guest | Final action reaches registration summary |
| Three guests, first and second | 303 directly to next empty form |
| Third guest | 303 to completed registration summary |
| Edit with people missing | Save changes returns to summary |
| Edit after completion | Save changes returns to summary |
| Unknown headcount | Neutral label; saved state determines destination |
| Zero remaining capacity | Existing server capacity guard; no surplus creation |
| Missing acknowledgement | Save rejected; checkbox and error visible |
| Legal text closed | Required acknowledgement remains visible |
| Validation failure | Permitted values and valid signature preserved |
| Next guest | Previous identity/signature/acknowledgement absent |
| Repeated/concurrent save | Existing capacity and side-effect guards preserved |
| Non-default language | Labels and redirect language persist |
| No JavaScript | Ordinary server form remains usable |

Use route behavior and a real browser. String assertions alone do not prove visibility. Required browser/geometry checks must have zero skips. Provide 390 px screenshots for every changed page and the relevant signature, next-person and completion states. Report unavailable browser tooling as a gap.

## Required analytics contract

For each measure specify grain, source columns, eligibility, effective date, currency, tax, discount policy, invoice corrections, missing-data behavior and precision. Separate issue amount, outstanding balance and paid-status amount. Cash remains unavailable without a verified allocation ledger. Specify Europe/Prague boundaries as half-open intervals.

The first extract is read-only, minimized and deterministic for a given source snapshot. No scheduler, drivers, migrations, deployment or production query. Use existing db.py helpers and a verified consistent-read mechanism. Exclude names, email, guest details and tokens. Tests use synthetic data.

Later publication requires validated generations, atomic switch, deletion/correction propagation, idempotent retries and visibly stale last-good data on failure. Recovery must restore BI configuration and permissions as well as reporting data. Migration recovery must reconcile writes and external effects after cutover.

## Exact delivery evidence

Each implementation report must include base and final SHA if committed, actual changed files, commands and exit status, failures/skips, screenshots and unresolved issues. Local files are not proof of a remote PR update or deployment. Do not mark a blocked brief todo.

The owner merges and deploys. No production credentials or real guest data belong in this public-repository bundle.

## Baseline correction discovered during execution

The supplied PR #583 commit contains the nested legal disclosure, but the executor found that current main already includes the legal partial directly and has no inner `.g-legal-text` disclosure. Task 0451 was blocked before mutation. The initial helper report established the reviewed commit structure, not the current baseline structure. A fresh exact brief must distinguish the two. No application patch, browser test result or screenshot was produced for 0451.
