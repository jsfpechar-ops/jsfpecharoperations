# 2064: parity case `g-stay-fee` (stay-fee box, Python vs Go)

Status: todo
Depends on: 2063 (Go box) | Base commit: HEAD | Branch: current
Executor: Haiku 5.5 | Fits one session: 30 tool calls (stop at 25; commit after every step: `2064 step k`)
Executor trailers (every commit):
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and `Claude-Session: https://claude.ai/code/session_014N5J8NCpdqN2TbR61gYRQf`

## 1. Objective

Prove the Go stay-fee box equals Python's: a seeded claimed stay with `stay_fee_collect=1`, guest pay on for both stacks, case `g-stay-fee` (cs and en, 390/768/1280), QR image masked, QR payload compared as text.

## 2. Context

- Seed: `scripts/e2e/seed_parity_guest.py` (`out["res_claimed"] = stay(apt, "e2e-guest-claimed")` at ~line 58, `set_claim(...)` ~60, guest inserts ~72). Cases: `scripts/e2e/parity_cases.py` (`GUEST_CASES`, `("g-stay-claimed", "/l/{tok}/{res_claimed}", ["claim"], "H")` at ~138; `QR_PAYLOAD_CASES` at ~85 with `{"mask": [css...], "texts": [css...]}`). Env: `scripts/e2e/parity_env.sh` (exports, e.g. line 30).
- The box needs: an apartment with `stay_fee_collect=1`, a rate above 0, a payout IBAN (legal entity or apartment bank account), a stay whose guests are all in (remaining <= 0), at least one CZE/SVK guest so the QR is offered, and `UBYHOST_STAY_FEE_GUEST_PAY=on` for both Python and Go. Look at how Python tests seed this: `grep -n 'stay_fee_collect' App/tests/test_guest_*fee*.py | head`.
- The existing `g-stay-claimed` stay must stay unchanged (its own apartment has no fee collection). Use a new apartment or a new reservation on an apartment whose fee flags are set only for this stay; do not change the `res_claimed` rows.
- DOM to mask/compare (from `_fee_pay.html`): image `img.g-fee-qr-img`; payload text: the QR is an image, so compare the visible text of `.g-fee-iban`, `.g-fee-amt`, `.g-fee-calc` and the VS `dd`, plus the SPAYD itself where the harness can read it: the QR payload is NOT in the page text, so also add a Go-side check in step 3 (the DB test of 2063 already compares the payload; here the harness compares data URIs by decoding: see `QR_PAYLOAD_CASES` handling in `scripts/e2e/page_parity_visual.py`/`diff_harness.py`; `grep -n 'QR_PAYLOAD_CASES' scripts/e2e/*.py`).

## 3. Files

| Path | Action |
|---|---|
| `scripts/e2e/seed_parity_guest.py` | edit: add `res_fee` |
| `scripts/e2e/parity_cases.py` | edit: case + QR entry |
| `scripts/e2e/parity_env.sh` | edit: guest pay on |
| `docs/tasks/2064-report.md` | report |

## 4. Steps

1. Anchors: `grep -nF 'out["res_claimed"] = stay(apt, "e2e-guest-claimed")' scripts/e2e/seed_parity_guest.py`; `grep -nF '("g-stay-claimed", ' scripts/e2e/parity_cases.py`; `grep -nF '"apt-guide-qr": {"mask"' scripts/e2e/parity_cases.py`; `grep -n 'QR_PAYLOAD_CASES' scripts/e2e/*.py | head`; `grep -nF 'UBYHOST_AI_FEATURES=leon' scripts/e2e/parity_env.sh`. Missing: STOP.
2. Seed: in `seed_parity_guest.py` add `out["res_fee"]`: a second apartment (or the claimed apartment copy) with `stay_fee_collect=1`, `stay_fee_rate_czk=50`, a valid test IBAN (a documented test number, e.g. `CZ6508000000192000145399`), a claimed stay with `declared_guests=1` and one complete CZE guest (copy the `set_claim` and guest insert shape from lines ~58-80), so remaining is 0. Add the placeholder `{res_fee}` to the placeholder list the case runner knows (follow how `res_claimed` is registered: `grep -n 'res_claimed' scripts/e2e/*.py`). Commit `2064 step 2`.
3. Env: add `export UBYHOST_STAY_FEE_GUEST_PAY=on` to `parity_env.sh` next to the other `UBYHOST_*` exports, with a comment `# 2064: the guest stay-fee box (production has it on)`. Confirm both stacks read it (they start from this env: `grep -n 'parity_env' scripts/e2e/parity_gate.sh | head`). Commit `2064 step 3`.
4. Case: in `GUEST_CASES` after `g-stay-claimed-nocookie` add `("g-stay-fee", "/l/{tok}/{res_fee}", ["claim"], "H")`. In `QR_PAYLOAD_CASES` add `"g-stay-fee": {"mask": ["img.g-fee-qr-img"], "texts": [".g-fee-amt", ".g-fee-calc", ".g-fee-iban", ".g-fee-rail .g-summary-list"]}`. cs and en x 390/768/1280 come from the default language/viewport matrix of GUEST_CASES: confirm with `grep -n 'GUEST_CASES' scripts/e2e/*.py | head` that no per-case language list is needed. Commit `2064 step 4`.
5. Do not run the full parity tool. Run only the syntax check and the case listing: `python3 -c "import ast,sys; [ast.parse(open(f).read()) for f in ['scripts/e2e/parity_cases.py','scripts/e2e/seed_parity_guest.py']]" 2>&1 | tail -30` and `python3 scripts/context_lint.py 2>&1 | tail -3`. The full gate (owner/orchestrator run) must show `g-stay-fee` not `visible` at all six cell types; the QR image is masked, the payload text compared. If the gate shows a difference in the box, report it in `docs/tasks/2064-report.md` (do not fix Go here; open a follow-up brief).
6. Write the report (section 9), set `Status: review`, open one draft PR.

## 5. Do not touch

`App/app/**`, `go/**`, the existing seed rows of `res_claimed`, other cases, other env exports.

## 6. Commands

Only step 5's two commands. The parity tool and the guest browser tests are run by the orchestrator (2063 runs the guest browser and geometry tests with 0 skipped).

## 7. Acceptance

- [ ] Seed adds `res_fee`; existing seed rows untouched (`git diff` shows only additions).
- [ ] `UBYHOST_STAY_FEE_GUEST_PAY=on` exported once in `parity_env.sh`.
- [ ] `g-stay-fee` in `GUEST_CASES` and `QR_PAYLOAD_CASES`.
- [ ] Both files parse; context lint passes.

## 8. Stop and ask

Anchor missing; the harness has no place to register the new placeholder; more than 25 tool calls.

## 9. Report

`docs/tasks/2064-report.md`, 600 tokens at most.
