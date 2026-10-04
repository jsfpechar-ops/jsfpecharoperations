# 04. Legal positions for UbyHost

This is reasoned research, not legal advice from an attorney.

Researched 3 October 2026. Anything I could not open or confirm in a primary source is marked [UNVERIFIED]. zakonyprolidi.cz, the ÚOOÚ cookie guidance pages, the EDPB website and the CNIL French pages returned empty when fetched. I used government mirrors (mze.gov.cz, esipa.cz), the EDPB guideline PDF (Sedona Conference copy of the adopted text) and a Czech law firm article quoting the ÚOOÚ instead.

## Summary of decisions

| # | Question | Decision | Product change |
|---|---|---|---|
| 1 | Umami Cloud on marketing pages | No consent banner. Notice in the privacy policy plus an opt-out link. | Strict tracker config: EU region, `data-do-not-track`, `data-exclude-search`, `data-domains`; no distinct IDs, replays, heatmaps or custom personal data. |
| 2 | Three onboarding e-mails | Service e-mails to own customers. Treat them as if § 7(3) zákon 480/2004 Sb. applied anyway. Legal basis: legitimate interest. | Opt-out checkbox at sign-up, one-click opt-out link and sender identification in every e-mail, suppression list. |
| 3 | gclid capture and offline upload | Needs prior, explicit, optional consent. | Unchecked checkbox on sign-up. Store gclid only if ticked. Upload only consented rows with `Ad User Data = Granted`. |
| 4 | Retention | Guest book 6 years (§ 101(4) zákon 326/1999 Sb.). Stay-fee book 6 years (§ 3g(4) zákon 565/1990 Sb.). Invoices 10 years. Passport photos: delete within 7 days. UbyPort raw XML: 90 days. | Scheduled deletion jobs per data class. |
| 5 | Roles and subprocessors | Processor for guest data, controller for host accounts, analytics and ads data. Google is an independent controller. | Publish a subprocessor list and a DPA (zpracovatelská smlouva) for hosts. |
| 6 | Meta Conversions API (fbclid) | Needs prior, explicit, optional consent, as for gclid. Meta Platforms Ireland is joint controller for collection and sending, independent controller afterwards. | Separate unchecked box shown only with `fbclid` ("came from Facebook or Instagram"). One server-side `CompleteRegistration` event with `fbc` only, `opt_out=true`. Delete `fbc` 7 days after sending, 90 days after the click at most. |

---

## 1. Umami Cloud on the public marketing pages, no banner

### Position
No consent banner is needed. This holds only if Umami Cloud runs in the EU region, only on public marketing pages, and in the minimal configuration below. Add a short privacy-policy paragraph and an opt-out link.

### Reasoning
- § 89(3) zákon 127/2005 Sb. (opt-in since 1 Jan 2022) requires consent to store or access information on the user's device, unless the access is necessary for a service the user explicitly asked for. The ÚOOÚ applies this to "similar technologies", not only cookies. [UNVERIFIED: I could not open the statute text on zakonyprolidi.cz. The wording is cited from the ÚOOÚ cookie page.]
- EDPB Guidelines 2/2023 (v2, Oct 2024), para 31-32: JavaScript that tells the browser to send information is "gaining access" under Art. 5(3) ePrivacy. The Umami script does exactly that, so Art. 5(3), and § 89(3) in Czech law, applies. Not using cookies does not take you outside the rule.
- The ÚOOÚ told eLegal (published 7 July 2025) two things. First, cookieless tools that build a hash of the visitor (device, IP, browser settings) are "similar technologies". Second, analytics can fall under the "necessary" exemption if it (1) serves only to measure traffic, (2) does not allow overall tracking of a person's navigation, (3) produces only anonymous statistics, (4) is not combined with other data, and (5) does not make data available to third parties. The ÚOOÚ says this needs a case-by-case assessment.
- CNIL's audience-measurement exemption uses similar conditions: inform users, let them object, use the data only for audience measurement, no cross-checking with other data, a single publisher, and a limit on lifetime. Note that the CNIL requires an opt-out to be offered.
- Umami builds a session hash from IP, user agent and website ID (Umami docs, "Sessions"). It uses no cookies (Umami FAQ). The salt rotates monthly by default in self-hosted Umami (`SALT_ROTATION`). [UNVERIFIED for Umami Cloud.]
- Umami Cloud has servers "in the US and EU" (Cloud FAQ). A DPA page exists at umami.is/dpa, but its text loads client-side and I could not read it. [UNVERIFIED: whether the DPA includes SCCs. The operator, Umami Software, Inc., is a US company.]
- Umami features that would break the ÚOOÚ condition about not tracking a person's navigation: Distinct IDs, session replays, heatmaps, and the per-visitor "Visitor profile" history. Keep the first three off. Do not use the visitor profile view for individuals.
- Umami acts as UbyHost's processor. Under the ÚOOÚ condition, that does not count as "making data available to third parties", provided Umami does not use the data for its own purposes. This depends on the DPA wording. [UNVERIFIED]

### What the product must do
Code:
- Create the website in the Umami Cloud **EU** region. Accept the DPA in the account and save a PDF copy in the compliance folder.
- Load the tracker only on public marketing pages (home, pricing, features, blog, legal pages). Never load it on `/app`, the host dashboard, guest pages, PIN pages, sign-up success pages, or any URL that contains a token.
- Tracker tag:
  ```html
  <script defer src="https://cloud.umami.is/script.js"
    data-website-id="..."
    data-domains="ubyhost.cz,www.ubyhost.cz"
    data-do-not-track="true"
    data-exclude-search="true"
    data-exclude-hash="true"></script>
  ```
  `data-exclude-search="true"` is required. Without it, Umami would record `?gclid=...` from ad clicks, and that would undo the consent design in section 3.
- Do not call `umami.identify()`, do not use Distinct IDs, do not send custom event data containing e-mail, names or IDs. Leave Replays and Heatmaps off. Track only page views and, at most, anonymous button events such as `signup_click`.
- Update the CSP `script-src` and `connect-src` to allow the Umami host.
- Opt-out link on the privacy page. On click, run `localStorage.setItem('umami.disabled', 1)` and show a confirmation. Umami documents this flag ("Exclude my own visits"). Storing it is at the user's request, so no consent is needed for it. Add an "opt back in" link that removes the key.
- Add Umami to `cookie_inventory.py` as "cookieless analytics, no cookies set; optional localStorage key `umami.disabled` only after opt-out".

UI text (privacy page, next to the opt-out):
- EN: "We measure visits to our public pages with Umami, without cookies. [Turn off measurement in this browser]"
- CS: "Návštěvnost veřejných stránek měříme nástrojem Umami bez cookies. [Vypnout měření v tomto prohlížeči]"

