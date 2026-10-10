# 0040 shared host CSS report

**Status:** implementation frozen; 444-combination lane matrix and final full coverage suite passed
**Executor:** owner-authorized Luna team
**Branch:** `task/host-design-staging`

I changed only [host.css](/workspace/jsfpecharoperations/App/app/static/host.css).
The corrected shared page lane now keeps headers, contextual navigation,
toolbars, expanded filters, results, and empty states centered together. The
invoice builder heading has a separate 1050px cap matching its form workspace.
The all-unconfigured Stay fees table uses compact Property/Status/actions tracks in its
all-unconfigured state. The invoice builder action bar is in document flow so
it does not cover form fields.

A final route review found two direct-child Back links on Stay fee setup/detail
that were not inside `page_header`; their inline-sized boxes stayed at the
wrapper edge. A direct-child-only offset now aligns those links to the centered
1080px lane without widening the anchor's keyboard/click hit area. Other Back
links use the shared header macro and already inherit the lane.

The staging corner reminder was a persistent `.notification-stack` from
`_host_alerts.html`, separate from transient feedback. It now uses the same
centered 1080px lane in normal flow at desktop and mobile sizes; the existing
warning colors, message links, and dismiss actions remain intact. Required
Chromium validation confirmed the open, non-dismissible alert stays in normal
flow.

The final 760px review also found the dashboard header inherited the app-wide
column layout but retained centered cross-axis alignment. Host dashboard
headers now wrap as a row with a left-aligned date/title and intrinsic-width
action controls; the Add stay action remains adjacent where it fits. Validation
confirmed at 760px that the title aligns with the result lane and controls fit
inside the header without intersecting the title, with the alert fixture
inserted after server startup so database initialization could not resolve it
first.

The address form’s Save/Back group also left sticky positioning after the
focused mobile ZIP field overlapped it. It now follows the form in normal flow;
the existing paired controls and button sizes are preserved. The focused
overlap check passed; the Czech viewport-edge measurement is within 0.5px of
the test’s 1px rounding tolerance.

The Stays table now gives row actions enough space for EN/CS Copy plus More at
desktop widths, and wraps the stay date at natural separators inside its own
track. At 721–1100px it becomes a labeled two-column card layout; at mobile
widths the row actions remain adjacent, with 44px touch targets. The external
portal link remains on one line. Deadline and reporting status pills are
constrained to their own tracks and wrap at natural spaces, keeping overdue
and scheduled-ready text readable without crossing into neighboring cells.
Wrapped overdue badges use modest rounded-rectangle corners so the full Czech
label remains legible against its red background. The row Send action now
matches More at 42px desktop and 44px mobile. Feedback, manual-copy recovery,
and command copy-denial content use the host content lane in normal flow; empty
feedback regions are visually clipped without removing their live announcers.

Validation captured 40 synthetic before screenshots and DOM rectangles at
1440–2048px across dashboard, stays, properties, operators, invoices, fees,
invoice settings/details, and property forms. The original title/result
left-edge mismatch grew from 38px at 1440 to 342px at 2048. Focused required
Chromium checks then passed EN/CS Stays at 1024 and 1280: no viewport overflow,
all visible Copy/More pairs fit within the panel and share a 42px row, date and
property content stays inside its table track, and portal links remain
unwrapped. The fresh Czech 1280 screenshot shows the date on two natural lines
without overlapping the property identity. The latest focused required
Chromium run passed 4 tests with 0 skips, covering the actual open alert,
760px dashboard, mobile property Save behavior, fee Back links, and collapsed
sidebar geometry. A follow-up Stays midwidth browser run passed EN/CS at 1024
and 1280 after a synthetic overdue fixture exposed deadline and scheduled-ready
pill overflow; the refreshed screenshots show both labels wrapping within
their own cells. The refreshed Czech 1280 visual review confirmed the overdue
words stay inside the red badge and row Send aligns with More. Dashboard and
invoice owners also reported their focused matrices passing. The 444-combination
lane matrix completed with 1 pass and 0 mismatches. The final full coverage
suite rechecked the frozen CSS with stronger visible-text and all-action guards:
3030 passed, 0 skipped, 7 warnings, and 89.57% coverage. The enhanced JS month
filter now removes the empty-state wrapper border, padding, and background so
its month trigger is the only visible control; the native no-JS fallback
styling remains available.

Property-focused evidence is under `/workspace/generated_images/host-wide-audit/after/`:
`after-address-focused-360-en.png`, `after-fee-backlink-1440-cs-0.png`, and
`after-stays-actions-en-1280.png` / `after-stays-actions-cs-1280.png` (rounded
overdue badge and aligned Send / More). The focused stays geometry logs are
`/tmp/ubyhost-stays-midwidth-final2.log` and
`/tmp/ubyhost-wide-actions-containment.log`. The focused lane, Save, and backlink
checks are in `/tmp/ubyhost-wide-focused-final3.log`. Enhanced month geometry
passed at 390/1280 EN/CS in `/tmp/ubyhost-filter-geometry-final.log`. Final full
coverage is in `/tmp/ubyhost-final2-full-coverage.log` (624.83 seconds, exit 0).
No commits or pushes were made.
