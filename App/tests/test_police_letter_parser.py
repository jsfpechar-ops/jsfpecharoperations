"""1083: the police web-service letter parser (pure, no I/O)."""

from __future__ import annotations

import dataclasses
import socket
import time
import unicodedata

import pytest

from app.police_letter import (
    FIELDS,
    FILLED_STATES,
    MAX_LETTER_CHARS,
    FieldResult,
    LetterResult,
    confirmed_fields,
    line_from_form,
    parse_letter,
)
from app.ubyport_sample_pdf import (
    SAMPLE_CASE_REF,
    SAMPLE_CONTACT,
    SAMPLE_DS_BARCODE,
    SAMPLE_EXTRACT_DATE,
    SAMPLE_FACILITY_LINE1,
    SAMPLE_FACILITY_LINE2,
    SAMPLE_IDUB,
    SAMPLE_JID,
    SAMPLE_LETTER_DATE,
    SAMPLE_PROCESSOR,
    SAMPLE_RECIPIENT_ISDS,
    SAMPLE_RECIPIENT_NAME,
    SAMPLE_SIGNATORY,
    SAMPLE_SIGNATORY_ROLE,
    SAMPLE_WS_PASSWORD,
    SAMPLE_WS_USER,
    SAMPLE_ZKRATKA,
)

FAKE_PW = "Zz9!fake-pass"
FAKE_IDUB = "000011112222"
TITLE = "Přihlašovací údaje pro robotické vkládání Ubyport Webová služba"
L_USER = "Přihlašovací jméno:"
L_PW = "Přístupové heslo:"
L_MARK = "Zkratka ubytovacího zařízení:"

MISSING = ("missing", "")
UNREADABLE = ("unreadable", "")
AMBIGUOUS = ("ambiguous", "")
CONFLICT = ("conflict", "")


def found(value):
    return ("found", value)


def derived(value):
    return ("derived", value)


def exp(idub=MISSING, user=MISSING, mark=MISSING):
    return {"uby_idub": idub, "uby_ws_user": user, "uby_mark": mark}


OFFICIAL = f"{TITLE}\n{L_USER} {SAMPLE_WS_USER}\n{L_PW} {SAMPLE_WS_PASSWORD}\nIDUB: {SAMPLE_IDUB}\n"
OFFICIAL_NEXT_LINE = f"{TITLE}\n{L_USER}\n{SAMPLE_WS_USER}\n{L_PW}\n{SAMPLE_WS_PASSWORD}\nIDUB:\n{SAMPLE_IDUB}\n"
FULL_BODY = (
    "POLICEJNÍ PREZIDIUM ČESKÉ REPUBLIKY\n"
    "Č. j.: CPR-302-445/ČJ-2026-880014\n"
    "Praha 15. dubna 2026\n"
    "\n"
    "Vážený pane,\n"
    "na základě Vaší žádosti Vám zasíláme údaje k webové službě.\n"
    "\n" + OFFICIAL + "\n"
    "S pozdravem\n"
    "plk. Mgr. Demo Vedoucí\n"
    "Strana 1 z 2\n"
)
OK_ALL = exp(found(SAMPLE_IDUB), found(SAMPLE_WS_USER), derived(SAMPLE_ZKRATKA))


def idub_only(value_part):
    return f"IDUB: {value_part}\n"


def user_only(login):
    return f"{L_USER} {login}\n"


# 1088 rule 7: the strings the sample letter draws, one per line, in drawing
# order, without UbyHost's own annotations.
FULL_LETTER = "\n".join(
    [
        f"JID: {SAMPLE_JID}",
        "ŘEDITELSTVÍ SLUŽBY CIZINECKÉ POLICIE",
        "Informační odbor",
        f"Č. j. {SAMPLE_CASE_REF}",
        f"Praha {SAMPLE_LETTER_DATE}",
        "Počet stran: 1",
        "Přílohy: 1 el.soubor",
        SAMPLE_RECIPIENT_NAME,
        f"ISDS: {SAMPLE_RECIPIENT_ISDS}",
        "Ubyport- Webová služba - přiděleno",
        (
            "V příloze Vám zasílám požadované přihlašovací údaje pro systém Ubyport - Webová "
            "služba."
        ),
        (
            "Pro implementaci webové služby do Vašeho hotelového programu kontaktujte výrobce "
            "Vašeho hotelového programu."
        ),
        (
            "Přidělením těchto přihlašovacích údajů nejsou nijak dotčeny (zůstávají plně funkční) "
            "přihlašovací údaje do Internetové aplikace Ubyport, která tak zůstává zálohou pro "
            "oznamování ubytovaných cizinců v případě, že by měl systém Ubyport - webová služba "
            "poruchu a nešlo by dočasně prostřednictvím něj oznamovat ubytované cizince."
        ),
        "DŮLEŽITÉ:",
        (
            "Aby se přiložený PDF dokument otevřel a zobrazil správně, doporučujeme jej otevřít "
            "v programu Adobe Acrobat Reader (prohlížeč PDF) nebo v internetovém prohlížeči MS "
            "Edge (prohlížeč WWW a PDF), nejlépe v nejnovějších verzích. V programu Adobe "
            "Acrobat a jiných editorech PDF dokumentů, se obsah nemusí zobrazit správně, nebo může "
            "zcela chybět."
        ),
        "Zpracoval:",
        SAMPLE_PROCESSOR,
        SAMPLE_SIGNATORY,
        SAMPLE_SIGNATORY_ROLE,
        "Olšanská 2",
        "130 51 Praha",
        "Tel.: +420 725 798 600",
        "E-mail: podatelna@policie.gov.cz",
        "ID DS: demo0000",
        SAMPLE_DS_BARCODE,
        "VÝPIS Z DATABÁZE PŘIHLAŠOVACÍCH ÚDAJŮ",
        TITLE,
        L_USER,
        SAMPLE_WS_USER,
        L_PW,
        SAMPLE_WS_PASSWORD,
        "IDUB:",
        SAMPLE_IDUB,
        "Ubytovací zařízení:",
        SAMPLE_FACILITY_LINE1,
        SAMPLE_FACILITY_LINE2,
        "Poučení:",
        "1.",
        (
            "Tento účet slouží pro robotické vkládání dat prostřednictvím webové služby a "
            "nemůže být použit k jiným účelům."
        ),
        "2.",
        (
            "Ztratí-li nebo zapomene-li uživatel heslo, může požádat Ředitelství služby "
            "cizinecké policie o vygenerování nového hesla."
        ),
        "3.",
        "Uživatel se řídí provozním řádem Internetové aplikace Ubyport.",
        "4.",
        (
            "Při podezření na porušení provozního řádu Internetové aplikace Ubyport nebo "
            "jiné činnosti ohrožující kybernetickou"
        ),
        "bezpečnost může být uživatel zablokován.",
        f"V Praze dne {SAMPLE_EXTRACT_DATE}",
        "Vystavilo: Ředitelství služby cizinecké policie",
        "",
    ]
)
PW_SEPARATED = (
    "2099-8877-6655",
    "2099.8877.6655",
    "2099  8877  6655",
    "2099/8877/6655",
)
SOFT = "\u00ad"

