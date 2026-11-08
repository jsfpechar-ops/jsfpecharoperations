# 1030 report

Status: blocked

## Files changed (commits on claude/project-thread-73qjig, not pushed)
- `df4b8a2b` step 1: `App/app/templates/guest/_fee_pay.html` (details/summary to plain blocks, no radios, all open)
- `6ece6348` step 2: `App/app/static/guest.css` (fee option rules replaced, radio and open rules removed)
- `064ed194` step 3: `App/app/i18n.py`, `App/app/guest_uk_i18n.py` (fee_now_body copy, 6 languages)
- `0a71eb3b` step 4: `App/app/mail_notify.py` (build_completion `fee` argument and block), `App/app/claim.py` (`_completion_fee`, `fee=` at the completion call), `App/app/i18n.py` and `App/app/guest_uk_i18n.py` (receipt fee keys, 6 languages)
- Untracked, not committed: this report.

## Commands
- `App/.venv/bin/python -m pytest tests/test_guest_mail.py tests/test_guest_languages.py tests/test_mail_label_case.py tests/test_mail_side_padding.py -q --tb=short -x 2>&1 | tail -30`
  Last lines: `110 passed in 2.67s`

## Done vs brief section 7
- [x] No radio marks; all enabled options visible at once (code only, not yet viewed in a browser)
- [ ] Receipt tests: not written (step 5 not started)
- [ ] Test-map guest browser row with `-rs`: not run (step 6)
- [ ] Screenshots 390/768/1280 and receipt.txt / receipt.html: not produced (step 6)
- [ ] Report: this file (partial)

## Deviations
- `App/.venv` did not exist. Created it (gitignored) and installed `requirements.txt` and `requirements-dev.txt`. `requirements-dev.txt` alone does not include the runtime deps.
- Brief asks for 5 new mail keys but lists 4 names. Used 5: `mail_completion_fee_heading`, `mail_completion_fee_total`, `mail_completion_fee_calc_title`, `mail_completion_fee_ways` ("Pay by: %(ways)s."), and `mail_completion_fee_vs` (the variable-symbol sentence, shown only when iban is enabled).
- Added `stay_fee` to the import line in `claim.py` (needed for `_completion_fee`).
- Stopped at the executor tool-call limit.
- Done: steps 1 to 4. Left: steps 5 to 7.

## Questions
- Should the "payment details are on your stay page" sentence also appear when iban is off? The brief puts it only in the iban sentence, so it is currently omitted then.
- Is the 5-key count right, or should the variable-symbol sentence sit inside the ways paragraph?

## Owner steps left
- None yet. Next executor run: finish steps 5 to 7, then open the PR.
