# 1634: Completion receipt — entry code line + guide block, marker plumbing, i18n, goldens

Status: todo
Depends on: 1633 | Base commit: d39b1351 | Branch: task/1634-completion-mail-entry-code-guide
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier B (mail)

## 1. Objective

The completion receipt gains: an entry-code line next to the door code, and a guide block (internal guide button + external guide link) after the door code. The entry code travels encrypted in the outbox payload and is injected only at send, exactly like the door PIN. Plain-text fallback carries the guide links but not the entry code.

## 2. Context

Anchor 1 — markers, `App/app/mail.py:184-185`:

```python
DOOR_CODE_MARKER = "{{door_code}}"
DOOR_CODE_KEY = "door_code_enc"
```

Anchor 2 — injection step to mirror, `App/app/mail.py:358-369`:

```python
def _with_door_code(value: str, payload: Dict[str, Any]) -> str:
    if DOOR_CODE_MARKER not in value:
        return value
    token = payload.get(DOOR_CODE_KEY)
    if token is None:
        raise db.DecryptionError("outbox payload has a door code with no secret")
    ...  # replace DOOR_CODE_MARKER with door_codes.guest_pin_display(db.decrypt_field(token))
```

Wire the new `_with_entry_code` into both delivery chains next to the existing calls, `App/app/mail.py:423` and `:440`:

```python
            _with_door_code(_with_secret(stored_body(payload), payload), payload),
...
            _with_door_code(_with_secret(stored_html(payload), payload), payload),
```

Anchor 3 — door-code block inside `build_completion`, `App/app/mail_notify.py:1805-1820` (insert the entry-code line adjacent, and the guide block after this block):

```python
    if door_code:
        code_title = _guest_text(lang, "door_code_title")
        times = _guest_text(
            lang, "door_code_times", checkin=door_code["checkin"], checkout=door_code["checkout"]
        )
        blocks.extend([
            _block_heading(code_title),
            _block_paragraph(mail.DOOR_CODE_MARKER, size=22),
            _block_paragraph(times),
        ])
        text_lines.extend(["", code_title, mail.DOOR_CODE_MARKER, times])
```

Anchor 4 — payload key set at claim time, `App/app/claim.py:860`:

```python
    if code_row is not None:
        payload[mail.DOOR_CODE_KEY] = code_row["pin_enc"]
```

Add `payload[mail.ENTRY_CODE_KEY] = apartment["entry_code_enc"]` next to it (only when set and inside the visibility window — reuse the same window rule as brief 1633; if outside the window, omit both the marker from the body and the key).

Anchor 5 — fallback body, `App/app/claim.py:630` `def _guest_fallback_text(...)`: built from the i18n catalogue only, must not throw; add the guide links (non-secret) there, never the entry code (the door code is already absent there — keep it that way).

Resulting receipt order: stay panel → what you sent → fee → entry code line + door code → guide block → host quiet link → note.

Rules: mail secrets use the marker pattern so the outbox never stores them (`docs/context/rules.md` §Mail); a missing secret fails the send (`db.DecryptionError`, handled at `mail.py:538`). Absolute internal guide URL via the same `config_public(apartment)` + `_stay_link` pattern used for the stay URL in `claim.py`. i18n: every language in `App/app/i18n.py` (`mail_completion_*` and page keys). Mail output is pinned by goldens — update them. Go-first: mail jobs are Python-served today; pending owner decision (decisions.md 2026-11-14). Do not add the entry code to `build_door_code` (`mail_notify.py:1507`) — owner decision 2026-11-14: receipt + stay page only.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/mail.py` | edit | `ENTRY_CODE_MARKER = "{{entry_code}}"`, `ENTRY_CODE_KEY = "entry_code_enc"`, `_with_entry_code()` next to `_with_door_code`, wired into both delivery chains |
| `App/app/mail_notify.py` | edit | `build_completion` (:1724): entry-code line + guide block after the door-code block; fallback text gets guide links |
| `App/app/claim.py` | edit | set `payload[mail.ENTRY_CODE_KEY]` next to :860; pass guide URLs into `_guest_mail_content("completion", ...)` and `_guest_fallback_text` |
| `App/app/i18n.py` | edit | new `mail_completion_*` / fallback keys, every language |
| `App/tests/test_claim_mail.py`, `App/tests/test_completion_fee_mail_1077.py`, `App/tests/golden/` | edit | update goldens + assertions: entry code injected at send, never stored in outbox payload as plaintext, absent outside window, guide links present in text+html+fallback |

No other file may change.

## 4. Steps

1. Verify anchors verbatim (stop if missing — §8).
2. `mail.py`: add marker/key + `_with_entry_code` (decrypt via `db.decrypt_field`; display raw value — it is a host-typed code, no `guest_pin_display` formatting); wire into both chains at :423/:440.
3. `mail_notify.build_completion`: after the door-code block, entry line (`{{entry_code}}` marker + label) and guide block (button to absolute internal guide URL when live; external link with domain when set); same lines into `text_lines`; fallback gains guide links only.
4. `claim.py`: set the payload key (window rule as in 1633); pass guide URLs through content.
5. i18n all languages; update goldens.
6. Run §6.

## 5. Do not touch

`build_door_code` (`mail_notify.py:1507`) — no entry code there (owner decision). Guest templates, QR guide, Leon, exports, retention, door_codes.py logic. No new dependency. Secret-grep the staged diff: no real code value anywhere in it.

## 6. Commands

From `App/`: `.venv/bin/python -m pytest tests/test_ses_mail.py tests/test_mail_*.py tests/test_*_mail.py tests/test_lifecycle_mail.py tests/test_notification_copy.py -q --tb=short -x 2>&1 | tail -30`
From `App/`: `.venv/bin/python -m pytest tests/test_claim_*.py tests/test_endtoend.py -q --tb=short -x 2>&1 | tail -30`
From `App/`: `.venv/bin/python -m pytest tests/test_*_i18n.py tests/test_copy_cleanup.py -q --tb=short -x 2>&1 | tail -30`
From repo root: `python3 scripts/context_lint.py 2>&1 | tail -10`

## 7. Acceptance

- [ ] Golden completion mail shows order: stay panel → what you sent → fee → entry line + door code → guide block → host link → note, in HTML and text and fallback (fallback: guide links yes, entry code no).
- [ ] Outbox payload stores `entry_code_enc` ciphertext only; a payload with the marker but no key fails the send with `DecryptionError` (test).
- [ ] No entry code in `build_door_code` output (test).
- [ ] Mail + claim + i18n test rows green; context lint green.

## 8. Stop and ask

Stop and write the report if: an excerpt is not found; a test fails twice; 25 tool calls or ~50k tokens; a file outside §3 needs a change; §5 would be touched; a golden diff looks wrong (investigate, don't blindly re-pin); you need push/merge/deploy.

## 9. Report

Write `docs/tasks/1634-report.md` (≤600 tokens), `Status: review`, one PR.

## Risk list (for the reviewer)

`App/app/mail.py`, `App/app/mail_notify.py`, `App/app/claim.py`, mail goldens.

## Owner steps

1. Send a staging completion mail to a test claim; confirm order and that the outbox row holds ciphertext only.
2. Go-first decision recorded (decisions.md 2026-11-14) — applies to the whole 1631-1634 thread.
