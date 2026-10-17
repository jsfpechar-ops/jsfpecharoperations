# Copy, search and status-feedback review

Owner request, 2026-10-10. This is the original reference-code review and
prototype analysis. Application integration is now implemented by the
owner-authorized Luna executors in tasks 0032 and 0039; see the
[application review](host-design-application-review.md) for current evidence.
The supplied HTML is treated as visual reference code.

## Copy example: use its effect, fix its behavior

The first example supplies the overlapping copy/checkmark SVGs and a drawn
check stroke. It does **not** call the clipboard; its entire wrapper is a
clickable div and an idle timer invents confirmations. Its 30px button and
10px toast are too small for this app's audience.

Retain the checkmark effect in a real button with a readable label, using coral
confirmation on the button and semantic green for a confirmed success notice.
Reserve one icon slot and enough label width before/after copying. Confirm
only after a successful clipboard write; handle denied access and unsupported
clipboard APIs, with selection/manual-copy fallback. Copy guest links/messages,
identifiers and search copy actions must share this outcome handling.

Paths inspected before implementation: `App/app/static/app.js::initCopy` handles `[data-copy]`
buttons (including stay links and Guest links messages). The old
`execCommand('copy')` false result reached the success branch, and asynchronous
clipboard rejection lacked a handler. The command palette also promised success
when the clipboard API was unavailable. Task 0032 corrects these outcome
contracts and verifies denied-copy/manual-source behavior in Chromium.

No copied link, PIN, identifier, guest message or guest identity belongs in a
toast, telemetry, screenshot fixture or newly retained browser record. The
preview copies only `https://example.invalid/guest/demo`.

## Search example: keep the current engine

The second example is a seven-item local demo. Its opening/selection/filter
visuals are useful; its selected command merely closes the panel. It lacks a
real search endpoint and complete focus/ARIA behavior, and auto-types queries.
Replacing the current engine would remove functionality.

The existing app already has visible Search, Ctrl/⌘K, arrow/Enter operation,
a native dialog, `/api/command-palette`, grouped results, multi-word fuzzy
matching, recent ordering and real navigation/actions. Keep that engine and
its permission scope. Borrow quieter selected rows, predictable spacing, a
large labelled input, visible close control and readable result context.
Familiar destinations/property names beat “commands” as the main language.
Shortcuts remain optional. Do not introduce blur-heavy effects or animation
that searches/types/opens by itself.

Follow-ups within a scoped search-polish brief: ensure the combobox exposes
its active result, close restores focus, empty results are distinct from
network failure, and keyboard/touch hover share one clear highlight. The
prototype shows this treatment on fictional properties/pages; it is not a
replacement for the real search endpoint or fuzzy engine.

## Notification example: approved visual family, truthful results

The third example supplies white/light notification cards, semantic icons,
stacking and a lifetime indicator. Its default theme is dark, its rail is
`aria-hidden`, subtitles truncate and it generates random updates. Adapt the
card structure and small entrance motion; remove demo lifecycle code, dark
theme hooks, automatic updates, truncated messages and the frame-by-frame
spring/progress loop.

Use existing colors and language, one accessible announcement per outcome,
44px dismiss targets, readable wrapping and reduced motion. Place cards above
mobile/browser safe areas and away from fixed controls. Maximum three visible,
deduplicate identical updates, queue the remainder without losing errors.
Success/info: seven seconds, pausing on hover, focus and hidden documents.
Failures/partial warnings/Undo: persistent until dismissed. Dismissing a focused
card restores focus to the originating control when it still exists.

| Trigger / actual result | Treatment and truthful wording |
|---|---|
| Save completed | Green check, “Changes saved” |
| Copy completed | Checkmark on the unchanged-size button; green “Copied” |
| Send initiated, no confirmed result yet | Muted blue information, “Report is being sent” |
| Confirmed acceptance with normal proof handling | Green “Report accepted”; report/receipt access remains visible |
| `ok_duplicate` | Settled information, “Already reported”; never “New report sent” or a fabricated new receipt |
| `partial` | Amber persistent warning; use the existing result explanation and link to the report |
| `error` | Red persistent failure with the existing actionable explanation |
| `transport_error` or uncertain/missing proof | Persistent warning/error appropriate to the actual existing outcome; never imply acceptance |
| Delete performed through archive operation | Information, “Item moved to Archived”; retain Undo if the existing flow provides it |
| Restore completed | Green “Item restored” |

`docs/OPERATIONS.md` distinguishes guest `submit_state` from `submission.state`;
severity and receipt rules remain authoritative. No new send, retry, state
transition, receipt generation or retention behavior is part of visual polish.
Unknown flash messages default to information; do not infer success by searching
their text for keywords. Persistent row statuses/field errors/report evidence
stay on the page. Existing auth or guest no-JS behavior must still work.

## Implementation sequence and scope

1. Shared notification shell, timers, announcements and copy result handling.
2. Bind existing host save/report flash results to variants using their actual
   outcomes, without altering the filing operation. Review receipt uncertainty
   and mixed/duplicate outcomes explicitly in that brief.
3. Search appearance/accessibility polish preserving its current engine and
   endpoint; no replacement command system.

Use the same components wherever the host UI currently uses transient bubbles.
This is not approval to convert static warnings or statuses into temporary
toasts, nor to redesign public/auth/guest workflows. Guest copy helpers that
share the host bundle must retain semantics and their required browser checks.

Browser review is documented in [the report](host-control-review-report.md).
There are no production changes in this review.
