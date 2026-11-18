# 1702d2 report: police-letter connection test on save

Status: review
Executor: Haiku 5.5. Branch: claude/beautiful-archimedes-lxhrit (brief's task/ branch not used, per owner instruction).

## Files (commit 6701a3a, `1702d2 step 1`)

- go/internal/ubyport/readonly.go (new), readonly_test.go (new)
- go/internal/web/properties/apartment_update.go (replaced), apartment_update_test.go (replaced)
- go/internal/web/properties/apartment_update_letter_test.go (new)
- go/internal/web/properties/apartmentupdate/i18n.json, i18n_keys.txt (replaced)

## Commands (last lines)

- Step 0: branch ok; `1`; `7`; `3`; four `: OK`.
- Step 1: seven `: OK`.
- Step 2 (gofmt, build, vet): no output.
- Step 3: CI only (no App/.venv).
- Step 4: PostgreSQL 16 on port 56331, started, stopped and removed.
- Step 5: `ok` for properties, palette, cmd/ubyhost-web, ubyport; the twelve named tests `--- PASS`.
- Step 5 SKIP count: `0`.
- Context lint: `context lint: OK`.

## Checklist (§7)

- [x] Step 0 and step 1 hashes
- [x] Step 2 empty
- [ ] Step 3 (CI only)
- [x] Step 5 four `ok`, named tests PASS, SKIP 0
- [x] Commits limited to §3 paths
- [x] No App/, no UBYPORT_GO_PATHS, no existing ubyport filing files changed

## Rule 2 reason

The Go connection test sends three read-only calls to the UbyPort host that Python and the Go filing path already use; no new destination.

## Deviations

Done: steps 0 to 2, 4, 5, 7. Step 3 CI only. Step 6 UX pending until 1705.

## Accepted differences (from the brief)

- An unreadable XML answer is `unreachable` in Go (500 in Python).
- `MaxBatchSize` uses `strconv.Atoi`; audit text only.
- `errorSeverity` accepts one Unicode `Nd` digit, not superscripts.
- Verified time is the request time, not `utcnow()`.

## Owner steps left

None. UX pending until 1705. 1702e (wizard posts) is next.
