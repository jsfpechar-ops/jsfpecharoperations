# 2057: parity harness: PIN pass fix, guide token and MUST_HAVE seeds, rerun, parity_gate.sh

Status: todo
Depends on: 2055 and 2056 merged (precondition: `git log --oneline -30 | grep -c '2055\|2056'` is at least 2, else STOP) | Base commit: HEAD | Branch: current
Executor: Haiku 5.5 | Fits one session: 30 tool calls (stop at 25; commit after every step)
Supersedes: 2042c (this brief contains its gate step; step 6 marks it replaced)

## 1. Objective

Make the guest parity run trustworthy: the PIN pass must not crash, the guide pages must have a guide token, the Leon/guide stay cases must have the five MUST_HAVE cards done, then rerun group H and the PIN pass, look at the visible rows, and add the one-command gate `scripts/e2e/parity_gate.sh`. Harness and seed only; no app code.

## 2. Context

- PIN crash: `config.DB_BACKEND` is postgresql only if `UBYHOST_DATABASE_URL` is set when `app.config` is first imported. In the normal path `audit.start_py` (page_parity_audit.py:210-215) does `os.chdir(APP); sys.path.insert(0, APP); os.environ.update(...)` in-process. The PIN path in `page_parity_visual.py` main() (line 235-237) uses `audit.start_py_process`, which sets the URL only in the child env, so the harness itself (`shots._run_pre_sql` -> `app.db`, App/scripts/go_page_parity_screenshots.py:213-232) imports the sqlite backend and crashes.
- `/g/{tok}` and `/g/{tok}/leon` (cases g-guide-apt, g-leon-apt in `scripts/e2e/parity_cases.py:145,147`) need `apartment.guide_token` (`App/app/guide_token.py`: `ensure(apartment_id)` returns it). Today `{tok}` there is the permalink token, so both stacks print "guest link is not valid" (App/app/routes/guest_guide_view.py:203-211).
- `g-leon-stay` / guide stay cases: Python 404 unless `guest_guide.progress(apt)["live"]`: all `MUST_HAVE = ("checkin","wifi","heating","checkout","emergency")` cards done or skipped (guest_guide.py:82,283-294). `seed_parity_extra.guide()` (line 28-42) adds only the first 4 of `KINDS` and fills 2.
- Seeds run as subprocesses: `run_extra_seed` (page_parity_visual.py:84) and `run_guest_seed` (:97) return a JSON dict of refs used for `{...}` placeholders in `parity_cases.py` (`fill`, line 76). `refs["token"]` is the permalink token; `seed_parity_guest.py` returns `res_*` and guest ids.

## 3. Files

| Path | Action |
|---|---|
| `scripts/e2e/page_parity_visual.py` | edit `main()` `if pin:` block (line ~235) |
| `scripts/e2e/seed_parity_extra.py` | edit `guide()` (line 28-42): all five MUST_HAVE cards done; return `guide_token` |
| `scripts/e2e/parity_cases.py` | edit lines 145 and 147 only (`{tok}` -> `{gtok}`) |
| `scripts/e2e/parity_gate.sh` | new |
| `docs/tasks/2042c-guest-parity-inspect-gate.md` | line 3: `Status: replaced by 2057` |
| `docs/tasks/2057-report.md` | report |

## 4. Steps

1. PIN fix. `grep -nF 'py_proc, py_base = audit.start_py_process(py_port, db_url, public, audit.PIN_ENV)' scripts/e2e/page_parity_visual.py` (must match once). Insert immediately BEFORE that line, same indentation (8 spaces):
```
        os.chdir(audit.APP)
        sys.path.insert(0, str(audit.APP))
        os.environ.update({**audit.PIN_ENV, "UBYHOST_DATABASE_URL": db_url, "UBYHOST_PUBLIC_BASE_URL": public})
```
   Verify `sys` and `os` are imported at the top (`grep -n '^import\|^from' scripts/e2e/page_parity_visual.py | head`); `audit.APP` exists (`grep -n '^APP' scripts/e2e/page_parity_audit.py`). Check: `python3 -c "import ast,sys;ast.parse(open('scripts/e2e/page_parity_visual.py').read())" 2>&1 | tail -3` prints nothing.
