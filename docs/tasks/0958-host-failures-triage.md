# 0958 host failures triage (+ fix)

Branch fix: `cursor/0958-host-test-stale-fixes-5056` off main.

## Outcomes on current main
| Test | Call | Fix |
|------|------|-----|
| fee frozen “Your records” | was stale on 0958 (pre-`7b1eff2c`); **passes on main** | none |
| property setting `door_codes` | already fixed on main | none |
| keyboard → `#door_codes` | already uses `lock_id` on main | none |
| rail cards Back → `#sec-basics` | **stale/brittle test** (Turbo race) | wait for `details#sec-basics` attached after `go_back` |

Evidence for Back: URL matched before DOM swap; `document.getElementById('sec-basics')` was null until wait; host page then renders correctly.
