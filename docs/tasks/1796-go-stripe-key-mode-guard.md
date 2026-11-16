# 1796: Go Stripe key/mode guard and webhook livemode check

Status: todo
Depends on: none | Base commit: current tip of the working branch | Branch: task/1796-go-stripe-key-mode-guard
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier: A (money path; the orchestrator reads the diff of every file in section 3)

## 1. Objective

Make a Stripe secret key whose prefix does not match `UBYHOST_STRIPE_MODE` count as misconfiguration (Stripe off, one log line), and make the webhook ignore a signed event whose `livemode` does not match the mode. Today a live key under `MODE=test` charges real cards while the rows are stored as `mode=test` ([plan](../plans/ai-payments-hardening.md), P1 item 1).

## 2. Context

Rules (AGENTS.md): 3 no secrets (the log line and the tests never print or contain a real key; fake keys only); 4 no new dependency; 11 Go first (this brief is Go only; the Python side is out of scope, see section 5).

**Anchor 1** `go/internal/payments/onboarder.go`, in `func (s *StripeOnboarder) guard`:

```go
	mode := s.mode()
	key := strings.TrimSpace(s.Getenv("UBYHOST_STRIPE_SECRET_KEY"))
	if (mode != "test" && mode != "live") || key == "" {
		return "", "", ErrStripeOff
	}
```

`guard` is the only place Go reads `UBYHOST_STRIPE_SECRET_KEY`; every Stripe call goes through it, and `ErrStripeOff` is already handled by all callers (connect.go, paylink_routes.go, requests.go).

**Anchor 2** `go/internal/payments/webhook.go`:

```go
type stripeEvent struct {
	ID   string `json:"id"`
	Type string `json:"type"`
```

and, in `WebhookHandler`, right after signature verification:

```go
		event, err := verifyEvent(raw, sig, secret, at)
		if err != nil {
			log.Printf("stripe webhook signature rejected")
			text(w, http.StatusBadRequest, "bad signature")
			return
		}
		if isBookingEvent(event) {
```

The booking branch (booking_webhook.go `Process`, or `forwardToPython`) and `processEvent` both come after this point, so one check here covers every event type and the forward to Python.

**Decision: answer 200 `ignored` with one log line, not 4xx.** The handler already answers 200 "ignored" for mode off, and 200 for a replayed event id and for event types it does not handle. A 4xx or 5xx makes Stripe retry the same event for up to three days and flags the endpoint as failing, and a retry cannot succeed because the mismatch is configuration, not a transient fault. 400 stays reserved for a bad signature.

**Missing `livemode`:** Stripe always sends it. A signed event with no `livemode` field is accepted unchanged (the existing tests post events without it); only an explicit mismatch is ignored.

