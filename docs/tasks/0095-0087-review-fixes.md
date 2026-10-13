# 0095: 0087 review fixes: password copy, honest guest message, evidence test

Status: review
Depends on: 0087 (PR #381, head e96eefb7f97bc33df1f5160363acd539fea2458e) | Base commit: e96eefb7f97bc33df1f5160363acd539fea2458e | Branch: task/0087-host-copy-address-corrections (push to the same branch; this updates PR #381)
Executor: Cursor local agent (composer, Kimi or GLM) | Fits one session | Run before 0088

## 1. Objective

Fix the issues from the review of PR #381: the password field says the same sentence twice, the edit page shows a guest message that guests do not actually see, and the screenshot test writes to a hard-coded folder on every browser run. Also remove the dead code and unused strings 0087 left behind, and add the missing evidence.

## 2. Context

Owner-approved UX rules for this brief (2026-10-13):

- **Password:** one visible sentence under the field. Saved: "Password saved. Leave blank to keep it." Not saved: "Password from your police letter." (unchanged). When a password is saved, the empty box shows eight dark dots (`••••••••`) as its placeholder, so the host sees something is in there. The dots are a fixed placeholder: the real password (or its length) is never sent to the page, and the input value stays empty, so saving without typing keeps the stored password through the existing blank-keeps logic. No placeholder when no password is saved.
- **Guest message:** the box shows exactly what guests see. New property: the box is prefilled with the default (create already stores the default when blank). Edit: the box shows the stored value, blank if blank. Clearing the message on edit stays allowed (`App/tests/test_calmer_forms.py::test_update_with_blank_guest_message_stores_blank`). Guest pages show no message when it is blank (`App/app/templates/guest/form.html:53` `{% if apartment.guest_message %}`).

Anchors (at the base commit). If one is not found verbatim, STOP (§8).

`App/app/templates/apartment_form.html`:

```jinja2
        <input type="password" id="uby_ws_password" name="uby_ws_password" autocomplete="new-password"
               placeholder="{{ t('automation.password_keep') if editing and has_password else t('automation.password_paste') }}">
        <div class="hint">
```

```jinja2
                placeholder="{{ t('apartment.form.guest_message.placeholder') }}">{{ (apartment.guest_message or t('apartment.form.guest_message.default')) if editing else t('apartment.form.guest_message.default') }}</textarea>
```

`App/app/host_i18n.py` (EN, then CS):

```python
        "apartment.form.ubyport.password_edit_hint": "Leave blank to keep the saved password.",
```

```python
        "apartment.form.ubyport.password_edit_hint": "Pro zachování uloženého hesla nechte prázdné.",
```

`App/tests/test_host_copy_corrections.py:27`:

```python
EVIDENCE = Path("/workspace/docs/tasks/0087-evidence")
```

Existing screenshot tests only write when a capture variable is set, for example `App/tests/test_host_property_controls_browser.py`:

```python
    if os.environ.get("UBYHOST_CAPTURE_PROPERTY_CONTROLS") == "1":
```

`App/app/routes/admin.py` `def _append_query_param(path: str, name: str, value: str) -> str:` and `App/app/routes/setup_wizard.py` `def _address_preview(apartment) -> str:` have no callers after 0087.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/apartment_form.html` | edit | Steps 1, 2 |
| `App/app/host_i18n.py` | edit | Steps 1, 4 |
| `App/app/routes/admin.py` | edit | Step 4 |
| `App/app/routes/setup_wizard.py` | edit | Step 4 |
| `App/tests/test_host_copy_corrections.py` | edit | Steps 3, 5 |
| `docs/tasks/0087-report.md` | edit | Step 6 |
| `docs/tasks/0087-evidence/` | edit | Step 5 captures |
| `docs/tasks/0095-0087-review-fixes.md` | edit | Status only |
| `docs/tasks/0095-report.md` | create | Report |

No other file may change.

## 4. Steps

1. **Password field.** In `apartment_form.html` replace the two anchor lines and the hint `div` opening with:

   ```jinja2
           <input type="password" id="uby_ws_password" name="uby_ws_password" autocomplete="new-password"
                  {% if editing and has_password %}placeholder="••••••••" {% endif %}aria-describedby="uby_ws_password-hint">
           <div class="hint" id="uby_ws_password-hint">
   ```

   In the existing `<style>` block at the top of `apartment_form.html`, after the `.property-address-grid .field > label { min-height: 2.9em; }` line, add:

   ```css
     #uby_ws_password::placeholder { color: inherit; opacity: 1; letter-spacing: .12em; }
   ```

   The input keeps no `value` attribute.

   Keep the `{% if editing and has_password %}` hint branch below it unchanged. In `host_i18n.py` change the two `password_edit_hint` values:
   - EN: `"Password saved. Leave blank to keep it."`
   - CS: `"Heslo je uložené. Pro jeho zachování nechte pole prázdné."`

   Do not change `password_new_hint`, credential saving or `has_password`.
2. **Guest message.** Replace the textarea value expression with:

   ```jinja2
   {{ (apartment.guest_message or '') if editing else t('apartment.form.guest_message.default') }}
   ```

   Do not change `apartment_create` (blank still stores the default) or the update route (blank still stores blank).
3. **Gate the evidence test.** In `test_host_copy_corrections.py`:
   - Replace the `EVIDENCE` line with ``EVIDENCE = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "0087-evidence"``.
   - In `test_copy_correction_pages_browser_evidence`, make every `EVIDENCE.mkdir` and `page.screenshot` call run only when `os.environ.get("UBYHOST_CAPTURE_0087") == "1"`, so the checks still run on every required-browser run.
4. **Dead code and unused strings.**
   - Delete `_append_query_param` (admin.py) and `_address_preview` (setup_wizard.py).
   - Run ruff (§6). Remove only the imports it reports as F401 because of this; expect `validation` in setup_wizard.py and the urllib names in admin.py.
   - In `host_i18n.py` delete these keys from both EN and CS:
     - `automation.password_keep`, `automation.password_paste`
     - `apartment.form.ubyport.password_saved`
     - `apartment.form.ubyport.derived_mark_hint`, `apartment.form.ubyport.derived_name_hint`, `apartment.form.ubyport.derived_contact_hint`
     - `apartment.form.address.lede`, `apartment.form.address.line_label`, `apartment.form.address.line_placeholder`, `apartment.form.address.police_details_title`, `apartment.form.address.line_details_mismatch`
     - `setup.address.preview_label`, `setup.address.preview_empty`, `setup.address.line_placeholder`
     - `stay_fees.send.open_databox`, `housebook.lede`

     Before deleting each key, run `git grep -n "<key>" -- App` and confirm the only hits are the two locale lines. Keep any key with another hit (`derived_summary` and `housebook.legal_title` are used by tests: keep them).
   - Leave `validation.split_czech_address` and its helpers alone.
5. **Tests and evidence.** Add these tests to `test_host_copy_corrections.py`:
   - `test_password_field_has_one_sentence`: on the edit page of a property with a saved password, the EN page contains "Password saved. Leave blank to keep it." exactly once, the `uby_ws_password` input has `placeholder="••••••••"`, has no `value` attribute, does not contain the stored password text anywhere in the page, and has `aria-describedby="uby_ws_password-hint"`. Posting the edit form with `uby_ws_password` empty keeps `uby_ws_password_enc` unchanged. On `/apartments/new?lang=en`, the input has no `placeholder` and "Password from your police letter." appears once.
   - `test_edit_shows_stored_guest_message_exactly`: insert a property with `guest_message=""`. The edit page's `<textarea id="guest_message"` content is empty and does not contain the EN default.

   Then extend the browser test:
   - With capture on, take full-page screenshots at 360, 390 and 1280 in EN and CS of:
     - the property edit page (`#ubyport` and `#address` open);
     - the setup address page after a failed submit (the 400 error state);
     - `/stay-fees/<id>?month=2026-08`.
   - Run geometry on the edit page through 360/390/760/1024/1280/1440/1680/2048 with the sidebar expanded and collapsed, reusing the existing helper in `App/tests/test_host_wide_geometry_browser.py` (read-only). If no helper can be called from outside that file, STOP (§8).
   - Capture with `UBYHOST_CAPTURE_0087=1`. Commit only the PNGs under `docs/tasks/0087-evidence/`.
6. **Report fixes.** In `docs/tasks/0087-report.md` add that `App/tests/test_police_defaults.py` was also changed. Prove the "6 pre-existing failures" claim: check out base `98c600be8e3e3cde2779e6b955f25f1c4992c1b0`, run only those 6 test node IDs with the §6 environment, and paste the last 5 lines. If any of them passes there, say so plainly: that failure belongs to 0087 and must be fixed in this brief or reported as a blocker.

## 5. Do not touch

- Credential storage, encryption or `_apply_police_defaults`.
- Guest pages (`App/app/templates/guest/`).
- The create/update guest-message save logic and `test_calmer_forms.py`.
- Schema, migrations, dependencies, filing, TTLock, and workflow/deploy files.
- No push to `main`, no merge, no deploy. Push only to `task/0087-host-copy-address-corrections`.

Hard rules: copy says each thing once (rule 9); template change needs browser and geometry tests with 0 skipped plus screenshots (rule 7).

## 6. Commands

From `App/`:

```bash
UBYHOST_REQUIRE_BROWSER=1 UBYHOST_UBYPORT_ENV=mock UBYHOST_DEPLOYMENT=staging UBYHOST_ENABLE_SCHEDULER=0 .venv/bin/python -m pytest tests/test_host_copy_corrections.py tests/test_calmer_forms.py tests/test_police_defaults.py tests/test_ubyport_sample_pdf.py tests/test_setup_wizard.py tests/test_host_property_controls_browser.py -q -rs
UBYHOST_CAPTURE_0087=1 UBYHOST_REQUIRE_BROWSER=1 UBYHOST_UBYPORT_ENV=mock UBYHOST_DEPLOYMENT=staging UBYHOST_ENABLE_SCHEDULER=0 .venv/bin/python -m pytest tests/test_host_copy_corrections.py -q -rs
UBYHOST_REQUIRE_BROWSER=1 UBYHOST_UBYPORT_ENV=mock UBYHOST_DEPLOYMENT=staging UBYHOST_ENABLE_SCHEDULER=0 .venv/bin/python -m pytest tests -q -rs --cov=app --cov-fail-under=86
.venv/bin/ruff check app tests tools --select E9,F63,F7,F82,F401,F841
```

From the repo root: `python3 scripts/context_lint.py`, `git diff --check`, `git status --short` (no stray files outside §3).

Expected: the focused run passes with 0 skipped. The full run has no failures beyond the base-proven ones from step 6. Ruff and lint are clean.

## 7. Acceptance

- [ ] Edit page with a saved password shows eight dots in the empty password box and "Password saved. Leave blank to keep it." once; the stored password is not in the HTML; saving without typing keeps it. No dots when no password is saved. The CS page shows the CS sentence once.
- [ ] Edit page of a property with a blank message shows an empty box. A new property shows the default. Clearing still saves blank.
- [ ] A required-browser run without `UBYHOST_CAPTURE_0087` writes no files (`git status --short` clean after it).
- [ ] `_append_query_param`, `_address_preview` and the listed unused keys are gone; ruff is clean.
- [ ] Screenshots at 360/390/1280 EN/CS for the edit page, the setup error state and stay-fee detail; geometry at the widths in step 5 with the sidebar expanded and collapsed; 0 browser skips.
- [ ] 0087 report corrected, with base-run output for the 6 failures.
- [ ] CI green on the new head of PR #381.

## 8. Stop and ask

Stop, and write the report, if:

- an anchor is not found;
- a test fails twice;
- one of the 6 "pre-existing" failures passes on the base;
- the geometry helper cannot be reused without editing its file;
- a file outside §3 needs a change;
- §5 would be touched;
- you need push to anything but the task branch, merge, secrets or deploy.

## 9. Report

Write `docs/tasks/0095-report.md` (1,500 tokens at most) and set `Status: review`. Include:

1. The base and result SHA, and `git diff --stat`.
2. Each §6 command with the last 5 lines of its output.
3. §7 ticked.
4. Screenshot paths.
5. Deviations.
6. Questions.

## Owner steps

1. Open a fresh Cursor chat on branch `task/0087-host-copy-address-corrections` and paste: "First run `git fetch origin claude/quirky-lamport-9svmd1 && git checkout FETCH_HEAD -- docs/tasks/0095-0087-review-fixes.md`, then run docs/tasks/0095-0087-review-fixes.md exactly."
2. When it reports, ask the orchestrator to review PR #381 again.
3. Merge #381 into the integration branch only after that review approves it and CI is green.
