# 0177 report

Status: review

## Files changed

- `App/app/templates/reservations.html`: Property column removed (th and td). Stay cell now shows the colour dot (reuses `property_identity` with an empty name), the title, the source badge, and a muted property line when `stay_label` differs from `internal_name`.
- `App/app/routes/admin.py`: `RESERVATION_PAGE_SIZE = 15`.
- `App/tests/test_overhaul.py`: page counts 1-50 of 52 becomes 1-15, 51-52 becomes 16-30, "Page 2 of 2" becomes "Page 2 of 4".
- `App/tests/test_host_wide_geometry_browser.py`: removed the `.stay-col-property .property-identity` selector.
- `docs/tasks/0177-screenshots/` (390 and 1280 px) and this report.

No CSS change, so step 4 (design lint, static versions) was not run.

## Commands (last 5 lines)

- `pytest tests/test_overhaul.py -k paginate`: 1 passed.
- Browser set (4 files, `-rs`): 18 passed, 1 failed. The failure is `test_list_pages_share_order_edges_and_rhythm`, the known one. No skips.
- `shots.py ... --widths 390,1280`: "3 shots, 0 with problems".
- 0102-evidence cleanup: ran, not refused.

## Checklist (section 7)

- [x] No Property column; property once per row on desktop and phone; 15 rows per page; tests pass with 0 skipped, except the known failure.

## Deviations

- The brief's browser list omits `test_host_wide_geometry_browser.py`, which I edited, so I ran it too. It passed.
- Commit trailer: the launch message asked for Sonnet 5.5, but the session attribution is Claude Haiku 5.5, which is the model running. I used Haiku 5.5. Change it if the Sonnet line is wanted.
- Steps 1 to 3 went in one commit, `0177 step 1 to 3`.

## Questions

None.

## Owner steps left

- Review and merge the PR with `scripts/merge-pr-on-green.sh`. Production deploy is manual.
