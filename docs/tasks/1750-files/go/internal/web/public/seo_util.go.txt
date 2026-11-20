package public

import (
	"fmt"
	"strings"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
)

// Indexable paths and crawler rules mirror App/app/seo.py.

var indexablePaths = []string{
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
}

var privatePrefixes = []string{
	"/l/", "/account/", "/admin/", "/alerts", "/api/", "/apartments", "/celebrations",
	"/cleaning", "/dashboard", "/demo", "/dev", "/entities", "/feeds", "/guest-links",
	"/guests", "/guide", "/housebook", "/invoice", "/mail", "/onboarding",
	"/privacy-requests", "/reservations", "/settings", "/smart-locks", "/stay-fees",
	"/submissions", "/sync",
}

var aiAndScraperAgents = []string{
	"GPTBot", "ClaudeBot", "Claude-Web", "anthropic-ai", "Google-Extended",
	"Google-CloudVertexBot", "Applebot-Extended", "CCBot", "Bytespider", "TikTokSpider",
	"Amazonbot", "meta-externalagent", "meta-externalfetcher", "FacebookBot", "cohere-ai",
	"cohere-training-data-crawler", "AI2Bot", "Ai2Bot-Dolma", "Diffbot", "ImagesiftBot",
	"Omgilibot", "Omgili", "Webzio-Extended", "Timpibot", "PanguBot", "img2dataset",
	"Scrapy", "AhrefsBot", "SemrushBot", "MJ12bot", "DotBot", "DataForSeoBot", "BLEXBot",
}

const tdmNotice = "# Text and data mining, AI training and automated scraping of this site\n" +
	"# are not permitted. Rights reserved under Art. 4(3) of Directive (EU)\n" +
	"# 2019/790 and the Czech Copyright Act (No. 121/2000 Coll.).\n" +
	"# Terms: /terms#s11"

// TDMRepJSON is seo.TDMREP_JSON.
const TDMRepJSON = `[{"location": "/*", "tdm-reservation": 1}]
`

var publicLanguages = []string{"en", "cs"}

func pageURL(base, path, lang string) string {
	u := base + path
	if lang != "" {
		return u + "?lang=" + lang
	}
	return u
}

func alternates(base, path string) [][2]string {
	out := make([][2]string, 0, len(publicLanguages)+1)
	for _, lang := range publicLanguages {
		out = append(out, [2]string{lang, pageURL(base, path, lang)})
	}
	out = append(out, [2]string{"x-default", pageURL(base, path, "")})
	return out
}

// RobotsTXT is seo.robots_txt() for the given public base URL (no trailing slash).
func RobotsTXT(getenv func(string) string) string {
	base := hostweb.PublicBase(getenv)
	lines := []string{tdmNotice, ""}
	for _, agent := range aiAndScraperAgents {
		lines = append(lines, "User-agent: "+agent)
	}
	lines = append(lines, "Disallow: /", "", "User-agent: *", "Content-Signal: search=yes, ai-input=yes, ai-train=no")
	for _, prefix := range privatePrefixes {
		lines = append(lines, "Disallow: "+prefix)
	}
	lines = append(lines, "", "Sitemap: "+base+"/sitemap.xml", "")
	return strings.Join(lines, "\n")
}

type publishedRow struct {
	Slug        string
	PublishedAt *string
}

// SitemapXML is seo.sitemap_xml(), with optional property pages from publishedRows.
func SitemapXML(getenv func(string) string, publishedRows []publishedRow) string {
	base := hostweb.PublicBase(getenv)
	lines := []string{
		`<?xml version="1.0" encoding="UTF-8"?>`,
		`<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" ` +
			`xmlns:xhtml="http://www.w3.org/1999/xhtml">`,
	}
	for _, path := range indexablePaths {
		for _, lang := range publicLanguages {
			lines = append(lines, "  <url>")
			lines = append(lines, fmt.Sprintf("    <loc>%s</loc>", pageURL(base, path, lang)))
			for _, pair := range alternates(base, path) {
				lines = append(lines, fmt.Sprintf(`    <xhtml:link rel="alternate" hreflang="%s" href="%s"/>`, pair[0], pair[1]))
			}
			lines = append(lines, "  </url>")
		}
	}
	for _, row := range publishedRows {
		lines = append(lines, "  <url>")
		lines = append(lines, fmt.Sprintf("    <loc>%s/p/%s</loc>", base, row.Slug))
		if row.PublishedAt != nil && *row.PublishedAt != "" {
			lines = append(lines, fmt.Sprintf("    <lastmod>%s</lastmod>", *row.PublishedAt))
		}
		lines = append(lines, "  </url>")
	}
	lines = append(lines, "</urlset>", "")
	return strings.Join(lines, "\n")
}
