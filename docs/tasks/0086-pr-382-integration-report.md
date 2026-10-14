# PR #382: combined design merge readiness

PR: https://github.com/jsfpechar-ops/jsfpecharoperations/pull/382
Branch: claude/quirky-lamport-9svmd1

## Scope

The owner merged #389 into #382 as `4bfb4532825354f4f7dba2dd9a172da9b1eb1e4c`.
That candidate contains the approved UI from `c1ebe7d04124c805903b0bca3d757962b9dbb9fc`.
Integrate current main `7ea23223b7a6ee700fab70f3731ea9144a15613c`;
the common ancestor is `ab0a2f1e43d3162b425cdd23402925536aa59548`.

- Preserve all #389 wizard, checklist, phone, message, menu and layout changes.
- Preserve main's retry guard against adopting a cancelled stay's period PIN.
- Preserve keypad-confirmation `#` and translated validity/first-use instructions.
- Preserve staging demo isolation: demos do not issue live codes or send guest mail.
- Include main's regression tests for these production fixes.
- Resolve documentation in favor of actual 0094/0101/0102 navigation.
  Do not resurrect removed /setup*, /automation, or web-service-letter routes.
- Keep the architecture map aligned with the surviving eight-step wizard.

Main's application/test edits are non-overlapping with the candidate changes
and are combined from the common ancestor. Documentation has a real overlap:
main describes the older setup routes, while this branch intentionally removes
them. No new filing, invoice, fee, dependency or database behavior is introduced.

## Verification

The UI candidate c1ebe7d passed all seven CI jobs in run 38598924765, including
full tests and the expanded real-Chromium suites/screenshots. The integration
commit is checked again by the exact-head #382 workflow: full tests with
coverage, lint, dependency audit, smoke, guest/host browser geometry, Docker,
secrets and context checks. No local commands or human screenshot review are claimed;
the execution workspace is unavailable.

## Owner release

#389 is already included; no separate merge or retarget is needed. After the
combined #382 checks are green, mark the draft ready and use
`scripts/merge-pr-on-green.sh 382 --squash`. The helper pins the tested head and
refuses pending or failed checks. Deploy the resulting main commit as appropriate.

This integration updates the feature branch; it does not merge #382 or deploy.
