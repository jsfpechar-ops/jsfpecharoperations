# 0552 report: Go submission_problem mail renderer

Status: review

## Files changed
- New: App/scripts/mail_golden.py, App/tests/test_mail_golden.py, App/tests/golden/mail/ (cases.json and 18 golden files for 6 cases), go/internal/mail/submission_problem.go, go/internal/mail/submission_problem_test.go, docs/tasks/0552-report.md.
- Not touched: App/app, other go packages, go.mod, go.sum, templates, CSS, JS.

## Commands (last lines)
- `cd go && gofmt -l . (empty) && go vet ./... && go test ./internal/mail/ -count=1 -v`: all 6 cases PASS (byte-equal subject, text, HTML), lang "cs" refused: `ok github.com/.../go/internal/mail 0.004s`.
- `cd App && .venv/bin/python -m pytest tests/test_mail_golden.py -q --tb=short -x`: `1 passed in 0.66s`.
- `python3 scripts/context_lint.py | tail -3`: `ERROR docs/tasks/0552-go-g5d3b-mail-render.md: needs a 'Status: <blocked|done|in-progress|replaced|review|todo>' line` then `context lint: FAIL`. The brief's own line is `Status: ready`, which the lint does not accept. The brief is not mine to edit, so it is left as is.

## Deviations from the brief
1. `Stay` has an extra `PropertyName` field. Python prints each stay's property name in the HTML, and the brief's struct had no place for it.
2. `BuildSubmissionProblem` takes two base URLs: `appBaseURL` for links and `publicBaseURL` for the logo. Python uses `config.app_base_url()` for links and `PUBLIC_BASE_URL` for the logo, so one parameter cannot match both. The signature is `(appBaseURL, publicBaseURL, lang, propertyName, state, reason, transport, stays, submissionID)`.
3. The golden script sets `UBYHOST_PUBLIC_BASE_URL=https://www.example.test` beside the app origin, so a swapped pair changes the bytes.
4. `lang` "" maps to "en", as Python's `normalise_language` does. Any other language returns `ErrLanguage`, as the brief says.
5. `cases.json` is written by a one-off script, not by hand, so the 1200-character reason is exact. The English constants were generated from `host_i18n.STRINGS["en"]` by a one-off script in /tmp (outside the repo). It checks that `translate()` equals the raw catalogue value and aborts on any other `%`.
6. Not covered by the goldens: `fmtDate` prints years below 1000 without zero padding. Python's `%Y` is platform-dependent there.

## Owner steps left
None. Nothing was pushed. The owner or orchestrator needs to decide on the brief's `Status: ready` line for the lint.
