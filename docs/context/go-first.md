# Go first

Owner, 2026-11-13. Python is being retired ([plan](../plans/go-full-move.md)). What is not in Go yet: [remaining](../plans/go-full-move-remaining.md).

- **New feature:** Go only. If its page or job is not in Go yet, the port brief comes first and the feature brief names it in `Depends on`.
- **Bug fix:** fix it in Go. If the area is not in Go yet, port it first. If Python still serves that path or job in production (not in `UBYHOST_GO_PATHS` or `UBYHOST_GO_JOB_KINDS`), the brief's owner steps include the switch, so the fix reaches production.
- **Python may change only for:**
  1. Port plumbing a Go brief needs: reading a switch, golden scripts, parity tests, removal PRs.
  2. Dependency and security bumps.
  3. A filing, security or data-loss bug on a path Python still serves: the smallest fix goes into Python too, in the same brief as the Go fix.
- A brief whose section 3 names a file under `App/app/` says which of the three applies. If none does, the reviewer rejects it.
- A `todo` brief from before this rule that changes Python behaviour is not run as is: the orchestrator re-targets it to Go first.
- Brief writer by tier ([workflow](workflow.md#roles-and-models)): Opus for tier A, Sonnet for B and C. If unsure of a tier, take the higher one.
