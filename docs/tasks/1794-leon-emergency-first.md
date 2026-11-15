# 1794: Leon answers danger words first (blocked: no go-first exception fits)

Status: blocked
Depends on: owner decision (see §2) | Base commit: n/a | Branch: task/1794-leon-emergency-first
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

Tier A (guest-facing safety). Plan item L1 in [ai-payments-hardening](../plans/ai-payments-hardening.md#l1-emergency-first-do-before-the-port-go-first-exception-to-be-named-in-the-brief).
Do not run this brief. It holds no implementation steps until the owner decides §2.

## 1. Objective

A guest who writes a danger word ("fire", "gas", "heart attack") must always get the fixed 112 reply and the host must always get an urgent question, even when the chat is paused, rate-limited or busy. Today those three checks return first, so the guest gets "paused" or "slow down" instead of 112.

## 2. Context

**Bug, confirmed (no plan differences in the lines):** `App/app/leon.py` `reply()` lines 527-538 return `paused`, `slow_down` and `busy` before any danger check. `looks_dangerous()` (line 166) is called only in `_answer()` when the model gave no verdict (line 619). `_DANGER` (lines 113-117) has no "heart attack", "can't breathe", "choking", "overdose" in any of en, cs, de, es, fr, uk. The guest chat routes (`/g/{token}/leon`, `/l/{token}/{reservation_id}/guide/leon`) are served by Python only: `App/app/routes/guest_leon.py`, 4 routes, 0 in Go (route ledger in go-full-move-remaining). Go has only the host wizard (`go/internal/web/ai/leon_handlers.go`, `leon_try.go`).

**Why blocked.** [go-first](../context/go-first.md) allows Python changes only for:

1. Port plumbing a Go brief needs. Does not fit: this is a behaviour fix, not plumbing.
2. Dependency and security bumps. Does not fit: no dependency changes.
3. "A filing, security or data-loss bug on a path Python still serves: the smallest fix goes into Python too, in the same brief as the Go fix." Does not fit, for two reasons. A missed 112 reply is a life-safety bug, not a filing, security (access, secrets, auth) or data-loss bug; calling it "security" stretches the word the reviewer is told to check. And the exception says "too, in the same brief as the Go fix": there is no Go guest chat to fix.

The rule says a brief with an `App/app/` file and no fitting exception is rejected, so this brief stays a stub.

**Recommendation (owner).** Add one exception line to go-first.md and one `[workflow]` line to decisions.md, for example: "4. A guest-safety bug (an emergency reply that does not reach the guest or the host) on a path Python still serves: the smallest fix goes into Python now, even with no Go version yet; the Go port must carry the same fix and tests." Then this brief is rewritten as the Python fix. Waiting for the port instead (L2) leaves guests without a 112 reply while paused or busy for the whole port.

**Notes for the rewrite (checked in the code):**

- Run `looks_dangerous(text)` right after the empty / too-long check in `reply()`. If it matches, skip paused, rate limit and busy, store the guest message, open an urgent question with `_open_question(..., urgent=True, triaged=False)`, and reply with `emergency_text(lang, cards)` (`leon_emergency` copy exists in all six languages: `i18n.py`, `guest_uk_i18n.py`). This makes no model call.
- Bypass only when the model would not be asked (paused, slow down, busy; cap and budget already reach the danger path). In the normal path, keep asking the model, so "is smoking allowed" or "how do I light the gas hob" still get a normal answer. The `_DANGER` comment on line 112 already says this.
- Two more gaps found: a danger word repeated within the same conversation hits `_open_twin` (line 588) and gets "asked already" instead of 112; a message over 500 characters (`MAX_MESSAGE_CHARS`) gets `too_long` even when it holds "fire". The rewrite should decide both.
- Tests go in `App/tests/test_leon.py` (test-map row "Guest bot (Leon)"): one per new keyword per language, and one each for paused, slow_down and busy with a danger word, checking that the reply kind is `emergency` and an urgent `guest_question` row exists.

**L2 alternative (port first):** the guest chat is about 860 lines of Python (`leon.py` 744 plus `guest_leon.py` 117) with templates, JS and 8 test files. That means about 3-4 tier-A Haiku briefs (reply state machine, routes and pages, parity tests, the `UBYHOST_GO_PATHS` switch). The fix lands only after all of them ship.

## 3. Files

None until §2 is decided. No file may change.

## 4. Steps

None. Blocked.

## 5. Do not touch

Everything. Hard rules 1, 2, 7, 8 and 11 apply to the rewrite.

## 6. Commands

None.

## 7. Acceptance

- [ ] Owner decision line for a guest-safety exception exists in `docs/context/decisions.md` (`grep -n 'guest-safety' docs/context/decisions.md`), or the owner picks L2 first.

## 8. Stop and ask

This brief is blocked. An executor that opens it stops at once and reports `blocked: needs owner go-first decision`.

## 9. Report

Blocked: do not run. The orchestrator rewrites this brief after the owner decides on the go-first exception.
