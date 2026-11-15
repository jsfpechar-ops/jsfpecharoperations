# 1791: Stripe key/mode guard (key prefix and webhook livemode)

Status: todo
Depends on: none | Base commit: <sha of branch tip at start> | Branch: task/1791-stripe-key-mode-guard
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier: B (payments). Plan: docs/plans/ai-payments-hardening.md, P1 item 1.

Overlap order: **1791 goes first.** Briefs 1792 and 1793 also edit `go/internal/payments/booking_webhook.go`. This brief does NOT edit that file or its test (the livemode check sits one level up in `webhook.go`, before `booking.Process`), so 1792/1793 rebase with no conflict from it. Only possible shared file: `webhook.go` (1793 may edit it; 1791 lands first).

## 1. Objective

Refuse a Stripe secret key whose prefix does not match `UBYHOST_STRIPE_MODE`, and ignore any signed webhook event whose `livemode` does not match the mode. A test key in live mode (or the reverse) must never reach Stripe, and a mismatched event must never change the database.

Decisions (stated here so Haiku does not design):
- Mode `test` needs `sk_test_` or `rk_test_`; mode `live` needs `sk_live_` or `rk_live_`. Restricted keys (`rk_`) are accepted because Stripe recommends them; they follow the same mode rule.
- Key mismatch: `guard` logs one line (never the key) and returns `ErrStripeOff`, the same as mode off, so no caller changes (fail closed, no Stripe call, no usage count).
- Webhook mismatch: log and answer **200 "ignored"** (not 4xx/5xx). Reason: a mode mismatch is a configuration error that a Stripe retry cannot fix; 5xx would make Stripe retry for days and disable the endpoint. The check runs after signature verification and before any DB access, so a mismatch never writes the event row or changes state.
- `livemode` absent from the JSON: not checked (Stripe always sends it; existing fixtures omit it). Pointer type distinguishes absent from false.

## 2. Context

Rules: AGENTS hard rules 1 (payments must not break UbyPort filing: this change touches only payments code), 3 (no real keys; use fake `sk_test_...` strings), 11 (Go).

`go/internal/payments/onboarder.go` lines 95-101 (guard start):
```go
func (s *StripeOnboarder) guard(ctx context.Context) (string, string, error) {
	mode := s.mode()
	key := strings.TrimSpace(s.Getenv("UBYHOST_STRIPE_SECRET_KEY"))
	if (mode != "test" && mode != "live") || key == "" {
		return "", "", ErrStripeOff
	}
	stamp := stampAt(s.Now())
```
(`log` is NOT imported in onboarder.go (verified): add `"log"` to its import block, in alphabetical order.)

`go/internal/payments/webhook.go` lines 75-81:
```go
type stripeEvent struct {
	ID   string `json:"id"`
	Type string `json:"type"`
	Data struct {
		Object map[string]any `json:"object"`
	} `json:"data"`
}
```
and lines 139-146:
```go
		event, err := verifyEvent(raw, sig, secret, at)
		if err != nil {
			log.Printf("stripe webhook signature rejected")
			text(w, http.StatusBadRequest, "bad signature")
			return
		}
		if isBookingEvent(event) {
```
`mode` is already a variable in that closure ("test" or "live" here, since `live` was true to pass the earlier check).

Tests: `go/internal/payments/onboarder_test.go` has `const onboardTestKey = "sk_test_onboarder_secret_0123"`, `onboardEnv(mode, key, extra)`, `newOnboarder(pool, env, fake)`, and `TestStripeOnboarderOffMakesNoCall` (lines ~125-145; cases map `"mode off"`, `"empty key"`; asserts ErrStripeOff, 0 fake requests, 0 `lock_api_usage` rows). `go/internal/payments/webhook_test.go` has `webhookEnv(mode, secret)`, `signedPost(t, h, body)`, `count(t, pool, q, args...)`, and `TestWebhookDatabase` using `testPool(t)`, `testNow`.

## 3. Files

