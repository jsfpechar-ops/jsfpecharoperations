"""0273: friendlier setup wizard (question titles, icon tiles, done count)."""
from __future__ import annotations

import re
from pathlib import Path

from app import host_i18n, property_setup
from tests.test_onboarding_wizard_survival import _full_apartment, host  # noqa: F401

APP_DIR = Path(__file__).resolve().parents[1] / "app"


def test_question_title_and_icon_on_every_step(host):
    flat = _full_apartment(host)
    apt_id = flat["id"]
    client = host["client"]
    for lang in ("en", "cs", "vi"):
        response = client.get(f"/apartments/{apt_id}/setup/calendar?lang={lang}")
        assert response.status_code == 200
        text = response.text
        assert 'class="setup-wizard-question"' in text
        assert host_i18n.translate(lang, "wizard.question.calendar") in text
        assert 'data-step-tone="teal"' in text


def test_done_count_words_and_tick(host, monkeypatch):
    flat = _full_apartment(host)
    apt_id = flat["id"]
    client = host["client"]
    base = f"/apartments/{apt_id}/setup"
    pattern = re.compile(r"(\d+) of 8 done")

    # A complete apartment already counts some steps: the words and the tick show it.
    shown = client.get(f"{base}/calendar?lang=en")
    assert shown.status_code == 200
    match = pattern.search(shown.text)
    assert match and int(match.group(1)) > 0
    assert "setup-wizard-tick" in shown.text

    # Zero done: no tick is shown.
    monkeypatch.setattr(property_setup, "done_count", lambda *args, **kwargs: 0)
    zero = client.get(f"{base}/calendar?lang=en")
    assert zero.status_code == 200
    assert "0 of 8 done" in zero.text
    assert "setup-wizard-tick" not in zero.text
    monkeypatch.undo()

    # A skip is counted on the next step page.
    client.post(base, data={"step": "calendar", "action": "skip"}, follow_redirects=False)
    after = client.get(f"{base}/police?lang=en")
    assert after.status_code == 200
    assert pattern.search(after.text) is not None
    assert "setup-wizard-tick" in after.text


def test_every_question_key_in_three_languages():
    for step in property_setup.STEPS:
        key = "wizard.question." + step
        for lang in ("en", "cs", "vi"):
            assert host_i18n.translate(lang, key) != key, (lang, key)


def test_wizard_css_reduced_motion_and_no_coral_icons():
    css = (APP_DIR / "static" / "wizard.css").read_text(encoding="utf-8")
    assert "prefers-reduced-motion" in css
    for line in css.splitlines():
        if "setup-wizard-ask" in line:
            assert "--brand" not in line, line
