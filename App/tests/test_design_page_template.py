"""host_page.html: slots, body kinds and the matching skeleton (MASTER 5)."""
import re
from pathlib import Path

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from app import templating
from app.main import app

TEMPLATES = Path(templating.__file__).resolve().parent / "templates"

SAMPLE = (
    '{% extends "host_page.html" %}{% set nav = "reservations" %}{% set body_kind = KIND %}'
    '{% block title %}Sample{% endblock %}{% block meta %}Meta line{% endblock %}'
    '{% block primary_action %}{{ ui_button("Do it", "primary", href="/x") }}{% endblock %}'
    '{% block secondary_actions %}{{ ui_button("Other", "secondary", href="/y") }}{% endblock %}'
    '{% block tabs %}{{ ui_tabs([("/a", "A", true), ("/b", "B", false)]) }}{% endblock %}'
    '{% block body %}<p class="ui-sub">body</p>{% endblock %}'
)


@pytest.fixture
def sample_route():
    def make(kind):
        name = f"_sample_{kind}.html"
        (TEMPLATES / name).write_text(SAMPLE.replace("KIND", repr(kind)), encoding="utf-8")
        path = f"/__design_sample_{kind}"

        @app.get(path)
        def _view(request: Request):  # pragma: no cover - test only
            return templating.render(request, name, {"nav": "reservations"})
        return path, TEMPLATES / name
    created = []
    yield lambda kind: created.append(make(kind)) or created[-1][0]
    for _, p in created:
        p.unlink(missing_ok=True)


@pytest.mark.parametrize("kind", ["list", "detail", "form", "settings"])
def test_each_body_kind_renders_header_slots_and_its_own_skeleton(sample_route, kind):
    path = sample_route(kind)
    with TestClient(app) as client:
        html = client.get(path + "?lang=en").text
    assert html.count("<h1") == 1 and "<h1>Sample</h1>" in html
    assert '<p class="ui-ph-meta" data-list-meta>Meta line</p>' in html
    assert html.count("ui-btn-primary") == 1
    assert 'class="ui-tab" href="/a" aria-current="page"' in html
    assert f'class="ui-body ui-body-{kind}"' in html
    assert f'data-skeleton-kind="{kind}"' in html
    assert "c05-skel" not in html
    assert 'data-page-skeleton role="status" hidden' in html


def test_pages_that_still_extend_base_keep_the_old_skeleton():
    base = (TEMPLATES / "base.html").read_text(encoding="utf-8")
    assert '{% block page_skeleton %}' in base and "data-page-skeleton" in base


def test_skeleton_script_waits_300ms_and_stays_400ms():
    script = (TEMPLATES.parent / "static" / "skeleton.js").read_text(encoding="utf-8")
    assert "var DELAY_MS = 300;" in script and "var MIN_VISIBLE_MS = 400;" in script
