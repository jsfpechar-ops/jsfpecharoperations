"""_ui.html renders the v2 catalog (docs/design/MASTER.md section 7)."""
import json
from pathlib import Path

import jinja2

APP_DIR = Path(__file__).resolve().parents[1] / "app"
ROOT = APP_DIR.parents[1]
CATALOG = json.loads((ROOT / "docs" / "design" / "catalog.json").read_text(encoding="utf-8"))
ENV = jinja2.Environment(loader=jinja2.FileSystemLoader(str(APP_DIR / "templates")), undefined=jinja2.StrictUndefined)
ENV.globals["t"] = lambda key, **kw: key


def _r(src, **ctx):
    return ENV.from_string('{% from "_ui.html" import ' + ", ".join(
        ["ui_button", "ui_icon_button", "ui_badge", "ui_chip", "ui_field", "ui_select", "ui_textarea", "ui_check",
         "ui_toggle", "ui_menu_begin", "ui_menu_end", "ui_menu_item", "ui_dialog_begin", "ui_dialog_end", "ui_empty",
         "ui_tip", "ui_pagination", "ui_pdot"]) + " with context %}" + src).render(**ctx)


def _classes(html):
    import re
    return {c for m in re.findall(r'class="([^"]*)"', html) for c in m.split()}


def test_button_variants_sizes_and_states():
    html = _r('{{ ui_button("Save", "primary", type="submit") }}{{ ui_button("Open", href="/x", size="compact", icon_name="plus") }}'
              '{{ ui_button("Wait", "secondary", loading=true) }}{{ ui_button("No", "danger", disabled=true) }}{{ ui_icon_button("Close", "x") }}')
    assert 'class="ui-btn ui-btn-primary" type="submit"' in html
    assert 'class="ui-btn ui-btn-secondary ui-btn-compact" href="/x"' in html and 'data-icon="plus"' in html
    assert "ui-btn-loading" in html and 'aria-busy="true"' in html
    assert "ui-btn-danger" in html and " disabled" in html
    assert 'aria-label="Close"' in html and "ui-btn-icon" in html


def test_badge_kinds_carry_a_word_and_overdue_a_mark():
    for kind in ("action", "attention", "done", "neutral"):
        assert f'class="ui-badge ui-badge-{kind}">Word</span>' in _r('{{ ui_badge(kind, "Word") }}', kind=kind)
    assert "ui-badge-overdue\">Late" in _r('{{ ui_badge("action", "Late", true) }}')


def test_fields_bind_help_and_errors_to_the_control():
    ok = _r('{{ ui_field("name", "Name", help="Only you see it") }}')
    assert 'aria-describedby="name-help"' in ok and 'class="ui-help" id="name-help"' in ok
    bad = _r('{{ ui_field("cp", "Number", error="Required") }}')
    assert "ui-field-err" in bad and 'aria-invalid="true"' in bad and 'id="cp-error"' in bad
    sel = _r('{{ ui_select("s", "State", [("a", "A"), ("b", "B")], selected="b") }}')
    assert '<option value="b" selected>' in sel
    assert 'role="switch"' in _r('{{ ui_toggle("tg", "Fee", checked=true) }}')


def test_menu_dialog_empty_and_pagination_render_their_hooks():
    html = _r('{{ ui_menu_begin() }}{{ ui_menu_item("Open", "/o") }}{{ ui_menu_item("Delete", danger=true) }}{{ ui_menu_end() }}')
    assert 'role="menu"' in html and "row-menu-trigger" in html and "ui-menu-danger" in html
    dlg = _r('{{ ui_dialog_begin("d1", "Title") }}<p>x</p>{{ ui_dialog_end() }}')
    assert '<dialog id="d1" class="ui-dialog" aria-labelledby="d1-title">' in dlg
    empty = _r('{{ ui_empty("None", "Next step.", "Add", "/add") }}')
    assert "ui-btn-primary" in empty and "data-empty-state" in empty
    pag = _r('{{ ui_pagination(2, 5, "/p=1", "/p=3", "Stays", "Show more", "Previous", "Next") }}')
    assert "data-pagination-more" in pag and pag.count("ui-btn-compact") == 2


def test_every_class_the_macros_emit_is_in_the_catalog():
    html = _r('{{ ui_button("a") }}{{ ui_icon_button("b", "x") }}{{ ui_badge("done", "c", true) }}{{ ui_chip("d", selected=true) }}'
              '{{ ui_field("f", "F", error="e") }}{{ ui_select("s", "S", [("1", "1")]) }}{{ ui_textarea("ta", "T") }}{{ ui_check("c1", "C") }}'
              '{{ ui_toggle("t1", "T") }}{{ ui_menu_begin() }}{{ ui_menu_item("i", danger=true) }}{{ ui_menu_end() }}'
              '{{ ui_dialog_begin("d", "D") }}{{ ui_dialog_end() }}{{ ui_empty("E") }}{{ ui_tip("tip", "text") }}'
              '{{ ui_pagination(1, 1) }}{{ ui_pdot(3, "P") }}')
    allowed = set(CATALOG["classes"]) | set(CATALOG["hooks"])
    assert _classes(html) <= allowed, _classes(html) - allowed


def test_host2_css_is_loaded_last_in_the_signed_in_head():
    base = (APP_DIR / "templates" / "base.html").read_text(encoding="utf-8")
    assert base.index("host-design0123.css") < base.index("/static/host2.css")
