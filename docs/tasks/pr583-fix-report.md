# PR #583 fix report — navigation and visible acknowledgement

Status: review (local only; not pushed, not merged).

## Request and authorisation check

The pasted prompt is `previous-bundle/LOCAL-AI-PROMPT.md`. Two of its pointers are
stale against current source:

- `docs/plans/postgresql/ubyhost-ahndoff/20261030/README.md` does not exist. The
  current handoff is `docs/plans/postgresql/ubyhost-handoff/README.md`.
- `docs/context/workflow.md` records the Luna 6.0 / Cursor executor exception as
  retired (2026-10-17); the bundle's task-specific Luna section says it is closed
  by the latest owner-supplied AGENTS.md. No `docs/tasks` brief is `todo`:
  0451–0454 are `review`, 0455–0456 are `blocked`.

The owner's current message nevertheless ranks PR #583 first. I therefore did
not apply the manifest bundle and instead executed the one source-verified
request it marks as priority: `handoff/INPUT-pr583-handoff.md`, after checking
its reviewed commit is still the live PR head.

## Base verification (no patch applied)

| Item | Value |
|---|---|
| PR #583 base | `8b5317d0a49b840136fbfbcad7fb06af100f3575` |
| PR #583 head (reviewed commit) | `69efd1a51212d2a2e20d96c62c8138a020496272` — unchanged |
| Bundle `manifest.json` base | `8b5317d0…` (exists in this clone) |
| Manifest file hashes | 48/48 SHA-256 match |
| Bundle target files vs current tree | differ (main lacks 0451–0454; PR branch differs in form/legal/claim/CSS) |

The recorded base is not the current checkout HEAD, and the manifest-listed
files differ from the live source, so no bundle patch was applied: nothing was
overwritten and nothing was applied twice. 0452 (analytics) and 0455/0456
(PostgreSQL) stay unexecuted as gated.

## Work done on `fix/pr583-navigation-ack-restored` (from `69efd1a5`)

1. `App/app/templates/guest/form.html` — removed the outer `<details
   class="g-legal-fold">` wrapper; the partial's own `.g-legal-text` disclosure
   is now the single fold, and the required `legal_ack` checkbox/label stay
   visible outside it. The save button now renders `t(save_action_key)`.
2. `App/app/routes/guest.py` — `_form_context` computes the action in order:
   edit → `guest_save_changes`; unknown headcount → `guest_save_details`; one
   remaining → `submit_registration`; otherwise `save_continue_next`. After the
   save, the reservation is re-read (the save can persist a headcount typed on
   the first form) and the redirect continues to `/new` only for a new guest
   with a known positive missing count. Edits and the final guest return to the
   summary. Validation, capacity, persistence, reporting, door-code and
   notification calls are untouched.
3. `App/app/guest_uk_i18n.py`, `App/app/i18n.py` — six-language
   `guest_save_changes` / `guest_save_details` labels; `person_saved` shortened
   to "Previous guest saved." (and the equivalent in cs/de/es/fr/uk).
4. `App/app/templates/guest/claim.html` + `App/app/static/guest.css` — the email
   help control now takes its accessible name from the existing approved string
   `tw_email_more`, and shows one visible "?" (the generated duplicate removed).
5. `App/tools/smoke.py` — a save now expects either the completed summary or the
   "previous guest saved" strip on the next form.
6. `App/tests/test_guest_browser_e2e.py` — real-browser checks: the ack stays
   visible with `.g-legal-text` closed, the sticky submit button does not cover
   it, submitting without it is blocked, the next form is blank, and the
   three-person flow has no Saved/Add-a-person page. Adds the 390 px English run
   and writes the four evidence screenshots when `UBYHOST_0451_SHOTS=1`.
7. `App/tests/test_guest_navigation.py` — HTTP coverage for the ack outside the
   fold, the four save-action labels, direct three-person progression, edit
   returning to the summary without a duplicate row, unknown-headcount
   progression, and the one-person submit label.
8. `App/tests/static_versions.json` — regenerated after the `guest.css` change.

## Validation (on the restored branch)

```
UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_guest_*.py \
  tests/test_guest_browser_e2e.py tests/test_host_geometry.py -q -rs --tb=short -x
560 passed in 178.11s (0 skipped)
```

```
.venv/bin/python -m pytest tests/test_static_versions.py tests/test_form_chrome.py \
  tests/test_ticket_wallet_v3.py tests/test_guest_notice_ack.py -q --tb=short
39 passed in 0.93s
```

```
UBYHOST_REQUIRE_BROWSER=1 UBYHOST_0451_SHOTS=1 .venv/bin/python -m pytest \
  "tests/test_guest_browser_e2e.py::test_a_group_of_three_registers_everyone_on_one_phone[en-390]"
1 passed in 9.72s
```

Local smoke (mock UbyPort, staging profile, no production access):
`44 pages checked / no dead pages, no server errors`, exit 0.
`git diff --check` clean; `python3 scripts/context_lint.py` → `context lint: OK`.

390 px screenshots (390 × H, inspected once):

- `docs/tasks/screenshots-0451/acknowledgement-390.png` (390×812, viewport)
- `docs/tasks/screenshots-0451/claim-390.png` (390×1346)
- `docs/tasks/screenshots-0451/next-guest-390.png` (390×1920)
- `docs/tasks/screenshots-0451/completion-summary-390.png` (390×1503)

## Deviations and gaps

- A concurrent process using this workspace committed
  `21351f13` + merge `6c02d24a` on the original `fix/pr583-navigation-ack` and
  included a 0453 contextual-help implementation and the main merge. That work is
  preserved there; this verified work is isolated on
  `fix/pr583-navigation-ack-restored` to avoid clobbering it. No force-push, no
  reset of the other branch.
- Not pushed; PR #583 description still needs the final behaviour/verification
  text and the invalid `Closes #0` removal (owner/reviewer step).
- PR CI not re-run from this machine; the three failures observed at the reviewed
  head were addressed locally (stale `static_versions.json`, smoke confirmation
  wording, and browser tests that still expected the removed legal step).
- Contextual help for the remaining fields (0453) was not implemented here: it
  needs approved-source wording. Billing analytics (0452) and PostgreSQL
  (0455/0456) were not executed; their gates stand.
- No merge, push to main, deployment, production query or secret access.
