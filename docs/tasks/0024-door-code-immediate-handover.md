# 0024: A door code that fails is handed to the host within about a minute

Status: todo
Depends on: PR #325 merged (0023 done) | Base commit: `main` after PR #325 | Branch: task/0024-door-code-immediate-handover
Executor: Cursor local agent (composer, Kimi or GLM) | Fits one session

## 1. Objective

When TTLock does not give a code, UbyHost tries once more after 1 minute. If that fails too, it stops and emails the host (support in copy) to create the code by hand, with an apology. The guest never reads that something went wrong. The guest page and door-code email state the real 24-hour first-use deadline. Every problem writes one log line starting with `DOOR_CODE_PROBLEM`.

## 2. Context

Owner decisions 2026-10-09 (do not re-open): hand over to the host at once instead of retrying for hours; once the host has been told, UbyHost stops trying (no second code turns up later); the guest reads only "You will receive your door code by e-mail" while waiting; the guest is told the code stops working if it is not used in time and to ask the host for a new one. Rules: 2 (the support copy is in the ROPA, task 0023), 4 (no dependency), 7 (template change: browser and geometry tests, 0 skipped).

TTLock's rule: a period code dies if it is not used within 24 h of its start. The start is check-in minus 1 h (`DOOR_CODE_BUFFER_HOURS`), so the deadline is `valid_from + 24 h`. Show that exact time; never "24 hours after check-in" (it is 1 h earlier).

Anchors, all in `App/app/` and each found verbatim exactly once:

A1 `door_codes.py`:
```python
BACKOFF_MINUTES = (1, 5, 15, 60, 240)
```
A2 `door_codes.py`:
```python
DELAY_MINUTES = 10
```
A3 `door_codes.py` (in `issue`, TTLockError branch):
```python
        elif attempts >= len(BACKOFF_MINUTES):
            new_state = FAILED
            next_at = None
```
A4 `door_codes.py` (same branch):
```python
            (new_state, reason[:40], next_at, now_iso, door_code_id),
        )
```
A5 `door_codes.py` (generic `except Exception:` branch):
```python
        log.exception("door_code_issue_failed door_code=%s", door_code_id)
        if attempts >= len(BACKOFF_MINUTES):
```
A6 `door_codes.py`:
```python
            (new_state, "transient", next_at, now_iso, door_code_id),
        )
```
A7 `door_codes.py` (end of `view`):
```python
        "checkout": _stay_checkin_label(reservation["date_to"], apartment["checkout_hour"]),
    }
```
A8 `door_codes.py` (`_alert_delayed`):
```python
        "a.internal_name, dc.last_error, (dc.id IS NOT NULL) AS has_row "
```
A9 `door_codes.py`:
```python
    for row in rows:
        reason = (row["last_error"] or "").strip() or ("waiting" if row["has_row"] else "not_set_up")
```
A10 `door_codes.py`:
```python
        log.warning(
            "door_code_delayed reservation=%s reason=%s", row["reservation_id"], reason
        )
```
A11 `door_codes.py` (`_send_code_mail`):
```python
        checkout=shown["checkout"],
    )
```
A12 `mail_notify.py` (`_door_code_notice`):
```python
    params: Dict[str, str] = {"property": apartment["internal_name"] or "", "date": stay_day}
```
A13 `mail_notify.py` (`door_code_delayed_notice`):
```python
        subject = _text(lang, "mail.door_code_notice.delayed.subject", **params)
        body = _text(lang, "mail.door_code_notice.delayed.body", **params)
```
A14 `mail_notify.py` (`build_door_code`), the lines `    checkout: str,\n    host: Optional[Dict[str, str]] = None,` and `    only_between = _guest_text(lang, "door_code_only_between")` and the two uses of `only_between`.
A15 `templates/guest/stay.html`:
```html
        <p class="g-intro">{{ t('door_code_only_between') }}</p>
```
A16 `templates/guest/stay.html`:
```html
      {% elif door_code.state == 'delayed' %}
        <p class="g-intro">{{ t('door_code_delayed') }}</p>
```
A17 `i18n.py`: the five `"door_code_only_between": ...` lines, the five `"door_code_preparing": ...` lines and the five `"door_code_delayed": ...` lines (en, cs, de, es, fr blocks, in that order).
A18 `host_i18n.py`: `"mail.door_code_notice.failed.subject"`, `"mail.door_code_notice.failed.body"`, `"mail.door_code_notice.delayed.subject"`, `"mail.door_code_notice.delayed.body"`: each once in the en block and once in the cs block.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/door_codes.py` | edit | 2 attempts, logs, first-use time, plan check |
| `App/app/mail_notify.py` | edit | reason in the failed notice; delayed uses the failed text; first-use line in the code mail |
| `App/app/i18n.py` | edit | guest texts (5 languages) |
| `App/app/host_i18n.py` | edit | host notice texts (en, cs) |
| `App/app/templates/guest/stay.html` | edit | 2 spots |
| `App/tests/test_door_code_handover.py` | create | 7 tests |
| `App/tests/test_door_codes_safeguards.py` | edit | only assertions on texts or timings this brief changes |
| `docs/tasks/0024-report.md` | create | report |

No other file may change.

## 4. Steps

1. A1 → keep it, and add below it:
```python
# A failed code is handed to the host after this many tries (1 min apart).
ISSUE_MAX_ATTEMPTS = 2
```
2. A2 → `DELAY_MINUTES = 5`.
3. A3 and A5: replace `len(BACKOFF_MINUTES)` with `ISSUE_MAX_ATTEMPTS` (2 places, nothing else).
4. After A4 insert (same indent as the `if new_state == FAILED:` below it):
```python
        log.error(
            "DOOR_CODE_PROBLEM stage=%s reservation=%s door_code=%s attempt=%s reason=%s",
            "handed_over" if new_state == FAILED else "attempt_failed",
            reservation["id"], door_code_id, attempts, reason,
        )
