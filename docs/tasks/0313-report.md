# 0313 report (Havel quick-help topics)

Status: review
Done: steps 1 to 8 and the report. Left: none (the PR is for the owner to open).

## Files changed
- App/app/havel_topics.py (step 2, new)
- App/app/host_i18n.py, App/app/host_vi_i18n.py: `havel.topic.support_body` in en, cs, vi (step 3)
- App/app/routes/havel.py: topics in the context, `q`, `read_keys`, nav keys, fragment template (step 4)
- App/app/templates/_havel_topics.html, _havel_fragment.html (new), _havel_form.html, havel.html (step 5)
- App/app/static/host2.css, App/app/templates/base.html (key 20261025-0313), App/tests/static_versions.json, docs/design/catalog.json, docs/design/pages/havel.md (step 6)
- App/tests/test_havel_topics.py (step 7, new)
- docs/tasks/screenshots-0313/havel-topic-390.png (step 8, new)

## Commands (last lines)
- Step 3: `Napište True`
- Step 4: import ok; `6` (havel_topics refs), `1` (safe_local_path)
- Step 5: `app/templates/havel.html:1`, `_havel_fragment.html:2`
- Step 6: `wrote .../App/tests/static_versions.json (36 files)`; `design lint: OK`
- Step 7: `11 passed in 1.79s` (test_havel_topics + test_havel_page)
- Step 8 screenshot: `1 passed in 2.06s`; throwaway test deleted
- Guards (test_design_guardrails_browser, test_a11y_guard_browser): `14 passed in 109.37s`, 0 skipped
- Section 6 list (topics, page, engine, host_i18n, em dashes, static versions): `53 passed, 1 warning`
- `design lint: OK`; `context lint: OK`

## Section 7
- [x] topics page, questions, answers, back links (tests and screenshot)
- [x] fragment with X-Havel: 1 (test)
- [x] topic and read_keys reach havel.ask, nav key reservations -> stays (test)
- [x] keys resolve in en and cs; bad topic or q gives 200 (test)
- [x] screenshot at 390 looked at; guards 0 skipped; design lint OK; static manifest written

## Deviations
- Drift applied: `host_i18n.lang_from_request(request)` in `_page_context` (not `request.state.lang`); cache key `20261025-0313`; topic property links use the first owned property id; tests use `html.unescape` and `?lang=en`; browser `chromium-1243`.
- `pages` and `page_url` keys went into the step 4 commit (the `_page_context` rewrite), not step 5.
- The step 5 grep for `havel_show_topics` in `_havel_fragment.html` gives 2 lines, not 1 (the attribute and the include are on separate lines). Behaviour is as specified.
- Step 8 fix: the a11y guard flagged `heading-level-skipped` (h3 under h1) and `nav-no-current` on the topic list. Title is now h2; the list is a `div role="group"`. Guards then pass.
- The step 4 `havel_page` body uses `items=[]` as the brief says, so the empty page no longer shows the `havel.intro` item.
- The screenshot shows "Havel is unavailable right now" (no AI in the harness). The template hides "Still need help? Ask Havel" and the composer in that state, so they are not in the image.

## Questions
1. Should "Still need help? Ask Havel" show even when Havel is unavailable (currently hidden by `not havel_state`)? The brief's acceptance expects it.

## Owner steps left
1. Open the PR for task/0313-havel-topics and check docs/tasks/screenshots-0313/havel-topic-390.png.
2. On staging, check that "Still need help? Ask Havel" appears and moves the cursor to the box (see Question 1).
