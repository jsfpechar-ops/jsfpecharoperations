# 0552: Go G5d-3b: render the submission_problem mail in Go, byte-equal to Python
Status: review
Depends on: 0551 (#646) | Base commit: main | Branch: claude/project-thread-bhyvh5
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 90k tokens
## 1. Objective
Plan v4 step 17 (G5), rule 1. The host mail sent when UbyPort does not take a batch is composed in Go with the same subject, text and HTML bytes Python produces. This brief is the pure renderer only (no database, no outbox): 0553 adds the contact lookup, stays query and outbox insert. Nothing calls the new code; nothing changes in production.
## 2. Context
- Python source of truth, `App/app/mail_notify.py`: `build_submission_problem` (594-694), `_build_text` (695), `_button` (724), `_build_html` (741-826), and every helper they reach: `_app` (95), `_esc` (99), `_clamp_reason` (114, `MAX_REASON_CHARS` 88), `_stay_label` (208), `_reason_text` (214), the `_block_*` helpers (240-380), `_footer_text`/`_footer_line_html`/`_shell` (458-544). Dates: `App/app/validation.py` `fmt_date` (1119) and `parse_iso_date` (1110). Strings: `App/app/host_i18n.py` `translate` (9921) and `lookup` (9903).
- Every production caller passes no `lang`, so the language is always `HOST_MAIL_LANGUAGE = "en"`. Go supports `en` only and returns an error for any other language.
- Golden pattern to copy: `App/scripts/ubyport_golden.py` + `App/tests/test_ubyport_golden.py` (regenerate to a tmp dir and compare byte for byte) and `go/internal/ubyport/request_test.go` (`goldenDir` relative path).
- **Traps:**
  - English strings: copy the exact `en` values of every key the renderer reads into Go constants, with `%(name)s` placeholders filled the way `lookup` does. Read the values out of `host_i18n.STRINGS["en"]` with a one-off Python command, never by hand.
  - `_esc` is `html.escape(quote=True)`: `& < > " '` become `&amp; &lt; &gt; &quot; &#x27;`. Go's `html.EscapeString` writes `&#39;` and `&#34;`: write your own.
  - `_clamp_reason` counts characters (runes), strips, and appends `…` after `rstrip()`.
  - `fmt_date` passes unparseable input through unchanged; accept what `parse_iso_date` accepts (read it).
  - Base URL: `_app` uses `UBYHOST_APP_BASE_URL` (trimmed, trailing `/` removed) or else `UBYHOST_PUBLIC_BASE_URL` (default `http://127.0.0.1:8080`, trailing `/` removed). In Go take the base URL as a parameter; the golden cases use `https://app.example.test`.
  - Empty `submission_id` (0) means no submission link, as in Python.
## 3. Files
New: `App/scripts/mail_golden.py`, `App/tests/golden/mail/cases.json` and one `<case>.subject.txt`, `<case>.text.txt`, `<case>.html` per case, `App/tests/test_mail_golden.py`, `go/internal/mail/submission_problem.go`, `go/internal/mail/submission_problem_test.go`. Write `docs/tasks/0552-report.md`. Nothing else.
## 4. Steps
1. `mail_golden.py` (`--out DIR`, default the golden dir; sets the base URL env before importing `app`; no database): for each case in `cases.json` call `build_submission_problem(...)` with `lang="en"` and write the three files. Cases (invented data only): `rejected_two_stays` (state `rejected`, reason with `<b>&"'`, two stays one with summary one without), `transport` (transport true, one stay), `no_reason_no_stays` (empty reason, no stays, submission_id 0), `long_reason` (1200-char reason with trailing spaces at the cut), `odd_date` (a stay `date_from` that does not parse), `unicode` (property `Byt Žižkov á`, summary with emoji).
2. `test_mail_golden.py`: regenerate into `tmp_path`, same names, byte-equal. Mark nothing `sqlite_only`.
3. `submission_problem.go`, package `mail`, top comment naming the Python lines: `type Stay struct{ID int64; DateFrom, DateTo, Summary string}`, `type Content struct{Subject, Text, HTML string}`, `func BuildSubmissionProblem(baseURL, lang, propertyName, state, reason string, transport bool, stays []Stay, submissionID int64) (Content, error)`.
4. `submission_problem_test.go`: read `cases.json` from `../../../App/tests/golden/mail`, render each case, compare all three parts byte for byte (print the first differing offset on failure); plus a test that `lang "cs"` errors.
5. Commit: `0552: Go G5d-3b submission_problem mail renderer matching Python`.
## 5. Do not touch
`App/app/` (all), other `go/internal/` packages, `go/cmd/`, `go.mod`/`go.sum` (no new dependency), compose, CI, templates/CSS/JS.
## 6. Commands
- From `go/`: `test -z "$(gofmt -l .)" && go vet ./... && go test ./internal/mail/ -count=1 2>&1 | tail -30`.
- From `App/`: `.venv/bin/python -m pytest tests/test_mail_golden.py -q --tb=short -x 2>&1 | tail -30`.
- From the repo root: `python3 scripts/context_lint.py | tail -3`.
## 7. Acceptance
`git diff --stat origin/main` lists only section 3 files and this brief. All six cases byte-equal in Go and in the Python regeneration test.
## 8. Stop and ask
Stop if `build_submission_problem` reads anything besides its arguments, `config` base URLs and `host_i18n` (for example the database or the clock), or if a string differs between what `translate` returns and the raw catalogue value.
## 9. Report
`docs/tasks/0552-report.md`: command tails, diff stat, anything you decided beyond section 2.
