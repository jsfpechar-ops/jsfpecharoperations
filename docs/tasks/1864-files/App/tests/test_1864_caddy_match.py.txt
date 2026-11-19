"""1864: the Caddy path matcher shared by the parity check and the browser stack.

scripts/caddy_match_cases.json is also checked against Caddy's own rule by
go/cmd/ubyhost-web/caddy_match_cases_test.go, so a pass here means the Python
matcher agrees with Caddy on every row.
"""
from __future__ import annotations

import json

import pytest

from tests import go_stack

CASES = json.loads(
    (go_stack.REPO_ROOT / "scripts" / "caddy_match_cases.json").read_text(encoding="utf-8")
)
STAY_SELECTOR = "/reservations/*[0-9]"


@pytest.mark.parametrize("entry,path,want", CASES)
def test_caddy_match(entry, path, want):
    assert go_stack.caddy_match(entry, path) is want


def test_stay_selector_catches_only_the_stay_page():
    routes = go_stack._parity_check().py_routes.routes()
    caught = sorted(
        f"{method} {path}"
        for method, path in routes
        if go_stack.caddy_match(STAY_SELECTOR, go_stack.PARAM.sub("1", path))
    )
    assert caught == [
        "GET /reservations/{reservation_id}",
        "POST /reservations/{reservation_id}",
    ]


def test_percent_escapes_are_refused():
    with pytest.raises(ValueError):
        go_stack.caddy_match("/a%20b", "/a b")
