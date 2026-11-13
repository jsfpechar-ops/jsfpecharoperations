# 1410: Delete the sidecar bundles of finished Go-port briefs

Status: review
Depends on: none | Base commit: 3d75651dd | Branch: cursor/1410-docs-sidecar-cleanup-4de2
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Delete three folders of copied Go, Python and JSON source that PR #1003 left under docs/ (`docs/plans/1301-files/`, `docs/plans/1302-files/`, `docs/tasks/1320-files/`) and point the briefs that mention them at the real files on main. The real files already live in `go/` and `App/`; the copies only add review noise and can drift.

## 2. Context

Rules: AGENTS.md hard rule 3 (public repo, nothing sensitive here), one explanation in one place. Docs only: no `App/` or `go/` edit.

Safety check done by the brief writer (rerun in step 1, do not skip it):

- A sidecar folder is deleted only when its owning brief has `Status: done` or `Status: review` AND the files it copies exist on main. Three folders pass: 1301 (review), 1302 (review), 1320 (review).
- No file under `scripts/`, `.github/`, `App/` or `go/` names any of the three folders (`git grep` returned nothing). `scripts/context_lint.py` only checks briefs and links, not these folders.
- Each of the three folders is named only by the briefs and reports listed in §3. Steps 3 to 9 rewrite those lines so `git grep` for the folder names finds nothing outside this brief.

Kept on purpose (do NOT delete, even though they are on the candidate list):

| Path | Why kept |
|---|---|
| `docs/tasks/1220-files/`, `docs/tasks/1221-files/`, `docs/tasks/1222-files/` | owning briefs 1220, 1221, 1222 still say `Status: todo` (their reports say review, but the brief Status is the rule). Re-running the brief would need the sidecars. |
| `docs/tasks/1321-files/`, `docs/tasks/1330-files/` | owning briefs 1321 and 1330 are `Status: todo`; 1321 §3 even says `keep`. |
| `docs/tasks/1240a-go-stay-fee-calc-code.md`, `docs/tasks/1242a-go-stay-fee-job-code.md` | owning briefs 1240 and 1242 are `Status: todo`; the briefs link to these code dumps. |
| `docs/tasks/1350-go-booking-webhook.patch`, `docs/tasks/1350-fix-1-go-booking-webhook.patch` | owning briefs 1350 and 1350-fix-1 are `Status: todo`. |
| `docs/tasks/1380-files/MANIFEST.sha256` | not a copy of source: one small checksum list that brief 1380 step 1 runs. |

Follow-up (not this brief): once the orchestrator flips the stale `todo` Status lines of 1220, 1221, 1222, 1240, 1242, 1321, 1330 and 1350 to `review`, a later brief can remove their sidecars the same way.

Escaping: in the old/new strings of steps 3 to 9 a backslash before a backtick is only markdown escaping. The file text has a plain backtick, no backslash. Every old string was checked to occur exactly once.

Anchors (each must be found verbatim in step 3 to 9, otherwise STOP):

- `docs/tasks/1301-go-property-pages.md` line 13 contains `the finished files are in \`docs/plans/1301-files/\` (flat bundle)`.
- `docs/tasks/1320-go-exports.md` line 17 contains `The exact files are sidecars in \`docs/tasks/1320-files/<repo path>.txt\``.

## 3. Files

| Path | Action | What |
|---|---|---|
| `docs/plans/1301-files/` | delete (`git rm -r`) | copies of the 1301 property-pages code |
| `docs/plans/1302-files/` | delete (`git rm -r`) | copies of the 1302 property-lists code |
| `docs/tasks/1320-files/` | delete (`git rm -r`) | `.txt` copies of the 1320 exports code |
| `docs/tasks/1301-go-property-pages.md` | edit | 4 reference spots (lines 13, 54-59, 109, 137) |
| `docs/tasks/1301-fix-1-go-property-pages.md` | edit | line 190 |
| `docs/tasks/1301-report.md` | edit | line 18 |
| `docs/tasks/1302-go-property-lists.md` | edit | 4 reference spots (lines 13, 59-63, 113, 141) |
| `docs/tasks/1302-report.md` | edit | line 7 |
| `docs/tasks/1320-go-exports.md` | edit | lines 17, 19, 67, 73, 76, 109 |
| `docs/tasks/1320-report.md` | edit | line 7 |
| `docs/tasks/1410-report.md` | create | the report |

No other file may change.

## 4. Steps

1. Verify the safety check and the real files. From the repo root run:
   `git checkout cursor/1410-docs-sidecar-cleanup-4de2 2>&1 | tail -3; git branch --show-current; for n in 1301-go-property-pages 1302-go-property-lists 1320-go-exports; do grep -m1 '^Status:' docs/tasks/$n.md; done; ls go/internal/web/properties/pages.go go/internal/web/properties/lists.go go/internal/web/exports/exports.go go/cmd/ubyhost-web/register_web_properties.go go/cmd/ubyhost-web/register_web_exports.go App/tests/test_go_properties_pages.py App/tests/test_go_properties_lists.py App/tests/test_go_exports.py 2>&1 | tail -30; git grep -n -E '1301-files|1302-files|1320-files' -- scripts .github App go | tail -30`
   Expected: branch name printed; three lines `Status: review`; eight paths listed with no `No such file`; the final `git grep` prints nothing. Any `Status: todo`, any missing file or any `git grep` hit: STOP (§8).
