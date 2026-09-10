from datetime import date

from app import validation as v


def errors(issues):
    return {i.field for i in issues if i.is_error}


def test_name_is_uppercased_and_cleaned():
    assert v.normalise_name("  van  der   Berg ") == "VAN DER BERG"
    assert v.normalise_name("O'Neill-Smith") == "O'NEILL-SMITH"
    # Digits and punctuation are not permitted in a name field.
    assert v.normalise_name("Smith2 (Jr.)") == "SMITH JR"
    # Czech diacritics survive, because appendix 3 explicitly allows them.
    assert v.normalise_name("Dvořák") == "DVOŘÁK"


def test_forbidden_characters_never_survive():
    dirty = "Ab|cd\r\nef"
    assert "|" not in v.normalise_name(dirty)
    assert "\r" not in v.normalise_note(dirty)
    assert "\n" not in v.normalise_note(dirty)


def test_document_number_normalisation():
    assert v.normalise_document(" ab 12-34 ") == "AB1234"
    assert v.normalise_document("p123456789") == "P123456789"


def test_birth_date_formats():
    assert v.normalise_birth_date("01011990") == "01011990"
    assert v.normalise_birth_date("1.1.1990") == "01011990"
    assert v.normalise_birth_date("1. 1. 1990") == "01011990"
    assert v.normalise_birth_date("01/01/1990") == "01011990"
    assert v.normalise_birth_date("9/9/1990") == "09091990"
    assert v.display_birth_date("01011990") == "01/01/1990"
    # An unknown day is written as zero, which appendix 3 allows.
    assert v.normalise_birth_date("00.05.1950") == "00051950"


def test_two_digit_year_picks_the_past():
    assert v.normalise_birth_date("010190").endswith("1990")


def test_birth_date_validation():
    stay = date(2026, 6, 1)
    assert not errors(v.validate_birth_date("01011990", stay))
    assert errors(v.validate_birth_date("31021990", stay)) == {"birth_date"}
    assert errors(v.validate_birth_date("01012030", stay)) == {"birth_date"}
    assert errors(v.validate_birth_date("", stay)) == {"birth_date"}
    # A partially unknown date is legal.
    assert not errors(v.validate_birth_date("00001950", stay))


def good_guest(**overrides):
    guest = {
        "surname": "SMITH",
        "first_name": "JOHN",
        "birth_date": "01011990",
        "nationality": "GBR",
        "doc_number": "P1234567",
        "visa_number": "",
        "res_street": "Baker Street 221B",
        "res_city": "London",
        "res_country": "GBR",
        "purpose": "10",
        "note": "",
    }
    guest.update(overrides)
    return guest


def test_valid_guest_passes():
    assert not errors(v.validate_guest(good_guest(), date(2026, 6, 1), date(2026, 6, 5)))


def test_document_number_minimum_length():
    assert errors(v.validate_guest(good_guest(doc_number="AB12"))) == {"doc_number"}


def test_inpass_requires_a_note():
    assert errors(v.validate_guest(good_guest(doc_number="INPASS"))) == {"note"}
    assert not errors(
        v.validate_guest(good_guest(doc_number="INPASS", note="parent doc P1234567"))
    )


def test_unknown_nationality_is_rejected():
    assert errors(v.validate_guest(good_guest(nationality="XY"))) == {"nationality"}
    # "UK" is a common mistake: the field wants ISO 3166-1 alpha-3.
    assert errors(v.validate_guest(good_guest(nationality="UK"))) == {"nationality"}


def test_residence_requires_full_address():
    assert "res_street" in errors(v.validate_guest(good_guest(res_street="")))
    assert "res_city" in errors(v.validate_guest(good_guest(res_city="")))
    assert "res_country" in errors(v.validate_guest(good_guest(res_country="")))


def test_residence_part_cannot_be_only_digits():
    assert "res_city" in errors(v.validate_guest(good_guest(res_city="12345")))


def test_departure_must_follow_arrival():
    issues = v.validate_guest(good_guest(), date(2026, 6, 5), date(2026, 6, 5))
    assert "stay_to" in errors(issues)


def test_compose_residence_format():
    # The police read this field, so the country is named in Czech.
    composed = v.compose_residence("Baker Street 221B", "London", "GBR")
    assert composed == "Baker Street 221B, London, GBR-Spojené království"
    assert len(v.compose_residence("x" * 200, "y" * 200, "GBR")) <= v.MAX_RESIDENCE


def test_czech_nationals_are_not_reportable():
    assert v.guest_is_reportable("GBR")
    assert not v.guest_is_reportable("CZE")
    assert not v.guest_is_reportable("")


def good_apartment(**overrides):
    apartment = {
        "uby_idub": "100227887600",
        "uby_mark": "CZGFW",
        "uby_name": "Apartment Vinohrady",
        "uby_contact": "host@example.com",
        "addr_okres": "Praha 2",
        "addr_obec": "Praha",
        "addr_obec_cast": "Vinohrady",
        "addr_street": "Korunní",
        "addr_house_no": "1234",
        "addr_orient_no": "12a",
        "addr_zip": "12000",
        "uby_ws_user": "UBY-WS12cdef",
        "uby_ws_password": "secret",
    }
    apartment.update(overrides)
    return apartment


def test_valid_apartment_passes():
    assert not errors(v.validate_apartment(good_apartment()))


def test_apartment_identifier_rules():
    assert errors(v.validate_apartment(good_apartment(uby_idub="123"))) == {"uby_idub"}
    assert errors(v.validate_apartment(good_apartment(uby_mark="ABC"))) == {"uby_mark"}
    assert errors(v.validate_apartment(good_apartment(addr_zip="123"))) == {"addr_zip"}


def test_house_number_accepts_evidence_form():
    assert not errors(v.validate_apartment(good_apartment(addr_house_no="E123")))
    assert errors(v.validate_apartment(good_apartment(addr_house_no="12345"))) == {"addr_house_no"}


def test_web_form_login_is_flagged_as_wrong_kind():
    issues = v.validate_apartment(good_apartment(uby_ws_user="ub1234567"))
    warnings = [i for i in issues if not i.is_error and i.field == "uby_ws_user"]
    assert warnings, "a ub… login should be flagged as the wrong credential type"


def test_missing_password_blocks_reporting():
    assert errors(v.validate_apartment(good_apartment(uby_ws_password=""))) == {"uby_ws_password"}