| Path | Action | What |
|---|---|---|
| go/internal/payments/onboarder.go | edit | add `keyMatchesMode`, call it in `guard` |
| go/internal/payments/webhook.go | edit | add `Livemode *bool` to `stripeEvent`; mismatch check after `verifyEvent` |
| go/internal/payments/onboarder_test.go | edit | add cases to `TestStripeOnboarderOffMakesNoCall` and one new table test |
| go/internal/payments/webhook_test.go | edit | add `TestWebhookLivemodeMismatch` |

No other file may change (in particular not `booking_webhook.go`, owned by 1792/1793 after this).

## 4. Steps

1. In `onboarder.go`, replace the guard condition block with:
```go
	if (mode != "test" && mode != "live") || key == "" {
		return "", "", ErrStripeOff
	}
	if !keyMatchesMode(key, mode) {
		log.Printf("stripe key prefix does not match UBYHOST_STRIPE_MODE=%s: refusing", mode)
		return "", "", ErrStripeOff
	}
```
and add below `guard`'s doc comment area (before the `guard` comment) this function:
```go
// keyMatchesMode reports whether the key prefix fits the mode: test needs
// sk_test_ or rk_test_, live needs sk_live_ or rk_live_ (restricted keys
// follow the same rule). It never logs or returns the key.
func keyMatchesMode(key, mode string) bool {
	return strings.HasPrefix(key, "sk_"+mode+"_") || strings.HasPrefix(key, "rk_"+mode+"_")
}
```
2. In `webhook.go`, change the struct to add a field after `Type`:
```go
	Livemode *bool  `json:"livemode"`
```
3. In `webhook.go`, directly after the `verifyEvent` error block and before `if isBookingEvent(event) {`, insert:
```go
		if event.Livemode != nil && *event.Livemode != (mode == "live") {
			log.Printf("stripe webhook ignored (livemode=%t, configured mode=%s): event %s", *event.Livemode, mode, event.ID)
			text(w, http.StatusOK, "ignored")
			return
		}
```
4. `onboarder_test.go`: in `TestStripeOnboarderOffMakesNoCall` add two cases to the `cases` map (they must also return ErrStripeOff with 0 requests and 0 usage rows):
```go
		"test mode with live key":  onboardEnv("test", "sk_live_abc123", nil),
		"live mode with test key":  onboardEnv("live", onboardTestKey, nil),
```
Then add a new test:
```go
func TestKeyMatchesMode(t *testing.T) {
	cases := []struct {
		name, key, mode string
		want            bool
	}{
		{"sk_test in test", "sk_test_a", "test", true},
		{"rk_test in test", "rk_test_a", "test", true},
		{"sk_live in live", "sk_live_a", "live", true},
		{"rk_live in live", "rk_live_a", "live", true},
		{"sk_live in test", "sk_live_a", "test", false},
		{"rk_live in test", "rk_live_a", "test", false},
		{"sk_test in live", "sk_test_a", "live", false},
		{"rk_test in live", "rk_test_a", "live", false},
		{"pk publishable in test", "pk_test_a", "test", false},
		{"no prefix", "abc", "test", false},
	}
	for _, c := range cases {
		if got := keyMatchesMode(c.key, c.mode); got != c.want {
			t.Errorf("%s: got %v, want %v", c.name, got, c.want)
		}
	}
}
```
5. `webhook_test.go`: add (use the same style as `TestWebhookDatabase`; `seedHost` is the helper there):
```go
func TestWebhookLivemodeMismatch(t *testing.T) {
	pool := testPool(t)
	seedHost(t, pool)
	h := func(m string) http.HandlerFunc {
		return WebhookHandler(pool, webhookEnv(m, "whsec_test"), func() time.Time { return testNow })
	}
	ev := func(id string, live bool) []byte {
		return []byte(fmt.Sprintf(`{"id":%q,"type":"account.updated","livemode":%t,"data":{"object":{"id":"acct_1",`+
			`"charges_enabled":true,"payouts_enabled":true,"requirements":{"currently_due":[]}}}}`, id, live))
	}
	// test-mode event at a live endpoint: 200, no event row, no state change.
	if got := signedPost(t, h("live"), ev("evt_lm_a", false)); got != 200 {
		t.Errorf("livemode=false in live mode: %d", got)
	}
	// live event at a test endpoint: same.
	if got := signedPost(t, h("test"), ev("evt_lm_b", true)); got != 200 {
		t.Errorf("livemode=true in test mode: %d", got)
	}
	if n := count(t, pool, `SELECT COUNT(*) FROM stripe_webhook_event WHERE event_id IN ('evt_lm_a','evt_lm_b')`); n != 0 {
		t.Errorf("mismatched events wrote %d rows", n)
	}
	if n := count(t, pool, `SELECT COUNT(*) FROM stripe_account WHERE onboarding_state = 'complete'`); n != 0 {
		t.Errorf("mismatched event mirrored account state")
	}
	// matching livemode is processed.
	if got := signedPost(t, h("test"), ev("evt_lm_c", false)); got != 200 {
		t.Errorf("matching livemode: %d", got)
	}
	if n := count(t, pool, `SELECT COUNT(*) FROM stripe_webhook_event WHERE event_id = 'evt_lm_c'`); n != 1 {
		t.Errorf("matching event rows: %d", n)
	}
}
```
If `seedHost` leaves a `complete` account row already, change the state assertion to compare the count before and after the mismatched posts instead (read it before the first post). Check `seedHost` with one grep first.

