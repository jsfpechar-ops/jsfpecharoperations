# 2019 report — UX gate (rule 10) for briefs 2011-2018

The gate ran on `vibe/go-parity-all-d1d44c` and its evidence is archived at
[UX_GATE_2011-2018_2026-11-22](../archive/UX_GATE_2011-2018_2026-11-22.md) — 78 renders
(26 page labels × 390/768/1280), all screenshots under `/tmp`, never in the repo.

## Result

**PASS with findings:** 1 PASS, 19 PASS (findings), **5 FAIL**, 1 GAP. No 5xx except the
already-diagnosed ZIP route, no sideways scroll anywhere, light-mode-only holds, layout
lint green with 0 skipped.

## The five FAIL rows (each described, not attributed)

| brief | page | defect |
|---|---|---|
| — | `/admin` | A tab label truncates at 390 ("Sy…", rule 8); KPIs wrap mid-number; two tables render as tables below 768 (rule 10) with IDs over three lines; 27 overdue + 25 signup rows with no pagination; raw env var names in the amber banner |
| 2014 | `/apartments/{id}/booking-site` | A stray, unstyled property name renders above the app chrome at every width; the page is otherwise only the Max-plan paywall, with no preview of the site |
| 2014 | `/apartments/{id}/guide/questions` | "UbyHost" is the H1 with a coral underline instead of the property name, then a second heading; "Guest questions" is coral (rule 9); the phone tab bar reads Cleaning/More here and Today/Calendar elsewhere (rule 1); FAB overlaps the More tab |
| 2013 | `/booking-sites` | Singular "Booking site" for a list; row internals inconsistent (status/pill above the name in row one, name first later); the last row has no property name at all; 30 px "Set up" pills |
| 2015 | `/guests/{id}` | "Street and number *(optional)*" contradicts "Street and number are required"; red errors and "That signature could not be saved…" render on a clean first GET; 5 muted fine-print lines (rule 7) |

## The honest limit

No Python reference was captured: `App/scripts/go_page_parity_screenshots.py` is broken
and the gate was not permitted to patch `App/`. So the five FAIL rows are measured against
the design system and geometry only — this document cannot say whether any of them is new
in the parity work or pre-existing.

## Recommended next step

Fix `go_page_parity_screenshots.py` so the Python reference is captured in the same run,
which turns this gate from "Go pages vs the design system" into a true visual Go-vs-Python
diff. Tracked as brief 2021 onward.
