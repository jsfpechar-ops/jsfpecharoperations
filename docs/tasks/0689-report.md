# 0689 report: Go push review fixes
Status: review

## Files changed
- go/internal/webpush/webpush.go: Send takes ctx first (NewRequestWithContext); new PushHosts and EndpointAllowed (https, no userinfo, default port, host suffix).
- go/internal/webpush/webpush_test.go: ctx arg at call sites; TestEndpointAllowed.
- go/internal/pushsend/pushsend.go: pushHosts removed; allowed() uses webpush.EndpointAllowed (AllowEndpoint override kept); ctx passed from deliver; logs push_transport_error, push_unreadable_device, push_gone, push_refused (no endpoint or keys).
- go/internal/pushweb/pushweb.go: pushHosts and pushHost removed; cleanSubscription uses webpush.EndpointAllowed, same errBadSubscription.

## Commands (last lines)
- gofmt -l . (empty), go vet ./...: clean.
- go test ./internal/webpush/ ./internal/pushsend/ ./internal/pushweb/ ./cmd/... -count=1: ok for all four packages.
- go test ./internal/webpush/ -run TestEndpointAllowed -v: PASS.
- python3 scripts/context_lint.py: "context lint: OK".

## Brief 7 ticked
Tests pass (DB tests skip locally), vet and gofmt clean.

## Deviations
- Worktree is at /tmp/wt0689 as the brief says; the brief copy is not committed.
- Not pushed and no PR opened (executor rule; owner or orchestrator to push).

## Questions
None.

## Owner steps left
- Push branch task/0689-go-push-review-fixes and open the PR.
