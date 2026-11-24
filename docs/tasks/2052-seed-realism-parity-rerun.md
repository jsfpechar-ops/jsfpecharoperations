# 2052: realistic parity seed and rerun (submissions, questions, Leon, privacy, invite)

Status: todo
Precondition: briefs 2049, 2050 and 2051 are MERGED into the branch you start from (2051 makes Go tolerate NULL `mode` and `guest_ids`; 2049 and 2050 change the question page and copy). If `grep -c "COALESCE(s.mode" go/internal/web/submissions/data.go` prints 0, STOP: 2051 is not merged.
Executor: Haiku 5.5, alone. Limits: 100k tokens, 30 tool calls. Read only AGENTS.md, docs/context/executor.md, this brief and the files named below.
Scope: `scripts/e2e/` only. Branch: the branch you are on; do not push or merge.

## 1. Objective

The 2041 parity run could not compare submissions (seed rows were fake, Go answered 500), guide questions (none seeded), Leon settings, privacy requests and the account invite. Seed realistic rows, add the cases, rerun groups E and F plus the new cases at 390/768/1280 in cs and en, and report every `visible` or `error` row in plain words.

## 2. Context (verified in this checkout)

`scripts/e2e/seed_parity_extra.py` (125 lines) has blocks `guide, questions, leon, cleaning, havel, privacy, submission, invite, property, unsub`, run from `App/` as `python ../scripts/e2e/seed_parity_extra.py <owner_user_id> <apartment_id> <reservation_id>`; it prints one JSON of ids on stdout; a failing block is skipped (named on stderr). Today: `submission` inserts fake states `draft` and `sent` with no mode or guest_ids; `leon`, `privacy`, `invite` raise "not seeded"; `questions` needs an existing `guest_chat` row and fails otherwise.

Verified helpers:
- Real submission states (`App/app/templates/submissions.html:8` outcome_keys): ok, ok_duplicate, partial, error, failed, transport_error, outcome_unknown, not_configured, running. This brief seeds `ok`, `error`, `transport_error`, `running`. Real filings (`App/app/reporting.py` ~1815-1821) write `apartment_id, created_at, mode, state='running', guest_ids=json.dumps([ids]), endpoint`, then set finished_at, pseudo_stamp, receipt_pdf, header_errors, record_errors, error_text on completion. Mode values: read `grep -n "reports.mode\." App/app/host_i18n.py | head` and use two keys that exist (e.g. the automatic and the manual one).
- Chats: `leon.stay_chat(apartment_id, reservation_id, lang)` (`App/app/leon.py:302`), `leon._store(chat_id, role, kind, text, sources=None, client_id=None)` (`:340`; role is `guest|leon|host`). `guest_question` insert columns are in the existing `questions()` block: chat_id, message_id, apartment_id, summary, status ('open'/'answered'), answer, urgent, triaged, created_at, answered_at.
- Leon on an apartment: columns `apartment.leon_enabled=1` and `apartment.leon_terms_version = leon.LEON_TERMS_VERSION` (`leon.py:442`, used at `:451` and `:479`). The AI test list is NOT a database setting: `ai.on_test_list` reads env `UBYHOST_AI_TEST_EMAILS` (`App/app/config.py:572`), and an EMPTY value lets every account through. So no `db.set_setting` is needed; do not set that env var. (`ai.enabled()` also needs `UBYHOST_AI_FEATURES` and an API key; the seed cannot supply those. If the leon page shows the "AI off" state on both stacks, report that, do not work around it.)
- Privacy request: `dsr.create(owner_user_id=, received_at=, channel=, request_type=, subject_kind=, guest_id=None, reservation_id=None, handled_by=None)` (`App/app/dsr.py:52`). Channel values: email|post|in_person|support|other; request types: access|rectification|erasure|restriction|portability|objection|other. For `subject_kind` use `"guest"` (confirm: `grep -n "subject_kind" App/app/dsr.py App/app/templates/privacy_requests.html | head`; if the value is not accepted, STOP).
- Invite: `auth.create_account(email, display_name, role="host")` returns the account id (`App/app/auth.py:683`); `login_link.issue(account, purpose=login_link.INVITE, remember=True)` returns the token (`App/app/login_link.py:68`); `account` must be the row (`db.query_one("SELECT * FROM user_account WHERE id = ?", (id,))`). The case path `account-accept` uses `{invite_token}` (`scripts/e2e/parity_cases.py` line ~100). The seed key must be `invite_token` (check `fill()` in `scripts/e2e/page_parity_visual.py`: `grep -n "def fill" -A12 scripts/e2e/page_parity_visual.py`).
- Existing cases that name seed ids: `submissions-full`, `submission-draft` (`{submission_id}`), `submission-sent` (`{submission_sent}`), `guide-questions-full`, `guide-question` (`{question_id}`), `apt-guide-questions`, `leon-settings-full`, `leon-setup-cards-full`, `privacy-requests-full`, `account-accept` in `scripts/e2e/parity_cases.py` lines 86-117.
- Output: `PARITY_OUT` defaults to `~/.local/parity/visual`; rows print `identical|invisible|visible|error|accepted`; `report-<groups>.md` lists `visible` rows with side PNG paths.

