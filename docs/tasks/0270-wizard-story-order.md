# 0270: Wizard steps in story order, test run last (C, part 1)

Status: todo
Depends on: none | Base commit: 48c21b3 | Branch: claude/project-thread-4b2e7k (commit here, do not push)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Reorder the setup wizard so hosts answer the setup questions first and finish with the guest link and a test run: property, calendar, police login, when to report, stay fee, door lock, guest link, test run. Today the demo runs before the police option is chosen, so it can never show the end of the story.

## 2. Context

- The order lives only in `STEPS` in `App/app/property_setup.py`. Stored state is keyed by step name, so old stored state stays valid. Navigation (`next_step`, `prev_step`, `current`, `may_view_step`) all read `STEPS`.
- A step can be answered only while it is the current guide step, so tests that post steps must post them in the new order.
- This brief changes the code and the test-client tests only (no Playwright). Brief 0271 fixes the Playwright click-throughs. Playwright tests in `tests/test_onboarding_wizard_browser.py` will still fail after this brief; that is expected. Do not run them.

Excerpt `App/app/property_setup.py` lines 14-23:

```
STEPS = (
    "property",
    "calendar",
    "guest_link",
    "try_it",
    "police",
    "stay_fee",
    "door_lock",
    "automation",
)
```

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/property_setup.py | edit | new order + comment |
| App/tests/wizard_walk.py | create | test helper that answers steps in order |
| App/tests/test_onboarding_wizard_survival.py | edit | 3 tests follow the new order |
| App/tests/test_onboarding_wizard_browser.py | edit | 9 test-client tests (no Playwright) follow the new order |

No other file may change.

## 4. Steps

**Step 1.** Replace the excerpt with:

```
# 0270: story order (idea C). Setup questions first, then the guest link, and
# the test run last, so the demo can show the whole workflow.
STEPS = (
    "property",
    "calendar",
    "police",
    "automation",
    "stay_fee",
    "door_lock",
    "guest_link",
    "try_it",
)
```

**Step 2.** Create `App/tests/wizard_walk.py`:

```python
"""0270: answer setup wizard steps in their order until a target step is current."""
from __future__ import annotations

from urllib.parse import urlparse

from app import property_setup

_ACTIONS = {
    "calendar": "skip",
    "police": "wait",
    "stay_fee": "skip",
    "door_lock": "none",
    "guest_link": "done",
    "try_it": "skip",
}


def current_step(client, apartment_id: int) -> str:
    """The step the wizard entry sends the host to ('' when it leaves the wizard)."""
    entry = client.get(f"/apartments/{apartment_id}/setup", follow_redirects=False)
    path = urlparse(entry.headers.get("location", "")).path
    step = path.rsplit("/", 1)[-1]
    return step if "/setup/" in path and (step in property_setup.STEPS or step == "done") else ""


def walk_to(client, apartment_id: int, target: str) -> str:
    """Answer each step (police: wait, automation: manual) until ``target`` is current.

    ``target`` may be a step name or "done". Returns the step it stopped on.
    """
    base = f"/apartments/{apartment_id}/setup"
    for _ in range(len(property_setup.STEPS) + 1):
        step = current_step(client, apartment_id)
        if step == target or step in ("", "done") or step == "property":
            return step
        if step == "automation":
            response = client.post(
                f"/apartments/{apartment_id}/automation-timing",
                data={
                    "automation_mode": "manual",
                    "submit_after_hours": "24",
                    "setup_step": "automation",
                    "return_to": property_setup.wizard_url(
                        apartment_id, property_setup.next_step("automation") or "done"
                    ),
                },
                follow_redirects=False,
            )
        else:
            response = client.post(
                base, data={"step": step, "action": _ACTIONS[step]}, follow_redirects=False
            )
        assert response.status_code == 303, (step, response.status_code)
    return current_step(client, apartment_id)
```

Note: after the last step the entry may redirect to the overview (`/apartments/<id>?view=overview`), which `current_step` returns as `''`. Commit.

**Step 3.** `tests/test_onboarding_wizard_survival.py`. Add `from tests.wizard_walk import walk_to` next to the other imports (check how the file imports `app`; if `tests.` imports fail, use `from wizard_walk import walk_to` and confirm with a run).

a) `test_try_it_skip_deletes_demo_stay`: replace the two lines

```
    client.post(base, data={"step": "calendar", "action": "skip"}, follow_redirects=False)
    client.post(base, data={"step": "guest_link", "action": "done"}, follow_redirects=False)
```

with `    assert walk_to(client, apt_id, "try_it") == "try_it"`.

b) `test_demo_action_teaches_pin_then_opens_the_guest_form_and_reuses_its_stay`: the same replacement.

c) `test_finish_setup_with_police_credentials_deferred`: replace from the line `    actions = [("calendar", "skip"), ("guest_link", "done"), ("try_it", "skip")]` down to and including the line `    assert property_setup.load(apt_id)["finished"] is defer_police` with:

```
    actions = [("calendar", "skip")]
    if defer_police:
        actions.append(("police", "wait"))
    for step, action in actions:
        response = client.post(base, data={"step": step, "action": action}, follow_redirects=False)
        assert response.status_code == 303
    saved = client.post(
        f"/apartments/{apt_id}/automation-timing",
        data={
            "automation_mode": mode,
            "submit_after_hours": "24",
            "setup_step": "automation",
            "return_to": f"{base}/stay_fee",
        },
        follow_redirects=False,
    )
    assert saved.status_code == 303
    target = urlparse(saved.headers["location"]).path
    assert target == f"{base}/{'stay_fee' if defer_police else 'police'}"
    assert property_setup.load(apt_id)["finished"] is False
    if defer_police:
        assert walk_to(client, apt_id, "done") in ("done", "")
        assert property_setup.load(apt_id)["finished"] is True
```

