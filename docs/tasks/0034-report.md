# 0034: Quiet host dashboard — implementation report

Status: review

Implemented the Quiet overview in `App/app/templates/dashboard.html`, using a
Prague-date candidate set and a single five-row display cap in the dashboard
handler. Counts come from all candidates before truncation. Routine stays are
current or arrive within 30 days; unresolved overdue and failed work remains a
candidate outside that window. The display deduplicates stay IDs, prioritizes
Needs action, then current stays, then the nearest arrivals. Its actionable
overflow link counts only omitted unique Needs action stays.

The dashboard now has four white semantic count cards with neutral zero states,
a plain title, compact date/property/status rows, aligned Open and More actions,
and a native keyboard/touch More disclosure preserving guest and archive
actions. Guest-form copying uses the owner-approved label and URL. Actionable
missing-guest counts retain their localized wording inside the amber status
pill; ready rows stay blue, overdue rows red, and waiting counts taupe. The
positive cards use a quiet colored attention line, with hover and visible
keyboard focus. Setup warnings, onboarding, feed/sync and no-feed states remain.
Rows use the existing guest-count macro so known headcounts remain visible and
unknown empty counts stay quiet. Filed-on-time and filed-late badges appear once
in the task slot; overdue stays red only while unresolved. Filing and deadline
calculation logic are unchanged.

`App/app/reporting.py` keeps the default `dashboard_rows` date window for its
other callers. The dashboard-specific overview option uses Prague local time,
includes long current stays and older unresolved urgent work, and does not
alter filing state or deadline calculations. The dashboard-only selection
helper enforces the total row cap and current-before-arrivals ordering.
The candidate helper annotation accepts the actual `sqlite3.Row` returned by
`db.query` plus `Mapping[str, Any]` test/adaptor inputs. A local `Any` view is
needed because the Python `sqlite3.Row` stub permits integer/slice indexing,
while runtime callers use its supported column-name indexing. No suppression,
query, state, or selection behavior changed.

Validation from `App/`:

- Dashboard policy, queue, copy, order, and empty-state tests: **38 passed**.
- Expanded regression checks including deadlines, query budgets, and encrypted
  reporting data: **84 passed** across the combined focused run.
- Required Chromium dashboard browser tests: **2 passed, 0 skipped**. The
  original single-waiting stay case remains. A second real-route fixture has
  six actionable stays, one waiting stay, one ready guest, and an unresolved
  overdue stay older than 45 days. It verifies all four positive counts before
  truncation, five unique displayed rows, one omitted actionable stay, status
  colors, overflow, responsive geometry, and separate hover/focus states. When
  the cap hides all current rows, the empty current section is omitted and the
  Waiting card links to the stays list instead. Browser geometry checks measure
  all six row and menu actions at EN/CS widths 360 and 390px and require 44px;
  desktop Open and More remain 42px.
- Final dashboard CI regression run across deadline, headcount, Czech language,
  signed-in chrome, overview policy, and required browser modules: **44 passed,
  0 skipped**.
- Meaningful screenshots: `generated_images/host-quiet-dashboard/dashboard-{en,cs}-{360,390,1280}.png`.
  Separate interaction screenshots use `dashboard-hover-{locale}-{width}.png`
  and `dashboard-focus-{locale}-{width}.png`; retained baseline captures use
  `dashboard-single-{locale}-{width}.png`.
- One existing Starlette `TestClient` deprecation warning appears in the
  focused Python run.
- `python3 scripts/context_lint.py`: **OK**. It reports that 10 App commits
  landed after the last `docs/context/status.md` update; root owns that status
  refresh.
- Type-only follow-up: scoped dashboard policy tests **5 passed**; scoped Ruff
  checks **passed**. Full CI mypy still exits nonzero on its existing baseline
  of **175 informational findings**, with the former dashboard `Row` argument
  finding removed. Its remaining `reporting.py` findings are in the unrelated
  hand-filing datetime code at lines 2183–2184.

No deployment was performed. This change is ready for root review; staging is
the next deployment target after that review.
