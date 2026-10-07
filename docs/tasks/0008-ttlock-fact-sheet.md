# 0008: TTLock fact sheet (spike, docs only)

Status: todo
Depends on: none | Base commit: 6a22fbf | Branch: task/0008-ttlock-fact-sheet
Executor: Cursor local agent (composer, Kimi or GLM) | Fits one session

## 1. Objective

Write `docs/TTLOCK.md`, a fact sheet of the TTLock Open Platform behaviour that the door-code feature depends on. Every fact gets the URL of the official doc page it came from. The plan in `docs/plans/ttlock-door-codes.md` picks its endpoint from these facts, so a guess here becomes a locked-out guest later.

## 2. Context

- Plan: `docs/plans/ttlock-door-codes.md`, sections "Verified facts" and "Open facts". Do not change the plan. Write facts only in `docs/TTLOCK.md`.
- Official docs live at `https://euopen.ttlock.com` (EU) and `https://open.ttlock.com`. Only use pages on those two hosts. Third-party clients, blogs and forum posts do not count as a source.
- Rule 3 (public repo): no client id, secret, token, lock id, account name or passcode in any file. Use the doc examples' placeholder values only.
- Rule 4: no new dependency. This task adds no code.

Already verified (do not re-research, copy into the sheet with the source "official `/v3/keyboardPwd/get` page"):

- `get` returns a 6 to 9 digit random code made in the cloud, no gateway needed, not customisable.
- Validity is accurate to the hour (19:20 becomes 19:00).
- Type 3 (period) must be used at least once within 24 h after the start time, or it is invalidated.
- Response `{"keyboardPwd": "0563456", "keyboardPwdId": 10236}`. The code is a string and can start with 0.

## 3. Files

| Path | Action | What |
|---|---|---|
| `docs/TTLOCK.md` | create | The fact sheet, format in step 2 |
| `docs/tasks/0008-report.md` | create | Report, §9 |
| `docs/tasks/0008-ttlock-fact-sheet.md` | edit | `Status:` line only |

No other file may change.

## 4. Steps

1. Read the official page for each endpoint and answer each question below. The paths below are the orchestrator's best guess. If the docs use a different path, use the docs' path and note it. Write "not stated in the docs" when the page does not say. Never fill a gap from memory.
   - **OAuth** (`/oauth2/token`): grant types, parameters (is the password md5?), `expires_in` value, whether a refresh returns a new `refresh_token` and whether the old one stops working.
   - **Error codes** (the global error code page): the exact meaning of 10003, 10004, 10007, and every code that means "access token expired or invalid" or "refresh token invalid". Also the code for "lock not connected to a gateway", if one exists.
   - **Add custom passcode** (`/v3/keyboardPwd/add`): `addType` values, whether type 2 needs a gateway, whether the 24 h first-use rule applies, allowed code length, how to set a period.
   - **Delete passcode** (`/v3/keyboardPwd/delete`): `deleteType` values. Does deleting a `get` random code via the cloud without a gateway stop the lock from accepting it? Quote the exact sentence if the docs say.
   - **Change passcode** (`/v3/keyboardPwd/change`): can it move the period of a `get` code? Gateway needed?
   - **List passcodes of a lock** (`/v3/lock/listKeyboardPwd`): parameters, whether it shows the name we set, so a retry can find a code it already created.
   - **Lock list** (`/v3/lock/list`) and **lock detail** (`/v3/lock/detail`): which field says the lock has a gateway (for example `hasGateway`).
   - **Gateway list** (`/v3/gateway/list`): response fields.
   - **Unlock records** (`/v3/lockRecord/list`): does a passcode unlock appear without a gateway? Can we tell that a given `keyboardPwdId` was used?
   - **Rate limits**: any stated request limit per app or per lock.
   - **Hosting and processor**: the company that runs the platform, where `euapi.ttlock.com` data is stored, and the privacy policy URL.
2. Write `docs/TTLOCK.md` with these sections, in this order. Each fact is one bullet ending in `(source: <url>)`.
   ```
   # TTLock Open Platform: facts UbyHost relies on
   Checked: 2026-10-07 by task 0008. Re-check before changing App/app/ttlock.py.
   ## Auth and tokens
   ## Error codes
   ## Random passcode (get)
   ## Custom passcode (add)
   ## Delete and change
   ## Finding codes and locks
   ## Unlock records
   ## Limits
   ## Processor and hosting
   ## Not stated in the docs
   ```
   The last section lists every question from step 1 that the docs do not answer.
3. Run the lint (§6).
4. Set `Status: review` in this brief. Write the report. Open one PR.

## 5. Do not touch

`App/`, `docs/plans/`, `docs/context/` (the orchestrator updates status and decisions after review). Rule 3: no secret or account data anywhere.

## 6. Commands

From the repo root: `python3 scripts/context_lint.py`. Expected last line: `context lint: OK`. No pytest run is needed (no code change).

## 7. Acceptance

- [ ] `docs/TTLOCK.md` exists with the 10 sections in step 2, in order.
- [ ] Every bullet outside "Not stated in the docs" ends with `(source: https://euopen.ttlock.com/...)` or `(source: https://open.ttlock.com/...)`. Check: `grep -c 'source: https://\(eu\)\?open.ttlock.com' docs/TTLOCK.md` is at least 15.
- [ ] Every question in step 1 is answered or listed under "Not stated in the docs".
- [ ] `git diff --stat` shows only the 3 files in §3.
- [ ] `grep -niE 'client_secret=|accessToken=[^x]' docs/TTLOCK.md` finds no real-looking value.

## 8. Stop and ask

Stop, and write the report, if:

- the official doc hosts cannot be reached (say which URL failed);
- a page contradicts the "Already verified" list in §2 (quote both);
- a file outside §3 needs a change;
- a step is unclear;
- you need credentials, a real lock, push, merge, secrets, SSH or deploy (hand that to the owner).

## 9. Report

Write `docs/tasks/0008-report.md` (1,500 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `docs/TTLOCK.md`: spot-check 3 sources, including the delete and the error-code facts.

## Owner steps

Every lock has a Wi-Fi gateway (owner, 2026-10-07). This test checks that a remote delete reaches the lock. Do it once, on one lock, in the TTLock phone app.

1. Open the TTLock app. Tap the lock. Tap **Passcodes**, then **Generate Passcode**, then **Custom** (or **Timed** if Custom is missing). Set the start to the next full hour and the end 2 hours later. Save it.
2. Walk away from the lock (out of Bluetooth range). In the app, delete that passcode.
3. After the start time, type the code on the lock. Write down whether the door opened. It should not.
4. Send the orchestrator the result of step 3 and which option you used in step 1.