FULLWIDTH = "".join(chr(0xFF10 + int(d)) for d in SAMPLE_IDUB)
ARABIC_INDIC = "١" * 12

ROWS = [
    # --- official layout ---
    ("official", OFFICIAL, OK_ALL),
    ("official_value_next_line", OFFICIAL_NEXT_LINE, OK_ALL),
    ("official_crlf", OFFICIAL.replace("\n", "\r\n"), OK_ALL),
    ("official_cr", OFFICIAL.replace("\n", "\r"), OK_ALL),
    ("official_nbsp", OFFICIAL.replace(": ", ": "), OK_ALL),
    ("official_narrow_nbsp_tab", OFFICIAL.replace(": ", ": \t "), OK_ALL),
    (
        "official_no_diacritics",
        f"Prihlasovaci jmeno: {SAMPLE_WS_USER}\nPristupove heslo: {FAKE_PW}\nIDUB: {SAMPLE_IDUB}\n",
        OK_ALL,
    ),
    ("official_full_body", FULL_BODY, OK_ALL),
    ("official_decomposed_labels", unicodedata.normalize("NFD", OFFICIAL), OK_ALL),
    # --- IDUB ---
    ("idub_11_digits", idub_only("12345678901"), exp(idub=UNREADABLE)),
    ("idub_15_digits", idub_only("123456789012345"), exp(idub=UNREADABLE)),
    ("idub_spaces_inside", idub_only("1234 5678 9012"), exp(idub=UNREADABLE)),
    ("idub_letter_o", idub_only("12345678901O"), exp(idub=UNREADABLE)),
    ("idub_letter_l", idub_only("12345678901l"), exp(idub=UNREADABLE)),
    ("idub_fullwidth", idub_only(FULLWIDTH), exp(idub=UNREADABLE)),
    ("idub_trailing_superscript", idub_only(SAMPLE_IDUB + "²"), exp(idub=UNREADABLE)),
    ("idub_words_after", idub_only(SAMPLE_IDUB + " (viz níže)"), exp(idub=UNREADABLE)),
    (
        "idub_trailing_period",
        idub_only(SAMPLE_IDUB + "."),
        exp(idub=found(SAMPLE_IDUB)),
    ),
    ("idub_trailing_comma", idub_only(SAMPLE_IDUB + ","), exp(idub=found(SAMPLE_IDUB))),
    ("idub_13_digits", idub_only("0000111122223"), exp(idub=found("0000111122223"))),
    ("idub_14_digits", idub_only("00001111222233"), exp(idub=found("00001111222233"))),
    ("idub_no_colon", f"IDUB {FAKE_IDUB}\n", exp(idub=found(FAKE_IDUB))),
    ("idub_lower_label", f"idub: {FAKE_IDUB}\n", exp(idub=found(FAKE_IDUB))),
    ("idub_xidub", f"XIDUB: {FAKE_IDUB}\n", exp()),
    ("idub_twice_same", idub_only(FAKE_IDUB) * 2, exp(idub=found(FAKE_IDUB))),
    (
        "idub_two_different",
        idub_only(FAKE_IDUB) + idub_only(SAMPLE_IDUB),
        exp(idub=UNREADABLE),
    ),
    (
        "idub_one_readable_one_not",
        idub_only(FAKE_IDUB) + idub_only("1234"),
        exp(idub=UNREADABLE),
    ),
    ("idub_two_lines_down", f"IDUB:\n\n{FAKE_IDUB}\n", exp(idub=UNREADABLE)),
    ("idub_on_password_line", f"Heslo a IDUB: {FAKE_IDUB}\n", exp(idub=UNREADABLE)),
    # --- extra numbers ignored ---
    (
        "extra_numbers",
        OFFICIAL
        + "Telefon: 420777000111\nPCR00DEMOsample001\n20261110120000\n"
        + "Účet: 123456789012/0100\nIČO: 12345678\n1234567890123\n",
        exp(UNREADABLE, found(SAMPLE_WS_USER), derived(SAMPLE_ZKRATKA)),
    ),
    ("extra_numbers_no_label", "420777000111\n20261110120000\nIČO: 12345678\n", exp()),
    # --- login ---
    (
        "login_plain",
        user_only("UBY-WS_ABCDE"),
        exp(user=found("UBY-WS_ABCDE"), mark=derived("ABCDE")),
    ),
    (
        "login_lower_six",
        user_only("uby-ws_abcde1"),
        exp(user=found("uby-ws_abcde1"), mark=derived("ABCDE1")),
    ),
    (
        "login_no_underscore",
        user_only("UBY-WSab12cd"),
        exp(user=found("UBY-WSab12cd"), mark=derived("AB12CD")),
    ),
    ("login_test_account", user_only("uby-tws1ab45"), exp(user=found("uby-tws1ab45"))),
    ("login_4_chars", user_only("UBY-WS_ABCD"), exp(user=UNREADABLE)),
    ("login_7_chars", user_only("UBY-WS_ABCDEFG"), exp(user=UNREADABLE)),
    ("login_other_shape", user_only("ub1234567"), exp(user=UNREADABLE)),
    ("login_no_underscore_5", user_only("UBY-WSabcde"), exp(user=UNREADABLE)),
    (
        "login_no_label",
        f"UBY-WS_ABCDE\nIDUB: {FAKE_IDUB}\n",
        exp(idub=found(FAKE_IDUB)),
    ),
    (
        "login_two_different",
        user_only("UBY-WS_ABCDE") + user_only("UBY-WS_VWXYZ"),
        exp(user=UNREADABLE),
    ),
    (
        "login_two_cases",
        user_only("UBY-WS_ABCDE") + user_only("uby-ws_abcde"),
        exp(user=found("UBY-WS_ABCDE"), mark=derived("ABCDE")),
    ),
    (
        "login_on_password_line",
        f"Heslo a {L_USER} UBY-WS_ABCDE\n",
        exp(user=UNREADABLE),
    ),
    (
        "login_password_word_en",
        f"Password / {L_USER} UBY-WS_ABCDE\n",
        exp(user=UNREADABLE),
    ),
    (
        "login_words_after",
        user_only("UBY-WS_ABCDE platí od zítra"),
        exp(user=UNREADABLE),
    ),
    # --- printed zkratka ---
    (
        "mark_equal_to_derived",
        OFFICIAL + f"{L_MARK} {SAMPLE_ZKRATKA}\n",
        OK_ALL,
    ),
    (
        "mark_equal_other_case",
        OFFICIAL + f"{L_MARK} {SAMPLE_ZKRATKA.lower()}\n",
        OK_ALL,
    ),
    (
        "mark_conflicts_with_login",
        OFFICIAL + f"{L_MARK} XYZ12\n",
        exp(found(SAMPLE_IDUB), CONFLICT, CONFLICT),
    ),
    ("mark_without_login", f"{L_MARK} ABCDE\n", exp()),
    ("mark_no_diacritics", "Zkratka ubytovaciho zarizeni: ABCDE\n", exp()),
    ("mark_label_split", "Zkratka ubytovacího\nzařízení: ABCDE\n", exp()),
    ("mark_lower_case", "zkratka ubytovacího zařízení: abcde\n", exp()),
    ("mark_six_chars", f"{L_MARK} AB12CD\n", exp()),
    ("mark_podle_prilohy", f"{L_MARK} podle přílohy\n", exp()),
    ("mark_then_heslo_line", f"{L_MARK}\nHeslo: {FAKE_PW}\n", exp()),
    ("mark_4_chars", f"{L_MARK} ABCD\n", exp()),
    ("mark_7_chars", f"{L_MARK} ABCDEFG\n", exp()),
    ("mark_with_c_caron", f"{L_MARK} ABCČE\n", exp()),
    (
        "mark_unreadable_blocks_derivation",
        OFFICIAL + f"{L_MARK} podle přílohy\n",
        exp(found(SAMPLE_IDUB), CONFLICT, CONFLICT),
    ),
    (
        "mark_ambiguous_blocks_derivation",
        OFFICIAL + f"{L_MARK} ABCDE\n{L_MARK} VWXYZ\n",
        exp(found(SAMPLE_IDUB), CONFLICT, CONFLICT),
    ),
    (
        "mark_bare_label_differs",
        OFFICIAL + "Zkratka: ABCDE\n",
        exp(found(SAMPLE_IDUB), CONFLICT, CONFLICT),
    ),
    (
        "mark_bare_label_equal",
        OFFICIAL + f"Zkratka: {SAMPLE_ZKRATKA.lower()}\n",
        OK_ALL,
    ),
    (
        "mark_bare_label_prose",
        OFFICIAL + "Zkratka často odpovídá části za UBY-WS_.\n",
        exp(found(SAMPLE_IDUB), UNREADABLE, MISSING),
    ),
    ("mark_bare_label_no_login", "Zkratka: ABCDE\n", exp()),
    (
        "mark_with_test_login",
        user_only("uby-tws1ab45") + f"{L_MARK} ABCDE\n",
        exp(user=found("uby-tws1ab45")),
    ),
    (
        "mark_with_unreadable_login",
        user_only("UBY-WS_ABCD") + f"{L_MARK} ABCDE\n",
        exp(user=UNREADABLE),
    ),
    # --- password never out ---
    (
        "password_looks_like_login",
        f"{TITLE}\n{L_USER} {SAMPLE_WS_USER}\n{L_PW} UBY-WS_ZZZZZ\nIDUB: {SAMPLE_IDUB}\n",
        exp(found(SAMPLE_IDUB), UNREADABLE, MISSING),
    ),
    ("password_only", f"{L_PW} UBY-WS_ZZZZZ\n", exp()),
    (
        "password_next_line_fake",
        f"{L_USER}\n{SAMPLE_WS_USER}\n{L_PW}\n{FAKE_PW}\nIDUB:\n{SAMPLE_IDUB}\n",
        OK_ALL,
    ),
    (
        "login_label_then_password_label",
        f"{L_USER}\n{L_PW}\nUBY-WS_ABCDE\n{FAKE_PW}\n",
        exp(user=UNREADABLE),
    ),
    # --- OCR-like noise ---
    (
        "noise_pipes_underscores",
        f"| {TITLE} |\n___\n| {L_USER} {SAMPLE_WS_USER}\n|\n_ {L_PW} {FAKE_PW}\n| IDUB: {SAMPLE_IDUB}\n_|_\n",
        OK_ALL,
    ),
    ("noise_doubled_spaces", OFFICIAL.replace(" ", "  "), OK_ALL),
    ("noise_soft_hyphen_title", OFFICIAL.replace("údaje", "úda­je"), OK_ALL),
    (
        "noise_capital_labels",
        f"PŘIHLAŠOVACÍ JMÉNO: {SAMPLE_WS_USER}\nPŘÍSTUPOVÉ HESLO: {FAKE_PW}\nIDUB: {SAMPLE_IDUB}\n",
        OK_ALL,
    ),
    ("noise_trailing_spaces", OFFICIAL.replace("\n", "   \n"), OK_ALL),
    # --- size ---
    ("size_empty", "", exp()),
    ("size_spaces_only", " \n\t   ", exp()),
    (
        "size_exactly_max",
        OFFICIAL + "\n" + "x" * (MAX_LETTER_CHARS - len(OFFICIAL) - 1),
        OK_ALL,
    ),
    ("size_over_max", OFFICIAL + "x" * (MAX_LETTER_CHARS - len(OFFICIAL) + 1), exp()),
    # --- never raises ---
    ("raise_none", None, exp()),
    ("raise_bytes", b"IDUB: 000011112222", exp()),
    ("raise_int", 12345, exp()),
    ("raise_lone_surrogate", "\ud800\n" + OFFICIAL + "\ud800", OK_ALL),
    ("raise_nul", "\x00\n" + OFFICIAL + "\x00", OK_ALL),
    ("raise_label_flood", "IDUB:" * 4000, exp(idub=UNREADABLE)),
    # --- unicode look-alikes ---
    ("lookalike_kelvin_login", user_only("UBY-WS_ABCDK"), exp(user=UNREADABLE)),
    ("lookalike_long_s_mark", f"{L_MARK} abcdſ\n", exp()),
    ("lookalike_kelvin_mark", f"{L_MARK} ABCDK\n", exp()),
    ("lookalike_arabic_indic_idub", idub_only(ARABIC_INDIC), exp(idub=UNREADABLE)),
    # --- attempt 2: review findings (rule 11) ---
    ("wrap_idub_digits", f"IDUB: {SAMPLE_IDUB}\n66", exp(idub=UNREADABLE)),
    ("wrap_idub_digits_next_line", f"IDUB:\n{SAMPLE_IDUB}\n66\n", exp(idub=UNREADABLE)),
    ("wrap_idub_word", f"IDUB: {SAMPLE_IDUB}\nPraha\n", exp(idub=found(SAMPLE_IDUB))),
    ("wrap_idub_noise_fragment", f"IDUB: {SAMPLE_IDUB}\n| 66\n", exp(idub=UNREADABLE)),
    ("wrap_login_letter", f"{L_USER} UBY-WS_ABCDE\nF", exp(user=UNREADABLE)),
    ("wrap_login_three_chars", f"{L_USER} UBY-WS_ABCDE\nF12\n", exp(user=UNREADABLE)),
    ("wrap_login_next_line", f"{L_USER}\nUBY-WS_ABCDE\nF\n", exp(user=UNREADABLE)),
    (
        "wrap_not_when_label_follows",
        f"{L_USER} UBY-WS_ABCDE\nTelefon: 420777000111\n",
        exp(user=found("UBY-WS_ABCDE"), mark=derived("ABCDE")),
    ),
    ("mark_next_line_adresa", "Zkratka ubytovacího zařízení\nAdresa\n", exp()),
    ("mark_next_line_praha", "Zkratka ubytovacího zařízení\nPraha\n", exp()),
    ("mark_next_line_hotel", "Zkratka ubytovacího zařízení:\nHotel\n", exp()),
    ("mark_next_line_valid_shape", f"{L_MARK}\nABCDE\n", exp()),
    (
        "mark_next_line_blocks_derivation",
        OFFICIAL + "Zkratka ubytovacího zařízení\nAdresa\n",
        exp(found(SAMPLE_IDUB), CONFLICT, CONFLICT),
    ),
    (
        "mark_bare_differs_from_login",
        user_only("UBY-WS_ABCDE") + "Zkratka: XYZWV\n",
        exp(user=CONFLICT, mark=CONFLICT),
    ),
    ("prose_idub_period", "V dotazu uveďte IDUB.\n420974841356", exp()),
    ("prose_idub_period_newline", "V dotazu uveďte IDUB.\n420974841356\n", exp()),
    ("prose_idub_comma", "Sdělte IDUB, 420974841356\n", exp()),
    ("prose_idub_question", "Znáte IDUB?\n420974841356\n", exp()),
    (
        "prose_idub_no_colon_next_line",
        "V dotazu uveďte IDUB\n420974841356\n",
        exp(idub=UNREADABLE),
    ),
    (
        "prose_idub_then_real",
        f"V dotazu uveďte IDUB.\n\nIDUB: {FAKE_IDUB}\n",
        exp(idub=found(FAKE_IDUB)),
    ),
    ("prose_login_period", f"Použijte {L_USER[:-1]}.\nUBY-WS_ABCDE\n", exp()),
    (
        "password_becomes_idub",
        f"{L_PW}\nIDUB:\n934857203948\n{SAMPLE_IDUB}",
        exp(idub=UNREADABLE),
    ),
    (
        "password_label_two_above_then_label",
        f"{L_PW}\n{L_USER}\nIDUB:\n934857203948\n",
        exp(idub=found("934857203948"), user=UNREADABLE),
    ),
    (
        "password_label_two_above_blank",
        f"{L_PW}\n\nIDUB:\n934857203948\n",
        exp(idub=found("934857203948")),
    ),
    (
        "password_label_above_login",
        f"{L_PW}\n{L_USER}\nUBY-WS_ZZZZZ\nUBY-WS_ABCDE\n",
        exp(user=UNREADABLE),
    ),
    (
        "idub_two_number_lines",
        f"IDUB:\n934857203948\n{SAMPLE_IDUB}\n",
        exp(idub=UNREADABLE),
    ),
    (
        "guard_inflection_heslem",
        f"Heslem je {L_USER} UBY-WS_ZZZZZ\n",
        exp(user=UNREADABLE),
    ),
    (
        "guard_inflection_hesla",
        f"Zadání hesla a IDUB: {FAKE_IDUB}\n",
        exp(idub=UNREADABLE),
    ),
    (
        "guard_capitals_no_diacritics",
        f"HESLEM je {L_USER} UBY-WS_ZZZZZ\n",
        exp(user=UNREADABLE),
    ),
    # --- attempt 3: global rules (rule 12) and the second review ---
    (
        "a3_column_labels",
        f"{L_USER}\n{L_PW}\n{SAMPLE_WS_USER}\nIDUB:\n934857203948\n\n{SAMPLE_IDUB}",
        exp(idub=UNREADABLE, user=UNREADABLE),
    ),
    (
        "a3_password_three_above",
        f"{L_PW}\n\n\nIDUB:\n934857203948\n\n{SAMPLE_IDUB}",
        exp(idub=UNREADABLE),
    ),
    # A single number after the IDUB label: found is unavoidable here. The
    # guards are the connection test (check-answers) and the host's tick.
    (
        "a3_single_number_after_password_label",
        f"{L_PW}\nIDUB: 934857203948",
        exp(idub=found("934857203948")),
    ),
    (
        "a3_number_above_label",
        f"{SAMPLE_IDUB}\nIDUB:\n934857203948\n{L_PW}",
        exp(idub=UNREADABLE),
    ),
    (
        "a3_login_above_label",
        f"{SAMPLE_WS_USER}\n{L_USER}\nUBY-WS_ZZZZZ\n{L_PW}",
        exp(user=UNREADABLE),
    ),
    ("a3_wrap_quote_idub", f"> IDUB: {SAMPLE_IDUB}\n> 66", exp(idub=UNREADABLE)),
    ("a3_wrap_bullet_idub", f"IDUB: {SAMPLE_IDUB}\n• 66", exp(idub=UNREADABLE)),
    ("a3_wrap_dash_idub", f"IDUB: {SAMPLE_IDUB}\n- 66", exp(idub=UNREADABLE)),
    ("a3_wrap_star_tab_idub", f"IDUB: {SAMPLE_IDUB}\n\t* 66", exp(idub=UNREADABLE)),
    (
        "a3_wrap_date_line_idub",
        f"IDUB: {SAMPLE_IDUB}\n15.04.2026\n",
        exp(idub=UNREADABLE),
    ),
    ("a3_wrap_quote_login", f"> {L_USER} UBY-WS_ABCDE\n> F", exp(user=UNREADABLE)),
    ("a3_wrap_bullet_login", f"{L_USER} UBY-WS_ABCDE\n• F1.\n", exp(user=UNREADABLE)),
    (
        "a3_mark_table_header",
        "Zkratka ubytovacího zařízení\tAdresa\n\nDEMO1\tHlavní 1",
        exp(),
    ),
    (
        "a3_mark_table_header_with_login",
        user_only(SAMPLE_WS_USER)
        + "Zkratka ubytovacího zařízení\tAdresa\n\nDEMO1\tHlavní 1",
        exp(user=CONFLICT, mark=CONFLICT),
    ),
    ("a3_mark_same_line_word", "Zkratka ubytovacího zařízení Praha", exp()),
    (
        "a3_mark_same_line_word_with_login",
        user_only(SAMPLE_WS_USER) + "Zkratka ubytovacího zařízení Praha",
        exp(user=CONFLICT, mark=CONFLICT),
    ),
    (
        "a3_mark_variant_zarizeni",
        user_only(SAMPLE_WS_USER) + "Zkratka zařízení: XYZ12",
        exp(user=CONFLICT, mark=CONFLICT),
    ),
    (
        "a3_mark_variant_ubyt",
        user_only(SAMPLE_WS_USER) + "Zkratka ubyt. zařízení: XYZ12",
        exp(user=CONFLICT, mark=CONFLICT),
    ),
    (
        "a3_mark_variant_uz",
        user_only(SAMPLE_WS_USER) + "Zkratka UZ: XYZ12",
        exp(user=CONFLICT, mark=CONFLICT),
    ),
    (
        "a3_mark_variant_next_line",
        user_only(SAMPLE_WS_USER) + "Zkratka:\nXYZ12",
        exp(user=CONFLICT, mark=CONFLICT),
    ),
    (
        "a3_mark_variant_inflected_capitals",
        user_only(SAMPLE_WS_USER) + "POUŽIJTE ZKRATKU XYZ12\n",
        exp(user=CONFLICT, mark=CONFLICT),
    ),
    (
        "a3_mark_variant_equal",
        user_only(SAMPLE_WS_USER) + f"Zkratka UZ: {SAMPLE_ZKRATKA}\n",
        exp(user=found(SAMPLE_WS_USER), mark=derived(SAMPLE_ZKRATKA)),
    ),
    (
        "a3_numeric_password",
        f"{L_USER} {SAMPLE_WS_USER}\n{L_PW} 934857203948\nIDUB: {SAMPLE_IDUB}\n",
        exp(UNREADABLE, found(SAMPLE_WS_USER), derived(SAMPLE_ZKRATKA)),
    ),
    (
        "a3_spaced_phone_number",
        OFFICIAL + "Telefon: +420 777 000 111\n",
        OK_ALL,
    ),
    (
        "a3_spaced_idub_and_other_number",
        "IDUB: 2099 8877 6655\nÚčet 934857203948\n",
        exp(idub=UNREADABLE),
    ),
    (
        "a3_number_without_label_then_prose",
        f"{SAMPLE_IDUB}\nVaše IDUB je výše\n",
        exp(idub=UNREADABLE),
    ),
    (
        "a3_login_prefix_mention",
        user_only("UBY-WS_ABCDE") + "Login začíná UBY-WS_\n",
        exp(user=UNREADABLE),
    ),
    # --- 1088: separated IDUB candidates (a numeric password) ---
    (
        "h_pw_chain_dash",
        f"IDUB: {SAMPLE_IDUB}\n{L_PW} 2099-8877-6655\n",
        exp(idub=UNREADABLE),
    ),
    (
        "h_pw_chain_dot",
        f"IDUB: {SAMPLE_IDUB}\n{L_PW} 2099.8877.6655\n",
        exp(idub=UNREADABLE),
    ),
    (
        "h_pw_chain_double_space",
        f"IDUB: {SAMPLE_IDUB}\n{L_PW} 2099  8877  6655\n",
        exp(idub=UNREADABLE),
    ),
    (
        "h_pw_chain_slash",
        f"IDUB: {SAMPLE_IDUB}\n{L_PW} 2099/8877/6655\n",
        exp(idub=UNREADABLE),
    ),
    ("h_idub_chain_alone", "IDUB: 2099-8877-6655\n", exp(idub=UNREADABLE)),
    # --- 1088: chains that are not candidates (placed before the letter: a
    # digit line right after the IDUB is the wrap guard, kept from 1083) ---
    ("h_plus_phone", "+420 777 000 111\n" + OFFICIAL, OK_ALL),
    (
        "h_plus_phone_unbroken",
        "+420777000111\n" + OFFICIAL,
        exp(UNREADABLE, found(SAMPLE_WS_USER), derived(SAMPLE_ZKRATKA)),
    ),
    ("h_plus_phone_callout", FULL_LETTER + f"{SAMPLE_CONTACT}\n", OK_ALL),
    ("h_ds_barcode", "380.0000.0000001\n" + OFFICIAL, OK_ALL),
    (
        "h_phone_without_plus",
        "420 777 000 111\n" + OFFICIAL,
        exp(UNREADABLE, found(SAMPLE_WS_USER), derived(SAMPLE_ZKRATKA)),
    ),
    (
        "h_barcode_other_shape",
        "380.0000.000001.1\n" + OFFICIAL,
        exp(UNREADABLE, found(SAMPLE_WS_USER), derived(SAMPLE_ZKRATKA)),
    ),
    # --- 1088: the full sample letter ---
    ("h_full_sample_letter", FULL_LETTER, OK_ALL),
    # --- 1088: dash and space logins ---
    (
        "h_login_en_dash",
        OFFICIAL + "UBY\u2013WS_DEMO1\n",
        exp(idub=found(SAMPLE_IDUB), user=UNREADABLE),
    ),
    (
        "h_login_spaced_dash",
        OFFICIAL + "UBY - WS_DEMO1\n",
        exp(idub=found(SAMPLE_IDUB), user=UNREADABLE),
    ),
    (
        "h_login_em_dash_lower",
        OFFICIAL + "uby\u2014ws_demo2\n",
        exp(idub=found(SAMPLE_IDUB), user=UNREADABLE),
    ),
    # --- 1088: mark conflict, 4 to 7 characters and soft hyphens ---
    (
        "h_mark_4",
        OFFICIAL + f"{L_MARK} DEMO\n",
        exp(found(SAMPLE_IDUB), CONFLICT, CONFLICT),
    ),
    (
        "h_mark_7",
        OFFICIAL + f"{L_MARK} DEMO1XY\n",
        exp(found(SAMPLE_IDUB), CONFLICT, CONFLICT),
    ),
    (
        "h_mark_soft_hyphen",
        OFFICIAL + f"{L_MARK} DE{SOFT}MO1\n",
        exp(found(SAMPLE_IDUB), CONFLICT, CONFLICT),
    ),
    (
        "h_mark_soft_hyphen_next_line",
        OFFICIAL + f"{L_MARK}\nDE{SOFT}MO1\n",
        exp(found(SAMPLE_IDUB), CONFLICT, CONFLICT),
    ),
    (
        "h_mark_unicode_5",
        OFFICIAL + f"{L_MARK} DĚMO1\n",
        exp(found(SAMPLE_IDUB), CONFLICT, CONFLICT),
    ),
    ("h_mark_same", OFFICIAL + f"{L_MARK} DEMO1\n", OK_ALL),
    ("h_mark_label_only", OFFICIAL + f"{L_MARK}\n", OK_ALL),
    # --- 1088: wrap guard ---
    (
        "h_login_wrapped_then_text",
        f"{L_USER} UBY-WS_ABCDE\nF    {L_PW} xx\n",
        exp(user=UNREADABLE),
    ),
    # --- 1088: text before a label ---
    (
        "h_text_before_label",
        f"{L_PW}\nXy7kLm9 IDUB: {SAMPLE_IDUB}\n",
        exp(idub=UNREADABLE),
    ),
    (
        "h_bullet_before_label",
        f"\u2022 IDUB: {SAMPLE_IDUB}\n",
        exp(idub=found(SAMPLE_IDUB)),
    ),
    ("h_pipe_before_label", f"| IDUB: {SAMPLE_IDUB}\n", exp(idub=found(SAMPLE_IDUB))),
    # --- 1088 attempt 2: runs inside chains, "+" runs, more separators ---
    (
        "h2_run_in_longer_chain",
        "IDUB: 934857203948\n\nevid. 209988776655/2026\n",
        exp(idub=UNREADABLE),
    ),
    (
        "h2_numeric_password_in_chain",
        f"{L_PW}\nIDUB: 934857203948\n\nDEMO1 209988776655 15 3\n",
        exp(idub=UNREADABLE),
    ),
    ("h2_plus_run", "IDUB: 934857203948\n\n+209988776655\n", exp(idub=UNREADABLE)),
    (
        "h2_plus_long_run",
        "IDUB: 934857203948\n\n+2099887766551234\n",
        exp(idub=UNREADABLE),
    ),
    (
        "h2_en_dash_chain",
        "IDUB: 934857203948\n\n1111\u20132222\u20133333\n",
        exp(idub=UNREADABLE),
    ),
    (
        "h2_spaced_hyphen_chain",
        "IDUB: 934857203948\n\n1111 - 2222 - 3333\n",
        exp(idub=UNREADABLE),
    ),
    ("h2_comma_chain", "IDUB: 934857203948\n\n1111,2222,3333\n", exp(idub=UNREADABLE)),
    (
        "h2_underscore_chain",
        "IDUB: 934857203948\n\n1111_2222_3333\n",
        exp(idub=UNREADABLE),
    ),
    (
        "h2_mark_soft_hyphen_in_label",
        OFFICIAL + f"Zkrat{SOFT}ka: XYZ12\n",
        exp(found(SAMPLE_IDUB), CONFLICT, CONFLICT),
    ),
]

