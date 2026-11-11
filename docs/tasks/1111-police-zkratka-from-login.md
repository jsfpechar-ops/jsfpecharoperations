# 1111: the police short name (zkratka) comes from the login; the box goes away

Status: todo
Tier: B | HIGH RISK (touches the value that reaches the police system; UBYPORT_CORE rule 1) | Base: origin/main 8b938415 (re-grep by quoted text) | Branch: claude/1102-police-zkratka-from-login (named 1102 by the owner; the task number is 1111 because 1102-1110 and 1120 are taken)
Executor: Haiku 5.5 | Attempts: 3 at most | Stop at 30 tool calls (executor.md), commit, report `Done: steps 1 to k`
Report: docs/tasks/1111-report.md

## 1. Objective

Owner (Josef, 2026-11-11): the zkratka is the part of the web-service login after the "_" (login UBY-WS_DEMO1 gives DEMO1), so UbyHost derives it and does not ask for it. Remove "Short name (zkratka)" from the editor and wizard police forms. Scope (owner decision): (a) derive and drop the box; (b) prove on current main that a full pasted letter fills every box in the editor and the wizard police step; fix only what is proven broken. Archive row, Read button and hours are already on main: do not touch them.

## 2. Context (investigation done by the orchestrator at 8b938415; do not redo)

Proven by running the code:
- `parse_letter` on a real-format letter (title, `Přihlašovací jméno: UBY-WS_DEMO1`, `Přístupové heslo:`, `IDUB: 209988776655`, `Ubytovací zařízení:` two lines) returns IDUB found, login found, zkratka derived DEMO1, password found, facility found. `test_police_letter_parser.py` and `test_setup_wizard_reuse_1101.py`: 255 passed.
- A bare paste of only `UBY-WS_DEMO1` returns all three fields missing. The login regex `uby-t?ws_?[A-Za-z0-9]{5,6}` needs the "Přihlašovací jméno" label; the IDUB value must be 12 to 14 digits, so the parser can never put a login into the IDUB box.
- Main wires the wizard: `setup_wizard/police.html` includes `_police_fields.html` (line 26) and has `form#police-letter-form` (line 41); `app.js` `initLetterPaste` finds the form by `getElementById("uby_idub").form` and hides `[data-letter-read]`. `test_setup_wizard_reuse_1101_browser.py` pastes `FULL_LETTER` on the wizard step and walks to the end.
- The derivation already exists: `validation.mark_from_ws_user` (UBY-WS_ABCDE gives ABCDE; `UBY-WSab12cd` with no underscore gives the six characters after UBY-WS; `uby-tws…` test logins and any other shape give ""), `admin._apply_police_defaults` (fills an EMPTY `uby_mark` from the login on create and on save), `host.js` (fills the box as the login is typed), `demo.py`.
- The Contact e-mail is the intended default: `_apply_police_defaults` copies the operator's `contact_email` into an empty `uby_contact` (docstring: derived from the operator e-mail). The sample letter prints a phone and says the police letters often print no contact.

Likely, not proven: Josef's screenshot (login in the IDUB box, empty boxes, Read button visible, Hours and Archive visible) shows the old build. Main CI was red from about 12:08 UTC, so "Deploy production" was skipped for every main commit after 04:24; #903/#909 were probably not live. A login in the IDUB box then came from him typing or pasting it there.

So no parser or wiring bug is proven. Step 1 proves it with a test; fix only what fails.

## 3. Files

- `App/app/templates/_police_fields.html` (hide the box, add the fallback note)
- `App/app/routes/admin.py` (`_wizard_step_payload` police branch, `_apartment_payload`, `_apply_police_defaults`, `_LETTER_BOX_LABELS`)
- `App/app/validation.py` (a small helper only; `validate_apartment` stays as is)
- `App/app/static/host.js` (the 0205 autofill block becomes a no-op when the box is absent; likely no edit)
- `App/app/static/app.js` (only if step 1 needs it; `LETTER_BOXES` already tolerates a missing box)
- `App/app/host_i18n.py`, `host_vi_i18n.py` (one new key)
- `App/app/templates/base.html` (cache keys, only for a changed asset)
- tests: `App/tests/test_police_defaults.py`, `App/tests/test_police_letter_flow.py`, `App/tests/test_police_zkratka_derived.py` (new), `App/tests/test_onboarding_wizard_browser.py`, `App/tests/test_setup_wizard_reuse_1101_browser.py`, `App/tests/test_host_police_paste_browser.py`, `App/tests/test_required_stars.py`
- `docs/context/decisions.md` (one short line)