**Python difference:** Python has no such guard (`App/app/stripe_connect.py` `_api` and `App/app/config.py` only check mode and non-empty key; no `livemode` check anywhere). There is nothing to mirror. Restricted keys (`rk_`) are not used anywhere in the repo today; they are allowed by the prefix rule because the plan names them.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/payments/onboarder.go` | edit | add `keyMatchesMode`; call it in `guard` |
| `go/internal/payments/webhook.go` | edit | add `Livemode *bool` to `stripeEvent`; add `livemodeMatches`; check it after `verifyEvent` |
| `go/internal/payments/onboarder_test.go` | edit | add `TestStripeOnboarderKeyModeMismatch` |
| `go/internal/payments/webhook_test.go` | edit | add `TestLivemodeMatches` and `TestWebhookLivemodeMismatch` |
| `docs/tasks/1796-report.md` | create | the report (section 9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Each must print the stated result, else STOP (section 8):
   - `grep -cF 'if (mode != "test" && mode != "live") || key == "" {' go/internal/payments/onboarder.go` prints `1`
   - `grep -cF 'log.Printf("stripe webhook signature rejected")' go/internal/payments/webhook.go` prints `1`
   - `grep -c 'livemode' go/internal/payments/webhook.go go/internal/payments/onboarder.go` prints `0` for both
   - `echo "${UBYHOST_TEST_DATABASE_URL:+set}"` prints `set` (the database tests skip without it; if empty, STOP and ask the owner for the variable)
1. `onboarder.go`: inside `guard`, immediately after the `if` block quoted in Anchor 1, insert:

   ```go
   	if !keyMatchesMode(mode, key) {
   		log.Printf("stripe off: UBYHOST_STRIPE_SECRET_KEY prefix does not match UBYHOST_STRIPE_MODE=%s (test mode needs sk_test_ or rk_test_, live mode needs sk_live_ or rk_live_)", mode)
   		return "", "", ErrStripeOff
   	}
   ```

   Add this function directly above the `// guard is stripe_connect._api` comment:

   ```go
   // keyMatchesMode reports whether the key prefix fits the mode: sk_ or rk_
   // followed by test_ in test mode, live_ in live mode. A key under the wrong
   // mode could charge real cards while rows are stored as test.
   func keyMatchesMode(mode, key string) bool {
   	return strings.HasPrefix(key, "sk_"+mode+"_") || strings.HasPrefix(key, "rk_"+mode+"_")
   }
   ```

   Add `"log"` to the import block if it is not there (`grep -nF '"log"' go/internal/payments/onboarder.go`). Command: `cd go && gofmt -l internal/payments | tail -5 && go build ./internal/payments/ 2>&1 | tail -30` prints nothing.
2. `webhook.go`: in `stripeEvent`, add a field after `Type`:

   ```go
   	Livemode *bool  `json:"livemode"`
   ```

   Run `gofmt -w go/internal/payments/webhook.go` to align the struct. Add this function after `stripeEvent`'s declaration:

   ```go
   // livemodeMatches: an event that says livemode must say true in live mode and
   // false in test mode. An event without the field is not judged.
   func livemodeMatches(ev stripeEvent, mode string) bool {
   	return ev.Livemode == nil || *ev.Livemode == (mode == "live")
   }
   ```

   Directly after the `if err != nil { ... "bad signature" ... return }` block that follows `verifyEvent` (Anchor 2) and before `if isBookingEvent(event) {`, insert:

   ```go
   		if !livemodeMatches(event, mode) {
   			log.Printf("stripe webhook ignored: event livemode does not match UBYHOST_STRIPE_MODE=%s (event %s)", mode, event.ID)
   			text(w, http.StatusOK, "ignored")
   			return
   		}
   ```

   Nothing is written to `stripe_webhook_event`, `stripe_account`, `payment_request` or the audit log on this path. Command: `cd go && gofmt -l internal/payments | tail -5 && go vet ./internal/payments/ 2>&1 | tail -30` prints nothing.
3. `onboarder_test.go`: append this test (uses the existing `onboardEnv`, `newStripeFake`, `newOnboarder`, `onboardTestKey`, `onboardInt`; the fake Stripe server makes no outside call):

   ```go
   func TestStripeOnboarderKeyModeMismatch(t *testing.T) {
   	pool := testPool(t)
   	onboardSeed(t, pool)
   	fake := newStripeFake(t)
   	cases := map[string]func(string) string{
   		"live key under test mode": onboardEnv("test", "sk_live_fake_0123", nil),
   		"test key under live mode": onboardEnv("live", onboardTestKey, nil),
   		"unknown prefix":           onboardEnv("test", "whsec_fake_0123", nil),
   	}
   	for name, env := range cases {
   		ob := newOnboarder(pool, env, fake)
   		if _, err := ob.OnboardingLink(context.Background(), 1, "https://ubyhost.example"); !errors.Is(err, ErrStripeOff) {
   			t.Errorf("%s: got %v, want ErrStripeOff", name, err)
   		}
   	}
   	if n := len(fake.requests()); n != 0 {
   		t.Errorf("requests = %d, want 0", n)
   	}
   	if n := onboardInt(t, pool, `SELECT COUNT(*) FROM lock_api_usage`); n != 0 {
   		t.Errorf("usage rows = %d, want 0", n)
   	}
   	for _, c := range []struct {
   		mode, key string
   		want      bool
   	}{
   		{"test", "sk_test_a", true}, {"test", "rk_test_a", true},
   		{"live", "sk_live_a", true}, {"live", "rk_live_a", true},
   		{"test", "sk_live_a", false}, {"live", "rk_test_a", false}, {"test", "sk_test", false},
   	} {
   		if got := keyMatchesMode(c.mode, c.key); got != c.want {
   			t.Errorf("keyMatchesMode(%q, %q) = %v, want %v", c.mode, c.key, got, c.want)
   		}
   	}
   }
   ```

   Command: `cd go && go test ./internal/payments/ -run TestStripeOnboarderKeyModeMismatch -count=1 -v 2>&1 | tail -30` shows `PASS`, not `SKIP`.