## 3. Files (you may touch only these)

`scripts/e2e/seed_parity_extra.py`, `scripts/e2e/parity_cases.py`, `docs/tasks/2052-report.md`. Copies of PNGs go to `/var/tmp/parity-visual/_visible-2052/` (outside the repo).

## 4. Steps (one commit each: `2052 step k`)

All edits: `grep -nF` the anchor first; not found means STOP. Only synthetic text ("E2E ...", `*@e2e.test`). Never print guest data. After each edit: `python3 -m py_compile scripts/e2e/seed_parity_extra.py 2>&1 | tail -5` (no output).

### Step 1: submissions (replace the body of `def submission(out, owner, apt):`)
Keep the function name and signature. New body (use the guest ids of the seeded apartment: `guest_ids = [r["id"] for r in db.query("SELECT g.id FROM guest g JOIN reservation r ON r.id = g.reservation_id WHERE r.apartment_id = ? ORDER BY g.id LIMIT 2", (apt,))]`; if the list is empty, STOP). Insert with `db.insert("submission", {...})`, `now = db.utcnow()`, `import json` is already imported:
- `ok`: mode M1, state `ok`, guest_ids `json.dumps(ids)`, endpoint `"https://example.invalid/e2e"`, finished_at now, pseudo_stamp `"E2E-STAMP-0001"`, receipt_pdf `"E2E-RECEIPT"` (a short non-empty text; the page only checks non-empty), header_errors `""`, record_errors `json.dumps(["" for _ in ids])`. Key `out["submission_ok"]`.
- `error`: mode M2, state `error`, same guest_ids, header_errors `"21"` (pick one code that exists: `grep -n "^21\b\|\"21\"" -r App/app/ubyport* | head -3`, else leave `""`), record_errors `json.dumps(["E2E record problem"] + ["" for _ in ids[1:]])`, finished_at now, endpoint as above, pseudo_stamp `"E2E-STAMP-0002"`. Key `out["submission_error"]`.
- `transport_error`: mode M1, state `transport_error`, guest_ids, error_text `"E2E connection refused"`, finished_at now, no pseudo_stamp, no receipt. Key `out["submission_transport"]`.
- `running`: mode M1, state `running`, guest_ids, no finished_at. Key `out["submission_running"]`.
- legacy: only `apartment_id, created_at, state='ok', finished_at`; mode, guest_ids and every other column NULL (proves the 2051 fix). Key `out["submission_legacy"]`.
Keep `out["submission_id"]` = the error row id and `out["submission_sent"]` = the ok row id so the two existing case rows keep working.

### Step 2: guest questions (replace `def questions(out, owner, apt):` body)
Add `from app import leon` to the import line (`from app import cleaning, db, guest_guide, havel, leon, lifecycle_mail`). Need a reservation id: add a second parameter read, `res = db.query_one("SELECT id FROM reservation WHERE apartment_id = ? ORDER BY id LIMIT 1", (apt,))`. Then `chat = leon.stay_chat(apt, res["id"], "en")`; `m1 = leon._store(chat["id"], "guest", "question", "E2E: is there a late check-in option?")`, `m2 = leon._store(chat["id"], "guest", "question", "E2E: the heating is not working and it is freezing")`, `m3 = leon._store(chat["id"], "leon", "answer", "E2E: I passed this to your host.")`. Insert three `guest_question` rows (open normal on m1: urgent 0, triaged 1; open URGENT on m2: urgent 1, triaged 1, summary `"E2E urgent: no heating"`; answered on m1 with answer text and answered_at, status `answered`). Keys: `out["question_id"]` = the URGENT open row (the `guide-question` case then shows the urgent banner from brief 2050), `out["question_open"]`, `out["question_answered"]`. The `chat` dict key `"id"` is used; if `leon.stay_chat` returns something else, STOP.

### Step 3: Leon enabled (replace `def leon(out, owner, apt):`)
Rename the local import to avoid shadowing: the function is called `leon` in this file and now `leon` is also the module. Rename the function to `leon_block` and update its tuple entry in `main()` (`("leon", leon)` becomes `("leon", leon_block)`). Body: `db.execute("UPDATE apartment SET leon_enabled = 1, leon_terms_version = ? WHERE id = ?", (leon.LEON_TERMS_VERSION, apt))`; `out["leon_enabled"] = 1`. No `db.set_setting` (see section 2).

### Step 4: privacy request (replace `def privacy(...)` body)
Add `dsr` to the `from app import ...` line. Body: two requests, `out["dsr_id"] = dsr.create(owner_user_id=owner, received_at=db.utcnow(), channel="email", request_type="access", subject_kind="guest")` and a second `channel="post", request_type="erasure"`. If `subject_kind` is rejected: STOP.

