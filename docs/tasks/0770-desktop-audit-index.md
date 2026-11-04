# 0770 to 0775: desktop and tablet audit fixes (index)

Status: todo

Source: `/mnt/project-files/ux-desktop-audit/audit-report.md` (2026-11-02, main 1bd2148). Every brief starts with "verify the finding still reproduces", because the audit's CSS causes were unverified guesses. The demo banner and "UKÁZKA" chip are fixture-only; nobody fixes them. Tablet (768/820) has no designed layout (finding 16); these briefs only fix clipping and overlap there. Pre-v2 pages (findings 7, 18-25) and the sidebar rail (17) are out of scope: separate briefs after owner decision.

Order (owner 2026-11-02: ONE big PR, not several; all six briefs commit one after the other on the same branch, in this order, to avoid `app2.css` conflicts; no merge between them. One draft PR at the end with all screenshots, merged on green when main CI is idle):

1. 0770 Overview (`0770-overview-desktop-fixes.md`)
2. 0771 Úklid (`0771-cleaning-desktop-fixes.md`)
3. 0772 Pobyty list (`0772-stays-list-desktop-fixes.md`)
4. 0773 Pobyt and Přidat pobyt (`0773-stay-and-add-stay-desktop.md`)
5. 0774 Nemovitost (`0774-property-desktop-fixes.md`)
6. 0775 Shared disclosure, help button, Nové ubytování (`0775-shared-disclosure-fab-new-property.md`): last, because it deletes the page-specific disclosure rules the earlier briefs leave alone.

Every brief: run its test-map row plus `UBYHOST_REQUIRE_BROWSER=1` `tests/test_0710_v2_mockup_match_browser.py` (0 skipped), screenshots at 1024/1280/1440/768/820/390, bump the `app2.css` cache key in `base.html`.

## 6. Commands

None. This file is an index; the lint treats every `NNNN-*.md` as a brief, so the sections below are stubs.

## 7. Acceptance

- [ ] Briefs 0770 to 0775 all done in the order above on one branch, one PR.

## 8. Stop and ask

Not executable. Orchestrator only.

## 9. Report

None; each brief writes its own report.

## 1. Objective

Index only (see top).

## 2. Context

The audit file named above.

## 3. Files

None.

## 4. Steps

None.

## 5. Do not touch

Everything.

Owner decision 2026-11-02: tablet layout approved (64 px icon rail from 768 up, bottom bar only below 768, gutters 24/32; mockup docs/design/mockup/ubyhost-tablet.html). decisions.md is at its token cap, so the line goes there when it is next compacted.

Design system (owner 2026-11-04): every brief 0770-0775 must follow [design-system.md](../design/design-system.md); the executor reads it first and pastes its section 5 checklist, ticked, into the PR. Where a brief's step conflicts with a rule there, the design system wins (tell the orchestrator).