## 5. Do not touch

`go/internal/payments/booking_webhook.go` (1792/1793), any Python file, `App/`, migrations, templates. Rules: no real or realistic keys in tests (hard rule 3); never log the key; no new dependency; no push or merge.

## 6. Commands

Go has no row in the Python test-map (the Python row `test_stripe_connect.py` is for the live Python path, which this brief does not change; run nothing there). Run from `go/`:
```
cd go && go build ./... 2>&1 | tail -30
cd go && go vet ./internal/payments 2>&1 | tail -30
cd go && go test ./internal/payments -run 'TestKeyMatchesMode|TestStripeOnboarderOffMakesNoCall|TestWebhookLivemodeMismatch|TestWebhookDatabase|TestBooking' -count=1 2>&1 | tail -30
python3 scripts/context_lint.py 2>&1 | tail -30
```
Expected: build and vet silent, tests `ok`. If tests need Postgres (`testPool`) and it is unavailable, the DB tests will skip: report that as `blocked`, do not claim green (skips count as not passing).

## 7. Acceptance

- [ ] `grep -n 'keyMatchesMode' go/internal/payments/onboarder.go` shows the helper and its call in `guard`.
- [ ] `grep -n 'Livemode' go/internal/payments/webhook.go` shows the field and the check before `isBookingEvent`.
- [ ] `git diff --stat` lists only the four files in section 3.
- [ ] The go test command prints `ok` with 0 skipped DB tests; every case named above ran (`go test -v ... | grep -c PASS`).
- [ ] `git diff -- go/internal/payments/booking_webhook.go` is empty.
- [ ] `grep -rn 'sk_live_' go/internal/payments/*.go` shows only the fake `sk_live_abc123`/`sk_live_a` strings in tests.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found verbatim (especially the `guard` block or `stripeEvent`);
- a test fails twice, or Postgres is unavailable so DB tests skip;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`);
- a file outside section 3 needs a change (e.g. a caller of `guard` that distinguishes `ErrStripeOff` from a new error: here none should);
- you think `livemode` absent should be refused, or the mismatch should be non-2xx: that is an owner decision, do not change it;
- you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/1791-report.md` (600 tokens at most) and set `Status: review`: files changed (`git diff --stat`), each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

`go/internal/payments/onboarder.go` (guard), `go/internal/payments/webhook.go` (mismatch placement: must be after signature check, before `booking.Process` and `processEvent`).

## Owner steps

1. Before switching to live: set `UBYHOST_STRIPE_MODE=live`, a key starting `sk_live_` (or `rk_live_`), and the live-mode webhook secret together. A mixed set now makes payments act as "off" and the log says why.
2. After deploy, in the Stripe dashboard confirm the webhook endpoint is the one for the same mode as the server; test events sent to a live server are logged and ignored (200), not retried.
