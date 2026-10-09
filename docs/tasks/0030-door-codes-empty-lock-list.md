# 0030: Saving a property with no lock list must not switch door codes off

Status: todo
Depends on: none | Base commit: 1d2d58d6 | Branch: task/0030-door-codes-empty-lock-list
Executor: Cursor local agent (composer, Kimi or GLM) | Fits one session

## 1. Objective

Re-land the fix from the stale PR #327 (closed in favour of this brief): when the door-code tick box is not on the page (no lock account, or the account's lock list is empty), saving the property form must leave `lock_provider` alone. Today it switches door codes off and writes a false `door_codes_off` audit row.

## 2. Context

Rules that apply: [rules: database](../context/rules.md#database) (no schema change here), AGENTS.md hard rule 7 (template change: browser and geometry tests pass with 0 skipped, plus screenshots).

The fix already exists as one commit, `a2415e2d` ("fix: do not turn off door codes when the lock list is empty"), on branch `cursor/critical-bug-audit-2784`. It was a clean cherry-pick onto the base commit when this brief was written. PR #327 itself failed CI only because its base was stale (unused imports in a file it does not touch; `main` passes lint).

The exact change, so you can check it or apply it by hand. Each excerpt must be found verbatim; if one is not, STOP (§8).

`App/app/routes/admin.py`, in `_save_apartment_form`:

```diff
@@ -1219,7 +1219,10 @@ def _save_apartment_form(apartment_id: int, request: Request, form) -> Optional[
                     "checkout_hour": cout,
                 }
             )
-        else:
+        elif "door_codes_fields" in form:
+            # The tick box is on the page. Unticked means off. The same
+            # hidden door_code_section is posted when the box is missing
+            # (no account, no locks); that must not switch codes off.
             payload["lock_provider"] = None
             if _form_str(form, "lock_id"):
                 payload["lock_id"] = _form_str(form, "lock_id")
@@ -1237,13 +1240,11 @@ def _save_apartment_form(apartment_id: int, request: Request, form) -> Optional[
     if credentials_changed:
         alerts.resolve(f"ubyport_auth_failed:{apartment_id}")
     db.audit("apartment_updated", f"id={apartment_id}")
-    if _form_str(form, "door_code_section") == "1" and ttlock.allowed_for(apartment["owner_user_id"]):
-        new_provider = payload.get("lock_provider")
-        if new_provider != prior_lock_provider:
-            if new_provider == "ttlock":
-                db.audit("door_codes_on", f"apartment={apartment_id}")
-            else:
-                db.audit("door_codes_off", f"apartment={apartment_id}")
+    if "lock_provider" in payload and payload["lock_provider"] != prior_lock_provider:
+        if payload["lock_provider"] == "ttlock":
+            db.audit("door_codes_on", f"apartment={apartment_id}")
+        else:
+            db.audit("door_codes_off", f"apartment={apartment_id}")
     return None
```

`App/app/templates/apartment_form.html`, add one hidden input directly above the `door_codes` checkbox line (inside the `{% else %}` branch where the box is shown):

```diff
       {% if door_code.test_mode %}<p class="small"><strong>{{ t('apartment.form.door_code.test_mode') }}</strong></p>{% endif %}
+      <input type="hidden" name="door_codes_fields" value="1">
       <div class="checkline"><input type="checkbox" id="door_codes" name="door_codes" value="1" ...
```

`App/tests/test_door_code_one_lock_one_property.py`: the existing `_save` helper's `data` dict gains `"door_codes_fields": "1",` after `"door_code_section": "1",`, and three tests are added at the end of the file (the helper `_save_without_door_code_controls` plus `test_an_empty_lock_list_does_not_switch_codes_off`, `test_a_missing_lock_account_does_not_switch_codes_off`, `test_the_lock_form_posts_the_fields_marker_when_the_box_is_shown`). Their full text is in commit `a2415e2d`; read it with `git show a2415e2d -- App/tests/test_door_code_one_lock_one_property.py`.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/routes/admin.py | edit | the two hunks above |
| App/app/templates/apartment_form.html | edit | one hidden input |
| App/tests/test_door_code_one_lock_one_property.py | edit | marker in `_save`, three new tests |
| docs/tasks/0030-report.md | create | the report (§9) |

No other file may change.

## 4. Steps

1. `git fetch origin cursor/critical-bug-audit-2784 main`
2. `git checkout -b task/0030-door-codes-empty-lock-list origin/main`
3. `git cherry-pick a2415e2d`. If it conflicts or an excerpt in §2 is not found, STOP (§8).
4. `git diff --stat origin/main` must list exactly the three files in §3.
5. From `App/`: `.venv/bin/ruff check app tests tools --select E9,F63,F7,F82,F401,F841` must print `All checks passed!`.
6. Run the commands in §6.
7. Take screenshots of the property form (door-code section, with a lock account that has locks) at 360, 390 and 1280 px. The hidden input changes no layout, so they should match the current page.
8. Write `docs/tasks/0030-report.md`, set `Status: review`, open one PR.

## 5. Do not touch

`App/app/ttlock.py`, `App/app/door_codes.py`, migrations, any other template, `docs/context/*`. AGENTS.md hard rules 5 (SQL only through `db.py`) and 6 (light mode only) still apply.

## 6. Commands

From `App/`:

```
.venv/bin/python -m pytest tests/test_door_code_one_lock_one_property.py -q
.venv/bin/python -m pytest tests -q
```

Expected: the first passes with the three new tests; the second passes with **0 skipped** (browser and geometry tests included).
From the repo root: `python3 scripts/context_lint.py` passes.

## 7. Acceptance

- [ ] `git diff --stat origin/main` shows only the §3 files.
- [ ] Ruff command in step 5 prints `All checks passed!`.
- [ ] Full test run passes, 0 skipped.
- [ ] Screenshots at 360, 390 and 1280 px are in the report.
- [ ] CI on the PR is green (`gh pr checks`).

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found, or the cherry-pick conflicts;
- a test fails twice;
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/0030-report.md` (1,500 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `App/app/routes/admin.py`: `_save_apartment_form`, the `elif "door_codes_fields" in form` branch and the audit block. Check an older browser tab (posted before this deploy, no marker) cannot switch codes off by accident: it now leaves `lock_provider` alone, which is the safe side.
- `App/app/templates/apartment_form.html`: the hidden input is inside the branch where the box is shown, never outside it.

## Owner steps

1. Open the PR the executor made and wait for the checks to go green.
2. Merge it with `scripts/merge-pr-on-green.sh <pr-number>`.
3. The branch `cursor/critical-bug-audit-2784` (old PR #327, already closed) can be deleted in GitHub (Branches page) after the merge.
