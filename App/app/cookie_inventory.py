"""One inventory of the cookies and local storage the app sets (FE-4).

The public privacy pages render this, and ``tests/test_cookie_inventory.py``
checks that no cookie or storage key is set anywhere in the app without a row
here. ``party`` is ``first`` or ``Cloudflare``; ``kind`` is ``cookie`` or
``localStorage``. Purpose and lifetime carry both languages in one place.
"""
from __future__ import annotations

from typing import Dict, Tuple

COOKIE_INVENTORY: Tuple[Dict[str, object], ...] = (
    {
        "name": "ubyhost_session",
        "set_by": "auth.py:attach_session",
        "party": "first",
        "kind": "cookie",
        "surface": "host",
        "purpose": {"en": "Keeps you signed in", "cs": "Udržuje přihlášení"},
        "lifetime": {
            "en": "12 hours, or 30 days with \u201cremember me\u201d",
            "cs": "12 hodin, nebo 30 dní s \u201ezapamatovat si m\u011b\u201c",
        },
    },
    {
        "name": "ubyhost_csrf",
        "set_by": "security.py:attach_csrf_cookie",
        "party": "first",
        "kind": "cookie",
        "surface": "host",
        "purpose": {
            "en": "Protects forms against cross-site requests",
            "cs": "Chr\u00e1n\u00ed formul\u00e1\u0159e p\u0159ed po\u017eadavky z jin\u00fdch str\u00e1nek",
        },
        "lifetime": {
            "en": "Matches the session, up to 30 days",
            "cs": "Shodn\u00e9 s relac\u00ed, a\u017e 30 dn\u00ed",
        },
    },
    {
        "name": "ubyhost_lang",
        "set_by": "host_i18n.py:remember_language",
        "party": "first",
        "kind": "cookie",
        "surface": "public",
        "purpose": {"en": "Remembers your language", "cs": "Pamatuje si v\u00e1\u0161 jazyk"},
        "lifetime": {"en": "180 days", "cs": "180 dn\u00ed"},
    },
    {
        "name": "ubyhost_pin",
        "set_by": "auth.py:attach_pin_session",
        "party": "first",
        "kind": "cookie",
        "surface": "guest",
        "purpose": {
            "en": "Keeps your guest stay access on this device",
            "cs": "Udr\u017euje p\u0159\u00edstup k pobytu na tomto za\u0159\u00edzen\u00ed",
        },
        "lifetime": {"en": "7 days", "cs": "7 dn\u00ed"},
    },
    {
        "name": "ubyhost_owned",
        "set_by": "routes/guest.py:remember_owned",
        "party": "first",
        "kind": "cookie",
        "surface": "guest",
        "purpose": {
            "en": "Remembers which forms this device submitted",
            "cs": "Pamatuje si, kter\u00e9 formul\u00e1\u0159e toto za\u0159\u00edzen\u00ed odeslalo",
        },
        "lifetime": {"en": "60 days", "cs": "60 dn\u00ed"},
    },
    {
        "name": "ubyhost_claim",
        "set_by": "routes/guest.py:remember_claim",
        "party": "first",
        "kind": "cookie",
        "surface": "guest",
        "purpose": {
            "en": "Keeps a claimed reservation on this device",
            "cs": "Udr\u017euje p\u0159evzatou rezervaci na tomto za\u0159\u00edzen\u00ed",
        },
        "lifetime": {"en": "60 days", "cs": "60 dn\u00ed"},
    },
    {
        "name": "ubyhost_guest_lang",
        "set_by": "routes/guest.py:remember_guest_language",
        "party": "first",
        "kind": "cookie",
        "surface": "guest",
        "purpose": {
            "en": "Remembers the guest's language",
            "cs": "Pamatuje si jazyk hosta",
        },
        "lifetime": {"en": "60 days", "cs": "60 dn\u00ed"},
    },
    {
        "name": "ubyhost-sidebar-collapsed",
        "set_by": "static/app.js",
        "party": "first",
        "kind": "localStorage",
        "surface": "host",
        "purpose": {"en": "Remembers the sidebar state", "cs": "Pamatuje si stav postrann\u00edho panelu"},
        "lifetime": {"en": "Until you clear it", "cs": "Dokud jej nevyma\u017eete"},
    },
    {
        "name": "ubyhost-command-recents",
        "set_by": "static/app.js",
        "party": "first",
        "kind": "localStorage",
        "surface": "host",
        "purpose": {
            "en": "Recent command-palette items",
            "cs": "Ned\u00e1vn\u00e9 polo\u017eky palety p\u0159\u00edkaz\u016f",
        },
        "lifetime": {"en": "Until you clear it", "cs": "Dokud jej nevyma\u017eete"},
    },
    {
        "name": "ubyhost-saved-stay-views",
        "set_by": "static/app.js",
        "party": "first",
        "kind": "localStorage",
        "surface": "host",
        "purpose": {
            "en": "Saved stay-list views",
            "cs": "Ulo\u017een\u00e9 pohledy na seznam pobyt\u016f",
        },
        "lifetime": {"en": "Until you clear it", "cs": "Dokud jej nevyma\u017eete"},
    },
    {
        "name": "__cf_bm",
        "set_by": "Cloudflare edge",
        "party": "Cloudflare",
        "kind": "cookie",
        "surface": "any",
        "purpose": {
            "en": "Cloudflare bot management, set only when the edge challenges the request",
            "cs": "Spr\u00e1va bot\u016f Cloudflare, nastav\u00ed se jen p\u0159i v\u00fdzv\u011b na hran\u011b",
        },
        "lifetime": {"en": "About 30 minutes", "cs": "P\u0159ibli\u017en\u011b 30 minut"},
    },
    {
        "name": "cf_clearance",
        "set_by": "Cloudflare edge",
        "party": "Cloudflare",
        "kind": "cookie",
        "surface": "any",
        "purpose": {
            "en": "Cloudflare challenge clearance, set only after a challenge is passed",
            "cs": "Potvrzen\u00ed v\u00fdzvy Cloudflare, nastav\u00ed se po jej\u00edm projit\u00ed",
        },
        "lifetime": {"en": "Up to 1 year", "cs": "A\u017e 1 rok"},
    },
)


def for_surface(surface: str) -> Tuple[Dict[str, object], ...]:
    return tuple(row for row in COOKIE_INVENTORY if row["surface"] in (surface, "any"))


def names() -> Tuple[str, ...]:
    return tuple(str(row["name"]) for row in COOKIE_INVENTORY)
