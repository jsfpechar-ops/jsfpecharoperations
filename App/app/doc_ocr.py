"""Document scanning (OCR): read a guest's passport photo into form fields.

A suggestion, never a record: the photo the guest already chose for the
upload step is sent to the model, the read comes back as form values, and
nothing is stored by this module - no row, no file, no log of the read
text. The guest sees the filled fields and corrects them before saving.

Max plan only (the pricing copy promises scanning on Max, and explicitly
not during the trial), behind ``UBYHOST_AI_FEATURES`` listing ``doc_ocr``
and the Anthropic provider, whose message format carries the image.
"""
from __future__ import annotations

import base64
import io
from typing import Any, Dict

from . import ai, billing, config, passport_photos, validation
from .ai import AIError

FEATURE = "doc_ocr"

# Anthropic's own ceiling for one image; larger pictures gain no accuracy.
MAX_EDGE = 1568
JPEG_QUALITY = 80

SYSTEM_BLOCKS = [
    (
        "You read photos of travel documents (passports and ID cards) for a "
        "check-in form. Read only what is printed on the document, preferring "
        "the two machine-readable lines at the bottom when they are legible. "
        "Use Latin letters exactly as printed there. Never guess or invent: "
        "when a field is not legible, return an empty string for it."
    ),
    (
        "Reply with one JSON object and nothing else, with exactly these "
        "string fields: surname, first_name, birth_date, nationality, "
        "doc_number. surname and first_name: uppercase Latin letters as in "
        "the machine-readable zone. birth_date: YYYY-MM-DD. nationality: the "
        "ISO 3166-1 alpha-3 country code of the issuing state. doc_number: "
        "the document number with no spaces. Empty string for anything you "
        "cannot read with confidence."
    ),
]

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["surname", "first_name", "birth_date", "nationality", "doc_number"],
    "properties": {
        "surname": {"type": "string"},
        "first_name": {"type": "string"},
        "birth_date": {"type": "string"},
        "nationality": {"type": "string"},
        "doc_number": {"type": "string"},
    },
}


class BadDocument(ValueError):
    """The upload is not an image this module can read (a PDF, for example)."""


def available(apartment) -> bool:
    """True when this property's guest form may offer the scan button.

    The gates, in order: the feature flag and key, the provider (the image
    travels in Anthropic's content blocks; the Mistral path sends text only),
    the owner's test-list entry, and the Max subscription - active, not a
    trial, matching what the pricing card promises.
    """
    if config.AI_PROVIDER != "anthropic":
        return False
    if not ai.enabled(FEATURE):
        return False
    owner_id = apartment["owner_user_id"] if apartment else None
    if owner_id is None or not ai.on_test_list_by_id(owner_id):
        return False
    ent = billing.entitlements(int(owner_id))
    return ent.status == "active" and ent.plan == "max"


def prepare_image(content: bytes, content_type: str) -> bytes:
    """A clean, metadata-free JPEG no larger than MAX_EDGE on its long side."""
    from PIL import Image

    ctype = passport_photos.validate_upload(content, content_type)
    if ctype == passport_photos.ALLOWED_PDF_TYPE:
        raise BadDocument("pdf")
    clean = passport_photos.reencode_image(content)
    with Image.open(io.BytesIO(clean)) as image:
        width, height = image.size
        scale = MAX_EDGE / max(width, height)
        if scale < 1:
            image = image.resize((max(1, round(width * scale)), max(1, round(height * scale))))
        out = io.BytesIO()
        image.save(out, format="JPEG", quality=JPEG_QUALITY)
    return out.getvalue()


def _clean(parsed: Dict[str, Any]) -> Dict[str, str]:
    countries = validation.country_codes()
    nationality = (parsed.get("nationality") or "").strip().upper()[:3]
    if nationality not in countries:
        nationality = ""
    birth = (parsed.get("birth_date") or "").strip()
    if len(birth) == 10 and birth[4] == "-" and birth[7] == "-":
        # The model replies ISO (YYYY-MM-DD); the form speaks DD.MM.YYYY.
        birth = f"{birth[8:10]}.{birth[5:7]}.{birth[0:4]}"
    return {
        "surname": validation.normalise_name(parsed.get("surname")),
        "first_name": validation.normalise_name(parsed.get("first_name")),
        "birth_date": validation.normalise_birth_date(birth),
        "nationality": nationality,
        "doc_number": validation.normalise_document(parsed.get("doc_number")),
    }


def read_document(jpeg: bytes, key: str) -> Dict[str, str]:
    """The document's fields as normalised form values; nothing is stored."""
    data = base64.b64encode(jpeg).decode("ascii")
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/jpeg", "data": data},
                },
                {"type": "text", "text": "Read this travel document."},
            ],
        }
    ]
    parsed = ai.call(FEATURE, SYSTEM_BLOCKS, messages, SCHEMA, key=key, max_tokens=1000)
    return _clean(parsed if isinstance(parsed, dict) else {})


__all__ = ["FEATURE", "BadDocument", "available", "prepare_image", "read_document", "AIError"]
