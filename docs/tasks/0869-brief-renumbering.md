# 0869: Brief renumbering for colliding task numbers

Status: todo (index only: the owning threads rename files on their own branches; never run this file as a brief)
Author: orchestrator, from `git diff --diff-filter=A` of every open PR against main `14c707d`, 2026-11-02.

## 1. Objective

Several open PRs add `docs/tasks/NNNN-*.md` files with the same number, so after merges the briefs and reports overwrite each other and `context_lint` "next free" is wrong. Each owning PR renames its colliding briefs and reports to the new number below before it merges. The lowest-risk owner keeps the old number.

## 2. Context

Merged main already uses 0812 to 0818 for Go and booking site. Open PRs reuse those numbers. #702 and #731 are stacked (same files), #713 is closed in favour of #723, #722 is stacked under #725: the same file in a stacked pair is not a collision.

## 3. Files

Rename each brief `NNNN-slug.md` and its `NNNN-report.md`. Also rename `docs/tasks/screenshots-NNNN/` only if the branch's own tests write there by that name; otherwise leave code, test names and CSS marker comments as they are (a marker such as `/* 0833 ... */` is a label, not a task id).

## 4. Steps

| PR (owner) | Old number and slug | New number |
|---|---|---|
| #702 (and stacked #731) | 0812 v2-help-tip-shared | 0870 |
| #702 / #731 | 0813 v2-remaining-pages-neighbour-gap | 0871 |
| #702 / #731 | 0814 v2-help-tip-small-inline | 0872 |
| #723 | 0814 phone-calendar-airbnb | 0873 |
| #723 | 0815 cleaning-calendar-airbnb | 0874 |
| #723 | 0816 calendar-airbnb-desktop-tablet | 0875 |
| #723 | 0817 calendar-airbnb-polish | 0876 |
| #723 | 0818 calendar-airbnb-desktop-review-fixes | 0877 |
| #725 | 0833 property-editor-airbnb-fix | 0878 |
| #727 | 0833 passport-ocr | 0879 |
| #727 | 0834 ocr-host-toggle | 0880 |
| #727 | 0835 ocr-scan-independent | 0881 |
| #729 | 0833 faster-onboarding | 0882 |
| #729 | 0834 onboarding-review-fixes | 0883 |
| #731 | 0834 wizard-half-the-taps | 0884 |
| #734 | 0842 guest-form-help-inline | 0885 |
| #734 | 0843 invoice-buyer-type-switch | 0886 |
| #725 | 0850 address-autofill-editor | 0887 |
| #737 | 0852 invoice-price-and-payment-defaults | 0888 |
| #737 | 0853 housebook-period-presets | 0889 |
| #737 | 0854 speed-pages-browser-shots | 0890 |

Kept unchanged: #723 keeps 0832 to 0835 and 0842; #707 keeps 0850 to 0863; #737 keeps 0843 (speed overview) to 0849; main keeps 0812 to 0818.
After renaming, #737 updates its index (0843 run-order table and the "0850 and 0851 are taken by #707" line) to the new 0888 to 0890. Calendar part 5 was planned as 0860+: use 0891 and up instead (0860 to 0863 are #707).

## 5. Do not touch

No code, tests or CSS in this brief. Do not renumber merged briefs.

## 6. Commands

`python3 scripts/context_lint.py 2>&1 | tail -30` from the repo root after the rename; the lint's "next free" line must read 0891 or higher.

## 7. Acceptance

- [ ] No `docs/tasks/NNNN-*.md` number is used by two different slugs across main and the open PRs.
- [ ] Context lint passes.

## 8. Stop and ask

If a brief is already cited by number in `decisions.md`, `status.md` or `known-issues.md`, update that line instead of leaving a dead number.

## 9. Report

None.
