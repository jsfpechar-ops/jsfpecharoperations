# 0084 report: host UX integration acceptance

Status: review. Executor: Claude (owner-authorized to implement and verify). Matrix: [host-ux-acceptance](../plans/host-ux-acceptance.md). The coordinator chose this path; brief §3 named `host-navigation-integration-acceptance.md`. Brief §3/§5 said "no application change"; the coordinator allowed small template/CSS fixes, listed below.

## Candidate

- C = `cc4e8d9a8f667bc6b60d3a108dd93dce4bd3c330` (`claude/quirky-lamport-9svmd1`), plus the `0084:` commit on top (tests, three small fixes, evidence, docs).
- P = `ab0a2f1e43d3162b425cdd23402925536aa59548` (origin/main). No unresolved conflicts; working tree clean before 0084.
- Reports read (all `Status: review` or equivalent, CI "not run" in each): 0087, 0095, 0088, 0089, 0090, 0091, 0092, 0093a, 0093, 0094, 0075, 0076, 0077, 0078, 0079, 0080, 0081, 0082, 0083.
- CI: checked by coordinator (GitHub). Full suite + coverage: run by coordinator.

## What was done

- New `App/tests/test_host_ux_acceptance.py` (12 tests, browser where needed, synthetic data, no live provider):
  - ownership counted on 26 rendered page families: unique ids, no nested forms, no cloned editor forms (EN/CS); each of 43 property settings has one editable control in the whole host; no copied guest-link/automation/fee editor; one shared entity editor; issued invoice has no editor;
  - one/many/no/archived properties on hubs, Search and the Properties summary;
  - all legacy GET/POST adapters land on the canonical home (POST rerenders with typed values, writes nothing on refusal);
  - shared business edit leaves the issued invoice row identical;
  - browser: rail/cards/Search/Back journeys in EN and CS; keyboard order with visible focus; JavaScript-off tabs, hash, property, business and invoice-details saves; geometry sweep 26 families × 9 widths × EN/CS × rail expanded/collapsed (780 renders, 25,951 controls).
- Every protocol §6 behaviour row is linked to a named test in the matrix §2.
- Screenshots: `docs/tasks/0084-evidence/` (96 JPG, 16 families × 360/390/1280 × EN/CS) and `measurements.json`, from `UBYHOST_CAPTURE_0084=1`.

## Defects fixed (small, template/CSS, each with a test)

1. **D1** `/entities` Business details and Add business forms had no `_csrf`: without JavaScript the canonical business save failed with "This form expired". Added the hidden field (`App/app/templates/entities.html`). Test: `test_without_javascript_tabs_reload_and_the_shared_editors_save`.
2. **D2** Guide at 360 px EN/CS overflowed (380 px) because of the UbyPort URL in a step. `overflow-wrap:anywhere` on guide steps.
3. **D3** Stay fees list at 760 px CS overflowed (773 px): sr-only actions header escaped the scroll panel. `.panel.fee-periods { position: relative }`, as the house book already does.
- D2/D3: `/* 0084 acceptance fixes */` block at the end of `App/app/static/host.css`; `host.css` cache key bumped in `base.html`. Test: `test_every_page_family_fits_every_width_language_and_rail_state`.

## Open (not fixed; need a brief or a decision)

- **O1** Dirty property settings: only the browser's native Leave/Stay prompt. Plan maintainability §5 requires a Save / Discard / Stay choice and a Discard control; neither exists. Drafts do survive in-page tab/group switches and Back/Forward. Needs a scoped `app.js`/template brief.
- **O2** FIXED ("0084 O2"): Properties, Businesses, Invoices, Stay fees and Reports lists are compact labelled cards when their panel is under 1000 px (container query, `/* O2 list cards */` in host.css), table above; no inner sideways scroll, actions visible. Test: `tests/test_host_list_cards_browser.py`; screenshots `0084-evidence/o2-*.png`.
- **O3** Pre-existing: most other host POST forms (account settings, archive/restore menus, smart-lock forms) depend on `csrf.js` and do not work with JavaScript off. Rule 6 covers auth forms only; noted, not changed.
- Carried over from task reports: the invoice-details lookup-only IČO (0076 decision 1); the Technical/2FA/passkey disclosures kept on Settings (0083); `#file-by-hand` stays a `<details>` (0080).

No filing, invoice, fee or lock logic was touched.

## Commands (from App/, env above, Chromium 1194)

```
pytest tests/test_host_ux_acceptance.py -q -rs                      → 12 passed (≈2 min; sweep ≈100 s)
UBYHOST_CAPTURE_0084=1 pytest tests/test_host_ux_acceptance.py -q   → 12 passed (evidence written)
pytest <30 focused files cited in the matrix>                       → 335 passed, 0 skipped
pytest test_overhaul (2 cited) test_guest_navigation (1) test_wp28_geometry
        test_host_controls_browser test_host_property_controls_browser → 14 passed
ruff check app tests tools --select E9,F63,F7,F82,F401,F841          → All checks passed!
python3 scripts/context_lint.py                                      → context lint: OK
```

## §7 acceptance

- [x] Predecessors integrated; C/P recorded.
- [x] One canonical editor and domain contracts: ownership/behaviour matrix.
- [ ] Full suite + coverage and current-head CI: coordinator.
- [x] EN/CS, all widths, rail states, long content, keyboard and focus measured.
- [x] Synthetic screenshots and measurements.
- [ ] No outstanding defect: O1 and O2 are open for review.

## Limitations

- The sweep checks horizontal fit and clipping of visible controls. It does not check vertical overlap or sticky-bar covering.
- Controls inside an intentional scroller are counted, not asserted.
- Full-page JPG screenshots show the fixed rail only in the first viewport height.
- The sweep measures the drawer (≤960 px) closed and does not open help tips or export menus.

## Owner steps

1. Open `docs/tasks/0084-evidence/property-guests-1280-en.jpg`, `property-overview-360-cs.jpg` and `fees-390-cs.jpg`.
2. Decide O1 (Save/Discard/Stay) and O2 (mid-width list tables), or ask the orchestrator for briefs.
3. After green CI on the 0084 head, release 0085 (staging) with this exact SHA. Stay off `main`.