2. Guide seed. In `seed_parity_extra.py` `guide()`: change `kinds = list(guest_guide.KINDS)[:4]` to `kinds = list(dict.fromkeys(list(guest_guide.MUST_HAVE) + list(guest_guide.KINDS)))[:6]` and fill EVERY must-have card: for each kind in `guest_guide.MUST_HAVE`, `guest_guide.save(apt, id, {"steps": "E2E steps text", "location": ""})` (use the same call the existing lines use for `ids[0]`; keep one card with only a location as today if it is not a MUST_HAVE kind, and keep `out["guide_item"]`, `out["guide_items"]` meaning (first item, all ids)). Then add `from app import guide_token` to the imports (line 16 list) and `out["guide_token"] = guide_token.ensure(apt)`. Verify after the rerun in step 4 (not by reading): `guest_guide.progress(apt)["live"]` must be true: add to the seed's stderr a line `print("guide live:", guest_guide.progress(apt)["live"], file=sys.stderr)` (the harness echoes stderr lines).
3. Cases. `grep -n 'g-guide-apt\|g-leon-apt' scripts/e2e/parity_cases.py`; replace `{tok}` by `{gtok}` in these two paths only. In `page_parity_visual.py` `fill()` (line 76) the extra dict must expose `gtok`: `sed -n 76,84p scripts/e2e/page_parity_visual.py`; add `"gtok": extra["guide_token"]` where other seed keys are mapped (read the function; if placeholders resolve straight from the merged seed dict, instead rename the seed key to `gtok` in step 2 and skip this). Check: `PARITY_GROUP=H PARITY_ONLY=g-guide-apt PARITY_WIDTHS=390 .venv/bin/python ../scripts/e2e/page_parity_visual.py 2>&1 | tail -8` (from `App/` after `source scripts/e2e/parity_env.sh`) must NOT list the "not valid" card (open the `g-guide-apt-cs-390-side.png` once).
4. Rerun group H, all widths: `cd /home/user/jsfpecharoperations && source scripts/e2e/parity_env.sh && cd App && PARITY_GROUP=H PARITY_WIDTHS=390,768,1280 .venv/bin/python ../scripts/e2e/page_parity_visual.py 2>&1 | tail -30` and note the report path it prints (default `$PARITY_OUT/report-H.md`).
5. PIN pass: `cd App && PARITY_PIN=1 PARITY_GROUP=P PARITY_WIDTHS=390,768,1280 .venv/bin/python ../scripts/e2e/page_parity_visual.py 2>&1 | tail -30` (cs and en are the pass languages). Expected: no Python traceback about sqlite; rows listed. If the crash persists, STOP with the last 30 lines.
6. View side PNGs of visible rows: `grep -n -A40 'Not identical' $PARITY_OUT/report-H.md | head -60` and the same for report-P. Open `<name>-390-side.png` (py left, go right) for at most 15 rows total, prefer cs, order: forms, stay states, claim, guide, Leon, PIN. One plain-words line per row in the report (what differs: field/label/message/button/spacing). Rows that show the same "link not valid" card on both sides: `WRONG STATE`, rerun that single case once with `PARITY_ONLY=<name>`, else mark it.
7. Gate. `source scripts/e2e/parity_env.sh` must exist (it does). `grep -n '"[A-Z]")' scripts/e2e/parity_cases.py | head` to see which groups have cases; create `scripts/e2e/parity_gate.sh` (then `chmod +x`) with exactly (drop group letters with no case):
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
   Prove the wiring once, narrowed: `PARITY_ONLY=g-hub-claimed PARITY_WIDTHS=390 bash scripts/e2e/parity_gate.sh 2>&1 | tail -15` (a line `GATE: PASS` or `GATE: FAIL` appears; do NOT run the full gate).
8. Mark 2042c: line 3 of `docs/tasks/2042c-guest-parity-inspect-gate.md` becomes `Status: replaced by 2057`. Run `python3 scripts/context_lint.py 2>&1 | tail -3`.
9. Write `docs/tasks/2057-report.md` (600 tokens): totals for H and P, the visible rows with plain-words causes, WRONG STATE rows, the gate command `bash scripts/e2e/parity_gate.sh 2>&1 | tail -15` and when to run it (before a deploy, owner or CI). Exclusions: anonymous pages (landing, login, signup, legal, pruvodce, /p/{slug}) by owner scope; retired features (booking site, payments). Commit by explicit path with the trailers.

## 5. Do not touch

`App/app/**`, `go/**`, other cases and seeds, `page_parity_audit.py`, `go_page_parity_screenshots.py`. A visible row is reported, never silenced or "fixed" here.

## 6. Commands

The commands in steps 3 to 8. Never the full pytest or Go suite.

## 7. Acceptance

- [ ] PIN pass runs (no sqlite traceback) and lists rows.
- [ ] `g-guide-apt` and `g-leon-apt` render the real guide, not "not valid"; seed prints `guide live: True`.
- [ ] Group H and P reports reviewed (at most 15 images); every visible row has a cause or `WRONG STATE`.
- [ ] `parity_gate.sh` executable, wiring proven; 2042c marked replaced; `context_lint` passes.

## 8. Stop and ask

Precondition fails; anchor not found; `{gtok}` cannot be wired without editing `fill()` beyond one line; 25 tool calls (commit, report what is left).

## 9. Report

`docs/tasks/2057-report.md`, 600 tokens at most.
