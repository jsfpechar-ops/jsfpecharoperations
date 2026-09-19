"""What search engines are allowed to see, and in which language.

Only the signed-out pages are indexable; everything behind the login carries
guest data. Each indexable page is offered in both languages under its own
``?lang=`` URL so Google can show Czech hosts the Czech page.
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import Request

from . import config, host_i18n

INDEXABLE_PATHS = (
    "/",
    "/login",
    "/legal",
    "/terms",
    "/privacy",
    "/dpa",
    "/pruvodce/hlaseni-cizincu-ubyport",
    "/pruvodce/online-ubytovaci-kniha",
)

# Everything a signed-in host works with. These redirect to the login page for
# a crawler anyway; saying so keeps them out of the index and off the budget.
PRIVATE_PREFIXES = (
    "/l/",
    "/account/",
    "/admin/",
    "/api/",
    "/apartments",
    "/automation",
    "/entities",
    "/guest-links",
    "/guests/",
    "/guide",
    "/housebook",
    "/reservations",
    "/settings",
    "/submissions",
)


def page_url(path: str, lang: str | None = None) -> str:
    base = f"{config.PUBLIC_BASE_URL}{path}"
    return f"{base}?lang={lang}" if lang else base


def alternates(path: str) -> list[tuple[str, str]]:
    """hreflang pairs, plus the negotiated URL as the default."""
    links = [(lang, page_url(path, lang)) for lang in host_i18n.LANGUAGES]
    links.append(("x-default", page_url(path)))
    return links


def head_links(request: Request) -> Dict[str, Any]:
    """Canonical and hreflang context, empty for pages we do not want indexed."""
    path = request.url.path
    if path not in INDEXABLE_PATHS:
        return {}
    requested = host_i18n.supported_language(request.query_params.get("lang"))
    return {
        "canonical_url": page_url(path, requested),
        "alternate_urls": alternates(path),
    }


def robots_txt() -> str:
    lines = ["User-agent: *"]
    lines += [f"Disallow: {prefix}" for prefix in PRIVATE_PREFIXES]
    lines += ["", f"Sitemap: {config.PUBLIC_BASE_URL}/sitemap.xml", ""]
    return "\n".join(lines)


def sitemap_xml() -> str:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
        'xmlns:xhtml="http://www.w3.org/1999/xhtml">',
    ]
    for path in INDEXABLE_PATHS:
        for lang in host_i18n.LANGUAGES:
            lines.append("  <url>")
            lines.append(f"    <loc>{page_url(path, lang)}</loc>")
            for code, href in alternates(path):
                lines.append(
                    f'    <xhtml:link rel="alternate" hreflang="{code}" href="{href}"/>'
                )
            lines.append("  </url>")
    lines += ["</urlset>", ""]
    return "\n".join(lines)
