# 1864: Stay page switch: the UBYHOST_GO_PATHS selector, tooling that understands it, the one PR

Status: review
Depends on: 1863 | Base commit: the series branch after 1863's last commit | Branch: task/1860-1864-stay-page (series, see below)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (checkpoint at 60k)
Tier: A (the selector decides whether the filing POSTs `/reservations/{id}/submit` and `/reservations/submit-ready` stay on Python; rule 1)

> **Series mode (owner 2026-11-19).** One executor runs 1860, 1861, 1862, 1863, 1864 in that order on one branch, `task/1860-1864-stay-page`, with no owner check in between. Commit every step as `1864 step k`, write `docs/tasks/1864-report.md`, set `Status: review`. This brief opens the ONE draft PR of the series (step 6). Never push to `main`, merge, deploy or touch a server: the switch itself is the owner steps at the end. Every command ends in `2>&1 | tail -30`. At the cap: commit, write the report as `blocked` with `Done: steps 0 to k. Left: ...`; a fresh session continues on the same branch.

## Open questions

None block the executor. Decided by the brief writer (closes 1861 Open question 2 and 1862 Open question 7):

1. **Selector: `/reservations/*[0-9]`.** Caddy's `path` matcher (`caddyhttp.MatchPath`, checked against Caddy's source) lower-cases both sides, cleans the request path (keeping a trailing slash), and then: `*` alone matches all; a pattern whose only two stars are its first and last character is a substring match; a pattern with one star at its start or its end is a suffix or prefix match; **every other pattern goes to Go `path.Match`**. `/reservations/*[0-9]` has one star that is neither first nor last, so it is `path.Match`: `*` never crosses a `/`, and `[0-9]` must be the last character. It matches `/reservations/<digits>` (and a segment like `abc1`, which Go answers 404 because the id must parse as a number), and nothing with a further segment.
2. **Never** `/reservations/*` (a prefix match: it would send `POST /reservations/{id}/submit`, `/submit-ready` and every other stay POST to Go, which does not serve them). **Never** `/reservations/[0-9]*` (a trailing star with no other star is a literal prefix match on the text `[0-9]`: it matches nothing).
3. **Tooling.** `scripts/go_parity_check.py` and `App/tests/go_stack.py` each have a `caddy_match` that escapes `[` as text, so today both say the selector catches nothing. This brief replaces the parity check's function with Caddy's rule and makes `go_stack.caddy_match` load it from that file, so there is one copy. A shared table, `scripts/caddy_match_cases.json`, is checked by a Go test against Caddy's rule (Go's own `path.Match`) and by a Python test against `caddy_match`. Python here is port plumbing (go-first exception 1: parity tooling and the browser stack).

## 1. Objective

Make the repo's tooling match Caddy for the selector `/reservations/*[0-9]`, prove that the selector sends exactly `GET` and `POST /reservations/{reservation_id}` to Go, document it in one sentence, and open the series' one draft PR with the owner steps that add the selector on the server, the before/after `curl` checks and the rollback.

## 2. Context

Rules 1, 3, 8 and 11. Caddy (READ-ONLY, `deploy/lightsail/caddy/Caddyfile.cloudflare` and `Caddyfile.acme`): `@go path {$UBYHOST_GO_PATHS:/__go_off__}`; a GET or HEAD that Go answers 501 plus `X-Ubyhost-Not-Ported` goes back to Python, a POST does not. Compose passes `UBYHOST_GO_PATHS` to the `caddy` service (`deploy/lightsail/docker-compose.yml`, `${UBYHOST_GO_PATHS:-/__go_off__}`). The value lives in `/opt/ubyhost/deploy/lightsail/.env` inside double quotes ([ENVIRONMENT](../ENVIRONMENT.md) `UBYHOST_GO_PATHS`: `deploy.sh` sources `.env`; without quotes the shell would treat `*[0-9]` as a file pattern).

Python stay routes (as `scripts/py_routes.py` lists them), with the samples `go_parity_check.py` builds (`{param}` replaced by `1`):

```text
GET  /reservations  /reservations.csv  /reservations/1  /reservations/1/dorucenka.zip  /reservations/1/guests/new
POST /reservations  /reservations/1  /reservations/submit-ready  /reservations/1/{archive,delete-demo,filed-by-hand,
     filed-by-hand/undo,guests,quick-edit,release-claim,remove-empty-slot,reopen-guest,resend-claim,submit,unarchive}
```

`/reservations/*[0-9]` catches only `/reservations/1` (GET and POST). 1861 serves the GET, 1863 the POST.

