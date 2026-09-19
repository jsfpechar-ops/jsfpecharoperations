# Google Search Console for ubyhost.com

Free configuration so Google can discover the Czech and English public pages
UbyHost publishes. Pair this with the Cloudflare bot/challenge rules in
**[CLOUDFLARE.md](CLOUDFLARE.md#seo-cloudflare-rules-for-google--bing)** —
especially **Bot Fight Mode Off** + custom Managed Challenge rules (Free BFM
cannot be path-skipped).

Nothing here is paid ads. Ranking still depends on useful content and links;
GSC only controls **verification, crawl, and reporting**.

---

## 1. Add and verify the property

1. Open [Google Search Console](https://search.google.com/search-console).
2. **Add property** → prefer **Domain** property: `ubyhost.com`  
   (covers `https://`, `www`, and all paths in one place).
3. Verify with the **DNS TXT** record Google shows:

   | Type | Name | Content |
   |------|------|---------|
   | TXT | `@` (or as Google shows) | `google-site-verification=…` |

4. Cloudflare → **DNS** → **Records** → add that TXT → wait a few minutes →
   **Verify** in Search Console.

HTML-file or meta-tag verification also works, but DNS is one-time and survives
app deploys.

If Cloudflare offers **Add to Search Console** under the zone, you can use that
shortcut; the property still ends up in the same GSC UI.

**GSC has no extra “SEO enable” switch** beyond verification + sitemap +
indexing requests below. hreflang is already in the app HTML/sitemap.

---

## 2. Confirm the live site is crawlable

Before submitting a sitemap, Cloudflare must not serve a challenge HTML page to
Google. Apply the **recommended Free config** in [CLOUDFLARE.md](CLOUDFLARE.md)
(BFM off + Rules 1–3), purge cache once, then:

| Check | Expected |
|-------|----------|
| Browser, hard refresh: `https://ubyhost.com/` | Czech landing; title contains *Online ubytovací kniha* |
| Browser: `https://ubyhost.com/login` | Title **Přihlášení · UbyHost** or **Log in · UbyHost**, never **Continue** |
| Browser or curl: `https://ubyhost.com/robots.txt` | Ends with `Sitemap: https://ubyhost.com/sitemap.xml` |
| Browser or curl: `https://ubyhost.com/sitemap.xml` | XML with `<urlset>`, not “Just a moment…” |

In GSC → **URL Inspection** → paste `https://ubyhost.com/` → **Test live URL**.

| Live test result | Meaning |
|------------------|---------|
| URL is available to Google | Good — continue |
| Soft 404 / Redirect / Server error / Crawled – currently not indexed with challenge HTML | Fix Cloudflare bot settings / cache first (BFM still on is the usual cause) |

Repeat the live test for `https://ubyhost.com/sitemap.xml`.

---

## 3. Submit the sitemap

1. GSC → left nav → **Sitemaps**.
2. **Add a new sitemap** → enter exactly:

   ```text
   sitemap.xml
   ```

3. Submit.

Status should become **Success** after Google fetches it (minutes to a day).
If it stays **Couldn’t fetch** / HTTP 403, the edge is still challenging
`/sitemap.xml` — turn **Bot Fight Mode** off (or use IP Access Allow AS15169)
per [CLOUDFLARE.md](CLOUDFLARE.md).

The app serves both languages under `?lang=cs` / `?lang=en` with reciprocal
`hreflang` tags. You do **not** submit separate sitemaps per language.

---

## 4. Request indexing for the money pages

URL Inspection → **Request indexing** for each (after the live test is green):

| URL | Why |
|-----|-----|
| `https://ubyhost.com/` | Default Czech homepage |
| `https://ubyhost.com/?lang=en` | English homepage alternate |
| `https://ubyhost.com/login` | Stops Google keeping the old **Continue** title |
| `https://ubyhost.com/pruvodce/hlaseni-cizincu-ubyport` | UbyPort guide (CS default) |
| `https://ubyhost.com/pruvodce/hlaseni-cizincu-ubyport?lang=en` | Same guide in English |
| `https://ubyhost.com/pruvodce/online-ubytovaci-kniha` | Guest-book guide (CS) |
| `https://ubyhost.com/pruvodce/online-ubytovaci-kniha?lang=en` | Guest-book guide (EN) |

Quota is limited; prioritize `/`, `/login`, and the two Czech guide URLs first.

---

## 5. Settings that help a `.com` aimed at Czech hosts

| Setting | Where | Value |
|---------|-------|-------|
| Users / owners | Settings → Users and permissions | Add yourself + anyone who should see crawl errors |
| Change of Address | Only if you moved from another domain | Skip for a first launch |
| International targeting (legacy) | Legacy tools / country targeting if still shown | **Czechia** if the control exists — `ubyhost.com` is not a `.cz` TLD, so this is a weak but free signal |
| Preferred www / non-www | Domain property | No choice needed; we publish apex `https://ubyhost.com` |

hreflang (`cs` / `en` / `x-default`) is already in page HTML and the sitemap.
GSC has no separate “enable hreflang” switch — watch **International Targeting**
/ page indexing reports for pairing errors after crawl.

---

## 6. Ongoing free monitoring

| Report | What to watch |
|--------|----------------|
| **Sitemaps** | Success; discovered URL count rises after deploys |
| **Pages** (indexing) | “Crawled – currently not indexed”, “Blocked by robots.txt”, “Soft 404” |
| **Experience** / Core Web Vitals | Optional; landing is light HTML/CSS |
| **Security issues** | Empty |
| **Links** | Grows slowly; no paid tool required |

Re-submit or re-inspect only after meaningful public HTML changes, not after
every host-app deploy.

---

## 7. Bing (optional, also free)

1. [Bing Webmaster Tools](https://www.bing.com/webmasters) → import from Google
   or verify via DNS.
2. Submit the same `https://ubyhost.com/sitemap.xml`.

Cloudflare Rule 1’s `cf.client.bot` covers Bingbot when Cloudflare recognises it.

---

## Checklist (copy into go-live notes)

- [ ] GSC **Domain** property `ubyhost.com` verified (DNS TXT)
- [ ] Cloudflare: Bot Fight Mode **Off**; custom Rules 1–3 live; cache purged once
- [ ] Live URL test OK for `/` and `/sitemap.xml`
- [ ] Sitemap `sitemap.xml` submitted → Success
- [ ] Indexing requested for `/`, `/login`, both guides (CS, then EN)
- [ ] Browser no longer shows `<title>Continue</title>` on `/login`
- [ ] (Optional) Country targeting → Czechia; Bing import

---

## What GSC cannot do

| Expectation | Reality |
|-------------|---------|
| “Guarantee #1 on Google” | No setting does that |
| Replace useful Czech/English content | Content and crawlability do |
| Fix Bot Fight Mode challenges | That is Cloudflare, not GSC |
| Index private host pages | Intentionally blocked in `robots.txt` |