4. `webhook_test.go`: append these two tests (uses the existing `webhookEnv`, `signedPost`, `seedHost`, `count`, `testPool`, `testNow`; `signedPost` signs with `whsec_test`). The account event matches `acct_1` seeded by `seedHost`, so a wrongly accepted event would flip the account to `complete`:

   ```go
   func TestLivemodeMatches(t *testing.T) {
   	yes, no := true, false
   	for _, c := range []struct {
   		mode string
   		live *bool
   		want bool
   	}{
   		{"test", &no, true}, {"test", &yes, false},
   		{"live", &yes, true}, {"live", &no, false},
   		{"test", nil, true}, {"live", nil, true},
   	} {
   		if got := livemodeMatches(stripeEvent{Livemode: c.live}, c.mode); got != c.want {
   			t.Errorf("livemodeMatches(mode=%s, live=%v) = %v, want %v", c.mode, c.live, got, c.want)
   		}
   	}
   }

   func TestWebhookLivemodeMismatch(t *testing.T) {
   	pool := testPool(t)
   	seedHost(t, pool)
   	body := func(id string, live bool) []byte {
   		return []byte(fmt.Sprintf(`{"id":%q,"type":"account.updated","livemode":%v,"data":{"object":{"id":"acct_1",`+
   			`"charges_enabled":true,"payouts_enabled":true,"requirements":{"currently_due":[]}}}}`, id, live))
   	}
   	for name, c := range map[string]struct {
   		mode string
   		live bool
   	}{
   		"live event under test mode": {"test", true},
   		"test event under live mode": {"live", false},
   	} {
   		h := WebhookHandler(pool, webhookEnv(c.mode, "whsec_test"), func() time.Time { return testNow })
   		if got := signedPost(t, h, body("evt_"+c.mode, c.live)); got != 200 {
   			t.Errorf("%s: status %d, want 200", name, got)
   		}
   	}
   	if n := count(t, pool, `SELECT COUNT(*) FROM stripe_webhook_event`); n != 0 {
   		t.Errorf("mismatched events wrote %d event rows", n)
   	}
   	if n := count(t, pool, `SELECT COUNT(*) FROM stripe_account WHERE onboarding_state = 'complete'`); n != 0 {
   		t.Errorf("mismatched event changed the account")
   	}
   	// A matching event is still processed.
   	h := WebhookHandler(pool, webhookEnv("test", "whsec_test"), func() time.Time { return testNow })
   	if got := signedPost(t, h, body("evt_ok", false)); got != 200 {
   		t.Fatalf("matching event: %d", got)
   	}
   	if n := count(t, pool, `SELECT COUNT(*) FROM stripe_webhook_event WHERE event_id = 'evt_ok'`); n != 1 {
   		t.Errorf("matching event rows: %d, want 1", n)
   	}
   }
   ```

   Check that `webhook_test.go` already imports `fmt` and `time` (`grep -nF '"fmt"' go/internal/payments/webhook_test.go`; it uses both today). Command: `cd go && go test ./internal/payments/ -run 'TestLivemodeMatches|TestWebhookLivemodeMismatch' -count=1 -v 2>&1 | tail -30` shows `PASS`, not `SKIP`.
