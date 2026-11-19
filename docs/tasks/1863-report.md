# 1863 report: stay settings save (POST)

Branch: `task/1860-1864-stay-page` | Status: **review**

## Files

Sidecars (10× MANIFEST `OK`): `post.go`, `filing.go`, `post_test.go`, `stayupdate/i18n_keys.txt`; `open_alert_export*.go`, `expire_on_cancel_export*.go`; `register_web_staydetail_test.go`; `test_1863_stay_detail_post_go_parity.py`. Edits: `handlers.go` (POST route), `register_web_staydetail.go` (comments), `i18n_keys.txt` (+two flash keys), `i18n.json`, `stayupdate/i18n.json`.

## Commands (last lines)

```
go vet/test staydetail, ubyport, ical, cmd/ubyhost-web: ok | gofmt -l: (empty)
i18n --check: exit 0
DB (postgres://postgres:ubyhost@127.0.0.1/postgres): all TestSave*, wrapper tests PASS, 0 skipped
parity UBYHOST_GO_PATHS=/__go_test__: 11 passed in 4.43s, 0 skipped
go_parity_check --paths /reservations/1: 1 entries, 2 method/route pairs, 0 missing
context lint: (with step 7)
```

## §7

- [x] Ten sidecar checksums OK; no post-copy edits to sidecar bodies.
- [x] Vet, gofmt, unit tests clean; every `TestSave*` and both wrapper DB tests pass, 0 skipped.
- [x] Parity 11 passed, 0 skipped; only `complete_immediate` enqueues submit on both sides.
- [x] `go_parity_check.py --paths "/reservations/1"`: 0 missing.
- [x] Diff vs series scope: §3 files only (plus status/report).

**Filing behaviour:** unchanged rules; the trigger after a stay-settings save now enqueues the existing submit sweep instead of filing in the request (tested: Go DB tests and Python-vs-Go parity, no UbyPort call).

## Accepted differences (§2)

- Python files during the request; Go enqueues `submit`, run by the owner of that job kind within its poll (~30 s). If a sweep row is already open, the next scheduled sweep (`UBYHOST_SUBMIT_SWEEP_MINUTES`, 10) files it.
- The sweep checks every automatic apartment; it sends only guests that are due anyway.
- Submission `mode` is `auto`, not `completion_immediate`. A failed sweep raises `sweep_failed:{apartment}`; Go raises `submission_immediate:{apartment}` only when the enqueue fails.
- Non-integer id: Go 404, Python 422; neither saves. `POST /reservations/submit-ready` gets 404 in Go before any check.
- Integer spellings no browser sends (`1_0`, non-ASCII digits): Python reads a number, Go none.

Re-run by a second executor (local PostgreSQL 16, `ubyhost_test`): `TestSave*` 10 PASS, both wrapper tests PASS, 0 skipped; parity with 1861: 14 passed, 0 skipped; `/reservations/1`: 0 missing.

## Deviations

None.

## Questions

None.

## Owner steps

None; switch is 1864 owner steps after merge.