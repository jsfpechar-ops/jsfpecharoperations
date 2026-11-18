# 1856 report

Status: blocked

## Lanes landed (this PR)

- Planning from `cursor/planning-consolidated-2385` (briefs 1855–1858, autopilot plan, status/decisions)
- **1855** merged: `go/internal/web/stays/*` query/view model

## Blocker

`stays.List` returns `calendar.AlertProgress` only. `reservations.html` needs per-row guest names, `reservation.summary`, `not_registered`, `deadline_cell` (`FiledAt`/`ByHand`), and `send_controls` for `ready_send_count`. Brief 1856 §3 names only `stays.List`; §5 forbids layout changes. Unblock in **1855b** (extend row model) then re-run 1856.

Evidence: `/cursor/stores/bc-1f0dcaf8-602c-4bf8-9bd7-7121fcecfa4f/internal/1856-stays-list-blocker.md`.

## Commands (1855)

```
cd go && go test ./internal/web/stays/... 2>&1 | tail -30
ok  	.../go/internal/web/stays	0.010s
python3 scripts/context_lint.py 2>&1 | tail -30
context lint: OK
```

## Not started

1857, 1858; hide Payments (A2); entry 1660+.

## Owner steps

None for this partial PR.