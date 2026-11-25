# 2064 report

Status: review (g-stay-fee renders the fee box on both stacks; full gate PASS; guest browser tests 785 passed, 0 skipped)
Done: steps 1 to 4 (seed, case, env). Left: fee box fix, step 3 full gate, guest browser and geometry tests, context lint, 2063 DB fee test.

## Commits
- 8af7140 2064 step 2-4: res_fee seed (own apartment, stay_fee_collect=1, rate 50, rails qr,iban, declared_guests=1 on reservation and claim, complete CZE guest), g-stay-fee case, QR entry, UBYHOST_STAY_FEE_GUEST_PAY=on.
- 2064 step 4 fix: fee case uses its own apartment token (tok_fee); the first run returned 404 on both sides because the apartment token was for `apt`.
- 2064 step 4 fix: guest_fee added to the owned cookie; before this the guest was not theirs.

## g-stay-fee result (cs/en x 390/768/1280)
- All six cells: identical, diff_px=0, 0 visible, 0 error. This is NOT a valid pass: both sides show the party step, not the fee box.
- cs 390 side and en 1280 side PNGs: both sides show "Registrace hosta" / "Guest registration", "Zaregistrováno: 0 z 1" / "Registered: 0 of 1", "Osoba 1 · nevyplněno" / "Person 1 · not filled in". No fee box, no amount, no IBAN, no QR area. Identical on both stacks.
- Likely cause (not verified): the fee guest row is not counted as complete by the stay page (check guest completeness fields or is_lead; see 2063 report session 3 note on is_lead).

## Full gate (step 3)
- Started once with nohup, then killed to fix the seed. No GATE line, no per-group verdicts. Not run to completion.

## Browser and geometry tests (step 4)
- Not run (tool cap).

## Leftover servers
- `ps -eo pid,cmd | grep -c '[u]byhost-web-parity'` = 0 after each run and after kill.

## Deviations
- Edits were applied with small Python scripts in $TMPDIR (anchor-checked), not the Edit tool.
- Steps 2 to 4 committed as one commit, then two fixes.
- Seed also: UPDATE legal_entity iban only when empty (payout IBAN), guest_fee in owned cookie, res_fee in claim cookie. These go beyond the brief's text; they are additions only.
- Commit trailer: the brief asks for Claude Opus 5.5; the commits use Claude Haiku 5.5 because the executing model is Haiku 5.5 (system attribution rule). Owner to decide.

## Owner steps left
- None until the fee box renders. Next: fix the guest completeness for res_fee, rerun `PARITY_GROUP=H PARITY_ONLY='g-stay-fee*'`, then full gate.

## Continuation (executor session 2)
- Step 1 fix (commit 03c4f21): the fee guest now has the same record shape as res_issued_done (valid PNG signature via sig_png(), doc_number, res_street/res_city/res_country, purpose 99), plus registration_completed_at on res_fee. The old SIG value is a header-only PNG and the guest was incomplete. Seed prints fee_guest_issues (empty = complete).
- g-stay-fee, group H, cs 390 and en 1280 side PNGs: both sides show the fee box. Amount 150 Kc / 150 CZK; rate 50 per counted night; "Pay now" notice; Bankovni prevod / Bank transfer with payee E2E Penzion s.r.o., IBAN CZ65 0800 0000 1920 0014 5399, VS 9; QR area blank (masked); "Osoba 1 uulozeno / saved" card. All six cells identical, diff_px=0.
- Full gate (nohup, /var/tmp/parity_gate.log): GATE: PASS. Per-group verdicts: A identical 75, accepted 3; B identical 92, invisible 2, accepted 2; C 30 identical; D identical 134, invisible 4, accepted 12; E identical 89, invisible 1; F identical 78, accepted 12; G identical 12; H identical 138; P identical 11, invisible 1. visible 0, error 0.
- Guest browser and geometry tests (App/tests test_guest_*.py, test_guest_browser_e2e.py), PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers, UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:5433/guest_test: 785 passed, 0 skipped.
- context_lint: OK.
- Leftover servers: 0.
