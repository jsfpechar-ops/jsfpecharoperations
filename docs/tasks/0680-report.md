# 0680 report

Files: `go/internal/palette/slug.go` (new, port of `guest_slug.ensure` and helpers), `slug_test.go` (new, 16 tests in the package), `db.go` (`linkKey` now calls `ensure`; the 0679 TODO is gone), `docs/tasks/0680-go-palette-slug-and-tests.md` (Status line only), this report.

Commands (tails):
- `gofmt -l .` and `go vet ./...` from `go/`: clean, no output.
- `UBYHOST_TEST_DATABASE_URL=postgres://postgres:ubyhost@127.0.0.1/t0679 go test ./internal/palette/ -count=1 -v`: 16 `--- PASS`, grep for SKIP: 0. Tail: `ok  github.com/jsfpechar-ops/jsfpecharoperations/go/internal/palette 8.212s`.
- `python3 scripts/context_lint.py | tail -3`: `context lint: OK` (plus a WARN that App commits touched status.md since its last update; for the orchestrator at review).

Section 7: palette tests pass, 0 skipped; vet and gofmt clean. Not run: the full suite, browser tests (no template or CSS change).

Decided beyond the brief:
- No new dependency, so no `golang.org/x/text` NFKD. Folding uses a hand table for Latin-1 Supplement, Latin Extended-A and a few compatibility forms (ª º ſ ĳ ŉ Ŀ), plus the `_FOLD_EXTRA` list. Czech names match Python. Other diacritics (e.g. Vietnamese, Latin Extended Additional) fold to `-` in Go but to a base letter in Python. Combining marks are dropped only in U+0300 to U+036F.
- The six readable expectations in the table test come from running `_generated_readable` in Python. The 40-character cut case also comes from Python.
- The exact-bytes golden (one signed-in host, no properties) was captured from the Go output and checked by eye for order and no HTML escaping. It was not compared against a live Python run.
- `ensure` runs in a transaction with `pg_advisory_xact_lock(hashtext('apartment_slug'), id)`, retries a code clash 8 times, and on unique violation (23505) returns the current slug, as Python's IntegrityError branch does.
- `created_at` is written as `db.utcnow()` format (second precision, `+00:00`).
- The palette GET now writes a slug for an apartment that has a token and no slug, as Python does.

Not done: nothing from brief section 4 is left out.

Owner steps left: none. Not pushed.
