# 0008: TTLock fact sheet, fill the gaps (docs only)

Status: todo
Depends on: none | Base commit: see branch | Branch: task/0008-ttlock-fact-sheet
Executor: Cursor local agent (composer, Kimi or GLM) | Fits one session

## 1. Objective

`docs/TTLOCK.md` already holds the TTLock facts the owner supplied. Its last section lists 7 facts the supplied docs do not state. Answer each one from the official TTLock docs, with the URL of the page it came from.

## 2. Context

- Read `docs/TTLOCK.md` in full (it is short). Do not change any existing fact. Only replace items in the section "Not stated in the supplied docs", and add a source line for the new pages.
- Only pages on `https://euopen.ttlock.com` or `https://open.ttlock.com` count as a source. Third-party clients, blogs, forums and manuals do not.
- Rule 3 (public repo): no client id, secret, token, lock id, account name or passcode anywhere. Use the docs' placeholder values only.
- Rule 4: no new dependency. This task adds no code.

## 3. Files

| Path | Action | What |
|---|---|---|
| `docs/TTLOCK.md` | edit | Answer the 7 open items, add the new sources |
| `docs/tasks/0008-report.md` | create | Report, §9 |
| `docs/tasks/0008-ttlock-fact-sheet.md` | edit | `Status:` line only |

No other file may change.

## 4. Steps

1. For each numbered item in "Not stated in the supplied docs", find the official page. Use the docs' real endpoint path even if it differs from the guess in the item.
2. Move each answered item into the section it belongs to (a new `## Lock list` or `## Passcode list` section is fine, placed before "Not stated"), as bullets ending in `(source: <url>)`. For the lock list and the passcode list, give the parameters and the response fields, including paging.
3. Leave an item under "Not stated in the supplied docs" only if the official docs really do not say. Write one line on what you searched.
4. Item 3 (admin sharing) and item 5 (moving a random code) usually need a real lock. If the docs do not settle them, leave them listed for the owner test.
5. Run the lint (§6). Set `Status: review`. Write the report. Open one PR.

## 5. Do not touch

`App/`, `docs/plans/`, `docs/context/`. Existing facts in `docs/TTLOCK.md`. Rule 3.

## 6. Commands

From the repo root: `python3 scripts/context_lint.py`. Expected last line: `context lint: OK`. No pytest run (no code change).

## 7. Acceptance

- [ ] Every new bullet ends with `(source: https://euopen.ttlock.com/...)` or `(source: https://open.ttlock.com/...)`.
- [ ] Items 1, 2, 6 and 7 are answered, or each has a "searched: ..." line.
- [ ] `git diff --stat` shows only the files in §3.
- [ ] `git diff docs/TTLOCK.md` deletes no line outside "Not stated in the supplied docs".

## 8. Stop and ask

Stop, and write the report, if:

- the official doc hosts cannot be reached (say which URL failed);
- an official page contradicts an existing fact in `docs/TTLOCK.md` (quote both, change neither);
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

- `docs/TTLOCK.md`: open 2 of the new source URLs and compare.

## Owner steps

Two checks on one real lock, in the TTLock phone app. Each takes about 10 minutes.

**A. Remote delete reaches the lock.**

1. Tap the lock, then **Passcodes**, then **Generate Passcode**, then **Timed**. Start at the next full hour, end 2 hours later. Save it. Do not type it yet.
2. Walk out of Bluetooth range. In the app, delete that passcode.
3. After the start time, type the code on the lock. Write down whether the door opened. It should not.

**B. A shared admin can make codes** (only if you want the separate UbyHost account, plan §8.2).

1. Create a second TTLock account (a spare e-mail).
2. From your main account, tap the lock, then **Send eKey**, enter the second account, and turn on **Authorized admin**. Send it.
3. Log in to the TTLock app with the second account. Tap the lock, then **Passcodes**, then **Generate Passcode**. Write down whether it lets you create a timed code.

Send the orchestrator the results of A and B.