2. Delete the three folders, one command each:
   `git rm -r -q docs/plans/1301-files && git status --short | tail -3`
   `git rm -r -q docs/plans/1302-files && git status --short | tail -3`
   `git rm -r -q docs/tasks/1320-files && git status --short | tail -3`
   Expected: each shows ` D`/`D ` lines only under the folder just removed. Do not remove anything else.
3. `docs/tasks/1301-go-property-pages.md`. Four edits with the edit tool; each old string must be found exactly once.
   a) old: `the finished files are in \`docs/plans/1301-files/\` (flat bundle)` -> new: `the finished files were a flat bundle, removed by brief 1410 (they live at the §3 paths on main)`
   b) old (6 lines, inside the code fence, lines 54-59):
   ```
   B=docs/plans/1301-files P=go/internal/web/properties
   mkdir -p $P/templates $P/testdata
   cp $B/pages.go $P/pages.go && cp $B/pages_test.go $P/pages_test.go && cp $B/guide.tmpl $P/templates/guide.tmpl
   cp $B/pages_cases.json $P/testdata/pages_cases.json && cp $B/i18n_keys.txt $P/i18n_keys.txt
   cp $B/register_web_properties.go go/cmd/ubyhost-web/register_web_properties.go
   cp $B/test_go_properties_pages.py App/tests/test_go_properties_pages.py
   ```
   -> new (one line): `# Done in the original run. The bundle was removed by brief 1410; the files are at the §3 paths on main.`
   c) old: `Do not edit the copied files, \`docs/plans/1301-files/\` or the golden by hand.` -> new: `Do not edit the copied files or the golden by hand.`
   d) old: `lists only §3 paths, this brief and \`docs/plans/1301-files/\`.` -> new: `lists only §3 paths and this brief.`
   Check: `grep -c '1301-files' docs/tasks/1301-go-property-pages.md` prints `0`.
4. `docs/tasks/1301-fix-1-go-property-pages.md` (line 190): old: `1300's files, \`App/\` (the Python test stays as it is), \`docs/plans/1301-files/\`, deploy and env docs.` -> new: `1300's files, \`App/\` (the Python test stays as it is), deploy and env docs.` Check: `grep -c '1301-files' docs/tasks/1301-fix-1-go-property-pages.md` prints `0`.
5. `docs/tasks/1301-report.md` (line 18): old: `- docs/plans/1301-files/ (bundle, already tracked)` -> new: `- the bundle (already tracked; removed later by brief 1410)`. Check: `grep -c '1301-files' docs/tasks/1301-report.md` prints `0`.
6. `docs/tasks/1302-go-property-lists.md`. Four edits:
   a) old: `the finished files are in \`docs/plans/1302-files/\` (flat bundle)` -> new: `the finished files were a flat bundle, removed by brief 1410 (they live at the §3 paths on main)`
   b) old (5 lines, lines 59-63):
   ```
   B=docs/plans/1302-files P=go/internal/web/properties
   cp $B/lists.go $P/lists.go && cp $B/lists_test.go $P/lists_test.go && cp $B/lists.tmpl $P/templates/lists.tmpl
   cp $B/lists_cases.json $P/testdata/lists_cases.json && cp $B/i18n_keys.txt $P/i18n_keys.txt
   cp $B/register_web_properties.go go/cmd/ubyhost-web/register_web_properties.go
   cp $B/test_go_properties_lists.py App/tests/test_go_properties_lists.py
   ```
   -> new (one line): `# Done in the original run. The bundle was removed by brief 1410; the files are at the §3 paths on main.`
   c) old: `Do not edit the copied files, \`docs/plans/1302-files/\` or the golden by hand.` -> new: `Do not edit the copied files or the golden by hand.`
   d) old: `lists only §3 paths, this brief and \`docs/plans/1302-files/\`.` -> new: `lists only §3 paths and this brief.`
   Check: `grep -c '1302-files' docs/tasks/1302-go-property-lists.md` prints `0`.
