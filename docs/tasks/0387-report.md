# 0387 report: completion mail shows the stay at a glance

Status: review
Executor: Haiku 5.5 | Branch: claude/project-thread-j8pnyp (not pushed, no PR opened)

## Files changed

- App/app/i18n.py: intro without dates (en, cs, de, es, fr); 8 panel keys after `mail_completion_note`
- App/app/guest_uk_i18n.py: same for uk
- App/app/mail_notify.py: `build_completion` takes filled, expected, checkin, checkout, address; stay panel; `_block_quiet_link` for the stay link
- App/app/claim.py: `_completion_facts` helper; passes facts and counts from `_guest_mail_content` and `maybe_notify_completion`
- App/tests/test_guest_mail.py: 2 tests updated, 2 added, NEW_GUEST_KEYS extended
- docs/tasks/screenshots-0387/completion-en-390.png, completion-cs-390.png, completion-uk-390.png

## Commands (last lines)

- Step 1: `pytest tests/test_guest_languages.py`: `47 passed in 1.32s`
- Step 3: `pytest tests/test_claim_mail.py tests/test_claim_fallback_text.py tests/test_claim_resend_complete.py`: `83 passed, 1 warning in 2.31s`
- Step 4: `pytest tests/test_guest_mail.py tests/test_guest_languages.py tests/test_property_names_in_mail.py tests/test_mail_side_padding.py`: `120 passed in 1.74s`
- Step 6: `python3 scripts/context_lint.py`: `context lint: OK` (WARN lines are open-brief overlaps, not failures)

## Section 7

- [x] All step commands pass.
- [x] Completion HTML has no printed stay URL; text part still has it.
- [x] Panel shows count, check-in, check-out, address in en/cs/uk previews.
- [x] 3 PNGs in docs/tasks/screenshots-0387/.

## Deviations

- Step 4 test: the brief asserts "Your stay" in the text part, but the step 2 code adds only the rows to the text part, not the panel title. I followed the step 2 code and asserted the title in the HTML part only. Rows are asserted in both parts.
- Step 5: the first uk preview rendered in English because uk is off by default (`UBYHOST_GUEST_LANGS`). Re-rendered with `UBYHOST_GUEST_LANGS=en,cs,de,es,fr,uk`; the fix is its own commit.
- Step 5: Python Playwright is not in App/.venv, so the screenshots used Node Playwright. Throwaway scripts live in /tmp/claude-0/, not committed.
- The panel sits before the door-code block in the HTML, as step 2's insertion point specifies.
- No PR opened, per the owner's instruction for this run (the executor template says to open one).

## Questions

None.

## Owner steps left

1. Review the screenshots, then open the PR and merge with `scripts/merge-pr-on-green.sh`.
2. Deploy as usual.

## Addendum A

- The guest stay link is gone from the receipt; the only link is a host-only "open this stay in UbyHost" link (A1 to A3), and the address row is dropped (A6). Mail test set: 203 passed.
- Previews re-rendered with `host_url` and no address (A5), with `UBYHOST_GUEST_LANGS=en,cs,uk`; the three PNGs are overwritten.
- Open question: the footer still says "registered with this address" in all three languages (existing copy, not in the brief, not changed).
