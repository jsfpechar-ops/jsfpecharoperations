"""0321: the eval case file stays valid (no API call)."""
import json
from pathlib import Path

from app import havel

CASES = json.loads((Path(__file__).parent / "havel_cases.json").read_text(encoding="utf-8"))
SPEC_KEYS = {"kind", "links_any", "action", "no_action", "not_contains", "contains_any", "sources_any",
             "lang", "steps", "support_summary", "next", "next_max", "next_contains_any"}


def test_the_75_cases_are_numbered_and_well_formed():
    cases = CASES["cases"]
    assert [c["id"] for c in cases] == list(range(1, 76))
    for case in cases:
        assert case["message"].strip(), case["id"]
        if case.get("unit") or case.get("local"):
            continue
        assert case.get("must"), case["id"]
        for part in ("must", "should"):
            spec = case.get(part, {})
            assert set(spec) <= SPEC_KEYS, (case["id"], set(spec) - SPEC_KEYS)
            assert set(spec.get("kind", [])) <= set(havel.KINDS), case["id"]
            assert set(spec.get("links_any", [])) <= set(havel.PAGES), (case["id"], spec.get("links_any"))
            if "action" in spec:
                assert spec["action"]["type"] in havel.ACTIONS, case["id"]


def test_the_local_case_is_answered_without_a_call():
    local = [c for c in CASES["cases"] if c.get("local")]
    assert local and all(havel.local_reply(c["message"]) for c in local)


def test_unit_cases_name_a_test_file_that_exists():
    root = Path(__file__).resolve().parents[1]
    for case in CASES["cases"]:
        if case.get("unit"):
            assert (root / case["unit"]).exists(), case["id"]
