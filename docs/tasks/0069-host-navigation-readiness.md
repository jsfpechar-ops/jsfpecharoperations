# 0069: Host navigation ownership and readiness

Status: todo
Depends on: none (designs approved in chat 2026-10-12) | Base commit: 0e8e468f6f8a7d4e33109493c115f580e0006504 | Branch: task/0069-host-navigation-readiness | PR base: task/host-navigation-integration
Executor: Cursor local agent (composer, Kimi or GLM) | Fits one session | Documentation and verification only

## 1. Objective

Verify the route/form ownership and current test baseline before the selected host navigation redesign. Produce a precise inventory that lets subsequent small briefs reuse one editor per setting without losing existing features or silently clearing unrelated values.

## 2. Context

Read AGENTS.md, this brief, and the named plan. Do not audit unrelated code. The app is FastAPI/Jinja2/plain JS/CSS; no new framework or dependency. This task changes no application code and performs no real filing, email, payment or lock operation.

Verified anchors at the base revision:

`App/app/routes/admin.py`:

```python
@router.get("/guest-links")
def guest_links(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    return _property_hub_redirect(request, "communication")
```

```python
    payload = _apartment_payload(form)
    if "automation_mode" not in form:
        for key in ("automation_mode", "submit_after_hours", "default_purpose"):
            payload.pop(key, None)
```

`App/app/templates/invoice_settings.html`:

```html
<form method="post" action="/invoices/settings">
```

`App/app/templates/stay_fee_setup.html`:

```jinja
  {% include "_stay_fee_fields.html" %}
```

`App/app/routes/invoices.py`:

```python
    raw_stay = request.query_params.get("reservation_id")
```

These are safety anchors, not a suggestion to change their behavior. If the revision has advanced, record the new SHA and confirm equivalent contracts before rewriting any later implementation brief. Task 0066's status line is stale relative to the merged revision; its report is historical evidence, not a current test result.

## 3. Files

Only these files may be created/edited. Follow the staging-first branch/report rules in [the execution protocol](../plans/host-navigation-execution-protocol.md):

| Path | Action | What |
|---|---|---|
| `docs/plans/host-navigation-ownership.md` | create | Verified inventory and next-phase exact scope |
| `docs/tasks/0069-report.md` | create | Required report, 1500 tokens maximum |
| `docs/tasks/0069-host-navigation-readiness.md` | edit | Status only, including the reason if blocked |

Read-only source allowlist:

- `docs/plans/host-navigation-maintainability.md`, `docs/HOST_APP_DESIGN.md`, `docs/DESIGN.md` sections named in the plan; `docs/tasks/0066-report.md`.
- `App/app/routes/admin.py`, `invoices.py`, `stay_fees.py`, `admin_accounts.py`, `api.py` — grep and focused ranges only.
- `App/app/templates/apartment_form.html`, `apartments.html`, `_components.html`, `_host_navigation.html`, `base.html`, `entities.html`, `invoice_settings.html`, `invoice_stay_picker.html`, `invoice_form.html`, `invoice_detail.html`, `invoices.html`, `stay_fee_setup.html`, `_stay_fee_fields.html`, `_account_parts.html`, `stay_fees.html`, `stay_fee_detail.html`, `dashboard.html`, `reservations.html`, `reservation_detail.html`, `settings.html`, `smart_locks.html`.
- `App/app/static/app.js`, `host.css`, `host-controls.css`, `tokens.css`; relevant `host_i18n.py` keys by grep.
- Relevant existing tests listed in plan §9; test runner/environment configuration only when needed to run the existing checks. Read-only `App/app/security.py`/`access.py` guards if route ownership cannot be confirmed from the named handlers.

No other file may change. Test-generated temporary artifacts do not authorize committing databases, real data or application edits. If a necessary source is absent/outside this list, report the missing path and request a scope correction.

## 4. Steps

