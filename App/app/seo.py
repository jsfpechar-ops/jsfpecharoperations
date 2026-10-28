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
    "/subprocessors",
    "/jak-to-funguje",
    "/cenik",
    "/pruvodce/hlaseni-cizincu-ubyport",
    "/pruvodce/online-ubytovaci-kniha",
)

# Everything a signed-in host works with. These redirect to the login page for
# a crawler anyway; saying so keeps them out of the index and off the budget.
PRIVATE_PREFIXES = (
    "/l/",
    "/account/",
    "/admin/",
    "/alerts",
    "/api/",
    "/apartments",
    "/celebrations",
    "/cleaning",
    "/dashboard",
    "/demo",
    "/dev",
    "/entities",
    "/feeds",
    "/guest-links",
    "/guests",
    "/guide",
    "/housebook",
    "/invoice",
    "/mail",
    "/onboarding",
    "/privacy-requests",
    "/reservations",
    "/settings",
    "/smart-locks",
    "/stay-fees",
    "/submissions",
    "/sync",
)

# Bots that collect pages for AI training or bulk resale. They get nothing,
# public pages included. AI search and answer bots (ChatGPT search, Claude,
# Perplexity) are not listed: like ordinary search engines they follow the
# rules for "*", so they see the public pages and never the app. robots.txt is
# advisory: well-behaved bots honour it, others need the Cloudflare bot rules.
AI_AND_SCRAPER_AGENTS = (
    "GPTBot",
    "ClaudeBot",
    "Claude-Web",
    "anthropic-ai",
    "Google-Extended",
    "Google-CloudVertexBot",
    "Applebot-Extended",
    "CCBot",
    "Bytespider",
    "TikTokSpider",
    "Amazonbot",
    "meta-externalagent",
    "meta-externalfetcher",
    "FacebookBot",
    "cohere-ai",
    "cohere-training-data-crawler",
    "AI2Bot",
    "Ai2Bot-Dolma",
    "Diffbot",
    "ImagesiftBot",
    "Omgilibot",
    "Omgili",
    "Webzio-Extended",
    "Timpibot",
    "PanguBot",
    "img2dataset",
    "Scrapy",
    "AhrefsBot",
    "SemrushBot",
    "MJ12bot",
    "DotBot",
    "DataForSeoBot",
    "BLEXBot",
)

TDM_NOTICE = (
    "# Text and data mining, AI training and automated scraping of this site\n"
    "# are not permitted. Rights reserved under Art. 4(3) of Directive (EU)\n"
    "# 2019/790 and the Czech Copyright Act (No. 121/2000 Coll.).\n"
    "# Terms: /terms#s11"
)

# TDMRep (W3C community report): the same reservation, machine-readable.
TDMREP_JSON = '[{"location": "/*", "tdm-reservation": 1}]\n'


def page_url(path: str, lang: str | None = None) -> str:
    base = f"{config.PUBLIC_BASE_URL}{path}"
    return f"{base}?lang={lang}" if lang else base


def alternates(path: str) -> list[tuple[str, str]]:
    """hreflang pairs, plus the negotiated URL as the default."""
    links = [(lang, page_url(path, lang)) for lang in host_i18n.PUBLIC_LANGUAGES]
    links.append(("x-default", page_url(path)))
    return links


def head_links(request: Request) -> Dict[str, Any]:
    """Canonical and hreflang context, empty for pages we do not want indexed."""
    path = request.url.path
    if path not in INDEXABLE_PATHS:
        return {}
    requested = host_i18n.supported_language(request.query_params.get("lang"))
    if requested not in host_i18n.PUBLIC_LANGUAGES:
        requested = None
    return {
        "canonical_url": page_url(path, requested),
        "alternate_urls": alternates(path),
    }


def robots_txt() -> str:
    lines = [TDM_NOTICE, ""]
    lines += [f"User-agent: {agent}" for agent in AI_AND_SCRAPER_AGENTS]
    lines += ["Disallow: /", "", "User-agent: *"]
    lines += ["Content-Signal: search=yes, ai-input=yes, ai-train=no"]
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
        for lang in host_i18n.PUBLIC_LANGUAGES:
            lines.append("  <url>")
            lines.append(f"    <loc>{page_url(path, lang)}</loc>")
            for code, href in alternates(path):
                lines.append(
                    f'    <xhtml:link rel="alternate" hreflang="{code}" href="{href}"/>'
                )
            lines.append("  </url>")
    # 0433: published property pages (search-visible only; the listing pages
    # are English-only per the owner decision, so no per-language variants).
    try:
        from . import config as _config
        from . import property_page

        base = _config.PUBLIC_BASE_URL.rstrip("/")
        for row in property_page.published_pages():
            lines.append("  <url>")
            lines.append(f"    <loc>{base}/p/{row['slug']}</loc>")
            if row["published_at"]:
                lines.append(f"    <lastmod>{row['published_at']}</lastmod>")
            lines.append("  </url>")
    except Exception:
        pass
    lines += ["</urlset>", ""]
    return "\n".join(lines)