7. `docs/tasks/1302-report.md` (line 7): old: `\`docs/plans/1302-files/\` (bundle, unchanged)` -> new: `the bundle (unchanged; removed later by brief 1410)`. Check: `grep -c '1302-files' docs/tasks/1302-report.md` prints `0`.
8. `docs/tasks/1320-go-exports.md`. Six edits:
   a) old: `The exact files are sidecars in \`docs/tasks/1320-files/<repo path>.txt\`; step 1 copies them into place byte for byte and checks the sha256 below. Never retype or edit them.` -> new: `The exact files were sidecars (removed by brief 1410); they live at the repo paths in the table on main. Never retype or edit them.`
   b) old: `file (repo path; sidecar = \`docs/tasks/1320-files/<path>.txt\`)` -> new: `file (repo path)`
   c) old: ` The sidecars under \`docs/tasks/1320-files/\` are already committed with this brief; leave them.` -> new: empty (delete the sentence and its leading space).
   d) old: `1. Copy the sidecars into place and check them (one call, repo root):` -> new: `1. Check the files (the sidecar copy was done in the original run; the sidecars were removed by brief 1410) (one call, repo root):`
   e) old (start of line 76): `cd docs/tasks/1320-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum App/scripts/exports_golden.py` -> new: `sha256sum App/scripts/exports_golden.py` (the rest of the line stays as it is).
   f) old: `this brief and \`docs/tasks/1320-files/\`, \`docs/tasks/1321*\`.` -> new: `this brief and \`docs/tasks/1321*\`.`
   Check: `grep -c '1320-files' docs/tasks/1320-go-exports.md` prints `0`.
9. `docs/tasks/1320-report.md` (line 7): old: `plus \`docs/tasks/1320-files/\`, \`docs/tasks/1320-report.md\`,` -> new: `plus the sidecar folder (removed later by brief 1410), \`docs/tasks/1320-report.md\`,`. Check: `grep -c '1320-files' docs/tasks/1320-report.md` prints `0`.
10. Final checks, one call: `git grep -n -E '1301-files|1302-files|1320-files' -- . ':!docs/tasks/1410-docs-sidecar-cleanup.md' ':!docs/tasks/1410-report.md' | tail -30; python3 scripts/context_lint.py 2>&1 | tail -30; git status --short | wc -l`
    Expected: `git grep` prints nothing; lint ends with an OK line (the same warnings as before are fine, no new `ERROR`); the status count equals the deleted files plus 7 edited briefs and reports (no other path).
11. Write `docs/tasks/1410-report.md` (§9), set this brief's line 3 to `Status: review`, then commit: `git add -A docs && git commit -q -m "1410: remove finished sidecar bundles (1301, 1302, 1320)" && git push -u origin cursor/1410-docs-sidecar-cleanup-4de2 2>&1 | tail -5`. Expected: push succeeds. Open a normal (not draft) PR against `main` titled `1410: remove finished sidecar bundles`, body: the §7 checklist and the kept-files table of §2. Command: `gh pr create --base main --head cursor/1410-docs-sidecar-cleanup-4de2 --title "1410: remove finished sidecar bundles" --body-file docs/tasks/1410-report.md 2>&1 | tail -5`. If `gh` is read-only or fails, STOP and hand that exact command to the owner. NEVER merge.

## 5. Do not touch

- Everything under `App/`, `go/`, `deploy/`, `scripts/`, `.github/`.
- Every kept path in the §2 table, in particular `docs/tasks/1220-files/`, `1221-files/`, `1222-files/`, `1321-files/`, `1330-files/`, `1380-files/`, the two `.patch` files and the two `*a-*-code.md` dumps.
- Any `Status:` line other than this brief's own.
- Hard rules: 3 (nothing sensitive added), 8 (never push to `main`, never merge).

## 6. Commands

- Step 1 command (checks). Expected: three `Status: review`, no `No such file`, empty `git grep`.
- Step 10 command. Expected: empty `git grep`; `python3 scripts/context_lint.py` OK.
- No tests run: docs only, no test-map row applies.

## 7. Acceptance

- [ ] `ls docs/plans/1301-files docs/plans/1302-files docs/tasks/1320-files 2>&1 | tail -5` prints three `No such file or directory`.
- [ ] `git grep -n -E '1301-files|1302-files|1320-files' -- . ':!docs/tasks/1410-docs-sidecar-cleanup.md' ':!docs/tasks/1410-report.md' | tail -30` prints nothing.
- [ ] `python3 scripts/context_lint.py 2>&1 | tail -30` ends OK.
- [ ] `git diff --stat origin/main...HEAD | tail -30` shows only the three deleted folders, the 7 edited briefs and reports, and this brief plus its report.
- [ ] `ls docs/tasks/1220-files docs/tasks/1321-files docs/tasks/1330-files docs/tasks/1380-files | head -3` still lists files (kept folders untouched).

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- step 1 shows a `Status: todo`, a missing real file or a `git grep` hit in `scripts/`, `.github/`, `App/` or `go/`;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1410-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- The three `git rm -r` lines: confirm each folder is only sidecars (step 1 `ls` lists the real files).
- The edited lines in `1301-go-property-pages.md`, `1302-go-property-lists.md` and `1320-go-exports.md`: only reference text changed, no step number moved.

## Owner steps

1. Open the PR the executor created and wait for the green check.
2. Merge it with `scripts/merge-pr-on-green.sh <PR number>`.
3. Ask the orchestrator for the follow-up brief that removes the remaining sidecars once the stale `todo` Status lines are fixed.
