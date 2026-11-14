# 1550: Booking site rollout plan: the order in which paths move to Go

Status: blocked — rules 7 and 10 need the browser and geometry tests plus 390/768/1280 screenshots of the Go guest pages, and there is no Go harness for guest pages (brief 1353 recorded the same gap for host pages); this brief is the switch order and checks for the owner and the orchestrator once that harness exists. Do not run as an executor brief.
Depends on: 1540, 1541, 1542, 1543, 1544 | Base commit: none (one big PR) | Branch: the current branch
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier B. Review: Opus orchestrator (rule 10 gate) and the owner.

**One big PR mode.** Work on the current branch. Never create a branch, never push, never open a PR. Commit `1550 step k` after each step that changes a file. Acceptance checks use `git log --oneline --grep='^1550 step'`, not a fixed base commit.

## 1. Objective

State the order and the checks for moving the public booking paths from Python to Go through `UBYHOST_GO_PATHS`, so no path is ever half Go. Nothing here is code.

## 2. Context

Caddy routes by path and ignores the method. I could not read the server's `UBYHOST_GO_PATHS`; I assumed it holds the `1351` entries (`/p/*/*.ics /p/*/b/*/*/calendar.ics /photos/property/*`) and the live payments PNG and webhook entries, and nothing else under `/p/` or `/terms/`. Check it first.

State after briefs 1540 to 1544 (all switched off, all verified in tests):

| Path | Go serves | Python serves | Switch as a whole? |
|---|---|---|---|
| `/terms/booking` | GET (1540) | GET | yes |
| `/p/{slug}/thanks` | GET (1540) | GET | yes |
| `/p/{slug}` | GET (1541) | GET | yes |
| `/p/{slug}/book` | POST (1541) | POST | yes (a GET gets Go's 404, Python's 405) |
| `/p/{slug}/checkout` | POST (1542, 1543) | POST | yes |
| `/p/{slug}/b/{id}/{token}` | GET (1544) | GET | yes |
| `/p/{slug}/b/{id}/{token}/calendar.ics` | GET (1351) | GET | already switchable |
| `/p/{slug}/b/{id}/{token}/cancel` | none | POST | no (1553, blocked) |
| `.../invoice.pdf`, `.../correction.pdf` | none | GET | no (1553, blocked) |
| `/p/{slug}/{token}.ics` | GET (1351) | GET | already switchable |

New routes that go live the moment they deploy only if the server value already covers them (for example a `/p/*` entry); with the assumed value none does.

Suggested order: (1) the pages and the quote step together, `/terms/booking`, `/p/*` limited as below, then (2) checkout, then (3) the manage page, then (4) the webhook (1554). Because Caddy path matchers are not regular expressions, `/p/*` would also send the cancel and PDF paths to Go, where no handler exists. Use these entries instead, one per row above, and test each with curl after the Caddy restart: `/terms/booking`, `/p/*/thanks`, `/p/*/book`, `/p/*/checkout`, `/p/*/b/*/*`. The bare `/p/{slug}` path has no segment-free matcher that excludes its siblings: use the exact entry for each live slug only if Caddy offers exact matching (`/p/old-town`), or leave `/p/{slug}` on Python until a matcher is agreed. Open question for the owner or the orchestrator; I did not verify Caddy's wildcard semantics on the server.

Gate before any switch (rules 7 and 10): the browser and geometry tests and the 390/768/1280 screenshots for each guest page, with the per-page notes written in the PR. This is the blocker: the existing Python browser tests exercise Python, and no Go harness renders the Go guest pages. A later brief should add one (render the Go handlers with the seeded fixture, run Playwright against them).

## 3. Files

None.

## 4. Steps

None.

## 5. Do not touch

Everything.

## 6. Commands

None.

## 7. Acceptance

- [ ] Not applicable.

## Risk list (for the reviewer)

- The Caddy entries (a wrong wildcard sends cancel or PDF requests to Go, which answers 404 to a guest).

## Owner steps

1. Open the server env file and read the `UBYHOST_GO_PATHS` line. Write down the `/p/` and `/terms/` entries it holds.
2. Do not add any entry from the list above until the gate is green and the orchestrator says so. Add one entry per deploy, restart Caddy, open the page in a browser, and remove the entry again if the page looks wrong.


## 8. Stop and ask

Stop, and write the report, if: a file outside section 3 needs a change; a test fails twice; a step is unclear; you reach 25 tool calls or about 50k tokens (report as `blocked`); you need push, merge, secrets, SSH or deploy (hand it to the owner with the exact command).

## 9. Report

Write `docs/tasks/1550-report.md` (600 tokens at most) and set `Status: review`: files changed (none expected), each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps left.