Privacy-policy paragraph:
- EN: "Website analytics. On our public pages (not in the app) we use Umami Cloud, operated by Umami Software, Inc., with data stored in the EU, to count visits. Umami does not set cookies and does not store your IP address. It derives a short-lived anonymous visit identifier from your IP address, browser type and our website ID, and we see only aggregated statistics (pages viewed, referring site, browser, device type, country). We do not combine this data with account data and we do not use it for advertising. Legal basis: our legitimate interest in understanding how our website is used (Art. 6(1)(f) GDPR). The exemption under § 89(3) of Act No. 127/2005 Coll. applies because the measurement serves only anonymous traffic statistics. You can switch measurement off in your browser here: [link]. We also respect your browser's Do Not Track setting."
- CS: "Měření návštěvnosti. Na veřejných stránkách webu (ne v aplikaci) používáme nástroj Umami Cloud provozovaný společností Umami Software, Inc. s ukládáním dat v EU, abychom zjistili počet návštěv. Umami nepoužívá cookies a neukládá vaši IP adresu. Z IP adresy, typu prohlížeče a identifikátoru našeho webu vytváří krátkodobý anonymní identifikátor návštěvy a my vidíme pouze souhrnné statistiky (zobrazené stránky, odkazující web, prohlížeč, typ zařízení, země). Tato data nespojujeme s údaji z vašeho účtu a nepoužíváme je k reklamě. Právní základ: náš oprávněný zájem porozumět používání webu (čl. 6 odst. 1 písm. f) GDPR). Jde o měření nezbytné pro provoz webu ve smyslu § 89 odst. 3 zákona č. 127/2005 Sb., protože slouží jen k anonymní statistice návštěvnosti. Měření můžete ve svém prohlížeči vypnout zde: [odkaz]. Respektujeme také nastavení Do Not Track ve vašem prohlížeči."

### Residual risk
**Low to medium.** The ÚOOÚ exemption is a case-by-case assessment, not a safe harbour. Umami's session hash is the kind of identifier the ÚOOÚ calls a "similar technology", and the Cloud dashboard can show per-visitor journeys. The risk drops to low if the Umami DPA confirms that Umami does not reuse the data and covers US transfers (SCCs or DPF). Read the DPA before go-live. If it does not cover these points, self-host Umami on the existing EU server instead.

### Sources
- https://uoou.gov.cz/cookies
- https://elegal.cz/analyticke-cookies-bez-souhlasu
- https://www.thesedonaconference.org/sites/default/files/meeting_paper/Recommended%204.5_EDPB%20Guidelines%202-2023%20on%20Technical%20Scope%20of%20Art.%205(3)%20of%20ePrivacy%20Directive.pdf (EDPB Guidelines 2/2023, adopted text)
- https://www.hunton.com/privacy-and-cybersecurity-law-blog/edpb-publishes-guidelines-to-clarify-scope-of-eu-cookie-notice-and-consent-requirements
- https://www.cnil.fr/en/sheet-ndeg16-use-analytics-your-websites-and-applications
- https://docs.umami.is/docs/faq
- https://docs.umami.is/docs/cloud/faq
- https://docs.umami.is/docs/cloud
- https://docs.umami.is/docs/sessions
- https://docs.umami.is/docs/tracker-configuration
- https://docs.umami.is/docs/exclude-my-own-visits
- https://umami.is/dpa (page title confirmed, body not readable)

---

## 2. Onboarding e-mails to registered hosts

The e-mails: no property after 3 days, no calendar after 3 days, no completed guest after 14 days.

### Position
These are service e-mails to UbyHost's own customers about finishing setup of a service they signed up for. Even so, build them to the standard for commercial communications to customers under § 7(3) zákon 480/2004 Sb. That costs one checkbox and one link, and it removes the argument. GDPR legal basis: legitimate interest, Art. 6(1)(f), with the right to object (Art. 21).

### Reasoning
- ÚOOÚ FAQ on 480/2004, Q6: purely "technical" messages to your own customer, such as changes to terms or service outages, are not commercial communications. Q1 says the opposite for anything that indirectly promotes the business, including requests for reviews. A setup nudge sits between the two: it is about the customer's own account, but it also encourages use of the product.
- ÚOOÚ Q8: a "customer" (zákazník) is anyone who has entered into a contract, paid or free. A registered host with an account has accepted the terms, so they count as a customer.
- § 7(3), per ÚOOÚ Q9: commercial e-mails to customers about the sender's own similar services are allowed without consent if (a) the customer could refuse when giving the e-mail address, and (b) every message has a clear, free, simple way to refuse. Q17: identify the sender clearly in the message itself (company name, IČO). A link alone is not enough. Q19: keep a suppression list ("seznam robinsonů"), with legal basis Art. 6(1)(c).
- Q16: commercial communications should be labelled in the subject. Keep these e-mails strictly functional (no prices, no upsell, no partner offers, no review requests). Then no "OS" label is needed, and a neutral subject is fine.
- Pending change: a draft zákon o digitální ekonomice would require customers to have a clear, free chance to refuse before the first message (eLegal, 21 May 2026). [UNVERIFIED: status and date in force.] A refusal checkbox at sign-up already meets this.
- GDPR: contract (6(1)(b)) is arguable but weak for optional nudges. Legitimate interest is the honest basis. Helping a paying or trial customer finish setup is expected and has minimal impact.

### What the product must do
Code:
- Sign-up form: add an **unchecked** checkbox: "Do not send me setup tips by e-mail". Store `onboarding_emails_opt_out` (bool) and the timestamp.
- Settings page: a toggle "Setup tips by e-mail" (default on, unless the host ticked the opt-out at sign-up).
- Every onboarding e-mail has a footer with an unsubscribe link carrying a signed token. One click unsubscribes, with no login. Add `List-Unsubscribe` and `List-Unsubscribe-Post: List-Unsubscribe=One-Click` headers.
- Unsubscribe writes to a suppression table (e-mail hash, timestamp, scope `onboarding`). The mail job checks this table before sending. The flag must never block transactional mail (password reset, UbyPort errors, invoices).
- Send each e-mail at most once per account. Stop the sequence once the condition is met. No more than these three e-mails.
- Content rule for templates: about the host's own setup only. No discounts, pricing or third-party offers. If marketing content is ever added, add "Novinky:" to the subject and treat the e-mail as a newsletter.

Footer text:
- EN: "You are receiving this because you created a UbyHost account and have not finished setting it up. Don't want these setup tips? [Unsubscribe with one click]. You will still receive essential account and service e-mails. Sender: [Company name], IČO [xxxxxxxx], [registered address]. Privacy: [link]."
- CS: "Tento e-mail dostáváte, protože jste si založili účet UbyHost a ještě jste nedokončili jeho nastavení. Nechcete tyto tipy k nastavení dostávat? [Odhlásit jedním kliknutím]. Nezbytné e-maily k účtu a službě vám budeme posílat i nadále. Odesílatel: [Obchodní firma], IČO [xxxxxxxx], [sídlo]. Ochrana osobních údajů: [odkaz]."

Sign-up checkbox:
- EN: "Do not send me setup tips by e-mail (you can change this anytime in Settings)."
- CS: "Nepřeji si dostávat e-mailem tipy k nastavení (kdykoli to můžete změnit v Nastavení)."

Privacy-policy paragraph:
- EN: "Setup e-mails. If you create an account and do not finish setting it up, we may send you up to three short e-mails with help (for example, when no property or calendar has been added). Legal basis: our legitimate interest in helping our customers use the service they signed up for (Art. 6(1)(f) GDPR) and § 7(3) of Act No. 480/2004 Coll. You can refuse these e-mails at sign-up, in Settings, or with the link in each e-mail. We keep a list of refused addresses so we do not write to them again (Art. 6(1)(c) GDPR)."
- CS: "E-maily k nastavení účtu. Pokud si založíte účet a nedokončíte jeho nastavení, můžeme vám poslat nejvýše tři krátké e-maily s nápovědou (například když nemáte přidané ubytování nebo kalendář). Právní základ: náš oprávněný zájem pomoci zákazníkům využívat službu, kterou si objednali (čl. 6 odst. 1 písm. f) GDPR), a § 7 odst. 3 zákona č. 480/2004 Sb. Tyto e-maily můžete odmítnout při registraci, v Nastavení nebo odkazem v každém e-mailu. Odmítnuté adresy evidujeme, abychom vám už nepsali (čl. 6 odst. 1 písm. c) GDPR)."

