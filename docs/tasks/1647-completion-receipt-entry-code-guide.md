# 1647: Go completion receipt — entry code line + guide block

Status: blocked — the receipt is built and queued only by Python `claim.maybe_notify_completion` (`App/app/claim.py:828`) and `mail_notify.build_completion` (`App/app/mail_notify.py:1724`) "until guest registration is on Go (W3)" (`docs/plans/go-mail-job.md` §5 item 5); the thread "Port guest registration pages" has not started
Depends on: 1641, 1643, 1644; the "Port guest registration pages" thread (it ports the completion step); the Go `mail` job live (thread "Plan and port mail job", J4: `mail` in `UBYHOST_GO_JOB_KINDS`), because only Go fills `{{entry_code}}` (1643) | Base commit: none | Branch: none
Executor: Haiku 5.5 | Not runnable. Tier B (mail with a secret). The orchestrator cuts this when the Go completion builder exists.

## 1. Objective

The completion receipt gains an entry-code line next to the door code and a guide block (internal guide button + external link) after it. Receipt order: stay panel → what you sent → fee → entry code + door code → guide → host link → note.

## 2. Context

Known design, verified on bdfaa4d4, kept for the later cut:

- **Window (owner 2026-11-14, decision 2):** the receipt carries the entry code whenever the receipt is sent, limited only by `entry_code_until` (omit it when today > `entry_code_until`). No `booked_level` window here: the receipt usually goes out weeks before check-in. Already-sent mail cannot be retracted; the stay page (1646) is the source of truth.
- Secret path: the body holds `{{entry_code}}` (`EntryCodeMarker`, 1643), the outbox payload holds `entry_code_enc` ciphertext only; filled at send; marker without key fails the send. When no code or outside `entry_code_until`, neither marker nor key.
- Never in the late-PIN door-code notice (Python `build_door_code`, `mail_notify.py:1507`, and its Go twin), QR guide, logs, audit values, analytics, exports, Leon.
- The plain-text fallback (Python `claim._guest_fallback_text`, `claim.py:630`) gets the guide links (not secret) but not the entry code, same as the door code today.
- Python anchors the Go twin replaces: door-code block in `build_completion` `mail_notify.py:1806` `    if door_code:`; payload key `claim.py:860` `        payload[mail.DOOR_CODE_KEY] = code_row["pin_enc"]`. Internal guide URL absolute, built like the stay link.
- Python `App/app/mail.py` gets no `{{entry_code}}`: no go-first exception applies, so the receipt ships only once Go both builds it and sends it.

## 3. Files

None. The files are named when the brief is cut.

## 4. Steps

None. Do not run this brief.

## 5. Do not touch

Everything.

## 6. Commands

None.

## 7. Acceptance

- [ ] Not applicable until the brief is cut.

## 8. Stop and ask

Stop at once: the brief is blocked.

## 9. Report

None.

## Risk list (for the reviewer)

When cut: no clear-text code in the outbox, `entry_code_until` honoured, door-code notice untouched, mail goldens.

## Owner steps

When cut: `mail` in both `UBYHOST_GO_JOB_KINDS` and `UBYHOST_JOB_QUEUE_KINDS` per `docs/plans/go-mail-job.md` §5, and the guest paths per the guest thread.
