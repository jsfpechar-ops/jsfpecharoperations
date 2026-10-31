# Portable bundle manifest

Base: `8b5317d0a49b840136fbfbcad7fb06af100f3575`. All changes are documentation; no App code is included.

`changes.patch` contains all tracked documentation changes and the three new task/report files. Flat copies hold complete replacement content. `manifest.json` records target paths and base/content hashes. Use either the patch or placement script, never both blindly.

Run `python3 place_files.py /absolute/repository/path` for a dry run; add `--apply` only after reviewing its output. It preflights every file and refuses changed destinations. Files already matching are skipped. The script never commits or pushes.

| Flat file | Destination |
|---|---|
| docs__context__decisions.md | docs/context/decisions.md |
| docs__context__known-issues.md | docs/context/known-issues.md |
| docs__context__prompts.md | docs/context/prompts.md |
| docs__context__rules.md | docs/context/rules.md |
| docs__context__status.md | docs/context/status.md |
| docs__context__workflow.md | docs/context/workflow.md |
| docs__plans__business-metrics-and-database-plan-20261030.md | docs/plans/business-metrics-and-database-plan-20261030.md |
| docs__plans__ux-smoothness-plan-20261030.md | docs/plans/ux-smoothness-plan-20261030.md |
| docs__tasks__0451-visible-guest-acknowledgement.md | docs/tasks/0451-visible-guest-acknowledgement.md |
| docs__tasks__0451-report.md | docs/tasks/0451-report.md |
| docs__tasks__0452-read-only-billing-extract.md | docs/tasks/0452-read-only-billing-extract.md |

Read REVIEW-RESULT.md, task reports and LOCAL-AI-PROMPT.md before execution. Both application briefs remain blocked.