### Residual risk
**Low.** With the sign-up opt-out, the footer and the suppression list, the e-mails meet the stricter standard even if a regulator calls them commercial communications. Fines under § 11 need bulk or repeated sending (ÚOOÚ Q22), and the maximum is CZK 10 million for legal persons (Q23).

### Sources
- https://uoou.gov.cz/cinnost/obchodni-sdeleni/casto-kladene-otazky-k-zakonu-c-4802004-sb
- https://uoou.gov.cz/cinnost/obchodni-sdeleni
- https://elegal.cz/v-newsletterech-se-bude-zprisnovat-i-zvolnovat

---

## 3. Self sign-up with Google Ads: gclid capture and offline click conversion upload

### Position
**Explicit consent is needed.** Add an optional, unchecked checkbox to the sign-up form. Persist the gclid only for hosts who tick it. Upload only those rows, with `Ad User Data = Granted` and `Ad Personalization = Denied`. Hosts who do not tick it can still sign up.

### Reasoning
(a) ePrivacy: reading `gclid` from the landing URL counts as device access.
- EDPB Guidelines 2/2023, para 48: a tracking link "collects an identifier which is not relevant in terms of resource identification" when the URL is visited. Para 50-51: when tracked URLs are distributed over a public network, Art. 5(3) applies, and collecting the identifier is "gaining access". Para 33: it does not matter that Google, not UbyHost, appended the identifier.
- The ÚOOÚ follows the EDPB's broad reading (eLegal, 2025). § 89(3) zákon 127/2005 Sb. therefore applies. Measuring ad conversions is not necessary for the sign-up service, so the exemption does not apply. Doing this server-side without a cookie does not change the result.
- Counter-argument: a server only reads its own request URL, and Art. 5(3) is about the device. This is defensible but goes against the EDPB text. Do not rely on it.

(b) GDPR basis for storing gclid and sharing it with Google.
- The gclid is linked to an identifiable sign-up, so it is personal data. The basis is consent, Art. 6(1)(a). The ePrivacy consent in (a) is needed anyway, and the EDPB and the ÚOOÚ do not accept legitimate interest for processing that follows non-exempt device access.
- Google acts as an independent controller for conversion measurement under the Google Ads Controller-Controller Data Protection Terms. UbyHost must name Google as a recipient and link to Google's Business Data Responsibility page (EU User Consent Policy help, checklist item 5).

(c) Google's EU User Consent Policy and the consent fields.
- The policy requires "legally valid consent" for cookies or other local storage where legally required, and for personal data used for ads personalization. It also requires: consent records with "the text and choices presented" and "the date and time"; clear instructions for revocation, as easy as giving consent; identification of each party receiving data; and a prominent link to business.safety.google/privacy.
- The CSV upload has two consent columns: **Ad User Data** ("consent for sending user data to Google for advertising purposes") and **Ad Personalization**. Allowed values are **Granted** or **Denied**. The default is unset (Google Ads Help 7014069). The Google Ads API says that if consent is not set, "it's possible that your conversions won't be attributable". For Customer Match, unset and "UNSPECIFIED" count as no consent (Help 14310715).
- Since March 2024 uploads for EEA users need these columns, or conversions may not count (PPC News Feed, 27 Feb 2024). [UNVERIFIED in a Google primary source for click conversions specifically. The Customer Match FAQ confirms the March 2024 requirement for that product.]
- Ad Personalization: UbyHost only measures, it does not build remarketing lists. Ask only for measurement consent and send `Ad Personalization = Denied`. [UNVERIFIED: whether Google counts click conversions with Ad User Data Granted and Ad Personalization Denied. I expect yes, because personalization is a separate purpose. Check the upload diagnostics after the first upload.]
- A checkbox works as the consent mechanism. Google requires a CMP or Consent Mode only when Google tags run on the site. UbyHost runs no Google tag.

(d) Import window.
- **90 days** after the click for GCLID-based imports. The error "This click is too old for its conversion to be imported" appears because Google keeps GCLIDs for only 90 days (Offline conversion imports FAQs, Q4 and Q6). Enhanced conversions for leads with user data (not used here) allow 63 days.
- Conversions within about 1 day of the click may not be recordable yet. Wait 4 to 6 hours after creating a new conversion action before the first upload (Help 7014069, 7012522).
- Google labels this file method "legacy" and recommends Data Manager and enhanced conversions for leads. CSV upload still works. Do not turn on enhanced conversions for leads at account level, or the GCLID-only template can fail (Help 7014069).

### Exact CSV format

Field names as documented in Google Ads Help answer 7014069 (field list and consent fields):

```
Parameters:TimeZone=Europe/Prague
Google Click ID,Conversion Name,Conversion Time,Conversion Value,Conversion Currency,Order ID,Ad User Data,Ad Personalization
Cj0KCQjw...,Host signup,2026-10-03 14:05:00+0200,1,CZK,u_10423,Granted,Denied
```

