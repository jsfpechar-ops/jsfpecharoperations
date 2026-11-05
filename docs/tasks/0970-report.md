# 0970 report (batch B12, executor)

Branch codex/0970-b12-register. Worktree /tmp/ubyhost-b12-worktree.

## Commits
- 1c30e623 0970 step 1 (test file)
- d9b2717a 0970 step 3 (code patch)
- this commit: 0970 step 6 (report and brief status)

## Step 2 baseline
export-before.csv: 740 bytes, sha256 82d62f0c9c38a0455ad25147061621654d955e94c1d540f2299ab5bd51900551 (matches the brief).

## Step 4
11 passed in 44.20s, 0 skipped. The CSV byte comparison passed against the baseline.

## Step 5 rows (last 5 lines of each; rows not in all.log had not finished)
### A rc=0
..........................................                               [100%]
42 passed in 781.42s (0:13:01)
### B rc=0
.                                                                        [100%]
1 passed, 3 deselected in 675.92s (0:11:15)
### C rc=0
  /tmp/ubyhost-b12-worktree/App/.venv/lib/python3.12/site-packages/starlette/testclient.py:463: DeprecationWarning: Setting per-request cookies=<...> is being deprecated, because the expected behaviour on cookie persistence is ambiguous. Set cookies directly on the client instance instead.
    return super().request(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
38 passed, 1 warning in 707.19s (0:11:47)
### D rc=0
........................................................................ [ 94%]
....                                                                     [100%]
76 passed in 33.13s
### E rc=0
............................                                             [100%]
28 passed in 24.51s
### F rc=0
WARN  test_0705_v2_shell_browser.py::test_non_v2_dashboard_still_loads_the_old_stylesheets_and_sidebar is named by open briefs 0784-settings-area-v2-old-shell-tests.md, 0851-fix-725-ci-and-savebar.md; say which goes first
WARN  test_signed_in_chrome.py::test_the_support_line_is_not_part_of_the_legal_link_row is named by open briefs 0784-settings-area-v2-old-shell-tests.md, 0851-fix-725-ci-and-savebar.md; say which goes first
WARN  3 commit(s) touched App/ after the last status.md update. Orchestrator: update docs/context/status.md at review.
next free: task 0971 | migration 0037
context lint: OK
### S rc=0
...                                                                      [100%]
3 passed in 0.98s

## Acceptance (section 7)
- [x] Step 4: 11 passed, 0 skipped.
- [x] CSV bytes equal the baseline.
- [x] Six header cells; no sideways scroll at 1280; no page overflow at 390, 768, 1024, 1280 (test assertions).
- [x] Surname and reporting status readable together (390/768 cards, 1280 table; EN and CS).
- [x] Details reached by Tab, opened by Enter, closed by Esc, no navigation (test).
- [x] English page shows English labels; Czech page shows Czech (test and screenshots).
- [ ] Step 5 rows A to S: see the section above; a row not listed as passed is not verified.
- [x] Seven screenshots viewed once.

## Screenshots (all seven viewed)
- register-390-en.png: stacked cards, no table; surname with first name and Reported / Not yet sent / Rejected pill; English. Pass a, b, d; c not applicable at 390.
- register-390-cs.png: same cards in Czech (Domovní kniha, Nahlášeno, Dosud neodesláno, Odmítnuto). Pass a, b, d.
- register-768-en.png: stacked cards, full names and pills, no table. Pass a, b, d; c not applicable.
- register-1280-en.png: six header cells (Stay, Property, Guest, Reported, Details, actions) inside the card; long surname whole. Pass a to d.
- register-1280-cs.png: Czech headers (Pobyt, Ubytování, Host, Nahlášeno, Podrobnosti), same layout. Pass a, b, d.
- register-1280-en-open.png: popover shows date of birth, Citizenship Germany (DEU), document, residence, Tourism, Signed, Close. Pass c, d. Wording issue: "Signed: Signed".
- register-1280-cs-open.png: Czech popover (Datum narození, Německo (DEU), Účel: Turistika, Podepsáno: Podepsáno). Pass d. Same repeated-label wording.

## Deviations
- Tool-call cap: Step 5 ran as one background sequence (row A took 13 min and row B 11 min, against the brief's 4 and 3.5 min estimates).
- Commits carry the Codex trailer plus the Claude attribution lines from the session instructions.
- App/.venv symlink already existed, so the ln in Step 0 was skipped.

## Questions
- Popover repeats the label in the value ("Signed: Signed", "Podepsáno: Podepsáno"). Owner to decide the wording.
- Vietnamese country names fall back to English (accepted in the brief).

## Owner steps left
- Read /tmp/ubyhost-b12/all.log for any Step 5 row not marked passed above.
- On a populated test account at desktop width: Tab to Details, Enter, Esc.
- Merge only with scripts/merge-pr-on-green.sh after the owner opens the PR.

Status: review
