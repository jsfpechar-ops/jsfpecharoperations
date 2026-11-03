"""0884 section A: baseline measurement of the setup wizard (steps, fields, POSTs).

Measurement only: prints the numbers, asserts nothing about the target.
Run: .venv/bin/python -m pytest tests/wizard_taps.py -q -s --tb=short -x 2>&1 | tail -30
"""
from __future__ import annotations

import json
from html.parser import HTMLParser

from app import property_setup
from tests.test_onboarding_wizard_survival import _full_apartment, host  # noqa: F401
from tests.wizard_walk import walk_to

_TEXT_TYPES = ("text", "email", "tel", "number", "date", "time", "url", "search", "")
_SKIP_TYPES = ("hidden", "submit", "button", "reset", "image")


# 0884: measured on the eight-step wizard before the change (brief step 1).
BEFORE = {"steps_defined": 8, "steps_visited": 5, "posts": 5, "fields_total": 32, "required_or_empty_total": 32}


class _FieldCounter(HTMLParser):
    """Counts form controls on one step page."""

    def __init__(self) -> None:
        super().__init__()
        self.controls = 0
        self.required_or_empty = 0
        self.choices = 0

    def handle_starttag(self, tag, attrs):
        if tag not in ("input", "select", "textarea"):
            return
        data = {key: (value or "") for key, value in attrs}
        kind = data.get("type", "").lower() if tag == "input" else tag
        if tag == "input" and kind in _SKIP_TYPES:
            return
        self.controls += 1
        if kind in ("radio", "checkbox"):
            self.choices += 1
            if "required" in data:
                self.required_or_empty += 1
            return
        empty = tag != "select" and kind in _TEXT_TYPES and not data.get("value", "").strip()
        if "required" in data or empty:
            self.required_or_empty += 1


class _CountingClient:
    """Wraps the test client and counts POSTs made by the walk."""

    def __init__(self, client) -> None:
        self._client = client
        self.posts = 0
        self.trace: list[str] = []

    def get(self, url, **kwargs):
        return self._client.get(url, **kwargs)

    def post(self, url, **kwargs):
        self.posts += 1
        data = kwargs.get("data") or {}
        self.trace.append(str(data.get("step") or url.rsplit("/", 1)[-1]))
        return self._client.post(url, **kwargs)


def _measure_page(client, apartment_id: int, step: str) -> dict:
    response = client.get(f"/apartments/{apartment_id}/setup/{step}?lang=en")
    if response.status_code != 200:
        return {"status": response.status_code, "controls": 0, "required_or_empty": 0, "choices": 0}
    counter = _FieldCounter()
    # Only the wizard body; the app shell's own controls are not wizard work.
    body = response.text.split("data-setup-wizard", 1)[-1].split('class="setup-wizard-foot"', 1)[0]
    counter.feed(body)
    return {
        "status": 200,
        "controls": counter.controls,
        "required_or_empty": counter.required_or_empty,
        "choices": counter.choices,
    }


def test_wizard_baseline_numbers(host):  # noqa: F811
    apartment = _full_apartment(host)
    apartment_id = apartment["id"]
    client = _CountingClient(host["client"])

    pages = {step: _measure_page(client, apartment_id, step) for step in property_setup.STEPS}

    # The walk: the existing helper answers each step with the cheapest answer.
    walk_to(client, apartment_id, "done")
    visited = list(dict.fromkeys(client.trace))

    report = {
        "steps_defined": len(property_setup.STEPS),
        "steps_visited": len(visited),
        "visited": visited,
        "posts": client.posts,
        "fields_total": sum(page["controls"] for page in pages.values()),
        "required_or_empty_total": sum(page["required_or_empty"] for page in pages.values()),
        "choice_taps_total": sum(page["choices"] for page in pages.values()),
        "pages": pages,
    }
    print("WIZARD_TAPS " + json.dumps(report, sort_keys=True))
    assert report["steps_defined"] == len(property_setup.STEPS)
    assert visited, "the wizard walk visited no step"
