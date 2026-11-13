# 1361 report

Status: blocked

## Files changed
- go/internal/web/customers/templates/i18n_keys.txt (created, sha256 b5498dea32e54f854edce94ab38b1588ac69200ad297c10915fe8ae84a1cdaed, matches)
- go/internal/web/customers/templates/i18n.json (generated, sha256 d070622638d7c64d6fb62e408f39008c8e84b569911a371a8be83070cd64a1ca, matches)

## Commands
- `python3 App/scripts/go_host_i18n.py` (run as `.venv/bin/python scripts/go_host_i18n.py` from App/): `wrote .../go/internal/web/customers/templates/i18n.json`

## Steps
- Step 1 (Postgres): skipped, `pg_isready -h 127.0.0.1 -p 55436` already accepting connections.
- Step 2: done, commit `1361 step 2`.
- Step 3: done, commit `1361 step 3`. Both sha256 match (template 7566ec3e..., pages.go 8ca114b0...). `go build ./internal/web/...` failed only with `undefined: asInt64` (defined in step 4); the build passes after step 4.
- Step 4: done, commit `1361 step 4`. Patch applied with `git apply --check` then `git apply`. query.go ef2a2dd3..., register_web_customers.go f567c86b... match. `go vet ./internal/web/... ./cmd/...` and `go build ./internal/web/...` clean.
- Steps 5 to 7: not started.

## Deviations
Done: steps 1 to 4. Left: steps 5 to 7. Step 3 was committed before step 4 because the brief orders it so; its build check only passes once step 4 is applied. Patch written to the session scratchpad instead of /tmp.

## Questions
None.

## Owner steps left
None. Brief status remains todo.
