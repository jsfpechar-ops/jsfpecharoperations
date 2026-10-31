# 0451: Direct guest progression and visible acknowledgement

Status: review
Base: `8b5317d0a49b840136fbfbcad7fb06af100f3575` | Branch: `codex/ubyhost-corrections-20261030` | Executor: Luna, owner-scoped authorization

## 1. Objective

After a new guest saves, open the next guest form immediately only when a freshly read reservation has a known positive missing count. The final new guest and every eligible saved edit return to the stay summary. Keep the prior guest saved status visible on the next form. Keep the required acknowledgement visible while optional legal explanations are collapsed. Keep server validation and save side effects unchanged.

## 2. Context: verified current source

- `App/app/routes/guest.py`: `_form_context` calculates `remaining`; `/save` ends with the saved summary redirect and ownership cookie. Unknown headcount is entered on the first form and persisted before save completes.
- `App/app/templates/guest/form.html`: the final button currently uses `submit`; the partial is included at the final wizard step.
- `App/app/templates/guest/_legal_notice.html`: explanatory legal text and the required `legal_ack` checkbox are in one outer container. No disclosure exists yet.
- `App/app/templates/guest/stay.html`: `just_saved` selects the saved/reporting confirmation.
- `App/tests/test_guest_navigation.py`: existing coverage includes party capacity, wrong stay, saved/reporting status, and claimant ownership.
- `App/tests/test_guest_notice_ack.py`: a missing acknowledgement returns 422 and persists no guest.
- `App/tests/test_guest_browser_e2e.py`: the existing three-person scenario currently uses an Add a person interstitial.

## 3. Files

| Path | Action |
|---|---|
| `App/app/routes/guest.py` | Add save action context; after all existing side effects, refresh reservation and advance only for a new guest with `missing > 0`; preserve `saved=1` and ownership cookie. If refreshed reservation is missing, return to summary. |
| `App/app/templates/guest/form.html` | Use the action key; display the concise prior-guest status when `saved=1`. |
| `App/app/templates/guest/_legal_notice.html` | Collapse only existing explanatory legal text and leave acknowledgement/error outside the disclosure. Do not change legal wording. |
| `App/app/i18n.py`, `App/app/guest_uk_i18n.py` | Add four save action labels and the short previous-guest status in all six supported languages; shorten saved summary body. |
| `App/tests/test_guest_navigation.py` | Verify direct known-count progression, edit return-to-summary while others remain and after completion, and no duplicate guest row on edit. |
| `App/tests/test_guest_browser_e2e.py` | Verify the three-person direct flow, empty identity/signature/ack state for each next guest, visible acknowledgement while legal text is closed, native missing-ack blocking, and unknown-count progression using a synthetic browser fixture. |
| `docs/tasks/0451-visible-guest-acknowledgement.md` | This brief. |
| `docs/tasks/0451-report.md` | Actual checks and remaining evidence. |
| `docs/tasks/screenshots-0451/` | Synthetic 390 px screenshots of acknowledgement, next-guest, and completion states. |

No CSS or JavaScript change is in scope. No static cache key change is needed.

## 4. Steps and save action rules

In `_form_context`, choose the action in this order:

1. Existing guest: `guest_save_changes`.
2. New guest with unknown or non-positive remaining count: `guest_save_details`.
3. New guest with exactly one remaining: `submit_registration`.
4. New guest with more than one remaining: `save_continue_next`.

After save side effects, fetch the reservation again and read `reporting.reservation_progress(...)["missing"]`. Redirect only if `existing is None`, the fresh `missing` value is known, and it is positive. Keep `saved=1` on the next form and on the summary redirect. Keep `_remember_owned` unchanged. Do not alter validation, capacity checks, persistence, reporting, door-code, or notification calls.

## 5. Do not touch

Do not change validation, capacity checks, persistence fields, reporting, door-code, or notification side effects. Preserve legal notice wording and all existing language/cookie/ownership helpers. 0451 owns save-action keys and confirmation copy; 0453 owns contextual-purpose keys and its shared email disclosure, applied only after this brief.

## 6. Commands

From `App/`, with `set -o pipefail`:

```bash
.venv/bin/python -m pytest tests/test_guest_*.py tests/test_guest_browser_e2e.py tests/test_host_geometry.py -q -rs --tb=short -x 2>&1 | tail -30
```

This is the guest row from `docs/context/test-map.md` plus the required geometry check; expand and report the actual `test_guest_*.py` filenames. Browser and geometry checks must have zero skips. Also run from repo root:

```bash
git diff --check 2>&1 | tail -30
```

## 7. Acceptance

- Three guests save in order with no Add a person page between them; the third save reaches the completed summary.
- The next form has blank name, signature, and acknowledgement values and shows the short prior-guest status.
- The required checkbox and label are visible while `.g-legal-text` is closed; submitting without acknowledgement is blocked and server missing-ack coverage still passes.
- Unknown headcount shows the neutral `Save details` action. The entered headcount, persisted on first save, determines whether a next form opens.
- An eligible incomplete edit says `Save changes` and returns to summary while another guest is missing; editing does not create a duplicate row. A completed or reported form remains locked and returns 403.
- Existing wrong-stay/ownership/capacity protections remain covered by their current tests.
- Legal explanation text remains byte-for-byte unchanged; acknowledgement validation remains required.

## 8. Stop and ask

Stop only if the source structure materially differs from the verified anchors, a test fails twice, or required local browser tooling is unavailable. Preserve partial local work and report exact evidence. Do not push, commit, merge, deploy, add dependencies, or edit unrelated files.

## 9. Report and screenshots

Capture one synthetic 390 px screenshot for the acknowledgement step with legal text closed, one next-guest form with the saved status, and the completed summary. Inspect each once. The report must include exact commands, exit codes, skipped count, screenshot paths, and remaining gaps. Set Status to `review` only when all mandatory evidence exists; otherwise use `blocked` with the exact missing evidence.