Keep the lines after it unchanged. Read the 20 lines after it once; if one of them posts a step by name, apply the new order there too and say so under Deviations.

Run: `.venv/bin/python -m pytest tests/test_onboarding_wizard_survival.py -q --tb=short 2>&1 | tail -30`. All must pass. Commit.

**Step 4.** `tests/test_onboarding_wizard_browser.py`, test-client tests only. Add the same `walk_to` import. `_create(host)` makes a property WITHOUT a police login, so `walk_to` answers police with "wait". Edits:

a) `test_back_from_later_step_reaches_earlier_page`: replace its body after `base = …` with:

```
    assert walk_to(client, flat["id"], "guest_link") == "guest_link"
    at_link = client.get(f"{base}/guest_link?lang=en")
    assert at_link.status_code == 200
    back = client.get(f"{base}/automation?lang=en", follow_redirects=False)
    assert back.status_code == 200
    assert 'data-setup-step="automation"' in back.text
```

b) `test_police_waiting_can_finish_setup_via_automation`: replace the six `client.post(base, …)` lines and the automation save so the flow is: post calendar skip; post police wait; POST automation-timing with `"return_to": f"/apartments/{flat['id']}/setup/stay_fee"`; assert the redirect path ends with `/setup/stay_fee`; then `walk_to(client, flat["id"], "done")`. Keep the final assertions (`state["finished"]`, police `waiting`), and delete the now-wrong assertion `assert path.endswith("/setup/done")`.

c) `test_done_count_includes_skipped_door_lock_when_unavailable`: replace the `for step, action in (…): client.post(…)` loop with `    walk_to(client, flat["id"], "try_it")`. Keep `assert "6 of 8" in overview` (property, calendar, automation, stay fee, door lock not available, guest link).

d) `test_back_skips_steps_that_do_not_apply`: docstring becomes `"""Back from the guest link skips door_lock when the property has no lock."""`; replace the loop with `    walk_to(client, flat["id"], "guest_link")` and the page GET with `client.get(f"{base}/guest_link?lang=en")`. Keep both href assertions (stay_fee present, door_lock absent).

e) `test_try_it_open_skip_moves_on`: replace the calendar and guest_link posts with `    walk_to(client, flat["id"], "try_it")`; change the last assertion to `assert "/setup/done" in skipped.headers["location"]` (the test run is the last step).

f) `test_finished_applicable_steps_without_a_lock_are_not_seven_of_eight`: new flow: `client.post(base, data={"step": "calendar", "action": "skip"}, follow_redirects=False)`; the police POST unchanged except `"return_to": f"{base}/automation"` and its assertion `assert "/setup/automation" in police.headers["location"]`; delete the stay_fee skip line; the automation POST gets `"return_to": f"{base}/stay_fee"` and `assert "/setup/stay_fee" in done.headers["location"]` instead of the `/setup/done` assertion; then `walk_to(client, flat["id"], "done")` before `assert property_setup.load(flat["id"])["finished"] is True`.

g) `test_waiting_hide_show_and_demo_exclusion`: keep the first loop ("A step that is not on screen cannot be answered"). Replace the calendar skip and guest_link done posts with `    assert walk_to(client, flat["id"], "try_it") == "try_it"`. Delete these four lines (police is already waiting, and skipping the test run would finish setup):

```
    skipped = client.post(setup, data={"step": "try_it", "action": "skip"}, follow_redirects=False)
    assert "/setup/police" in skipped.headers["location"]
    waited = client.post(setup, data={"step": "police", "action": "wait"}, follow_redirects=False)
    assert "/setup/stay_fee" in waited.headers["location"]
```

Keep `assert property_setup.load(flat["id"])["steps"]["police"] == "waiting"` and everything after.

h) `test_no_js_calendar_skip`: `assert "/setup/guest_link" in …` becomes `assert "/setup/police" in skipped.headers["location"]`.

i) `test_phone_guest_sharing_and_clear_setup_actions` (Playwright, but only this line): replace

```
        host["client"].post(
            f"/apartments/{flat['id']}/setup", data={"step": "calendar", "action": "skip"},
            follow_redirects=False,
        )
```

with `        walk_to(host["client"], flat["id"], "guest_link")`.

Run: `.venv/bin/python -m pytest tests/test_onboarding_wizard_browser.py -q --tb=short -k "back_from_later or police_waiting_can_finish or done_count_includes or back_skips or try_it_open_skip or finished_applicable or waiting_hide_show or no_js_calendar_skip or guests_registered or legacy_unfinished or create_lands" 2>&1 | tail -30`. All must pass. Commit.

## 5. Do not touch

Routes, templates, i18n, other tests. Do not edit Playwright click-throughs (0271 does). Never push. Do not delete or skip a test, and do not weaken an assertion beyond the replacements written here.

## 6. Commands

From `App/`:

- `.venv/bin/python -m pytest tests/test_onboarding_wizard_survival.py tests/test_onboarding.py tests/test_property_readiness.py tests/test_lock_question_0234.py tests/test_fee_setup_compatibility.py tests/test_demo_stay_exclusion.py tests/test_property_health_0244.py -q --tb=short 2>&1 | tail -30`
- the `-k` run in step 4.

## 7. Acceptance

- [ ] `STEPS` is in the new order.
- [ ] Both command lines pass.
- [ ] No test deleted or skipped.

## 8. Stop and ask

Per TEMPLATE. Also stop if a test outside the ones named fails in the first command: report its name and last 15 lines; do not edit it.

## 9. Report

`docs/tasks/0270-report.md` (600 tokens max), `Status: review`, commits `0270 step k`. Do not push.
