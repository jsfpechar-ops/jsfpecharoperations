# 0525 report
Status: blocked
Deviations: Done: steps 1 to 3. Left: steps 4 to 5 (test_0525_stay_detail.py, static version bump, screenshots at 1280 and 390 px) and the section 6 pytest and browser runs. Stopped at the 25-call checkpoint before step 4.

Commits on task/0525-stay-detail-style after aee53c8: step 1, step 2, step 3, this report.

Diff stat (aee53c8 to HEAD, before this report):
 3 files changed, 18 insertions(+), 2 deletions(-)

Step 1: reservation_detail.html, `guest-card-doc` span added to guest cards and to the placeholder card (`—`). Anchors found; no command in the step.
Step 2: host2.css, block appended inside `@media (min-width: 1024px)` (guest-cards card, guest-card rows, 4-column head grid, door card). No command in the step.
Step 3: `python3 scripts/design_lint.py 2>&1 | tail -5` -> `design lint: OK`.

Deviations:
- Step 2: bare px is forbidden by the S2 lint, so 16 px is `var(--space-4)` and 18 px is `var(--text-lg)`.
- Step 2: the head grid has 4 tracks but 3 children. The menu sits inside `guest-card-state`, so the 4th track is empty. No `guest-card-doc` style rule was added (not in the brief).
- Step 2: placeholder cards keep their dashed look from host.css.
- Step 3: the new classes went into `classes` (the list lint reads) and their descriptions into `class_notes`. `data-stay-header-copy` was not added: lint does not check data attributes.
- Browser geometry not yet run for the step-2 CSS. Section 8 assertion edits: none so far.

Questions: none.
Owner steps left: none yet.