STATUS = {
    "size_empty": "empty",
    "size_spaces_only": "empty",
    "size_over_max": "too_long",
    "raise_none": "empty",
    "raise_bytes": "empty",
    "raise_int": "empty",
}


def test_table_size_and_ids():
    assert len(ROWS) >= 50
    ids = [row[0] for row in ROWS]
    assert len(ids) == len(set(ids))
    assert set(STATUS) <= set(ids)
    assert len("IDUB:" * 4000) == MAX_LETTER_CHARS
    by_id = {row[0]: row[1] for row in ROWS}
    assert len(by_id["size_exactly_max"]) == MAX_LETTER_CHARS
    assert len(by_id["size_over_max"]) == MAX_LETTER_CHARS + 1


@pytest.mark.parametrize("row_id,text,expected", ROWS, ids=[row[0] for row in ROWS])
def test_parse_letter_table(row_id, text, expected):
    started = time.monotonic()
    result = parse_letter(text)
    elapsed = time.monotonic() - started

    assert isinstance(result, LetterResult)
    assert result.status == STATUS.get(row_id, "ok")
    assert tuple(result.fields) == FIELDS
    got = {
        name: (result.fields[name].state, result.fields[name].value) for name in FIELDS
    }
    assert got == expected
    for name in FIELDS:
        item = result.fields[name]
        assert isinstance(item, FieldResult)
        assert (item.value != "") == (item.state in FILLED_STATES)
        assert item.value.isascii()
    shown = repr(result)
    assert "Xy7kLm9" not in shown
    for name in FIELDS:
        item = result.fields[name]
        assert bool(item.source) == (item.state in FILLED_STATES)
        for part in item.source:
            assert len(part) <= 120
            assert SAMPLE_WS_PASSWORD not in part
            assert FAKE_PW not in part
            assert not any(pw in part for pw in PW_SEPARATED)
    assert SAMPLE_WS_PASSWORD not in shown
    assert FAKE_PW not in shown
    assert "UBY-WS_ZZZZZ" not in shown
    assert elapsed < 1.0
    # Purity: the same input twice gives equal results.
    assert parse_letter(text) == result