Current code, the anchors `docs/tasks/1864-files/apply_1864.py` replaces (it STOPs unless each occurs exactly once):

```python
# scripts/go_parity_check.py, lines 8-9 of the docstring and lines 33-40
For each UBYHOST_GO_PATHS entry (Caddy `path` matcher: exact, trailing * = prefix,
other * = glob inside one segment) it finds the Python routes (METHOD /path)
def caddy_match(entry, sample):
    e, s = entry.lower(), sample.lower()
    if "*" not in e:
        return e == s
    if e.endswith("*") and "*" not in e[:-1]:
        return s.startswith(e[:-1])
    pat = re.escape(e).replace(r"\*", "[^/]*")
    return re.fullmatch(pat, s) is not None
# App/tests/go_stack.py: the same caddy_match body with type hints and the docstring
# """Same rules as scripts/go_parity_check.py and Caddy path matchers.""", and the imports
import os
import re
import shutil
```

What the script writes: in the parity check, `_class_char`, `_glob_regex` (Go `path.Match` as a regular expression: `*` is `[^/]*`, `?` is `[^/]`, `[...]`/`[^...]` classes with ranges, `\` escapes; `None` for a pattern Go rejects) and the new `caddy_match` (Caddy's order above; an entry containing `%` raises `ValueError`, since no entry uses escapes). In `go_stack.py`: `import functools` and `import importlib.util`, `_parity_check()` (`functools.lru_cache`, loads `REPO_ROOT / "scripts" / "go_parity_check.py"` with `importlib.util.spec_from_file_location`) and `caddy_match(entry, sample)` returning `_parity_check().caddy_match(entry, sample)`. Existing entries keep their meaning; entries starting with `*` (for example `*.php`) now match across segments, as Caddy does (the old regex did not).

Sidecars in `docs/tasks/1864-files/` (copied by step 1; `apply_1864.py` is run, never copied):

| Target | sha256 |
|---|---|
| `scripts/caddy_match_cases.json` | `7fd5bcd0bce552712e054d48bd9b50d7e6b14ce839af51b136772ae383041e9d` |
| `App/tests/test_1864_caddy_match.py` | `7833884de42fc2df20679fa785647fd54ec8a5ba71696e350e9d13d6f774b272` |
| `go/cmd/ubyhost-web/caddy_match_cases_test.go` | `122bace9dff82a1527dac9cac783d9175aee5a479b315de4628378b980ef6679` |
| `docs/tasks/1864-files/apply_1864.py` (not copied) | `d562960be5aa45e5ae84e766a0a4e7e03279826d5ce753672ce200736df408a3` |

The table has 32 rows: the selector against all stay paths above, `/reservations/12/`, `/reservations/`, `/reservations.csv`, upper case, the two forbidden selectors, existing entry styles (`/payments/qr/*.png`, `/entities/*/archive`, `*.php`, `*/wp-*`), `?`, classes, negated classes and a malformed `[`. The Go test (`caddyPathMatch`, a copy of Caddy's matcher order calling `path.Match`) reads it from `../../../scripts/caddy_match_cases.json`. The Python test checks every row through `go_stack.caddy_match`, that the selector catches exactly `GET` and `POST /reservations/{reservation_id}` among all Python routes, and that `%` raises.

## 3. Files

| Path | Action | What |
|---|---|---|
| `scripts/go_parity_check.py` | edit (script) | docstring lines 8-9, `caddy_match` plus two helpers |
| `App/tests/go_stack.py` | edit (script) | two imports, `_parity_check`, `caddy_match` delegates |
| `scripts/caddy_match_cases.json` | new (sidecar) | the shared table |
| `App/tests/test_1864_caddy_match.py` | new (sidecar) | Python side of the table, selector test |
| `go/cmd/ubyhost-web/caddy_match_cases_test.go` | new (sidecar) | Caddy side of the table |
| `docs/ENVIRONMENT.md` | edit | one sentence in the `UBYHOST_GO_PATHS` row |

No other file may change (besides this brief's status line and the report).

## 4. Steps

0. Checks (one call): `git branch --show-current; git log --oneline -5; grep -c '^Status: review' docs/tasks/186[0-3]-*.md; grep -nF 'mux.Handle("POST /reservations/{reservation_id}"' go/internal/web/staydetail/handlers.go; grep -nF 'def caddy_match' scripts/go_parity_check.py App/tests/go_stack.py; grep -cF 'only after the owner has checked the Go webhook. |' docs/ENVIRONMENT.md`. Expect branch `task/1860-1864-stay-page`, last commit `1863 step ...`, four briefs at `review`, the POST line, both functions, and `1`. Otherwise STOP.
1. Copy and verify (one call), then run the patch:

```bash
S=docs/tasks/1864-files; for f in $(cd $S && find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "$(dirname "$f")" && cp "$S/$f.txt" "$f"; done; sha256sum -c $S/MANIFEST.sha256 2>&1 | tail -10; sha256sum $S/apply_1864.py | tail -1; python3 $S/apply_1864.py 2>&1 | tail -5
```

   Expect three `OK`, the `apply_1864.py` sha from §2, then `patched scripts/go_parity_check.py` and `patched App/tests/go_stack.py`. Any `FAILED`, other sha or `STOP:` line: STOP (`git checkout -- scripts App/tests` first). Commit `1864 step 1`.
2. `docs/ENVIRONMENT.md`: replace `only after the owner has checked the Go webhook. |` with:

```text
only after the owner has checked the Go webhook. An entry is matched like Caddy's `path` matcher (`caddy_match` in `scripts/go_parity_check.py`): a single star at the end is a prefix match, any other `*` stays inside one path segment and `[0-9]` is one digit, so `/reservations/*[0-9]` is the stay page alone (GET and POST `/reservations/<id>`), never `/reservations/<id>/submit` or `/reservations/submit-ready`. |
```

   Commit `1864 step 2`.
3. Tests (each in one call). From `go/`: `go vet ./cmd/ubyhost-web/ 2>&1 | tail -30; gofmt -l cmd/ubyhost-web 2>&1 | tail -30; go test ./cmd/ubyhost-web/ -run 'TestCaddyMatchCases|TestStayDetailRoutesRegistered' -count=1 -v 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -30`. From `App/`: `.venv/bin/python -m pytest tests/test_1864_caddy_match.py -q --tb=short -x 2>&1 | tail -30` (34 passed: 32 table rows and 2 tests). Then the two series parity tests, which use `go_stack`: `UBYHOST_GO_PATHS=/__go_test__ .venv/bin/python -m pytest tests/test_1861_stay_detail_go_parity.py tests/test_1863_stay_detail_post_go_parity.py -q --tb=short -x -rs 2>&1 | tail -30` (0 failed, 0 skipped). A failure in `test_1864_caddy_match.py` or the Go test: STOP; never edit the table or the sidecars.
4. Route check, from the repo root: `python3 scripts/go_parity_check.py --paths "/reservations/*[0-9]" 2>&1 | tail -30`. Expect exactly `1 entries, 2 method/route pairs checked, 0 missing`. Then `scripts/go_switch_preflight.sh "/reservations/*[0-9]" 2>&1 | tail -30` and copy its last 5 lines into the report (a `go_jobs_parity.py` failure that also happens on `origin/main` is not this series': say so). Then `python3 scripts/context_lint.py 2>&1 | tail -30`. Commit `1864 step 4`.
5. Report `docs/tasks/1864-report.md` (§9), set this brief's `Status: review`. Commit `1864 step 5`.
6. The one PR. Push `task/1860-1864-stay-page` and open ONE draft PR to `main` titled `Stay page in Go (1860-1864): page, desktop layout, settings save, switch tooling`. Body, in this order, taken from the five reports (copy, do not rewrite): (a) one line per brief, what it did; (b) the UX gate per page from 1861 and 1862 (`390: ...; 768: ...; 1024: ...; 1280: ...` for `stay-detail` and `stay-archived`) and the design-system checklist ticked; (c) filing (UBYPORT_CORE guidance 4): "Filing changes only after the owner adds the selector: saving a complete stay of an `immediate` property then queues the existing `submit` sweep job instead of filing during the request; the send starts within the next job poll (about 30 s). No new filing path. Tested by `TestSave*` and `test_1863_stay_detail_post_go_parity.py`."; (d) the route check line from step 4; (e) the Owner steps below, copied verbatim. If your environment cannot push or open a PR: STOP and give the owner `git push -u origin task/1860-1864-stay-page` and the body file path.

## 5. Do not touch

`App/app/`, every Caddyfile, `docker-compose.yml`, `deploy/`, any `.env`, `scripts/py_routes.py`, `scripts/e2e/`, the sidecars and the table after copying, the 1860-1863 files. Never add `/reservations/*[0-9]` (or any selector) to a committed file other than docs and tests. No server, no deploy, no merge.

## 6. Commands

Steps 3 and 4 (Go: vet, gofmt, the two tests; App: `test_1864_caddy_match.py`, the two parity tests; root: `go_parity_check.py`, `go_switch_preflight.sh`, `context_lint.py`). No other test-map row: the change is test tooling, and CI runs the rest.

## 7. Acceptance

- [ ] Three sidecar `OK`, the script sha matches, both files patched.
- [ ] `TestCaddyMatchCases` and `TestStayDetailRoutesRegistered` pass; vet and gofmt clean.
- [ ] `test_1864_caddy_match.py`: 34 passed. The 1861 and 1863 parity tests: 0 failed, 0 skipped.
- [ ] `go_parity_check.py --paths "/reservations/*[0-9]"`: `2 method/route pairs checked, 0 missing`.
- [ ] `git diff --stat origin/main` lists only the files of 1860-1864's §3 tables, their briefs' status lines and the five reports (the brief files themselves too if step 0 of 1860 copied them).
- [ ] One draft PR, body (a) to (e).

## 8. Stop and ask

As [TEMPLATE](TEMPLATE.md) §8, plus: an anchor of `apply_1864.py` is not found once; the table disagrees with the Go test or with `caddy_match`; `go_parity_check.py` catches any route other than `GET` and `POST /reservations/{reservation_id}`, or reports one missing; a step would change a Caddyfile, compose or a server.

## 9. Report

`docs/tasks/1864-report.md`, 600 tokens at most: files, each command's last 5 lines, §7 ticked, the route check line, the PR link (or the hand-over), deviations, questions.

## Risk list (for the reviewer)

`_glob_regex` (a class may match `/`, as in Go; ranges; escapes), the order of the special cases in `caddy_match`, `go_stack._parity_check` loading by path, the ENVIRONMENT sentence. Check the PR's filing paragraph against 1863's report.

## Owner steps

Do these only after the PR is merged and deployed (green merges deploy by themselves). Replace `YOUR-DOMAIN` with your app's address, for example `app.ubyhost.cz`.

1. On GitHub, open the PR and click **Ready for review**. On your computer, in the repo folder, run `scripts/merge-pr-on-green.sh <PR number>`; it waits for green checks and merges. Then open the **Actions** tab on GitHub and wait until the **Deploy production** run for that merge shows a green tick.
2. Open a terminal on your computer and connect to the server: `ssh ubuntu@YOUR-SERVER-IP`.
3. Type `cd /opt/ubyhost/deploy/lightsail` and press Enter.
4. Type `grep '^UBYHOST_GO_PATHS=' .env` and press Enter. Copy the line it prints into a note on your computer: that is your rollback. If it prints nothing, write "none" in the note.
5. Before changing anything, run these three lines one by one and write down the three numbers they print:
   `curl -s -o /dev/null -w '%{http_code}\n' -X POST https://YOUR-DOMAIN/reservations/1/submit`
   `curl -s -o /dev/null -w '%{http_code}\n' -X POST https://YOUR-DOMAIN/reservations/submit-ready`
   `curl -s -o /dev/null -w '%{http_code}\n' -X POST https://YOUR-DOMAIN/reservations/1/remove-empty-slot`
6. Type `nano .env` and press Enter. Find the line starting with `UBYHOST_GO_PATHS=`. Inside its double quotes, after the last path, type one space and then `/reservations/*[0-9]`. Keep the closing double quote. If there was no such line, add this new line at the end: `UBYHOST_GO_PATHS="/reservations/*[0-9]"`. Press Ctrl+O, Enter, then Ctrl+X to save and close.
7. Type `./scripts/caddy-validate.sh` and press Enter. It must end with `Valid configuration`. If it shows an error, do step 11 (rollback) now.
8. Type `docker compose up -d caddy` and press Enter. Wait 10 seconds.
9. Run the three `curl` lines from step 5 again. All three numbers must be the same as before. If any number changed, do step 11 now.
10. On a laptop, log in and open one stay. You should see the new layout: the breadcrumb above the stay's name and the actions next to it. Change the private note under Stay settings and save: you must see "Stay saved." and the new note. On your phone, open the same stay: it must look exactly as before. From now on, saving a complete stay queues police filing instead of filing during the save; only one open `submit` job runs at a time, so if a sweep is already in progress the stay waits for the next sweep, within about 10 minutes; nothing else changes.
11. Rollback (only if step 7, 9 or 10 went wrong): `nano .env`, put back the line from your note from step 4 (or delete the `UBYHOST_GO_PATHS=` line if your note says "none"), save as in step 6, then run `./scripts/caddy-validate.sh` and `docker compose up -d caddy`. Run the three `curl` lines again: they must show the numbers from step 5.
