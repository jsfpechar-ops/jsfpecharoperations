# 2050 report: guest-question page elements in Go

Status: blocked (follow-up 2 step 2: screenshots not taken, executor call cap)

## Files changed
- go/internal/web/guest/leon_questions.go: 24 strings (en and cs) added to lqI18n; handoffRow.CreatedAt; handoffCardID; lqTopics (11); lqTopicOptions; lqDay; lqLines; renderQuestion data (Status, Urgent, Triaged, Door, CreatedDay, AnswerText, CardID, QuestionLines, SummaryLines, AnswerLines, SummaryDiffers, TopicOptions, ApartmentID).
- go/internal/web/guest/templates/leon_questions.tmpl: guest_question.html body rewritten to mirror guest_question.html (date line, urgent banner, question section with badges, answered section with card section, open or dismissed answer form, more section with dismiss form).
- go/internal/web/guest/leon_questions_keys_test.go (new file): checks that every new key exists in en and cs, that there are 11 topics, and that the template has the expected sections.

## Python elements now in Go
- guest_question.urgent_banner, shown_to_guest, field.answer, field.answer_help, dismiss_help, dismissed_banner: in the template (ports the Python markup).
- card section: Add to guide title, help, button, done, open link, and the 11-topic select.
- more section (dismiss) and ui-section ids question, answer, card, more.
- Date line, urgent and unread badges, 11 topics (replaces the 7 hard-coded topics).

## Commands
- go build ./... : rc 0
- gofmt -w on leon_questions.go and the new test: rc 0
- go test ./internal/web/guest/... -count=1 : ok (last 5 lines: PASS for TestLeonQuestionPageKeysAndSections, TestLeonQuestionsGoldenShape, TestLeonQuestionsSignedOutGolden, TestLeonQuestionsTemplateChrome; ok github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/guest)
- The two DB integration tests (TestLeonGoneWithoutLiveGuide, TestLeonEntryCodeStayAndQRIntegration) SKIP because UBYHOST_TEST_DATABASE_URL is not set. Not run.

## Checklist
- [x] strings added to en and cs (copied from host_i18n.py)
- [ ] detail page DB-rendered check: not run (no DB render test)
- [ ] 4 DB-backed Go tests (brief step 4): NOT written. Replaced by one template-source test (deviation).
- [ ] seed_parity_extra.py and parity_cases.py (step 5): skipped, moved to 2052 (no parity run, per owner exception)
- [ ] layout lint browser test 390/768/1280: NOT run (cap reached)
- [ ] screenshots: NOT taken

## Deviations
- Single commit instead of per-step commits (cap reached).
- New test file leon_questions_keys_test.go instead of additions to leon_questions_test.go.
- Brief step 4 DB tests not written; the template-source test only checks keys and sections, not rendered markup.
- handoffCardID cuts the title at 120 runes; handoffAddGuide (existing) cuts at 120 bytes. For non-ASCII titles longer than 120 the card lookup can miss. Not fixed here (outside brief).
- Card link uses /apartments/<id>/guide/<CardID> from the brief; Python's base_url was not checked.
- Python's settings_back_header partial and ui_section call-block structure are written as the equivalent raw section markup (the Go ui_section macro is a call block that the template cannot use).

## Questions
- Should the DB-backed tests (brief step 4) and the parity seed (2052) be scheduled as a follow-up?

## Owner steps left
- Run the layout lint browser test and the 390/768/1280 screenshots for guest-question detail (not done).

## Follow-up (brief section 10)

- Step 1 (5bafc80): `handoffCardTitle` in leon_questions.go mirrors Python `card_title` (summary else question, whitespace collapsed, 120 runes, strip, "Guest question" fallback). Used by both `handoffCardID` and `handoffAddGuide`. Unit test with a 130-character Czech title.
- Step 2: no diff. Python `base_url` is `/apartments/<id>/guide`, so the card link is `/apartments/<id>/guide/<card_id>`. The Go href was already this string; nothing changed.
- Step 3 (6db38f7): `leon_questions_db_test.go` with 4 DB-backed tests (open urgent banner; answered answer and shown_to_guest; dismissed banner; add-to-guide then card lookup and open-card href). Add-to-guide wrote to a non-existent `guide_card` table; it now writes `guide_item.steps`.
- Guest package with DB: ok, 3 SKIP (TestConfirmClaimAppliesDeclaredGuests, TestStayOverviewMailOnHonorsClaimCookie, TestConfirmClaimRace; none from the files touched).
- Step 4 not run: layout lint browser test and 390/768/1280 screenshots were not run (executor call cap).
- Owner: step 4 still open. Run `test_layout_lint_browser.py` and screenshot the question detail page (open urgent, answered, dismissed).

## Follow-up 2 (brief section 11)

- Step 1 (dcbb909): handoff add-to-guide sets `guide_item.sort_order = len(Kinds)+1` (25), same value as Python `add_custom` and the Go custom-card paths. Go `guide_data.go` `addCustom` uses the unexported `guideKinds` (24 entries), so the guest package uses exported `guideimport.Kinds` (24 entries, same count). DB test asserts sort_order. `go test -run TestHandoff ./internal/web/guest/` passes (4 DB tests + 1 unit test, 0 skipped).
- Step 2: `test_layout_lint_browser.py`: 4 passed, 0 skipped (230.9 s).
- Step 2 screenshots (390/768/1280 for open urgent, answered, dismissed): NOT taken. The executor call cap was reached before seeding the rows and viewing the shots. Owner or next executor: seed the three questions in layout_test and take the nine shots.

