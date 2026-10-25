# 0387 report

Status: review

## Files changed
- App/app/templates/guest/_leon.html: header with avatar, visually hidden label, pill composer, send button with arrow icon, counter hidden by default.
- App/app/static/guest-leon.js: counter hidden above 450 chars, textarea auto-grow to 132 px inside updateCount (also runs after send).
- App/app/static/guest.css: one appended block; send button `min-width: 0` (an older `.g-leon-send` rule set `min-width: 120px`, which made the first render wide).
- App/app/templates/guest/base.html: guest-leon.js key `20261025-0387`, guest.css key `20261025-0387b` (see Deviations).
- App/tests/static_versions.json: regenerated with --write.
- App/tests/test_guest_leon_browser.py: counter assertion changed to is_hidden; new test_leon_chat_look_on_a_phone.
- docs/tasks/screenshots-0387/leon-chat-390.png, leon-chat-host-390.png.

## Commands (§6)
- ruff E9,F63,F7,F82,F401,F841: All checks passed!
- pytest (7 files): 75 passed, 0 skipped (last line: "75 passed in 222.58s").

## §7
- [x] §6 commands pass with 0 skipped.
- [x] Both screenshots exist and were viewed; they show the §1 look.

## Deviations
- Done: steps 1 to 5, all of them.
- guest.css key is `20261025-0387b`, not `20261025-0387`: the manifest test refuses a changed file under an unchanged key, and the key was bumped after the min-width fix.
- Commit trailer uses Co-Authored-By: Claude Haiku 5.5 (the session attribution), not the Opus line in §9.

## Questions
- None.

## Owner steps left
- Review and merge with scripts/merge-pr-on-green.sh. Do not push from this executor.
