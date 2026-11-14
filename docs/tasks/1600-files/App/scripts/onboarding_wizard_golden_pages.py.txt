"""Write go/internal/web/onboarding/testdata/wizard_golden_pages.json (brief 1600).

Run from App/: .venv/bin/python scripts/onboarding_wizard_golden_pages.py

Part "pages" of the setup wizard goldens: GET of the police and property
steps. The seed, the pins and the recorder are in onboarding_wizard_golden.py.
"""

from __future__ import annotations

from onboarding_wizard_golden import TESTDATA, case, cli, render  # noqa: F401 (render: the parity test)

OUT = TESTDATA / "wizard_golden_pages.json"

CASES = [
    # police: the guide's step, nothing filled, no password stored
    case("police_current", "GET", "/apartments/23/setup/police"),
    case("police_filled", "GET", "/apartments/11/setup/police"),
    case("police_scheduled_waiting", "GET", "/apartments/17/setup/police"),
    case("police_immediate_cs", "GET", "/apartments/19/setup/police", lang="cs"),
    case("police_scheduled_vi", "GET", "/apartments/22/setup/police", lang="vi"),
    case("police_ahead_of_guide", "GET", "/apartments/12/setup/police"),
    case("police_signed_out", "GET", "/apartments/23/setup/police", user=None),
    # property: legacy guide, two operators and none chosen, default hours
    case("property_new", "GET", "/apartments/12/setup/property"),
    case("property_operator_chosen", "GET", "/apartments/24/setup/property"),
    case("property_done_back", "GET", "/apartments/11/setup/property"),
    case("property_finished", "GET", "/apartments/13/setup/property"),
    case("property_escaped_cs", "GET", "/apartments/19/setup/property", lang="cs"),
    case("property_one_operator_edges", "GET", "/apartments/26/setup/property", user=2),
    case("property_no_operator_vi", "GET", "/apartments/25/setup/property", user=3, lang="vi"),
    case("property_foreign", "GET", "/apartments/25/setup/property"),
]

if __name__ == "__main__":
    cli(OUT, CASES)