### Step 5: account invite (replace `def invite(...)` body)
Add `auth, login_link` to the import line. Body: `acct_id = auth.create_account("invitee@e2e.test", "E2E Invitee", role="host")`; `row = db.query_one("SELECT * FROM user_account WHERE id = ?", (acct_id,))`; `out["invite_token"] = login_link.issue(row, purpose=login_link.INVITE, remember=True)`. Wrap nothing else.

### Step 6: cases (`scripts/e2e/parity_cases.py`, list `EXTRA_CASES`)
After the line `("submission-sent", "/submissions/{submission_sent}", "host", "E"),` add:
```
    ("submission-ok", "/submissions/{submission_ok}", "host", "E"),
    ("submission-transport", "/submissions/{submission_transport}", "host", "E"),
    ("submission-running", "/submissions/{submission_running}", "host", "E"),
    ("submission-legacy-null", "/submissions/{submission_legacy}", "host", "E"),
```
After the line `("guide-question", "/apartments/{apt}/guide/questions/{question_id}", "host", "F"),` add:
```
    ("guide-question-answered", "/apartments/{apt}/guide/questions/{question_answered}", "host", "F"),
```
(`submission-draft` and `submission-sent` keep their names; they now hold the real error and ok rows. Rename nothing.) Leave `privacy-requests-full`, `account-accept`, `leon-settings-full`, `leon-setup-cards-full`, `guide-questions-full` as they are: they now find data. Check: `python3 -m py_compile scripts/e2e/parity_cases.py 2>&1 | tail -5`.

### Step 7: seed dry check (from `App/`)
Run the parity harness in a mode that prints skipped blocks (step 8 does it). If any block prints `{"skipped": ...}` on stderr, fix only that block once; if still skipped, STOP and report the reason.

### Step 8: rerun (from `App/`, env: `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`, `PATH=/usr/local/go/bin:$PATH`)
`PARITY_GROUP=E,F .venv/bin/python ../scripts/e2e/page_parity_visual.py 2>&1 | tail -30`. Expect the six new E/F cases to be present at 390/768/1280 in cs and en, no `SKIPPED (seed block missing)` lines, none of them `error`. Note: `submission-legacy-null` MUST NOT be a Go 500 (that is the point).
Then read the final report file (`report-E-F.md` under `PARITY_OUT`; the path is printed at the end) with `grep -c . | tail -1` and `grep -E "visible|ERR" <file> | head -40`.

### Step 9: view and classify (cap 15 image reads)
For each `visible` or `error` row, open its side PNG (one read per row; group cs/en or width variants by viewing the 1280 en first, then at most one narrower width if different). In plain words, per row: what Python shows, what Go shows, the difference, and a verdict: REAL (function or text missing in Go), HARNESS, or ACCEPTED-CANDIDATE. Then copy every `visible` row's side PNG: `mkdir -p /var/tmp/parity-visual/_visible-2052 && cp <side pngs> /var/tmp/parity-visual/_visible-2052/ 2>&1 | tail -5`. If more than 15 reads would be needed, classify the rest from the report notes only and say so.

## 5. Do not touch

`App/app/`, `go/`, other scripts, `scripts/e2e/page_parity_visual.py`, `scripts/e2e/seed.py`, goldens, dependencies, secrets. Do not change the `ACCEPTED` dict. Do not fix Go differences you find: report them. No push, no merge.

## 6. Commands

Each step ends with its command; step 8 is the rerun. Never run pytest.

## 7. Acceptance

- [ ] seed prints ids for submissions (5 rows incl. NULL legacy), questions (incl. one open urgent), Leon enabled, dsr, invite_token; no block skipped
- [ ] 7 new or newly-populated cases ran at 3 widths x cs/en, none `SKIPPED`
- [ ] `submission-legacy-null`: Go answers 200 (not 500); state it in the report
- [ ] every `visible`/`error` row described in plain words with a verdict; at most 15 PNG reads
- [ ] visible side PNGs copied to `/var/tmp/parity-visual/_visible-2052/`

## 8. Stop and ask

Precondition not met; anchor not found; a block still skipped after one fix; `subject_kind` or `leon.stay_chat` mismatch; the harness crashes twice; more than 12 distinct `visible` cases (list them from the report and ask which to open).

## 9. Report

`docs/tasks/2052-report.md`, 600 tokens at most: files changed, command tails, section 7 ticked, a table of visible/error rows (case, widths, plain-words difference, verdict), PNG folder path, Deviations, Questions, `Status: review`. Commit trailers:
```
Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014N5J8NCpdqN2TbR61gYRQf
```

## Note from the orchestrator (before the run)

Do not edit the ACCEPTED dict. In the report, classify `guide-item` (cs and en) as ACCEPTED with the reason "Go keeps one Save per form (design-system rule 5); Python shows Save and next card plus Save; see brief 2051 section 11", and the `apt-guide-full` Leon help placement as ACCEPTED (brief 2051 section 10). Every other difference on those pages is still reported.
