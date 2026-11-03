# 0829 report: finish the /guide search

Status: blocked (only by the guest-guide help-tip failures below, which belong to the other executor's help-tip work)

Not committed, pushed or PR'd: the parent instruction said the orchestrator commits.

## Changes
- Step a: `App/app/templates/guide.html` removed the `guide.js` script tag. `App/app/templates/base.html` loads `/static/guide.js?v=20261102-0829` (defer, turbo-tracked) after host.js, under `show_nav`. `App/app/static/guide.js` now binds via `onPage` (same pattern as host.js), returns early without `#guide-search`, and the window hashchange and document click listeners stay behind the `__guideListeners` guard. The `turbo:load` listener was removed because `onPage` already reruns per page.
- Step b: `App/tests/test_0828_guide_search_browser.py` added `test_search_still_filters_after_turbo_swap_from_sidebar`. It opens /havel, clicks the visible `/guide` link (Turbo swap), types "PIN" and checks the filter. Passes.
- Step c: `App/tests/test_guide_coverage.py` regex now matches `<details class="guide-section ..." id=`.
- Step d: no CSS change. The host /guide geometry cases in the 0800 test already pass at all widths, so the 0828 block was not touched. This is a deviation from the "probe then fix" wording.
- Step e: no screenshots regenerated (see Deviations).

## Commands (final tails)
- `.venv/bin/python -m pytest tests/test_0828_guide_search_browser.py tests/test_guide_coverage.py tests/test_0507_page_hooks_browser.py -q --tb=line -p no:cacheprovider -rs` → `17 passed in 23.20s`
- `.venv/bin/python -m pytest tests/test_0800_v2_remaining_pages_browser.py -k guide -q --tb=line -p no:cacheprovider -rs` → `6 failed, 16 passed, 84 deselected` (all 6 failures are `test_v2_remaining_page[guest-guide-*]` at 320/390/768/1024/1280/1440, each `tap target 18x18 (min 24): <button class="help-tip-btn"> "?"`). Host `guide` and the GUIDE_PADDING cases: `8 passed`.
- Re-run of Turbo test alone: `1 passed in 3.63s`.
- `.venv/bin/python tests/test_static_versions.py --write` → `refusing: app2.css changed but still has ?v=20261102-0812` (left for the orchestrator to bump, per brief).
- repo root `python3 scripts/design_lint.py` → `design lint: OK`

## Deviations
- Step d: no CSS fix needed because the host /guide geometry tests pass.
- Step e: screenshots not regenerated. Guide.html and base.html changed, so the owner or orchestrator should take one 390 px shot per changed page.

## Questions
- Guest-guide 0800 failures (help-tip tap target 18 px) are from the help-tip work, not this change. Confirm with the other executor before treating this as blocked.

## Owner steps left
- Bump the static key for app2.css (refused above) and then run `tests/test_static_versions.py --write`.
- Once the help-tip executor makes `help-tip-btn` 24 px, rerun the 0800 guide command for 0 failed.
- Commit and open the PR.
