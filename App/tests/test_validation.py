import base64
from datetime import date

from app import validation as v

# A real 1x1 PNG, because the validator checks the magic bytes.
SIGNATURE = "data:image/png;base64," + base64.b64encode(
    bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000a49444154789c6300010000050001od7a1f0000000049454e44ae42"
        "6082".replace("od", "0d")
    )
).decode()


def errors(issues):
    return {i.field for i in issues if i.is_error}


def test_name_is_uppercased_and_cleaned():
    assert v.normalise_name("  van  der   Berg ") == "VAN DER BERG"
    assert v.normalise_name("O'Neill-Smith") == "O'NEILL-SMITH"
    # Digits and punctuation are not permitted in a name field.
    assert v.normalise_name("Smith2 (Jr.)") == "SMITH JR"
    # Czech diacritics survive, because appendix 3 explicitly allows them.
    assert v.normalise_name("Dvořák") == "DVOŘÁK"


def test_unsupported_letters_are_transliterated_not_deleted():
    """Deleting a letter files a name that no longer matches the passport."""
    # Vietnamese and Turkish letters are outside CP1250; the passport's
    # machine-readable line spells them NGUYEN and ISMAIL.
    assert v.normalise_name("Nguyễn") == "NGUYEN"
    assert v.normalise_name("İsmail") == "ISMAIL"
    # Romanian comma-below, which is a different codepoint to the cedilla form.
    assert v.normalise_name("Șerban") == "SERBAN"
    # Letters CP1250 does have must be left exactly as they are.
    assert v.normalise_name("Dvořák") == "DVOŘÁK"
    assert v.normalise_name("Müller") == "MÜLLER"


def test_non_latin_script_is_reported_as_a_script_problem():
    """A Cyrillic surname normalises to nothing; "required" would be a lie."""
    raw = {"surname": "Иванов", "first_name": "Иван"}
    values = v.normalise_guest(raw)
    assert values["surname"] == ""
    issues = v.validate_guest(values, raw=raw)
    surname_issue = next(i for i in issues if i.field == "surname")
    assert "Latin letters" in surname_issue.message
    # Without the raw input there is nothing better to say than "required".
    assert "required" in next(
        i for i in v.validate_guest(values) if i.field == "surname"
    ).message


def test_over_length_names_are_reported_instead_of_cut():
    """Appendix 5 section 10.5: tell the user on first save, do not truncate."""
    long_given = "Maria Jose Guadalupe Fernanda"  # 29 characters
    assert len(long_given) > v.MAX_FIRST_NAME

    unclamped = v.normalise_guest({"first_name": long_given}, clamp=False)
    assert unclamped["first_name"] == long_given.upper()
    assert "first_name" in errors(v.validate_guest(unclamped))

    # Importers and demo data still get a value the database column accepts.
    clamped = v.normalise_guest({"first_name": long_given})
    assert len(clamped["first_name"]) == v.MAX_FIRST_NAME


def test_forbidden_characters_never_survive():
    dirty = "Ab|cd\r\nef"
    assert "|" not in v.normalise_name(dirty)
    assert "\r" not in v.normalise_note(dirty)
    assert "\n" not in v.normalise_note(dirty)


def test_xml_illegal_control_characters_are_stripped():
    """AR-21: one control character makes the whole SOAP batch unparseable."""
    assert v.strip_forbidden("A\x01B") == "A B"


def test_document_number_normalisation():
    assert v.normalise_document(" ab 12-34 ") == "AB1234"
    assert v.normalise_document("p123456789") == "P123456789"


def test_birth_date_formats():
    assert v.normalise_birth_date("01011990") == "01011990"
    assert v.normalise_birth_date("1.1.1990") == "01011990"
    assert v.normalise_birth_date("1. 1. 1990") == "01011990"
    assert v.normalise_birth_date("01/01/1990") == "01011990"
    assert v.normalise_birth_date("9/9/1990") == "09091990"
    assert v.display_birth_date("01011990") == "01.01.1990"
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


