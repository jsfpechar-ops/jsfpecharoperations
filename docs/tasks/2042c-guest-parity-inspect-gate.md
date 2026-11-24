# 2042c: V2 visual parity, guest pages: inspect differences, gate command

Status: todo
Depends on: 2042b (done and merged or on this branch) | Base commit: HEAD | Branch: current
Executor: Haiku 5.5 | Fits one session: 30 tool calls (stop at 25)

## 1. Objective

Read the 2042b results, describe every visible guest-page difference in plain words (fields, labels, validation messages, buttons, steps), add `scripts/e2e/parity_gate.sh`, prove its wiring once, write the report. **Do not fix differences.**

## 2. Context

- Results: `docs/tasks/2042b-report.md` names the report files (`report-H.md`, `report-P.md`) and the PNG directory. Rows: `name-lang width verdict`; the side-by-side image is `<name>-<width>-side.png` (py left, go right), diff image `-diff.png`.
- `page_parity_visual.py` exits 1 on any `visible` or `error` row (main(), last line). `PARITY_GROUP`, `PARITY_ONLY`, `PARITY_WIDTHS`, `PARITY_PIN` select runs. Group names: A, B, C, D (host and admin, per 2040/2041), E, F, G as defined in `parity_cases.py` (`grep -n '"[A-Z]")' scripts/e2e/parity_cases.py | head`: use only groups that exist), H guest, P PIN.
- Guest pages carry the same cookies on both stacks (claim cookie signed by the shared `UBYHOST_SECRET_KEY`; see 2042b section 2).

## 3. Files

| Path | Action | What |
|---|---|---|
| `scripts/e2e/parity_gate.sh` | new | the aggregate command |
| `docs/tasks/2042-report.md` | write | final verdict table, visible causes, gate command, exclusions |

## 4. Steps

1. `cat docs/tasks/2042b-report.md | tail -30`; `grep -c . /var/tmp/parity-visual/report-H.md` is not guaranteed: use the paths in the 2042b report. Read the `Not identical:` list of report-H and report-P (`grep -n -A40 'Not identical' <file> | head -60`).
2. Inspect at most **15** images in total: for each visible case read `<name>-390-side.png` for `-cs` only (cs and en differ only by language; read the en one only when a text difference is suspected). Prefer cases in this order: forms (`g-form-*`), stay states, claim landing, guide, Leon, PIN, share, unsubscribe. A case that is identical or invisible at all widths needs no read. A page showing the same "link not valid" card on both sides is `WRONG STATE` (seed or cookie wrong): re-run that single case once (`PARITY_GROUP=H PARITY_ONLY=<name> ...`), else mark it so.
3. For each inspected case write one line in plain words: what differs (field present/missing, label text, validation message, button label or place, step order, spacing/size only), at which width. Quote copy exactly only when a label or message differs.
4. Create `scripts/e2e/parity_gate.sh` (then `chmod +x`) with exactly:
```
#!/usr/bin/env bash
# Pre-deploy gate: Python vs Go pixel parity for every host, admin and guest page. Exit 1 on any visible or error row.
set -u
cd "$(dirname "$0")/../.."
source scripts/e2e/parity_env.sh
rc=0
cd App
for g in A B C D E F G H; do
  PARITY_GROUP=$g .venv/bin/python ../scripts/e2e/page_parity_visual.py 2>&1 | tail -3
  [ "${PIPESTATUS[0]}" -eq 0 ] || rc=1
done
PARITY_PIN=1 PARITY_GROUP=P .venv/bin/python ../scripts/e2e/page_parity_visual.py 2>&1 | tail -3
[ "${PIPESTATUS[0]}" -eq 0 ] || rc=1
if [ "$rc" -eq 0 ]; then echo "GATE: PASS"; else echo "GATE: FAIL"; fi
exit $rc
```
   Before writing it, `grep -n 'PARITY_GROUP\|"[E-G]"' scripts/e2e/page_parity_visual.py scripts/e2e/parity_cases.py | head -8` and delete letters from the `for g in` list that no case uses (an empty group prints 0 rows and exits 0, so this is only tidiness).
5. Prove the wiring once, narrowed: `PARITY_ONLY=g-hub PARITY_WIDTHS=390 bash scripts/e2e/parity_gate.sh 2>&1 | tail -15` (groups without a match print 0 rows; the line `GATE: ...` appears; it fails if `g-hub` is visible: that is a correct result). Do not run the full gate.
6. Write `docs/tasks/2042-report.md` (replace the partial one; keep it short): totals from 2042b; table `case | 390 | 768 | 1280`; per visible cause one plain-words line (step 3); `WRONG STATE` / SKIPPED rows; the gate command `bash scripts/e2e/parity_gate.sh 2>&1 | tail -15` and when to run it (before a deploy, by owner or CI; wall time is the sum of the group runs, take the per-group figures from the 2040/2041 reports); "Next briefs": one line per visible cause. Exclusions: anonymous pages (landing, login, signup, signup/verify, legal, terms, privacy, dpa, subprocessors, jak-to-funguje, cenik, pruvodce/*, /p/{slug}, /p/{slug}/thanks, /terms/booking, /account/email/confirm) by owner scope decision; retired features (booking site, payments, Stripe).
7. `python3 scripts/context_lint.py 2>&1 | tail -3`. Commit by explicit path (`scripts/e2e/parity_gate.sh`, `docs/tasks/2042-report.md`, `docs/tasks/2042c-report.md`) with message `2042c: guest parity findings, gate command` and trailers `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`, `Claude-Session: https://claude.ai/code/session_014N5J8NCpdqN2TbR61gYRQf`.

## 5. Do not touch

`App/app/**`, `go/**`, `scripts/e2e/page_parity_visual.py`, `parity_cases.py`, seeds.

## 6. Commands

```
bash scripts/e2e/parity_gate.sh 2>&1 | tail -15      # narrowed with PARITY_ONLY in step 5 only
python3 scripts/context_lint.py 2>&1 | tail -3
```

## 7. Acceptance

- [ ] At most 15 image reads; every visible guest case has a plain-words cause or `WRONG STATE`.
- [ ] `parity_gate.sh` exists, executable, wiring proven with the narrowed run.
- [ ] `2042-report.md` has verdict table, causes, gate command, exclusions. `context_lint` passes.

## 8. Stop and ask

- 2042b report missing or `blocked`: stop.
- 25 tool calls used: commit, report what is left.
- Never edit app code to fix a row.

## 9. Report

`docs/tasks/2042c-report.md` (600 tokens at most) plus `docs/tasks/2042-report.md`.