- Required: `Google Click ID`, `Conversion Name` (exact spelling and case of the conversion action), `Conversion Time`.
- Optional: `Conversion Value`, `Conversion Currency` (ISO 4217), `Order ID` (use the internal sign-up ID to deduplicate).
- Consent: `Ad User Data`, `Ad Personalization`, values `Granted` or `Denied`.
- Time format: `yyyy-MM-dd HH:mm:ss+z`, for example `2026-10-03 14:05:00+0200`. Google also accepts `MM/dd/yyyy HH:mm:ss`, `yyyy-MM-ddTHH:mm:ss+z` and `yyyy-MM-dd HH:mm:ss Europe/Prague`. Set the time zone both in the `Parameters:TimeZone=` row (time zone ID recommended, to avoid DST errors) and in each timestamp.
- Do not add columns that are not in the template. Do not include e-mail or other unhashed personal data.
- [UNVERIFIED: the exact header string in Google's downloadable template, including column order and capitalisation. The names above are copied from the Help article text. The template file from gstatic did not load. Before the first upload, download the template in Google Ads (Goals > Conversions > Uploads > Templates) and diff its headers against the exporter.]

### What the product must do
Code:
- Landing and sign-up pages: read `gclid` (and `gbraid`/`wbraid` if present) from the query string on the server. Put it only into a hidden form field on the sign-up page. Do not write it to a cookie, localStorage, the database or Umami until the form is submitted with the checkbox ticked.
- If the visitor moves from the landing page to the sign-up page, carry the value in the sign-up link query string (`/signup?gclid=...`), not in a cookie.
- On submit:
  - Checkbox ticked: store `gclid`, `gclid_captured_at` (the landing-page request time, carried in a signed hidden field), `ads_consent = true`, `ads_consent_at`, `ads_consent_text_version` (for example `ads-v1-cs`), and the exact displayed text in a `consent_texts` table.
  - Checkbox not ticked: discard the gclid and store nothing about it.
- Access logs: Caddy (and Cloudflare, if used) log full URLs, so the gclid ends up in logs. Either strip `gclid`, `gbraid`, `wbraid` from logged URIs, or keep access logs for 14 days or less. Pick one. Stripping is better.
- Exporter (admin, manual CSV): select rows where `ads_consent = true`, consent not withdrawn, `gclid_captured_at` within the last 85 days (a safety margin inside the 90-day window), and not yet uploaded. Write the CSV format above with `Ad User Data=Granted`, `Ad Personalization=Denied`. Record `uploaded_at`.
- Delete the gclid 90 days after the click, or 30 days after a successful upload, whichever comes first. Keep the consent record (text version, timestamps) for the account lifetime plus 3 years, as proof. [UNVERIFIED: the 3 years comes from the general civil limitation period, § 629 občanský zákoník, which I did not open.]
- Withdrawal: Settings > Privacy > "Use my sign-up to measure UbyHost's Google Ads" toggle. Off means: delete the gclid if not uploaded, exclude the row from future exports, and log the withdrawal. If it was already uploaded within the last 55 days, retracting it via conversion adjustment is optional (FAQ Q8 allows adjustments up to 55 days).

Sign-up checkbox (unchecked by default, not required, placed under the terms checkbox):
- EN: "Optional: I agree that UbyHost may record that I came from a Google ad and share that click identifier with Google (an independent controller) to measure our ad campaigns. No personalised ads. You can withdraw anytime in Settings. [How Google uses data](https://business.safety.google/privacy/)"
- CS: "Nepovinné: Souhlasím, aby UbyHost zaznamenal, že jsem přišel z reklamy Google, a předal tento identifikátor kliknutí společnosti Google (samostatnému správci) k měření úspěšnosti našich reklam. Bez personalizované reklamy. Souhlas můžete kdykoli odvolat v Nastavení. [Jak Google používá data](https://business.safety.google/privacy/)"

Show the checkbox only when a gclid is present. Without a gclid there is nothing to consent to, which keeps the form short.

Privacy-policy paragraph:
- EN: "Google Ads measurement. If you arrived at our sign-up page from a Google ad, the page address contains a click identifier (gclid). We keep this identifier only if you tick the optional consent box during sign-up. We then send it to Google Ireland Ltd. together with the fact and time of your sign-up, so that we can see which ads bring new customers. We do not send your name or e-mail address and we do not use this for personalised advertising. Google processes this data as an independent controller; see https://business.safety.google/privacy/. Legal basis: your consent (Art. 6(1)(a) GDPR and § 89(3) of Act No. 127/2005 Coll.). We delete the identifier at the latest 90 days after the ad click. You can withdraw consent anytime in Settings > Privacy. Withdrawal does not affect processing before it."
- CS: "Měření reklam Google Ads. Pokud jste na registrační stránku přišli z reklamy Google, obsahuje adresa stránky identifikátor kliknutí (gclid). Tento identifikátor uchováme jen tehdy, pokud při registraci zaškrtnete nepovinný souhlas. Poté jej spolu s informací o registraci a jejím čase předáme společnosti Google Ireland Ltd., abychom věděli, které reklamy přivádějí nové zákazníky. Vaše jméno ani e-mail nepředáváme a údaje nepoužíváme k personalizované reklamě. Google tyto údaje zpracovává jako samostatný správce, viz https://business.safety.google/privacy/. Právní základ: váš souhlas (čl. 6 odst. 1 písm. a) GDPR a § 89 odst. 3 zákona č. 127/2005 Sb.). Identifikátor smažeme nejpozději 90 dní po kliknutí na reklamu. Souhlas můžete kdykoli odvolat v Nastavení > Soukromí. Odvolání nemá vliv na zpracování před ním."

### Residual risk
**Low** with the checkbox. **Medium to high** without it, because the EDPB names tracked URLs explicitly, and Google's policy lets Google restrict conversion measurement for non-compliant accounts. Commercial cost: expect only a minority of hosts to tick the box, so measured conversions will be undercounted. That is acceptable for a small budget. Use Google Ads' own click data and sign-up totals as a sanity check.

### Sources
- https://www.thesedonaconference.org/sites/default/files/meeting_paper/Recommended%204.5_EDPB%20Guidelines%202-2023%20on%20Technical%20Scope%20of%20Art.%205(3)%20of%20ePrivacy%20Directive.pdf (para 31-33, 46-51)
- https://elegal.cz/analyticke-cookies-bez-souhlasu
- https://www.google.com/about/company/user-consent-policy/
- https://www.google.com/about/company/user-consent-policy-help/
- https://support.google.com/google-ads/answer/7014069?hl=en
- https://support.google.com/google-ads/answer/7012522?hl=en
- https://support.google.com/google-ads/answer/10029210?hl=en
- https://support.google.com/google-ads/answer/14310715?hl=en
- https://developers.google.com/google-ads/api/docs/conversions/upload-offline
- https://business.safety.google/adscontrollerterms/
- https://ppcnewsfeed.com/ppc-news/2024-02/consent-mode-v2-compliance-for-offline-conversion-imports/ (secondary)

---

## 4. Retention periods

### Position
| Data | Who decides | Retention | Statute | Implementation |
|---|---|---|---|---|
| Guest book (domovní kniha) entries, foreign and domestic guests | Host (controller); UbyHost as processor | 6 years from the last entry. Signed paper forms replacing the book: 6 years from the end of the foreign guest's stay. | § 101(4) zákon 326/1999 Sb. (the duty to keep the book is in § 103) | Delete each guest record on 31 January of the year after its 6-year period ends, counted from the end of the stay. |
| Stay-fee book (evidenční kniha, poplatek z pobytu) | Host; UbyHost as processor | 6 years from the last entry | § 3g(4) zákon 565/1990 Sb. (record contents in § 3g(2)) | Same records and same deletion job as above. Fee amount or exemption reason is kept per record. |
| Invoices UbyHost issues to hosts | UbyHost (controller) | 10 years from the end of the tax period of the supply | § 35 zákon 235/2004 Sb. (VAT payers). § 31 zákon 563/1991 Sb.: accounting records 5 years, financial statements 10 years from the end of the accounting period | Keep for 10 years from the end of the calendar year, then delete. |
| Passport or ID photos uploaded for verification | Host; UbyHost as processor | No statutory duty. Delete within 7 days after the stay is checked in, or immediately when the host marks the guest verified. Hard cap: 30 days. | Art. 5(1)(c) and (e) GDPR | Nightly purge job. Store only the extracted fields that are legally required. |
| Raw UbyPort request and response XML | UbyHost on the host's behalf (processor) | 90 days | No statute. Operational logs under Art. 5(1)(e) and Art. 32 GDPR. | Keep the XML encrypted, admin-only access. Delete after 90 days. Keep a small receipt row (stay ID, submitted_at, UbyPort result code, reference number, no personal fields) for 6 years, matching the guest-book period, as proof of reporting. |
| Host account data | UbyHost | Contract duration plus 3 years | Limitation period, § 629 zákon 89/2012 Sb. [UNVERIFIED, not opened] | Anonymise 3 years after account closure, except invoices. |
| gclid and ads consent | UbyHost | gclid: 90 days after the click at most. Consent record: account lifetime plus 3 years. | Art. 7(1) GDPR (proof of consent); Google UCP (keep consent records) | See section 3. |
| Onboarding opt-out suppression list | UbyHost | As long as UbyHost sends such e-mails | ÚOOÚ FAQ Q19, Art. 6(1)(c) | Store a hash of the e-mail address. |

### Reasoning
- § 101(4) zákon 326/1999 Sb. (text from the MZe mirror of the statute): "Domovní knihu ubytovatel uchovává po dobu 6 let od provedení posledního zápisu. Listinné dokumenty nahrazující domovní knihu je ubytovatel povinen uschovávat po dobu 6 let od ukončení ubytování cizince." The retention rule is in § 101(4), not § 103. § 103 lists the host's duties, including keeping the book. [UNVERIFIED: that the mirror shows the version in force on 3 Oct 2026. Check on e-sbirka.gov.cz.]
- § 3g(4) zákon 565/1990 Sb. (esipa.cz consolidated text, version from 1 Jan 2025): "Plátce poplatku je povinen uchovávat evidenční knihu po dobu 6 let ode dne provedení posledního zápisu." The section is § 3g, not § 3i. § 3h is the simplified regime for event organisers.
- Interpretation risk: both laws count 6 years "from the last entry" of the book. For a continuously kept electronic book, a literal reading means never deleting while the property is active. Counting per record (6 years from the end of each stay) matches the GDPR storage-limitation principle and the rule for the paper forms in § 101(4), second sentence. UbyHost is the processor, so make the per-record rule the documented default and say so in the host DPA. The host remains the controller and can export the book before deletion.
- § 35 zákon 235/2004 Sb.: tax documents are kept 10 years from the end of the tax period in which the supply took place (Pohoda summary of § 35). If UbyHost is not a VAT payer, the VAT rule does not apply, but 10 years is still a safe single rule. § 31 zákon 563/1991 Sb.: 5 years for accounting documents and 10 years for financial statements (epravo summary). [UNVERIFIED: whether a new accounting act replaces 563/1991 before 2027.]
- ID photos: neither 326/1999 nor 565/1990 requires a copy of the document. They require only listed data (§ 3g(2) zákon 565/1990 Sb.: document type and number). Keeping photos of passports is high-risk data without a legal need. [UNVERIFIED: the Czech ID card act restricts copying of občanský průkaz without the holder's consent. I did not open it. This is another reason to delete quickly.]
- 90 days for raw XML is proportionate. UbyPort rejections and police queries surface within days or weeks. The small receipt row keeps the proof the host needs without keeping full guest data twice.

### What the product must do
- One `retention.py` module with a table of data classes and periods (the table above), run nightly by the scheduler. Every deletion writes an audit line: class, count, cutoff date.
- Host export: before any guest-book deletion run, the host can download the book (CSV and PDF) for any period.
- Account closure: offer an export. Then delete guest data within 30 days, or return it to the host on request (Art. 28(3)(g) GDPR). Keep invoices for 10 years.
- Backups: the age-encrypted nightly backups and the S3 copies roll off after 30 days. State this, so a deleted record is gone from backups within 30 days.

Privacy-policy paragraph (UbyHost's own data):
- EN: "How long we keep data. Invoices: 10 years from the end of the year of issue (Act No. 235/2004 Coll., § 35). Account data: while your account is active and 3 years after closure. Sign-up click identifier from Google Ads: at most 90 days after the click. Consent records: while your account is active and 3 years after. Backups are overwritten within 30 days."
- CS: "Jak dlouho údaje uchováváme. Faktury: 10 let od konce roku vystavení (§ 35 zákona č. 235/2004 Sb.). Údaje účtu: po dobu trvání účtu a 3 roky po jeho zrušení. Identifikátor kliknutí z Google Ads: nejvýše 90 dní od kliknutí. Záznamy o souhlasech: po dobu trvání účtu a 3 roky poté. Zálohy se přepisují do 30 dní."

DPA clause for hosts (guest data):
- EN: "UbyHost keeps each guest record for 6 years after the end of the stay (§ 101(4) of Act No. 326/1999 Coll.; § 3g(4) of Act No. 565/1990 Coll.) and then deletes it, unless the host exports it first. ID document photos are deleted within 7 days after check-in and never later than 30 days after upload. Raw UbyPort messages are deleted after 90 days. A record of each submission without personal data is kept for 6 years."
- CS: "UbyHost uchovává každý záznam o hostovi 6 let od konce pobytu (§ 101 odst. 4 zákona č. 326/1999 Sb.; § 3g odst. 4 zákona č. 565/1990 Sb.) a poté jej smaže, pokud si jej ubytovatel předtím nevyexportuje. Fotografie dokladů totožnosti se mažou do 7 dnů od příjezdu, nejpozději 30 dní od nahrání. Původní zprávy pro UbyPort se mažou po 90 dnech. Záznam o každém odeslání bez osobních údajů se uchovává 6 let."

### Residual risk
**Medium** for the guest-book counting rule (per record versus per book). **Low** for everything else. The per-record reading is the more privacy-protective one, and the host can keep an exported copy.

### Sources
- https://mze.gov.cz/public/portal/mze/legislativa/vap48225-153239 (§ 101 zákon 326/1999 Sb.)
- https://esipa.cz/sbirka/sbsrv.dll/sb?DR=AZ&CP=1990s565-2021s363_20250101 (§ 3g zákon 565/1990 Sb.)
- https://portal.pohoda.cz/dane-ucetnictvi-mzdy/dph/danovy-doklad/uchovavani-danovych-dokladu/ (§ 35 zákon 235/2004 Sb.)
- https://www.epravo.cz/top/clanky/delka-archivace-ucetnich-dokumentu-42894.html (§ 31 zákon 563/1991 Sb.)
- https://www.chaman.cz/en/pruvodci/evidence-hostu-ubyport (secondary, practice)
- https://uoou.gov.cz/cinnost/obchodni-sdeleni/casto-kladene-otazky-k-zakonu-c-4802004-sb (Q19)

---

## 5. Roles, privacy policy and subprocessors

### Position
| Processing | UbyHost's role | Legal basis (UbyHost's own processing) |
|---|---|---|
| Guest data: guest book, stay-fee book, UbyPort reports, ID photos, guest e-mails sent for the host | **Processor** for the host (Art. 28 GDPR). The host is the controller, with legal duties under zákon 326/1999 Sb. and zákon 565/1990 Sb. | Not applicable. The host's basis is Art. 6(1)(c). |
| Host account, login, 2FA, support, invoices | **Controller** | Art. 6(1)(b) contract; 6(1)(c) tax and accounting law; 6(1)(f) security |
| Onboarding e-mails | Controller | Art. 6(1)(f); § 7(3) zákon 480/2004 Sb. |
| Umami analytics on marketing pages | Controller; Umami is UbyHost's processor | Art. 6(1)(f); § 89(3) exemption |
| gclid and Google Ads conversion upload | Controller; **Google is an independent controller and recipient**, not a subprocessor | Art. 6(1)(a) consent |
| Turnstile bot check on login and PIN | Controller; Cloudflare's role [UNVERIFIED] | Art. 6(1)(f) security. Strictly necessary under § 89(3). |

### Reasoning
- Hosts decide whom they accommodate and carry the statutory duties, so they are controllers. UbyHost acts on their instructions, so it is a processor and needs a written DPA with each host (Art. 28(3)). It must list its subprocessors and give hosts notice of changes with a right to object (Art. 28(2) and (4)).
- Google Ads: Google's Controller-Controller Data Protection Terms govern advertiser data that Google uses for measurement. Google therefore goes in the "recipients" section, not the subprocessor list, and the EU User Consent Policy disclosure link is required.
- AWS: the AWS GDPR DPA, with SCCs, is part of the AWS Service Terms and applies automatically (AWS GDPR Center). Region choice is under the customer's control.
- Cloudflare: the customer DPA includes the EU SCCs and states that Cloudflare is certified under the EU-US Data Privacy Framework (DPA sections 6.2 and 6.4). The app already loads Cloudflare Turnstile, so Cloudflare is in scope even if the optional Cloudflare proxy is not used.
- Hosting region: the hosting VM is AWS Lightsail. [UNVERIFIED: that it runs in Frankfurt (eu-central-1). The architecture review marks the region as an assumption. Confirm before writing "all data in the EU".]

### Subprocessor list (publish at /subprocessors, link it from the host DPA)

| Subprocessor | Purpose | Data | Location | Transfer safeguard |
|---|---|---|---|---|
| Amazon Web Services EMEA SARL (AWS Lightsail) | Application hosting and database | All app data, including guest data | EU, Frankfurt [UNVERIFIED region] | AWS DPA in the Service Terms, SCCs |
| Amazon Web Services EMEA SARL (Amazon SES) | Sending e-mail | Recipient address, e-mail content | eu-central-1 (Frankfurt) | Same |
| Amazon Web Services EMEA SARL (Amazon S3) | Encrypted backups, later file storage | All app data, age-encrypted | eu-central-1 (Frankfurt) | Same |
| Cloudflare, Inc. | Turnstile bot protection; optional CDN and proxy | IP address, browser signals, request metadata | Global network, US company | Cloudflare DPA, EU SCCs, EU-US DPF |
| Umami Software, Inc. (Umami Cloud) | Website statistics, marketing pages only | Page views, referrer, browser, device, country, short-lived visit hash | EU region | Umami DPA [UNVERIFIED contents] |

Recipients that are not subprocessors: Google Ireland Ltd. (Google Ads conversion measurement, independent controller, only with consent); Policie ČR, UbyPort (statutory reporting on the host's behalf); the municipality (stay-fee reports, if the host uses that feature).

Entity names: AWS contracts with EEA customers through Amazon Web Services EMEA SARL [UNVERIFIED, not opened this session]. Use the entity printed on the AWS invoice.

### What the product must do
- Publish: privacy policy (EN, CS), subprocessor page, host DPA (zpracovatelská smlouva) accepted at sign-up through a checkbox linked to the terms. Store the version and timestamp.
- E-mail hosts 30 days before adding a subprocessor (Art. 28(2) general authorisation). Store the notice.
- Records of processing (Art. 30): one page per row of the role table above.

Privacy-policy paragraph on roles:
- EN: "Who is responsible. For your account, invoices, our website statistics and Google Ads measurement, [Company name], IČO [xxxxxxxx], [address] is the controller. For the data of your guests (guest book, stay-fee records, reports to the foreign police through UbyPort and any document photos), you as the accommodation provider are the controller and we process the data only on your instructions as your processor, under our data processing agreement. Our subprocessors are listed at [link]. Google Ireland Ltd. receives the Google Ads click identifier only if you consent, and it processes this as an independent controller."
- CS: "Kdo odpovídá za zpracování. Za údaje vašeho účtu, faktury, statistiky návštěvnosti webu a měření reklam Google Ads je správcem [Obchodní firma], IČO [xxxxxxxx], [sídlo]. Za údaje vašich hostů (domovní kniha, evidence k poplatku z pobytu, hlášení cizinecké policii přes UbyPort a případné fotografie dokladů) jste správcem vy jako ubytovatel a my je zpracováváme pouze podle vašich pokynů jako zpracovatel na základě zpracovatelské smlouvy. Seznam našich subzpracovatelů najdete zde: [odkaz]. Společnost Google Ireland Ltd. obdrží identifikátor kliknutí z Google Ads jen s vaším souhlasem a zpracovává jej jako samostatný správce."

### Residual risk
**Low**, once the Lightsail region is confirmed as EU and the Umami DPA has been read. **Medium** until then: the privacy policy must not say "EU only" before both are verified.

### Sources
- https://aws.amazon.com/compliance/gdpr-center/
- https://www.cloudflare.com/cloudflare-customer-dpa/
- https://business.safety.google/adscontrollerterms/
- https://www.google.com/about/company/user-consent-policy-help/
- https://docs.umami.is/docs/cloud/faq
- https://umami.is/dpa (title only)

---

## 6. Meta Conversions API: fbclid capture and a server-side sign-up event

Added 4 October 2026 for WP21. The owner will run Meta (Facebook and Instagram) ads and also post links in Facebook groups. Meta Pixel and Meta cookies are out of scope: the event is sent only from the server.

### Position
**Explicit consent is needed, on the same reasoning as for `gclid` (section 3).** Show a separate, optional, unchecked box on the sign-up form only when the link carried `fbclid` and the Conversions API is configured. Store `fbc`, and the browser type string (User-Agent) of the sign-up submit, only when the box is ticked. After the e-mail address is verified, send Meta one `CompleteRegistration` event from a background job, with `fbc` and `client_user_agent` as the only customer parameters and `opt_out = true` (attribution only). For collecting and sending the data, UbyHost and Meta Platforms Ireland Ltd. are **joint controllers** (Art. 26 GDPR) under the Meta Business Tools Terms and the Controller Addendum; Meta is an independent controller for what it does afterwards. The wording must say "came from Facebook or Instagram", not "from an ad", because Facebook adds `fbclid` to ordinary post and group links too.

### Reasoning
(a) ePrivacy: reading `fbclid` from the URL is gaining access to information on the device.
- `fbclid` is an identifier Meta appends to the outbound URL. It has no role in locating the resource. EDPB Guidelines 2/2023 para 48 to 51 (tracking links, identifiers in URLs distributed over a public network) and para 33 (it does not matter who appended the identifier) apply exactly as to `gclid`. [Relied on the section 3 reading of the guideline PDF; not reopened this session.]
- § 89(3) zákon 127/2005 Sb. therefore requires consent. Measuring campaigns is not strictly necessary for the sign-up service, so the exemption does not apply. Doing it on the server without a cookie does not change that.
- `fbclid` also appears on links shared in ordinary posts and groups (Meta calls it the "ClickID" and documents it for ad clicks; its presence on organic links is common knowledge and visible in practice, but Meta's page does not say so). [UNVERIFIED in a Meta primary source for organic links.] Saying "from a Facebook ad" would therefore misdescribe many visitors. The box says "came from Facebook or Instagram".

(b) GDPR basis and roles.
- `fbc` is linked to a named account and is designed to let Meta match the click to a Meta user. It is personal data. Basis: consent, Art. 6(1)(a). As in section 3, legitimate interest is not available after non-exempt device access.
- Meta Business Tools Terms (Czech version as served, section on GDPR roles): for event data about actions on the advertiser's website, where the advertiser and Meta Ireland jointly determine purposes and means, "jste v souladu s čl. 26 nařízení GDPR společnými správci", covering "shromažďování takových osobních údajů prostřednictvím určitých nástrojů společnosti Meta pro firmy a jejich následné předání společnosti Meta Ireland" for the purposes in sections 2.a.iii to 2.a.v.2. After the transfer, "zůstává společnost Meta Ireland nezávislým správcem". For campaign reports and analytics (sections 2.a.i and 2.a.ii), Meta Ireland acts as the advertiser's processor under the Meta Data Processing Terms.
- Controller Addendum (Czech version): the joint processing covers collection and transmission only. Responsibility table: lawfulness (Art. 6) each for its own processing; information to data subjects (Art. 13, 14) and making the essence of the arrangement available (Art. 26(2)) is **the advertiser's** job, with minimum content: that Meta Ireland is a joint controller, what the purposes are, that Meta's privacy policy (facebook.com/about/privacy) has Meta's details, legal basis and how to exercise rights against Meta, and that Meta handles Art. 15 to 20 rights for data it stores after the joint processing. Requests the advertiser receives about the joint processing must be passed to Meta "neprodleně, nejpozději však do sedmi kalendářních dnů".
- CJEU C-40/17 Fashion ID is the case law behind this split (joint control for collection and transmission only). [Not opened this session.]

(c) What Meta may do with the event, and why the box does not say "no personalised ads".
- Business Tools Terms: event data may be used for measurement and campaign reports, for ad delivery optimisation after aggregation, to "personalizaci funkcí a obsahu (včetně reklam a doporučení)", for safety and security, and for research and development.
- The server event parameter `opt_out` "indicates we should not use this event for ads delivery optimization. If set to true, we only use the event for attribution." UbyHost sends `opt_out = true`, which matches a consent "to measure our campaigns".
- [UNVERIFIED] whether `opt_out = true` also keeps Meta from the other own-purpose uses (personalisation, research). The Terms do not say. So the box and the policy say that Meta then uses the data as its own controller, and do not promise "no personalised ads" as the Google text does.
- The Terms require consent "ověřitelným způsobem" before Meta may store or access information on the device in the EU. UbyHost lets Meta store nothing on the device. Its own reading of `fbclid` needs consent anyway under (a), and the consent record (text version, time) makes it verifiable.
- The notice duty in the Terms is worded for pages that use Meta pixels ("na každé webové stránce, na které se naše pixely používají"). No pixel runs, so the privacy policy paragraph is the notice. [Interpretation.]

(d) Conversions API facts (Meta developer documentation, opened 4 Oct 2026).
- Endpoint: `POST https://graph.facebook.com/{API_VERSION}/{PIXEL_ID}/events`, access token as a parameter. Meta's example uses form fields `data` (JSON array) and `access_token`. The dataset (pixel) ID and a token generated in Events Manager are enough; no app review.
- Version: latest Graph API version is **v26.0** (introduced 29 July 2026; changelog). Conversions API versions follow the Graph API schedule, each supported for at least two years. Kept in config (`UBYHOST_META_GRAPH_VERSION`).
- Required per event: `event_name`, `event_time` (Unix seconds), `user_data`, `action_source`. `event_time` "can be up to 7 days before you send an event"; if any event is older, "we return an error for the entire request". Up to 1,000 events per request; one invalid event rejects the batch.
- `fbc` format: `fb.<subdomainIndex>.<creationTime>.<fbclid>`. When generated on a server without an `_fbc` cookie, use subdomain index `1`, and as creation time "the timestamp when you first observed or received this fbclid value", in milliseconds. Do not change the case of the `fbclid`. Meta recommends a 90-day `_fbc` cookie or server-side storage; UbyHost uses server-side storage, only with consent.
- Customer information: "You must provide at least one" `user_data` parameter. The v13 baseline rule lists combinations that are too broad on their own (city/state/zip/country/gender/user agent; date of birth plus user agent; first or last name plus gender). `fbc` is not in any of them, so `fbc` alone is a valid customer-information set.
- The parameters page and best practices say website events "require" `client_user_agent` and `event_source_url`. **Owner decision (4 October 2026): include `client_user_agent`.** The browser type string (User-Agent header) is captured when the sign-up form is submitted, and only when the Meta box is ticked; it is stored on the `ad_click` row, sent with the event, and deleted together with `fbc`. The consent text names it ("browser type string"), so the Meta consent version is `ads-meta-v2`. With `fbc` present, `fbc` plus user agent is not one of the v13 combinations that are too broad. Changing `action_source` is not an option, because Meta requires it to be accurate.
- `event_id`: used with `event_name` for deduplication against the browser Pixel within 48 hours. No Pixel runs here; a random `event_id` per sign-up still makes retries safe.
- `test_event_code`: shows events in Events Manager > Test events. Meta: events sent with it "are not dropped. They flow into Events Manager and are used for targeting and ads measurement purposes." Use it on staging only, with consenting test accounts.
- `data_processing_options`: only `LDU` (Limited Data Use) for US states exists. There is no EU option. UbyHost omits the field.

(e) Retention.
- After a successful send nothing in UbyHost uses `fbc` or the browser type string. The owner's default is to delete both 7 days after sending. An event that was refused, failed after retries, or could no longer be sent within Meta's 7-day `event_time` window is deleted at the next cleanup. Absolute cap: 90 days after the click (matching Meta's own 90-day `_fbc` lifetime). Keep the consent record (text version, timestamps) for the account lifetime plus 3 years, as in section 3.
- Meta's default attribution setting is 7-day click, 1-day view. [UNVERIFIED this session.] It does not affect what UbyHost keeps.

(f) Transfers. The recipient is Meta Platforms Ireland Ltd. (Dublin). The Terms point to a Meta European Data Transfer Addendum for onward transfers. [UNVERIFIED: its content and Meta's EU-US Data Privacy Framework status were not opened.]

### What the product must do
Code (implemented in WP21):
- Read `fbclid` on the landing, pricing and sign-up pages on the server, validate it (`[A-Za-z0-9_-]{1,500}`), and carry it with its first-seen time only in the signed `click` value (sign-up link and hidden field). No cookie, no Pixel, no Meta script.
- Show the Meta box only when `fbclid` is present and `UBYHOST_META_DATASET_ID` and `UBYHOST_META_ACCESS_TOKEN` are set. Unchecked, not required, its own `consent_texts` version (`ads-meta-v2-en` / `ads-meta-v2-cs`; v2 names the browser type string).
- Ticked: store `fbc = fb.1.<first-seen ms>.<fbclid>`, the User-Agent header of the sign-up submit (`client_user_agent`, printable ASCII, at most 512 characters), click time, consent time and text version in `ad_click`. Not ticked: store nothing about the click and no user agent.
- After e-mail verification, queue the event. A scheduler job (every 10 minutes) sends it: claim with compare-and-set, HTTP call with no transaction open, retries with backoff for network errors, 5xx, 429 and transient Graph errors, up to 8 attempts; invalid events fail at once; token or dataset errors raise an admin alert and keep retrying; events older than Meta's window expire unsent.
- Payload, exactly: `event_name = CompleteRegistration`, `event_time`, `event_id` (random), `action_source = website`, `event_source_url = <base URL>/signup` (no query string), `opt_out = true`, `user_data = {fbc, client_user_agent}` (`client_user_agent` left out if the browser sent none). Plus `test_event_code` only when configured. No e-mail, phone, name or IP address.
- Delete `fbc` and the browser type string 7 days after sending, at once after failure, expiry or withdrawal, and at the latest 90 days after the click.
- Settings > Privacy: "Use my sign-up to measure UbyHost's Facebook and Instagram campaigns" toggle. Off: delete `fbc`, never send an unsent event, log the withdrawal. An admin can withdraw on request.
- Admin: store `utm_*` and `signup_source` (`google`, `meta` or `none`). A click without consent never sets the source; the UTM label can.

Process (owner):
- Requests from data subjects about the Meta transfer go to Meta within 7 days (Controller Addendum), using Meta's form.
- Use a test dataset or test accounts with `UBYHOST_META_TEST_EVENT_CODE` on staging, and remove the code in production.

Sign-up checkbox (unchecked, not required, under the terms checkbox, only with `fbclid`):
- EN: "Optional: I agree that UbyHost may record that I came from Facebook or Instagram and send that click identifier and my browser type string, with the fact and time of my sign-up, to Meta Platforms Ireland Ltd. to measure our campaigns. Meta receives it as a joint controller and then uses it as its own controller. You can withdraw anytime in Settings. [How Meta uses data](https://www.facebook.com/privacy/policy/)"
- CS: "Nepovinné: Souhlasím, aby UbyHost zaznamenal, že jsem přišel z Facebooku nebo Instagramu, a předal tento identifikátor kliknutí a údaj o typu mého prohlížeče spolu s informací o mé registraci a jejím čase společnosti Meta Platforms Ireland Ltd. k měření úspěšnosti našich kampaní. Meta je při předání společným správcem a dále údaje zpracovává jako samostatný správce. Souhlas můžete kdykoli odvolat v Nastavení. [Jak Meta používá data](https://www.facebook.com/privacy/policy/)"

Privacy-policy paragraph:
- EN: "Facebook and Instagram measurement. If you arrived at our sign-up page from Facebook or Instagram, from an ad or from an ordinary post or group, the page address usually contains a click identifier (fbclid). We keep it only if you tick the optional Meta consent box during sign-up. After you confirm your e-mail address, our server sends Meta Platforms Ireland Ltd. one sign-up event with this identifier, your browser type string (the User-Agent your browser sent with the sign-up form), the time of sign-up, a random event number and the address of our sign-up page. We do not send your name, e-mail address, phone number or IP address, we do not use the Meta Pixel, and we set no cookie for this. We mark the event for measurement only, so that Meta uses it to report on our campaigns and not to optimise ad delivery. For collecting and sending these data, we and Meta Platforms Ireland Ltd. are joint controllers under Art. 26 GDPR (Meta Controller Addendum, https://www.facebook.com/legal/controller_addendum). Meta is responsible for your rights under Art. 15 to 20 GDPR for the data it stores after receiving them, and it processes them further as an independent controller; see https://www.facebook.com/privacy/policy/. Legal basis: your consent (Art. 6(1)(a) GDPR and § 89(3) of Act No. 127/2005 Coll.). We delete the identifier and the browser type string 7 days after they were sent, and if they were never sent, at the latest 90 days after the click. You can withdraw consent anytime in Settings > Privacy. Withdrawal does not affect processing before it."
- CS: "Měření na Facebooku a Instagramu. Pokud jste na registrační stránku přišli z Facebooku nebo Instagramu, ať už z reklamy, nebo z běžného příspěvku či skupiny, obsahuje adresa stránky obvykle identifikátor kliknutí (fbclid). Uchováme jej jen tehdy, pokud při registraci zaškrtnete nepovinný souhlas pro Metu. Po potvrzení vaší e-mailové adresy odešle náš server společnosti Meta Platforms Ireland Ltd. jednu událost registrace s tímto identifikátorem, údajem o typu vašeho prohlížeče (User-Agent, který prohlížeč odeslal s registračním formulářem), časem registrace, náhodným číslem události a adresou naší registrační stránky. Vaše jméno, e-mail, telefon ani IP adresu nepředáváme, nepoužíváme Meta Pixel a nenastavujeme k tomu žádné cookies. Událost označujeme jen pro měření, aby ji Meta použila k vykázání výsledků našich kampaní, a ne k optimalizaci doručování reklam. Pro shromáždění a odeslání těchto údajů jsme my a společnost Meta Platforms Ireland Ltd. společnými správci podle čl. 26 GDPR (Dodatek o správcích společnosti Meta, https://www.facebook.com/legal/controller_addendum). Za vaše práva podle čl. 15 až 20 GDPR k údajům, které Meta po přijetí uchovává, odpovídá Meta, která je dále zpracovává jako samostatný správce, viz https://www.facebook.com/privacy/policy/. Právní základ: váš souhlas (čl. 6 odst. 1 písm. a) GDPR a § 89 odst. 3 zákona č. 127/2005 Sb.). Identifikátor a údaj o typu prohlížeče smažeme 7 dní po odeslání, a pokud odeslány nebyly, nejpozději 90 dní po kliknutí. Souhlas můžete kdykoli odvolat v Nastavení > Soukromí. Odvolání nemá vliv na zpracování před ním."

Recipient line (privacy policy and /subprocessors, "recipients that are not subprocessors"):
- EN: "Meta Platforms Ireland Ltd. (Facebook and Instagram conversion measurement, joint controller for collection and sending, then independent controller), only with your consent." It is not a subprocessor.
- CS: "Meta Platforms Ireland Ltd. (měření konverzí z Facebooku a Instagramu, společný správce pro shromáždění a odeslání, poté samostatný správce), jen s vaším souhlasem."
- Section 5's role table gains a row: "fbclid and Meta Conversions API | Joint controller with Meta Platforms Ireland for collection and sending; Meta independent afterwards | Art. 6(1)(a) consent".

### Residual risk
**Low to medium** with the box. Low for the ePrivacy and GDPR basis, which mirror section 3. Medium for three points outside UbyHost's control: Meta's own further use of the event as an independent controller (the `opt_out` flag limits optimisation only, as far as documented); the `client_user_agent` requirement for website events, now met by sending the browser type string with consent (owner decision, consent version `ads-meta-v2`); and Meta's terms changing by notice. **High** without the box: the EDPB reading covers URL identifiers, and the joint-controller role makes UbyHost answerable for the lawfulness of the collection. Commercial cost: as with Google, only a minority will tick the box, and organic group traffic will show up as Meta-sourced sign-ups without any ad spend behind them.

### Sources actually opened
- https://developers.facebook.com/docs/marketing-api/conversions-api/parameters/fbp-and-fbc (rendered; fbc format, subdomain index 1, first-observed timestamp, 90-day cookie recommendation)
- https://developers.facebook.com/documentation/ads-commerce/conversions-api/parameters/server-event.md (event_time 7-day limit, event_id, action_source, opt_out, data_processing_options)
- https://developers.facebook.com/documentation/ads-commerce/conversions-api/using-the-api.md (endpoint, example request, batch rules, test_event_code)
- https://developers.facebook.com/documentation/ads-commerce/conversions-api/parameters/customer-information-parameters.md (at least one user_data parameter; fbc "do not hash"; client_user_agent required for website events)
- https://developers.facebook.com/documentation/ads-commerce/conversions-api/parameters.md and https://developers.facebook.com/documentation/ads-commerce/conversions-api/best-practices.md (required parameters for website events; v13 invalid combinations)
- https://developers.facebook.com/documentation/ads-commerce/conversions-api/get-started.md (access token from Events Manager, no app review)
- https://developers.facebook.com/documentation/ads-commerce/marketing-api/overview/data-processing-options.md (LDU, US states only)
- https://developers.facebook.com/documentation/ads-commerce/conversions-api/deduplicate-pixel-and-server-events.md (48-hour deduplication)
- https://developers.facebook.com/docs/graph-api/changelog (v26.0 latest, 29 July 2026)
- https://www.facebook.com/legal/terms/businesstools (served in Czech: joint controllership, purposes, consent and notice duties)
- https://www.facebook.com/legal/controller_addendum (served in Czech: scope, responsibility table, 7-day forwarding of requests)
- Not opened this session: EDPB Guidelines 2/2023 (see section 3 sources), CJEU C-40/17 Fashion ID, Meta European Data Transfer Addendum, Meta Data Processing Terms, Meta attribution-setting help pages.

---

## Open items to verify before go-live
1. Read the Umami Cloud DPA: SCCs or DPF, no own-purpose use, retention. If unclear, self-host Umami.
2. Confirm the Lightsail region is eu-central-1.
3. Download the Google Ads click-conversion CSV template and diff its headers against the exporter.
4. After the first upload, check that rows with `Ad Personalization=Denied` are counted.
5. Check § 101 and § 103 zákon 326/1999 Sb. and § 3g zákon 565/1990 Sb. on e-sbirka.gov.cz for amendments after 2025.
6. Check whether the zákon o digitální ekonomice (newsletter opt-out changes) has been passed.
7. First staging send to Meta with `UBYHOST_META_TEST_EVENT_CODE`: confirm that the `website` event with `fbc` and `client_user_agent` is accepted and matched (section 6).
8. Read the Meta Data Processing Terms and the European Data Transfer Addendum before go-live of the Meta integration (section 6).
9. Check in Google Ads (Goals > Conversions > Uploads > template) whether the legacy click-conversion file has GBRAID/WBRAID columns; until then, gbraid/wbraid are stored with consent but not exported (section 3).
