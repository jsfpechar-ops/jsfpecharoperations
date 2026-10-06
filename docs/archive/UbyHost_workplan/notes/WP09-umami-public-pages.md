# WP09: Umami on public pages only

Commit `da17a6f` on local branch `wp08` (amended from `ddabbdc`). It is stacked on WP08 (`e48ec43`, unchanged), so apply WP08 first. The only overlap is the import list in `main.py`. Both commits add one name to the `from . import (...)` block (`analytics`, `passport_photos`).

The amendment implements `04_legal_positions.md` sections 1 and 5 and the privacy-policy paragraph of section 4, which are now the owner's final decisions. All DRAFT markers are gone.

## Summary
- Config, all empty by default: `UMAMI_WEBSITE_ID`, `UMAMI_SCRIPT_URL`, optional `UMAMI_HOST_URL` (`data-host-url`), optional `UMAMI_DOMAINS` (defaults to the host of `UBYHOST_PUBLIC_BASE_URL`). Analytics is on only when the website ID and an `https://` script URL are set. Nothing about Umami is hard-coded except the documented Cloud gateway fallback (below).
- `app/analytics.py` holds the allowlist of public page templates, the tag attributes and the CSP origins. `templating.render` sets `umami_tag` only for allowlisted templates and marks the request; `render_guest` always sets `None`.
- `_umami.html` is the only template with the tag. It is included in `landing.html`, `product.html`, `pricing.html`, `public_guide.html` and `public_legal_base.html` (`/legal`, `/terms`, `/privacy`, `/dpa`, `/subprocessors`).
- Tag: `defer`, `src`, `data-website-id`, `data-domains`, optional `data-host-url`, `data-do-not-track="true"`, `data-exclude-search="true"`, `data-exclude-hash="true"`. No distinct IDs, tags, replays or performance options.
- CSP: `main._harden` uses a public variant only for marked responses. It adds the script origin to `script-src`, and the script origin plus the event endpoint to `connect-src`. Every other page keeps the exact old CSP.
- Events without properties: `login_click` on public `/login` links, `contact_click` on public `mailto:` links.
- Opt-out (section 1): on `/privacy`, while Umami is configured, a panel with the EN/CS text from the legal file, a "Turn off measurement in this browser" / "Vypnout měření v tomto prohlížeči" link and, after a click, "Measurement is off in this browser." with a "Turn measurement back on" / "Znovu zapnout měření" link. `app/static/umami-optout.js` (same-origin, so the CSP needs no change) sets or removes localStorage `umami.disabled`. Only `privacy.html` loads it.
- Privacy policy (EN and CS, owner's final wording):
  - Section 7: "Website analytics" / "Měření návštěvnosti" paragraph from section 1, followed by the opt-out panel and the Do Not Track sentence. Shown only while Umami is configured.
  - Section 3: "Who is responsible" / "Kdo odpovídá za zpracování" paragraph from section 5. Company name, IČO and address come from `UBYHOST_OPERATOR_NAME` / `_ICO` / `_ADDRESS`. "[link]" became `/subprocessors`, which `legal_links` turns into a link.
  - Section 11: "How long we keep data" / "Jak dlouho údaje uchováváme" paragraph from section 4.
  - Placeholders `[Company name], IČO [xxxxxxxx], [registered address]` (CS `[Obchodní firma] ... [sídlo]`) appear only when a value is empty and `UBYHOST_DEPLOYMENT` is not `production`. Production already refuses to start without the three values (`env_guard`), so the placeholder cannot reach production.
  - `PRIVACY_VERSION` 1.5 -> 1.6 in `config.py`, effective date line "4 October 2026. Version 1.6." / "4. října 2026. Verze 1.6.", `docs/ENVIRONMENT.md` table updated.
- `cookie_inventory.py`: a `umami.disabled` localStorage row in `COOKIE_INVENTORY` ("Cookieless analytics (Umami): no cookies are set. This optional key is stored only after you turn measurement off"). It must be in that list because our script writes it and `test_cookie_inventory` checks every `localStorage.setItem`. `COOKIELESS_SERVICES` keeps the Umami entry with the specified note ("cookieless analytics, no cookies set; optional localStorage key umami.disabled only after opt-out").
- `/subprocessors` (version 1.1 -> 1.2): new "Transfer safeguard" column. Rows in the order of section 5: AWS Lightsail, Amazon SES, Amazon S3 (all Amazon Web Services EMEA SARL), Cloudflare, Inc., Umami Software, Inc. (Umami Cloud). Then the two existing conditional rows, Render (demo) and Google Drive (backups). New panel "Recipients that are not subprocessors": Google Ireland Ltd., Policie ČR / UbyPort, the municipality.
- Docs: `deploy/lightsail/.env.example` and `docs/ENVIRONMENT.md` describe the four variables and the opt-out.

## Files changed
- `App/app/analytics.py` (new): allowlist, `enabled`, `tag`, `script_origin`, `connect_origins`, request mark.
- `App/app/static/umami-optout.js` (new): opt-out and opt-back-in toggle.
- `App/app/templates/_umami.html` (new): the only template with the tag.
- `App/app/config.py`: four `UMAMI_*` values; `PRIVACY_VERSION` 1.6.
- `App/app/templating.py`: `umami_tag` in `render`, `None` in `render_guest`.
- `App/app/main.py`: `_csp()` builder, `_public_csp()`, `_harden(..., public_analytics)`. `_CSP` unchanged byte for byte.
- `App/app/templates/landing.html`, `product.html`, `pricing.html`, `public_guide.html`, `public_legal_base.html`: include the partial; event attributes.
- `App/app/templates/_public_header.html`, `_public_footer.html`, `legal.html`, `dpa.html`: event attributes.
- `App/app/templates/privacy.html`: roles, analytics with opt-out, own retention; controller identity with dev placeholders.
- `App/app/templates/subprocessors.html`: safeguard column, recipients panel.
- `App/app/privacy_policy_i18n.py`: final analytics, opt-out, retention, roles and placeholder strings (EN, CS); version 1.6.
- `App/app/subprocessors_i18n.py`: section 5 rows, safeguards, recipients (EN, CS); version 1.2.
- `App/app/routes/legal.py`: `SUBPROCESSOR_IDS`, `RECIPIENT_IDS`, `legal_placeholders`, `cookieless_services`.
- `App/app/cookie_inventory.py`: `umami.disabled` row and `COOKIELESS_SERVICES`.
- `App/tests/test_umami_guard.py` (new): the guard, plus tag-attribute and opt-out tests.
- `App/tests/test_privacy_legal_positions.py` (new): legal text, placeholders, version, register.
- `App/tests/test_accounts.py`: expects `PRIVACY_VERSION == "1.6"`.
- `App/tests/test_legal_contents.py`: LD-4 backup keys now `aws_s3_purpose`/`aws_s3_data`; register version 1.2.
- `App/tests/test_no_tracking.py`: docstring note only.
- `deploy/lightsail/.env.example`, `docs/ENVIRONMENT.md`: variables, opt-out, privacy version.

## Tests added
`tests/test_umami_guard.py`, 40 tests, placeholder IDs and a placeholder script host:
- Static: only `_umami.html` has the tag; only the five shells include it; following extends/include edges, no app, guest, auth or error template reaches it; the allowlist has no app, guest or auth template.
- Unconfigured or `http://` script URL: no tag and the strict CSP everywhere.
- Configured, every public page in CS and EN: tag once with all attributes; CSP origins correct.
- New: the tag's `data-*` attributes are exactly website-id, domains, host-url, do-not-track, exclude-search, exclude-hash. `data-domains` defaults to the host of `PUBLIC_BASE_URL`.
- New: `/privacy` in CS and EN has the opt-out and opt-back-in links with the legal text and loads `umami-optout.js` from `'self'`; the script uses key `umami.disabled` with `setItem`/`removeItem`; only `privacy.html` references the script; no opt-out while Umami is unconfigured; no other public page has it.
- Cloud script without host URL allows `gateway.umami.is`; events carry no properties; `/privacy` and `/subprocessors` describe Umami in EN and CS.
- Auth pages, signed-in app pages, anonymous and claimed guest pages: no marker, strict CSP.

`tests/test_privacy_legal_positions.py`, 7 tests: roles paragraph names the configured operator (name, IČO, address) and links `/subprocessors`; placeholders outside production when empty; own retention paragraph in EN and CS; version 1.6 shown; no DRAFT/NÁVRH markers; every register row and field (including safeguard) rendered in EN and CS; recipients panel.

## Test commands and results (exact counts)
Run from `/tmp/wp/wp08/App` with `/tmp/pr230/App/.venv/bin/python -m pytest -q -p no:cacheprovider ...`:
- `test_umami_guard.py`: 40 passed. `test_privacy_legal_positions.py`: 7 passed.
- `test_no_tracking`, `test_umami_guard`, `test_privacy_legal_positions`, `test_public_*`, `test_legal_*`, `test_cookie_inventory`, `test_security_hardening`, `test_passport_photos`, `test_accounts`: 235 passed.
- Broad suite in three chunks:
  - `test_[a-f]*`: 600 passed, 2 skipped.
  - `test_[g-o]*`: 774 passed, 5 skipped, 1 failed (`test_host_geometry`: Chromium cannot launch here, missing `libXdamage.so.1`).
  - `test_[p-z]*`: 849 passed, 1 failed (`test_stale_submission::test_a_running_batch_without_a_live_claim_becomes_outcome_unknown`; also fails on the unchanged base in the same chunk, order-dependent).
- Ruff (`--select E9,F63,F7,F82,F401,F841`): all checks passed.

## Deviations from the spec and why
- Public pages: besides `landing.html` and `public_legal_base.html`, the standalone marketing pages `product.html`, `pricing.html` and `public_guide.html` also carry the tag, because the legal file says "home, pricing, features, blog, legal pages". Remove them from `analytics.PUBLIC_ANALYTICS_TEMPLATES` and the include if unwanted.
- `UMAMI_HOST_URL` and the Cloud gateway fallback: the live Cloud script posts to `https://gateway.umami.is/api/send`, so a CSP built only from the script origin would block every event.
- The tag in section 1 shows `cloud.umami.is` and `ubyhost.cz` domains. Both come from config here (`UMAMI_SCRIPT_URL`, `UMAMI_DOMAINS`), not hard-coded.
- The analytics paragraph and opt-out appear only while Umami is configured, so the policy never describes a tracker that is not running. The roles and retention paragraphs are always shown.
- Text placement: the "[link]" in the analytics paragraph is the opt-out panel right after "...switch measurement off in your browser here:". The "[link]" in the roles paragraph is `/subprocessors`. The lead words ("Website analytics.", "How long we keep data.", "Who is responsible.") became `h3` headings.
- `umami.disabled` is in `COOKIE_INVENTORY` (so it shows in the cookie table even with Umami off), because our own script writes it and the inventory test requires a row for every key written.
- Subprocessor register:
  - Render and Google Drive are not in the section 5 table but the repo still documents both (demo hosting, optional Drive backups in `privacy.s09_body` and `backup-gdrive.sh`). I kept them as conditional rows after the five. Delete them if the owner has dropped both.
  - S3 row: the legal file says "Encrypted backups" / "age-encrypted". The repo's LD-4 test forbids calling off-site copies encrypted until OPS-2 ships (Drive/S3 still lack `*.age`-only enforcement and expiry). I wrote "Off-site backups" / "Backup archives of all app data". Change both copy and test when OPS-2 lands.
  - Lightsail location says "EU, Frankfurt (eu-central-1)" without the "[UNVERIFIED region]" tag. The previous register already said this.
  - Umami location adds "Used only while the Operator enables it", matching the register's conditional convention.
- Google Ads: there is no `UBYHOST_SIGNUP_ENABLED` flag in the repo, so the Google Ireland recipient line is always listed, with a code comment in `routes/legal.py` and `subprocessors.html` to gate it once sign-up lands. The Google Ads sentences in the roles and retention paragraphs are also unconditional (they are worded "only if you consent" / "at most 90 days").
- The existing `privacy.s11_body` still says host account data is kept "for a reasonable period after termination". The new paragraph below it says 3 years. Not contradictory, but the lawyer may want s11 aligned.
- Version bump: `PRIVACY_VERSION` 1.6 (env default) with the effective date set to 4 October 2026. `TERMS_VERSION` and `DPA_VERSION` stay 1.5. The subprocessor register version (display only, not acceptance-tracked) went to 1.2.

## What Cursor must verify or adapt when applying on the real main
- Re-acceptance: `acceptance.pending()` compares against `config.PRIVACY_VERSION`, and `auth` redirects every signed-in host to `/account/accept` until they accept. The bump to 1.6 therefore makes every existing host accept the privacy policy again on their next request. If production sets `UBYHOST_PRIVACY_VERSION` in `.env`, that value wins and must also be raised to 1.6.
- Set the effective date in `privacy.effective` and `subprocessors.effective` (EN and CS) to the real release date.
- If main has new public page templates, decide whether each goes on the allowlist. The guard fails if a template includes `_umami.html` without being on it.
- If main's `_CSP` changed, `_csp()` must reproduce it exactly (`test_no_tracking.py::test_the_csp_is_exactly_the_reviewed_policy`).
- `request.state` carries the public-page mark from `templating.render` to the middleware. If main rebuilds the scope in a new middleware, re-run `test_public_pages_carry_the_tag_and_a_matching_csp`.
- If main renamed the subprocessor keys or the LD-4 test, re-map `aws_s3_*` there.
- If main added the self sign-up flag, show `recipient_google_ads` only when it is on.

## Manual steps for the owner
- Create the Umami Cloud account in the EU data region and add the site. Accept Umami's DPA and keep a PDF copy. Check it covers US transfers (SCCs or DPF) and no own-purpose use. If not, self-host Umami (legal file, residual risk).
- In the production `.env` only: `UMAMI_SCRIPT_URL` and `UMAMI_WEBSITE_ID` from the tracking code; `UMAMI_HOST_URL` if the snippet has `data-host-url`; `UMAMI_DOMAINS=ubyhost.com,www.ubyhost.com` if `www` is served. Check `UBYHOST_OPERATOR_NAME`, `_ICO`, `_ADDRESS` are the legal entity as registered.
- After deploy: on `/`, the script loads and `/api/send` returns 200 with no CSP error; `/login` and a `/l/...` page load nothing from Umami. On `/privacy`, click "Turn off measurement", reload `/`, and confirm no `/api/send` request; click "Turn measurement back on".
- In Umami, leave Replays, Heatmaps and Distinct IDs off, and do not use the visitor profile view.
- Confirm the Lightsail region is eu-central-1 before relying on "EU, Frankfurt" in the register.
- "Backups are overwritten within 30 days" in the new retention paragraph is true for the server copies today. The Drive and S3 copies expire only once OPS-2 ships. Ship OPS-2 before go-live or soften that sentence.
- Expect every host to be asked to accept the privacy policy 1.6 once after release.