```
After A6 insert the same block with `reason` replaced by `"transient"`.
5. A7: before the closing `}` add `"first_use_by": _fmt_local(_ms_to_iso(_iso_to_ms(valid_from) + 24 * 3_600_000)) if valid_from else "",`.
6. A8 → `"a.internal_name, a.owner_user_id, dc.last_error, (dc.id IS NOT NULL) AS has_row "`. A9: right after `for row in rows:` insert `        if not ttlock.allowed_for(row["owner_user_id"]):\n            continue` (codes are off for that host's plan; no alert, no mail). A10 → 
```python
        log.error(
            "DOOR_CODE_PROBLEM stage=delayed reservation=%s reason=%s", row["reservation_id"], reason
        )
```
7. A11 → `checkout=shown["checkout"],\n        first_use_by=shown["first_use_by"],\n    )`.
8. A12: after it add
```python
    if variant == "failed":
        params["reason"] = _door_code_reason(lang, (row["last_error"] or "").strip() or "other")
```
A13 → the same two lines with `.delayed.` replaced by `.failed.`.
9. A14: add `first_use_by: str,` after `checkout: str,`; replace the `only_between` line with `first_use = _guest_text(lang, "door_code_first_use", deadline=first_use_by)` and both uses of `only_between` with `first_use`.
10. A15 → `<p class="g-intro">{{ t('door_code_first_use', deadline=door_code.first_use_by) }}</p>`. A16: delete both lines (a late code then shows the waiting text; the host page keeps its own "delayed" text).
11. `i18n.py`: delete the five `door_code_delayed` lines. Replace each `door_code_only_between` line with a `door_code_first_use` line, and each `door_code_preparing` value, as follows:

| lang | `door_code_first_use` | `door_code_preparing` |
|---|---|---|
| en | `The code works from check-in to check-out. If you have not used it by %(deadline)s, it stops working. Then ask your host for a new code.` | `You will receive your door code by e-mail.` |
| cs | `Kód funguje od příjezdu do odjezdu. Pokud ho nepoužijete do %(deadline)s, přestane fungovat. Pak požádejte hostitele o nový kód.` | `Kód ke dveřím vám přijde e-mailem.` |
| de | `Der Code funktioniert vom Check-in bis zum Check-out. Wenn Sie ihn bis %(deadline)s nicht verwendet haben, funktioniert er nicht mehr. Bitten Sie dann Ihren Gastgeber um einen neuen Code.` | `Ihren Türcode erhalten Sie per E-Mail.` |
| es | `El código funciona desde el check-in hasta el check-out. Si no lo ha usado antes del %(deadline)s, dejará de funcionar. Entonces pida a su anfitrión un código nuevo.` | `Recibirá su código de la puerta por correo electrónico.` |
| fr | `Le code fonctionne de l'arrivée au départ. Si vous ne l'avez pas utilisé avant le %(deadline)s, il ne fonctionnera plus. Demandez alors un nouveau code à votre hôte.` | `Vous recevrez votre code de porte par e-mail.` |

12. `host_i18n.py`: delete the `.delayed.subject` and `.delayed.body` lines (en and cs). Set:
   - en subject `%(property)s: please create the door code yourself`
   - en body `We are sorry: UbyHost could not create the door code for the stay from %(date)s. Reason: %(reason)s. UbyHost support has been told. Please create a code in the TTLock app (open the lock, tap Passcodes) and send it to the guest. UbyHost will not try again, so the guest gets only your code. The guest was not told about the problem.`
   - cs subject `%(property)s: vytvořte prosím kód ke dveřím sami`
   - cs body `Omlouváme se: UbyHost nemohl vytvořit kód ke dveřím pro pobyt od %(date)s. Důvod: %(reason)s. Podpora UbyHost o tom ví. Vytvořte prosím kód v aplikaci TTLock (otevřete zámek, klepněte na Kódy / Passcodes) a pošlete ho hostovi. UbyHost to už znovu nezkusí, host tedy dostane jen váš kód. Host o problému neví.`
13. Create `App/tests/test_door_code_handover.py`. Copy the fixtures and the fake-TTLock pattern from `test_door_codes_safeguards.py`. Tests:
   1. a first transient failure → state `retrying`, `next_attempt_at` about 1 min later, no `door_code_notice` in `email_outbox`;
   2. a second failure → state `failed`, exactly one `door_code_notice` row, its `cc_email` is `support@ubyhost.com`, its body has `[transient` and `Passcodes`;
   3. `reconcile()` after that does not call TTLock again for that row;
   4. `caplog` has `DOOR_CODE_PROBLEM stage=attempt_failed` after the first failure and `DOOR_CODE_PROBLEM stage=handed_over` after the second;
   5. the guest stay page while waiting (also 6 min after registration) shows `You will receive your door code by e-mail.` and not `taking longer`;
   6. an issued code: the guest page and the door-code mail text both show the deadline `valid_from + 24 h` in `dd.mm.YYYY HH:MM` Prague time;
   7. `_alert_delayed()` with `ttlock.allowed_for` patched to return False: no alert, no mail.
14. Run the §6 commands. Fix only tests in `test_door_codes_safeguards.py` that assert the old 10 min, the old texts or the old retry count; list each in the report.

## 5. Do not touch

`ttlock.py`, `routes/`, `claim.py`, the host page `reservation_detail.html`, migrations. Revoke and move paths (`_handle_cancellations`, `_handle_moves`). Rule 1: nothing in UbyPort.

## 6. Commands

From `App/`:
- `.venv/bin/python -m pytest tests/test_door_code_handover.py tests/test_door_codes_safeguards.py -q` → 0 failed.
- `.venv/bin/python -m pytest tests/test_guest_browser_e2e.py tests/test_host_geometry.py tests/test_wp28_geometry.py -q -rs` → 0 failed, no `SKIPPED` line (if skipped: do not install anything, go to §8).
- `.venv/bin/python -m pytest tests -q` → 0 failed apart from the four DNS tests listed in 0023 §2.

From the repo root: `python3 scripts/context_lint.py` → `context lint: OK`.

## 7. Acceptance

- [ ] `grep -c '"door_code_first_use"' App/app/i18n.py` prints `5`; `grep -rn door_code_only_between App/app` prints nothing.
- [ ] `grep -c 'DOOR_CODE_PROBLEM' App/app/door_codes.py` prints `3`.
- [ ] The commands in §6 pass as stated.
- [ ] `git diff --stat main` lists only §3 files.

## 8. Stop and ask

Stop, and write the report, if: an anchor is not found exactly once; a test fails twice; a browser test is skipped; a file outside §3 needs a change; a new dependency seems needed; a step is unclear; you need merge, secrets, SSH or deploy.

## 9. Report

`docs/tasks/0024-report.md` (1,500 tokens at most), `Status: review`: files changed, each command with its last 5 lines, §7 ticked, deviations (every changed old test by name), questions, owner steps left.

## Risk list (for the reviewer)

`door_codes.py` diff (only the 2 attempt checks changed, budget path untouched); the five language rows in `i18n.py`; `stay.html`. Reviewer takes guest screenshots: waiting and issued, at 360, 390 and 1280 px.

## Owner steps

1. After merge and deploy: in Render, open the service, click **Logs**, type `DOOR_CODE_PROBLEM` in the search box. Every failed try, hand-over and late code shows up there.
2. Optional: if your Better Stack account receives the logs, create an alert on the text `DOOR_CODE_PROBLEM`.
