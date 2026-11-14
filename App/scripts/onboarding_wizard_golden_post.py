"""Write go/internal/web/onboarding/testdata/wizard_golden_post.json (brief 1602).

Run from App/: .venv/bin/python scripts/onboarding_wizard_golden_post.py

Part "post" of the setup wizard goldens: POST /apartments/{id}/setup. The
seed, the pins and the recorder are in onboarding_wizard_golden.py. The cases
run in order on one database, so a later case sees what an earlier one
wrote; the final rows (setup states, audit lines, demo stays, timing) are
compared too. Not here: "skip" on the try-it page while a demo stay exists
(it deletes the stay and its photo files in Python; Go answers 501, brief
1603).
"""

from __future__ import annotations

from onboarding_wizard_golden import TESTDATA, case, cli, render  # noqa: F401 (render: the parity test)

OUT = TESTDATA / "wizard_golden_post.json"


def post(name, path, form, **kw):
    return case(name, "POST", path, form=form, csrf=kw.pop("csrf", True), **kw)


POLICE = {"setup_step": "police", "step": "police", "action": "wait", "internal_name": "My",
          "legal_entity_id": "31", "uby_idub": " 123456789012 ", "uby_mark": "aakli", "uby_name": "BYT <1>",
          "uby_contact": "", "uby_ws_user": "UBY-WS_X"}

CASES = [
    # the guards: CSRF first, then the id, then the login, then the property
    post("no_csrf", "/apartments/11/setup", {"step": "calendar", "action": "skip"}, csrf=False),
    post("bad_id", "/apartments/abc/setup", {"step": "calendar", "action": "skip"}),
    post("signed_out", "/apartments/11/setup", {"step": "calendar", "action": "skip"}, user=None),
    post("foreign", "/apartments/21/setup", {"action": "hide"}),
    post("missing", "/apartments/999/setup", {"action": "hide"}),
    # hide and show (the exit button, the property page's resume link)
    post("hide", "/apartments/23/setup", {"action": "hide"}),
    post("show", "/apartments/23/setup", {"action": "show"}),
    post("show_not_hidden", "/apartments/11/setup", {"action": "show"}),
    post("show_hidden_cs", "/apartments/14/setup", {"action": "show"}, lang="cs"),
    # not the guide's step, or an action the step does not take
    post("wrong_step", "/apartments/11/setup", {"step": "police", "action": "wait"}),
    post("no_guide", "/apartments/13/setup", {"step": "", "action": ""}),
    post("property_not_skippable", "/apartments/24/setup", {"step": "property", "action": "skip"}),
    post("retired_none", "/apartments/14/setup", {"step": "door_lock", "action": "none"}),
    post("calendar_done_refused", "/apartments/14/setup", {"step": "calendar", "action": "done"}),
    # the guide's step
    post("calendar_skip", "/apartments/14/setup", {"step": "calendar", "action": "skip"}),
    post("police_wait_bad_hours", "/apartments/23/setup",
         {**POLICE, "automation_mode": "scheduled", "submit_after_hours": "0"}),
    post("police_wait_bad_mode_vi", "/apartments/23/setup",
         {**POLICE, "automation_mode": "sometimes", "submit_after_hours": "5"}, lang="vi"),
    post("police_wait_bad_no_setup_step", "/apartments/23/setup",
         {"step": "police", "action": "wait", "automation_mode": "", "submit_after_hours": ""}),
    post("police_wait_timing", "/apartments/23/setup",
         {**POLICE, "automation_mode": "immediate", "submit_after_hours": "100"}),
    post("police_wait_plain", "/apartments/27/setup", {"step": "police", "action": "wait"}),
    post("guest_link_done_finishes", "/apartments/11/setup", {"step": "guest_link", "action": "done"}),
    post("guest_link_done_again", "/apartments/11/setup", {"step": "guest_link", "action": "done"}),
    # the try-it page
    post("try_demo", "/apartments/11/setup", {"step": "try_it", "action": "demo"}),
    post("try_demo_again", "/apartments/11/setup", {"step": "try_it", "action": "demo"}),
    post("try_demo_existing_cs", "/apartments/20/setup", {"step": "try_it", "action": "demo"}, lang="cs"),
    post("try_demo_no_token", "/apartments/24/setup", {"step": "try_it", "action": "demo"}),
    post("try_keep", "/apartments/22/setup", {"step": "try_it", "action": "keep_demo"}),
    post("try_skip_no_stay", "/apartments/13/setup", {"step": "try_it", "action": "skip"}),
    post("try_other", "/apartments/13/setup", {"step": "try_it", "action": "x"}),
]

if __name__ == "__main__":
    cli(OUT, CASES)
