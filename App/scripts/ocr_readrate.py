"""Read-rate check for passport photos (run by the owner, locally).

Usage: python scripts/ocr_readrate.py DIR

Runs doc_ocr.prepare_image and doc_ocr.read_document on every jpg, jpeg or png
in DIR and prints only the file index, the outcome and the seconds taken.
Photos are the owner's own test passports and never go in the repo.
The output holds no field value, filename or MRZ text.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import doc_ocr  # noqa: E402

_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}


def main(argv: list[str]) -> int:
    folder = Path(argv[1])
    files = sorted(p for p in folder.iterdir() if p.suffix.lower() in _TYPES)
    ok = 0
    for index, path in enumerate(files, start=1):
        started = time.monotonic()
        try:
            jpeg = doc_ocr.prepare_image(path.read_bytes(), _TYPES[path.suffix.lower()])
            doc_ocr.read_document(jpeg)
            status = "ok"
        except (doc_ocr.BadDocument, OSError):
            status = "bad_file"
        except doc_ocr.NothingRead:
            status = "nothing_read"
        if status == "ok":
            ok += 1
        print(f"{index} {status} {time.monotonic() - started:.1f}s")
    percent = 100 * ok / len(files) if files else 0
    print(f"read {ok} of {len(files)} ({percent:.0f}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
