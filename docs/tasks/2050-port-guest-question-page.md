# 2050: port the missing guest-question page elements to Go (Option 1)

Status: todo
Executor: Haiku 5.5, alone. Limits: 100k tokens, 30 tool calls. Read only AGENTS.md, docs/context/executor.md, this brief and the files named below.
Follows: 2049 (copy and harness fixes; run it first, step 1 edits the same Go file). Branch: the branch you are on; do not push or merge.

## 1. Objective

Owner decision (binding): every function Python has must exist in Go. Python's host page `App/app/templates/guest_question.html` has elements the Go page (`go/internal/web/guest/templates/leon_questions.tmpl`, define `guest_question.html`) lacks. Port them with the same markup, copy and order. The list page (`guest_questions.html`) and the guide-page link `guest_questions.link` already match (Go: `go/internal/web/ai/guide/templates/guide_index.tmpl:34`, `QuestionsOpen`).

## 2. Context (verified, orchestrator, read-only)

Python host keys for this area that no Go file or JSON carries (16):

| Key | Class |
|---|---|
| guest_question.urgent_banner | MISSING-ELEMENT |
| guest_question.shown_to_guest | MISSING-ELEMENT |
| guest_question.field.answer, guest_question.field.answer_help | MISSING-ELEMENT |
| guest_question.dismiss_help | MISSING-ELEMENT |
| guest_question.dismissed_banner | MISSING-ELEMENT |
| guest_question.card.title, .help, .button, .done, .open | MISSING-ELEMENT (whole "Add to guide" section) |
| mail.guest_question.subject, .heading, .intro, .action, .footer | PRESENT-OTHER-KEY: English constants in `go/internal/mail/guest_question_host.go` (same text). A Czech host gets English there: out of scope, see 2049 owner questions |
| guest_questions.link | PRESENT-OTHER-KEY (Go guide catalogue, `go/internal/web/ai/guide/i18n.json`, used in `guide_index.tmpl`) |
| notification.guest_question.detail, .title, .title.urgent | PRESENT (`go/internal/hostweb/layout/i18n.json`) |
| guest_questions.badge.urgent, .unread | key present in `lqI18n`, but the Go detail page never renders the badges: MISSING-ELEMENT |

No DEAD keys found. Differences beyond keys, same page:
- Python wraps each part in `ui_section` (ids `question`, `answer`, `card`, `more`); Go has a plain blockquote and one form.
- Python shows a date line `created_at[:10] · door label` under the header; Go does not.
- Python topic list (11, `App/app/guest_guide.py:15` TOPICS: arrival, wifi, heating, kitchen, rooms, bathroom, rules, trash, checkout, area, emergency; labels `guest_guide.topic.<t>`; default `rules`); Go page hard-codes 7 other topics (`renderQuestion` in `leon_questions.go` ~line 540) and prints the raw slug.
- Python answered question: shows the answer as paragraphs plus `shown_to_guest`, and NO answer form; open or dismissed: answer form; dismiss form only while open.
- `card_for` (Python `guest_handoff.py:103`): the card id is the newest `guide_item` of the apartment with `kind='custom'` and `title = card_title(question)`; title = whitespace-collapsed summary, else question text, else "Guest question", cut to 120 chars (`guest_guide.LIMITS["title"]`; Go `handoffAddGuide` cuts at 120 too).

## 3. Files (you may touch only these)

`go/internal/web/guest/templates/leon_questions.tmpl`, `go/internal/web/guest/leon_questions.go`, `go/internal/web/guest/leon_questions_test.go`, `scripts/e2e/seed_parity_extra.py`, `scripts/e2e/parity_cases.py`, `docs/tasks/2050-report.md`.

## 4. Steps (one commit each: `2050 step k`)

### Step 1: strings (`leon_questions.go`, `lqI18n`)
Add these keys to BOTH the en and the cs block, after `"guest_question.dismiss"`. Copy the values from `App/app/host_i18n.py` (en: first block; cs: the cs block near line 10354): `grep -n '"guest_question\.\(urgent_banner\|shown_to_guest\|field\.answer\|field\.answer_help\|dismiss_help\|dismissed_banner\|card\.[a-z]*\)"' App/app/host_i18n.py | cut -c1-260`. 11 keys: urgent_banner, shown_to_guest, field.answer, field.answer_help, dismiss_help, dismissed_banner, card.title, card.help, card.button, card.done, card.open. Also add (same source) `guest_guide.add.topic`, `guest_guide.more.title` and the 11 `guest_guide.topic.<t>` keys listed above. Escape quotes as the file does; keep `%(max)s` as is. Keep existing keys (do not delete unused ones).
Check: `cd go && go test ./internal/web/guest/... 2>&1 | tail -30`.

