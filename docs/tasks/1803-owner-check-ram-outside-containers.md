# 1803: Owner check: RAM used outside containers

Status: todo
Depends on: none | Base commit: current tip of the working branch | Branch: none (no code, no PR)
Executor: Owner (Josef). Not a Haiku brief: Haiku never runs server commands (executor.md "Never").
Tier: C (read-only server commands, nothing changes)

## 1. Objective

The owner runs one read-only command twice on the server (once idle, once during a deploy) and pastes both outputs back, so the orchestrator can explain the about 800 MB of RAM used outside containers (1.4 GB at the peak). Image builds on the server are the suspect.

## 2. Context

[optimization-wins](../plans/optimization-wins.md) section 1: host RAM averages 1761 MB; the containers add up to about 960 MB; the rest is unexplained. Lane A, brief 1803: "Cause written into known-issues". The answer decides whether brief 1800 (build images in CI) is the fix or whether something else holds the memory.

The command only reads. It changes nothing, restarts nothing and prints no guest data (process names and memory sizes only).

## 3. Files

| Path | Action | What |
|---|---|---|
| `docs/context/known-issues.md` | edit (orchestrator, after the owner replies) | one entry with the finding |

No other file changes. No code.

## 4. Steps

Do these in order. If a step does not work as written, stop and send what you see.

**Part A: idle (nobody deploying)**

1. Open a terminal on your computer and log in to the server the way you always do (the same way you log in to deploy).
2. Go to the app folder, the same folder where you start a deploy.
3. Wait until no deploy is running and nobody is using the host pages heavily (early morning is fine).
4. Copy this line exactly, paste it, press Enter:

   `free -m; ps -eo rss,comm --sort=-rss | head -15`

5. Select all of the text it prints. Copy it. Paste it into the chat and write "IDLE" above it.

**Part B: during a deploy**

6. Open a second terminal window and log in to the server there too.
7. In the first window, start your deploy as you always do. Do not wait for it to finish.
8. About 1 to 2 minutes after the deploy starts (while it prints "Building image" or similar), go to the second window and run the same line again:

   `free -m; ps -eo rss,comm --sort=-rss | head -15`

9. If the line prints an error such as "connection lost", the server may be out of memory: write that down and tell me. That is also an answer.
10. Wait for the deploy to finish in the first window.
11. Copy the output of step 8 into the chat and write "DURING DEPLOY" above it.

## 5. Do not touch

Nothing on the server is changed. The owner only reads.

## How the orchestrator reads the result

- `free -m`: the "used" column is the host total. "available" is what is really free. "Swap" 0 means no safety buffer.
- `ps`: the first number is memory in KB per process, the second is its name. Add up names that belong together (all `dockerd`, `containerd`, `buildkitd`, `docker`, `postgres`, `python`, `java`).
- Reading rules:
  - Idle `used` about 1.7 GB with the containers listed in section 1 adding up to about 960 MB: the 800 MB gap shows up as `dockerd`, `containerd`, `systemd-journald`, `amazon-ssm-agent`, `snapd` or kernel cache. Name the biggest one.
  - During the deploy a `buildkitd`, `docker build`, `pip`, `go`, `node` or `cc1` process appears with several hundred MB, or `used` rises by 400 MB or more: image builds on the server are confirmed. Brief 1800 is the fix.
  - During the deploy `used` rises little and the 800 MB is already there when idle: builds are not the cause; write the biggest idle process as the finding and open a follow-up.
  - "buff/cache" is not a problem by itself (the kernel gives it back); only "available" counts.
- No guest data appears in this output. If anything looks like a name, an address or a document number, do not paste it and tell me.

## 6. Commands

Only the command in section 4. No tests.

## 7. Acceptance

- [ ] The owner pasted both outputs (IDLE and DURING DEPLOY) into the chat.
- [ ] The orchestrator wrote one entry in `docs/context/known-issues.md`: date, the biggest non-container process idle and during deploy (name and MB), and the verdict (builds confirmed, or not).
- [ ] The orchestrator ran `python3 scripts/context_lint.py 2>&1 | tail -10` clean.

## 8. Stop and ask

- The command prints an error, or the second terminal hangs for more than two minutes: stop and paste what you see.

## 9. Report

No `1803-report.md` from a Haiku. The orchestrator writes the known-issues entry (5 lines at most) and sets this brief's Status to `done`.

## Open questions for the orchestrator

- None found in the files. If the owner's server has no swap and the second terminal hangs during the deploy, treat that as a result, not an error.
