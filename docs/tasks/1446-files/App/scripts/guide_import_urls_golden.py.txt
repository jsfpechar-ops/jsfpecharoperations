"""Write go/internal/web/ai/testdata/guide_import_urls.json: what the Python
guest_guide_import.normalise_url answers for a list of links, for the Go port in
go/internal/web/ai/guide_import.go to repeat.

    python3 scripts/guide_import_urls_golden.py          write the file
    python3 scripts/guide_import_urls_golden.py --check  exit 1 when the file is stale

A link Python cannot parse at all (urlsplit raises ValueError, a 500 on the
route) is recorded with "error": "ValueError"; the Go port refuses those as a
bad link instead.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
OUT = APP_DIR.parent / "go" / "internal" / "web" / "ai" / "testdata" / "guide_import_urls.json"
sys.path.insert(0, str(APP_DIR))

from app import guest_guide_import as gi  # noqa: E402

CASES = [
    "https://www.booking.com/hotel/cz/vivus-3.cs.html?aid=1#x",
    "https://booking.com/hotel/DE/Hotel_Name.html",
    "https://m.booking.com/hotel/at/a.html",
    "https://www.booking.com/hotel/cz/a.html/",
    "https://www.booking.com/searchresults.html",
    "https://www.booking.com/hotel/cz/-bad.html",
    "https://www.booking.com/hotel/cze/a.html",
    "https://www.airbnb.com/rooms/53997462?adults=2",
    "https://www.airbnb.co.uk/rooms/plus/123/",
    "https://airbnb.cz/rooms/9",
    "https://m.airbnb.com.au/rooms/9/",
    "https://www.airbnb.com/rooms/abc",
    "https://www.airbnb.com/s/Prague",
    "https://www.airbnb.org/rooms/1",
    "  https://www.airbnb.com/rooms/123  ",
    "HTTPS://WWW.AIRBNB.COM/rooms/5",
    "https://WWW.Booking.com./hotel/cz/a.html",
    "http://www.airbnb.com/rooms/1",
    "ftp://www.airbnb.com/rooms/1",
    "//www.airbnb.com/rooms/1",
    "www.airbnb.com/rooms/1",
    "https://user@www.airbnb.com/rooms/1",
    "https://www.airbnb.com@evil.example/rooms/1",
    "https://www.airbnb.com:443/rooms/1",
    "https://www.airbnb.com:0/rooms/1",
    "https://www.airbnb.com:/rooms/1",
    "https://www.airbnb.com:abc/rooms/1",
    "https://www.airbnb.com:99999/rooms/1",
    "https://www.airbnb.com\\@evil.example/rooms/1",
    "https://www.airbnb.com/rooms/1 2",
    "https://www.airbnb.com/rooms/1\n",
    "https://www.airbnb.com/rooms/1\t",
    "\x01https://www.airbnb.com/rooms/1",
    "https://[::1]/rooms/1",
    "https://[::1/rooms/1",
    "https://127.0.0.1/rooms/1",
    "https://2130706433/rooms/1",
    "https://1.2.3.4./hotel/cz/a.html",
    "https://.",
    "https://",
    "https:///rooms/1",
    "https://www.airbnb.com",
    "https://www.airbnb.cz/rooms/1#frag",
    "https://www.airbnb.com/rooms/1?x=https://evil.example",
    "https://www.airbnb.com/rooms/%31",
    "https://www.airbnb.com/rooms/１２３",
    "https://www.airbnb.com/rooms/" + "9" * 20,
    "https://www.airbnb.com/rooms/" + "9" * 21,
    "https://www.example.com/rooms/1",
    "",
    "   ",
    "https://www.airbnb.com/rooms/1/" + "a" * 2100,
]


def render() -> str:
    out = []
    for raw in CASES:
        row = {"input": raw}
        try:
            row.update(gi.normalise_url(raw))
        except gi.GuideImportError as exc:
            row["error"] = exc.key
        except ValueError:
            row["error"] = "ValueError"
        out.append(row)
    return json.dumps(out, ensure_ascii=False, indent=1) + "\n"


def main(argv: list) -> int:
    text = render()
    current = OUT.read_text(encoding="utf-8") if OUT.exists() else None
    if "--check" in argv:
        if current != text:
            print(f"stale: {OUT}")
            return 1
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
