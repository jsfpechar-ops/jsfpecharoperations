# 2084: PR 1319, merge origin/main and close the Go and Python CI reds

Status: done
Depends on: 2071 (merged on this branch) | Base commit: df1244e227eb5a7845e40a1c70aa3056bcfd8647 | Branch: claude/nice-hawking-fw98ct (work in a worktree of it)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Merge `origin/main` (PR 1236, commit c3b3865ec) into the PR 1319 branch without losing 2065, 2069, 2070 or 2071, and fix the two CI reds: `gofmt -l .` (Go job) and `tests/test_static_versions.py` (Python `test` and `postgres full shard 1`). The result must pass `gofmt -l .`, `go vet ./...`, `go test ./... -count=1` and the static-version test.

## 2. Context

Rules: Go first; no new dependency; no push, no merge (owner does that); never push to `main`.

What was checked (read-only, on a scratch merge, `go test ./...` EXIT=0 afterwards):

- `git merge origin/main` conflicts only in `go/internal/web/guest/form_save.go`. `apply_declared_in.go` and `form_save_test.go` merge cleanly.
- PR 1236 added `headcount.ApplyDeclaredInTx`, `guestSaveValidateIssues` (new guest through `guestcontract.CheckNewGuest`, English messages), `ptrInt64`, a `partySize` argument on `insertGuestSaveRow`, and two tests that call `guestSaveValidateIssues`.
- HEAD (2071) already does all of that better: `insertGuestSaveRow` takes `partySize`, runs the first count through `partyDeps.applyDeclaredTx` (it has the cutoff rule), returns `guestInsert`, audits the count, and runs `runCompletion`. The `party_size` and `legal_ack` messages come from the guest catalog (`error_party_size`, `legal_ack_missing`) per language. `GuestLocalize` does NOT translate the English CheckNewGuest sentences, so main's version would lose the 2071 translations.
- So: keep HEAD's `form_save.go` whole; move HEAD's inline validation into a function named `guestSaveValidateIssues` (main's name) so main's two tests stay; delete `ApplyDeclaredInTx` (no caller, diverges from `applyDeclaredTx`: no cutoff rule, other timestamp format).
- Go gofmt red: `go/internal/web/guest/party_lead_hooks_test.go` line 56 (`pool:   pool,`). Only file listed by `gofmt -l .`; `go vet ./...` is clean.
- Latent red CI never reached because gofmt fails first: `TestGuestSaveNoticeAndHeadcount` (`form_save_test.go`) uses `testPool(t)`, which gives an unmigrated DB (`relation "user_account" does not exist`). Use `testPoolOptional(t)` (fresh migrated DB, skips without a URL).
- Python red: `App/app/static/app2.css` changed in 2046 but its key is still `?v=20261122-access-2036a`. That string appears only in: `App/app/templates/base.html:23`, `App/tests/static_versions.json:32`, `go/internal/hostweb/layout/shell.html:25`, `go/internal/hostweb/layout/testdata/v2_cs_impersonating.html:23`, `go/internal/hostweb/layout/testdata/v2_alerts_hidden.html:23`. New key: `20261124-2046a`.

If any excerpt below is not found verbatim, STOP (§8).

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/guest/form_save.go` | merge-resolve + edit | keep HEAD side, extract `guestSaveValidateIssues` |
| `go/internal/web/guest/form_save_test.go` | edit | adapt main's 2 calls; `testPoolOptional` in the 2071 test |
| `go/internal/headcount/apply_declared_in.go` | delete | dead duplicate of `applyDeclaredTx` |
| `go/internal/web/guest/party_lead_hooks_test.go` | gofmt | one line |
| `App/app/templates/base.html` | edit | key bump |
| `go/internal/hostweb/layout/shell.html` | edit | key bump |
| `go/internal/hostweb/layout/testdata/v2_cs_impersonating.html` | edit | key bump |
| `go/internal/hostweb/layout/testdata/v2_alerts_hidden.html` | edit | key bump |
| `App/tests/static_versions.json` | regenerate | `--write` |

No other file may change.

## 4. Steps

Work in a worktree of `claude/nice-hawking-fw98ct`. Use `.venv/bin/python` from `App/`; if the worktree has no `App/.venv`, use `/agent/repos/jsfpecharoperations/App/.venv/bin/python`.

1. Merge. From the worktree root:
   `git merge --no-ff origin/main 2>&1 | tail -10`
   Expect exactly one conflict, `go/internal/web/guest/form_save.go`. Any other conflict: STOP.

2. Take HEAD's file: `git checkout --ours go/internal/web/guest/form_save.go`. Then check `grep -c '<<<<<<<\|>>>>>>>' go/internal/web/guest/form_save.go` prints `0`.

3. In `go/internal/web/guest/form_save.go`, replace this block (inside `handleGuestFormSave`, after `if child { sig = "" }`):

```go
	from, to := parseDate(stayFrom), parseDate(stayTo)
	issues := validation.ValidateGuestForm(values, &from, &to, legalToday(d.now), raw)
	// guest.py:2462 — a new guest with no expected total gives a party size of 1–60.
	if existing == nil && headcount.Expected(res.overrideGuests, res.declaredGuests, res.reducedGuests) == nil {
		if n, err := strconv.Atoi(validation.Strip(form["party_size"])); err != nil || n < 1 || n > 60 {
			issues = append(issues, validation.Issue{Field: "party_size", Message: stringsCatalog.T(lang, "error_party_size", nil), Severity: "error"})
		}
	}
	if si := validation.GuestFormSignatureIssue(sig, child); si != nil {
		issues = append(issues, *si)
	}
	// guest.py:2480 — the guest must confirm the legal notice.
	if form["legal_ack"] == "" {
		issues = append(issues, validation.Issue{Field: "legal_ack", Message: stringsCatalog.T(lang, "legal_ack_missing", nil), Severity: "error"})
	}
```

with exactly this one line:

```go
	issues := guestSaveValidateIssues(form, res, values, raw, stayFrom, stayTo, sig, child, existing, legalToday(d.now), lang)
```

4. In the same file, insert this function immediately before the line `func postForm(r *http.Request) map[string]string {` (one blank line between):

```go
// guestSaveValidateIssues is the save route's database-free checks, in the
// order of guest.py: the form, the signature, then the legal acknowledgement.
// The two sentences owned by this function are worded in the guest's language.
func guestSaveValidateIssues(form map[string]string, res guestResMeta, values validation.GuestRow, raw map[string]string, stayFrom, stayTo, sig string, child bool, existing *guestSaveRow, today time.Time, lang string) []validation.Issue {
	from, to := parseDate(stayFrom), parseDate(stayTo)
	issues := validation.ValidateGuestForm(values, &from, &to, today, raw)
	// guest.py:2462 — a new guest with no expected total gives a party size of 1–60.
	if existing == nil && headcount.Expected(res.overrideGuests, res.declaredGuests, res.reducedGuests) == nil {
		if n, err := strconv.Atoi(validation.Strip(form["party_size"])); err != nil || n < 1 || n > 60 {
			issues = append(issues, validation.Issue{Field: "party_size", Message: stringsCatalog.T(lang, "error_party_size", nil), Severity: "error"})
		}
	}
	if si := validation.GuestFormSignatureIssue(sig, child); si != nil {
		issues = append(issues, *si)
	}
	// guest.py:2480 — the guest must confirm the legal notice.
	if form["legal_ack"] == "" {
		issues = append(issues, validation.Issue{Field: "legal_ack", Message: stringsCatalog.T(lang, "legal_ack_missing", nil), Severity: "error"})
	}
	return issues
}
```

5. In `go/internal/web/guest/form_save_test.go` make three edits.
   a. In `TestGuestSaveValidateIssuesLegalAckOnEdit` change the call line to (no `cfg,` argument, trailing `"en"`):
   `issues := guestSaveValidateIssues(form, res, values, raw, "2026-06-01", "2026-06-05", form["signature"], false, existing, time.Date(2026, 6, 1, 0, 0, 0, 0, time.UTC), "en")`
   b. In `TestGuestSaveValidateIssuesPartySizeOnNew` change the call line to:
   `issues := guestSaveValidateIssues(form, res, values, raw, "2026-06-01", "2026-06-05", form["signature"], false, nil, time.Date(2026, 6, 1, 0, 0, 0, 0, time.UTC), "en")`
   (`cfg` stays declared: `validation.GuestFormRaw(form, cfg.defaultPurpose)` still uses it.)
   c. In `TestGuestSaveNoticeAndHeadcount` change the first line `pool := testPool(t)` to `pool := testPoolOptional(t)`. It is the only `testPool(t)` left in the file.

6. Delete the dead duplicate: `git rm -f go/internal/headcount/apply_declared_in.go`.

7. Format: from `go/` run `gofmt -w internal/web/guest/party_lead_hooks_test.go`. The only change is `pool:   pool,` becoming `pool: pool,`.

8. Key bump. In each of these four files replace `20261122-access-2036a` with `20261124-2046a` (StrReplace, one occurrence per file): `App/app/templates/base.html`, `go/internal/hostweb/layout/shell.html`, `go/internal/hostweb/layout/testdata/v2_cs_impersonating.html`, `go/internal/hostweb/layout/testdata/v2_alerts_hidden.html`. Then from `App/`: `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -30`. Expect `app2.css` in `App/tests/static_versions.json` to now read `"v": "20261124-2046a"` with a new sha256, and no other entry to change.

9. Commit the merge: `git add -A go App && git commit --no-edit 2>&1 | tail -5`. (If git wants a message: "Merge origin/main into PR 1319; gofmt; app2.css key 20261124-2046a".) Do not push.

## 5. Do not touch

`App/app/` Python source, `go/internal/web/guest/party.go`, `go/internal/web/guest/i18n.json`, `go/internal/guestcontract/*`, any migration, `docs/` other than your report. Do not call `guestcontract.CheckNewGuest` from the route (it would drop the 2071 per-language messages). Do not re-add `ApplyDeclaredInTx`. AGENTS.md hard rules 3, 4, 5, 8 apply. No template layout change, so no screenshot is needed (the key bump only).

## 6. Commands

From `go/` (each ends with `| tail -30`):

- `grep -rn '<<<<<<<\|>>>>>>>' internal/web/guest internal/headcount | tail -30` — prints nothing.
- `gofmt -l . | tail -30` — prints nothing.
- `go vet ./... 2>&1 | tail -30` — prints nothing.
- `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:5433/guest_test go test ./internal/web/guest/ ./internal/headcount/ ./internal/hostweb/... -count=1 2>&1 | tail -30` — all `ok`.
- `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:5433/guest_test go test ./... -count=1 2>&1 | grep -v '^ok\|no test files' | tail -30` — prints at most log lines and no `FAIL`. This is the single full Go run, allowed by the owner for this CI fix; run it once.
- `go test ./internal/web/guest/ -count=1 -v -run 'TestGuestSave' 2>&1 | grep -E '^(---|ok|FAIL)' | tail -30` — `TestGuestSaveNoticeAndHeadcount`, `TestGuestSaveValidateIssuesLegalAckOnEdit`, `TestGuestSaveValidateIssuesPartySizeOnNew` PASS (run with the `UBYHOST_TEST_DATABASE_URL` above so the first one is not skipped).

From `App/`:

- `.venv/bin/python -m pytest tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py -q --tb=short -x 2>&1 | tail -30` — 16 passed.

From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30` — clean.

## 7. Acceptance

- [ ] `git log --oneline -3` shows a merge commit with two parents (`git rev-list --parents -n1 HEAD | wc -w` prints 3).
- [ ] No conflict markers; `git status --short | tail -5` is empty.
- [ ] `gofmt -l .` and `go vet ./...` print nothing.
- [ ] Full `go test ./... -count=1` has no FAIL.
- [ ] All 2071 tests pass un-skipped, and both of main's `TestGuestSaveValidateIssues*` tests pass.
- [ ] `grep -rn '20261122-access-2036a' App go | tail -5` prints nothing.
- [ ] `test_static_versions.py` and `test_wp07_cache_heartbeats.py` pass.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- the merge conflicts in any file other than `form_save.go`;
- a test fails twice (a `relation ... does not exist` error means a test still uses `testPool` instead of `testPoolOptional`, see step 5c);
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/2084-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat HEAD~1`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `go/internal/web/guest/form_save.go`: the diff against the first parent must show only the validation extraction; everything else (single transaction, audit, `runCompletion`, claim gating) is HEAD's.
- `go/internal/headcount/apply_declared_in.go`: deleted on purpose; `applyDeclaredTx` in `party.go` is the single implementation.
- Main's new-guest path used `guestcontract.CheckNewGuest` (adds `ValidateStayDates` and `ValidateStayDateText`). Not adopted: for a new guest the stay dates are the reservation's own, and HEAD keeps the 2071 translated messages. Note this in known-issues if the owner wants the stricter check later.

## Owner steps

1. Open PR 1319 and read the merge commit's diff for `form_save.go` only.
2. Push the branch from the worktree: `git push origin HEAD:claude/nice-hawking-fw98ct`.
3. Wait for CI. When the Go job, `test` and `postgres full shard 1` are green, keep the PR as draft until you want it to ship.
