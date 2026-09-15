"""Destructive host actions live inside ⋮ row menus on a phone.

A mis-tap there can pull a guest out of the house book export or kill a guest
link that is already sitting in a check-in message. This walks the templates
rather than naming the buttons, so a new destructive action cannot ship
without a confirmation step.
"""
from __future__ import annotations

import re
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parent.parent / "app" / "templates"

# Verbs that either destroy data or invalidate something a guest already has.
DESTRUCTIVE = (
    "archive",
    "delete",
    "purge",
    "regenerate",
    "remove",
    "clear-demo",
    "disconnect",
)

FORM_TAG = re.compile(r"<form\b[^>]*>", re.IGNORECASE | re.DOTALL)


def _host_templates() -> list[Path]:
    # The guest form has no destructive actions and no confirm dialog to use.
    return [
        path
        for path in sorted(TEMPLATES.rglob("*.html"))
        if "guest" not in path.relative_to(TEMPLATES).parts
    ]


def _destructive_forms() -> list[tuple[Path, str]]:
    found = []
    for path in _host_templates():
        text = path.read_text()
        for tag in FORM_TAG.findall(text):
            if 'method="post"' not in tag.lower():
                continue
            action = re.search(r'action="([^"]*)"', tag)
            if not action:
                continue
            target = action.group(1).lower()
            # "unarchive" restores; it is the undo, not the damage.
            if "unarchive" in target:
                continue
            # Stay archives return an undo toast. They are deliberately
            # reversible and should not interrupt triage with a modal.
            if "/reservations/" in target and target.endswith("/archive"):
                continue
            if any(verb in target for verb in DESTRUCTIVE):
                found.append((path, tag))
    return found


def test_the_sweep_actually_finds_the_destructive_actions():
    """Guard the guard: a broken scan would make every assertion below vacuous."""
    forms = _destructive_forms()
    assert len(forms) >= 6, f"only found {len(forms)} destructive forms, scan is broken"
    actions = " ".join(tag for _, tag in forms)
    assert "/archive" in actions
    assert "regenerate" in actions


def test_every_destructive_action_asks_first():
    missing = [
        f"{path.relative_to(TEMPLATES)}: {tag.strip()[:110]}"
        for path, tag in _destructive_forms()
        if "data-confirm" not in tag
    ]
    assert not missing, "destructive actions with no confirmation step:\n" + "\n".join(missing)


def test_every_confirmation_carries_a_message():
    """An empty dialog tells the host nothing about what they are about to lose."""
    silent = [
        f"{path.relative_to(TEMPLATES)}: {tag.strip()[:110]}"
        for path, tag in _destructive_forms()
        if "data-confirm" in tag
        and not re.search(r'data-confirm-message="[^"]+"', tag)
    ]
    assert not silent, "confirmations with no message:\n" + "\n".join(silent)