## 2b. Design

D1. **The value sent to the police does not change.** `reporting.py` still reads the stored `uby_mark`. Only where the stored value comes from changes: the server derives it on every police save.

D2. **Rule.** On a save that posts a login: `derived = validation.mark_from_ws_user(login)`. If `derived` is non-empty and (the stored mark is empty, or the login changed from the stored login), store `derived`. Otherwise keep the stored mark. A saved property whose login is unchanged keeps its stored zkratka even if it differs from the derived one.

D3. **The form no longer posts `uby_mark`.** In both police-step save paths (`_wizard_step_payload` police branch and `_apartment_payload`, which loops `APARTMENT_TEXT_FIELDS` and then runs `payload["uby_mark"].upper()`), a form without `uby_mark` must not overwrite the stored value with "". When the field is posted (fallback box), it is saved upper-cased as today. Check the editor save path that writes the payload to the row so an absent key is not written as "" (grep `uby_mark` around admin.py 1578, 1707, 1750, 3165).

D4. **Fallback.** The box shows only when the login box holds a value and `mark_from_ws_user` returns "" for it (test login `UBY-TWS…`, or a shape the check does not know) or when the stored mark is empty and the login is non-empty and not derivable. It is a plain `police_box('uby_mark', ...)` plus the one new key `apartment.form.ubyport.mark_fallback` under it: "We cannot read the short name from this login. Type the short name the police gave you." (EN, CS, VI; the existing `mark_hint` says "fills in by itself", so use the new key as that box's hint and do not show both). The server computes the condition in the template from `apartment`/`letter_fill` (add a Jinja test or pass a flag; no JS needed). After a failed save the box stays visible.

D5. **Required list.** Remove `uby_mark` from the missing-label list `_LETTER_BOX_LABELS` and from the red "required" star set for the form. Keep `uby_mark` in `property_setup.STEP_FIELDS["police"]`, in `validate_apartment` and in `report_complete`: a property without a derived or typed mark is still not report-complete (filing needs it). If the login is empty the missing item is the login, not the zkratka.

D6. **Letter paste.** Keep `uby_mark` in `police_letter.FIELDS` (the parser still derives and checks conflicts). `apply()` in `initLetterPaste` must skip a box that is not on the page. When the letter's login is a test login and the box is absent, the status line says nothing about zkratka.

D7. **Contact.** No change. The e-mail default stays (optional box, editable). Do not remove the default.

## 4. Steps (commit after each: `1111 step k`)

1. **Prove main first (failing-first rule).** Add `tests/test_police_zkratka_derived.py`: (a) `parse_letter` on the real-format letter above gives login `UBY-WS_DEMO1` and zkratka derived `DEMO1` (use `SAMPLE_*` from `app.ubyport_sample_pdf`); (b) an editor POST to `/police-letter` with that letter (HTML path, as `test_police_letter_flow.py` does) renders the IDUB, login, password and facility values and no value in the wrong box; (c) the same on the wizard step `/apartments/{id}/setup/police`. Run it. All pass: write "works on main" in the report and go on. Any fails: that failure is the bug; fix the smallest thing, keep the test.
2. **Failing tests for the change** (write them, run, see them fail): save with login `UBY-WS_DEMO1` and no `uby_mark` posted stores `DEMO1` (editor and wizard); a saved property with `uby_mark=OLD01` and an unchanged login keeps `OLD01` when `uby_mark` is not posted; a changed login `UBY-WS_NEW22` replaces it; login without "_" `UBY-WSab12cd` stores `AB12CD`; login `UBY-TWS12345` with no mark: the box is rendered, with the new hint; with a derivable login the page has no `id="uby_mark"`; a posted `uby_mark` (fallback) is stored upper-cased.
3. Implement D2, D3 (admin.py, a helper in validation.py if needed), then the template (D4), D5, the i18n key in EN, CS and VI (keep the three key sets equal; run the key-consistency test named in test-map).
4. Update the existing tests that fill `#uby_mark` (`test_onboarding_wizard_browser.py` lines about 193 and 876, the 1101 browser test, `test_required_stars.py` line 74 list, `test_wizard_old_look_0953.py` line 65): remove the fill, use a login that derives (`UBY-WS_SYNTH`), assert the stored mark. Do not weaken any other assertion.
5. Cache keys: bump `app2.css?v=` and `app.js?v=` in `base.html` only for an asset you changed (new `20261111-1111a`).
6. `docs/context/decisions.md`: append one line `- 2026-11-11 | [ux] Zkratka derived from the WS login; box only if the login has no readable one | owner | 1111`. Fix nothing else in that file (see section 8).

## 5. Do not touch

`reporting.py`, the SOAP and mock code, `validation.mark_from_ws_user` and `_MARK_RE`, `validate_apartment`'s mark check, the `uby_mark` column, `police_letter.py` (unless step 1 proves a bug), the Archive, Read-button and hours code.

## 6. Commands (each ends `2>&1 | tail -30`)

From `App/`, `.venv/bin/python -m pytest ... -q --tb=short -x`:
- `tests/test_police_zkratka_derived.py tests/test_police_defaults.py tests/test_police_letter_parser.py tests/test_police_letter_flow.py tests/test_validation.py tests/test_validation_i18n.py tests/test_required_stars.py tests/test_property_readiness.py`
- Filing row of test-map (HIGH RISK, run all): `test_ubyport_*.py test_soap.py test_worker.py test_submission_*.py test_stale_submission.py test_filed_by_hand.py test_filing_watchdog.py test_police_*.py test_deadline*.py test_claim_*.py test_endtoend.py`
- Host row, 0 skipped (`-rs`): `tests/test_host_police_paste_browser.py tests/test_host_police_letter_browser.py tests/test_setup_wizard_reuse_1101_browser.py tests/test_onboarding_wizard_browser.py tests/test_host_geometry.py tests/test_layout_lint_browser.py`
- From the repo root: `python3 scripts/context_lint.py`.

## 7. Acceptance

- [ ] Step 1 result written in the report (works on main, or the proven bug and its fix).
- [ ] No zkratka box on the editor or wizard police step with a derivable login; save stores the derived value.
- [ ] Fallback box and its explanation show only for a non-derivable login; one explanation in one place (rule 9); EN/CS/VI keys equal.
- [ ] Stored zkratka kept for an unchanged login; `reporting.py` untouched; filing tests green.
- [ ] A property with a derivable login and empty mark becomes report-complete after one save (wizard walks on without the box).
- [ ] UX gate (rule 10): layout lint 0 skipped, screenshots at 390, 768 and 1280 of the editor police section and the wizard police step (with the box, and the fallback case at 390), one line per page of what you saw, design-system checklist ticked in the PR.
- [ ] Cache keys bumped only for changed assets. `context_lint` shows no new error.

## 8. Stop and ask

- An anchor is not found, or the editor save writes `uby_mark=""` through a path this brief does not name.
- Step 1 fails in a way that needs a parser change for a letter format you cannot reproduce from the sample.
- `decisions.md` on main holds merge-conflict markers (lines about 64-68: `<<<<<<< HEAD`, `=======`, `>>>>>>> origin/main`) and is over its 2200-token cap, so `context_lint` already fails there before this brief. Do not fix it in this PR; write one report line so the orchestrator does.

## 9. Report and PR

Report as executor.md says. Write the PR body last, from the final diff: what was derived, what stays (stored values, filing), the step 1 result, screenshots notes.

## 10. Owner questions

1. A stored zkratka that differs from the login-derived one stays until the login changes. OK, or always re-derive?
2. Is the operator's e-mail the right default for the police Contact box? (Kept as is.)