### Step 2: handler data (`leon_questions.go`)
a) `handoffRow` add `CreatedAt string`. In `handoffList` and `handoffGet` add `COALESCE(q.created_at,'')` as the last selected column and scan it last (both functions, both queries). `q.urgent` and `q.triaged` are already selected.
b) New `func (s *lqServer) handoffCardID(ctx context.Context, apt int64, row *handoffRow) (int64, error)`: title = `strings.Join(strings.Fields(first non-empty of row.Summary, row.Question), " ")`, empty -> "Guest question", cut to 120 runes then `strings.TrimSpace`; `SELECT id FROM guide_item WHERE apartment_id = $1 AND kind = 'custom' AND title = $2 ORDER BY id DESC LIMIT 1`; no row -> 0, nil.
c) In `renderQuestion`, replace the `Topics` list by the 11 Python topics (order above) and add to `data`: `"Question": row` fields as separate keys: `Status` (row.Status), `Urgent` (row.Urgent == 1 && row.Status == "open"), `Triaged` (row.Triaged != 0), `Door`, `CreatedDay` (first 10 chars of CreatedAt), `AnswerText` (row.Answer), `CardID` (from handoffCardID, only when `row.Status == "answered"`, else 0), keep `Answered`.
Check: `cd go && go build ./... 2>&1 | tail -30`.

### Step 3: template (`leon_questions.tmpl`, define `guest_question.html`)
Rewrite the body (keep the header and `.Error` banner lines) to mirror `App/app/templates/guest_question.html` lines 15-65, using the Go macros `ui_section`, `ui_banner`, `ui_badge`, `ui_textarea`, `ui_select`, `ui_button` (see `go/internal/hostweb/layout/macros_ui.go`; copy the argument order from another `.tmpl` that calls them: `grep -rn "ui_textarea\|ui_select" go/internal/web --include=*.tmpl | head -3`). Order:
1. `<div class="ui-sub">{{.CreatedDay}} · door label</div>` (`guest_questions.door.qr` / `.stay` by `.Door`).
2. `.Error` banner (exists), then `{{if .Urgent}}ui_banner "attention" urgent_banner{{end}}`.
3. Section id `question`, title `guest_question.asked`: urgent badge (`guest_questions.badge.urgent`, kind attention) when `.Urgent`; unread badge (`guest_questions.badge.unread`, kind neutral) when `not .Triaged`; question text as paragraphs (split on newline, skip blank; add a Go func or loop over `strings.Split` precomputed in the handler as `QuestionLines`, `SummaryLines`, `AnswerLines`); summary lines under `<p class="ui-sub">guest_question.summary</p>` only when the summary differs from the question.
4. Answered: section id `answer` (title `guest_question.your_answer`) with answer paragraphs and `<p class="ui-sub">shown_to_guest</p>`; section id `card` (title `card.title`): if `.CardID > 0`: `<p class="ui-sub">card.done</p>` plus button secondary `card.open` href `/apartments/<id>/guide/<CardID>`; else `<p class="ui-sub">card.help</p>` and the form posting to `{{.Base}}/{{.QuestionID}}/card` with csrf, `ui_select` id `question-topic`, label `guest_guide.add.topic`, options (slug, `guest_guide.topic.<slug>`), selected `rules`, name `topic`, and button primary `card.button` icon `plus`.
5. Not answered: section id `answer` (title `guest_question.your_answer`) with the dismissed banner (neutral) when `.Status == "dismissed"`, then the form to `{{.Base}}/{{.QuestionID}}` with csrf, `ui_textarea` id `question-answer`, label `field.answer`, name `answer`, help `field.answer_help` with `max` = `.MaxChars`, rows 5, `maxlength` and `required`, value `.AnswerDraft`; button primary `guest_question.send` icon `send`. When `.Status == "open"`: section id `more` (title `guest_guide.more.title`) with a form to `{{.Base}}/{{.QuestionID}}/dismiss`, csrf, `<p class="ui-sub">dismiss_help</p>`, button quiet `guest_question.dismiss`.
Remove the old single form and its dismiss `formaction` button.
Check: `cd go && go build ./... 2>&1 | tail -30 && go test ./internal/web/guest/... 2>&1 | tail -30`. A golden or test that pins the old markup: update only that expectation to the new markup and say so in the report; any other failure: STOP.

