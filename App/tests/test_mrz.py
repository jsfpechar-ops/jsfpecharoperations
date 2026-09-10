from app import mrz

# A synthetic ICAO 9303 specimen; check digits are computed to be valid.
TD3 = (
    "P<GBRSMITH<<JOHN<PAUL<<<<<<<<<<<<<<<<<<<<<<<\n"
    "1234567897GBR9001017M3001015<<<<<<<<<<<<<<02"
)


def test_check_digit_algorithm():
    # Worked example from ICAO 9303 part 3.
    assert mrz.check_digit("D23145890734") == "9"
    assert mrz.check_digit("340712") == "7"


def test_td3_passport_parses():
    result = mrz.parse(TD3)
    assert result.ok, result.error
    assert result.kind == "TD3"
    assert result.surname == "SMITH"
    assert result.first_name == "JOHN PAUL"
    assert result.doc_number == "123456789"
    assert result.nationality == "GBR"
    assert result.issuing_state == "GBR"
    assert result.birth_date == "01011990"
    assert result.sex == "M"


def test_single_blob_is_split():
    result = mrz.parse(TD3.replace("\n", ""))
    assert result.ok
    assert result.surname == "SMITH"


def test_bad_check_digit_produces_a_warning_not_a_failure():
    broken = TD3.replace("1234567897GBR", "1234567890GBR")
    result = mrz.parse(broken)
    assert result.ok
    assert any("check digit" in w for w in result.warnings)


def test_german_issuing_code_is_mapped_to_iso():
    line1 = "P<D<<MUSTERMANN<<ERIKA<<<<<<<<<<<<<<<<<<<<<<"
    line2 = "C01X00T478D<<6408125F2702283<<<<<<<<<<<<<<<4"
    result = mrz.parse(line1 + "\n" + line2)
    assert result.ok
    assert result.nationality == "DEU"


def test_td1_identity_card_parses():
    lines = [
        "I<UTOD231458907<<<<<<<<<<<<<<<",
        "7408122F1204159UTO<<<<<<<<<<<6",
        "ERIKSSON<<ANNA<MARIA<<<<<<<<<<",
    ]
    result = mrz.parse("\n".join(lines))
    assert result.ok, result.error
    assert result.kind == "TD1"
    assert result.surname == "ERIKSSON"
    assert result.first_name == "ANNA MARIA"
    assert result.doc_number == "D23145890"
    assert result.nationality == "UTO"
    assert result.birth_date == "12081974"


def test_unrecognised_layout_is_reported_clearly():
    result = mrz.parse("not an mrz at all")
    assert not result.ok
    assert "Unrecognised MRZ layout" in result.error


def test_empty_input():
    assert not mrz.parse("").ok