def test_lines_and_labels():
    result = parse_letter(OFFICIAL)
    idub = result.fields["uby_idub"]
    user = result.fields["uby_ws_user"]
    mark = result.fields["uby_mark"]
    assert (idub.line, idub.label, idub.lines) == (4, "IDUB", (4,))
    assert (user.line, user.label, user.lines) == (2, "Přihlašovací jméno", (2,))
    assert (mark.state, mark.line, mark.label) == ("derived", 2, "Přihlašovací jméno")

    two = parse_letter(idub_only(FAKE_IDUB) + "\n" + idub_only(SAMPLE_IDUB)).fields[
        "uby_idub"
    ]
    assert (two.state, two.value, two.line, two.lines) == ("unreadable", "", 1, (1, 3))

    conflict = parse_letter(OFFICIAL + f"{L_MARK} XYZ12\n")
    assert conflict.fields["uby_ws_user"].lines == (2, 5)
    assert conflict.fields["uby_mark"].lines == (2, 5)
    assert conflict.fields["uby_mark"].line is None

    bad = parse_letter("x\n" + idub_only("1234")).fields["uby_idub"]
    assert (bad.state, bad.line, bad.label) == ("unreadable", 2, "IDUB")


def test_source_slices():
    same = parse_letter(OFFICIAL).fields
    assert same["uby_idub"].source == (f"IDUB: {SAMPLE_IDUB}",)
    assert same["uby_ws_user"].source == (f"{L_USER} {SAMPLE_WS_USER}",)
    assert same["uby_mark"].source == same["uby_ws_user"].source

    below = parse_letter(OFFICIAL_NEXT_LINE).fields
    assert below["uby_idub"].source == ("IDUB:", SAMPLE_IDUB)
    assert below["uby_ws_user"].source == (L_USER, SAMPLE_WS_USER)
    assert below["uby_mark"].source == below["uby_ws_user"].source

    # Noise before the label is not part of the slice.
    noisy = parse_letter(f"| IDUB: {SAMPLE_IDUB}\n").fields["uby_idub"]
    assert noisy.source == (f"IDUB: {SAMPLE_IDUB}",)

    # A 200-character label line is cut to 120.
    long_line = "IDUB" + " " * 182 + f": {SAMPLE_IDUB}"
    assert len(long_line) == 200
    cut = parse_letter(long_line + "\n").fields["uby_idub"]
    assert (cut.state, cut.value) == ("found", SAMPLE_IDUB)
    assert cut.source == (long_line[:120],)

    # Every state that is not filled has no source.
    for text in (
        "x\n" + idub_only("1234"),
        OFFICIAL + f"{L_MARK} XYZ12\n",
        f"{L_PW}\nXy7kLm9 IDUB: {SAMPLE_IDUB}\n",
        f"Heslo IDUB:\n{SAMPLE_IDUB}\n",
    ):
        for item in parse_letter(text).fields.values():
            if item.state not in FILLED_STATES:
                assert item.source == ()


