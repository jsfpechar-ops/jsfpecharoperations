# 1700d: Go RUIAN suggest route on the local table

Status: todo — scoped (2026-11-17). Executable only after its exact-diff pass: sidecars in `docs/tasks/1700d-files/`, anchors and sha256 table (§2), written to the rules in [workflow](../context/workflow.md#writing-briefs-for-haiku). Until then the executor must not start it. The exact-diff pass (sidecars, sha256, anchors) comes later; this brief is scoped only.
Depends on: 1700c merged (table `ruian_address`, `ruian.Fold`) | Base commit: current tip of the working branch | Branch: task/1700d-go-ruian-suggest
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (split in two briefs if the exact-diff pass finds more)
Tier: B (Sonnet writes the exact-diff pass; orchestrator reads the diff of the risk-listed files)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1700d step k`. Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1700d step'`.

## 1. Objective

Serve `GET /apartments/ruian-suggest` from Go, querying the local `ruian_address` table with `pg_trgm`, with the same JSON shape and the same signed-out and rate-limit behaviour as Python's `apartments_ruian_suggest` (`App/app/routes/admin.py` ~1334). Replaces the live ČÚZK call (plan: [ruian-local](../plans/ruian-local.md) §3).

## 2. Context

Hard rules (AGENTS.md): 1 filing correctness first (suggest only pre-fills form fields the user can edit); 2 privacy first (nothing typed leaves the server; no new outbound request); 3 no real data in tests (made-up rows); 4 no new dependency; 5 SQL only through the existing Go DB helpers, `$n` placeholders; 6 forms work without JavaScript (this is an enhancement endpoint, `[]` is always safe); 11 Go first.

**Python source of truth:** `App/app/routes/admin.py` 1333-1344 (route), `App/app/ruian.py` (`usable_query` min 3 characters after whitespace collapse, `rate_limited` 60 per 3600 s under scope `ruian` keyed by the owner id, `record_lookup`, `suggest` returns at most 6 `{label, fields}`), `App/app/static/ruian_suggest.js` (reads `label` and `fields`). Python order: signed out gives `401` with body `[]`; disabled, short query or rate-limited gives `200 []` without recording; otherwise the lookup is recorded and the result returned.

**Routes in scope (method path, Python function):**

- GET /apartments/ruian-suggest (apartments_ruian_suggest)

**Reuse:** `rateBlocked` and `rateRecord` in `go/internal/web/properties/ares.go` (scope string `"ruian"`, key the owner id as text, max 60, window 3600); the session/owner helper the other `properties` handlers use; `ruian.Fold` from 1700c. The `ruian_address` columns and the result mapping are in the plan §3.

**Parity method:** the JSON shape is tested against hand-written expected JSON from the fixture rows (the Python route needs the network, so there is no golden script). Accepted difference: `label` text is built from our table, not the ČÚZK geocoder (same format `street cp[/co], part, zip district`); `addr_okres` follows the owner answer to Q1 in the plan §9 (until answered: omit the key, which the JS accepts).

**Risk:** low; read-only. The one trap is the route order: `/apartments/ruian-suggest` must be matched before `/apartments/{id}`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/properties/ruian_suggest.go` | create | handler, query, mapping, JSON |
| `go/internal/web/properties/ruian_suggest_test.go` | create | tests with made-up rows inserted into `ruian_address` |
| `go/cmd/ubyhost-web/register_web_properties_ruian.go` | create | registers the route (`init()` through `registerRoutes`) |
| `go/cmd/ubyhost-web/register_web_properties_ruian_test.go` | create | route registration test |
| `docs/tasks/1700d-report.md` | create | the report (§9) |

No other file may change. 1700a (new-property form) and 1700b (create) do not own this route any more (split of 2026-11-17); if their briefs still list it, say so in the report instead of editing them.

## 4. Steps

0. Checks (repo root). The exact-diff pass fills in the anchors and the `ls` line proving the new files do not exist. `ls go/internal/ruian/fold.go` must exist (1700c merged); else STOP.
1. Copy the sidecars and run `sha256sum -c`: all OK.
2. Add the handler. Query: fold the text with `ruian.Fold`, split into tokens, `WHERE search LIKE '%' || $n || '%'` for every token (escape `%` and `_`), `ORDER BY similarity(search, $q) DESC, code LIMIT 6`. Map rows to `{label, fields}` (`addr_obec_cast` only when `part` differs from `obec`; empty values are left out of `fields`; `addr_house_no` is the house number, `addr_orient_no` includes the letter). Answer `[]` (never `null`) when nothing matches. Content type `application/json`.
3. Add the behaviour order of §2: signed out `401 []`; disabled (`UBYHOST_RUIAN_ENABLED` 0, false, no, off) / short query / rate-limited `200 []`; else record, then answer. A database error answers `200 []` and logs.
4. Register the route in one new `register_web_*.go`; it stays dormant: nothing is added to `UBYHOST_GO_PATHS`.
5. Tests: happy path (street + number, diacritics folded: `vaclavske 12`), village without street, `č.ev.` row, letter after orient number, six-result cap, no match is `[]` and not `null`, two-character query, signed out, disabled env, rate limit (61st call in an hour is `[]`, and 60 rows are recorded), a query with `%` and `_` matches nothing special. Run §6; write the report.

## 5. Do not touch

`UBYHOST_GO_PATHS` or any server file; `handlers.go` and shared `i18n.json`; Python files (`App/app/ruian.py` and `admin.py` stay until a later cleanup brief); `go/internal/ruian/**` (owned by 1700c); `docs/ENVIRONMENT.md`.

## 6. Commands

- `cd go && gofmt -l . | tail -5` prints nothing
- `cd go && go vet ./internal/web/... ./cmd/... 2>&1 | tail -20` is silent
- `cd go && go test ./internal/web/properties/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30` passes, no test skipped
- `python3 scripts/context_lint.py 2>&1 | tail -10` is clean

No screenshots: no template or CSS changes.

## 7. Acceptance

- For the fixture rows the JSON has the same keys as Python's (`label`, `fields` with only `addr_street, addr_house_no, addr_orient_no, addr_zip, addr_obec, addr_obec_cast, addr_okres`).
- Status codes and bodies for signed out, disabled, short and rate-limited requests equal Python's (`401 []`, `200 []`).
- The rate limit shares the `rate_limit_event` rows (scope `ruian`) with Python, so a switch of the path does not reset the count.
- No outbound request in the code path (no `http` client import in the new file).
- `git log --oneline --grep='^1700d step'` shows one commit per step; `git diff --stat` lists only §3 paths.

## 8. Stop and ask

Stop and write the report instead of continuing when: an anchor is not found verbatim; `ruian_address` or `ruian.Fold` is missing or differs from the plan; the `pg_trgm` extension is missing in the test database; a file outside §3 would have to change; a test needs a skip.

## 9. Report

Write `docs/tasks/1700d-report.md` (600 tokens at most) and set this brief's `Status: review`. The report has: 1. files changed; 2. each command with the last 5 lines of output and the SKIP count; 3. §7 ticked; 4. deviations; 5. questions; 6. owner steps left.

## Risk list (for the reviewer)

Read `ruian_suggest.go`: LIKE escaping, the `LIMIT 6`, the rate-limit order (record only after the checks), no query text in log lines (the typed address is not logged).

## Owner steps

None now: nothing is switched on. Later, after 1700c has loaded the table (`SELECT rows FROM ruian_import;`):

1. On the server, open the env file that holds `UBYHOST_GO_PATHS` (see docs/ENVIRONMENT.md).
2. Add `/apartments/ruian-suggest` to the comma-separated list (exact path).
3. Run `scripts/caddy-validate.sh`, then `docker compose up -d caddy`.
4. On the new-property form, type "vaclavske 12": suggestions appear. Rollback: remove the path again and repeat step 3.
