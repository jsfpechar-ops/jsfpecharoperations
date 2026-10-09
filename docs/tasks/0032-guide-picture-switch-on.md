# 0032: Guide drops the form picture that shows the privacy switch off

Status: review
Depends on: none | Base commit: 20413d1 | Branch: task/bundle-0025-0031 (PR #332, commit on top of it)
Executor: Cursor local agent (composer, Kimi or GLM) | Fits one session

## 1. Objective

The TTLock form picture in the door-lock guide shows *Manage their own users only* switched **off**, while step 6 says to switch it **on**. Hosts copy pictures, and with the switch off UbyHost sees the host's own codes. No screenshot with the switch on can be taken (the owner's account is the lock's admin), so the form picture goes; steps 5 and 6 already say what to do. Also fix the misplaced marker in the home picture.

## 2. Context

- Rule 2 (privacy first): UbyHost must see only the codes it creates.
- `App/app/templates/guide.html`, verbatim: `{% set door_shots = {3: ['home'], 4: ['create-admin'], 5: ['form']} %}`
- `App/app/guide_i18n.py`: the keys `"guide.door_codes.shot_form"` (English, line 54; Czech, line 219).
- `App/tests/test_ttlock_guide_pictures.py`, verbatim: `SHOTS = ("home", "create-admin", "form")` and `assert "{% set door_shots = {3: ['home'], 4: ['create-admin'], 5: ['form']} %}" in template`
- `App/app/static/guide/ttlock-home.png`: the marker "1" circle and arrow point at the **Remote** row. The alt text says "1 Authorized Admin". The red box is already round Authorized Admin (row 2, column 3); only the "1" circle and arrow are in the wrong place. Pictures must stay PNG under 300,000 bytes.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/guide.html` | edit | `door_shots` becomes `{3: ['home'], 4: ['create-admin']}`; `?v=20261009` becomes `?v=20261010` |
| `App/app/guide_i18n.py` | edit | Delete both `guide.door_codes.shot_form` lines (English and Czech) |
| `App/app/static/guide/ttlock-form.png` | delete | |
| `App/app/static/guide/ttlock-home.png` | edit | Move the "1" circle and arrow so they point at the Authorized Admin box. Nothing else changes |
| `App/tests/test_ttlock_guide_pictures.py` | edit | `SHOTS = ("home", "create-admin")`; template assert uses the new `door_shots` line; add `assert not (APP / "static" / "guide" / "ttlock-form.png").exists()` with a comment: the form picture showed the privacy switch off |
| `docs/tasks/0032-report.md` | create | Report |

No other file may change.

## 4. Steps

1. `git fetch origin task/bundle-0025-0031 && git checkout task/bundle-0025-0031`
2. Make the edits in §3, in that order.
3. Run §6, write the report, commit and push to `task/bundle-0025-0031`.

## 5. Do not touch

Every file not in §3, including step texts in `guide_i18n.py`. Hard rules 2, 3, 7.

## 6. Commands

From `App/`: `.venv/bin/python -m pytest tests -q`, all pass, 0 skipped in browser and geometry tests. From the repo root: `python3 scripts/context_lint.py` prints `context lint: OK`.

## 7. Acceptance

- [ ] `/guide#door-codes` shows pictures under steps 3 and 4 only.
- [ ] Marker "1" in the home picture points at Authorized Admin.
- [ ] `git grep -n "shot_form\|ttlock-form"` returns only the new test line.
- [ ] Screenshots of `/guide#door-codes` at 360, 390 and 1280 px in `docs/tasks/0032-screenshots/`.

## 8. Stop and ask

Stop, and write the report, if: an excerpt is not found; a test fails twice; a file outside §3 needs a change; you need merge, secrets or deploy.

## 9. Report

`docs/tasks/0032-report.md` (1,500 tokens at most), `Status: review`: files changed, commands with the last 5 lines of output, §7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

`ttlock-home.png` (look at it), `guide.html`, the test file.

## Owner steps

1. Run this brief in Cursor.
2. When the report is in, the orchestrator reviews it; then merge PR #332 with `scripts/merge-pr-on-green.sh 332`.
