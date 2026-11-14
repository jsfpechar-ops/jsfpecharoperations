"""Write go/internal/web/onboarding/testdata/wizard_golden_finish.json (brief 1601).

Run from App/: .venv/bin/python scripts/onboarding_wizard_golden_finish.py

Part "finish" of the setup wizard goldens: GET of the finish page (done) and
of the try-it page. The seed, the pins and the recorder are in
onboarding_wizard_golden.py. The order matters: the first finish page of a
property records the celebration, so the second one shows no confetti.
"""

from __future__ import annotations

from onboarding_wizard_golden import TESTDATA, case, cli, render  # noqa: F401 (render: the parity test)

OUT = TESTDATA / "wizard_golden_finish.json"

CASES = [
    # done: tested, report complete, a stay in June: the ready card, confetti once
    case("done_ready_celebrate", "GET", "/apartments/19/setup/done"),
    case("done_ready_again_cs", "GET", "/apartments/19/setup/done", lang="cs"),
    # finished, not tested: the banner, no calendar
    case("done_all_set", "GET", "/apartments/13/setup/done"),
    # police waiting: the partial banner and the fix button
    case("done_police_waiting", "GET", "/apartments/17/setup/done"),
    # guide still open on the guest link step
    case("done_guide_open_vi", "GET", "/apartments/11/setup/done", lang="vi"),
    # tested and celebrated, demo stay registered
    case("done_ready_celebrated", "GET", "/apartments/22/setup/done"),
    # legacy state, nothing set up
    case("done_legacy", "GET", "/apartments/12/setup/done"),
    case("done_signed_out", "GET", "/apartments/19/setup/done", user=None),
    case("done_foreign", "GET", "/apartments/21/setup/done"),
    # try_it: no demo stay, an open one, a registered one (scheduled 12 h), immediate mode
    case("try_none", "GET", "/apartments/11/setup/try_it"),
    case("try_open", "GET", "/apartments/20/setup/try_it"),
    case("try_open_vi", "GET", "/apartments/20/setup/try_it", lang="vi"),
    case("try_registered", "GET", "/apartments/22/setup/try_it"),
    case("try_registered_cs", "GET", "/apartments/22/setup/try_it", lang="cs"),
    case("try_immediate_company", "GET", "/apartments/19/setup/try_it"),
    case("try_legacy", "GET", "/apartments/12/setup/try_it"),
    case("try_foreign", "GET", "/apartments/21/setup/try_it"),
]

if __name__ == "__main__":
    cli(OUT, CASES)
