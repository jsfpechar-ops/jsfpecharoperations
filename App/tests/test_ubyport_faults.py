"""Fault table and police-code words for the host (brief A1b P2)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from app import host_i18n
from app.ubyport import errors as uby_errors
from app.ubyport import faults

REPO = Path(__file__).resolve().parents[2]
GOLDEN = REPO / "go" / "internal" / "ubyport" / "testdata" / "fault_table.json"
ROW_NO_ERRORS = "Odpověď neobsahuje záznamy o chybách"
ROW_RUNTIME = "Chyba běhu programu"


def test_fault_code_for_rows_and_unknown():
    assert faults.code_for("fault", f"x {ROW_NO_ERRORS} y") == "uby_runtime_no_errors"
    assert faults.code_for("fault", ROW_RUNTIME.upper()) == "uby_runtime"
    assert faults.code_for("fault", "Length cannot be less than zero") is None
    assert faults.code_for("http4xx", "HTTP 404") == "http_404"
    assert faults.code_for("dial", "x") is None


def test_fault_host_copy_keys_and_capped_text():
    assert faults.host_copy_key("fault", ROW_RUNTIME) == "ubyport.fault.uby_runtime"
    assert faults.host_copy_key("fault", "something new") == "ubyport.fault.unknown"
    assert faults.host_copy_key("dial", ROW_RUNTIME) is None
    assert len(faults.host_detail("a" * 500)) == faults.FAULT_DETAIL_CAP


def test_host_lines_seed_codes_in_three_languages():
    for lang in ("en", "cs", "vi"):
        table = host_i18n.STRINGS[lang]
        lines = uby_errors.host_lines("", "112;106", lang)
        assert lines == [
            (table["ubyport.code.112.text"], table["ubyport.code.112.action"]),
            (table["ubyport.code.106.text"], table["ubyport.code.106.action"]),
        ]
        assert all(text and action for text, action in lines)


def test_unknown_code_quotes_police_text_with_code():
    codebook = {"ERR_CZE_555": "Neznámá položka"}
    lines = uby_errors.host_lines("", "ERR_CZE_555", "en", codebook)
    assert len(lines) == 1
    assert "Neznámá položka" in lines[0][0]
    assert "(police code 555)" in lines[0][0]
    assert "“Neznámá položka”" in lines[0][0]


def test_unknown_fault_falls_back_to_capped_text():
    text = host_i18n.STRINGS["en"]["ubyport.fault.unknown"] % {
        "detail": faults.host_detail("x" * 400)
    }
    assert "x" * faults.FAULT_DETAIL_CAP in text
    assert "x" * (faults.FAULT_DETAIL_CAP + 1) not in text


def test_ubyport_copy_has_no_em_dash():
    for lang in ("en", "cs", "vi"):
        for key, value in host_i18n.STRINGS[lang].items():
            if key.startswith("ubyport."):
                assert "—" not in str(value), (lang, key)


def test_fault_table_python_go_same_rows():
    expected = [{"key": k, "match": m, "text_key": t} for k, m, t in faults.FAULT_ROWS]
    assert json.loads(GOLDEN.read_text(encoding="utf-8")) == expected
    assert [row["key"] for row in expected] == ["uby_runtime_no_errors", "uby_runtime"]
    scripts = str(REPO / "App" / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    import ubyport_fault_golden

    assert ubyport_fault_golden.table() == expected
