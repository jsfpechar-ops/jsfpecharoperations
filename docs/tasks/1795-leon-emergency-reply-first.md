# 1795: Leon emergency reply first (BLOCKED: needs an owner decision)

Status: blocked
Depends on: none | Base commit: n/a | Branch: task/1795-leon-emergency-reply-first
Executor: Haiku 5.5 | Fits one session: not runnable until the owner answers

This is a blocked stub. Haiku must not run it. No steps exist yet.

## 1. Objective

Make a guest who writes a danger word to Leon always get the fixed 112 copy, even when Leon is paused, rate limited, busy, over the cap or out of budget, and tell the host. Source: [ai-payments-hardening, L1](../plans/ai-payments-hardening.md), principle B6.

## 2. Context (what the code does today, checked)

- `App/app/leon.py`, the send-message function (about lines 515-545): `too_long`, then `paused_until` returns `leon_paused`, then `rate_limit.blocked(...)` returns `leon_slow_down`, then `_take_turn` returns `leon_busy`. All return with `store=False` before any danger check. A guest writing "fire" while paused gets the paused text: no 112, nothing stored, host not told.
- `looks_dangerous(redacted)` is only used later, when the model could not read the message (about line 79 of the later range): kind `emergency`, body `emergency_text(lang, cards)`. The cap and budget branches (`reason = "cap"` and the budget check) also sit before it.
- `_DANGER` (lines 113-117) has en, cs, de, es, fr, uk words but misses "heart attack", "can't breathe", "choking", "overdose", "unconscious" (en only has `unconscious`), "gas leak", "carbon monoxide".
- Go mirror `go/internal/web/ai/leon_core.go` holds only `LeonEmergencyText` and the model output kind `emergency`. It has no paused, slow-down or busy handler, so it has no ordering problem to fix; the guest chat handler is not in Go.
- `guest_leon.py` routes are Python-served (`docs/plans/go-full-move-remaining.md` rows for `guest_leon.py`).

## 3. Files

None yet. A Python brief would name `App/app/leon.py` (send-message function, `_DANGER`), `App/tests/test_leon.py` and `App/tests/test_guest_leon_chat.py`.

## Why it is blocked: the exact go-first text

[go-first](../context/go-first.md):

- "**Bug fix:** fix it in Go. If the area is not in Go yet, port it first. If Python still serves that path or job in production (not in `UBYHOST_GO_PATHS` or `UBYHOST_GO_JOB_KINDS`), the brief's owner steps include the switch, so the fix reaches production."
- "**Python may change only for:** 1. Port plumbing a Go brief needs ... 2. Dependency and security bumps. 3. A filing, security or data-loss bug on a path Python still serves: the smallest fix goes into Python too, in the same brief as the Go fix."
- "A brief whose section 3 names a file under `App/app/` says which of the three applies. If none does, the reviewer rejects it."

Exception 3 names filing, security and data-loss bugs. A missing 112 reply is a guest-safety bug, which the text does not name. Exception 3 also wants a Go fix in the same brief, and the guest chat has no Go handler to fix. Exceptions 1 and 2 do not apply. So a Python-only brief would be rejected by the reviewer.

## Question for the owner

Approve a go-first exception for this safety fix, or port the guest chat first?

- If approved: the orchestrator records a decision line in `docs/context/decisions.md` naming the exception ("guest-safety bug on a path Python still serves: smallest Python fix, Go port carries the same order"), then rewrites this brief as a Python fix. Scope then: emergency keyword check first (before paused, slow-down, busy, cap, budget; no model call); fixed 112 copy in the guest's language; host notified through the existing danger path, at most once per conversation per hour (reuse what exists); keyword list extended only in en, cs, de, es, fr, uk; no message text in logs; tests for paused, rate limited, budget exhausted and each new keyword; ordinary message while paused still gets the paused text. The Go port (L2) must carry the same order. Out of scope: the Go port, pause per device, Turnstile, prompt text, new dependency.
- If port first: this brief waits for the L2 port brief, and `Depends on` names it.

## Plan differences

- The plan says the exception is "to be named in the brief"; none in go-first fits, so it cannot be named.
- The Go mirror has no ordering problem (it has no such checks); the plan implies a Go counterpart.

## 4. Steps

None until the owner answers.

## 5. Do not touch

Everything: this is a stub.

## 6. Commands

None yet.

## 7. Acceptance

- [ ] Owner has answered the question; the orchestrator has replaced this stub with a runnable brief.

## 8. Stop and ask

Haiku: do not start. Hand this file back to the orchestrator.

## 9. Report

No report: nothing runs.

## Risk list (for the reviewer)

None yet.

## Owner steps

1. None now. Owner answered 2026-11-16: Go only, no Python exception.

## Owner decision (2026-11-16)

- **Go only.** No go-first exception; `App/app/leon.py` is not changed.
- This brief stays blocked until [1726](1726-go-guest-leon-questions.md) (Go guest Leon chat) is merged. Then the orchestrator rewrites it as a Go brief against the 1726 handler: keyword danger check before the paused, slow-down, busy, cap and budget checks; fixed 112 copy; host notified at most once per conversation per hour; extended keyword list; the tests listed above.
- Until 1726 is live in production the gap stays open: a paused or rate-limited guest who writes a danger word gets no 112 reply.