1. Confirm the owner recorded the design families/changes in the plan; only then set this brief to in-progress. Run `git status --short`, `git branch --show-current`, `git rev-parse HEAD`. Record pre-existing changes; do not stage or overwrite them. Confirm the anchor snippets.
2. Build `docs/plans/host-navigation-ownership.md` with these exact sections: **Revision and selected designs**, **Route and entry-point table**, **Field/editor ownership**, **Compatibility and return navigation**, **Save semantics**, **Baseline results**, **Next brief scope**.
3. Route table columns: URL/method; handler; template/partial; record scope; authorization/CSRF guard; editable or summary; legacy/return behavior. Cover Properties/property/create, guest-links/automation redirects, feeds, entities, invoice settings/new/preview/detail, fee setup/list/detail, Stays/detail, account settings and shared lock account links. List unique controls before recommending retirement of an editor.
4. Ownership table columns: field/group; every current rendering; every save/validation path; canonical proposed owner; affected entry points; preserved unique behavior. Inspect property omitted-checkbox/default values, automation presence check, credentials blank/changed semantics, entity/controller IDs, guest PIN/link actions, lock section sentinel and fee normalization. Distinguish legitimately shared fields from different scopes. No secrets or actual user values in the document.
5. Confirm guest-link copy/PIN/message/preview/regeneration, timing/test/code-list actions, copy-from-property, address wizard scope, ARES, bank/IBAN-only accounts, VAT, signatures, invoice stay eligibility/immutability, fee finalization/markers and archived/access states are accounted for. Do not exercise live provider operations.
6. Run the checks in §6 once as the baseline. Required browser prerequisites must be present; do not count skips as acceptance. Record failures and environmental limitations without changing application code or weakening tests. Task 0066's report numbers must be labelled historical.
7. In **Next brief scope**, list the exact field partials/render sites to extract first and the exact relevant tests. The first implementation brief is markup extraction/payload equivalence only, before tabs/save changes. Identify any shared fields whose consolidation needs a separate domain correction brief.
8. Write the report under §9 and set Status to review, or blocked with the actual failure/scope reason. The inventory is evidence for the orchestrator to write exact implementation diffs; it is not permission to execute phases 1–7.

## 5. Do not touch

All `App/` implementation files, dependencies, migrations, production/staging data, secrets, filing/lock/fee/invoice business logic, guest-facing pages, PDFs, public marketing, authentication behavior, retention and tests. A report PR may target only `task/host-navigation-integration`; do not target or merge main, deploy, or change test acceptance. Hand publication/merge to the owner if the standard executor environment cannot perform it. No test-baseline acceptance changes.

## 6. Commands

From repository root:

```bash
git status --short
git branch --show-current
git rev-parse HEAD
python3 scripts/context_lint.py
```

From `App/`, using the existing supported test environment:

```bash
.venv/bin/python -m pytest tests -q
```

Expected: full results captured, context lint OK, required host browser/geometry checks actually run with 0 skipped. If failures/skips occur, record the actual evidence and scope a follow-up; do not assert green. Do not repeat a failed full suite without a specific environment fix or changed cause.

## 7. Acceptance

- [ ] Owner design selections, exact revision and pre-existing changes recorded.
- [ ] Every named page/action in the route table points to a source path; no invented handler or UI feature.
- [ ] Property, shared entity/invoice fields and fee setup overlap documented with record scope and unchanged-value risks.
- [ ] Legacy anchors, redirects, safe return parameters and one/many/no-property behavior recorded.
- [ ] Existing stay-linked invoice and finalized fee contracts take precedence over older mockup/spec text.
- [ ] Current test results distinguished from the historical 0066 report; failures/skips disclosed.
- [ ] Next extraction brief has explicit candidate files and tests; no application edits made.
- [ ] Context lint passes and report is within its cap.

No new UI screenshots are required for this documentation-only task. Every later template/CSS brief requires the repo's screenshots and zero-skip browser/geometry checks.

## 8. Stop and ask

Stop and report if an anchor/contract is absent, an unapproved design change is needed, a required source lies outside §3, a new dependency is needed, test environment cannot run required browser checks, a test fails twice, application fixes are needed, or any push/merge/secrets/SSH/deploy is requested. Readiness failures produce a correction brief rather than an unplanned patch.

## 9. Report

Create `docs/tasks/0069-report.md` (1500 tokens maximum): files changed and diff stat; baseline commands and last five output lines; §7 checked/unchecked; verified duplicate/shared-editor findings; discrepancies/limitations; exact next-phase recommendation; owner steps. Link the detailed ownership inventory rather than repeating it.

## Risk list (for the reviewer)

Read the full ownership inventory, this brief's status diff and the report. There must be no application diff. Check claims against the precise route/template evidence, especially property partial-save assumptions, invoice-settings overlap and fee setup compatibility.

## Owner steps

1. Designs were approved in chat on 2026-10-12; no repeated design confirmation is needed.
2. Establish the integration branch from the reviewed planning branch using the execution protocol; it must stay off main until staging approval.
3. Open a fresh Cursor chat using the master prompt; review its inventory/report before the orchestrator releases the next brief.

## Executor prompt

```text
Read AGENTS.md and docs/tasks/0069-host-navigation-readiness.md.
Run only when its Status is todo. Follow the documentation-only scope exactly.
Read only its named sources, verify editor ownership and capture the current
test baseline. Do not implement the redesign or change tests. Write the required
inventory and report, then set the brief to review or blocked with evidence.
```
