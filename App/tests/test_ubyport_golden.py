"""0477: the ZapisUbytovane request bytes are pinned before the Go port.

The golden files in tests/golden/ubyport are the bytes Python sends today for
the invented cases in cases.json. The Go port must produce the same bytes from
the same inputs. Regenerate with scripts/ubyport_golden.py only after a
deliberate, reviewed change to the wire format.
"""
from __future__ import annotations

import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from app import auth, db, reporting
from app.ubyport import client as client_module
from app.ubyport import soap
from app.ubyport.client import UbyportClient

APP_DIR = Path(__file__).resolve().parents[1]
GOLDEN = APP_DIR / "tests" / "golden" / "ubyport"
GENERATOR = APP_DIR / "scripts" / "ubyport_golden.py"


def _committed_cases():
    return json.loads((GOLDEN / "cases.json").read_text(encoding="utf-8"))


def test_regenerated_envelopes_match_committed_files_byte_for_byte(tmp_path):
    subprocess.run(
        [sys.executable, str(GENERATOR), "--out", str(tmp_path)],
        check=True,
        capture_output=True,
    )
    committed = sorted(GOLDEN.glob("*.xml"))
    regenerated = sorted(tmp_path.glob("*.xml"))
    assert [p.name for p in regenerated] == [p.name for p in committed]
    assert len(committed) == len(_committed_cases())
    for path in committed:
        assert (tmp_path / path.name).read_bytes() == path.read_bytes(), path.name


def test_every_committed_envelope_is_well_formed_xml():
    files = sorted(GOLDEN.glob("*.xml"))
    assert len(files) >= 6
    for path in files:
        ET.fromstring(path.read_bytes())


# --- through the real submit path -----------------------------------------

SUCCESS_RESPONSE = """<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
  <s:Header />
  <s:Body>
    <ZapisUbytovaneResponse xmlns="http://UBY.pcr.cz/WS_UBY">
      <ZapisUbytovaneResult xmlns:a="http://schemas.datacontract.org/2004/07/WS_UBY"
 xmlns:i="http://www.w3.org/2001/XMLSchema-instance">
        <a:ChybyHlavicky></a:ChybyHlavicky>
        <a:ChybyZaznamu xmlns:b="http://schemas.microsoft.com/2003/10/Serialization/Arrays">
          <b:string>;</b:string>
        </a:ChybyZaznamu>
        <a:DokumentChybyPotvrzeni i:nil="true" />
        <a:DokumentPotvrzeni i:nil="true" />
        <a:PseudoRazitko>F8EA613D-C8C5-4671-924D-EE4F8588E08D</a:PseudoRazitko>
      </ZapisUbytovaneResult>
    </ZapisUbytovaneResponse>
  </s:Body>
</s:Envelope>"""


def _seed_owned(username: str, token: str):
    from tests.test_send_controls import _seed

    db.init_db()
    existing = db.query_one("SELECT id FROM user_account WHERE username = ?", (username,))
    owner_id = (
        existing["id"]
        if existing
        else auth.create_account(f"{username}@example.test", "Golden Owner", username=username)
    )
    apartment, _reservation, guest_id = _seed("manual", token, owner_user_id=owner_id)
    return apartment, guest_id


def _cleanup(apartment):
    apartment_id = apartment["id"]
    db.execute("DELETE FROM alert WHERE apartment_id = ?", (apartment_id,))
    db.execute("DELETE FROM submission WHERE apartment_id = ?", (apartment_id,))
    db.execute(
        "DELETE FROM guest WHERE reservation_id IN "
        "(SELECT id FROM reservation WHERE apartment_id = ?)",
        (apartment_id,),
    )
    db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apartment_id,))
    db.execute("DELETE FROM apartment WHERE id = ?", (apartment_id,))
    db.execute("DELETE FROM legal_entity WHERE id = ?", (apartment["legal_entity_id"],))


def test_the_envelope_leaving__post_matches_the_golden_builder_for_the_db_rows(monkeypatch):
    apartment, _guest_id = _seed_owned("golden-0477", "tok-golden-0477")
    try:
        real = UbyportClient("https://ubyport.invalid", use_ntlm=False)
        captured = []

        def capture(_self, *args):
            captured.extend(a for a in args if isinstance(a, str) and a.startswith("<?xml"))
            return SUCCESS_RESPONSE

        monkeypatch.setattr(UbyportClient, "_post", capture)
        monkeypatch.setattr(reporting, "client_for", lambda *_a, **_k: real)
        monkeypatch.setattr(reporting.validation, "validate_apartment", lambda _a: [])
        pairs = reporting.collect_sendable(apartment["id"], ignore_automation=True)
        assert pairs, "the seeded guest must be sendable"
        reporting.submit_batch(apartment, pairs, mode="manual")

        assert len(captured) == 1
        expected = soap.build_zapis_ubytovane(
            reporting.header_from_apartment(apartment),
            [reporting.guest_payload(g, r) for g, r in pairs],
            real.auth_code,
            client_module.include_wsa_header(),
        )
        assert captured[0] == expected
    finally:
        _cleanup(apartment)
