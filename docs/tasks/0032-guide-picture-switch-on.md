# 0032: Guide pictures show the privacy switch on

Status: todo
Depends on: owner screenshot (Owner steps 1-3) | Base commit: 20413d1 | Branch: task/bundle-0025-0031 (PR #332, commit on top of it)
Executor: Cursor local agent (composer, Kimi or GLM) | Fits one session

## 1. Objective

The TTLock form picture in the door-lock guide shows *Manage their own users only* switched **off**, while step 6 says to switch it **on**. Hosts copy pictures, and with the switch off UbyHost sees the host's own codes. Replace the picture with the owner's screenshot that shows it on, and fix the misplaced marker in the home picture.

## 2. Context

- Rule 2 (privacy first): UbyHost must see only the codes it creates.
- `App/app/guide_i18n.py` line 46, verbatim: `"guide.door_codes.step6": 'Switch on Manage their own users only, so UbyHost sees only the codes it creates itself and never your own codes or the codes of other people. Then tap Send.',`
- `App/app/static/guide/ttlock-home.png`: the marker "1" arrow points at the **Remote** row. The alt text (`guide.door_codes.shot_home`) says "1 Authorized Admin". The red box is already round Authorized Admin; only the "1" circle and arrow sit in the wrong place.
- `App/tests/test_ttlock_guide_pictures.py` requires each picture to be a PNG under 300,000 bytes.
- The owner puts the new screenshot at `docs/tasks/0032-screenshots/ttlock-form-switch-on.png` (Owner steps). If it is not there, STOP (§8).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/static/guide/ttlock-form.png` | replace | Owner's screenshot with the switch on, with the same four numbered markers and boxes as the current picture (1 Recipient, 2 Name, 3 the switch, 4 Send), same width (583 px), PNG under 300 KB |
| `App/app/static/guide/ttlock-home.png` | edit | Move the "1" circle and arrow so they point at the Authorized Admin box. Nothing else changes |
| `App/app/templates/guide.html` | edit | Cache-bust: `?v=20261009` becomes `?v=20261010` |
| `docs/tasks/0032-report.md` | create | Report |

No other file may change. Copy text stays as it is.

## 4. Steps

1. `git fetch origin task/bundle-0025-0031 && git checkout task/bundle-0025-0031`
2. Build the new `ttlock-form.png` from `docs/tasks/0032-screenshots/ttlock-form-switch-on.png`: scale to 583 px wide, draw the four markers in the same orange and style as the current picture, save as PNG. Check `stat -c %s` < 300000.
3. Edit `ttlock-home.png`: move marker "1" and its arrow so they line up with the Authorized Admin box (row 2, column 3).
4. In `guide.html`, change `?v=20261009` to `?v=20261010`.
5. Run §6, write the report, commit and push to `task/bundle-0025-0031`.

## 5. Do not touch

Every file not in §3, including `guide_i18n.py`. Hard rules 3 (no personal data in the picture: the Recipient must be the example `hjhfa_uh1234abcd` or blurred, no real phone number or e-mail) and 7.

## 6. Commands

From `App/`: `.venv/bin/python -m pytest tests/test_ttlock_guide_pictures.py tests -q`, all pass, 0 skipped in browser and geometry tests. From the repo root: `python3 scripts/context_lint.py` prints `context lint: OK`.

## 7. Acceptance

- [ ] The form picture shows the switch **on**, with markers 1 to 4.
- [ ] Marker "1" in the home picture points at Authorized Admin.
- [ ] Both PNGs are under 300 KB. No real recipient name, phone or e-mail visible.
- [ ] Screenshots of `/guide#door-codes` at 360, 390 and 1280 px in `docs/tasks/0032-screenshots/`.

## 8. Stop and ask

Stop, and write the report, if: the owner screenshot is missing; an excerpt is not found; a test fails twice; a file outside §3 needs a change; you need merge, secrets or deploy.

## 9. Report

`docs/tasks/0032-report.md` (1,500 tokens at most), `Status: review`: files changed, commands with the last 5 lines of output, §7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

The two PNGs (look at them), `guide.html`.

## Owner steps

1. In the TTLock app open your lock, tap **Authorized Admin**, then **Create Admin**.
2. Choose **Permanent**, type `hjhfa_uh1234abcd` in Recipient and `UbyHost` in Name, and switch **Manage their own users only** on. Do **not** tap Send. Take a screenshot.
3. Send the screenshot to the chat (or put it in `docs/tasks/0032-screenshots/ttlock-form-switch-on.png` on branch `task/bundle-0025-0031`), then run this brief in Cursor.
4. When the report is in, the orchestrator reviews it; then merge PR #332 with `scripts/merge-pr-on-green.sh 332`.
