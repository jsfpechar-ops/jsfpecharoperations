"""Write the golden JSON for the Go iCal parser fixtures.

Run from App/: .venv/bin/python scripts/ical_golden.py
Each go/internal/ical/testdata/<name>.ics gets <name>.json: the output of
parse_events, or {"error": true} when it raises. The Go parser must match
these bytes.
"""

import json
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
TESTDATA = APP_DIR.parent / "go" / "internal" / "ical" / "testdata"
sys.path.insert(0, str(APP_DIR))

from app.icalsync import parse_events  # noqa: E402


def render(ics_text: str) -> str:
    try:
        payload = parse_events(ics_text)
    except Exception:
        payload = {"error": True}
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def generate(source: Path, target: Path) -> None:
    for ics in sorted(source.glob("*.ics")):
        text = ics.read_bytes().decode("utf-8")
        (target / f"{ics.stem}.json").write_text(render(text), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    generate(TESTDATA, TESTDATA)
