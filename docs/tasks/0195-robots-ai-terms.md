# 0195: Keep AI and scraping crawlers out (robots.txt, tdmrep, Terms)

Status: ready
Depends on: none | Branch: claude/project-thread-1u1cuj
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

The owner wants a robots.txt like superhostem.cz's, plus a Terms clause, so crawlers and AI are discouraged from analysing the site and app. Ordinary search engines keep indexing the public marketing and legal pages. AI-training, AI-answer and bulk-scraping bots are refused everywhere. The EU text-and-data-mining opt-out is stated in robots.txt, in a machine-readable `/.well-known/tdmrep.json`, and in Terms §11 (English and Czech).

## 2. Context

- `App/app/seo.py`: `PRIVATE_PREFIXES` (lines 33-47) and `robots_txt()` (line 72). Served by `App/app/main.py:355-357`.
- superhostem.cz robots.txt only has `User-Agent: *` with Disallow lines for its app paths. Ours already does that; this brief adds the AI group and missing app paths.
- Terms text: `App/app/terms_i18n.py`, key `terms.s11_body` in `"en"` (line 179) and `"cs"` (line 516). Section anchor on the page is `#s11`.
- No template, CSS or JS changes, so no screenshots and no `?v=` keys. `TERMS_VERSION` stays `1.7` (owner decides on a bump; legal v1.7 is still awaiting lawyer review).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/seo.py` | edit | AI agent list, notice, more private prefixes, new robots body, tdmrep string |
| `App/app/main.py` | edit | `/.well-known/tdmrep.json` route |
| `App/app/terms_i18n.py` | edit | append clause to `terms.s11_body` en + cs |
| `App/tests/test_public_seo.py` | edit | two tests |

## 4. Steps

### Step 1: `App/app/seo.py`, private prefixes

Anchor `grep -nF '"/guest-links",' App/app/seo.py`. Replace the whole `PRIVATE_PREFIXES = ( ... )` tuple with:

```python
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
```

### Step 2: `App/app/seo.py`, AI list and notice

Directly after the `PRIVATE_PREFIXES` tuple (blank line before and after), insert:

```python
# Bots that collect pages for AI training, AI answers or bulk resale. They get
# nothing, public pages included; ordinary search engines keep the rules for
# "*". robots.txt is advisory: well-behaved bots honour it, others need the
# Cloudflare bot rules.
AI_AND_SCRAPER_AGENTS = (
    "GPTBot",
    "ChatGPT-User",
    "OAI-SearchBot",
    "ClaudeBot",
    "Claude-User",
    "Claude-SearchBot",
    "Claude-Web",
    "anthropic-ai",
    "Google-Extended",
    "Google-CloudVertexBot",
    "Applebot-Extended",
    "CCBot",
    "PerplexityBot",
    "Perplexity-User",
    "Bytespider",
    "TikTokSpider",
    "Amazonbot",
    "meta-externalagent",
    "meta-externalfetcher",
    "FacebookBot",
    "cohere-ai",
    "cohere-training-data-crawler",
    "MistralAI-User",
    "DuckAssistBot",
    "YouBot",
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
```

### Step 3: `App/app/seo.py`, robots body

Replace the body of `robots_txt()` (anchor `grep -nF 'def robots_txt' App/app/seo.py`) with:

```python
def robots_txt() -> str:
    lines = [TDM_NOTICE, ""]
    lines += [f"User-agent: {agent}" for agent in AI_AND_SCRAPER_AGENTS]
    lines += ["Disallow: /", "", "User-agent: *"]
    lines += ["Content-Signal: search=yes, ai-train=no, ai-input=no"]
    lines += [f"Disallow: {prefix}" for prefix in PRIVATE_PREFIXES]
    lines += ["", f"Sitemap: {config.PUBLIC_BASE_URL}/sitemap.xml", ""]
    return "\n".join(lines)
```

### Step 4: `App/app/main.py`, tdmrep route

Anchor `grep -nF 'def robots():' App/app/main.py`. After that function's `return` line, add a blank-line-separated route:

```python


@app.get("/.well-known/tdmrep.json", include_in_schema=False)
def tdmrep():
    return Response(seo.TDMREP_JSON, media_type="application/json")
```

(Two blank lines before `@app.get`, matching the file. Do not add a third blank line before the `/sitemap.xml` route.)

### Step 5: `App/app/terms_i18n.py`, English clause

Anchor `grep -nF 'the Service, comply with law, and enforce these Terms."' App/app/terms_i18n.py`. Replace that one line with:

```python
            "the Service, comply with law, and enforce these Terms. Without the Operator's prior "
            "written consent, no one, whether or not they hold an Account, may: (a) scrape, crawl, "
            "harvest or systematically download the Service, its website or its content with robots, "
            "spiders, scripts or other automated means, except through features the Service itself "
            "offers (such as data export) and search engines indexing the public pages as robots.txt "
            "allows; (b) use any of it for text and data mining, automated analysis, or to train, "
            "fine-tune, test or feed artificial intelligence or machine-learning systems; or (c) build "
            "a competing product or dataset from it. The Operator expressly reserves text and data "
            "mining under Article 4(3) of Directive (EU) 2019/790 and the Czech Copyright Act "
            "(No. 121/2000 Coll.); the reservation is also given in machine-readable form in "
            "robots.txt and /.well-known/tdmrep.json."
```

### Step 6: `App/app/terms_i18n.py`, Czech clause

Anchor `grep -nF 'Obsahu výhradně pro poskytování a zlepšování Služby, plnění zákona a vymáhání Podmínek."' App/app/terms_i18n.py`. Replace that one line with:

```python
            "Obsahu výhradně pro poskytování a zlepšování Služby, plnění zákona a vymáhání Podmínek. "
            "Bez předchozího písemného souhlasu Provozovatele nesmí nikdo, ať už má Účet, nebo ne: "
            "(a) automatizovaně procházet, stahovat nebo vytěžovat Službu, její web či obsah pomocí "
            "robotů, crawlerů, skriptů nebo jiných automatizovaných prostředků, s výjimkou funkcí, "
            "které Služba sama nabízí (např. export dat), a vyhledávačů indexujících veřejné stránky "
            "v rozsahu povoleném souborem robots.txt; (b) je používat k vytěžování textů a dat, "
            "automatizované analýze nebo k trénování, dolaďování, testování či napájení systémů umělé "
            "inteligence nebo strojového učení; ani (c) z nich vytvářet konkurenční produkt nebo "
            "datovou sadu. Provozovatel si výslovně vyhrazuje vytěžování textů a dat podle čl. 4 "
            "odst. 3 směrnice (EU) 2019/790 a autorského zákona (č. 121/2000 Sb.); výhrada je "
            "uvedena i ve strojově čitelné podobě v souborech robots.txt a /.well-known/tdmrep.json."
```

### Step 7: tests

In `App/tests/test_public_seo.py`, after `test_robots_keeps_crawlers_out_of_the_workspace` (anchor `grep -nF 'def test_the_sitemap_lists_both_languages' App/tests/test_public_seo.py`, insert before it), add:

```python
def test_robots_refuses_ai_and_scraper_bots_but_not_search_engines():
    body = _client().get("/robots.txt").text
    ai_group, _, everyone = body.partition("User-agent: *")

    for agent in ("GPTBot", "ClaudeBot", "CCBot", "Google-Extended", "PerplexityBot"):
        assert f"User-agent: {agent}\n" in ai_group, agent
    assert "Disallow: /\n" in ai_group
    assert "Disallow: /\n" not in everyone, "search engines lost the public pages"
    assert "Googlebot" not in body and "Bingbot" not in body
    assert "ai-train=no" in everyone
    assert "2019/790" in body


def test_tdmrep_reserves_text_and_data_mining():
    response = _client().get("/.well-known/tdmrep.json")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == [{"location": "/*", "tdm-reservation": 1}]


def test_terms_reserve_scraping_and_ai_training_in_both_languages():
    from app.terms_i18n import TERMS_STRINGS

    assert "train" in TERMS_STRINGS["en"]["terms.s11_body"]
    assert "2019/790" in TERMS_STRINGS["en"]["terms.s11_body"]
    assert "trénování" in TERMS_STRINGS["cs"]["terms.s11_body"]
    assert "2019/790" in TERMS_STRINGS["cs"]["terms.s11_body"]
```

## 5. Commit

One commit per step: `0195 step k`.

## 6. Test

From `App/`:

`.venv/bin/python -m pytest tests/test_public_seo.py tests/test_terms_copy.py tests/test_wp24_terms_dpa.py tests/test_owner_decisions.py tests/test_operator_naming.py tests/test_legal_acceptance.py -q --tb=short -x 2>&1 | tail -30`

From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`

## 7. Done when

- [ ] All §6 tests pass.
- [ ] `/robots.txt` starts with the notice, then the AI group with `Disallow: /`, then `User-agent: *`.
- [ ] `/.well-known/tdmrep.json` returns the JSON.
- [ ] Terms §11 has the clause in English and Czech.

## 8. Stop if

An anchor is not found, or a §6 test fails twice. Report, do not guess.
