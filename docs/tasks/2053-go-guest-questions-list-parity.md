# 2053: Go guest questions list matches Python

Status: ready. Executor: Haiku 5.5 (30 tool calls). Report: `docs/tasks/2053-report.md`.
Commit trailers on every commit:
```
Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014N5J8NCpdqN2TbR61gYRQf
```

## 1. Why (facts, already verified)

2052 parity run: `guide-questions-full` (cs/en x 390/768/1280) differs. Python row = the **guest's message text** as the link (`q.question`, which is `guest_chat_message.text`; the summary is not used in the list), then a grey sub line `date · stay link` (`t('guest_questions.door.<door>')`), and a badge cell: `Urgent` (attention) and `Unread` (neutral) only while open, then one state badge: open "Waiting" (action), answered "Answered" (done), dismissed "Dismissed" (neutral). Go shows the summary, no date, no badges, plain text `stay link · Waiting`.

Data is already loaded: `handoffList` (`go/internal/web/guest/leon_questions.go` ~420) selects `Question` (message text), `Urgent`, `Triaged`, `CreatedAt`, `Door`, `Status`. No new SQL, no new struct field. Catalogue keys `guest_questions.badge.urgent`, `guest_questions.badge.unread`, `guest_questions.state.{open,answered,dismissed}`, `guest_questions.door.{qr,stay}` already exist in en and cs in `leon_questions.go` lqI18n (en: Urgent, "Not read by Leon (AI)", Waiting, Answered, Dismissed; cs: Naléhavé, "Leon (AI) nečetl", Čeká, Zodpovězeno, Odloženo). Step 1 verifies that they match Python.

Read first: `AGENTS.md`, `docs/context/executor.md`. Open only the files named here.

## 2. Files

- `go/internal/web/guest/leon_questions.go` (one small method)
- `go/internal/web/guest/templates/leon_questions.tmpl` (list rows, ~lines 17-21)
- `go/internal/web/guest/leon_questions_db_test.go` (extend seed, add one test)
- `scripts/e2e/seed_parity_extra.py` (`questions` block, ~42-63)
- `scripts/e2e/parity_cases.py` (~109-111)
- `docs/tasks/2053-report.md` (new)

## 3. Do not touch

Python files, the detail page template (`guest_question.html` define), CSS, `lqI18n` strings (unless step 1 finds a mismatch: then STOP), other seed blocks, other parity cases, the ACCEPTED dict in the parity script, `App/`.

## 4. Steps

### Step 1: verify keys match Python (no edit)
```
grep -n "guest_questions.badge\|guest_questions.state\|guest_questions.door" App/app/*i18n*.py | head -30 | cut -c1-160
```
Compare with the Go values listed in section 1 (en and cs). Equal: go on. Different: STOP and ask.

### Step 2: day helper
Anchor: `func (s *lqServer) handoffGet(ctx context.Context, apt, qid int64) (*handoffRow, error) {` (`grep -nF`). Insert **before** it:
```go
// Day is the date part of CreatedAt, as Python shows q.created_at[:10].
func (r handoffRow) Day() string { return lqDay(r.CreatedAt) }

```
Command: `cd go && /usr/local/go/bin/go build ./internal/web/guest/ 2>&1 | tail -30` Expect no output.

### Step 3: template rows
In `go/internal/web/guest/templates/leon_questions.tmpl`, find with `grep -nF '<tr class="ui-row clickable-row" data-href="{{$.Base}}/{{.ID}}" tabindex="0" role="link">'` (it is inside `{{define "guest_questions.html"}}`, the first of two matches is not guaranteed: use the one inside the `{{range .Questions}}` of the list, ~line 17). Replace these 4 lines:
```
<tr class="ui-row clickable-row" data-href="{{$.Base}}/{{.ID}}" tabindex="0" role="link">
  <td><a href="{{$.Base}}/{{.ID}}">{{if .Summary}}{{.Summary}}{{else}}{{.Question}}{{end}}</a></td>
  <td>{{if eq .Door "qr"}}{{lqT $.Lang "guest_questions.door.qr"}}{{else}}{{lqT $.Lang "guest_questions.door.stay"}}{{end}} · {{lqT $.Lang (printf "guest_questions.state.%s" .Status)}}</td>
</tr>
```
with:
```
<tr class="ui-row clickable-row" data-href="{{$.Base}}/{{.ID}}" tabindex="0" role="link" aria-label="{{.Question}}">
  <td class="ui-cell-first" data-card="primary"><a href="{{$.Base}}/{{.ID}}">{{.Question}}</a><span class="ui-sub"> {{.Day}} · {{if eq .Door "qr"}}{{lqT $.Lang "guest_questions.door.qr"}}{{else}}{{lqT $.Lang "guest_questions.door.stay"}}{{end}}</span></td>
  <td data-card="badge">{{if and (eq .Status "open") (gt .Urgent 0)}}{{ui_badge "attention" (lqT $.Lang "guest_questions.badge.urgent")}} {{end}}{{if and (eq .Status "open") (eq .Triaged 0)}}{{ui_badge "neutral" (lqT $.Lang "guest_questions.badge.unread")}} {{end}}{{if eq .Status "open"}}{{ui_badge "action" (lqT $.Lang "guest_questions.state.open")}}{{else if eq .Status "answered"}}{{ui_badge "done" (lqT $.Lang "guest_questions.state.answered")}}{{else}}{{ui_badge "neutral" (lqT $.Lang "guest_questions.state.dismissed")}}{{end}}</td>
</tr>
```
Keep the surrounding `{{range .Questions}}` and `{{end}}</tbody>` untouched. The `<thead>` stays as is. Command: `cd go && /usr/local/go/bin/go build ./internal/web/guest/ 2>&1 | tail -30`. Expect no output. Commit `2053 step 3`.

