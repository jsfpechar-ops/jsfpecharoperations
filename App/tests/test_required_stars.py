"""1010: every control the app cannot continue without has a red star, and every star has a required control."""
import re
from pathlib import Path

T = Path(__file__).resolve().parent.parent / "app" / "templates"
AUDITED = [
    "_property_editor.html", "_property_address_fields.html", "_property_identity_fields.html",
    "_property_operator.html", "_property_calendars.html", "_stay_fee_fields.html",
    "_entity_business_fields.html", "setup_wizard/property.html", "setup_wizard/calendar.html",
    "setup_wizard/police.html", "reservations.html", "guest_form_admin.html",
]
LEGEND_ONCE = ["_property_editor.html", "reservations.html", "guest_form_admin.html", "_entity_business_fields.html"]
# control id -> reason it may be required without a star. Empty on purpose: add nothing without an owner decision.
ALLOW: dict = {}

CTRL = re.compile(r"<(?:input|select|textarea)\b.*?>", re.S)
REQ = re.compile(r"(?<![-\w])required\b")
ID = re.compile(r'\bid="([^"]+)"')
LABEL_STAR = re.compile(r'<label\b[^>]*\bfor="([^"]+)"[^>]*>[^<]*<span class="req-star"')
TAIL = r"(?:true|required|fee_required|fee_needed|not has_password)"


def _text(name):
    return (T / name).read_text(encoding="utf-8")


def _controls(text):
    return [(m.group(1), tag) for tag in CTRL.findall(text) for m in [ID.search(tag)] if m]


def _starred_ids(text):
    ids = set(LABEL_STAR.findall(text))
    for line in text.splitlines():
        m = re.search(r"field_label\('([^']+)'", line)
        if m and (re.search(r"required=(?!false)\w", line) or re.search(rf"'\s*,\s*{TAIL}\s*\)\s*\}}\}}", line)):
            ids.add(m.group(1))
    return ids


def _macro_labelled(text):
    return re.search(r"field_label\(name,[^\n]*,\s*required\)", text) is not None


def test_every_required_control_has_a_star():
    bad = []
    for name in AUDITED:
        text = _text(name)
        stars = _starred_ids(text)
        for cid, tag in _controls(text):
            if not REQ.search(tag) or cid in stars or cid in ALLOW:
                continue
            if cid == "{{ name }}" and _macro_labelled(text):
                continue
            bad.append(f"{name}: {cid}")
    assert not bad, bad


def test_every_star_has_a_required_control():
    bad = []
    for name in AUDITED:
        text = _text(name)
        controls = _controls(text)
        for sid in _starred_ids(text):
            tags = [tag for cid, tag in controls if cid == sid]
            if tags and not any(REQ.search(t) or "aria-required" in t for t in tags) and sid not in ALLOW:
                bad.append(f"{name}: {sid}")
    assert not bad, bad


def test_editor_police_fields_are_starred_and_aria_required():
    text = _text("_property_editor.html")
    for fid in ("uby_idub", "uby_ws_user", "uby_mark", "uby_name"):
        line = next(ln for ln in text.splitlines() if f"text_field('{fid}'" in ln)
        assert "required=true" in line, fid
    macro = text[text.index("{% macro text_field"):text.index("{% endmacro %}")]
    assert "field_label(name, label, help, optional, '', required)" in macro
    assert 'aria-required="true"' in macro
    assert "uby_ws_password', t('setup.label.password')" in text and "not has_password" in text  # 1099 label


def test_street_is_starred_and_other_optional_address_fields_stay_unstarred():
    # Owner decision 2026-11-08: the street is mandatory (Airbnb listings are rarely in street-less villages).
    text = _text("_property_address_fields.html")
    street = next(ln for ln in text.splitlines() if "address_input('addr_street'" in ln)
    assert "'', true," in street
    for fid in ("addr_orient_no", "addr_obec_cast", "addr_okres"):
        line = next(ln for ln in text.splitlines() if f"address_input('{fid}'" in ln)
        assert "required" not in line and not line.rstrip().endswith("true) }}"), fid


def test_one_legend_per_form_and_wizard_calendar_step_shows_it():
    for name in LEGEND_ONCE:
        assert _text(name).count("required_legend") == 1, name
    layout = _text("setup_wizard/_layout.html")
    assert re.search(r"wizard_step in \([^)]*'calendar'[^)]*\).*required_legend", layout)


def test_editor_stay_fee_fields_star_follows_the_rate():
    text = _text("_stay_fee_fields.html")
    assert "set fee_needed = fee_required or" in text
    for fid in ("stay_fee_vs", "stay_fee_council_account", "stay_fee_authority_name"):
        line = next(ln for ln in text.splitlines() if f"field_label('{fid}'" in ln)
        assert re.search(r"'',\s*fee_needed\)", line), fid
        tag = next(tag for cid, tag in _controls(text) if cid == fid)
        assert """aria-required="{{ 'true' if fee_needed else 'false' }}\"""" in tag, fid
    rate_line = next(ln for ln in text.splitlines() if "field_label('stay_fee_rate_czk'" in ln)
    assert "fee_required)" in rate_line and "fee_needed" not in rate_line

