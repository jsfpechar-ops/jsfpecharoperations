# 0102 report: Onboarding wizard

Status: review fixes for PR #389

## Review fixes

1. Property step: done. A legacy property with a blank address and no operator renders `setup_wizard/property.html` and a completed save reaches the calendar step.
2. Back: done. GET serves any applicable step at or before the current one. Back skips a step that does not apply (no lock, property already complete). The page title names the step on screen.
3. Rejected save: done. Forms post `setup_step`. `refuse_setup_save` whitelists it and re-renders that step with the typed values. `legal_entity_id` values `abc` and `None` do not raise. An unknown `setup_step` is not treated as a wizard page.
4. try_it open state: done. Skip the test is on the page in every state, including a demo stay with no registered guest.
5. Overview checklist: done. The readiness checklist shows whenever the wizard is not the active surface (hidden, no stored state, archived, inactive, demo, and finished). The setup-complete panel shows only when setup is finished.
6. Save advances only a resolved step: done. A police save that is still missing the password, a door-lock save with no lock, and invalid automation hours re-render that step with the message on the page. A save whose `return_to` ends in `/done` calls `finish()` only when no required step is unresolved, so "I'm still waiting for my police login" cannot finish setup.
7. `guests_registered`: done. When it is true, guest link and try-it count as done, including an older unfinished property.
8. `done_count`: done. A property without door-lock capability counts that step as skipped, so the overview card, progress and checklist agree. A finished property is not left at "7 of 8".
9. Copy: done. `wizard.guest_link.ready` is "Ready" / "Připraveno". The overview guest-link card links to guest settings (PIN and regenerate).
10. Cleanup: done. Wizard context is computed once in `setup_entry`, `setup_step` and `setup_action`, and passed into `render_wizard`. Hide and show do not compute it. Door-lock context is one helper. `refuse_fee_save` builds the fee draft once. Wizard `return_to` uses `wizard_setup_prefix` / `wizard_return_to` from the fee refusal, the setup save, and calendar add. Grep found no references to `_setup_progress_for`, the `keep` action, or `property_setup.SAVE_SECTIONS` (already absent, including tests).

## Test result

`UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-shots UBYHOST_CAPTURE_0047=1 .venv/bin/python -m pytest tests -q -rs` from `App/`:

```
3481 passed, 7 warnings in 777.93s
```

0 failed, 0 skipped.

The three failures from the previous run are fixed. Copy confirmation writes the live-region text in the same turn (`app.js`), so it is not empty when the button already says Copied. Stay-row geometry was 109px in Czech because fontconfig substituted Noto Sans for Segoe UI and Roboto; aliasing those families to Liberation Sans in this environment brings the rows within the existing limits. No test was skipped, disabled or loosened.

`ruff check app tests tools --select E9,F63,F7,F82,F401,F841`: all checks passed.
`python3 scripts/context_lint.py`: OK (existing status WARN only).

## Screenshots

- Property step: `docs/tasks/0102-evidence/08-property-step-en-1280.png`
- Rejected police save: `docs/tasks/0102-evidence/11-police-error-en-1280.png`
- try_it open, with Skip: `docs/tasks/0102-evidence/10-try-it-open-en-1280.png`
- Overview with the guide hidden: `docs/tasks/0102-evidence/12-overview-hidden-en-1280.png`
- Overview guest-link card: `docs/tasks/0102-evidence/13-overview-guest-link-en-1280.png`
- Back on the calendar step: `docs/tasks/0102-evidence/09-back-calendar-en-1280.png`

## Not done

- No schema change. None was needed.
- `_setup_progress_for`, the `keep` action and `SAVE_SECTIONS` were already gone. Nothing to delete.