def test_results_are_frozen():
    result = parse_letter(OFFICIAL)
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.status = "empty"
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.fields["uby_idub"].value = "1"


def test_no_network(monkeypatch):
    def boom(*_args, **_kwargs):
        raise AssertionError("the parser must not open a socket")

    monkeypatch.setattr(socket, "socket", boom)
    result = parse_letter(FULL_BODY)
    got = {
        name: (result.fields[name].state, result.fields[name].value) for name in FIELDS
    }
    assert got == OK_ALL


def test_label_flood_is_fast():
    started = time.monotonic()
    result = parse_letter("IDUB:" * 4000)
    assert time.monotonic() - started < 1.0
    assert result.status == "ok"
    assert result.fields["uby_idub"].state == "unreadable"
    started = time.monotonic()
    parse_letter("IDUB" + " " * (MAX_LETTER_CHARS - 5) + "x")
    assert time.monotonic() - started < 1.0


class RaisingForm:
    def get(self, _key):
        raise RuntimeError("boom")


ALL = "uby_idub,uby_ws_user,uby_mark"

CONFIRMED_ROWS = [
    ("none_form", None, ([], [])),
    ("empty_form", {}, ([], [])),
    ("raising_form", RaisingForm(), ([], [])),
    ("fields_none", {"letter_fields": None}, ([], [])),
    (
        "fields_list",
        {"letter_fields": ["uby_idub"], "letter_ok": "1"},
        ([], []),
    ),
    ("fields_bytes", {"letter_fields": b"uby_idub"}, ([], [])),
    ("all_ticked", {"letter_fields": ALL, "letter_ok": "1"}, (list(FIELDS), [])),
    ("none_ticked", {"letter_fields": ALL}, (list(FIELDS), list(FIELDS))),
    (
        "stale_per_field_ticks",
        {
            "letter_fields": ALL,
            "letter_ok_uby_idub": "1",
            "letter_ok_uby_ws_user": "1",
            "letter_ok_uby_mark": "1",
        },
        (list(FIELDS), list(FIELDS)),
    ),
    ("tick_zero", {"letter_fields": "uby_idub", "letter_ok": "0"}, (["uby_idub"], ["uby_idub"])),
    ("tick_on", {"letter_fields": "uby_idub", "letter_ok": "on"}, (["uby_idub"], ["uby_idub"])),
    ("tick_bytes", {"letter_fields": "uby_idub", "letter_ok": b"1"}, (["uby_idub"], ["uby_idub"])),
    ("tick_int", {"letter_fields": "uby_idub", "letter_ok": 1}, (["uby_idub"], ["uby_idub"])),
    ("tick_list", {"letter_fields": "uby_idub", "letter_ok": ["1"]}, (["uby_idub"], ["uby_idub"])),
    (
        "unknown_ignored_order_duplicates",
        {"letter_fields": "uby_mark, password,uby_idub,uby_mark,,uby_ws_password", "letter_ok": "1"},
        (["uby_idub", "uby_mark"], []),
    ),
    ("tick_with_nothing_listed", {"letter_fields": "", "letter_ok": "0"}, ([], [])),
]


