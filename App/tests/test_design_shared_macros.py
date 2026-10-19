"""_components.html badges and menus render the v2 catalog (MASTER 7.5, 7.8)."""
import re

from app.templating import templates


def _render(src, **ctx):
    env = templates.env
    ctx.setdefault("t", lambda key, **kw: key)
    ctx.setdefault("tp", lambda key, n, **kw: f"{key}:{n}")
    return env.from_string('{% from "_components.html" import progress_pill, submission_pill, row_menu_begin, row_menu_end, copy_button, bulk_send_ready, empty_state with context %}' + src).render(**ctx)


def test_progress_pill_maps_tones_to_kinds_and_keeps_the_tone():
    cases = {"failed": ("action", "red", "! "), "incomplete": ("action", "amber", ""), "ready": ("action", "blue", ""),
             "awaiting_guest": ("neutral", "teal", ""), "reported": ("done", "green", ""), "not_required": ("neutral", "grey", "")}
    for status, (kind, tone, mark) in cases.items():
        html = _render("{{ progress_pill(status) }}", status=status)
        assert f'class="ui-badge ui-badge-{kind}' in html and f'data-tone="{tone}"' in html, status
        assert (">" + mark) in html
    assert "ui-badge-overdue" in _render("{{ progress_pill('failed') }}")


def test_submission_pill_uses_attention_for_amber_and_overdue_for_red():
    assert 'ui-badge-attention' in _render("{{ submission_pill('partial') }}")
    assert 'ui-badge-action ui-badge-overdue' in _render("{{ submission_pill('error') }}")
    assert 'ui-badge-done' in _render("{{ submission_pill('ok') }}")


def test_row_menu_and_copy_button_use_catalog_classes_and_lucide():
    html = _render("{{ row_menu_begin() }}{{ row_menu_end() }}{{ copy_button('x') }}")
    assert 'class="ui-btn ui-btn-quiet ui-btn-icon ui-btn-compact row-menu-trigger"' in html
    assert 'data-icon="ellipsis-vertical"' in html and 'data-icon="copy"' in html
    assert 'class="row-menu-panel ui-menu-panel" role="menu" hidden' in html
    assert "<circle cx=\"3.25\"" not in html


def test_bulk_send_and_empty_state_are_secondary_and_v2():
    html = _render("{{ bulk_send_ready(2, '/') }}{{ empty_state('T', 'B', '/a', 'Go') }}")
    assert 'class="ui-btn ui-btn-secondary send-all"' in html and "(2)" in html
    assert '<div class="ui-empty" data-empty-state>' in html and 'class="ui-btn ui-btn-primary" href="/a"' in html
    assert re.search(r"<h2>T</h2>", html)