### Step 4: Go tests
In `leon_questions_db_test.go`, function `seedHandoffQuestions`:
1. Extend the message insert: add a fourth tuple `(7804, 780, 'guest', 'question', 'Heater is broken now', '', '2026-11-20')` (put a comma after the `(7803, ...)` tuple).
2. Extend the guest_question insert: add `(7904, 780, 78, 7804, 'Heater summary differs', 'open', '', 1, 0, '2026-11-20')` after the 7903 tuple (comma after it). Row 7904 is open, urgent, not triaged.

Add at the end of the file:
```go
func TestHandoffListMatchesPythonRows(t *testing.T) {
	s, q := seedHandoffQuestions(t)
	rows, open, err := s.handoffList(context.Background(), 78)
	if err != nil {
		t.Fatal(err)
	}
	if open != 2 {
		t.Fatalf("open %d, want 2", open)
	}
	rec := httptest.NewRecorder()
	r := httptest.NewRequest("GET", "/apartments/78/guide/questions", nil)
	q.r = r
	data := map[string]any{"Lang": "en", "ApartmentID": int64(78), "ApartmentName": "Handoff Flat", "OpenCount": open,
		"Questions": rows, "Base": "/apartments/78/guide/questions"}
	s.renderHost(rec, r, q, "guest_questions.html", data)
	body := rec.Body.String()
	for _, want := range []string{
		">Heater is broken now</a>", ">Where is the key?</a>", ">Is the heater on?</a>",
		`<span class="ui-sub"> 2026-11-20 · QR page</span>`,
		"Urgent", "Not read by Leon (AI)", "Waiting", "Answered", "Dismissed",
	} {
		if !strings.Contains(body, want) {
			t.Errorf("list misses %q", want)
		}
	}
	if strings.Contains(body, "Guest asks for the key") || strings.Contains(body, "Heater question") {
		t.Error("list shows the summary; Python shows the message text")
	}
	// Row order and per-row badges: 7904 (open urgent unread) first, then 7901, then answered 7902 and dismissed 7903 by newest first.
	i4 := strings.Index(body, "/questions/7904")
	i1 := strings.Index(body, "/questions/7901")
	i3 := strings.Index(body, "/questions/7903")
	i2 := strings.Index(body, "/questions/7902")
	if !(i4 >= 0 && i4 < i1 && i1 < i3 && i3 < i2) {
		t.Errorf("row order wrong: %d %d %d %d", i4, i1, i3, i2)
	}
	// A dismissed row must not carry Urgent or Unread, even if the columns say so.
	row3 := body[i3:]
	if j := strings.Index(row3, "</tr>"); j > 0 {
		row3 = row3[:j]
	}
	if strings.Contains(row3, "Urgent") || strings.Contains(row3, "Not read by Leon") {
		t.Error("dismissed row shows an open-only badge")
	}
}
```
(Row 7902/7903 both have `created_at` equal; dismissed and answered sort by `-q.id`, so 7903 comes before 7902.)
Commands (use `go vet` if the `renderHost` signature differs: STOP then):
```
cd go && gofmt -l ./internal/web/guest/ 2>&1 | tail -30
cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:5433/layout_test PATH=/usr/local/go/bin:$PATH go test ./internal/web/guest/... -count=1 -run 'Handoff|LeonQuestions' -v 2>&1 | tail -30
```
Expect: gofmt prints nothing; `--- PASS` for TestHandoffListMatchesPythonRows and the three older TestHandoff* tests, 0 SKIP for these. If the Postgres on 5433 is down, source it first: `source scripts/e2e/parity_env.sh` as its own command (never pipe `source`). Test fails: read the last 30 lines, fix once, rerun, else STOP. Also run `cd go && PATH=/usr/local/go/bin:$PATH go test ./internal/web/guest/... -count=1 2>&1 | tail -30`: expect `ok`. Commit `2053 step 4`.

