"""The landing demo reel plays once and then gets out of the way.

It used to loop forever: `(active + 1) % scenes.length` every 3,000ms, with
scene crossfades of 400–500ms and bouncy overshoot beziers on the keyframes.
DESIGN.md forbids looping motion, and the reel sits directly under the hero's
primary call to action, so the two were competing. Now it runs the four scenes
a single time, rests on the fourth, and offers Replay.
"""
from __future__ import annotations

import re
from pathlib import Path

from starlette.testclient import TestClient

from app import db
from app.landing_i18n import LANDING_STRINGS
from app.main import app

STATIC = Path(__file__).resolve().parents[1] / "app" / "static"
JS = (STATIC / "landing.js").read_text(encoding="utf-8")
CSS = (STATIC / "landing.css").read_text(encoding="utf-8")

# The audit's motion budget for the reel: 240ms, except the signature stroke,
# which stays ≤600ms because drawing the signature is the thing being shown.
CAP_MS = 240
SIGN_CAP_MS = 600


def _client() -> TestClient:
    db.init_db()
    return TestClient(app)


def _animation(name: str) -> str:
    """The `animation` shorthand that runs `@keyframes <name>`."""
    found = re.search(rf"animation: {name} ([^;]+);", CSS)
    assert found, f"no animation runs {name}"
    return found.group(1)


def _duration_ms(shorthand: str) -> int:
    found = re.match(r"(\d+(?:\.\d+)?)(ms|s)\b", shorthand)
    assert found, f"no duration at the front of {shorthand!r}"
    value = float(found.group(1))
    return int(value * 1000) if found.group(2) == "s" else int(value)


def test_the_reel_advances_once_instead_of_looping():
    assert "% scenes.length" not in JS, "the reel still wraps around to scene 1"
    assert "setInterval" not in JS, "an interval can only ever run forever"
    assert "clearTimeout" in JS
    assert "is-done" in JS, "nothing marks the reel as finished"


def test_the_finished_reel_offers_replay_not_play():
    assert 'toggle.dataset.replay' in JS
    assert "replay()" in JS
    assert 'mode === "done"' in JS


def test_the_finished_reel_rests_on_the_last_scene():
    # Reduced motion and the end of the run land in the same place.
    assert 'let active = reducedMotion.matches ? last : 0;' in JS
    assert "active = last;" in JS


def test_every_scene_animation_fits_the_motion_budget():
    for name in ("booking-drop", "type-reveal", "ready-flip", "receipt-pop", "toast-in"):
        assert _duration_ms(_animation(name)) <= CAP_MS, name
    assert _duration_ms(_animation("sign")) <= SIGN_CAP_MS


def test_no_scene_animation_overshoots():
    assert "cubic-bezier(.2, 1.4" not in CSS
    assert "cubic-bezier(.2, 1.35" not in CSS
    assert "cubic-bezier(.2, 1.3" not in CSS
    for name in ("booking-drop", "sign", "ready-flip", "receipt-pop", "toast-in"):
        assert "var(--ease-standard)" in _animation(name), name


def test_scene_changes_use_the_base_motion_token():
    rule = re.search(r"\n\.reel-scene \{(.*?)\n\}", CSS, re.S)
    assert rule, "no .reel-scene rule"
    transition = rule.group(1)
    assert "opacity var(--motion-base) var(--ease-standard)" in transition
    assert "transform var(--motion-base) var(--ease-standard)" in transition
    assert "400ms" not in transition and "500ms" not in transition


def test_the_finished_reel_fills_its_progress_bars():
    rule = re.search(r"\.product-reel\.is-done \.reel-progress i span \{([^}]*)\}", CSS)
    assert rule, "a finished reel leaves its progress bars empty"
    assert "scaleX(1)" in rule.group(1)


def test_the_replay_label_comes_from_the_translation_table():
    for lang in ("en", "cs"):
        html = _client().get(f"/?lang={lang}").text
        for key in ("landing.demo.play", "landing.demo.pause", "landing.demo.replay"):
            assert f'data-{key.rsplit(".", 1)[1]}="{LANDING_STRINGS[lang][key]}"' in html
    assert LANDING_STRINGS["en"]["landing.demo.replay"] == "Replay demo"
    assert LANDING_STRINGS["cs"]["landing.demo.replay"] == "Přehrát znovu"


def test_the_auto_advancing_caption_is_not_a_live_region():
    for lang in ("en", "cs"):
        html = _client().get(f"/?lang={lang}").text
        caption = re.search(r"<p[^>]*data-reel-caption[^>]*>", html)
        assert caption, "the reel has no caption"
        assert "aria-live" not in caption.group(0), (
            "a caption that rewrites itself every 3s must not be announced"
        )
        announcer = re.search(r"<p[^>]*data-reel-announce[^>]*>", html)
        assert announcer, "nothing left to announce Replay through"
        assert 'aria-live="polite"' in announcer.group(0)
        assert "sr-only" in announcer.group(0), "an empty paragraph would push the layout"
    assert ".sr-only {" in CSS, "landing.html does not load app.css"


def test_only_replay_writes_to_the_live_region():
    assert JS.count("announce(") == 2, "the announcer is written from somewhere else too"
    replay = re.search(r"function replay\(\) \{(.*?)\n  \}", JS, re.S)
    assert replay, "no replay() to hook the announcement onto"
    assert "announce(" in replay.group(1)


def test_the_reel_toggle_is_a_44px_svg_button():
    rule = re.search(r"\n\.reel-toggle \{(.*?)\n\}", CSS, re.S)
    assert rule, "no .reel-toggle rule"
    assert "width: 44px;" in rule.group(1)
    assert "height: 44px;" in rule.group(1)
    for lang in ("en", "cs"):
        html = _client().get(f"/?lang={lang}").text
        for icon in ("reel-icon-pause", "reel-icon-play", "reel-icon-replay"):
            assert f'class="reel-icon {icon}"' in html, icon


def test_the_toggle_uses_no_unicode_glyphs():
    html = _client().get("/").text
    assert "Ⅱ" not in html, "the Roman-numeral pause can render as an emoji"
    assert "▶" not in html, "the play glyph can render as a colour emoji"
    assert "data-reel-icon" not in html
    assert "icon.textContent" not in JS


def test_the_mock_receipt_is_labelled_as_an_example():
    for lang in ("en", "cs"):
        html = _client().get(f"/?lang={lang}").text
        example = LANDING_STRINGS[lang]["landing.demo.example"]
        assert f'class="receipt-example">{example}</small>' in html
    assert "DEMO-000000" in _client().get("/").text
    assert "CZ-UHP-849271" not in _client().get("/").text
