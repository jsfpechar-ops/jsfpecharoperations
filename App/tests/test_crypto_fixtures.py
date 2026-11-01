"""Drift guard for the Go crypto port: the committed fixtures must match the Python oracle."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from cryptography.fernet import Fernet, MultiFernet
from itsdangerous import URLSafeTimedSerializer

APP = Path(__file__).resolve().parents[1]
SCRIPT = APP / "scripts" / "crypto_fixtures.py"
COMMITTED = APP.parent / "go" / "internal" / "secure" / "testdata" / "fixtures.json"


def test_fixtures_match_generator(tmp_path):
    out = tmp_path / "fixtures.json"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--out", str(out)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "fixtures written: 19"
    assert out.read_text(encoding="utf-8") == COMMITTED.read_text(encoding="utf-8")


def test_python_decrypts_and_loads_committed_tokens():
    data = json.loads(COMMITTED.read_text(encoding="utf-8"))
    keys = data["keys"]
    for case in data["fernet"]:
        plain = bytes.fromhex(case["plaintext_hex"])
        for label, token in case["tokens"].items():
            fernet = Fernet(keys[label].encode("ascii"))
            assert fernet.decrypt(token.encode("ascii"), ttl=None) == plain

    mf = data["multifernet"]
    multi = MultiFernet([Fernet(k.encode("ascii")) for k in mf["keys"]])
    for token in mf["tokens"].values():
        assert multi.decrypt(token.encode("ascii"), ttl=None) == bytes.fromhex(
            mf["plaintext_hex"]
        )

    for case in data["signer"]:
        serializer = URLSafeTimedSerializer(data["secret"], salt=case["salt"])
        assert serializer.loads(case["token"], max_age=None) == case["value"]
