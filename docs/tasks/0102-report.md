# 0102 report: Onboarding wizard

Status: final fix round for PR #389 (cross-step overwrite)

## Step 0, before the fixes

`tests/test_onboarding_wizard_survival.py` written first and run against `264be3e`. Full output: `docs/tasks/0102-step0-before.txt`.

```
AssertionError: property overwrote uby_idub: '' != '123456789012'

FAILED tests/test_onboarding_wizard_survival.py::test_cross_step_guarded_fields_survive_each_wizard_post
FAILED tests/test_onboarding_wizard_survival.py::test_property_step_shows_stored_values_and_refused_save
FAILED tests/test_onboarding_wizard_survival.py::test_calendar_sync_failure_stays_in_wizard
FAILED tests/test_onboarding_wizard_survival.py::test_stay_fee_save_skips_door_lock_when_unavailable
FAILED tests/test_onboarding_wizard_survival.py::test_try_it_skip_deletes_demo_stay
FAILED tests/test_onboarding_wizard_survival.py::test_refuse_setup_save_ignores_posted_id
FAILED tests/test_onboarding_wizard_survival.py::test_form_return_to_drops_fragment_by_default
7 failed, 1 warning in 1.52s
```

0F (browser click-through) was added in the same file as the other browser tests and ran with the suite after the fixes.

## Step 0, after the fixes

Full output: `docs/tasks/0102-step0-after.txt`.

```
.......                                                                  [100%]
7 passed, 1 warning in 0.93s
```

## Fixes

1. Partial-form overwrite: done. A wizard post with a whitelisted `setup_step` writes only `property_setup.STEP_FIELDS` for that step. `credentials_changed` is computed only on the police step (and on the ordinary settings save).
2. Property step renders stored values: done. `property_values` is set from the apartment before the identity and address includes. A refused save re-renders the typed values.
3. Calendar sync failure stays in the wizard: done. When `return_to` is a wizard path, a failed first sync redirects to that wizard step with the error.
4. `return_to` from `next_applicable_step`: done. Step forms no longer hard-code the next URL. A stay-fee save with no door lock lands on automation in one redirect.
5. Live region: done. `announceFeedback` clears the text, then writes it after 20ms. The copy test waits for the live-region text.
6. `_form_return_to` drops the fragment again: done. `keep_fragment=True` is opt-in. It is used for the automation-timing save, because that form's `return_to` is `/apartments#property-summaries`. Smart locks, archive, reservations, entities and regenerate-pin drop the fragment as before. A post with `return_to=/smart-locks#x` is accepted as `/smart-locks`.
7. Refused-save draft is a whitelist: done. `refuse_setup_save` copies only fields the step owns. A posted `id=999` is not rendered as an input value.
8. try_it Skip deletes the demo stay: done. Skip calls `demo.delete_demo_stay` when a demo stay exists. On a registered demo, Skip (deletes) and Keep are the two actions; the extra button that did the same delete is gone.
9. Cleanup: done. `_setup_guide_bundle` builds the facts and `property_setup.current(...)` once for progress, the post-save redirect and the wizard page. `_wizard_step_path` is removed. The overview guest-link control uses `copy_inline`. The door-lock select uses `.setup-wizard-lock-field`.

## Test result

From `App/`:

```
UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/workspace/docs/tasks/0102-evidence UBYHOST_CAPTURE_0047=1 .venv/bin/python -m pytest tests -q --tb=line
```

```
3490 passed, 7 warnings in 742.93s (0:12:22)
```

0 failed, 0 skipped.

`ruff check` on the edited modules (`E9,F63,F7,F82,F401,F841`): all checks passed.
`python3 scripts/context_lint.py`: OK (existing status WARN only).

## Screenshots

- Property step with stored name and address: `docs/tasks/0102-evidence/15-property-stored-values-en-1280.png`
- Overview after a full click-through, police checklist intact: `docs/tasks/0102-evidence/14-overview-after-journey-en-1280.png`
- Calendar step with the sync error: `docs/tasks/0102-evidence/16-calendar-sync-error-en-1280.png`
- After try_it Skip (demo stay deleted): `docs/tasks/0102-evidence/17-try-it-after-skip-en-1280.png`

## Not done

- No schema change. None was needed.
- The ordinary property settings save (no `setup_step`) is unchanged.
- `App/tests/fonts.conf` is test-only. This environment maps the UI font stack onto Noto Sans, which wraps Czech stay rows past the geometry cap. The file points that family at Liberation Sans, the same adjustment as the previous round. It is not a product font change.
