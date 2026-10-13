# 0097: Reporting & fees explained; no guessed facility name

Status: done
Depends on: 3248c8d (`claude/quirky-lamport-9svmd1`) | Branch: local worktree, not pushed
Executor: Claude (owner-authorized) | Fits one session

## 1. Objective
This task acts on the owner's staging feedback for Settings › Reporting & fees:
- remove the request-letter generator;
- never prefill the facility name;
- explain the police and fee fields in plain words;
- show the example police letter in the section;
- fix the misplaced summary on the Stay fees list.

## 2. Context
- Rule 1: filing correctness beats everything. Payloads, credentials, code lists and the readiness rules stay unchanged, except that the name default is gone.
- Help uses the 0093 macros `field_label`/`help_tip`. Plan §4: help is a `?`, one explanation in one place, no backend narration.
- History: 0043 added the defaults, 0044 the letter, and 0087 moved the sample PDF to the Guide.

## 3. Files
| Path | What |
|---|---|
| App/app/routes/admin.py | `_apply_police_defaults` without the name default; letter helper removed; `/ws-request.txt` → 303 to Police reporting |
| App/app/templates/_property_editor.html | Police reporting section only: sample link, fine-print line (`id="ws-request-letter"` kept for old anchors), `?` for each field |
| App/app/templates/_stay_fee_fields.html | `?` for each fee field (input names unchanged) |
| App/app/host_i18n.py | hints rewritten in place, `ws_request.*` removed, `# 0097` block |
| App/app/static/host.css | `.fee-list-summary` margin `0 auto 10px`; `/* 0097 */` block |
| App/tests/* | test_police_defaults, test_ws_request_letter, test_ubyport_sample_pdf, test_host_list_cards_browser, test_host_copy_corrections, new test_reporting_help_0097 |

## 4. Steps
1. Replace the letter block with one line that links <https://policie.gov.cz/reditelstvi-sluzby-cizinecke-policie/jake-jsou-moznosti-zasilani-dat-aplikaci-ubyport>. That page describes the three UbyPort sending modules, the web service among them.
2. Keep only the abbreviation (UBY-WS_) and the contact (operator e-mail) defaults. Stored values are not rewritten.
3. Write `?` text that names the line on the police letter for each police field, and plain words for each fee field.
4. Link the sample PDF beside the heading. The Guide copy stays.
5. Search the git history for a stay-fee example. None existed, so none was invented.
6. Fix the summary margin and add a geometry assertion.

## 5. Do not touch
Submission code, credential storage, code lists, base.html `?v=`, setup guide, Guest links, Door lock, Bookings.

## 6. Commands
From App/ (staging/mock, REQUIRE_BROWSER=1): the test files above. Root: `python3 scripts/context_lint.py`.

## 7. Acceptance
- [x] No letter generator; one fine-print line.
- [x] `uby_name` is never derived; readiness still requires it.
- [x] Every police and fee field has a `?` (EN/CS).
- [x] Sample link beside the heading.
- [x] The summary is in the lane at 360–1440.
- [x] Screenshots in docs/tasks/0097-evidence/.

## 8. Stop and ask
Owner: should an annotated stay-fee example be made (see the report)?

## 9. Report
[0097-report](0097-report.md).
