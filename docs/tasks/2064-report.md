# 2064 report

Status: blocked (g-stay-fee does not render the fee box; gate and guest browser tests not run)
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
