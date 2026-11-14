# 1652: Go twin of `property_page.publish_page` (slug rules, history, publish flags)

Status: todo
Tier: B (public page slugs: a wrong slug breaks printed QR links; golden from Python)
Depends on: none | Base commit: current branch (One big PR mode) | Branch: current branch
Executor: Haiku 5.5 | Fits one session: 15 tool calls, 30k tokens

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1652 step k`. Never create a branch, never push, never open a PR.

## 1. Objective

Port `property_page.slug_for`, `ensure_slug`, `publish` and `publish_page` (`App/app/property_page.py` 14-115 and 192-200) as `booking.SlugFor`, `EnsureSlug` and `PublishPage` in `go/internal/web/booking`. Brief 1597 (`POST /demo`) publishes the demo Vinohrady page with it; the booking-site routes that rename or publish pages can reuse it later. No route is added.

## 2. Context

Rules (AGENTS.md): 2 no new personal-data field and no outbound request. 4 no new dependency (`golang.org/x/text/unicode/norm` is already in `go.mod` and used by `stayfees` and `auth`). 5 plain PostgreSQL. 11 Go first: port plumbing for a Go brief.

Python in short: the slug is `<name>-<xxxx>`: the name ASCII-folded (NFKD, characters that are not ASCII dropped), lower case, every run of characters outside `a-z0-9` becomes one `-`, cut to 48 characters and trimmed of `-` (an empty result is `apartment`), and `xxxx` is the first four hex characters of `sha256("apartment:<id>")`. `ensure_slug` inserts the `property_slug` row (`published = 0`) or, when the slug changed after a rename, writes the old one to `property_slug_history` and updates the row. `publish_page` sets `published`, `published_at` (a time, or NULL when unpublishing) and `updated_at` on `property_page` (no row: no effect) and then on `property_slug`.

**All code is pre-written, compiled and tested.** Sidecars: `docs/tasks/1652-files/<repo path>.txt`.

| sha256 | file | action | lines |
|---|---|---|---|
| `4ec35a56f0e5780ddb748fb1da5978a16ae3292b72a9641c0e9126428e29fbeb` | `go/internal/web/booking/publish.go` | create | 116 |
| `cc9cf6398c995032fa3d7c62f3a709faf2c9a0725d6c549ec7a7791d771db285` | `go/internal/web/booking/publish_test.go` | create | 111 |
| `fbeff6b304e0a2701410a513c0c5b52ad9d87f5404d2b14b1576170962a5c62b` | `go/internal/web/booking/testdata/slug_golden.json` | create | 81 |

`slug_golden.json` holds 16 names with Python's slug (Python 3.12, made by running `slug_for`): accents, an en dash, full-width letters, ligatures, `№`, a name with no ASCII letter, an empty name, a 60-character name, a name whose cut leaves a trailing `-`. The booking test `TestPublishPage` runs on PostgreSQL: publish sets both rows and the slug; unpublish sets the flags to 0 and `published_at` NULL; a rename writes exactly one history row and a second publish adds none; a property without a `property_page` row gets a published slug and no page row; an unknown apartment is an error.

**Known difference:** Python's NFKD comes from Python 3.12's Unicode tables, Go's from `x/text`; they agree on the 16 golden names. A name using a character added to Unicode after the older table would fold differently; none of the app's names do.

**Verified by the brief writer** in a throwaway copy of `go/` with exactly these files, PostgreSQL 16 on a disposable port: `gofmt -l` empty, `go vet ./internal/web/booking/` clean, `go mod tidy -diff` empty, `go test ./internal/web/booking/ -count=1` ok (whole package, database tests run).

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/booking/publish.go` | create | `NormaliseSlugName`, `SlugFor`, `EnsureSlug`, `PublishPage` |
| `go/internal/web/booking/publish_test.go` | create | two tests |
| `go/internal/web/booking/testdata/slug_golden.json` | create | Python's slugs |
| `docs/tasks/1652-files/**` | keep | sidecars (do not edit) |
| `docs/tasks/1652-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root): `ls go/internal/web/booking/publish.go 2>&1 | tail -1` says "No such file"; `grep -rn 'func SlugFor\|func PublishPage\|func EnsureSlug' go/internal | tail -3` prints nothing; `grep -c 'func StampAt' go/internal/web/booking/site.go | tail -1` prints `1`; `grep -c 'golang.org/x/text' go/go.mod | tail -1` prints `1`; `grep -cF 'def publish_page(apartment_id: int, *, published: bool) -> None:' App/app/property_page.py | tail -1` prints `1`; `find docs/tasks/1652-files -name '*.txt' | wc -l | tail -1` prints `3`. Anything else: STOP (§8).

1. Copy the sidecars and check them (repo root):

   ```bash
   cd docs/tasks/1652-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF' 2>&1 | tail -5
   4ec35a56f0e5780ddb748fb1da5978a16ae3292b72a9641c0e9126428e29fbeb  go/internal/web/booking/publish.go
   cc9cf6398c995032fa3d7c62f3a709faf2c9a0725d6c549ec7a7791d771db285  go/internal/web/booking/publish_test.go
   fbeff6b304e0a2701410a513c0c5b52ad9d87f5404d2b14b1576170962a5c62b  go/internal/web/booking/testdata/slug_golden.json
   EOF
   ```

   All three lines must end with `: OK`. Commit "1652 step 1".

2. Format, build, vet (from `go/`):

   ```bash
   cd go && gofmt -l internal/web/booking 2>&1 | tail -5; go build ./... 2>&1 | tail -30; go vet ./internal/web/booking/ 2>&1 | tail -30; go mod tidy -diff 2>&1 | grep -v downloading | tail -5
   ```

   Expected: no output at all. Anything printed: STOP.

3. PostgreSQL: as brief 1596 or 1602 (`UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55440/postgres`; brief 1440 step 3 starts a throwaway server). No server: write "CI only" and STOP before step 4.

4. Tests (from `go/`):

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55440/postgres go test ./internal/web/booking/ -count=1 2>&1 | tail -10
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55440/postgres go test ./internal/web/booking/ -count=1 -v -run '^(TestSlugForMatchesPython|TestPublishPage)$' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -6
   ```

   Expected: `ok` for the package, then two `--- PASS` lines and `ok`; no `--- SKIP`, no `--- FAIL`.

5. Write the report (§9), set `Status: review`, commit "1652 step 5". Last, from the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 5. Do not touch

Every other file under `go/` (no route changes), `App/`, `deploy/`, `docs/context/*`, `go/go.mod`, `go/go.sum`.

## 6. Commands

Exactly those of §4. Test-map: the coordinator adds the `go/internal/web/booking` row. Never the full suite.

## 7. Acceptance

- [ ] `sha256sum -c` printed `: OK` for all 3 files; step 2 printed nothing.
- [ ] Step 4 printed `ok` for the package and two `--- PASS` (none `SKIP`).
- [ ] `git diff --stat main...HEAD | tail -10` lists only the paths of §3 and the sidecars.

## 8. Stop and ask

Stop, and write the report, if a check or hash is not as stated, a test fails twice (do not edit sidecars: report), you reach 15 tool calls or about 30k tokens, a new dependency seems needed, a file outside §3 needs a change, or you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/1652-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with the last 5 lines of its output, §7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

`publish.go`: `NormaliseSlugName` (cut at 48 before the final trim), `EnsureSlug` writes history only when the slug changes, `PublishPage` writes `published_at` NULL when unpublishing.

## Owner steps

None (no route uses it yet).
