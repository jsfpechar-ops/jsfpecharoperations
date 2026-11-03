# 0840 report: stay row copy icon

Status: blocked

## Files changed

None kept. `App/app/templates/reservations.html` was edited (step 2) and then reverted with the exact inverse edit. `git diff` on that file is empty. No commit was made.

## Stopped at

Step 1 passed: the copy handler in `App/static/app.js` (lines 320-410) keeps the icon. It wraps only text nodes, and an SVG icon is an element, so it is left in place.

Step 2 applied the brief's line after `row-actions` `<td>` (line 234). The anchor was found.

Step 3 (test) and step 4 (commands) were not run.

## Why blocked (brief premise is wrong)

The icon sits in the table row `tr.clickable-row` inside `div.card.stays-desk`. On phones that container is hidden: `App/app/static/app2.css` line 474 sets `.stays-desk{display:none}` and line 475 sets `.stays-phone{display:block}`. The phone view is the `div.stays-phone` card list (`reservations.html` line 154). Its cards are plain links to the stay page (line 171). The row-menu copy action is on the stay page, as `tests/test_host_stay_actions_browser.py` already notes.

So the icon is never visible or tappable at 390 px, and the objective ("On a phone, one tap on the row icon") is not met. The phone cards in `reservations.html` (lines 154-187) would need the icon, and that is outside the brief's §2 and §3. This needs a new brief from the orchestrator.

## Commands

Not run. Step 2 had no command of its own.

## Deviations

- Commit denied by the permission classifier (`[Unrequested Commit in a Connected App]`). The brief asks for commits, but the orchestrator's instructions say not to commit, so none was attempted again.
- Done: steps 1 and 2 (edit then revert). Left: steps 3 and 4, plus the phone placement decision above.

## Questions

1. Should the icon go on the phone card (`div.stays-phone`, `reservations.html` lines 154-187) instead? That would need a new brief and a decision on the card markup.
2. Or should the stay-page copy action be the only phone path, with this task dropped?

## Owner steps left

None until the orchestrator answers the questions above.