def test_stay_dates_outside_the_booking_are_refused():
    """The period is the police record's cFrom/cUntil and drives retention."""
    early = v.validate_stay_dates(
        date(2025, 6, 5), date(2026, 6, 10), date(2026, 6, 5), date(2026, 6, 10)
    )
    assert errors(early) == {"stay_from"}

    late = v.validate_stay_dates(
        date(2026, 6, 5), date(2027, 6, 10), date(2026, 6, 5), date(2026, 6, 10)
    )
    assert errors(late) == {"stay_to"}

    inside = v.validate_stay_dates(
        date(2026, 6, 6), date(2026, 6, 9), date(2026, 6, 5), date(2026, 6, 10)
    )
    assert inside == []
    # The boundaries themselves are the booking, not an escape from it.
    assert v.validate_stay_dates(
        date(2026, 6, 5), date(2026, 6, 10), date(2026, 6, 5), date(2026, 6, 10)
    ) == []
    # A missing date is "not supplied", never "outside".
    assert v.validate_stay_dates(None, None, date(2026, 6, 5), date(2026, 6, 10)) == []
    assert v.validate_stay_dates(date(2026, 6, 5), None, None, None) == []
    assert v.STAY_DATE_TOLERANCE_DAYS == 0


def test_the_reach_back_window_never_widens_to_unbounded():
    """W3.5 [F23]: a blank or hand-edited value must not open the whole history."""
    assert v.normalise_reachback_days(None) == 365
    assert v.normalise_reachback_days("") == 365
    assert v.normalise_reachback_days("not a number") == 365
    assert v.normalise_reachback_days(0) == 365
    assert v.normalise_reachback_days(-30) == 365
    assert v.normalise_reachback_days(1) == 1
    assert v.normalise_reachback_days("30") == 30
    assert v.normalise_reachback_days(10**9) == v.REACHBACK_DAYS_MAX
    assert v.REACHBACK_DAYS_DEFAULT == 365


def test_a_drawn_signature_must_be_a_png_or_jpeg_data_url():
    """signature_png is TEXT in one SQLite file, and every "this guest signed"
    check downstream is a look at its prefix, so this is the only gate."""
    assert v.is_valid_signature(SIGNATURE)
    assert v.parse_signature_data_url(SIGNATURE).startswith(b"\x89PNG\r\n\x1a\n")
    # JPEG is allowed, and its magic bytes are checked the same way.
    jpeg = "data:image/jpeg;base64," + base64.b64encode(
        b"\xff\xd8\xff\xe0" + b"\x00" * 32
    ).decode()
    assert v.is_valid_signature(jpeg)

    # An SVG is an image type, and a script container. Nothing here renders one.
    assert not v.is_valid_signature("data:image/svg+xml;base64," + base64.b64encode(
        b"<svg xmlns='http://www.w3.org/2000/svg'/>"
    ).decode())
    # PNG declared, but the bytes are something else.
    assert not v.is_valid_signature(
        "data:image/png;base64," + base64.b64encode(b"<html>hi</html>").decode()
    )
    # The paper-import marker is a marker, not a signature to be stored.
    assert not v.is_valid_signature("imported")
    assert not v.is_valid_signature("")
    assert not v.is_valid_signature(None)
    # A bare URL, a non-base64 payload, and an empty payload.
    assert not v.is_valid_signature("https://example.com/sign.png")
    assert not v.is_valid_signature("data:image/png;base64,!!!not base64!!!")
    assert not v.is_valid_signature("data:image/png;base64,")


def test_an_oversized_signature_is_refused():
    """A hand-built request must not put a blob in the database file."""
    def png_of(size: int) -> str:
        return "data:image/png;base64," + base64.b64encode(
            b"\x89PNG\r\n\x1a\n" + b"\x00" * (size - 8)
        ).decode()

    assert v.is_valid_signature(png_of(v.MAX_SIGNATURE_BYTES))
    assert not v.is_valid_signature(png_of(v.MAX_SIGNATURE_BYTES + 1))
    # Rejected on the payload's length, before anything is decoded.
    assert not v.is_valid_signature(
        "data:image/png;base64," + "A" * (v._MAX_SIGNATURE_PAYLOAD_CHARS + 4)
    )


def test_signature_issue_names_the_field_and_says_what_to_do():
    issue = v.signature_issue("data:image/svg+xml;base64,PHN2Zy8+")
    assert issue is not None
    assert issue.field == "signature"
    assert issue.is_error
    assert issue.message == v.SIGNATURE_INVALID_MESSAGE
    assert v.signature_issue(SIGNATURE) is None


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
