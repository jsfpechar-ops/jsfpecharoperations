# TTLock access disclosure

Status: review (verification pending)

## Result
- The property Door lock tab, property hours and both relevant wizard steps show the one-hour margin and actual access hours.
- The preview follows unsaved hour changes, marks previous/next-day boundaries and asks for missing hours.
- The Guide puts the explanation and a concrete 15:00/11:00 example near the top.
- English, Czech and Vietnamese use one shared set of disclosure strings. The existing ui-facts component supplies layout and tokens; no new CSS.
- The host JavaScript asset version changed so browsers load the preview.

## Verification
58 server-side cases compare displayed hours and day labels against ttlock.stay_window, including both DST transitions.
The focused browser job exercises Chromium and WebKit; EN/CS/VI; 360, 390, 820, 1024, 1180 and 1280 px; all 24 hours; missing values; 200% text; no JavaScript; and disconnected locks.
Geometry checks measure containment, text clipping/overlap, page overflow, contrast and readable value sizes. Screenshots at 390 px cover every changed screen and language.
The dedicated CI job rejects skipped/failed checks and uploads screenshots plus JUnit.

The managed execution environment could not start (managed network requirements require sandbox enforcement).
No local Python, browser, geometry, design lint or context lint was run. CI results and screenshots must be reviewed before merge.
Source edits were prepared through the connected GitHub API on a feature branch. No production deployment.

## Owner review
1. Open the pull request and the door-code-access-review check.
2. Check all results pass with zero skipped, then download the screenshot artifact.
3. Review the five screens at 390 px, including the actual times and day labels.
4. Merge through scripts/merge-pr-on-green.sh only after the required checks pass; deploy manually.
