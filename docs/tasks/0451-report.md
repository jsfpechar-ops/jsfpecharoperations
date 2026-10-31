# 0451 report

Status: review.

- Baseline: `8b5317d0a49b840136fbfbcad7fb06af100f3575`, branch `codex/ubyhost-corrections-20261030`.
- New guests advance only when a fresh reservation read reports known positive missing count; final guests and eligible edits return to summary. A missing fresh reservation returns safely to summary. `saved=1` and ownership tracking remain in place.
- Localized save actions and concise previous-guest status are added. The acknowledgement remains visible outside the collapsed legal explanation; existing legal wording and save side effects are unchanged.
- Navigation tests cover unknown and known counts, incomplete eligible edits returning to summary, completed edit lock returning 403, Add another after a complete one-person party, saved/reporting messaging, and duplicate prevention.
- Focused affected suite: 114 passed. Full guest map plus geometry command: `.venv/bin/python -m pytest tests/test_guest_*.py tests/test_host_geometry.py -q -rs --tb=short -x` — 558 passed, 0 skipped.
- Screenshot paths, 390 px, synthetic fixtures: `docs/tasks/screenshots-0451/acknowledgement-390.png`, `next-guest-390.png`, and `completion-summary-390.png`. Inspected; legal copy is collapsed while acknowledgement and button remain visible, and the next guest form is blank with its saved status.

`git diff --check` passed. No commit, push, merge, or deployment was performed.