5. Run the section 6 commands; write the report.

Commit after each step with the message `1796 step k` (one commit for step 0 is not needed).

## 5. Do not touch

- Everything under `App/` (Python stays as is: no filing, security or data-loss bug on a Python-served path justifies a change here; go-first exception 3 does not apply).
- `booking_webhook.go`, `checkout_session.go`, `connect.go`, any migration, `go.mod` and `go.sum`.
- AGENTS.md hard rules in play: 3 (no real or realistic keys in code, tests, logs or the report), 4 (no new dependency), 5 (no schema change).
- No live Stripe call in a test: the tests use the existing fake server and the handler directly.

## 6. Commands

The [test-map](../context/test-map.md) payments row is for Python only; this brief changes Go only, so these run instead (from the repo root):

- `cd go && gofmt -l internal/payments | tail -5` prints nothing
- `cd go && go vet ./internal/payments/ 2>&1 | tail -20` is silent
- `cd go && go test ./internal/payments/ -count=1 -v 2>&1 | grep -c SKIP` prints `0` (needs `UBYHOST_TEST_DATABASE_URL`)
- `cd go && go test ./internal/payments/ -count=1 2>&1 | tail -30` prints `ok`
- `python3 scripts/context_lint.py 2>&1 | tail -10` is clean

## 7. Acceptance

- [ ] A key with the wrong prefix for the mode (and a key with no `sk_`/`rk_` prefix) makes `guard` return `ErrStripeOff`, makes no Stripe request, and adds no `lock_api_usage` row (`TestStripeOnboarderKeyModeMismatch`).
- [ ] The log line names the mode and the required prefixes and never prints the key (`grep -n 'log.Printf.*key' go/internal/payments/onboarder.go | tail -5` shows no `%s` bound to `key`).
- [ ] A signed event with `livemode` opposite to the mode gets 200 `ignored`, writes no `stripe_webhook_event` row and changes no account (`TestWebhookLivemodeMismatch`); a matching event still processes.
- [ ] All existing payments tests still pass; 0 skipped.
- [ ] `git diff --stat` lists only the files in section 3.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt or step 0 check is not as stated;
- a test fails twice;
- `UBYHOST_TEST_DATABASE_URL` is unset;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside section 3 needs a change;
- section 5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1796-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. Section 7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

`go/internal/payments/onboarder.go` (`guard`, `keyMatchesMode`) and `go/internal/payments/webhook.go` (`livemodeMatches` and its call site, which must sit after signature verification and before the booking and `processEvent` branches).

## Owner steps

1. Before setting `UBYHOST_STRIPE_MODE` and `UBYHOST_STRIPE_SECRET_KEY` on the server, check the key starts with `sk_test_` (or `rk_test_`) for `test` and `sk_live_` (or `rk_live_`) for `live`. A mismatched pair now turns Stripe off and logs the reason instead of charging.
2. After deploy, if payments look off, open the `ubyhost-go` log and search for `UBYHOST_STRIPE_SECRET_KEY prefix does not match`.

## Plan differences

- The plan says "check the prefix at startup". The code has no startup hook for Stripe config: the key is read per call in `guard`, so the check lives there (one log line per refused call, no key in it). Startup validation would need a new config-load path and is not worth it for this fix.
- The plan cites `onboarder.go:95-100`; the code is at lines 96-100 (same content). Plan lines for items 2 to 5 were not checked.
- Python has no key-prefix or `livemode` guard, so there is nothing to mirror, and it is deliberately left unchanged.
- The plan says "refuse on mismatch" for the webhook; this brief answers 200 `ignored` (reason in section 2) so Stripe does not retry.

## Owner decisions (2026-11-16)

- **Go only.** No Python change in this brief or as a follow-up.
- **Test database.** CI sets `UBYHOST_TEST_DATABASE_URL` (`.github/workflows/ci.yml`). If the executor has none locally, the new tests skip there: the report must say so, and the PR is ready only when CI shows them run and pass, not skipped.
