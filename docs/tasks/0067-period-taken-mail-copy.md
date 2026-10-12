# 0067: Informational period_taken mail

Status: done
Depends on: 0037 (merged) | Base commit: f55e156 | Branch: task/0067-period-taken-mail-copy
Executor: Cursor local agent (composer; copy-only, the cheapest model fits) | Fits one session

## 1. Objective

TTLock support confirmed on 2026-10-12 that `-1026` means "Passcode with this validity period has been generated before and deleted". The `period_taken` host mail still tells the host an older code may still open the door and asks them to check the TTLock app; it becomes a short notice that needs no action.

## 2. Context

- Plan: [ttlock-door-codes §6](../plans/ttlock-door-codes.md#6-states), [TTLOCK error codes](../TTLOCK.md#error-codes). A deleted code no longer opens the door (owner test 2026-10-10).
- This brief now owns the `mail.door_code_notice.period_taken.*` copy (it was 0037's).
- Rule 9: one explanation in one place; no sentence the button already says.
- Logic does not change: `door_codes.py`, `ttlock.py` and `mail_notify.py` (including the support CC) stay as they are.

Anchor A, `App/app/host_i18n.py`, `en` block. Found verbatim once:

```python
        "mail.door_code_notice.period_taken.subject": "%(property)s: an older door code covers the stay from %(date)s",
        "mail.door_code_notice.period_taken.body": "TTLock reported that another code already covers exactly the hours of the stay from %(date)s, for example the code of a cancelled or moved stay. UbyHost is giving this guest a new code of their own. If the older code was not deleted, it still opens the door during this stay. Check this lock's passcodes in the TTLock app.",
```

Anchor B, `App/app/host_i18n.py`, `cs` block. Found verbatim once:

```python
        "mail.door_code_notice.period_taken.subject": "%(property)s: pobyt od %(date)s pokrývá i starší kód ke dveřím",
        "mail.door_code_notice.period_taken.body": "TTLock hlásí, že přesně hodiny pobytu od %(date)s už pokrývá jiný kód, například kód zrušeného nebo přesunutého pobytu. UbyHost dává tomuto hostovi jeho vlastní nový kód. Pokud starší kód nebyl smazán, otevírá dveře i během tohoto pobytu. Zkontrolujte kódy tohoto zámku v aplikaci TTLock.",
```

If either anchor is not found verbatim, STOP (§8).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/host_i18n.py` | edit | Step 1 and 2: four strings |

No other file may change.

## 4. Steps

1. Replace anchor A with:

```python
        "mail.door_code_notice.period_taken.subject": "%(property)s: the stay from %(date)s got its own door code",
        "mail.door_code_notice.period_taken.body": "A code for exactly the hours of the stay from %(date)s was made earlier and deleted, for example the code of a cancelled or moved stay. TTLock does not issue a second random code for the same hours, so UbyHost gave this guest a code of their own. The deleted code no longer opens the door. Nothing to do.",
```

2. Replace anchor B with:

```python
        "mail.door_code_notice.period_taken.subject": "%(property)s: pobyt od %(date)s dostal vlastní kód ke dveřím",
        "mail.door_code_notice.period_taken.body": "Pro přesně hodiny pobytu od %(date)s už dříve vznikl kód, který byl smazán, například kód zrušeného nebo přesunutého pobytu. TTLock pro stejné hodiny druhý náhodný kód nevydá, proto UbyHost dal tomuto hostovi vlastní kód. Smazaný kód už dveře neotevře. Nemusíte nic dělat.",
```

3. Run the commands in §6.

## 5. Do not touch

`App/app/door_codes.py`, `App/app/ttlock.py`, `App/app/mail_notify.py`, every other i18n key, `App/tests/`. Hard rules 2, 3, 8, 9 apply.

## 6. Commands

From `App/`:

```
grep -c 'older door code\|starší kód' app/host_i18n.py      # expect 0
grep -c 'got its own door code\|dostal vlastní kód' app/host_i18n.py   # expect 2
.venv/bin/python -m pytest tests -q                          # expect all pass
```

From the repo root: `python3 scripts/context_lint.py` (expect no errors).

## 7. Acceptance

- [ ] Both greps give the expected counts.
- [ ] The full test suite passes.
- [ ] `git diff --stat` shows only `App/app/host_i18n.py`, 4 lines changed (plus the report).
- [ ] Context lint clean.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- a test fails twice;
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/0067-report.md` (1,500 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

`App/app/host_i18n.py`: only the four `period_taken` strings; placeholders `%(property)s` and `%(date)s` kept.

## Owner steps

1. Open the PR the executor pushed and check that CI is green.
2. Merge it with `scripts/merge-pr-on-green.sh <PR number>`.
3. Nothing to deploy for staging beyond the usual; production picks it up on your next manual deploy.