### Step 5: seed
In `scripts/e2e/seed_parity_extra.py`, `questions` block. Anchor: `grep -nF '"urgent": 0, "triaged": 1, "created_at": now, "answered_at": now,' scripts/e2e/seed_parity_extra.py`. After the closing `})` of that insert (the `out["question_answered"]` one), add:
```python
    m3 = leon._store(chat["id"], "guest", "question", "E2E: the hot water stopped, please help now")
    m4 = leon._store(chat["id"], "guest", "question", "E2E: can we keep the bikes in the hall?")
    out["question_urgent_unread"] = db.insert("guest_question", {
        "chat_id": chat["id"], "message_id": m3, "apartment_id": apt,
        "summary": "E2E urgent unread: no hot water", "status": "open", "answer": "",
        "urgent": 1, "triaged": 0, "created_at": now,
    })
    out["question_dismissed"] = db.insert("guest_question", {
        "chat_id": chat["id"], "message_id": m4, "apartment_id": apt,
        "summary": "E2E question dismissed", "status": "dismissed", "answer": "",
        "urgent": 0, "triaged": 1, "created_at": now, "answered_at": now,
    })
```
(`dismiss()` in `App/app/guest_handoff.py:222` sets status `dismissed` and `answered_at`; columns match the inserts above.) Command: `python3 -c "import ast,sys;ast.parse(open('scripts/e2e/seed_parity_extra.py').read())" 2>&1 | tail -30` Expect no output.

### Step 6: parity cases
In `scripts/e2e/parity_cases.py`, after the line `("guide-question-answered", "/apartments/{apt}/guide/questions/{question_answered}", "host", "F"),` (grep -nF it) add:
```python
    ("guide-question-urgent-unread", "/apartments/{apt}/guide/questions/{question_urgent_unread}", "host", "F"),
    ("guide-question-dismissed", "/apartments/{apt}/guide/questions/{question_dismissed}", "host", "F"),
```
Command: `python3 -c "import ast;ast.parse(open('scripts/e2e/parity_cases.py').read())" 2>&1 | tail -30` Expect no output. Commit `2053 steps 5-6`.

### Step 7: parity rerun (list and the two new detail cases)
Run `source scripts/e2e/parity_env.sh` as its own command (never piped). Then from the repo root, use the exact invocation the 2051 brief uses (`docs/tasks/2051-go-submissions-null-safety-guide-save.md` line ~89), with:
```
PARITY_GROUP=F PARITY_ONLY=guide-questions-full-cs,guide-questions-full-en,guide-question-urgent-unread-cs,guide-question-urgent-unread-en,guide-question-dismissed-cs,guide-question-dismissed-en,guide-question-cs,guide-question-en,guide-question-answered-cs,guide-question-answered-en App/.venv/bin/python scripts/e2e/page_parity_visual.py 2>&1 | tail -30
```
(If the case names carry the width in a different suffix, copy the pattern from the 2051 line; a name not found: STOP.) Expect: all rows `identical` or `invisible` at 390/768/1280 for cs and en, Go status 200 everywhere. The seed must be rerun by the script itself; if the script does not reseed, STOP and ask.
For any row reported visible: open its `*-side.png` (Python left, Go right) and describe it in the report in plain words. Even when all identical, open `guide-questions-full-en-1280-side.png`, `-768-side.png` and `-390-side.png` once each and describe: which five rows are shown, order, badges per row, wrapping at 390.

### Step 8: UX gate (rules 7 and 10)
From `App/`:
```
UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:5433/layout_test .venv/bin/python -m pytest tests/test_go_pages_layout_lint_browser.py -q -x -rs 2>&1 | tail -30
```
Expect `passed`, `0 skipped`. Then, if `tests/test_layout_lint_browser.py` is in the test-map row for host pages, run it the same way: `0 skipped`. The three parity list screenshots from step 7 count as the per-page screenshots; in the report write "390: ...; 768: ...; 1280: ..." for the list page. Skipped tests mean broken: STOP.

### Step 9: lint, report, commit
`python3 scripts/context_lint.py 2>&1 | tail -3` Expect no errors. Write `docs/tasks/2053-report.md` (600 tokens max: files, command tails, section 5 ticked, per-width description, deviations). Mark `Status: review`. Commit `Brief 2053: Go guest questions list parity` with the trailers. Do not push, do not open a PR unless the orchestrator says so.

## 5. Checklist

- [ ] link text is the message text (`.Question`), not the summary
- [ ] sub line `date · stay link` (cs: `odkaz na pobyt`; QR door: `QR page`)
- [ ] Urgent and Unread badges only while open; state badge Waiting / Answered / Dismissed
- [ ] `go test ./internal/web/guest/...` ok with DB, new test passes, 0 skip for it
- [ ] two new seed rows (open urgent unread, dismissed) and two new parity cases
- [ ] parity list and detail cases identical or invisible at 3 widths, cs and en
- [ ] layout lint browser tests green, 0 skipped
- [ ] context_lint clean, report written, commits carry trailers

## 6. Stop and ask

- An anchor is not found verbatim, or a catalogue string differs from Python.
- `renderHost` or `handoffRow` has a different shape than shown.
- Parity shows any visible difference you cannot explain from this brief, or the script cannot reseed.
- A test fails twice, or any test skips.
