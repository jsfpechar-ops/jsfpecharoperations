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
