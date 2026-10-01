# Implementation plan: Ticket Wallet v3, stay-fee legal clarity, host redesign

**Status (Oct 2026):** Revised after owner clarification: stay-fee remittance already exists on `main`; the legal audit documents **clarified gaps** and drives **incremental** alignment—not a separate codebase import.

**Spec sources on GitHub:**

| Workstream | Docs |
|------------|------|
| Ticket Wallet v3 | [`ticket-wallet-v3-stay-fee-audit/V3_FIXES.md`](ticket-wallet-v3-stay-fee-audit/V3_FIXES.md), `ticket-wallet-v3.bundle` |
| Stay-fee legal audit | [`LEGAL_AUDIT_IMPLEMENTED.md`](ticket-wallet-v3-stay-fee-audit/LEGAL_AUDIT_IMPLEMENTED.md), [`COMBINED_CURSOR_HANDOFF.md`](ticket-wallet-v3-stay-fee-audit/COMBINED_CURSOR_HANDOFF.md), [`TEST_REPORT.md`](ticket-wallet-v3-stay-fee-audit/TEST_REPORT.md) |
| Host-app redesign | [`host-app-redesign/host-app-redesign/`](host-app-redesign/host-app-redesign/) (`CURSOR_PROMPT.md`, `IMPLEMENTATION.md`, `apply_handoff.py`) |

**Branches pushed (implementation in progress):**

- `fix/ticket-wallet-v3` — guest flow + browser CI
- `cursor/host-app-redesign-a4fb` — host shell from docs payload
- `cursor/stay-fee-legal-audit-a4fb` — legal alignment (currently stacked on host commit; merge host first, then rebase fee-only commits)

---

## How the three plans relate

| Plan | Role |
|------|------|
| **Ticket Wallet v3** | Restore reverted guest flow + v3 fixes + Playwright browser tests |
| **Stay-fee legal audit** | Answers prior legal/product gaps (7 items + finalization/register rules); checklist to align existing remittance code |
| **Host-app redesign** | Host navigation, `host.css`, templates—fee detail UX among other screens |

Stay-fee **code already on `main`** (list, detail, on-demand PDF/CSV, guest decisions, PRs #207–#210). The audit resolved ambiguous questions in writing; implementation **closes the delta** to those answers. Local branch `fix/stay-fee-legal-audit` / `a4be2d0` is optional reference only.

---

## Stay-fee: seven clarified gaps (main vs audit target)

Authority: [`LEGAL_AUDIT_IMPLEMENTED.md`](ticket-wallet-v3-stay-fee-audit/LEGAL_AUDIT_IMPLEMENTED.md) over conflicting parts of [`PLAN_STAY_FEE_REMITTANCE.md`](stay-fee-remittance/PLAN_STAY_FEE_REMITTANCE.md).

| # | Gap | On `main` before alignment | Audit target |
|---|-----|---------------------------|--------------|
| 1 | Month boundary | Night overlap in `nights_in` | Commenced days `(arrival, departure]`; Aug/Sep split per §3c |
| 2 | 60-day boundary | Long stays → `not_subject`, excluded | Block finalize at exact 60-night case until **written office answer** per facility (`scope-ruling`) |
| 3 | 18th birthday | Minor on arrival day only | Per chargeable day; split nights; `charge` cannot bill minor days |
| 4 | Sensitive exemptions | Free-text reason | Controlled categories + bylaw ref; encrypted; privacy/DPA/guest notice |
| 5 | Art. 18 restriction | `restricted` flag | Full §3g identity in CSV; controller decides individual requests |
| 6 | Durable records | PDF/CSV regenerated each download | `stay_fee_filing`: finalize → frozen encrypted bytes; versions; retention/export |
| 7 | Same VS, multiple facilities | Per-property reports | One report/register per facility (no assumed combined filing) |

**External (document in PR/release; UI blocks where noted):**

- Written municipality ruling for exact 60-night case
- Controller GDPR **Art. 9** basis for disability-related exemption data
- Counsel on § **3g(3)** evidenční kniha vs live records + sealed exports

---

## Delivery order

1. **Phase 0** — Fast-forward `main` from `origin` (plan uploads + PR #211 docs).
2. **Phase 1** — PR **`fix/ticket-wallet-v3`** → `main`. Merge on green CI (guest-browser job) + phone test (group of 2).
3. **Phase 2** — PR **`cursor/host-app-redesign-a4fb`** → `main` (`apply_handoff.py` or patch).
4. **Phase 3** — PR **`cursor/stay-fee-legal-audit-a4fb`** → `main` after Phase 2 (rebase so PR is fee-only on top of merged host). Checklist: handoff docs + tests in `TEST_REPORT.md`.

Ticket Wallet is independent of host/stay-fee. Host redesign before stay-fee reduces merge conflicts in `stay_fee_detail.html`, `stay_fees.py`, `host_i18n.py`.

---

## Verification

- `cd App && .venv/bin/python -m pytest tests -q` (86% coverage gate)
- Stay-fee: EN/CS fee detail—blockers, finalize, byte-stable re-download, correction
- Ticket Wallet: browser e2e + manual phone smoke
- Deploy: manual workflow only; test DB migration on a copy before production

---

## Subagent progress (for owner)

- `main` synced to `f9dbc33`
- Branches pushed; open draft PRs in GitHub UI if automation cannot create them
- Stay-fee branch: core finalize/filing/counting landed; handoff gaps may remain (scope-ruling UI, controlled exemption forms, full privacy/export matrix)—track against `LEGAL_AUDIT_IMPLEMENTED.md` before merge