@pytest.mark.parametrize(
    "row_id,form,expected", CONFIRMED_ROWS, ids=[r[0] for r in CONFIRMED_ROWS]
)
def test_confirmed_fields_table(row_id, form, expected):
    assert confirmed_fields(form) == expected


LINE_ROWS = [
    ("seven", "7", 7),
    ("one", "1", 1),
    ("max", "100000", 100000),
    ("leading_zero", "007", 7),
    ("over_max", "100001", None),
    ("zero", "0", None),
    ("negative", "-1", None),
    ("exponent", "1e3", None),
    ("huge", "999999999", None),
    ("letters", "abc", None),
    ("empty", "", None),
    ("arabic_indic", "٣", None),
    ("superscript", "²", None),
    ("spaces", " 7 ", None),
    ("plus", "+7", None),
    ("none", None, None),
    ("list", ["7"], None),
    ("bytes", b"7", None),
    ("int", 7, None),
]


@pytest.mark.parametrize(
    "row_id,raw,expected", LINE_ROWS, ids=[r[0] for r in LINE_ROWS]
)
def test_line_from_form_table(row_id, raw, expected):
    assert line_from_form({"letter_line_uby_idub": raw}, "uby_idub") == expected


def test_line_from_form_never_raises():
    assert line_from_form(None, "uby_idub") is None
    assert line_from_form({}, "uby_idub") is None
    assert line_from_form(RaisingForm(), "uby_idub") is None
    assert line_from_form({"letter_line_uby_mark": "7"}, "uby_idub") is None


def test_nfc_never_turns_a_character_into_ascii():
    from app.police_letter import _NFC_KEEP, _normalise

    to_ascii = {
        chr(cp)
        for cp in range(0x80, 0x110000)
        if unicodedata.normalize("NFC", chr(cp)).isascii()
    }
    assert to_ascii == set(_NFC_KEEP)
    for char in to_ascii:
        assert _normalise(f"a{char}b") == f"a{char}b"
