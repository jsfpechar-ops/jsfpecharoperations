"""0500: same-origin prefetch rules, rendered only in the signed-in host shell."""
from __future__ import annotations

import json
import re

from fastapi.testclient import TestClient

from app.main import app
from tests.test_signed_in_chrome import host_with_property  # noqa: F401  (fixture reuse)

RULES = re.compile(r'<script type="speculationrules">(.*?)</script>', re.S)
EXCLUSIONS = ("[data-no-prefetch]", "[target=_blank]", "[download]", "/logout*", "/lang*",
              "/api/*", "/admin/*", "/*export*", "/*.pdf*", "/*/pdf*", "/*.zip*")


def test_signed_in_shell_renders_prefetch_rules_with_exclusions(host_with_property):
    page = host_with_property.get("/?lang=en").text
    match = RULES.search(page)
    assert match, "speculation rules block missing from the signed-in shell"
    rule = json.loads(match.group(1))["prefetch"][0]
    assert rule["eagerness"] == "moderate"
    where = json.dumps(rule["where"])
    assert '"href_matches": "/*"' in where
    for pattern in EXCLUSIONS:
        assert pattern in where, pattern


def test_login_page_has_no_prefetch_rules():
    page = TestClient(app).get("/login?lang=en").text
    assert "speculationrules" not in page
