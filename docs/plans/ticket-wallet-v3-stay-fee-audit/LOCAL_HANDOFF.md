# Local UbyHost stay-fee handoff

The completed code is committed in the local checkout:

- Checkout: `/Users/j.pechar/Documents/Codex/2026-09-30/stay-fee-7-open-items-plan/work/ubyhost`
- Branch: `fix/stay-fee-legal-audit`
- Tip commit: `a4be2d0` (merges the legal audit and selected host-app redesign)
- Working tree: clean at handoff

Open this checkout in Cursor and start with `docs/plans/stay-fee-remittance/COMBINED_CURSOR_HANDOFF.md`, `LEGAL_AUDIT_IMPLEMENTED.md`, `TEST_REPORT.md`, and `docs/HOST_APP_DESIGN.md`. Implementation is in `App/app/stay_fee.py`, `App/app/routes/stay_fees.py`, `App/app/db.py`, the fee templates, privacy/retention/export modules, and their tests. The code is already implemented; the handoff records what to preserve and what still needs an authority or controller decision.

Final local gate: 2,081 passed, 2 skipped; 89.72% coverage (86% required). CI-selected Ruff rules, JavaScript syntax, and Git whitespace checks passed.

GitHub upload was blocked by the enterprise pre-push security hook, which identified `github.com/jsfpechar-ops/jsfpecharoperations` as an unapproved destination for DoorDash source code. Nothing was pushed and no PR was created. Do not bypass the hook or copy the source to another external destination. Ask enterprise security in `#ask-enterprise-security` to review the destination and advise an approved route.
