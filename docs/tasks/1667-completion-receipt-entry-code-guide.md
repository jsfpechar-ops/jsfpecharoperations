# 1667: Go completion receipt — entry code lines (up to 3) + guide block

Status: blocked — the receipt is built and queued only by Python `claim.maybe_notify_completion` (`App/app/claim.py:828`) and `mail_notify.build_completion` (`App/app/mail_notify.py:1724`) "until guest registration is on Go (W3)" (`docs/plans/go-mail-job.md` §5 item 5); the thread "Port guest registration pages" has not started
Depends on: 1661, 2032, 2036, 1663, 1664; the "Port guest registration pages" thread (it ports the completion step); the Go `mail` job live (thread "Plan and port mail job", J4: `mail` in `UBYHOST_GO_JOB_KINDS`), because only Go fills `{{entry_code}}` (1663) | Base commit: none | Branch: none
Executor: Haiku 5.5 | Not runnable. Tier B (mail with a secret). The orchestrator cuts this when the Go completion builder exists.

## 1. Objective

The completion receipt gains one line per extra entry code (up to 3, owner 2026-11-22 D1, D2) after the TTLock door code, each as `<Type label>: <code>` in the host's `position` order, and a guide block (internal guide button + external link) after it. Receipt order: stay panel → what you sent → fee → door code, then entry codes → guide → host link → note.

## 2. Context

Known design, verified on bdfaa4d4, kept for the later cut:

- **Window (owner 2026-11-14, decision 2):** the receipt carries the entry code whenever the receipt is sent, limited only by each row's `valid_until` in `apartment_entry_code` (omit a row when today > its `valid_until`). No `booked_level` window here: the receipt usually goes out weeks before check-in. Already-sent mail cannot be retracted; the stay page (1666) is the source of truth.
- Secret path (D1 change: 1663 is not merged yet, `grep -rn entry_code go/internal/mail/` finds nothing on main, so 1663 must be amended before this brief is cut to cover three codes): the body holds indexed markers `{{entry_code_1}}` to `{{entry_code_3}}`, one per row that is in its window; the outbox payload holds the matching `code_enc` ciphertexts only (one key per position); filled at send; marker without key fails the send. A row with no code or outside its `valid_until` gets neither marker nor key. Type labels are plain catalog text (not secret); a custom `other` label is host free text, so it is never logged or put in audit values.
- Never in the late-PIN door-code notice (Python `build_door_code`, `mail_notify.py:1507`, and its Go twin), QR guide, logs, audit values, analytics, exports, Leon.
- The plain-text fallback (Python `claim._guest_fallback_text`, `claim.py:630`) gets the guide links (not secret) but not the entry code, same as the door code today.
- Python anchors the Go twin replaces: door-code block in `build_completion` `mail_notify.py:1806` `    if door_code:`; payload key `claim.py:860` `        payload[mail.DOOR_CODE_KEY] = code_row["pin_enc"]`. Internal guide URL absolute, built like the stay link.
- Mail evidence (owner 2026-11-14, nothing may say "pending"). How mail is pinned today: `App/tests/golden/mail/*.{html,text.txt,subject.txt}` plus `App/tests/test_mail_golden.py` and `App/scripts/mail_golden.py` cover only `submission_problem` and `cancelled_with_guests`; there is no golden for the completion receipt, and `App/tests/test_completion_fee_mail_1077.py`, `test_mail_side_padding.py`, `test_guest_receipt_sent_mail.py` call `mail_notify.build_completion` without a render. So the brief that is cut adds: (1) a golden for the Go-built receipt (`.html`, `.text.txt`, `.subject.txt`) in the three combinations of 1666: door code + entry code + guide + external link + fee; entry code only; nothing optional; (2) a pytest browser test (pattern of the guide browser tests, `UBYHOST_REQUIRE_BROWSER`) that loads each golden HTML with `page.set_content` in Chromium at 390 and 1280 px wide, saves screenshots, and asserts: no horizontal scroll, door code and entry code visible and in monospace/readable size, the guide button visible and at least 44 px tall, long codes and domains wrap; (3) a check that the plain-text part and the fallback (`claim._guest_fallback_text`) read correctly: guide links present, entry code absent from the fallback, no `{{entry_code}}` marker left in any part sent without a key. The test fills the marker with a fixture value the way the outbox does, so the screenshots show a real code, never the marker. The PR describes each of the six screenshots as "390: ...; 1280: ...".
- Python `App/app/mail.py` gets no `{{entry_code}}`: no go-first exception applies, so the receipt ships only once Go both builds it and sends it.

## 3. Files

None. The files are named when the brief is cut.

## 4. Steps

None. Do not run this brief.

## Design (email)

Components: the existing receipt layout (table-based, inline styles, no images required). After the door code, one row per entry code: the type label (small, grey) above the code, which is monospace, 24 px, letter-spaced, `white-space: nowrap` for codes of 12 characters or fewer (longer codes may wrap). Then, under the codes, one small line (G4): "Codes can change. Your stay page always has the current ones." / "Kódy se mohou změnit. Aktuální najdete vždy na stránce pobytu." (guest catalog, every guest language like 1666; shown only when at least one entry code is in the mail). Then the guide block: the "Open the guide" button (`min-height` 44 px, full width at 390) and, when `guide_external_url` is set, the domain as a text link; copy as in 2033 §Design.

Plain-text part: one line per code as `Garage: 4821#` (type label, colon, code; for type Other the host's label as written), the door code first, then the changes line, then the guide links (no code in the fallback text, as in §2).

States (golden HTML, rendered with `page.set_content` at 390 and 1280, file `receipt-<state>-<width>.png`): `door-only`, `door-3codes`, `nolock-codes`, `guide-ours`, `guide-external`, `guide-both`, `none`. Checks as in §2 (no horizontal scroll, buttons at least 44 px, long codes and domains wrap, marker replaced by a fixture value so the image shows a real code). The PR describes each image per width. Light mode only; no images needed (nothing is loaded from outside).

## 5. Do not touch

Everything.

## 6. Commands

Filled when the brief is cut. It must include the Go mail golden test and, from `App/`: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest <the new receipt browser test> -q -rs --tb=short -x 2>&1 | tail -30` (0 skipped).

## 7. Acceptance

Filled when the brief is cut. It must contain: golden files committed and byte-checked; the browser test green with 0 skipped; six screenshots (three combinations at 390 and 1280) opened and described in the PR; text and fallback parts checked as in §2; no "pending" wording.

## 8. Stop and ask

Stop at once: the brief is blocked.

## 9. Report

None.

## Risk list (for the reviewer)

When cut: no clear-text code in the outbox, each row's `valid_until` honoured, door-code notice untouched, mail goldens.

## Owner steps

When cut: `mail` in both `UBYHOST_GO_JOB_KINDS` and `UBYHOST_JOB_QUEUE_KINDS` per `docs/plans/go-mail-job.md` §5, and the guest paths per the guest thread.
