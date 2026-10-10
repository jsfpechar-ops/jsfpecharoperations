# 0033 implementation report

The Stays, Invoices, Stay fees and Guest register pages now use expandable filter panels with server-applied summaries. Native GET controls remain usable without JavaScript. Stays and Guest register share a single From/Until calendar; date edits stage until Apply dates, and filter criteria submit once on Apply filters. Invoice month selection remains optional; Stay fees require a month. Month changes and year stepping stay draft until the outer form is applied.

Stays keep explicit Upcoming, Past, All and Archived views. `archive_scope=1` preserves Archived results while users edit custom dates, property or status, and Reset returns to Archived. It does not change ownership or status SQL predicates. Saved-view labels use the applied summary even when filter-panel drafts are dirty. The Guest register Delete label still posts to the existing soft-archive route and retains Undo/Restore behavior. CSV export summaries display the applied property scope while retaining existing query parameters. Archive success wording retains the existing flash keys and restoration guidance.

Validation used real Chromium against the application, with no browser-test skips. Draft calendar coverage includes keyboard selection/focus, one-sided dates, Clear, reversed bounds, Escape/outside cancellation, and outer Cancel. Month coverage checks grid options, required/optional semantics, local stepper behavior, Cancel restoration and one-request submission. Stays tests cover native no-JS GETs, archived property/status and Reset, saved-view draft isolation, and the soft-archive POST. The geometry suite checks EN/CS at 360, 390, 471, 760, 850 and 1280px; day controls and draft date inputs are measured at mobile widths. The page heading, filter rail and results share the same content edge.

Combined route/filter/geometry run and output:

```text
UBYHOST_BROWSER_EXECUTABLE=/usr/bin/chromium UBYHOST_REQUIRE_BROWSER=1 XDG_CONFIG_HOME=/tmp/ubyhost-luna-xdg/config XDG_CACHE_HOME=/tmp/ubyhost-luna-xdg/cache .venv/bin/python -m pytest tests/test_stay_fee_list.py tests/test_stays_empty_workspace.py tests/test_wp33_gates.py tests/test_host_filter_panels_browser.py tests/test_host_geometry.py::test_the_month_filter_shares_its_page_edges -q
...................................                                      [100%]
35 passed, 1 warning in 23.11s
```

The warning is Starlette's existing `httpx` deprecation notice. This run has zero browser skips. It also rechecks the month stepper native bounds, past-month availability and crafted-month fallback, empty-workspace controls, unbounded default Stays, and the explicit Upcoming exclusion. Additional checks passed: `node --check App/app/static/app.js`, Python compilation for the route, localization and browser test, `git diff --check`, and `python3 scripts/context_lint.py` (OK; it warns that 10 App commits need the orchestrator's status.md review update).

Final soft-coral month-choice check, with EN/CS selected-month screenshots at mobile/desktop widths:

```text
UBYHOST_BROWSER_EXECUTABLE=/usr/bin/chromium UBYHOST_REQUIRE_BROWSER=1 UBYHOST_CAPTURE_FILTERS=1 XDG_CONFIG_HOME=/tmp/ubyhost-luna-xdg/config XDG_CACHE_HOME=/tmp/ubyhost-luna-xdg/cache .venv/bin/python -m pytest tests/test_host_filter_panels_browser.py tests/test_host_geometry.py::test_the_month_filter_shares_its_page_edges -q
.....                                                                    [100%]
5 passed, 1 warning in 32.44s
```

The selected month uses the existing soft-coral `--brand-soft` background with `--brand-ink` text and a brand-action border. The test asserts the computed selected background. The 81 rendered application screenshots are in [`generated_images/host-design-application/filters`](/workspace/generated_images/host-design-application/filters). They include collapsed/expanded Stays, Invoices, Stay fees and Guest register states in English and Czech at 390px and 1280px, date and month popovers, selected Invoice months in both languages and widths, and Stay-fee detail month panels in both languages and widths. Full-page captures reset scroll to the top before capture.

## Owner steps

1. Review the screenshots, task diff and the filter/export/property integrations on `task/host-design-staging`.
2. Run the repository-wide suite and context lint after all parallel task files settle. This executor did not commit or push.
