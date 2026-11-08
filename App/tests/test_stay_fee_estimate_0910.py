"""Brief 0910: the form-end fee estimate never raises and renders nothing when it cannot compute."""
import pytest

from app import config, routes  # noqa: F401  (import check)
from app.routes import guest as guest_routes


APARTMENT = {
    "stay_fee_collect": 1,
    "stay_fee_rate_czk": 50,
    "addr_obec": "Praha",
    "legal_entity_id": None,
}
RESERVATION = {"id": 7, "date_from": "2026-07-01", "date_to": "2026-07-04"}


@pytest.fixture(autouse=True)
def _gate_on(monkeypatch):
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)


def _values(**overrides):
    data = {"birth_date": "01.01.1980", "res_country": "DE", "res_city": "Berlin"}
    data.update(overrides)
    return data


def test_adult_with_stay_dates_gets_a_positive_estimate():
    result = guest_routes._fee_estimate(APARTMENT, RESERVATION, _values())
    assert result is not None
    assert result["days"] > 0
    assert result["amount"] == result["days"] * 50


@pytest.mark.parametrize("birth", ["", "   ", "xx.yy.zzzz", "31.02.1999", "--", "0"])
def test_blank_or_unparseable_birth_date_never_raises(birth):
    result = guest_routes._fee_estimate(APARTMENT, RESERVATION, _values(birth_date=birth))
    assert result is None or (result["amount"] > 0 and result["amount"] == result["days"] * 50)


def test_missing_stay_dates_render_nothing():
    no_dates = {"id": 7, "date_from": None, "date_to": None}
    assert guest_routes._fee_estimate(APARTMENT, no_dates, _values()) is None


def test_reservation_with_only_bad_dates_renders_nothing():
    bad = {"id": 7, "date_from": "not-a-date", "date_to": ""}
    assert guest_routes._fee_estimate(APARTMENT, bad, _values()) is None


def test_zero_rate_renders_nothing(monkeypatch):
    zero = dict(APARTMENT, stay_fee_rate_czk=0)
    assert guest_routes._fee_estimate(zero, RESERVATION, _values()) is None


def test_property_not_collecting_renders_nothing():
    off = dict(APARTMENT, stay_fee_collect=0)
    assert guest_routes._fee_estimate(off, RESERVATION, _values()) is None


def test_fee_qr_payload_carries_plain_vs_and_short_message():
    from app import payments
    payload = payments.spayd("CZ6508000000192000145399", 150, "2", "Stay fee 2")
    assert "*X-VS:2*" in payload
    assert payload.endswith("MSG:STAY FEE 2")
    assert "0000000002" not in payload


def test_obec_rule_for_the_form_carries_the_folded_obec_and_tables():
    import json
    rule = json.loads(guest_routes._fee_obec_rule({"addr_obec": "Praha"}))
    assert rule["obec"] == "PRAHA" and rule["country"] == "CZE"
    assert rule["aliases"]["PRAGUE"] == "PRAHA" and "PRAHA" in rule["bases"]
    assert guest_routes._fee_obec_rule({"addr_obec": ""}) == ""


def test_estimate_is_drawn_from_the_page_load_values_only():
    """Root cause of the Prague guest still shown 100 CZK: a new form is rendered with empty
    values, so the estimate cannot know the home city typed later; signature.js hides it."""
    assert guest_routes._fee_estimate(APARTMENT, RESERVATION, {})["amount"] > 0
    typed = _values(res_country="CZE", res_city="Prague")
    assert guest_routes._fee_estimate(APARTMENT, RESERVATION, typed) is None
    assert guest_routes._fee_estimate(APARTMENT, RESERVATION, _values(res_country="CZE", res_city="Prahaa"))


def test_form_script_folds_like_the_backend():
    import json, shutil, subprocess, pathlib
    node = shutil.which("node")
    if not node:
        pytest.skip("node missing")
    src = (pathlib.Path(guest_routes.__file__).resolve().parents[1] / "static" / "signature.js").read_text()
    start = src.index("function fold(text)")
    end = src.index("var country = document.getElementById(\"res_country\")")
    rule = json.loads(guest_routes._fee_obec_rule({"addr_obec": "Praha"}))
    js = ("var rule=%s;%s;for (const c of process.argv.slice(1)) console.log(key(c));" % (json.dumps(rule), src[start:end]))
    out = subprocess.run([node, "-e", js, "Prague", "Praha 2", "Praha-Vinohrady", "Brno", "Prahaa"],
                         capture_output=True, text=True, check=True).stdout.split()
    assert out == ["PRAHA", "PRAHA", "PRAHA", "BRNO", "PRAHAA"]