### Step 4: Go tests (`leon_questions_test.go`)
Add tests next to `TestLeonQuestionsGoldenShape` (copy its setup): (a) open urgent question page contains the `guest_question.urgent_banner` en text and the `guest_questions.badge.urgent` text, and the dismiss section; (b) dismissed question shows `dismissed_banner` and no dismiss form; (c) answered question shows `shown_to_guest` text, the card select with 11 options, and no `name="answer"` textarea; (d) answered question whose custom card exists (insert a `guide_item` with the card title) shows `card.done` and the open link. Use the en texts from step 1. Check: `cd go && go test ./internal/web/guest/... 2>&1 | tail -30`.

### Step 5: seed and parity cases
a) `scripts/e2e/seed_parity_extra.py`, function `questions`: add a third row after the answered one: `summary "E2E question urgent open"`, `status "open"`, `urgent 1`, `triaged 0`, same other fields; set `out["question_urgent_id"]`. Also add `out["question_answered_id"]` for the answered row (capture the `db.insert` return).
b) `scripts/e2e/parity_cases.py`: `grep -n "question" scripts/e2e/parity_cases.py | head -20`. Add cases for the guest-guide index (`apt-guide`, exists: confirm it shows the questions link with the open count; else add), the list (`apt-guide-questions`, exists) and three question detail cases: open urgent, open normal, answered. Copy the spec of the existing question-detail case (if none, copy the form of `apt-guide-questions` and use `/apartments/{apt}/guide/questions/{question_urgent_id}` etc.).
c) Rerun from `App/` (2045 form, add `PARITY_GROUP` if the script needs it): `PARITY_ONLY=apt-guide-cs,apt-guide-en,apt-guide-questions-cs,apt-guide-questions-en,<the three new detail cases, cs and en> .venv/bin/python ../scripts/e2e/page_parity_visual.py 2>&1 | tail -30`. Expect all `identical` or `invisible` at 390/768/1280. A `visible` row: open that one side PNG (max 2 reads), report it, STOP. Rule 7 and 10 apply: also `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_go_pages_layout_lint_browser.py -q -x -rs 2>&1 | tail -30` (0 skipped, zero findings), open the three `-go.png` widths of the urgent detail case and write "390: ...; 768: ...; 1280: ..." in the report.

## 5. Do not touch

(Details in section 7.)

## 6. Commands

Each step ends with its command.

## 7. Acceptance

See the checklist at the end of section 8. Touch nothing outside section 3: `App/app`, `deploy/`, other Go packages and templates, goldens other than the one in step 3, dependencies, secrets. No push, no merge.

## 8. Stop and ask

Anchor not found; a macro's argument order unclear after one grep; a golden diff outside the question pages; a test fails twice; a parity row visible.

Checklist (tick in the report):
- [ ] 11 + 13 strings added to en and cs (copied from Python)
- [ ] detail page: urgent banner and badge, unread badge, date line, sections, shown_to_guest, dismiss_help, dismissed banner, card section with 11 topics
- [ ] 4 new Go tests and `go test ./internal/web/guest/...` green
- [ ] parity rows (guide index, questions list, 3 detail cases, cs and en) identical/invisible
- [ ] layout lint browser test green, 0 skipped; 390/768/1280 lines written

## 9. Report
`docs/tasks/2050-report.md`, 600 tokens at most: files changed, each command with its last 5 lines, checklist, Deviations, Questions, `Status: review`. Commit trailers:
```
Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014N5J8NCpdqN2TbR61gYRQf
```

## 10. Follow-up (orchestrator review of the first run)

Run in the same worktree, on top of commit af55109.
1. Title cut parity. Read Python `card_title` and `card_for` in `App/app/guest_handoff.py` (~232-262; grep `def card_title`, `def card_for`). Python slices `str` (characters). In `go/internal/web/guest/leon_questions.go`, the existing `handoffAddGuide` cuts 120 **bytes** (`title[:120]`, ~line 561): this can split a UTF-8 Czech character and makes the new `handoffCardID` lookup (120 runes, ~line 471) miss the card. Make both use one helper that matches `card_title` exactly (runes, same trim/whitespace rules as Python). Add a Go unit test with a Czech title over 120 characters containing diacritics: add-to-guide then card lookup finds the same card.
2. Card link. Python's "open card" button is `base_url ~ '/' ~ card_id` (App/app/templates/guest_question.html ~34); find `base_url` for that page in Python (grep `base_url` in App/app/routes/guest_guide.py or the question route) and make Go's href identical.
3. DB-backed tests: rerun `go test ./internal/web/guest/...` with `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:5433/layout_test`; 0 skipped for the files you touched. Write the DB-backed tests the brief's step 4 asked for (answered question shows answer + shown_to_guest; open urgent shows the banner and badge; dismissed shows the dismissed banner; card done shows the open-card link).
4. Layout lint browser test green, 0 skipped; screenshots of the Go question detail page (open urgent, answered, dismissed) at 390/768/1280, viewed and described per width.
