# UbyHost — UX audit (Phase 1 of the dumbproof overhaul)

**Status:** Phase 1 only. This is the audit, and nothing else changed: no code, template, CSS, JS or string was touched. Phase 2 starts when Joe has read this and says which `UX-N` items to build.
**Brief:** [`PLAN_UX_UI_OVERHAUL.md`](PLAN_UX_UI_OVERHAUL.md) · **Baseline:** `main` @ `b5cc9d7`, **757 tests passing** · **Date:** 2026-09-24

**How it was done.** All five surfaces were audited against the brief's seven-lens rubric (§3), with [`DESIGN.md`](../DESIGN.md), [`LOGO.md`](../LOGO.md) and `tokens.css` treated as product-owner decisions. The screens were **rendered through the real app** (FastAPI `TestClient`, mock UbyPort, `demo.seed()` plus empty and half-configured workspaces) in **EN, CS and with no language cookie**, including error states. Every mail kind was built through its real send path and read back from the outbox. JavaScript was traced by hand, because there is no browser harness and the brief (§0 rule 11) says not to add one. The HTML structure was checked with a spec-compliant parser. Findings cite `file:line` as of `b5cc9d7`. The scratch render scripts were kept out of the repo.

---

## At a glance

| Surface | blocker | high | medium | low | total |
|---|---|---|---|---|---|
| A · Guest form | 2 | 11 | 13 | 10 | 36 |
| B · Auth | 3 | 4 | 11 | 8 | 26 |
| C · Host app | 1 | 14 | 20 | 10 | 45 |
| D · Public site | 1 | 5 | 12 | 13 | 31 |
| E · E-mail | 2 | 5 | 8 | 9 | 24 |
| **All** | **9** | **39** | **64** | **50** | **162** |

**Verdict.** The foundations are better than most products this size. The arrival lane, the inline-error pattern, the host contact footer, key parity, reduced motion and the "Next step" command panel are all real and working. The failures cluster in four places:

1. **Recovery and edge paths.** The happy path is fine, but the path a stressed person takes goes nowhere. Examples: a guest who forgot to sign, a host who lost their phone, a claim link opened in the mail app's own browser.
2. **Language.** Czech hosts get English errors, and foreign guests land on Czech. On two auth screens the language switch destroys state.
3. **"Done" isn't unmistakable.** The guest "all done" screen's main button adds a person. Every save says "reported" even when nothing was sent. The completion mail doesn't say "nothing else to do".
4. **Jargon and bureaucratic tone** in exactly the places the brief warns about: the legal notice, the passport copy and the host "Next step" hints.

### The 9 blockers (fix these first)

| # | where | fix |
|---|---|---|
| UX-1 | A · Form · signature | Block "Continue" on the signature step until signed. If Submit finds no signature, reveal the signature step before showing the message; new `signature_missing` copy |
| UX-2 | A · Stay hub · all done | Remove the duplicate primary "Add another person" (`stay.html:113–117`). Keep a quiet in-card option; new done copy + `all_done_receipt` |
| UX-3 | B · Recovery codes | Hide the language switch on the one-shot recovery page (block override) and move "can't be shown again" above the codes |
| UX-4 | B · 2FA code / chrome | Add `lang_next` so the switch on the 2FA page goes to `/login`; add `GET /login/2fa` → 303 `/login?notice=2fa_expired` so a JSON 405 can't appear |
| UX-5 | B · 2FA code | "Lost your phone? Use a recovery code" `<details>` with a text-keyboard recovery field, plus a "no codes? email support@" line |
| UX-6 | E · claim / claim_resend | Keep the `#c=` secret across the PIN gate: `_safe_return_to` preserves the fragment; `signature.js` appends `location.hash` to the PIN form's `return_to`; TestClient round-trip test. Add the "asked for a PIN?" line to `mail_claim_next_body` (EN/CS) |
| UX-7 | E · submission_problem (transport) | Add the missing `mail.submission_problem.reason_transport` key EN/CS, plus a test that no raw `mail.` key text appears in either part |
| UX-8 | C · Host guest form | Move the verify-identity `<form>` out of the main guest form (button uses `form="verify-{id}"`); add a nesting regression test |
| UX-9 | D · Landing hero + product + guide + final CTAs | ⚑ Replace "Try UbyHost" → `/login` with "Request access" / "Požádat o přístup" → localized `mailto:support@…` plus a visible address line, at all 5 call sites |

### Lowest-scoring screens (dumbproof score ≤ 2 / 5)

| Score | Surface → screen |
|---|---|
| 1 | C → Host guest form (`guest_form_admin.html`): the main action is dead for unverified foreign guests |
| 1 | B → Lost password / lost device (paths that don't exist) |
| 2 | A → Claim · passport step · signature step · legal notice + submit · stay hub |
| 2 | B → Shared auth chrome · 2FA code at login · Recovery codes |
| 2 | C → First run (onboarding) · Stay detail · Property form |
| 2 | D → Public chrome (mobile) · Landing hero · Legal notice · Terms/Privacy/DPA |
| 2 | E → claim · claim_resend · submission_problem (transport variant) |

---

## Decisions for Joe (before or during Phase 2)

These items are marked **⚑** in the backlog. The auditor recommends an answer, but each one is a product-owner, legal or plan-author call, so none gets built until you say so.

1. **Guest default language (A-3 [UX-10]).** Today guests default to Czech (`routes/guest.py:153–163`, pinned by `tests/test_guest_language.py:78`), but the `i18n.py` docstring says English. **Recommendation:** fall back on `Accept-Language` (cs/sk → CS, anything else → EN) on the guest form only. The public site should keep ignoring Accept-Language, because that's deliberate and tested for SEO canonicals (see D, "What's already right").
2. **Czech noun for the host (A-23 [UX-59] + E-15 [UX-59]).** CS copy uses "hostitel" 12× and "ubytovatel" 37× for the same person, and the two auditors split on which to keep. **Recommendation:** use **"hostitel"** in all guest UI and guest mail, as DESIGN.md's PO copy table already does ("Váš hostitel"). It reads human, not bureaucratic (brief §4). Keep "ubytovatel" only inside legal-notice sentences. If you prefer "ubytovatel", update DESIGN.md in the same commit.
3. **Public CTA (D-1 [UX-9]).** "Try UbyHost" leads 5× to `/login`, and `/login` says "No public sign-up… ask your administrator". **Recommendation:** "Request access" / "Požádat o přístup" → a localized `mailto:`. A self-serve sign-up is out of scope, because it's a business change.
4. **Host-mail language (E-14 [UX-80]).** Host mails are hard-coded `"lang": "en"`, and the invoice plan specs a Czech host mail. Pick CS default, EN default, or bilingual subjects until a per-user preference exists.
5. **Legal copy sign-off (A-11b [UX-19], A-30 [UX-117], B-10 [UX-64], D-30 [UX-161]).** These items give the guest legal notice and the privacy processor paragraph plain-language rewrites, collapse the doubled login acceptance text into one line, and cover the public "Professional review" / staging notes. They change legal wording, so a lawyer should glance at them.
6. **Logo sizes vs LOGO.md (B-21 [UX-125], D-21 [UX-152]).** The code renders the login lockup at 178 px (doc: 220), the login hero at 170 px (doc: 300) and the landing final mark at 56 px (doc: 64). The doc also cites a dead selector for the product-mock mark. Either the code moves to the doc or the doc moves to the code.
7. **Tagline and independence line (D-12 [UX-106], D-13 [UX-107], D-18 [UX-112]).** Use the locked tagline "Guest reporting, handled for you." as the final landing CTA, add a "not operated or endorsed by the Czech Police or UbyPort" line, and pick one public name for the house-book feature.
8. **Plan conflicts (C-21 [UX-86], C-30 [UX-95]).** The status label "Exempt / Výjimka" (meaning "no report needed") collides with the stay fee's "Exempt / Osvobodit". **Recommendation:** rename it to "No report needed / Nehlásí se" *before* the stay fee ships. Separately, PLAN_POPLATEK §7.2 (own `#stay-fee-settings` panel) and PLAN_GUEST_INVOICE §3.5 (invoice toggle "after `stay_fee_cash` in `#communication`") disagree on where the invoice toggle lives. **Recommendation:** use one "Payments / Platby" panel holding both.
9. **`color-scheme` meta in mail (E-23 [UX-139]).** DESIGN.md asks for `color-scheme: light` on documents, but two mail tests currently pin *no* color-scheme. Adding `<meta name="color-scheme" content="light only">` stops mail clients auto-inverting. It doesn't add a theme, but it needs your OK because it changes pinned tests.

## Where the repo doesn't match the brief (§0 rule 10)

None of these blocks the audit. Each is either absorbed into a backlog item or noted for you.

- **`initDocType()` and a document-type select don't exist.** They are only specified in PLAN_POPLATEK §9.1. The nationality select has no default (`form.html:109`, first option "—").
- **`:focus-visible` is not in `tokens.css`.** The guest ring is in `guest.css:47–51` and the host/auth ring in `app.css:26`. The public site has no global rule: `landing.css:1039` covers only `.reel-toggle`, so every other public link falls back to the browser default ring (D findings).
- **Guest validation messages are not in `i18n.py`.** EN lives in `validation.py`, CS in a hand-kept map in `routes/guest.py:48–131`, so the parity tests can't see them (A-19 [UX-55], C-7 [UX-35]).
- **There is no password-reset flow at all,** and `user_account` has no e-mail column (`db.py:24–38`). Brief §6.B assumes one. B-6 [UX-23] covers the gap with honest copy, and self-serve reset is recorded as a future feature.
- **2FA is mandatory only when `DEPLOYMENT == "production"`** (`auth.py:287`).
- **`dates_changed` is listed in `mail.KINDS`** (`mail.py:27–35`) and described in `docs/SES.md:19`, but it has no builder, no sender and no copy (E-16 [UX-134]).
- **LOGO.md sizes and selectors drift from the CSS** (see decision 6). DESIGN.md's stack list also omits `landing.css` / `landing.js`.
- **Both feature plans' route stubs use English-only flashes** (`msg="Saved."`, `err="No such guest."`). C-6 [UX-34] and C-23 [UX-88] fix the pattern, and the plans should be updated to use `_flash` keys.
- **Both plan insertion points on the stay page exist exactly as described** (`reservation_detail.html:274–275`): #stay-fee before `{% if submissions %}`, #invoice after it. No mismatch there.

## Making room for the stay fee and guest invoices

The brief (§0 rule 8, §7) requires that the post-fix layouts have a home for both features. These backlog items are the ones that matter, and each is flagged in the backlog's "plan impact" column:

| Where | Item(s) | What it secures |
|---|---|---|
| Guest stay hub (`stay.html`) | A-2 [UX-2], A-16 [UX-52] | One coral button per state. A fixed vertical order: ① status/progress → ② primary action (*Add person* while people are missing) → ③ **money** (stay-fee card, PLAN_POPLATEK G4–G7) → ④ your people → ⑤ quiet secondary links (invoice "Need an invoice?", PLAN_GUEST_INVOICE G1). A-16 [UX-52] moves the plan's §10.2 anchor, so update the plan text in that commit. |
| Guest form (`form.html`) | A-26 [UX-113], A-7 [UX-14], A-11b [UX-19] | Hiding the visa field for CZ/EU guests frees room for the doc-type select (§9.1). The review list should include doc type once it exists. The plain-language legal notice ships before the plan's `legal_notice_stay_fee_*` paragraph. |
| Host stay page (`reservation_detail.html`) | C-16 [UX-81] | Page grammar: **Now** (next step) → **Guests** → **Payments `#money`** (stay-fee panel, then invoice panel) → **Police reporting** → **Stay settings**. Both plans' panels land inside `#money` at the anchor they already name. |
| Host property form (`apartment_form.html`) | C-2 [UX-30], C-15 [UX-43], C-29 [UX-94], C-30 [UX-95] | Enter can no longer trigger "Test connection" and drop edits. The readiness checklist must not count fee/invoice fields as required. One Payments panel for both toggles. |
| Host guest form | C-1 [UX-8] | Fixes the nested-form bug before the stay fee adds a field to that form. |
| Operators (`entities.html`) | C-27 [UX-92] | The "Operator / Provozovatel" rename goes first, so the bank and invoice fieldsets use the new noun. |
| Completion e-mail | E-7 [UX-29], E-22 [UX-73], E-8 [UX-74] | Closure copy defines the no-fee baseline. The builder gets ordered slots (status → money panel → secondary links → closing note → footer, max one coral button), and both plans' mail blocks slot in via `_block_panel`. Reply-To is centralized, so new guest kinds (invoice) can't forget it. |
| Plurals, dates, flashes | A-13 [UX-50], C-19 [UX-84], C-20 [UX-85], C-23 [UX-88] | The shared plural helper (reuse `alerts._plural_key`), Prague-local timestamps and "what + next" flash keys are ready for `stay.fee.*` and invoice strings. |

**If stay-fee or invoice work starts before Phase 2 reaches these items, pull them forward first:** A-2 [UX-2], A-16 [UX-52], A-11b [UX-19], C-1 [UX-8], C-2 [UX-30], C-16 [UX-81], C-21 [UX-86], C-27 [UX-92], E-7 [UX-29], E-8 [UX-74], E-22 [UX-73]. Their `[UX-N]` numbers are in the backlog.

---

# Per-screen audit

The temporary audit ids (`A-3`, `C-16`…) are the auditor's working numbers. The bracketed `[UX-N]` next to each one is its place in the final backlog.

## Surface A — Guest registration form

Evidence base: every template, `guest.css`, `signature.js`, `claim.js`, guest keys in `i18n.py`, and the guest routes in `routes/guest.py`. `validation.py`, `codelists.py` and `claim.py` were traced where they decide what the guest sees. The key screens were **rendered for real** in EN and CS with a TestClient script (`/tmp/uby-2-audit/scratch_A/render.py`, output in `scratch_A/out/` and `scratch_A/outpp/` for the passport-required variant): picker, claim, claim-sent, claim-error, confirm, form (new, 422 error, person 2), stay hub (1 of 2 saved, all done), assigned, privacy, bad link, stay gone. Guest JS (`signature.js`) was traced by hand because there is no browser in the sandbox. Every JS finding below cites the exact lines.

**Where the repo differs from the brief (§0 rule 10):**
1. `initDocType()` and a document-type select **do not exist** in `signature.js` or `form.html`. They are only specified in `PLAN_POPLATEK_Z_POBYTU.md` §9.1. The nationality select has no default (first option is "—", `form.html:109`).
2. `:focus-visible` is **not** in `tokens.css`. The guest focus ring lives in `guest.css:47–51`. `tokens.css` only zeroes the motion variables under reduced motion. `guest.css:886–888` has its own global reduced-motion block.
3. The `i18n.py` docstring (lines 3–5) says English is "the language the form speaks until the guest chooses". The routes default to **Czech** (`routes/guest.py:153–163`, `host_i18n.PUBLIC_DEFAULT_LANGUAGE = "cs"`), and `tests/test_guest_language.py:78` asserts Czech.
4. Guest validation messages are **not in `i18n.py`**. English lives in `validation.py` and Czech in a hand-kept map in `routes/guest.py:48–131`. The i18n parity tests cannot see them.
5. `stay.html` has no stay-fee states yet (complete-unpaid / paid). That is expected: they arrive with PLAN_POPLATEK §10.2.

---

### A → Shared guest chrome (`guest/base.html`, `guest/_host.html`, `guest/_why.html`, `static/guest.css`)

**Job of this screen:** frame every guest page. The guest should know where they are and in which language, and help should always be one scroll away.

**Current flow:** skip link → header (`h1` "Guest registration" plus facility "Old Town Loft, Prague" and a tone mark; `base.html:19–26`) → EN/CS pill (`base.html:27–32`) → page content → `_host.html` "Your host" card with entity name, `tel:` and `mailto:` (`base.html:40`) → privacy footer line + link. `_why.html` is a closed `<details>` that the page templates include.

**Friction found:**
- [high] **A foreign guest lands in Czech.** `_language()` (`routes/guest.py:153–163`) falls back to `PUBLIC_DEFAULT_LANGUAGE = "cs"` and ignores `Accept-Language`. The host shares `/l/{token}` without `?lang` (`routes/admin.py:201, 503`). So a German guest's very first screen is "Zadejte přístupový PIN". The escape hatch is a pill labelled with the ISO codes "EN / CS". Many foreigners know Czech as "CZ", not "CS". The pill is also ~23 px tall (`guest.css:98–106`: 12.5 px font, `line-height:1`, 5 px padding), below the 44 px bar. This fails lens 2 on the first screen, for exactly the users the police report exists for. (`i18n.py` itself says "Guests are by definition foreigners".)
- [medium] Tap targets under 44 px: `.g-back` (`guest.css:798–807`, ~22 px), the signature "Clear" (`guest.css:671–679`, ~28 px), the host `tel:`/`mailto:` links as bare `<p><a>` (`_host.html:6–7`), and the `.g-arrival-message` summary (`guest.css:207`).
- [low] `tel:` href keeps spaces (`_host.html:6` → `tel:+420 777 123 456`). Most dialers cope, but strip them.
- [low] ALL-CAPS kickers (`.g-question-kicker`, `guest.css:134–141`; `.g-details h3`, `guest.css:713–720`) read like form-section labels (brief §4).
- [low] Dead or broken CSS: `.g-legal-notice h3 { color: var(--g-text) }` and `border-top: … var(--g-border)` use undefined variables (`guest.css:781, 789`), so the legal-ack separator never renders. `.g-fold`, `.g-host-info`, `.g-badge`, `.g-stay .arrow` are unused by any guest template.

**Dumbproof score (1–5):** 3. The calm, consistent footer and chrome are good, but the default language and the language control fail foreign guests on screen one.

**Fix recommendation:**
- Language. When there is no `?lang` and no cookie, use `Accept-Language`: primary tag `cs` or `sk` → `cs`, anything else → `en`. **This is a product-owner decision.** The Czech default is deliberate (route docstring), and `test_guest_language.py:78` must be updated intentionally, never weakened. Relabel the pill with endonyms "English" / "Čeština" (language names are not translated) and set a `lang` attribute on each link. `.g-lang a { min-height:44px; padding:12px 14px; display:inline-flex; align-items:center; }`.
- Tap targets: `.g-back`, `.g-sign .bar button` and `.g-arrival-message summary` get `min-height:44px; display:inline-flex; align-items:center`. In `_host.html`, render phone and e-mail as block links with `min-height:44px`, and use `tel:{{ host.phone|replace(' ','') }}`.
- `text-transform:none` on the kickers (keep weight and colour). Replace `--g-text` → `--g-ink` and `--g-border` → `--g-line`. Delete the unused selectors.

---

### A → PIN (`guest/pin.html`)

**Job of this screen:** prove the guest got the host's message, with one 6-digit code.

**Current flow:** the card "Enter the access PIN" plus help → one input (`inputmode="numeric"`, `pattern="[0-9]{6}"`, `autocomplete="one-time-code"`, `autofocus`, 30 px monospace; `pin.html:12–13`) → Continue → recovery line "Can't find the PIN? Ask your host…" → host footer. Errors show in a `g-err` above the input (`pin.html:6`). Turnstile appears after 3 failures.

**Friction found:**
- [low] The error isn't tied to the input: there is no `aria-invalid`/`aria-describedby` on `#pin` when `error` is set, unlike the form's `invalid()` pattern.
- (The language problem above hits hardest here, because this is screen one.)

**Dumbproof score (1–5):** 4. One field, the right keypad, recovery copy, host contact on screen.

**Fix recommendation:** when `error` is set, give the error div `id="pin-error"` and the input `aria-invalid="true" aria-describedby="pin-error"`. No copy change.

---

### A → Find your stay / arrival lane (`guest/pick.html`)

**Job of this screen:** confirm "you're at the right place" and let the guest tap their dates.

**Current flow:** hero band. Kicker "GUEST REGISTRATION" → property name at 29–42 px → "Welcome — guest registration for Old Town Loft." → city → a collapsed "A message from your host" (`pick.html:4–15`) → collapsed `_why` → "Which stay is yours?" plus help → lanes. Each lane is one `<a>` holding a range cue, "24.09.2026 → 27.09.2026", "3 nights", a status and "That's my stay →" (`pick.html:23–43`) → host footer. `pick_stay` never auto-skips (`routes/guest.py:805–847`).

**DESIGN.md arrival-lane spec check: PASS.** The IA order, the always-render single-stay case, rows as the whole hit target, the range cue, a hairline-separated shared surface with no shadows, the 220 ms staggered entrance, the coral range accent on hover/focus, the 1 px press settle, reduced motion (global override `guest.css:886`), the host message collapsed, and why as secondary are all implemented as documented.

**Friction found:**
- [medium] **"1 nights" / "1 nocí" / "3 nocí".** `nights()` returns an int and the label is one fixed key (`i18n.py:190` "nights", `:709` "nocí"). Rendered output: `1 nights`, `3 nocí`, which should be "1 noc", "3 noci". The same bug appears on claim, assigned, form and stay.
- [low] The quiet status reads as a second CTA: `stay_not_started` = "Select these dates" / "Vybrat tento termín" (`i18n.py:131/652`) sits next to "That's my stay →". DESIGN.md specifies "Not started yet" / "Zatím nezačato".
- [low] A stay arriving *today* shows "Ongoing" / "Právě probíhá" in coral (`routes/guest.py:842`, `start <= today < end`). To a guest standing at the door this reads as "someone is already in".
- [low] Repetition in the first viewport: "Guest registration" three times (h1, kicker, welcome sentence), the property name twice and the city twice (header `facility` plus hero). On CS pages the city is `city_en` ("Prague").

**Dumbproof score (1–5):** 4. The primary action is unmistakable and the spec is implemented. The copy needs polish.

**Fix recommendation:**
- Nights plural helper (see backlog A-13 [UX-50]): new keys `night_one` EN "%(n)s night" / CS "%(n)s noc"; `nights_few` EN "%(n)s nights" / CS "%(n)s noci" (2–4); `nights_many` EN "%(n)s nights" / CS "%(n)s nocí". Add a Jinja global `nights_label(from, to)` in `templating.py`. Replace every `{{ nights(...) }} {{ t('nights') }}`.
- `stay_not_started` → EN "Not started yet" / CS "Zatím nezačato".
- New key `stay_arriving_today` EN "Arriving today" / CS "Příjezd dnes", used when `start == today`. Keep "Ongoing" for later days, and render both in the muted status colour, not the accent.
- Drop the hero kicker (`pick.html:5`). The h1 already says it.

---

### A → Claim: party size + e-mail (`guest/claim.html`)

**Job of this screen:** say how many people are staying and where to send the private link.

**Current flow:** `_why` (before the back link, unlike every other page) → "← Choose different dates" → dates card → "Confirm the number of guests and your e-mail" plus help → "How many people are staying?" (`type=number`, `inputmode=numeric`) → "What is your e-mail address?" (`type=email`, `autocomplete=email`) → **two hint paragraphs of ~100 words** (`i18n.py:86–96`) → "Send me the form link". After submitting: the same URL with `claim_sent=1`.

**Friction found:**
- [high] **Staging text leaks to production guests.** `claim_sent_body` (`i18n.py:99–102`, CS `:620–623`) ends with "On staging, the host can also copy the link from Settings → Guest e-mails." / "Na stagingu může hostitel odkaz zkopírovat v Nastavení → E-maily hostům." (rendered in `en_claim_sent.html`).
- [high] **After sending, the whole form renders again** under the green "Check your e-mail" card (`claim.html:14–19` and then `:24–50` unconditionally). The guest can't tell whether they are done or must submit again, and resubmitting trips `claim_error_cooldown`. The card also doesn't say which address was used, or what to do if nothing arrives.
- [medium] The e-mail link often opens in a different browser (the mail app's webview), which asks for the **PIN again** (`claim_landing` → `_require_pin`). Nothing warns the guest.
- [medium] A wall of legal-style text sits at the moment of commitment. `claim_email_help` mentions "property manager", "authorised host users" and "public guest screens show only a masked version". `claim_cookie_help` lists cookie lifetimes. `claim_help` adds the jargon line "The public link then shows that the stay is assigned to your masked e-mail." DESIGN.md requires these points at collection, but not in this length or register.
- [low] The page title is two instructions joined together ("Confirm the number of guests and your e-mail").

**Dumbproof score (1–5):** 2. Confirmation is ambiguous (lens 6) and internal jargon leaks (lens 2).

**Fix recommendation:**
- `claim.html`: when `claim_sent`, **replace** the form with the sent card and wrap the form in a closed `<details>` whose summary is the new key `claim_sent_retry`.
  - `claim_sent_body` EN "We sent a link to %(email)s. Open it on this phone to continue — it works for 30 minutes. If it asks for the PIN again, enter the same PIN." / CS "Poslali jsme odkaz na %(email)s. Otevřete ho v tomto telefonu a pokračujte — platí 30 minut. Pokud se znovu zeptá na PIN, zadejte stejný." (`email` = `claim.email_masked`.)
  - `claim_sent_retry` EN "No e-mail after a few minutes? Check spam, or send it again" / CS "E-mail ani po pár minutách nepřišel? Zkontrolujte spam, nebo ho pošlete znovu".
- Condensed copy that keeps every DESIGN.md collection point (private link, one reminder, receipt plus host copy, masking, no marketing, necessary cookies):
  - `claim_title` EN "How many people, and your e-mail" / CS "Počet osob a váš e-mail".
  - `claim_help` EN "We'll e-mail you a private link so only your group can open the forms." / CS "Pošleme vám soukromý odkaz, aby formuláře otevřela jen vaše skupina."
  - `claim_email_help` EN "We send the link here, one reminder the day before arrival if forms are missing, and a receipt (your host gets a copy). Elsewhere it is shown masked. No marketing." / CS "Pošleme sem odkaz, jedno připomenutí den před příjezdem, pokud formuláře chybí, a potvrzení (kopii dostane i ubytovatel). Jinde se adresa zobrazuje zakrytě. Žádný marketing."
  - `claim_cookie_help` EN "Only necessary cookies: PIN access (7 days), your language and this stay (60 days)." / CS "Jen nezbytné cookies: přístup přes PIN (7 dní), jazyk a tento pobyt (60 dní)."
- Move `{% include "guest/_why.html" %}` below the back link, to match the other pages.

---

### A → Confirm from e-mail (`guest/confirm.html`)

**Job of this screen:** one tap proving a human opened the e-mail link, so a mail scanner can't claim the stay.

**Current flow:** dates → "Is this your reservation?" → help "E-mail scanners open links automatically. Click the button to prove this is you." → "Yes, this is my stay" (`confirm.html:9–17`). `claim.js` reads the secret from the URL fragment and scrubs it.

**Friction found:**
- [low] The help explains the mechanism rather than the action, and says "Click" on a phone (`i18n.py:123`). The CS version is fine but also technical.

**Dumbproof score (1–5):** 4. One action and a clear button.

**Fix recommendation:** `claim_confirm_help` EN "One tap to confirm it's really you." / CS "Jedním klepnutím potvrďte, že jste to opravdu vy." Add nights to the dates card for parity with the other summaries (via `nights_label`).

---

### A → Stay already assigned (`guest/assigned.html`)

**Job of this screen:** tell someone on a device without the claim cookie that the stay belongs to an e-mail, and let the owner resend the link.

**Current flow:** "← Choose different dates" → stay card (kicker "YOUR SELECTED STAY", property, city, dates, nights) → "This reservation is already assigned". The body repeats the masked e-mail, then the `g-private-link-note` repeats it again with "Private link last sent 2026-09-24" → "Enter the same e-mail…" field plus the same ~100 words of claim hints → "Send me the link again" → full-width ghost "This is not my reservation" → host footer.

**DESIGN.md assigned-screen spec check: PASS with two deviations.** Stay summary ✓, masked-only e-mail ✓, private-link guidance ✓, last-sent date ✓, primary resend ✓, host footer ✓.

**Friction found:**
- [low] **Doc deviation:** DESIGN.md says the secondary back / not-mine action should appear "when other stays are available". The template renders both the top back link (`:3`) and the bottom ghost button (`:48`) unconditionally, although the route passes `can_pick_other`. With no other stays, "This is not my reservation" leads to the "no stays" page.
- [low] The last-sent date is raw ISO (`claim_last_sent_at[:10]`, `:26`), while every other date is `date_cz`.
- [low] The masked e-mail is printed twice, and the wording is stiff: "has already been assigned the e-mail".

**Dumbproof score (1–5):** 4. The primary action is clear. Tidy-up only.

**Fix recommendation:**
- Wrap `:3` and `:48` in `{% if can_pick_other %}`.
- Format the date with `| date_cz`.
- `assigned_body` EN "This stay is already linked to the e-mail below. If that's you, we can send the private link again." / CS "Tento pobyt je už propojený s e-mailem níže. Pokud jste to vy, pošleme vám soukromý odkaz znovu." (drop `%(email)s`; the note box shows it).
- Reuse the condensed claim hints from the claim screen.

---

### A → Form wizard, step 1 "Your details" (`guest/form.html:63–163`)

**Job of this screen:** enter the identity fields exactly as printed in the travel document.

**Current flow:** above every step: back link, `_why` card, host-message card (coral-tinted, expanded, `:33–38`), dates card, "Person 1 of 2" (`:56–58`), and the sticky "Step 1 of 4" bar (`:59–61`, unhidden by `signature.js:207`). Then the step itself: given name (`autocomplete=given-name`), surname, date of birth (`type=text inputmode=numeric`, auto-slash), nationality select, document number (`autocapitalize=characters`), the checkline "child on a parent's passport" (which reveals the parent doc field), visa (optional), purpose select (preset from the property default) → "Continue".

**Hypothesis checks:**
- `g-wizard-progress hidden` → **PASS.** `show()` sets `progress.hidden = false` (`signature.js:207`) and writes "Step N of M" / "Krok N z M" into visible text. It is sticky, with `aria-live="polite"`. It is legible but small and muted (13 px `--ink-muted`), and it has no step name.
- Doc-type / nationality defaults → **the doc-type select doesn't exist yet** (see note 1). Nationality has **no default**. The one smart default that exists is good: home country copies nationality when empty (`signature.js:165–172`).

**Friction found:**
- [high] **Czech country names sort by code point.** `codelists.py:94, 95–101` uses a plain `sorted(key=label)`. In the rendered CS select, **"Česko" is option 246 of 254**, after "Zimbabwe" and "Západní Sahara". Čad, Černá Hora, Čína, Řecko, Španělsko, Švédsko and Švýcarsko are also at the bottom. On an iOS wheel a Czech guest must scroll past ~245 entries, and a guest looking under "C" won't find it. No common countries are pinned.
- [high] **Birth date invites errors.** The hint says "Type the 8 digits from your passport" (`i18n.py:235`), but passports print the month as letters ("04 JUL 1990"), so there are not 8 digits to copy. DD/MM vs MM/DD (US guests) is undetectable for days ≤ 12. Because the form **locks the moment it is saved** (see stay hub), a swapped date can only be fixed by the host. A pasted or autofilled ISO date ("1990-07-04") becomes "19/90/0704" (`signature.js:135–146`).
- [medium] Chrome repeated above every step: why card, full host-message card, dates card, person line and step bar. That is ~350–420 px on a 375×667 phone before the first field, once the host message is set. `guest.css:726–750` already contains a compact `.g-fold` "folded away on the form so the first question is on screen", but no template uses it. The host message was already shown (collapsed) on the picker.
- [medium] Two progress systems ("Person 1 of 2" and "Step 1 of 4") are stacked and styled differently. The step bar gives no hint of what's left.
- [medium] Purpose shows police codes, and ALL-CAPS in Czech: "10 - Tourism", "10 - TURISTIKA", "93 - TZV. ADS vízum udělované občanu Číny" (`codelists.py:104–121`, `validation.py:61–77`).
- [medium] Child on a parent's passport. The parent document field is never `required` (`signature.js:150–163`), so the omission is only caught on the server. The server error says "…the **note** must contain the parent's document number" (`validation.py:456–460`), but the guest never sees a "note". It is keyed `note`, so the parent input gets no `bad` class and no `aria-invalid` (`form.html:138–143`).
- [low] The visa field is shown to Czech and EU guests, who can never have a Schengen visa. That is one needless decision for the majority.
- [low] `doc_number` lacks `spellcheck="false" autocorrect="off"`.

**Dumbproof score (1–5):** 3. The fields are good, but prevention is weak exactly where the data is legally binding and unfixable after save.

**Fix recommendation:**
- Countries (`codelists.py`): sort with an accent-folded key, `unicodedata.normalize("NFD", label)` with combining marks stripped, then the label. Prepend an `<optgroup>` new key `countries_common` EN "Most common" / CS "Nejčastější" with CZE, SVK, DEU, POL, AUT, GBR, USA, UKR, then `countries_all` EN "All countries" / CS "Všechny státy". Use it for both nationality and home country. No preselection: locale ≠ nationality (see Rejected).
- Birth date:
  - `birth_date_help` EN "Day, month, year — e.g. 04/07/1990 for 4 July 1990. Slashes are added for you." / CS "Den, měsíc, rok — např. 04/07/1990 pro 4. července 1990. Lomítka se doplní sama."
  - Add a live read-back under the field, `aria-live="polite"`: new key `birth_date_readback` EN "That is %(date)s." / CS "Tedy %(date)s.", with the date from `Intl.DateTimeFormat(lang, {day:'numeric', month:'long', year:'numeric'})`, so "4 July 1990" / "4. července 1990". Zero extra typing, and it catches swaps.
  - In `apply()`, detect `^\d{4}-\d{2}-\d{2}$` and reorder.
- Compact chrome: one line "24.09.–27.09. · Person 1 of 2" above the sticky bar. The bar label gets step titles from `data-step-title`, e.g. "Step 2 of 4 · Home address" / "Krok 2 z 4 · Trvalé bydliště", in 14 px, weight 600, `--ink`. Render `_why` on the form with the existing `.g-fold` one-line style. Show the host message on the form only as a closed `.g-fold` "A message from your host".
- Purpose: display labels without the "NN - " prefix. Use sentence-case CS from the bundled list, overriding the police `text_cs` for display only (the stored code is unchanged): "Zdravotní, Obchodní, Kulturní, Návštěva rodiny nebo přátel, Pozvání, Oficiální (politický), Podnikání (OSVČ), Sportovní, Turistika, Studium (školení, stáž), Tranzit (průjezd), Letištní tranzit, Zaměstnání, Vízum ADS (občané Číny), Ostatní".
- Child: in `initChildToggle`, set `parent_doc_number.required = toggle.checked`. The guest route maps the `note` issue onto the `parent_doc_number` field for `bad`/`invalid()`. Guest-side EN message "Enter the parent's passport or ID number." / CS "Zadejte číslo pasu nebo průkazu rodiče." Use a guest-route override map, not `validation.py`, so the host form is unaffected.
- Visa: hide `#visa_number`'s field in JS when nationality is CZE or an EU/EEA/CH code, and clear it. This frees room for the plan's doc-type select, so step 1 has no net growth.

---

### A → Form wizard, step 2 "Permanent home address" (`form.html:165–193`)

**Job of this screen:** enter the home address the police record needs.

**Current flow:** help "Your permanent home address abroad, as shown in your passport. Required for the police report." → street (`autocomplete=street-address`), city (`address-level2`), country select (pre-copied from nationality) → Back / Continue.

**Friction found:**
- [medium] **Person 2+ on the same device retypes the family address.** The server already knows the owned guests' residence (the `ubyhost_owned` cookie), but `/new` starts empty.
- [low] The help says "abroad" and "as shown in your passport". That is wrong for Czech guests (a Czech ID card carries the address).
- [low] `street-address` on a single-line input (should be `address-line1`). The country select has no `autocomplete="country"`.

**Dumbproof score (1–5):** 4. A short step with a smart country default.

**Fix recommendation:**
- In `_form_context` for `/new`, when the device owns a completed guest on this stay, prefill `res_*` from the most recent one. Show the new key `residence_copied` EN "Copied from %(name)s — change it if this person lives elsewhere." / CS "Převzato od: %(name)s. Pokud tato osoba bydlí jinde, adresu změňte."
- `residence_help` EN "Your permanent home address, as in your passport or ID card. Required by law." / CS "Adresa trvalého bydliště podle pasu nebo občanského průkazu. Vyžaduje ji zákon."
- Fix the autocomplete tokens.

---

### A → Form wizard, passport/ID step (`form.html:195–219`, when `passport_photo_policy == 'required_foreign'`)

**Job of this screen:** a foreign guest photographs or uploads the ID page.

**Current flow:** "Passport or ID document" plus a 4-sentence help → "Take photo" / "Choose file" (both secondary) → hidden `<input type=file>` (`:213`) whose `required` flag JS sets when nationality ≠ CZE (`:348`) → file-name line → format hint.

**Friction found:**
- [high] **"Continue" silently does nothing without a file.** `stepIsValid` calls `checkValidity()`/`reportValidity()` on each field (`signature.js:192–201`). The required file input has the `hidden` attribute, and browsers cannot show a validation bubble on, or focus, a hidden control. No message appears and nothing moves.
- [high] Jargon in `passport_photo_help` (`i18n.py:261–266`): "Access in the app is restricted to authorised host users", "a scheduled stale-file sweep is the backstop", "a registration form with up to 11 guests". CS: "pojistkou je plánované mazání starých souborů".
- [medium] **Czech guests get an empty step.** For CZE the step still counts ("Step 3 of 5") and only says "Czech citizens do not upload a passport photo in this form."
- [low] "Choose your nationality above" (`passport_photo_pending_nat`) points "above", but nationality is on a hidden earlier step. The CS says "státní příslušnost" while the field label is "Státní občanství".
- [low] After a 422 re-render the chosen file is gone (browsers can't restore file inputs). The error "Please upload a photo…" is clear enough.

**Dumbproof score (1–5):** 2. The primary task can stall silently, and the copy is internal.

**Fix recommendation:**
- In `stepIsValid`, when the invalid field is `input[type=file][hidden]`, write `passport_photo_missing` into `#passport-file-err` (already `role="alert"`), focus `#passport-take-btn` and return false.
- Mark the card `data-guest-step-skip-when="CZE"`. `initGuestWizard` recomputes the active steps list when nationality changes, so Czech guests see "Step N of 4".
- `passport_photo_help` EN "Your host must check your details against your document. Take a photo of the page with your photo, or upload a PDF. Only your host can see it, and it is deleted after they check it." / CS "Ubytovatel musí vaše údaje porovnat s dokladem. Vyfoťte stránku s fotografií, nebo nahrajte PDF. Uvidí ji jen ubytovatel a po kontrole se smaže."
- `passport_photo_hint` EN "A JPEG, PNG or WebP photo up to 5 MB, or a PDF up to 15 MB." / CS "Fotka JPEG, PNG nebo WebP do 5 MB, nebo PDF do 15 MB."
- `passport_photo_pending_nat` EN "Choose your nationality in step 1 first." / CS "Nejdřív v kroku 1 vyberte státní občanství."

---

### A → Form wizard, signature step (`form.html:222–238`)

**Job of this screen:** sign with a finger.

**Current flow:** "Signature" + "Sign with your finger or mouse. This is required by Czech law." → 175 px canvas → bar with a status span (`class="err" role="alert"`) and "Clear" → Back / Continue.

**Friction found:**
- [blocker] **Skipping the signature causes a silent dead end at Submit.** Nothing in the step is a constraint-validated input (the canvas isn't an input, and `#signature` is `type=hidden`), so "Continue" always advances (`signature.js:192–201, 237–239`). On the last step, "Submit my details" triggers `initSignature`'s submit guard (`signature.js:95–105`). It runs `preventDefault()`, writes "Please sign before submitting." into a span **inside the hidden signature step**, and calls `scrollIntoView()`/`focus()` on a `display:none` canvas. The guest taps Submit and **nothing visible happens**, with no hint that the problem is two steps back.
- [medium] The reassurance "Signature already saved. Sign again only if you need to change it." is written into the same `class="err" role="alert"` span (`signature.js:83`, `form.html:229`). It renders red and bold, and is announced as an alert. It also makes `.err:not(:empty)` true, which skews `active`-step detection and `focusFirstError` (`signature.js:175, 190`).
- [low] CS `signature_kept` is missing a comma: "…znovu jen pokud…" should be "…znovu, jen pokud…".

**Dumbproof score (1–5):** 2. Signing itself is easy, but the missing-signature path is a dead end on the primary task.

**Fix recommendation:**
- `stepIsValid(step)`: if the step contains `#sig-canvas` and `#signature` is empty, set `#sig-status` to `data-missing`, focus the canvas and return false.
- The submit guard: if the wizard is active, first `show(indexOf(signature step))`, then scroll and focus. Expose `show` via a `guest-wizard:show` CustomEvent so `initSignature` doesn't reach into wizard state.
- `signature_missing` EN "Please sign in the box before you continue." / CS "Než budete pokračovat, podepište se prosím do rámečku."
- For the kept state, swap the span to `class="hint"` + `role="status"`. `signature_kept` EN "Your signature is saved. Sign again only if you want to change it." / CS "Podpis máme uložený. Znovu se podepište, jen pokud ho chcete změnit."

---

### A → Form wizard, legal notice + submit (`guest/_legal_notice.html`, `form.html:240–244`)

**Job of this screen:** understand the obligations, tick the box, submit.

**Current flow:** "Legal information" → intro → disclaimer "UbyHost is a software tool and this information does not replace legal advice." → six h3 sections, ~300 words in EN (passport section only for foreign nationality) → law citation → privacy link → ack checkline (~35 words) → "Submit my details" → "Back" button below it.

**Friction found:**
- [high] **Bureaucratic and internal wording at the final, most tired moment.** "automatic reporting can occur without an in-app verification step" (`i18n.py:304–309`). "(UbyPort) … without waiting for in-app identity verification" (`:319–323`). The software disclaimer (`:293`) speaks about UbyHost's liability, not the guest's task. This is the brief §4 "government form" pattern.
- [high] **There is no review before an irreversible save.** A guest-saved form is locked immediately (`reporting.guest_form_locked` = signed and complete), and the next screen says "Please check what you submitted below" — after checking can no longer lead to a fix. A typo spotted on the stay hub means messaging the host.
- [medium] `guest.css:876–884` intends a sticky Submit on phones, but the selector `form > .g-btn[type="submit"]` never matches: the button sits inside `<div data-guest-step>`. The guest scrolls ~300 words to find it.
- [low] The ack label is long and bundles three claims (`i18n.py:337–340`).

**Dumbproof score (1–5):** 2. The one action is clear, but it's buried under jargon, and there's no chance to catch mistakes before they're locked.

**Fix recommendation (copy should get a lawyer's glance; meaning is preserved):**
- **Review block** at the top of this step. New keys `review_title` EN "Check before you send" / CS "Před odesláním zkontrolujte", and `review_help` EN "After you send, these details are locked and only your host can change them." / CS "Po odeslání se údaje uzamknou a změnit je může už jen ubytovatel." JS builds a `<dl>` from the filled labels and values: name, DOB with its read-back, nationality, document, address. Each row has a "Change" button (new key `review_edit` EN "Change" / CS "Změnit") that calls `show(step)`. No new typing, no new step.
- Copy:
  - `legal_notice_intro` EN "Please read this before you send." / CS "Před odesláním si to prosím přečtěte."
  - Remove `legal_notice_disclaimer` from the guest step (keep it on the privacy page).
  - `legal_notice_duty_body` EN "Everyone staying must be registered. Foreign guests are reported to the Foreign Police within three working days; Czech citizens only go into the house book. This is required by law." / CS "Registrovat se musí každý ubytovaný. Cizince ubytovatel do tří pracovních dnů ohlásí cizinecké policii, občany ČR jen zapíše do domovní knihy. Vyžaduje to zákon."
  - `legal_notice_accuracy_body` EN "Enter everything exactly as in your passport or ID card. Your details may be reported automatically, before your host checks them, and false details can mean a fine for your host." / CS "Vše vyplňte přesně podle pasu nebo občanského průkazu. Údaje se mohou ohlásit automaticky ještě předtím, než je ubytovatel zkontroluje, a za nepravdivé údaje hrozí ubytovateli pokuta."
  - `legal_notice_reporting_body` EN "Complete records of foreign guests may be sent to the Czech Police automatically — straight away or after a delay your host chooses. The same details stay in the house book for six years." / CS "Kompletní záznamy cizinců se mohou Policii ČR odeslat automaticky — hned, nebo s odkladem, který nastaví ubytovatel. Stejné údaje zůstávají šest let v domovní knize."
  - `legal_notice_passport_body` EN "Foreign guests upload a photo of their passport or ID page (or a PDF). Only your host sees it, to compare it with what you entered. It is deleted after the check, or automatically after your stay. It is never sent to the police." / CS "Cizinci nahrají fotku stránky pasu nebo průkazu (nebo PDF). Uvidí ji jen ubytovatel, aby ji porovnal s vyplněnými údaji. Po kontrole se smaže, jinak automaticky po skončení pobytu. Policii se nikdy neposílá."
  - `legal_ack_label` EN "My details are correct, and I have read the information above and the privacy notice." / CS "Moje údaje jsou správné a přečetl(a) jsem si informace výše i zásady zpracování údajů."
- Fix the sticky selector to `[data-guest-step] > .g-btn[type="submit"]`.

---

### A → Form validation-error state (HTTP 422 re-render of `form.html`)

**Job of this screen:** show what's wrong and where, then let the guest fix it fast.

**Current flow (rendered `cs_form_422.html`):** "Opravte prosím následující:" summary above the why card (`form.html:22–29`) → the wizard opens the first step containing `.bad`/`.err` (`signature.js:190`) → `focusFirstError()` focuses the first `.bad` field. Per-field messages come from `err_for`, and `invalid()` adds `aria-invalid` + `aria-describedby` (verified on 4 fields). The signature is repainted, and `legal_ack` is kept.

**Friction found:**
- [medium] Summary messages don't match the labels, and some don't say which field. CS says "Země je povinná." but the field is labelled "Stát". "Státní příslušnost je povinná." sits under a field labelled "Státní občanství". "Toto datum neexistuje – zkontrolujte den a měsíc." doesn't name *date of birth*. The summary lists items from later hidden steps with no link to them.
- [low] `form_expired_help` (the CSRF 403 page) says "Reload the page". After a POST, reloading re-posts the stale token and fails again (`i18n.py:148`).

**Dumbproof score (1–5):** 4. A strong a11y pattern. The wording needs alignment.

**Fix recommendation:**
- Add a guest-side EN override map next to `CS_VALIDATION_MESSAGES` (this keeps host copy in `validation.py` untouched), then fix the CS map:
  - "Choose your nationality." / "Vyberte státní občanství."
  - "Choose the country of your home address." / "Vyberte stát trvalého bydliště."
  - "Date of birth: that date does not exist — check the day and month." / "Datum narození: takové datum neexistuje — zkontrolujte den a měsíc."
  - The other birth-date messages get the same "Date of birth: …" / "Datum narození: …" prefix.
- Make each summary `<li>` a link `href="#{{ issue.field }}"`. Clicking calls the wizard's `show()` for the step that owns the field.
- `form_expired_help` EN "Nothing was saved. Start again from the link below." / CS "Nic se neuložilo. Začněte znovu přes odkaz níže."

---

### A → Stay hub: saved / add person / all done (`guest/stay.html`)

**Job of this screen:** say plainly whether the group is done, and if not, what the single next step is.

**Current flow:**
- *After saving person 1 of 2* (`en_stay_saved1.html`): back link → dates → green card **"Details submitted and reported — Your host has already reported this record."** → "1 of 2 people completed" plus bar → "Your submission" card (uppercase name, DOB, nationality, document, purpose "10 - Tourism", residence "…, GBR-United Kingdom", "Saved and locked…") → primary "Add a person" at the very bottom.
- *All done* (`en_stay_done.html`): ✓ "Thank you, everything is complete / … nothing more you need to do." In the same card: "Is someone in your group still not registered?…" plus a ghost "Add another person". Then every summary card. Then **a second, primary coral full-width "Add another person"** (`stay.html:113–117`).

**Hypothesis check (done vs one-more-thing):** **FAILS.**

**Friction found:**
- [blocker] **The all-done state's strongest button is "Add another person"**, and it appears twice (`stay.html:39–45` ghost, `:113–117` primary). It POSTs immediately with no confirmation. `add_another_person` raises `declared_guests` by one (`routes/guest.py:1136–1167`), and the guest has no way to lower it again. One mistaken tap turns a completed stay back into "incomplete": reminders go out and the host gets alerts. That is a likely wrong action with no guest-side recovery. It contradicts the headline right above it.
- [high] **"Details submitted and reported" is shown after every save**, even when nothing has been reported (manual mode, Czech guests who are never reported). `just_reported` is computed from `person.locked` (`routes/guest.py:926–929`). `locked` is true for *any* signed, complete form (`reporting.py:269–279`), so `saved_title`/`saved_body` are effectively dead code. This makes a false legal-status claim, and the guest mail (Surface E) says the opposite: "not proof of police reporting".
- [medium] **The next step is not stated while people are missing.** `still_missing` only renders inside the "other people" card (`:93–107`), which appears only when some saved persons are *not* on this device. The typical one-phone family sees no "1 more to go". The primary "Add a person" sits below all the summary cards, one to three screens down.
- [medium] The all-done card doesn't say that a receipt was e-mailed or that the page can be closed. That is lens 6: "what happens next".
- [medium] The summary shows police-format values: "10 - TURISTIKA", "GBR-Spojené království" (from `compose_residence`, `validation.py:300–312`).
- [low] CS "vyplněno %(done)s z %(total)s osob" is lowercase and breaks for total = 1. "Chybí ještě údaje %(n)s osob(y)." uses a bracket plural.

**Dumbproof score (1–5):** 2. Done isn't unmistakable, and there is a dead-end-risk action in the done state.

**Fix recommendation:**
- Delete `stay.html:113–117` (the bottom primary add-another in the done state). Keep the in-card form, restyled as a quiet text-button (this keeps `test_completed_party_can_add_another_person` green).
  - `all_done_title` EN "Thank you — everyone is registered" / CS "Děkujeme — všichni jsou zaregistrovaní".
  - `all_done_body` EN "There is nothing more you need to do. You can close this page." / CS "Nic dalšího už dělat nemusíte. Stránku můžete zavřít."
  - New key `all_done_receipt` (when mail is enabled) EN "We have sent a confirmation to %(email)s." / CS "Potvrzení jsme poslali na %(email)s."
  - `someone_missing` EN "Forgot someone? Everyone staying must be registered, including children." / CS "Zapomněli jste na někoho? Registrovat se musí každý ubytovaný, včetně dětí."
- `just_reported` = any of the guest's own forms with `submit_state == SENT`. Otherwise use:
  - `saved_title` EN "Saved — thank you" / CS "Uloženo — děkujeme".
  - `saved_body` EN "Your details are saved. Next, add the next person in your group." / CS "Vaše údaje jsou uložené. Teď přidejte další osobu ze skupiny."
  - `form_locked_short` EN "Saved and locked. To change anything, contact your host." / CS "Uloženo a uzamčeno. Pro změnu kontaktujte ubytovatele."
- Move the "Add a person" `g-btn` directly under the progress card. Always show the plural-free `still_missing` EN "Still to register: %(n)s" / CS "Zbývá zaregistrovat: %(n)s". `people_progress` EN "Registered: %(done)s of %(total)s" / CS "Zaregistrováno: %(done)s z %(total)s".
- Collapse each "Your submission" card into `<details>`, with the summary "John Smith · saved ✓" / "John Smith · uloženo ✓". Display the purpose label without its code and the country name without "GBR-".

**Layout principles so stay-fee and invoice land cleanly** (PLAN_POPLATEK §1.1 G4–G7 and §10.2; PLAN_GUEST_INVOICE §0.5 G1, §3.1 C/D):
1. **Fixed vertical order:** ① status (done ✓ / "Still to register: N") → ② the one next action (Add a person, only while people are missing) → ③ **money** (the stay-fee card, then the invoice link) → ④ your records (collapsed) → ⑤ host footer. The plan's insertion point, "after the status chain, before `{% for person in people if person.mine %}`", maps onto ③ and stays valid if ② moves up under ①. Update the plan's anchor sentence when A-16 [UX-52] ships.
2. **One coral button per state.** Incomplete: Add a person. Complete and unpaid: the fee card's "Pay online" (plan §10.2 uses `g-btn`). Add-another must never be primary, which the blocker fix above guarantees. Otherwise G5 would ship two coral buttons.
3. `fee_so_far` (G4) is a one-line muted `<p>` under ① and never a card. The paid state (G7) is a one-line card.
4. The invoice link is a quiet text link in ③ after the fee card, shown only after checkout. **Don't add "Need an invoice?" to `_host.html` globally** (invoice plan §3.1 D). Gate it with a context flag (`show_invoice_link`), set on the stay hub and the unavailable page only, so it never competes on PIN, claim or form screens.
5. Plan copy to revisit before it ships: `fee_line` "%(nights)s night(s)" / "noc(í)" should use `nights_label`. "Variable symbol" and the "QR Platba" figcaption are jargon for non-Czech guests (the brief flags VS). For non-`czech_first` viewers, suggest EN `fee_vs` "Payment ID (variable symbol)", with CS unchanged "Variabilní symbol".

---

### A → Form screen: room for the stay-fee additions (`form.html`, PLAN_POPLATEK §9, G2–G3)

**Job of this screen:** (forward-looking) absorb a document-type select, an optional "Anything your host should know?" row and one legal paragraph, without a new step.

**Current flow:** n/a (not built). The plan puts `doc_type` inside `#doc-wrap` (hidden with the child toggle ✓), `.g-more` `<details>` as the last child of step 1, and `legal_notice_stay_fee_*` in the legal notice.

**Friction found:**
- [medium] Step 1 is already the densest step (8 controls). The plan adds two more.
- [medium] The legal step is already ~300 words, and G3 adds a paragraph.
- [low] The plan's default "Passport unless CZE" will be wrong for many EU guests who travel on a national ID card.

**Dumbproof score (1–5):** n/a.

**Fix recommendation:**
- Ship A-26 [UX-113] (hide visa for CZE/EU) and A-11b [UX-19] (shorter legal copy) **before** PLAN_POPLATEK §9, so its additions land with no net growth.
- Keep the plan's rules as they are: no new `data-guest-step`, the optional row closed, the doc type following nationality until touched. Those match the brief's "smart default that's easy to override". Ask the plan owner whether EU/EEA nationalities should default to `op` ("National ID card").
- `.g-more summary` at 44 px min-height (the plan's CSS already does this).

---

### A → Unavailable / locked / expired (`guest/unavailable.html`)

**Job of this screen:** say which of the dead-end cases happened and who to contact.

**Current flow:** "?" mark → title/body from `_unavailable()` (`routes/guest.py:468–515`: no_stays, bad_link, stay_gone, form_expired, rate_limited, not_yours, already_filed, form_locked) → "Start again" ghost (when a token exists) → `_why` → host footer (or "Use the phone or e-mail in the message that contained this link." when there is no entity contact). Never UbyHost support ✓.

**Friction found:**
- [high] **Early openers see an apparent error.** The apartment link lists only stays within `permalink_window_days` (default 2). A guest who opens the Airbnb message the day they book sees "There are no upcoming stays to fill in right now", then "The apartment link only lists stays that start in the next few days… open the stay-specific link…" (`i18n.py:134–139`). "Apartment link" and "stay-specific link" are internal terms, and the likely reason ("too early") is never stated clearly.
- [low] `_why` on error pages (`unavailable.html:14`) is noise, and "Start again" on `form_locked`/`already_filed` loops back to a stay that can't be changed.

**Dumbproof score (1–5):** 3. Never a true dead end, thanks to the host footer, but the most common case reads like a fault.

**Fix recommendation:**
- `no_stays` EN "There's nothing to register yet" / CS "Zatím tu není co vyplnit".
- `no_stays_help` EN "Registration opens a few days before arrival. Come back to this same link then. Already arrived? Message your host — they can send you a direct link to your stay." / CS "Registrace se otevírá pár dní před příjezdem. Pak se vraťte na tento odkaz. Už jste na místě? Napište ubytovateli, pošle vám přímý odkaz na váš pobyt."
- Drop `_why` here, and hide "Start again" for `form_locked`/`already_filed`/`not_yours`.

---

### A → Privacy notice (`guest/privacy.html`)

**Job of this screen:** the legally required notice, reachable from every page and returning to where the guest was.

**Current flow:** Back → title/intro → one long `g-legal` card with 13 sections → Back (ghost). `return_to` brings the guest back to the form step URL ✓.

**Friction found:**
- [low] **Contact split:** the processor paragraph prints "Software support is support@ubyhost.com" (`privacy_processor_body`, `i18n.py:445–451`; rendered). It does route stay questions to the host, but DESIGN.md says guest pages show the PM contact, not `support@ubyhost.com`. GDPR Art. 13 needs the controller's contact, which is already shown, not the processor's.
- [low] Operator jargon: "staging console copies" (`privacy_retention_body`), "Production pages may also be challenged by Cloudflare Bot Fight Mode" (`privacy_bot_protection_body`).

**Dumbproof score (1–5):** 3. It's a legal document and fine in structure, but it carries internal terms and a support address.

**Fix recommendation:** remove "Software support is %(email)s;" from `privacy_processor_body`. EN "…to run the registration form, transactional messages, and stored records. Questions about your stay go to your host; personal-data requests go to the controller named above." / CS "…kvůli chodu registračního formuláře, transakčním zprávám a uložení záznamů. Dotazy k pobytu směřujte na ubytovatele, žádosti k osobním údajům na správce uvedeného výše." Remove "and staging console copies" / "a konzolové kopie ve stagingu". Replace "Production pages may also be challenged by Cloudflare Bot Fight Mode" with EN "Cloudflare may also check suspicious traffic." / CS "Cloudflare může také prověřit podezřelý provoz." (Lawyer glance.)

---

### A → Cross-cutting copy consistency (all guest templates, `i18n.py`)

**Job of this screen:** the same concept gets the same word everywhere (lens 7).

**Current flow:** n/a.

**Friction found:**
- [medium] CS uses **"hostitel" (12×) and "ubytovatel" (37×)** for the same person. The footer is "Váš hostitel", the host message is "Zpráva od vašeho ubytovatele", and the passport copy says "Hostitel musí…". EN mixes "your host", "property manager" (`claim_email_help`) and "accommodation provider".
- [medium] **EN/CS say different things:** `why_point_passport` EN "If your host asks for it, you upload…" vs CS "Pokud nejste občanem ČR, musíte nahrát…" (`i18n.py:44/567`).
- [low] The date separator differs: stays render "24.09.2026", while the DOB field forces "01/01/1990" (both languages).

**Dumbproof score (1–5):** 3.

**Fix recommendation:**
- Standardize CS on **"ubytovatel"** (the legal term, already dominant, and what PLAN_POPLATEK/INVOICE CS copy uses): `host_details` "Váš ubytovatel", `host_details_help` "Pokud cokoli potřebujete, obraťte se na svého ubytovatele. UbyHost ubytování neprovozuje a rezervaci změnit nemůže." Update the DESIGN.md outline table in the same commit and tell Surface E, which owns `mail_guest_footer_*`. EN: "your host" everywhere guest-facing.
- `why_point_passport` EN "If your host requires it, foreign guests upload a photo of their passport or ID page so the host can check the details. Only your host sees it, and it is deleted after the check." / CS "Pokud to ubytovatel vyžaduje, cizinci nahrají fotku stránky pasu nebo průkazu, aby mohl údaje zkontrolovat. Vidí ji jen ubytovatel a po kontrole se smaže."
- Optionally (low), switch the DOB auto-separator to "." in both languages to match every other date (`validation` already parses dots; `date_placeholder` → "DD.MM.YYYY" / "DD.MM.RRRR"; update the "Enter the full date…" messages).

---


## Surface B — Auth / login

Evidence base: every screen below was rendered through the real app (`TestClient(app)`, mock UbyPort, EN and CS cookies, plus a no-cookie visitor). Scratch scripts are in `/tmp/uby-2-audit/scratch_B/` (`render.py`, `probe.py`, and rendered HTML in `out/`). No file under `/tmp/uby-2` was changed.

Flow map as the code runs it (`App/app/routes/admin_accounts.py`, `App/app/auth.py:270-293`):
`GET /login` → `POST /login` → (a) wrong password → login re-render 401 · (b) 12 failures per IP+username or 30 per IP in 15 min → 429 · (c) `totp_enabled` → `two_factor_login.html` rendered **in the POST response**, with a 10-minute signed `pending` token (`auth.py:28`) → `POST /login/2fa` → next page · (d) `must_change_password` → `/account/password` (forced set-password screen) → in **production**, every account without 2FA is sent to `/account/2fa/setup` (`auth.py:287-290`) → `POST` → `two_factor_recovery.html` rendered **in the POST response** → "I saved them — continue" → `/`. Logout is `POST /logout` → `/login`.

Things that don't exist: there is **no self-serve "forgot password" route**, and `user_account` has **no e-mail column** (`db.py:24-38`). Nobody can sign up; an admin creates the account on `/admin/users` and passes on a temporary password shown once (`users.html:11-27`). The only recovery an admin can do is **Reset password**, which also quietly clears 2FA (`admin_accounts.py:316-317`, `auth.reset_totp`).

---

### B → Shared auth chrome (`auth_base.html`)

**Job of this screen:** a calm, branded frame for every signed-out or first-run security step, with a language switch and a way to get help.

**Current flow:** From the top: horizontal lockup (`auth_base.html:21`), EN/CZ pill switch (`:23-28`), env banner on mock deployments (`:29`), then the page body. After that comes a footer with the long `legal.use_acceptance` paragraph (`:32`) and links: Legal · Terms · Privacy · DPA · `support@ubyhost.com` (`:33-40`, from `operator().email`, which defaults to support@ in `config.py:149`). On the right sits a marketing hero with the stacked lockup, headline and a fake product card (`:44-67`, `aria-hidden`). The hero is hidden below 900px (`app.css:2375`, `:3036`).

**Friction found:**
- [blocker] **The language switch sends you to `request.url.path` (`auth_base.html:25`). On the pages that exist only as POST responses, that goes badly:**
  - On the **recovery-codes page** the switch goes to `GET /account/2fa/setup`. 2FA is now on, so that page redirects to `/settings` with "Two-factor authentication is already enabled." The eight codes are **gone for good**, because only their hashes are stored. (Verified in `probe.py`: after the switch, `codes visible: False`.)
  - On the **2FA code page after a wrong code** the switch goes to `GET /login/2fa`, which returns a raw JSON **405 `{"detail":"Method Not Allowed"}`**. That is a dead end.
  - On the first 2FA render it goes to `/login`, so the host has to type the password again.
  - Why a Czech host will click it: see the language-flip finding under Login below.
- [low] **The logo sizes don't match `docs/LOGO.md`, and the later CSS overrides the size the doc asks for.** `app.css:2140` sets `.auth-logo` to `min(220px,70vw)` as documented, but `app.css:2894` overrides it to `min(178px, 60vw)`. The hero mark is documented at 300px (`app.css:2141-2145`) but overridden to `min(170px, 34%)` (`app.css:2959`). The hero really is hidden below 900px, the horizontal lockup is the only logo on mobile, the stacked lockup appears only in the hero, and `mix-blend-mode: multiply` is kept (`app.css:2120-2130`). So placements pass and sizes fail.
- [low] **The language switch buttons are about 22px tall** (`app.css:341-351`: 11px text, 4px/9px padding). That is under half of 44px, on the one control a non-Czech host needs first on a phone. The labels are "EN" / "CZ" (`host_i18n.py:25-26`). "CZ" is a country code, while the page uses `lang="cs"`. That's acceptable, but see Rejected.
- [low] **The acceptance paragraph repeats on every auth page.** `legal.use_acceptance` (`host_i18n.py:518-523`) shows on the 2FA code, 2FA setup, recovery-codes and set-password screens. The host is already logged in and has already agreed by then, yet the paragraph is the longest text on each of those screens.
- [low] **Practice deployments show a developer instruction to anyone before login.** The env banner (`_env_banner.html`, `role="alert"`) says "Set UBYHOST_UBYPORT_ENV to test or prod…" on the public login page. The copy belongs to Surface C, but a demo visitor meets it here first.

**Dumbproof score (2/5):** it looks calm and on-brand, but one control (the language switch) destroys state on two of the five screens that use this chrome.

**Fix recommendation:**
1. Add a `lang_next` context variable. `auth_base.html:25` should use `{{ lang_next | default(request.url.path ~ …) }}`.
   - `two_factor_login.html` sets `lang_next = '/login'`.
   - `two_factor_recovery.html` **hides the switch** with a `{% block lang_switch %}` override. It has no safe GET to return to, and after the language fix in B-5 [UX-22] the page already shows in the host's language.
   - Add `GET /login/2fa` → 303 `/login?notice=2fa_expired`, so a stray GET never shows JSON again.
2. `.auth-lang-switch button { min-height: 44px; min-width: 44px; font-size: var(--text-sm); }`.
3. Remove `<p class="auth-foot-acceptance">` from `auth_base.html` and keep the links. Login keeps its own single acceptance line (see Login).
4. Logo: either delete the overrides at `app.css:2894` and `:2959` so the documented 220/300px apply, or have Joe update LOGO.md to 178/170. Which one is the owner's call. The code and the doc must agree.

---

### B → Login (`login.html`)

**Job of this screen:** get a returning host into their workspace in one try, and tell a stuck host exactly what to do.

**Current flow:**
1. Logo, then the language pill, then the h1 **"Your guest reporting workspace."** / "Váš pracovní prostor pro hlášení hostů." (`host_i18n.py:54`), then the lede "Log in to your UbyHost account" / "Přihlaste se do UbyHost".
2. Username field (`type=text autocomplete=username autocapitalize=none spellcheck=false autofocus`) and password field (`autocomplete=current-password`) (`login.html:16-27`). A "Remember me for 30 days" checkbox. The Turnstile widget, when configured (`:32-34`).
3. The pill button **Continue** / Pokračovat (`:35`). Under it, a grey box with the acceptance sentence (`:36-41`). Under that, the footnote "No public sign-up. UbyHost is invite-only — ask your administrator for an account." (`:44-46`). Then the footer's **second** acceptance paragraph and the links (auth_base).
4. Errors appear in `.auth-alert role=alert` above the form. The username is kept; the password is cleared.

**Friction found:**
- [high] **Every error on this screen is English, even on the Czech page.** Signed-out visitors get Czech by default (`templating.py:113-117`, `PUBLIC_DEFAULT_LANGUAGE="cs"`). The route still passes English literals: "That username or password is not correct." (`admin_accounts.py:59`), "Too many failed attempts. Wait about 15 minutes and try again." (`:46`), and "Security check failed. Please try again." (`:38`). Rendered `login_wrong_cs.html` shows a Czech form with an English error. The moment a host is stuck is exactly when they read a language they didn't choose.
- [high] **The site switches to English right after login.** A host who never touched the switch sees Czech on /login. Once signed in, the fallback becomes `DEFAULT_LANGUAGE="en"` (`templating.py:113-116`), and nothing writes the language cookie at login. So the very next screen (set password, 2FA setup, recovery codes, dashboard) is English. Verified: `pw_forced_nocookie.html` is English after a Czech login page. This is what pushes a Czech host to the language switch, which then loses their recovery codes (see Shared auth chrome).
- [high] **There is no "forgot password" path.** Nothing on the page says what to do. The only hint of help is the bare `support@ubyhost.com` as the fifth link in the 12.5px footer (`auth_base.html:38-40`), with no label. The footnote talks about *sign-up* ("ask your administrator for an account"), which doesn't help someone who already has an account. It also names an "administrator" the host has never met; in this product that person is UbyHost support. Lockout copy (`admin_accounts.py:46`) says "wait" and gives no contact.
- [medium] **The acceptance text is too long, says the same thing twice, and reads like a legal form.** Right under the button: "By logging in or using UbyHost, you agree to the Terms…, the Privacy Policy, and the Legal notice. If you do not agree, do not log in or use the Service." (`host_i18n.py:65-71`), in a tinted box that looks as if it must be read. The footer then adds a second, longer and *different* statement (`legal.use_acceptance`, `:518-523`). It includes the raw path "(including the Data Processing Agreement at /dpa)" and a consumer-law clause. Answer to hypothesis §6.B: it reads like required reading, and there are two versions of it. That makes it look *more* like something hidden, not less.
- [medium] **A deep link (`next`) is lost after one wrong password.** `login.html:15` reads `next` from the *query string*, but the form posts to plain `/login`. After an error the page re-renders with `next=""` (verified in `login_wrong_cs.html`). A host who follows a link from an e-mail (`/login?next=/reservations/123`) and mistypes once lands on the dashboard.
- [medium] **Messages sent back to the login page are silently dropped.** An expired CSRF form redirects to `/login?err=This+form+expired…` (`security.py:165-175`), and a bad or expired 2FA `pending` token redirects to `/login` with nothing (`admin_accounts.py:102-108`). `login.html` only renders `error`, never `flash_error`. So the page just reloads empty, and the host assumes the password was wrong. Putting free text in `?err=` on the login page is also a content-injection risk; it should become a coded notice.
- [low] **The h1 is a marketing line; the real instruction is in the lede.** At `clamp(2.1rem,3.2vw,2.9rem)` weight 790 (`app.css:2904-2910`), the h1 "Your guest reporting workspace." wraps to three lines at 375px and pushes the button toward the fold. The CS lede "Přihlaste se do UbyHost" is missing the case ending; other strings use "UbyHostu" (`host_i18n.py:1101`).
- [low] **After an error, focus goes back to the username** (`autofocus` is hard-coded on `#username`, `login.html:18`), which is already filled in. The field to retype is the password. The error isn't linked to either field (no `aria-invalid`/`aria-describedby`).
- [low] **Turnstile doesn't know the page language.** The widget has no `data-language="{{ lang }}"` (`login.html:33`), so it follows the browser, not the page. Pressing Continue before the challenge finishes gives the vague English 403 above.
- [low] **The "Remember me" checkbox is 16px** (`app.css:2237`), and the label row is about 20px tall.

**Dumbproof score (3/5):** the happy path is fine and the input attributes are right. But errors are in the wrong language, there is no recovery path, and the legal text is doubled.

**Fix recommendation:**
- **Error keys** (new `auth.error.*` in `host_i18n.py` `_INTERFACE_STRINGS`, EN+CS; the route passes the key, the template translates it):
  - `auth.error.bad_credentials` — EN "That username and password don't match. Check for typos and Caps Lock." / CS "Uživatelské jméno a heslo nesedí. Zkontrolujte překlepy a Caps Lock."
  - `auth.error.locked` — EN "Too many unsuccessful attempts. Try again in 15 minutes — or, if you've forgotten your password, email %(email)s." / CS "Příliš mnoho neúspěšných pokusů. Zkuste to znovu za 15 minut, nebo pokud jste heslo zapomněli, napište na %(email)s."
  - `auth.error.turnstile` — EN "We couldn't finish the security check. Wait until the check above the button shows a tick, then press Continue again." / CS "Bezpečnostní kontrolu se nepodařilo dokončit. Počkejte, až se u kontroly nad tlačítkem objeví fajfka, a stiskněte Pokračovat znovu."
- **Keep the language at login:** in `login_submit` and `two_factor_login`, call `host_i18n.remember_language(response, request.state.lang)` on the success response (`admin_accounts.py:79-84`, `:127-136`).
- **Forgot password:** add `<details class="auth-help">` right under the password field. No JS needed.
  - Summary `login.forgot_summary`: EN "Forgot your password?" / CS "Zapomněli jste heslo?"
  - Body `login.forgot_body`: EN "Email %(email)s with your username. We'll set a temporary password for you, and you'll choose a new one when you log in." / CS "Napište na %(email)s a uveďte své uživatelské jméno. Nastavíme vám dočasné heslo a při přihlášení si zvolíte nové."
  - Use `operator().email`.
- **One acceptance line**, plain text with no box. Replace `login.acceptance_*`:
  - EN "By logging in, you agree to the [Terms of Service] (incl. [DPA]), [Privacy Policy] and [Legal notice]."
  - CS "Přihlášením souhlasíte s [obchodními podmínkami] (vč. [DPA]), [zásadami ochrany osobních údajů] a [právními informacemi]."
  - Drop the footer paragraph (see Shared auth chrome). Style it `--text-xs`, `--ink-muted`, no background, visible underlined links, so it clearly isn't hiding anything.
  - *Legal sign-off needed:* the consumer clause moves into the Terms, and the audit event at `admin_accounts.py:85-94` still records the versions.
- **Footnote** `login.footnote`: EN "No account yet? UbyHost is invite-only — write to %(email)s." / CS "Ještě nemáte účet? UbyHost je jen na pozvání — napište na %(email)s."
- **h1 / lede swap:**
  - `login.title`: EN "Log in to UbyHost" / CS "Přihlášení do UbyHostu"
  - `login.lede`: EN "Your guest reporting workspace." / CS "Váš pracovní prostor pro hlášení hostů."
- **Keep `next` on error:** the route passes `next`, the template uses `{{ next if next is defined else request.query_params.get('next','') }}`, and on error re-renders `autofocus` moves to `#password`.
- **Coded notices** in `auth_base` (`?notice=form_expired|2fa_expired|logged_out`), mapped to keys. Never render free text from the URL.
  - `auth.notice.form_expired` — EN "This page was open too long. Please log in again." / CS "Stránka byla otevřená příliš dlouho. Přihlaste se prosím znovu."
  - `auth.notice.2fa_expired` — EN "Signing in took more than 10 minutes, so we started over to keep your account safe. Enter your password again." / CS "Přihlášení trvalo déle než 10 minut, a proto jsme kvůli bezpečnosti začali znovu. Zadejte znovu heslo."
  - `auth.notice.logged_out` — EN "You're logged out." / CS "Odhlásili jste se."
  - Change `security.py:175` to use `?notice=form_expired`.
- **Turnstile:** add `data-language="{{ lang }}"`. Tap target: `.auth-remember { min-height: 44px; }`.

---

### B → 2FA code at login (`two_factor_login.html`)

**Job of this screen:** prove it's really the host, and give a host who lost their phone a clear way in.

**Current flow:** The h1 is "Security code" / "Bezpečnostní kód". The lede says "Enter the six-digit code from your authenticator app, or one recovery code." It is followed by one field labelled "Authentication code" / "Ověřovací kód" (`type=text inputmode=numeric autocomplete=one-time-code maxlength=12`, `:13-14`), the button "Verify and sign in", and the link "Start over" → `/login`. A wrong code shows "That code is not valid." (English only, `admin_accounts.py:124`). Too many attempts shows "Too many attempts. Wait about 15 minutes." (English, `:115`). If the `pending` token is older than 10 minutes, the host is silently bounced to `/login` (`:101-103`). Recovery codes are accepted in the same field, without regard to case or dashes (`auth.py:64-68`, `:102-123`; verified that `aaaa-bbbb` logs in).

**Friction found:**
- [blocker] **On a phone, a recovery code often can't be typed at all.** Recovery codes look like `4415-E886` (hex letters A–F, `auth.py:71-72`). The only field has `inputmode="numeric"`, and on iOS that opens a number pad with no letters. A host who printed their codes, as `account.2fa.recovery_lede` suggests, is stuck at their phone. That is exactly the lost-device case.
- [blocker] **The language switch on this page leads to a JSON 405 or loses the step** (see Shared auth chrome).
- [high] **Nothing helps a host who has lost both the phone and the codes.** No "Lost your phone?" line, no support address in the card; only the bare footer e-mail. The fix already exists (an admin *Reset password* also resets 2FA, `admin_accounts.py:316-317`), but nobody tells the host to ask for it.
- [medium] **The wait message and the 10-minute token clash.** The lockout says "Wait about 15 minutes" and leaves the host on this page. The `pending` token dies after 10 minutes (`auth.py:28`), so after doing what they were told, the next submit silently drops them on /login.
- [low] **The same thing has two names.** Title "Security code" vs label "Authentication code"; CS "Bezpečnostní kód" vs "Ověřovací kód".
- [low] **"Start over" doesn't say it means re-entering the password.**

**Dumbproof score (2/5):** the TOTP happy path is fine, but the lost-device path, the one the brief asks about, fails on mobile and gives no contact.

**Fix recommendation:**
- Keep the main field numeric for the 6-digit code. Under it, add `<details class="auth-help">`:
  - Summary `account.2fa.lost_summary`: EN "Lost your phone? Use a recovery code" / CS "Ztratili jste telefon? Použijte obnovovací kód"
  - Inside, a second `<form>` with the same `pending`, `<input name="code" inputmode="text" autocapitalize="characters" autocomplete="off" spellcheck="false" placeholder="XXXX-XXXX">`, label `account.2fa.recovery_label` EN "Recovery code" / CS "Obnovovací kód", and the same submit.
  - Below it, `account.2fa.no_codes`: EN "No recovery codes either? Email %(email)s with your username and we'll reset two-factor for you." / CS "Nemáte ani obnovovací kódy? Napište na %(email)s své uživatelské jméno a dvoufázové ověření vám resetujeme."
  - No JS needed.
- Change `account.2fa.code_lede` to EN "Enter the six-digit code from your authenticator app." / CS "Zadejte šestimístný kód z autentizační aplikace." The recovery route now has its own home.
- Error keys:
  - `auth.error.code_invalid` — EN "That code didn't work. Codes change every 30 seconds — enter the one showing now." / CS "Kód nefunguje. Kódy se mění každých 30 vteřin — zadejte ten, který vidíte teď."
  - `auth.error.code_locked` — EN "Too many wrong codes. Wait 15 minutes, then log in again from the start." / CS "Příliš mnoho chybných kódů. Počkejte 15 minut a pak se přihlaste znovu od začátku." Add a link to `/login`.
- An expired `pending` token redirects to `/login?notice=2fa_expired`.
- Label `account.2fa.code_label` → EN "Security code" / CS "Bezpečnostní kód" (same as the title).
- `account.2fa.start_over` → EN "Use a different account" / CS "Přihlásit se jiným účtem".

---

### B → 2FA setup (`two_factor_setup.html`)

**Job of this screen:** connect an authenticator app in under a minute. In production this step is mandatory.

**Current flow:**
1. The h1 is "Set up two-factor authentication", with the lede "UbyHost contains identity documents, so every host account requires an authenticator app."
2. A 220px QR code, with the alt text hard-coded in English: "QR code for your authenticator app" (`:9`).
3. A small numbered list (`<ol class="small">`):
   - "Scan this QR code in your authenticator app, or add a **TOTP** entry for UbyHost."
   - "Or enter this setup key manually:" followed by a 32-character unbroken `<code>` (e.g. `GXPWT5ZIXB6V7UL5ASMJWFJI23KVNJF3`).
   - "Enter the generated six-digit code below."
4. The field "Six-digit code" (`inputmode=numeric autocomplete=one-time-code pattern=[0-9]{6} maxlength=6`) and the button "Enable two-factor authentication".
5. A wrong code re-renders with "That code is not valid." (English, `admin_accounts.py:200`).

There is no CSRF hidden input (it relies on `csrf.js`), no logout, no back link, and no help. In production, `require_login` allows only this page and `/logout` (`auth.py:287-290`).

**Friction found:**
- [high] **A host setting up on their phone can't scan a QR code shown on that same phone.** Their only option is to copy by hand a 32-character string with no grouping and no copy button. There's no `otpauth://` "open in app" link, although `auth.totp_uri()` already builds one (`auth.py:60-61`; the route computes it and passes only the QR, `admin_accounts.py:177-181`).
- [medium] **There is no way out, and no one to ask.** In production this screen is forced. If the host has no authenticator app on hand, there is no "Log out" and no "which app should I use?". "TOTP" is jargon; the name of a protocol tells nobody what to install.
- [medium] **Setup doesn't accept a code the way the apps display it.** Authenticator apps show codes as "123 456". The setup field's `maxlength=6` cuts a pasted "123 456" to "123 45", `pattern` fails with a browser-native message, and the server doesn't strip spaces here (`admin_accounts.py:195`), although the login route does (`auth.py:103`).
- [medium] **The error is English only on the CS page, and doesn't hint at clock drift.**
- [low] **The QR `alt` text is English only, and there are inline styles** (`:9-10`). The step list is at `.small` size, so the instructions are the smallest text on the page.
- [low] **Without JS, the form fails silently.** There is no explicit `_csrf` hidden field, unlike `login.html:14`. Without JS the post fails and lands on the silent `?err=` path.

**Dumbproof score (3/5):** clear on a laptop, poor on a phone, and it traps a host who has no app ready.

**Fix recommendation:**
- **Open-in-app button:** pass `totp_uri` to the template. Show `<a class="btn" href="{{ totp_uri }}">` with `account.2fa.setup_open_app`: EN "Add to authenticator app on this phone" / CS "Přidat do autentizační aplikace v tomto telefonu". Show it first below 900px and after the QR on desktop.
- **Setup key:** display it in groups of four (`GXPW T5ZI XB6V …`, via a Jinja filter; the value is unchanged) and add a Copy button (`common.copy`). This needs a few lines of vanilla JS loaded on auth pages; reuse the `data-copy` pattern from `app.js:14-40` in a tiny auth script, or load `app.js`.
- **Copy:**
  - `account.2fa.setup_scan`: EN "Open an authenticator app (for example Google Authenticator, Microsoft Authenticator or 1Password) and scan this QR code." / CS "Otevřete autentizační aplikaci (třeba Google Authenticator, Microsoft Authenticator nebo 1Password) a naskenujte tento QR kód."
  - `account.2fa.setup_key`: EN "Can't scan? Type this key into the app:" / CS "Nejde naskenovat? Zadejte do aplikace tento klíč:"
  - `account.2fa.qr_alt`: EN "QR code that adds UbyHost to your authenticator app" / CS "QR kód pro přidání UbyHostu do autentizační aplikace"
- **Error** `auth.error.setup_code_invalid`: EN "That code didn't match. Enter the newest six-digit code from the app. If it keeps failing, make sure your phone sets its clock automatically." / CS "Kód nesouhlasí. Zadejte nejnovější šestimístný kód z aplikace. Pokud to stále nejde, zkontrolujte, že má telefon automatické nastavení času."
- **Accept spaces:** strip spaces server-side; drop `pattern`; set `maxlength=7`.
- **Hidden `_csrf` field:** add it.
- **Log out:** add the auth-chrome "Not you? Log out" (see B-13 [UX-67]).

---

### B → Recovery codes (`two_factor_recovery.html`)

**Job of this screen:** make sure the host really keeps their lost-phone lifeline before moving on.

**Current flow:** The h1 is "Save your recovery codes" / "Uložte si obnovovací kódy". The lede says "Store these in a password manager or printed copy. Each works once if you lose your authenticator." Then 8 codes in a 2-column `.panel` with inline grid styles (`:7-9`), the bold "They will not be shown again.", and a link styled as a button, "I saved them — continue" → `/` (`:11`, inline styles). The page is the body of the `POST /account/2fa/setup` response (`admin_accounts.py:206`).

**Friction found:**
- [blocker] **The language switch here throws the codes away** (see Shared auth chrome). After the language flip at login (see Login), a Czech host is likely to press it.
- [medium] **Reload, or the browser's "resubmit form?", creates a new set of codes and silently kills the ones already written down.** The POST handler never checks `totp_enabled`, and while the TOTP code is still valid (±30 s, `valid_window=1`) it runs `new_recovery_codes()` again. Verified in `probe.py`: `re-POST … new codes differ: True`, `first code still valid: False`.
- [medium] **There's no Copy all, Print or Download.** "Store these in a password manager" means selecting eight `<code>` elements by hand on a phone.
- [low] **"Shown once" is only said after the list, in small bold text.** CS "při ztrátě autentizátoru": "autentizátor" is stiff. The page doesn't say where the codes will be used later.

**Dumbproof score (2/5):** the message and the single action are clear, but the page can quietly destroy the very thing it exists to protect.

**Fix recommendation:**
- Hide the language switch on this page (see Shared auth chrome).
- In `two_factor_setup_submit`, if `account["totp_enabled"]` is already 1, **don't regenerate**. Redirect to `/settings?msg=` with `flash.accounts.twofa_enabled`.
- Add **Copy all** (`data-copy`, vanilla) and **Print** (`window.print()`, with an `@media print` rule that shows only the card). Replace inline styles with an `.auth-codes` class.
- **Copy** (lede first, then the "shown once" line above the codes):
  - `account.2fa.recovery_lede`: EN "If you ever lose the phone with your authenticator app, each of these codes lets you log in once. Keep them in a password manager or print them." / CS "Pokud někdy přijdete o telefon s autentizační aplikací, každý z těchto kódů vás jednou přihlásí. Uložte si je do správce hesel nebo si je vytiskněte."
  - `account.2fa.recovery_once`: EN "Save them before you leave this page — they can't be shown again." / CS "Uložte si je, než stránku opustíte — znovu je zobrazit nelze."

---

### B → Choose your password, first login (`account_password.html`, `must_change_password` branch)

**Job of this screen:** swap the admin-issued temporary password for the host's own, on the first try.

**Current flow:**
1. auth_base chrome. The h1 is "Choose your password", with the lede "Replace the temporary password before opening your workspace."
2. The field **"Current password"** (placeholder "Temporary password…", `autocomplete=current-password`).
3. "New password" (`minlength=12 autocomplete=new-password`, placeholder "At least 12 characters…"), with the **rules shown up front** as `.auth-hint`: "Use at least 12 characters, upper- and lower-case letters, and a number."
4. "Repeat new password", then the button **Continue**.
5. Errors: "Current password is wrong." / "The new passwords do not match." / `password_error()` output such as "Use both upper- and lower-case letters.". All are English only (`admin_accounts.py:221,227,233`; `auth.py:153-162`). On error, **all three fields are cleared**.
6. On success the host goes to `/` with "Password changed.", which in production is immediately replaced by the 2FA setup redirect (flash lost).

**Friction found:**
- [high] **Errors are English only** (verified: `pw_forced_weak_cs.html` shows "Use both upper- and lower-case letters." under a Czech form). The language flip at login makes it worse: without a cookie the whole page is English (`pw_forced_nocookie.html`).
- [medium] **The first-run sequence has no sense of progress and no exit.** In production it's three forced screens in a row (password → 2FA setup → recovery codes) with no "step 1 of 3" and no log out. A host who planned "just log in" doesn't know how long this takes.
- [medium] **An error doesn't point at the field that caused it.** It sits in a top alert, and there's no `aria-invalid`/`aria-describedby`. The rules hint isn't linked with `aria-describedby`. All three fields are wiped, so the temporary password has to be found and pasted again.
- [low] **The label says "Current password" in forced mode**, while the placeholder says "Temporary password". The label should just say what it is.
- [low] **"Remember me" is thrown away.** The session re-issued here and after 2FA setup drops the flag (`admin_accounts.py:241`, `:207`), so a host who ticked "Remember me for 30 days" gets 12 hours.
- Hypothesis §6.B ("rules stated before typing?"): **pass**. The rules show under the field before any input, in both branches.

**Dumbproof score (3/5):** the rules come up front, which is the key thing. The language, progress and error handling all fall short.

**Fix recommendation:**
- **Errors → keys:**
  - `auth.error.temp_password_wrong` — EN "That temporary password isn't right. Use the one you were given." / CS "Dočasné heslo nesedí. Použijte to, které jste dostali."
  - `auth.error.current_password_wrong` — EN "Your current password isn't right." / CS "Současné heslo nesedí."
  - `auth.error.passwords_mismatch` — EN "The two new passwords are different. Type the same one in both fields." / CS "Nová hesla se liší. Do obou polí napište stejné heslo."
  - `password_error` returns keys: `auth.password.too_short` "Use at least 12 characters." / "Použijte alespoň 12 znaků."; `auth.password.mixed_case` "Use both upper- and lower-case letters." / "Použijte malá i velká písmena."; `auth.password.digit` "Add at least one number." / "Přidejte alespoň jednu číslici."; `auth.password.too_long` "Use no more than 256 characters." / "Použijte nejvýše 256 znaků."
  - Keep the English strings in `create_account` for the admin form via the same keys (C).
- **Field-level errors:** show them under the field (`aria-invalid`, `aria-describedby="new_password-hint new_password-error"`). Keep `current_password` filled only when the error is about the new password. Don't echo secrets otherwise; that's a security trade-off, so document it either way.
- **Forced-mode label** `account.password.temporary`: EN "Temporary password" / CS "Dočasné heslo".
- **Progress**, only when `DEPLOYMENT=='production' and not totp_enabled`:
  - `account.password.choose_lede`: EN "Step 1 of 3 · Replace the temporary password with your own." / CS "Krok 1 ze 3 · Nahraďte dočasné heslo vlastním."
  - Setup lede prefix "Step 2 of 3 ·" / "Krok 2 ze 3 ·". Recovery "Step 3 of 3 ·" / "Krok 3 ze 3 ·".
  - In non-production, show the lede without the step prefix.
- **Log out** (auth_base, when `current_user`): a small POST form, `auth.not_you` EN "Not you? Log out" / CS "Nejste to vy? Odhlásit se".
- **Keep "Remember me":** carry `rm` from the session payload when re-issuing the session.

---

### B → Change password, in-app (`account_password.html`, `base.html` branch)

**Job of this screen:** a signed-in host changes their password without surprises.

**Current flow:** Host chrome, the h1 "Change password", the lede "Changing it signs out your other sessions." / CS "Změna odhlásí ostatní relace.". Three fields with the right `autocomplete` values and the rules hint up front. The button "Save password". A `banner err` shows English-only errors. On success: `/` with the flash "Password changed." / "Heslo bylo změněno."

**Friction found:**
- [high] The English-only errors are shared with the forced screen above (same fix item).
- [low] **CS "relace" (sessions) is IT jargon.** Also, success sends the host to the dashboard instead of back to Settings, where they came from (`settings.html:190`).
- [low] **No hidden `username` field for password managers.** Without it, some managers save the new password against the wrong entry.

**Dumbproof score (4/5):** simple and honest; only the language of its errors and one word of jargon.

**Fix recommendation:**
- `account.password.change_lede`: EN "Changing it logs you out on your other devices." / CS "Změnou hesla se odhlásíte na ostatních zařízeních."
- On success, redirect to `/settings#settings-account`.
- Add `<input type="hidden" autocomplete="username" value="{{ current_user.username }}">` (applies to both branches).

---

### B → Lost password / lost device, the paths that don't exist yet (login + `users.html` hand-off)

**Job of this screen:** a locked-out host gets back in with one message to the right place.

**Current flow:** There is no self-serve path, and there can't be one without schema work (no e-mail on `user_account`). What really happens: the host must guess to e-mail the unlabelled `support@ubyhost.com` in the footer. An admin opens `/admin/users` → row menu → **Reset password**, which generates a temporary password and **also resets 2FA** (`admin_accounts.py:316-317`). The panel says only "Password reset … The old password no longer works." (`users.html:13-16`, `host_i18n.py:2341-2342`). The admin passes on the credentials somehow. First-account creation works the same way (`users.create.*`). The credential panel doesn't include the login address or what the host will be asked to do.

**Friction found:**
- [high] **The host has no signposted route** (covered by the Login and 2FA items: forgot-password disclosure, "no codes" line).
- [medium] **The admin isn't told that Reset also wipes 2FA,** so they don't know it's the lost-phone fix. The new host isn't warned that an authenticator app will be required at first login.
- [medium] **A signed-in host who changed phones can't re-enrol 2FA or get new recovery codes.** `/account/2fa/setup` bounces enabled accounts to Settings (`admin_accounts.py:168-169`), and Settings offers no re-enrol. So they need support even while logged in.

**Dumbproof score (1/5):** nobody is told what to do. Recovery works only if the host already knows whom to e-mail.

**Fix recommendation:**
- Login/2FA copy as above.
- In `users.html`, when `new_credential.reset`, add `users.credential.reset_2fa`: EN "Two-factor authentication was reset too. They'll set it up again right after choosing a new password." / CS "Resetovalo se i dvoufázové ověření. Hned po zvolení nového hesla si ho nastaví znovu."
- For every new credential, add `users.credential.next_steps`: EN "Send them the login address %(url)s with these details. At first login they'll choose a password and set up an authenticator app." / CS "Pošlete jim adresu pro přihlášení %(url)s spolu s těmito údaji. Při prvním přihlášení si zvolí heslo a nastaví autentizační aplikaci."
- Later, a separate item overlapping with C: Settings → "Move to a new phone", which requires the current password plus a current code, then re-runs setup and issues new codes.

---

### B → Logout (`POST /logout`)

**Job of this screen:** end the session and confirm it.

**Current flow:** The sidebar button posts to `/logout`, which clears the cookie and does a 303 to `/login` (`admin_accounts.py:141-145`). The login page looks exactly as before, with no message.

**Friction found:**
- [low] **No confirmation.** On a shared reception PC, the only evidence of logging out is the login form showing again.

**Dumbproof score (4/5):** it works; it just doesn't say so.

**Fix recommendation:** redirect to `/login?notice=logged_out`, which shows "You're logged out." / "Odhlásili jste se." through the coded-notice mechanism (B-12 [UX-66]).

---


## Surface C — Host app, including onboarding

**How I checked this.** I rendered 60+ host pages in **EN and CS** with a FastAPI `TestClient`. The script is `/tmp/uby-2-audit/scratch_C/render.py`, and `render2.py` covers non-demo states. It uses a real admin account, and the pages were rendered in four states:
- a workspace with nothing set up;
- a legal entity only;
- a bare property just after creation;
- the full `demo.seed()` dataset, with the demo apartments then renamed to non-demo names so the send, reported and rejected paths render.

I also POSTed 18 host actions in both languages and captured the flash text each one puts in the redirect (`msg=` / `err=`). Line numbers below refer to the repo as cloned. Output files are in `/tmp/uby-2-audit/scratch_C/out{,2}/`. I checked HTML structure with a spec-compliant parser (html5lib, installed only into the scratch dir). Nothing under `/tmp/uby-2` was modified.

---

### C → Signed-in chrome: sidebar, app bar, alerts, toasts, confirm dialog (`base.html`, `_components.html`, `static/app.js`, `static/app.css`)

**Job of this screen:** keep the host oriented on every page: where am I, what is on fire, how do I get help.

**Current flow:**
1. **Desktop sidebar** (`base.html:37-152`), top to bottom:
   - the mark plus live "UbyHost" (per LOGO.md);
   - the environment badge;
   - the user;
   - "Search or jump…" (Ctrl K);
   - up to 8 property letter marks;
   - navigation groups: Operations (Overview, Stays), Records (Reports, House book), Properties (All properties, then "Set per property" with Guest links and Automation & UbyPort, then Legal entities), Account (Settings, Users);
   - a footer link row: Help · Legal · Terms · Privacy · DPA · Subprocessors · **Support — support@ubyhost.com** (`base.html:134-137`, from `operator().email`, default `support@ubyhost.com` in `config.py:149`);
   - then the EN/CZ switch, `?` and Log out.
2. **Mobile:** the app bar shows ☰, the mark, "Help", ⌕ and the environment badge.
3. **Open alerts:** every unresolved alert renders as a **fixed** bubble stack at the top right (`base.html:174-199`; `app.css:676-685`: `position:fixed; top:14px; right:14px; width:min(340px,…)`, full width on mobile at `app.css:1705`).
   - There is **no cap**: `templating.render` passes `alerts.present_many(raw_alerts)` in full, and `alerts.open_alerts` has no LIMIT (`alerts.py:356-364`).
   - With the demo data, every page carries 3 bubbles, two of them for the **same stay** (Vinohrady 16.09: "Overdue by 5 days · 1/2" and "Waiting for guest forms · 1/2").
4. **Flash:** a toast from `?msg=` / `?err=` (`base.html:201-228`, `templating.py:136-137`). The undo toast appears after archiving a stay.
5. **Destructive actions** go through `<dialog id="confirm-dialog">` via `form[data-confirm]` / `button[data-confirm]` (`app.js:532-590`).

**Friction found:**
- [high] **The alert stack is uncapped and fixed over the page-header action zone.**
  - Page-header CTAs sit top right ("Add a property", "Update calendars", "Send all ready stays"), exactly under a 340 px fixed stack. On a phone the stack spans the full width and covers the app bar and page title.
  - A host with 10 overdue stays gets 10–20 bubbles on **every** page, including pages about something else.
  - Appendix 5 §10.4(2) (cited in `alerts.py:3-6`) requires a prominent warning. It doesn't require covering the controls.
- [medium] **Duplicate alerts for one stay.** `deadline` and `guest_incomplete_checkin` both raise for the same reservation, so the host reads the same stay twice and dismisses twice.
- [medium] **Flash text rides in the URL.** `admin_helpers.back()` puts the message in the query string (`admin_helpers.py:13-27`), which causes three problems:
  1. The toast re-appears on reload or when a bookmarked URL is reopened.
  2. `flash.apartments.pin_rotated` puts the **new guest PIN into the URL** (`?msg=New PIN generated: 300424`, captured from `POST /apartments/1/regenerate-pin`), so it lands in browser history and access logs.
  3. Anyone can craft `/?msg=…` or `/?err=…` and show arbitrary text inside the signed-in chrome. It's escaped, but it's still a content-spoofing surface.
- [low] **Support is findable but buried.** The support address is the 7th item of a 13 px legal link row (`base.html:122-138`). It meets DESIGN.md's contact split, but a stressed host scanning for help reads it as legal small print.
- [low] **The language button says "CZ"** (`host_i18n.py` `lang.cs: "CZ"`), a country code sitting next to the language code "EN". Czech users recognise "CS" or "Čeština" more reliably.
- [low] **The command-palette search input has no label.** It's `data-command-input` with only a placeholder (`base.html:282`), and it's the only unlabelled control on every page (html5lib scan). Needs `aria-label`.
- [low] **The zero-state Overview has two `<h1>`s**: the page header's "Overview" and the onboarding "Your five-step launch" (`dashboard.html:71-79` plus `_components.html:311`).
- [low] **The env banner addresses operators, not hosts.** It reads "Set UBYHOST_UBYPORT_ENV to test or prod before you rely on it." (`_env_banner.html`). Fine on staging, but it's operator copy.

**Dumbproof score (1–5):** 3. Navigation and contact split are clear, but the uncapped fixed alert stack fights every page's primary action.

**Fix recommendation:**
- **Cap the stack** at 2 bubbles, most severe first. Then add one summary line: EN "%(n)s more alerts — see Overview" / CS "Další upozornění: %(n)s — zobrazit v Přehledu", linking `/#needs-action`.
- **Collapse alerts per reservation.** In `alerts.present_many`, merge rows that share a `reservation_id` into one bubble, keeping the most severe title.
- **Move the stack out of the header zone.** Place it bottom-right on desktop, above the toast stack (tokens `--z-toast`). On mobile, make it a single dismissible strip under `.appbar`, not over it.
- **PIN flash:** make the text PIN-free. EN "New PIN generated. Copy it from the guest link card and update your portal messages." / CS "Nový PIN je vygenerovaný. Zkopírujte ho z karty odkazu a upravte zprávy na portálech." The card already shows the PIN.
- **Longer term:** move flashes from `?msg=` to a signed one-shot cookie. This is a separate, larger item.
- **Sidebar support line:** move it out of the legal row onto its own line above the language row. EN "Need help with UbyHost? support@ubyhost.com" / CS "Potřebujete pomoc s UbyHostem? support@ubyhost.com".
- **Language label:** `lang.cs` becomes "CS". The CS table keeps "CS" too, or use "Čeština"/"English" in the switcher's `aria-label`.
- **Palette input:** add `aria-label="{{ t('command.open') }}"`.
- **Zero-state header:** drop the page-header `<h1>` when `onboarding_welcome` renders.

---

### C → First run: a brand-new host's first five minutes (`dashboard.html` zero state, `onboarding.html`, `_components.html::onboarding_*`, `onboarding.py`, `routes/onboarding.py`, then `entities.html` and `apartment_form.html` as reached from it)

**Job of this screen:** get a new host from an empty workspace to a guest link they can paste into Airbnb, with one obvious task at a time.

**Current flow (rendered; empty workspace, EN and CS):**
1. **`/` (Overview).** The page header "Overview" comes first, with the lede "Your reporting work, ordered by legal urgency and the next action." and an **"Update calendars"** button. Then `onboarding_welcome`:
   - kicker "Your five-step launch", h1 "Set it once. Welcome every guest calmly.", a lede, and a 0% meter with "Skip setup guidance";
   - a **"Do this now"** block: "1 Legal entity … Have ready: legal name, IČO, registered address, e-mail and phone", primary **"Add legal entity"**, "Learn why →";
   - the full list of all five steps, **repeating step 1 verbatim**, each with a "Learn why" disclosure;
   - "Nothing goes live by accident";
   - in mock only, "Explore with demo data".
2. **"Add legal entity"** opens `/entities`. There is a create form on the right. Only *Name* is `required` (`entities.html:8`), while IČO, seat and e-mail carry no marker at all.
   - On save, `create_entity` redirects to `/apartments/new?legal_entity_id=…` with "Added X. Next, add your first property." (good).
   - The onboarding step only counts as done when name, seat, IČO **and** e-mail are all filled (`onboarding.py:38-46`).
3. **`/apartments/new`** is the long property form (see the property form section). On create, the host lands on `/apartments/{id}#calendars` with "Property created. Next, paste your Airbnb or Booking.com calendar link." (good).
4. **Back on Overview (step 3 of 5)** the host sees three competing next steps:
   - the onboarding banner "Connect calendars" (coral);
   - a "Finish setup" panel: "My flat — 8 items to fix";
   - the empty queue "No stays in the current window. Either the calendars have nothing booked, or they have not been synced yet." with **"Update calendars now"**, which syncs zero calendars.
   - The header "Update calendars" is also still there.
5. **Step 4, "Automation & UbyPort",** links to `/automation#apartment-N`. The host picks a mode and credentials and saves. The step stays "not done" because it is really `apartment_count > 0 and not setup_issues` (`onboarding.py:87-95`), and the setup issues include **address fields that are not on the automation page** (house number, postcode, municipality: `validation.validate_apartment`). The automation card only shows a red "3 to fix" pill with no list (`automation.html:18-19`).
6. **Step 5, "Guest link",** is done exactly when steps 3 and 4 are done (`onboarding.py:97-110`), so it can **never** be the current step. Progress jumps from 3/5 to 5/5, and the finish card ("You are ready — Guest link and PIN are live") appears.

**Friction found:**
- [high] **A host with no Airbnb or Booking calendar can never finish onboarding.** The `calendars` step requires an active iCal feed (`onboarding.py:81-86`), and `guest_link` repeats that requirement. Direct-booking hosts who add stays by hand (Stays → Add stay) stay at "2 of 5" forever, and the banner nags on every page that includes `onboarding_banner`.
- [high] **Step 4 is a loop the host can't see.** The step sends them to `/automation`, but its done-condition is "no validation errors on the property", and some of those fields exist only on `/apartments/{id}#address`. `/automation` shows "N to fix" with no list and no field links. The host saves, nothing changes, and there's no explanation.
- [high] **Step 3's Overview names the wrong next action.** "Update calendars now" and header "Update calendars" are offered while **zero calendars are connected**. The empty copy "Either the calendars have nothing booked, or they have not been synced yet" doesn't consider "you haven't connected one". That puts three coral or neutral CTAs on one screen (banner, setup panel, empty state) with no single next step.
- [medium] **The step-1 done criterion is invisible.**
  - Entity form fields that the step needs (seat, IČO, e-mail) are unmarked. A host who saves name only gets "Added X. Next, add your first property.", yet onboarding still shows step 1 as current.
  - `onboarding.entity.prepare` lists "phone" as needed, but phone is optional (`entities.html:35`).
- [medium] **CS "Právnická osoba" / EN "Legal entity" is wrong for many hosts.** "Právnická osoba" legally means a company. A sole trader (fyzická osoba podnikající), the most common small STR host, reads "Přidat právnickou osobu" as "not me". The field hint already uses "provozovatel / správce objektu" (`apartment.form.entity.*`).
- [medium] **"Do this now" duplicates step 1 of the list directly below.** The first viewport repeats the same title, detail and "Have ready" twice, and "Learn why" appears twice.
- [medium] **Onboarding advice contradicts the defaults.** `onboarding.automation.prepare` says "Start with Manual if unsure", but the new-property form **pre-selects "Automatically after a set number of hours" with 24 h** (`apartment_form.html:242`, `value="scheduled" selected`). A host who follows the checklist and skims the form gets automatic police sending.
- [medium] **CS/EN copy is marketing-flavoured and has calques:**
  - "Set it once. Welcome every guest calmly." / "Nastavte jednou. Každého hosta přivítejte v klidu." is a slogan where a task title belongs;
  - "first guest journey" / "první cesta hosta" is a calque of UX jargon;
  - "Přesné hodnoty zabrání odmítnutí hlavičky UbyPortem" uses the protocol word *hlavička*;
  - "Chcete se nejdřív učit bez skutečných údajů?" is stiff;
  - "Politika fotografie pasu nebo dokladu" is a calque of "policy".
- [low] **Demo is offered where it can't work.** `reservations.html:231-233` renders "Explore with demo data" unconditionally, while the Overview gates it with `demo_available` (mock only). In prod, clicking it returns the EN-only error "Demo data is available only in a fresh staging or mock workspace." (`routes/onboarding.py:32`).
- [low] **The dismissed-state card doesn't check for an entity.** "Setup guidance is hidden" offers "Add a property" as primary (`dashboard.html:81-88`) even when no entity exists.

**Dumbproof score (1–5):** 2. Steps 1–3 are well guided with good "Next, …" flashes, but two primary-path dead ends (no-iCal hosts, the invisible step-4 loop) and a wrong next step on Overview fail lenses 1 and 4.

**Fix recommendation (the first five minutes, in order):**
1. **Make the calendar step satisfiable without iCal.** It is done if `feed_count > 0` **or** any active manual reservation exists. The step copy offers both:
   - EN "Connect Airbnb or Booking.com — or add a direct booking by hand." / CS "Připojte Airbnb nebo Booking.com — nebo přidejte přímou rezervaci ručně."
   - Secondary link EN "Add a stay by hand" / CS "Přidat pobyt ručně" → `/reservations#add-stay-panel`.
2. **Rename step 4 and make it finishable in one place.**
   - Title: EN "Police reporting details" / CS "Údaje pro hlášení policii".
   - URL: `/apartments/{id}#ubyport`. That page has the credentials **and** the address.
   - The `/automation` card lists the missing items with links instead of a count. EN "Still missing: IDUB, house number, postcode" / CS "Ještě chybí: IDUB, číslo popisné, PSČ" (each a link to `/apartments/{id}#field`).
3. **Give step 5 its own done signal.** It is done when the host copies the portal message or opens the guest preview. Record that with a tiny POST beacon from the copy button, or reuse the "finish" card as the step. Otherwise, drop to four steps so progress never jumps.
4. **Overview while stays = 0:**
   - If no feed exists, the empty state says EN "No stays yet. Connect a booking calendar so arrivals appear here automatically." / CS "Zatím žádné pobyty. Připojte kalendář rezervací a příjezdy se tu objeví samy." with **one** primary "Connect a calendar" / "Připojit kalendář" → `/apartments/{id}#calendars`.
   - Hide the header "Update calendars" until a feed exists.
   - When the onboarding banner is showing, suppress the "Finish setup" panel. The banner already names the one next step.
5. **Mark the entity fields.** Add `required` to seat, IČO and e-mail (they gate step 1). Change `onboarding.entity.prepare` to EN "Have ready: name, IČO, registered address and a contact e-mail." / CS "Připravte si: jméno nebo název, IČO, sídlo a kontaktní e-mail."
6. **Rename the entity concept** everywhere a host reads it, keeping the internal code name:
   - `nav.entities`: EN "Operators" / CS "Provozovatelé";
   - `onboarding.entity.title`: EN "Operator" / CS "Provozovatel";
   - `.action`: EN "Add operator" / CS "Přidat provozovatele";
   - detail: EN "Who runs the accommodation — a company or a self-employed person." / CS "Kdo ubytování provozuje — firma nebo podnikající fyzická osoba."
7. **New property defaults to Manual** (`apartment_form.html` `option value="manual" selected`), matching the onboarding advice.
8. **Remove the duplicate.** When `onboarding.current` is shown in "Do this now", render the list below as compact one-liners: title, ✓ or number, and no detail/prepare text.
9. **Copy (host_i18n EN and CS):**
   - `onboarding.welcome_title`: EN "Set up UbyHost in five steps" / CS "Nastavení UbyHostu v pěti krocích";
   - `onboarding.finish_line`: EN "Finish these five steps and you can send guests their registration link." / CS "Dokončete těchto pět kroků a můžete hostům poslat odkaz k registraci.";
   - `onboarding.property.why`: CS "Přesné údaje zabrání tomu, aby UbyPort hlášení odmítl.";
   - `onboarding.demo_title`: CS "Chcete si to nejdřív vyzkoušet nanečisto?";
   - `onboarding.finish_passport_tip`: EN "Passport or ID photo for this property:" / CS "Fotka pasu nebo dokladu u tohoto ubytování:".
10. **Gate the demo button** in `reservations.html` on `demo_available`, as the Overview already does.

---

### C → Overview / dashboard (`dashboard.html`, `routes/admin.py::dashboard`, `reporting.queue_groups`, `_components.html::next_action/progress_pill`)

**Job of this screen:** tell the host the single most urgent thing to do now, then the rest of the work queue.

**Current flow (rendered, demo data):**
1. Page header "Overview" with "Update calendars" and "Clear demo data".
2. **When onboarding is finished but not dismissed:** the large green **finish card** ("You are ready / Guest link and PIN are live", with link, PIN, tips and three buttons: `dashboard.html:92-96`) renders **above** everything else. Otherwise the onboarding banner renders.
3. The **focus card** (`dashboard.html:98-142`): eyebrow "Past the deadline", then property, dates, "overdue by 5 days", pill, "1 / 2 guest forms".
   - Buttons: "Copy guest link" (small), "Add a guest by hand", "Open the stay" (primary), and ⋯.
   - The focus is `needs_action[0] or waiting[0]` (`admin.py:145`).
4. The "Finish setup" panel, if there are validation issues.
5. The four queue sections: **Needs action now** (the focus stay is repeated as row 1), **Waiting for guests**, **Upcoming** and **Recently completed**. Each is a table: Stay (with next-action line) · Deadline · Guests "x / y" · Reporting pill · actions.
6. The collapsed "How sending works" note.

**Friction found:**
- [high] **The most urgent action isn't first.** Once onboarding finishes, the finish card (≈ 260 px tall, green gradient, 3 buttons, `app.css:1891-1899`) sits **above** an overdue focus card until the host clicks "Skip setup guidance". This is the brief §6.C hypothesis, confirmed. The same card also competes with the focus card's primary.
- [medium] **The "Recently completed" rows say the opposite of what they mean.** `next_action` has no branch for `reported` / `not_required`, so it falls through to `action.check_missing`: "Open the stay and check what is missing." That text renders next to a "Reported" or "Exempt" pill (`_components.html:28-36`).
  - The same section lists **future** stays ("arrives in 9 days") as "Recently completed".
- [medium] **"Deadline" column mixes two meanings.** Future stays show "arrives in 6 days", which is an arrival, not a deadline. A reader has to decode the colour.
- [medium] **Section headings have no counts.** `reporting.queue_counts` is computed and passed as `counts` (`admin.py:135,159`) but never rendered. The docstring even says "the counts beside the headings can be trusted". The host can't see "7 need action" without scrolling.
- [medium] **"Exempt" / "Výjimka"** (`status.not_required`) will collide with the stay-fee plan's per-guest **Exempt / Osvobodit** decision (PLAN_POPLATEK §13.3 `stay.fee.decision.exempt`). One word would mean "no police report" in one pill and "no fee" in the next panel.
- [low] **"0 / ?" guests** is unexplained. The "?" means "headcount unknown".
- [low] **The focus card repeats row 1 of "Needs action now"** in full.
- [low] **"Guest details are complete — they will send automatically when guests submit."** (`action.ready_immediate`) contradicts itself: complete, yet waiting for guests to submit.
- [low] **CS "1 / 2 formulářů hostů"** (`dashboard.focus.guest_forms`) is ungrammatical ("1 formulářů").

**Dumbproof score (1–5):** 3. The focus card is genuinely good and the queue is ordered by legal urgency, but the finish card outranks an overdue stay and completed rows tell the host to "check what is missing".

**Fix recommendation:**
- **Order:**
  1. The focus card always comes first.
  2. The onboarding finish card renders **below** the queue, or as a slim one-line banner when `focus.urgency in ('overdue','urgent')`. EN "Setup is done — your guest link and PIN are ready." / CS "Nastavení je hotové — odkaz a PIN pro hosty jsou připravené." plus a link "Show link" / "Zobrazit odkaz".
- **Add `next_action` branches:**
  - `reported`: EN "All guests reported. Nothing to do." / CS "Všichni hosté jsou nahlášení. Není třeba nic dělat." (key `action.reported`);
  - `not_required`: EN "Only Czech guests — nothing to report." / CS "Jen čeští hosté — policii se nic nehlásí." (key `action.not_required`).
- **Rename "Recently completed"** to EN "Done — nothing to do" / CS "Hotovo — není třeba nic dělat".
- **Counts in headings:** `dashboard.section.needs_action` gets `(%(count)s)` in both languages.
- **Rename the column** `dashboard.table.deadline` to EN "When" / CS "Kdy", keeping the deadline sub-line for non-future rows.
- **Rename the reporting status:** `status.not_required` and `stay.detail.guests.exempt` become EN "No report needed" / CS "Nehlásí se". This frees "Exempt" for the stay fee.
- **Show a dash for unknown headcount:** replace "?" with "—" and add `title` EN "Number of guests not known yet" / CS "Počet hostů zatím neznáme".
- **`action.ready_immediate`:** EN "All forms complete — UbyHost sends them automatically." / CS "Všechny formuláře jsou hotové — UbyHost je odešle automaticky."
- **`dashboard.focus.guest_forms`:** CS "Formuláře hostů: %(filled)s/%(expected)s"; EN "Guest forms: %(filled)s/%(expected)s".

---

### C → Stay detail (`reservation_detail.html`, `routes/admin.py::reservation_detail`, `reporting.send_controls`)

**Job of this screen:** for one booking, show whether the guests are registered and reported, and give the one action that moves it forward.

**Current flow (rendered: incomplete #1, demo #2, reported #2 non-demo, rejected #12, cancelled #18; EN and CS):**
1. **Header** (`:7-13`): "Vinohrady Studio · 23.09.2026 – 26.09.2026", lede "3 nights · Reserved" (the raw iCal summary), and "← Back to stays".
2. **Command panel** (`:15-86`): eyebrow "Next step" plus one sentence from `send_hint_key`. The primary button depends on state:
   - Send (`btn accent primary`) when sending is possible;
   - Fix when rejected and not sendable;
   - View reports when reported;
   - otherwise **Copy guest link**.
   
   Then "Add a guest" and ⋯ (copy link again, open guest form, archive with confirm, Guest links & templates). The collapsed "Edit stay details" holds the label and expected guests.
3. **Guest assignment panel** (`:88-118`): "No guest e-mail has claimed this stay yet." / "Assigned to l***@…" with Release (confirm) and Reopen.
4. **Metrics strip** (`:120-160`): Reporting deadline · Guest forms "x / y" plus "0 reported · 2 subject to the duty" · Reporting pill plus automation note.
5. **Guests** (`:162-272`):
   - one card per guest: name, lead pill, state pill, ⋯ (Edit, PDF, Archive with confirm);
   - 8 facts, including "Entered by: guest";
   - "Mark ID checked", issues, and `last_errors`;
   - an empty state "No guest has filled in a form yet." with "Add a guest".
6. **Reports** (`:274-298`, only `{% if submissions %}`): a table of When / Outcome / Receipt stamp with a coral **"Doručenka"** button per row.
7. **Stay settings** (`:300-324`, collapsed): guest e-mail, stay state, private note, Save.

**Friction found:**
- [high] **A reported stay is told the opposite of the truth.** Next step reads "Nothing to send: no guest record is subject to the reporting duty" on stay #2 after both guests were reported. Its own metric says "2 reported · 2 subject to the duty". `send_controls` uses `hint.nothing_duty` for both `not_required` and `reported` (`reporting.py:440-441`).
- [high] **A cancelled stay still looks active and asks for the guest link.** Stay #18 (`status='cancelled'`) renders "Next step: Send the check-in link to the guest…", primary "Copy guest link" and "arrives in 45 days". The only trace of the cancellation is the pre-opened Stay-settings `<details>` at the bottom (`:300`). A host can easily chase a guest who cancelled. Archived stays have the same problem: no banner.
- [high] **An incomplete stay gets a generic, partly wrong next step.** Stay #1 (1 of 3 forms) reads "Complete guest details, signatures, and passport checks before sending" (`hint.not_ready`):
  - It names no numbers.
  - It says passport checks are required, contradicting DESIGN.md ("Verification remains an explicit optional action") and `hint.ready_id_optional`.
  - It hides the most common way out, "fewer people came" (lower *Expected guests*), inside the collapsed "Edit stay details". Sending is impossible while `missing > 0` (`reporting.py:316`, `sendable_statuses` at `:422`), so a no-show can make the host miss the 3-working-day deadline.
- [medium] **A rejected stay's primary is Send.** Stay #12 reads "1 guest record(s) ready to report." with primary **Send to UbyPort**, while the stay pill says "Rejected" and the guest card shows "Record 1: invalid document number". The page invites re-sending unchanged data. `stay.detail.cta.fix` exists but only shows when sending is disabled (`:36-37`).
- [medium] **Raw values leak into both languages:**
  - "Entered by: **guest**" on the CS page (`:241`, `{{ guest.entered_by }}`);
  - a hard-coded Czech **"Doručenka"** button in EN (`:287`);
  - "3 nights · **Reserved**" / "Manual entry" (`admin.py:969`, stored EN) as the page lede;
  - report times as raw UTC ISO strings "2026-09-24 17:37" (`:176`, `:282`, via `db.utcnow()`, no local-time filter). That's two hours off for a Prague host in summer.
- [medium] **CS terminology and grammar are off:**
  - "Národnost" (`stay.detail.guests.nationality`) means *ethnicity* in Czech. The police field and the guide use **Státní občanství**.
  - "vedoucí" for the lead guest reads as "manager"; everyday Czech is **hlavní host**.
  - "Narozen" is gendered.
  - "0 nahlášeno · 2 podléhá povinnosti" is ungrammatical ("2 … podléhají") and bureaucratic.
  - "1 záznam(ů) hostů připraveno k hlášení" uses a "(ů)" plural hack.
  - "Označit doklad zkontrolovaný" is missing "jako".
  - "Uloženo pro vaši referenci" is a calque.
  - "3 nocí" should be "3 noci" (`stays.table.nights`).
- [medium] **The page has no grouping principle** (the brief §6.C concern):
  - Status is split across three blocks (command panel → guest assignment → metrics).
  - Stay edits are split across two places (top "Edit stay details" and bottom "Stay settings").
  - Reports are a bare `<h2>` plus a table.
  - The two planned panels would be appended between Guests and Reports with nothing tying them together.
- [low] **Missing guests are invisible.** With 1 of 2 filled, only one card renders. There's no "Guest 2 — not registered yet" row to act on.
- [low] **"Staying 23.09 – 26.09" repeats** on every guest card even when it equals the booking dates.
- [low] **Coral buttons in table rows** ("Doručenka", `btn small primary`) put one coral per row, against DESIGN.md's rule to keep row actions in the overflow menu.

**Verified insertion points for the two planned features:**
- `{% if submissions %}` is at `reservation_detail.html:274` and `<h2 id="reports">` at `:275`. Both exist exactly as PLAN_POPLATEK §11.2 ("directly before `{% if submissions %}`") and PLAN_GUEST_INVOICE §3.5 ("directly after `#stay-fee` … else directly before `{% if submissions %}`") describe.
- `reservation`, `apartment` and `progress` are all in the route context (`admin.py:1049-1097`), as §11.1 assumes.
- The existing guest cards end at `:272`, so "after the guest cards" (§1.1 H3) and "before `{% if submissions %}`" are the same slot.

**Dumbproof score (1–5):** 2. The "Next step" command panel is the right idea, but on three common states (reported, cancelled, incomplete) it says the wrong thing, and the page has no structure to absorb two more panels.

**Fix recommendation.** Adopt one explicit, ordered page grammar. Every future panel joins a group; none gets appended bare.

| # | Group (section id) | Answers | Contents |
|---|---|---|---|
| 0 | Header + **state banner** | "Is this stay live?" | For `status != 'active'` or `archived_at`, a `.banner` directly under the header. Hide Copy-link and the deadline metric. EN "This stay is cancelled — UbyHost sends nothing for it. If that's a mistake, set it back to Active in Stay settings." / CS "Tento pobyt je zrušený — UbyHost za něj nic neodesílá. Pokud jde o omyl, v Nastavení pobytu ho vraťte na Aktivní." For ignored: EN "Marked as not a guest stay — hidden from daily work." / CS "Označeno, že nejde o pobyt hostů — skryto z denní práce." |
| 1 | **Now** (`#now`): merge `.stay-command-panel` and `.detail-hero` | "What do I do next?" | One sentence, one coral button, and a compact 3-fact strip: deadline · forms x/y · reporting pill. |
| 2 | **Guests** (`#guests`) | "Who is staying and are they registered?" | The guest-assignment line (moved here from its own panel), the guest cards, and placeholder rows for missing guests: EN "Guest %(n)s — not registered yet" / CS "Host č. %(n)s — zatím neregistrován", with "Copy link" / "Add by hand". |
| 3 | **Payments** (`#money`, rendered only if any child renders) | "Is money settled?" | `#stay-fee` (PLAN_POPLATEK §11.2) then `#invoice` (PLAN_GUEST_INVOICE §3.5), in that order. Heading EN "Payments" / CS "Platby". |
| 4 | **Police reporting** (`#reports`) | "Is the police side done?" | The existing reports table, with the receipt download moved into the row ⋯ menu. Button label key `reports.receipt` (EN "Receipt (Doručenka)" / CS "Doručenka"). |
| 5 | **Stay settings** (collapsed) | "Change the booking itself" | One `<details>` merging the quick-edit (label, expected guests) and the settings form (e-mail, state, note). |

The two plans keep their anchor: the `#money` wrapper sits exactly where both plans insert today (between `:272` and `:274`). Ship this regrouping **before** PLAN_POPLATEK step 11, so §11.2's "insert before `{% if submissions %}`" becomes "insert inside `#money`" with a one-line note in both plans.

**Next-step copy** (new `send_hint_key` values in `reporting.send_controls`, EN and CS):
- `hint.all_reported` (status `reported`): EN "All guests are reported — nothing left to send." / CS "Všichni hosté jsou nahlášení — už není co odeslat."
- `hint.nothing_duty` (`not_required`, rewrite): EN "Only Czech guests on this stay — nothing goes to the police." / CS "Na pobytu jsou jen čeští hosté — policii se nic nehlásí."
- `hint.missing_guests` (status `incomplete` with `missing`): EN "Guest forms: %(filled)s/%(expected)s. Send the link to the others, add them yourself, or lower the guest count if fewer came." / CS "Formuláře hostů: %(filled)s/%(expected)s. Pošlete ostatním odkaz, zadejte je sami, nebo snižte počet hostů, pokud jich přijelo méně." Add the inline link EN "Change guest count" / CS "Změnit počet hostů", which opens the settings `<details>`.
- `hint.not_ready` (rewrite, no passport requirement): EN "Some guest details or signatures are missing — see the guests marked below." / CS "Některým hostům chybí údaje nebo podpis — viz označené hosty níže."
- `failed`: the eyebrow text becomes EN "UbyPort rejected a guest record. Fix the details marked in red below, then send again." / CS "UbyPort odmítl záznam hosta. Opravte údaje označené červeně níže a odešlete znovu." The button label becomes EN "Send again" / CS "Odeslat znovu". It's not coral until a rejected guest has been edited since the rejection, compared on `updated_at > submitted_at`.
- `stay.detail.ready_count`: drop "(s)/(ů)". EN "Ready to report: %(count)s guests." / CS "Připraveno k hlášení — hostů: %(count)s."

**Labels:**
- `stay.detail.guests.nationality`: CS "Státní občanství" (EN "Citizenship");
- `.lead`: CS "hlavní host" (EN "main guest");
- `.born`: CS "Datum narození" (EN "Date of birth");
- `.entered_by` values translated through new keys `stay.detail.guests.entered_by.guest|host|import`: EN "Guest" / "You" / "Import", CS "Host" / "Vy" / "Import";
- `stay.detail.metric.guests_note`: EN "Reported %(sent)s of %(reportable)s foreign guests" / CS "Nahlášeno %(sent)s z %(reportable)s cizinců";
- `stay.detail.settings.email_hint`: CS "Jen pro vaši informaci. …".
- Timestamps get a `datetime_local` filter (Europe/Prague) in `templating.py`, used for `submitted_at`, `created_at` and `last_sync`.

---

### C → Stays list (`reservations.html`, `routes/admin.py::reservations_list`, `reservation_create`)

**Job of this screen:** find any stay quickly, add a direct booking, and send everything that's ready.

**Current flow:**
1. **Header:** "Send all ready stays (N)" (coral when N > 0, disabled otherwise) and "Add stay", which opens the inline panel: property, arrival, departure, guests, label, e-mail, "Create stay".
2. **Toolbar:** range chips (Upcoming & current / Past / All dates / Archive) and a List/Timeline switch.
3. **Filter panel:** Apartment, Stay state, from/to dates, coral **Apply**, Clear, Save this view, Export stays (CSV).
4. **Table:** Stay (dates, nights, "In house") · Apartment · Source · Guests x/y · Reporting pill · Deadline · actions (Send, Copy guest link, ⋯).
5. **Empty states:**
   - no apartments: "There are no apartments yet, so there is nothing to show." with **"Add your first apartment"** (coral) and "Explore with demo data";
   - no stays: "No stays yet. Connect a calendar to an apartment, or use Add stay above." with "Go to apartments".

**Friction found:**
- [high] **Double-submitting "Create stay" returns a 500.** Reproduced: two identical POSTs to `/reservations` within one second fail with `sqlite3.IntegrityError: UNIQUE constraint failed: reservation.apartment_id, reservation.uid`. The cause is `uid = f"manual-{db.utcnow()}-{date_from}"`, which has one-second resolution (`admin.py:966`). A double-click or impatient re-click shows a server error after the stay was in fact created.
- [medium] **Raw DB status in the pill.** Cancelled or ignored stays show `<span class="pill grey">cancelled</span>` untranslated (`reservations.html:160`), confirmed on the CS render. Stored "Manual entry" (`admin.py:969`) and iCal "Reserved" appear in the Source column in both languages.
- [medium] **CS plural bug on every row:** "3 nocí", "4 nocí", "2 nocí" (`stays.table.nights` = "%(count)s nocí"). EN would print "1 nights". `alerts._plural_key` already implements one/few/many and isn't reused.
- [medium] **"Apartment" vs "Property" in EN.** The filter, column and empty state say "Apartment" / "Add your first apartment" / "Go to apartments", while nav, header and form say "Property" / "Add a property". CS is consistent ("Ubytování").
- [medium] **An empty workspace still shows the full toolbar**: disabled Send all, the chips, the whole filter panel and CSV export, above a one-line empty state. The one next step sits at the bottom.
- [low] **The filter's "Apply" is coral** (`btn primary filter-apply`, `:117`) and competes with the header primary. The form already auto-submits (`data-auto-submit`).
- [low] **Error flashes from this page are EN-only**: "The departure date must be after the arrival date.", "No stays were ready to send. Complete guest forms for foreign nationals first." (see the cross-cutting section).

**Dumbproof score (1–5):** 3. Fast, filterable and well labelled, but the 500 on double-submit and the raw-value leaks break trust.

**Fix recommendation:**
- **Make the uid collision-proof** (`uid = f"manual-{secrets.token_hex(8)}"`). Disable the submit button on submit (`app.js`: `form.addEventListener('submit', …btn.disabled = true)`) for every `.action-panel form`.
- **Translate the status pill:** `t('stays.filter.state.' ~ reservation.status)` (keys exist: `stays.filter.state.cancelled/ignored`). Store `summary` as NULL for manual stays and render `t('stays.source.manual')`: EN "Direct booking" / CS "Přímá rezervace".
- **Plurals:** add `stays.table.nights.one/.few`. EN "%(count)s night" / "%(count)s nights"; CS "%(count)s noc" / "%(count)s noci" / "%(count)s nocí". Pick with `_plural_key`, moved into `host_i18n` and exposed as a `tp()` template global.
- **EN wording:** change `stays.filter.apartment`, `stays.table.apartment`, `stays.empty.*` to "Property" / "Add your first property" / "Go to properties".
- **Empty workspace:** when `not apartments`, render only the empty state (no toolbar or filters). When apartments exist but there are no stays and a feed is present, show one CTA; without a feed, show "Connect a calendar" → `/apartments/{first}#calendars` (EN "Connect a calendar" / CS "Připojit kalendář").
- **Apply button:** make it `btn` (neutral).

---

### C → Guest links (`guest_links.html`, `routes/admin.py::guest_links`)

**Job of this screen:** copy the one link, PIN and message to paste into every booking portal.

**Current flow:** For each property there is a card: name plus a "Ready" (green) or "N setup items" (amber) pill; the permanent link with copy; the PIN with copy; an open "Suggested portal message" `<pre>` with **coral "Copy message"**; "Property setup"; and ⋯ (Set your own PIN, Generate a new PIN (confirm), Generate a new link (confirm)). The empty state is "No properties…" with "Add a property".

**Friction found:**
- [high] **The portal message comes only in the host's UI language.** `guest_links.message` renders with the host's language. A Czech host, the target user, copies a **Czech-only** message ("Vážení hosté, český zákon vyžaduje…") into Airbnb and Booking, whose guests are the foreign nationals who must register. The primary action of this page produces the wrong-language invitation for most of its readers.
- [medium] **No "Preview as guest".** Onboarding step 5 says "Preview exactly what guests see" and the finish card has "Preview guest page", but this page, where the link actually lives, has no preview link.
- [low] **The same concept (setup incomplete) is amber here but red elsewhere:** amber "N setup items" here, red "N to fix" on Properties and Automation (`apartments.html:49`, `automation.html:19`).
- [low] **The regenerate flashes land here** even when triggered from the property page, and one carries the PIN in the URL (see chrome).

**Dumbproof score (1–5):** 4. There's one clear primary per card and confirms on destructive actions, but the invitation's language is wrong for most readers.

**Fix recommendation:**
- **Make the message bilingual regardless of UI language.** English first, then Czech, separated by a blank line. Build it from both `STRINGS['en']` and `STRINGS['cs']` via a new `guest_links.message_bilingual` helper.
- Also offer a second, quiet "Copy English only" / "Kopírovat jen anglicky" in the ⋯ menu.
- Copy lede under the summary: EN "Guests from abroad read the English part; the form itself opens in their language." / CS "Zahraniční hosté si přečtou anglickou část; samotný formulář se otevře v jejich jazyce." Confirm the second clause against surface A before shipping.
- **Add a preview:** a quiet link EN "Preview as a guest" / CS "Zobrazit jako host" → `/l/{token}` (new tab), next to "Property setup".
- **Colour:** use one tone for "setup incomplete" everywhere, amber, since the guest link still works (see the status table).

---

### C → Property form (`apartment_form.html`, `routes/admin.py::apartment_new/apartment_detail/apartment_update/test_connection`)

**Job of this screen:** enter everything one property needs, and above all tell a new host the few things they must set before a guest can be invited, as distinct from what's needed to report.

**Current flow (rendered for a bare, just-created property; EN and CS):**
1. Onboarding banner, breadcrumb, header "My flat" with the lede "Complete the sections below so guest registration and UbyPort reporting work reliably."
2. **Section nav** (`:30-42`): 1. Property · 2. Address · **3. Automation & UbyPort** (in editing mode this links **off-page** to `/automation`) · 4. Guest link · 5. Calendars.
3. **Blocking banner** (`:44-54`): "This apartment cannot report to UbyPort yet." followed by the 8 issue messages **run together in one `<small>`**, not linked.
4. **Basic details:** name; city (optional); operator entity; "PM is also controller" checkbox; alternate controller; Active.
5. **Address:** okres, obec, část obce (opt), street (opt), č.p., č.o. (opt), PSČ.
6. **UbyPort web-service credentials** (`:134-210`):
   - an intro paragraph;
   - the sample-PDF button;
   - "Where each UbyHost field comes from (read this once)", a 6-row table;
   - the mismatch paragraph;
   - 6 fields, each with a hint **repeating** the table;
   - then **Test the connection** and **Refresh code lists** (`type=submit formaction=…`), with the note "Both use the saved credentials, so save first."
7. **Automation summary** (editing), with "Send timing, UbyPort credentials, and the default purpose … are configured on the Automation & UbyPort page". That's wrong for credentials, which sit just above.
8. **Guest links:**
   - the message textarea;
   - "There is exactly one link…";
   - link and copy, PIN (required, pattern), window days, reachback days, passport policy;
   - the suggested portal message;
   - Generate new link / new PIN / Archive (all `type=submit formaction` with `data-confirm`).
9. **Private notes**, then **Save changes** and "Back to apartments".
10. **Calendars** (separate forms below Save): the feed table (Remove with confirm) and "Connect a calendar" (URL, Portal, Your name) with "Add and sync".

**Friction found:**
- [high] **Pressing Enter in any field runs "Test the connection" and throws the edits away.**
  - In editing mode, the first submit button inside the `<form>` is "Test the connection" (`:198-200`). Save is the last one (`:370`). Verified on the rendered HTML: button order is test-connection, refresh-codelists, regenerate-link, regenerate-pin, archive, Save.
  - HTML implicit submission uses the **first** submit button. Pressing Enter in *Name*, *IDUB* or *PSČ* posts to `/apartments/{id}/test-connection`, which **ignores the form** and tests the *saved* credentials (`admin.py:766-793`), then redirects.
  - Every typed change, including the just-pasted password, is silently lost.
- [high] **"Test the connection" before saving loses the typed credentials.** A host pastes IDUB, login and password from the police PDF and naturally clicks *Test the connection*. The typed values are discarded and the test runs against empty saved values. The warning "Both use the saved credentials, so save first." is a muted hint **after** the buttons.
- [high] **"The three things I must set before I can invite a guest" can't be found.** The brief hypothesis is confirmed:
  - The form has no required-vs-optional split for reporting. Required police fields carry no marker, only optional ones say "(optional)", and none has `required`.
  - The blocking banner says the property "cannot report" but not that **guests can already register**. For inviting guests, only a name, an operator with contact and some stays matter; the link and PIN are generated automatically.
  - The 8 issue messages are one unlinked paragraph, in English even on the CS page (see the cross-cutting section).
- [medium] **UbyPort credentials are editable in two places with different help text** (`apartment_form.html#ubyport` and `/automation`). The section nav's "3. Automation & UbyPort" jumps to the *other* page while the credentials panel is right here. The automation panel text claims credentials live on the Automation page.
- [medium] **New properties default to Delayed sending with 24 h** (`:242`), contradicting onboarding's "Start with Manual if unsure".
  - The new-property lede `apartment.form.automation.new_lede` is bureaucratic: "The operating rules let you pick how much the app does on its own, and require that the choice is yours."
- [medium] **The help is duplicated and long.** The field-origin table and the per-field hints say the same thing twice (≈ 30 lines). The explanations are good, but a first-time host scrolls through about 9 screens before reaching Save.
- [low] **Dangerous and maintenance buttons live inside the save form** (regenerate link or PIN, archive, test, refresh). They're data-confirmed, but they make Enter-submission and focus order fragile.
- [low] **The permalink read-only input has no label** (`:278`; html5lib scan).
- [low] **Informal EN:** "…which is all the app needs to start chasing the data" (`apartment.form.calendars.lede`).

**Dumbproof score (1–5):** 2. Rich, accurate guidance, but two data-loss paths on the primary setup task, and no visible "what's required to invite versus to report".

**Fix recommendation:**
1. **Stop the Enter-key and Test-connection data loss:**
   - Move the Test and Refresh buttons **out** of the main `<form>` into their own small `<form>`s below the credentials panel, or keep them but give the main form a hidden first submit, `<button type="submit" hidden tabindex="-1">`, placed right after `<form>` so Enter always saves.
   - Make `test_connection` **save first** when the posted form carries credential fields: call `apartment_update`'s payload path, then test. Relabel the button EN "Save and test connection" / CS "Uložit a otestovat spojení".
2. **Add a readiness checklist at the top**, replacing the red run-on banner. It has two short lists, each item a link to its field anchor:
   - EN "**Ready to invite guests**" / CS "**Připraveno pro hosty**": ✓ Name · ✓ Operator with contact e-mail · ✓ Stays arriving (calendar or manual). When all ✓: EN "You can send the guest link now." / CS "Odkaz pro hosty už můžete poslat." plus "Copy guest link" / "Kopírovat odkaz".
   - EN "**Ready to report to the police**" / CS "**Připraveno k hlášení policii**": IDUB · Facility abbreviation · Facility name · House number · Postcode · Municipality · Web-service login · Password. Missing items render as links: EN "Missing: …" / CS "Chybí: …".
   - Mark the 8 reporting fields with a small EN "needed to report" / CS "nutné pro hlášení" tag instead of tagging only the optional ones.
3. **Fix the section nav:** in editing mode, "3." becomes EN "Police reporting" / CS "Hlášení policii" → `#ubyport`. The automation summary panel text becomes EN "Send timing and default purpose are set on the Automation page." / CS "Časování odesílání a výchozí účel pobytu nastavíte na stránce Automatizace."
4. **Default Manual** for new properties. Rewrite `apartment.form.automation.new_lede`: EN "Choose when UbyHost may send finished guest records to the police. You can change this any time." / CS "Zvolte, kdy smí UbyHost hotové záznamy hostů odeslat policii. Změnit to můžete kdykoli."
5. **Collapse the duplicated help:** keep the per-field hints and put the "Where each field comes from" table behind the sample-PDF link, collapsed, which it already is. Delete `apartment.form.ubyport.mismatch_help`'s repeat of the table.
6. **Planned-feature room** (see the backlog "conflicts" column):
   - PLAN_POPLATEK §7.2 adds its own `#stay-fee-settings` panel before Notes.
   - PLAN_GUEST_INVOICE §3.5 says the invoice toggle goes "in the `#communication` panel directly after the stay-fee settings block (after the `stay_fee_cash` checkbox)", but the stay-fee block isn't in `#communication`. That's a conflict.
   - Recommend one **"Payments" / "Platby"** panel (`#payments`) holding the stay-fee inputs, then the invoice toggle, with section-nav label EN "Payments" / CS "Platby". This mirrors the stay page's `#money` group.

---

### C → Properties list (`apartments.html`)

**Job of this screen:** see every property's setup health and open one.

**Current flow:**
- **Header:** "Update calendars" (with icon), "Legal entities", coral "Add a property" (no icon).
- **Table:** Property · Legal entity · IDUB · Calendars · Stays · Automation (blue or grey pill) · Setup (red "N to fix" / amber "Add calendar" / green "Ready") · ⋯ (Edit, Guest links, Automation & UbyPort → `#ubyport`, Archive with confirm).
- **Empty state:** "No properties yet. Add the legal entity that operates them first, then create a property." with "Add a legal entity" (neutral) and **"Add your first property" (coral)**.

**Friction found:**
- [medium] **The empty state contradicts itself.** The text says "add the legal entity first", but the coral button is "Add your first property". With the onboarding banner ("Add legal entity", coral) and the header ("Add a property", coral), a new host sees **three coral buttons naming two different first steps**.
- [low] **Two coloured chip columns plus an "Inactive" chip per row.** DESIGN.md says "do not crowd tables with many colored chips". Automation mode doesn't need colour.
- [low] **DESIGN.md asks for the coral page-header CTA "with an icon"** for frequent actions like add property. "Add a property" has no icon, while the secondary "Update calendars" does.

**Dumbproof score (1–5):** 3. A clear table, but the empty state names two conflicting first steps.

**Fix recommendation:**
- **Empty state:** if no entity, one coral "Add operator" / "Přidat provozovatele" and the text EN "First add who operates the property. Then you can add the property itself." / CS "Nejdřív přidejte, kdo ubytování provozuje. Potom přidáte samotné ubytování." If an entity exists, one coral "Add your first property".
- **Header:** hide "Add a property" while the empty state is showing.
- **Chips:** render Automation as plain text (`small muted`) and keep one Setup pill.
- **Icons:** add the `property` nav icon inside "Add a property" (same markup as `sync-btn-icon`).

---

### C → Host guest form: add or edit a guest by hand (`guest_form_admin.html`, `routes/admin.py::guest_new/guest_edit/guest_update/guest_verify_identity`)

**Job of this screen:** type in or correct one guest's police-report data, most often to fix a rejection.

**Current flow:**
1. Breadcrumb and header "Edit guest" with the stay.
2. A red banner if rejected ("…" plus `last_errors` plus help), or a blue banner if already sent.
3. The main `<form action="/guests/{id}">` (`:46`): identity, residence, stay, note.
4. **When editing an unverified foreign guest**, the verify panel (`:165-183`) contains **its own `<form action="/guests/{id}/verify-identity">`** (`:178-182`).
5. Signature pad, then **Save changes** / Cancel / PDF (`:213-219`), and `</form>` (`:220`).
6. A collapsed danger zone: Re-send (checkbox) and Delete (confirm).

**Friction found:**
- [blocker] **A nested `<form>` breaks Save on the most common edit.** An HTML parser ignores a `<form>` start tag inside an open form, and the inner `</form>` (`:182`) closes the **outer** one. I checked this with a spec-compliant parse of the rendered `/guests/1` (Italian guest, ID not checked):
  - The `/guests/1` form contains the fields up to the verify panel, plus **one** submit button, "Mark ID checked". Clicking it **saves the guest** instead of recording the ID check.
  - **"Save changes", the hidden `signature` input and the signature pad end up outside any form.** Save does nothing.
  - This hits exactly the path a host takes to fix a UbyPort rejection for a foreign guest: foreign, not yet ID-checked, open "Edit details", correct the document number, press Save. Nothing happens and there's no message. It's a primary-task dead end.
  - Tests post to the endpoints directly, so they can't catch it. Only `demo_guest_edit` among 60 rendered pages had the raw-form count differ from the parsed count.
- [medium] **Validation messages are English on the CS page.** `err_for()` prints `issue.message` from `validation.py` untranslated (`:7-9`). The guest side already has a CS translator (`routes/guest.py:304-321`, `CS_VALIDATION_MESSAGES`) that the host side doesn't use.
- [low] **Raw timestamps:** "Sent at 2026-09-24 17:37" is raw UTC (`:37`).

**Dumbproof score (1–5):** 1. The main action is dead for unverified foreign guests.

**Fix recommendation:**
- **Move the verify form out of the main form.** Render the verify panel's `<form id="verify-{{ guest.id }}" …></form>` **after** `</form>` (`:220`), and give the button inside the panel `form="verify-{{ guest.id }}"`. The layout stays the same and the nesting goes away.
- **Add a regression test** in `tests/test_host_guest_form.py`: render `/guests/{id}` for an unverified foreign guest, assert `html.count('<form')` equals the number of `</form>`, and that no `<form` occurs between the main form's open and close.
- **Localise issues on the host side:** reuse `routes.guest._localize_issues(issues, lang)` in `_render_host_guest_form` and `reservation_detail` (`row.issues`). Better, move the table to a shared module (see the cross-cutting section).

---

### C → Reports list and report detail (`submissions.html`, `submission_detail.html`)

**Job of this screen:** prove what was sent to the police, and understand and fix a rejection.

**Current flow:**
- **List:** header "Reports" with "Every UbyPort transmission and its Doručenka, retained as proof.", then "Download receipts (ZIP)" plus the hint "One PDF per successful transmission, built on disk to stay lightweight."
  - Table: When (raw UTC) · Property · Mode (**raw `submission.mode | capitalize`**, "Manual" on CS) · Guests · Outcome pill · Stamp · coral "Doručenka" plus "Details".
- **Detail:** breadcrumb and header "Report #2 · Karlín Loft · 2026-09-24 17:37:07 · sent manually".
  - A key-value panel: Outcome, **Endpoint**, Stamp, Finished.
  - A transport-error banner, header problems plus the help "Header errors come from the property settings, not the guest data.", and the guests table (result pill and errors).
  - Collapsed "Technical details" (XML).

**Friction found:**
- [medium] **No way from a report back to its stay,** where the fix and re-send happen. Header help says errors "come from the property settings" but doesn't link to that property's `#ubyport`.
- [medium] **Rejection text is English and points to a document that doesn't exist.** "12: UbyPort error 12 (see the Doručenka for details)" appears on the CS page (from `ubyport/errors.describe` when the code list isn't cached). A rejected report has **no** Doručenka, only an error PDF.
- [low] **Raw and technical values on the host surface:** "Mode: Manual" in CS; "Endpoint: None" or a URL in the main panel; nationality as "FRA"; "built on disk to stay lightweight" is an implementation detail.
- [low] **A transport error shows an empty "Guests in this transmission" table** with no message.

**Dumbproof score (1–5):** 3. It's honest proof, and the technical XML is correctly tucked away, but a rejected report doesn't lead the host to the fix.

**Fix recommendation:**
- **Next step for rejections:** on the detail page, when the outcome is rejected, add a coral "Open the stay to fix" / "Otevřít pobyt a opravit" button → `/reservations/{reservation_id}#guests`. Derive the id from the first guest. Header-error help gets a link EN "Open property reporting details" / CS "Otevřít údaje pro hlášení".
- **Error text:** `describe()` fallback becomes EN "UbyPort error %(code)s — refresh code lists on the property page to see the explanation." / CS "Chyba UbyPortu %(code)s — vysvětlení uvidíte po obnovení číselníků na stránce ubytování." It must not mention a Doručenka.
- **Mode column:** use `t('reports.mode.' ~ submission.mode)` in the list, as the detail already does.
- **Endpoint:** move it into Technical details.
- **Nationality:** print `country_name()`.
- **`reports.download_receipts_hint`:** EN "One PDF receipt per accepted report." / CS "Jedna PDF doručenka za každé přijaté hlášení."
- **Empty transport-error table:** EN "Nothing reached UbyPort, so no guest was processed." / CS "Do UbyPortu nic nedorazilo, žádný host nebyl zpracován."

---

### C → Automation & UbyPort (`automation.html`)

**Job of this screen:** choose when each property sends, and keep its web-service credentials current.

**Current flow:** For each property there is a panel: name plus a red "N to fix" or green "Ready" pill; timing select plus hours; default purpose; credentials (IDUB, mark, name, contact, login, password); then Save (coral, first), Test, Refresh, and "Full property setup".

**Friction found:**
- [high] **"N to fix" lists nothing,** and some of the items (address) aren't on this page, so the onboarding step 4 loop can't be finished here (see first run).
- [low] **Test and Refresh ignore the typed values,** as on the property form. Here Save is the first submit, so Enter is safe.

**Dumbproof score (1–5):** 3. It's a clean per-property form, but the red pill is a dead end.

**Fix recommendation:**
- **List the missing items:** replace the count pill with EN "Still missing: IDUB, house number" / CS "Ještě chybí: IDUB, číslo popisné", each linking to `/apartments/{id}#{field}`. Field labels come from `apartment.form.*`.
- **Save before testing:** the same fix as the property form ("Save and test").

---

### C → Legal entities (`entities.html`)

**Job of this screen:** record who operates each property, which is also the contact shown to guests.

**Current flow:** Breadcrumb, header, onboarding banner, then the explainer. On the left, the table: Name · Seat · IČO · Contact (amber "Missing" if no e-mail) · Properties · ⋯ (Archive with confirm, only when there are 0 properties); on the right, the "Add a legal entity" form. Archived entities are listed with Restore and Delete (confirm).

**Friction found:**
- [medium] **Field requirements are hidden.** The fields the onboarding step needs aren't marked, and saving with a name only succeeds silently.
- [medium] **CS "Právnické osoby" / "Právnická osoba"** excludes sole traders (see first run).
- [low] **The edit panel opens above the table via `?edit=`,** with its own Save. Two primaries appear when editing (edit Save plus add form).

**Dumbproof score (1–5):** 3.

**Fix recommendation:**
- Mark seat, IČO and e-mail `required`, with the hint EN "Shown to guests as your contact." / CS "Hostům se zobrazí jako váš kontakt." on e-mail.
- Rename to *Operators* / *Provozovatelé* in all host strings.
- While editing, collapse the add form into a "+ Add another operator" / "+ Přidat dalšího provozovatele" disclosure.

---

### C → House book, Settings, Archive, Users, Help (rarely visited; compact)

**House book** (`housebook.html`)
- **Job:** the legal register and export. **Flow:** filters, then Export ▾ (CSV, PDF bundle), then a wide table with ⋯ (Edit, PDF, Archive with confirm).
- **Friction:**
  - [low] nationality shows as a code ("DEU") while the residence line spells the country;
  - [low] "Narozen" / "Národnost" as in stay detail (CS "Datum narození" / "Státní občanství").
- **Score:** 4.
- **Fix:** labels as in stay detail.

**Settings** (`settings.html`)
- **Job:** status, data protection, account. **Flow:** section nav with 9 anchors; "Where reports go" (Deployment, target, **Endpoint**, poll intervals, public base URL); guest e-mails (the console outbox with full claim links on staging); PIN access ("The server setting UBYHOST_GUEST_PIN controls…"); code lists; archive link; retention purge (confirm ✓); activity log; operator with **support e-mail ✓** (`:220-223`); account; version.
- **Friction:**
  - [medium] operator and developer diagnostics (env var names, endpoints, poll intervals, "Mail backend: console") are addressed to every host;
  - [low] "Delete 0 expired record(s)" uses a "(s)" plural;
  - [low] the purge flash joins parts with the English " and " in CS (`exports.py:375`).
- **Score:** 3.
- **Fix:**
  - Gate "Where reports go", "Guest e-mails" and "Code lists" behind `current_user.role == 'admin'`, or one collapsed EN "Technical details" / CS "Technické údaje" `<details>`.
  - Translate the joiner: EN " and " / CS " a ".

**Archive hub** (`settings_archived.html`)
- **Job:** restore anything. **Flow:** tabs with counts, then per-type tables with Restore.
- **Friction:** none material; restore is non-destructive, so no confirm is needed. ✓
- **Score:** 4.
- **Fix:** no change needed.

**Users** (`users.html`, admin)
- **Job:** create or disable host workspaces.
- **Friction:**
  - [low] **Disable user has no `data-confirm`** (`:55-57`), while every other destructive toggle has one;
  - [low] "Hesla jsou hashována" / "hashed" is jargon for a host admin.
- **Score:** 4.
- **Fix:**
  - `data-confirm data-confirm-message` with EN "Disable %(name)s? They can't sign in until you enable them again." / CS "Vypnout účet %(name)s? Nebude se moci přihlásit, dokud ho znovu nezapnete."
  - Lede EN "Passwords are stored securely and can only be reset, never viewed." / CS "Hesla jsou bezpečně uložená — lze je jen resetovat, nikdy zobrazit."

**Help** (`guide.html`)
- **Job:** a self-serve manual.
- **Friction:**
  - [low] **CS terminology drifts** from the UI: "značka" (the UI says "zkratka"), "Permalink" (the UI says "odkaz pro hosty"), "vedoucí host";
  - [low] "Karta Další na řadě" refers to the focus card; that's correct.
- **Score:** 4.
- **Fix:** align the CS nouns with the UI ("zkratka", "odkaz pro hosty", "hlavní host").

---

### C → Cross-cutting: flash and confirmation messages (`routes/admin.py`, `routes/onboarding.py`, `routes/exports.py`, `host_i18n.py flash.*`)

**Job:** after every host action, say what happened **and** what's next.

**Current flow:** these are the redirect messages I captured from real POSTs.

| Action | EN (msg/err) | CS | Verdict |
|---|---|---|---|
| Create operator (first) | "Added X. Next, add your first property." | "Přidáno: X. Nyní přidejte první ubytování." | ✓ what + next |
| Create property | "Property created. Next, paste your Airbnb or Booking.com calendar link." | ✓ | ✓ |
| Create stay | "Stay created." | "Pobyt byl vytvořen." | what only |
| Save stay / property / guest / entity | "Saved." | "Uloženo." | what only |
| Sync | "Synced 2 calendar(s): 0 new, …" and err "Some calendars could not be read." | "Synchronizováno **1 kalendářů**…" and **EN err** | plural bug, EN leak |
| Test connection | "UbyPort reachable at %(endpoint)s (available=True, max batch 50)" | "…(dostupnost=True…)" | developer text |
| Regenerate PIN | "New PIN generated: 300424" | ✓ | secret in URL |
| Release claim | "Guest claim released." | "**Nárokování hosta** bylo uvolněno." | calque; UI says "Uvolnit přiřazení" |
| Submit incomplete | err "Complete guest details, signatures, and passport checks before sending" | ✓ CS | contradicts optional ID check |
| Send all, none ready | err "No stays were ready to send. …" | **EN** | EN leak |
| Add stay, bad dates | err "The departure date must be after the arrival date." | **EN** | EN leak (and the date inputs could prevent it) |
| Operator without name / property without name / bad calendar URL | "Name is required." / "Give the apartment a name." / "Calendar URL must use http:// or https://." | **EN** | EN leak |

**Friction found:**
- [high] **About 80 `err="…"` / `err=f"…"` literals in `routes/admin.py` (71), `routes/exports.py` (7), `routes/admin_accounts.py` (3) and `routes/onboarding.py` (2), are English-only.** A Czech host gets English errors at exactly the moment they're stuck. Examples: `admin.py:251,460,956,960,1029,1257,1276,1280-1291`, and "…open the Doručenka for details" at `:1291` for a *rejection*, which has no Doručenka. The validation-issue sentences are also EN-only (`validation.py`, 45 `Issue(...)` messages) and appear in the property banner, the host guest form and stay-detail guest cards.
- [medium] **"Saved." carries no next step.** Stay settings, property, guest and operator saves all say only "Saved.", and the stay-fee plan copies this literally (`msg="Saved."`, PLAN_POPLATEK §11.3). That's another EN literal.
- [medium] **"(s)" / "(ů)" plural hacks** appear in `flash.feeds.*`, `flash.reservations.*`, `stay.detail.ready_count`, "Delete 0 expired record(s)", and in CS "Importováno 1 pobytů" / "1 kalendářů".

**Fix recommendation:**
- **Route every `err=` and `msg=` through `_flash(request, key)`,** with new `flash.error.*` keys in both languages. Examples:
  - `flash.error.no_such_stay`: EN "This stay no longer exists." / CS "Tento pobyt už neexistuje.";
  - `flash.error.dates_order`: EN "Departure must be after arrival." / CS "Odjezd musí být po příjezdu.";
  - `flash.error.nothing_ready`: EN "Nothing is ready to send yet — open a stay to see what's missing." / CS "Zatím není nic připraveno k odeslání — otevřete pobyt a uvidíte, co chybí.";
  - `flash.error.name_required`: EN "Please enter a name." / CS "Vyplňte prosím název.";
  - `flash.error.rejected`: EN "UbyPort rejected %(count)s guest record(s) — open the stay to fix and resend." / CS "UbyPort odmítl záznamy hostů (%(count)s) — otevřete pobyt, opravte je a odešlete znovu.";
  - `flash.error.feeds_unreadable`: EN "Some calendars couldn't be read — see the alert on the property." / CS "Některé kalendáře nešly načíst — podrobnosti najdete u ubytování."
  - Add a test that greps `routes/*.py` for `err="` / `msg="` string literals.
- **Share validation translation:** move `CS_VALIDATION_MESSAGES` from `routes/guest.py` into a shared module and add the apartment messages to it. For example, "IDUB is required before anything can be reported." becomes CS "Bez IDUB nelze nic nahlásit."; "House number is required." becomes "Vyplňte číslo popisné."; "Postcode is required." becomes "Vyplňte PSČ." Apply it on host renders.
- **Replace "Saved." with what + next:**
  - `flash.reservations.saved`: EN "Stay saved." / CS "Pobyt uložen.";
  - `flash.reservations.created`: EN "Stay created. Next, copy the guest link or add guests yourself." / CS "Pobyt vytvořen. Teď zkopírujte odkaz pro hosty, nebo hosty zadejte sami.";
  - `flash.guests.saved`: EN "Guest saved. %(filled)s of %(expected)s forms are complete." / CS "Host uložen. Hotové formuláře: %(filled)s/%(expected)s.";
  - `flash.apartments.saved` (when issues remain): EN "Saved. Still missing for police reporting: %(fields)s." / CS "Uloženo. Pro hlášení policii ještě chybí: %(fields)s." (when none remain): EN "Saved. This property is ready to report." / CS "Uloženo. Ubytování je připravené k hlášení.";
  - stay-fee (for the plan): `stay.fee.saved` EN "Stay fee updated." / CS "Poplatek z pobytu upraven."
- **`flash.apartments.connection_ok`:** EN "Connection works — UbyPort accepted your web-service login." / CS "Spojení funguje — UbyPort přijal vaše přihlašovací údaje." Endpoint and batch size go to the activity log.
- **`flash.reservations.claim_released`:** EN "Assignment released — another e-mail can now claim this stay." / CS "Přiřazení uvolněno — pobyt teď může převzít jiný e-mail."
- **Plurals:** a `tp(key, n)` template global and `_flash_plural` built on `alerts._plural_key`, with `.one/.few` variants for the counted keys above.

---

### C → Cross-cutting: status words and colours for the same concept

| Concept | Overview / Stays list | Stay detail (stay) | Stay detail (guest card) | Reports | Property lists |
|---|---|---|---|---|---|
| Guest forms not finished | "Incomplete" **amber** / "Waiting for guest" grey | same | "Incomplete" amber | — | — |
| Complete, ID not checked | "ID not checked" **amber** | same | "ID not checked" amber | — | — |
| Ready to send | "Ready — you send" / "Ready — scheduled" **blue** | same | "Ready" blue | — | — |
| Accepted by police | "Reported" green | same | "Reported" green | "**Accepted**" green | — |
| Rejected | "Rejected" red | same | "Rejected" / "Rejected, final" red | "Rejected" / "**Not delivered**" red | — |
| No report needed | "**Exempt**" grey | same | "Exempt" grey | — | — |
| Setup incomplete | "N items to fix" (setup list, "!") | — | — | — | **red** "N to fix" (Properties, Automation) / **amber** "N setup items" (Guest links) |
| Stay cancelled | raw "cancelled" grey | nothing shown | — | — | — |

**Friction found:**
- [medium] **"ID not checked" is shown in amber, the warning colour, as the stay's reporting status.** DESIGN.md calls verification optional, and sending is enabled in that state (`hint.ready_id_optional`). Amber there reads as a problem the host must solve.
- [medium] **"Setup incomplete" is red on two pages and amber on a third.**
- [medium] **"Exempt"** collides with the stay-fee plan's "Exempt".
- [low] **"Reported" (stay) vs "Accepted" (report) is fine semantically,** but CS "Nahlášeno" vs "Přijato" should be linked, e.g. "Přijato (nahlášeno)".

**Fix recommendation:**
- **Complete but unverified:** show the stay-level pill as "Ready to report" (blue) with the secondary text EN "ID not checked (optional)" / CS "Doklad nezkontrolován (volitelné)". Keep amber for guest-card-level "Incomplete" only.
- **Setup incomplete = amber everywhere,** because guests can still register. Red is reserved for "police rejected" or "not delivered", the only states with legal consequences.
- **"Exempt" becomes "No report needed" / "Nehlásí se"** (see Overview).
- **Submission "Accepted":** CS "Přijato policií".

---

### C → Cross-cutting: destructive actions and `data-confirm`

Verified with `data-confirm`: archive stay (detail), archive guest, delete guest, release assignment, regenerate link and PIN (both pages), archive property (both), remove calendar, archive or delete operator, purge expired, clear demo, archive house-book entry.

Missing or inconsistent:
- [low] **Disable user** (`users.html:55`) has no confirm.
- [low] **Archive from a stay row** on Overview and Stays has no confirm, while the detail page has one. The row path shows an **Undo** toast (`base.html:217-226`), which is acceptable. Recommendation: keep the rows without confirm (undo is better) and **remove** the confirm on the detail archive in favour of the same undo toast, for consistency.
- [low] **Guest "Re-send to UbyPort"** is a red button guarded by a checkbox, which is acceptable, and hidden inside the collapsed danger zone ✓.

---


## Surface D — Public website

Evidence base: every page below was rendered through the real FastAPI app (`TestClient`, fresh DB, `?lang=en` and `?lang=cs`, plus a no-`lang` request). Script: `/tmp/uby-2-audit/scratch_D/render.py`, output in `/tmp/uby-2-audit/scratch_D/out/`. Routes: `/` → `routes/admin.py:119 dashboard()` renders `landing.html` when signed out; `/cenik`, `/jak-to-funguje`, `/pruvodce/{slug}`, `/legal`, `/terms`, `/privacy`, `/dpa`, `/subprocessors` → `routes/legal.py`. CSS was traced by hand (`landing.css` is 1,520 lines: an older layout at lines 1–960 plus a "2026 public landing" override layer from line 932, so later rules win and several earlier rules still leak through).

**Repo vs brief mismatches (brief §0 rule 10):** (1) Brief §0.6 says visible focus rings come from `:focus-visible` in `tokens.css`. `tokens.css` has **no** `:focus-visible` rule. `landing.css` defines one only for `.reel-toggle` (`:1039`), so every other public link/button relies on the browser default ring. (2) LOGO.md's landing placements don't match the code: the final-CTA mark renders at 56px, not 64px (`landing.css:1245` overrides `:730`), and the product-mock mark cited as `.product-shell aside img` 28px is dead CSS; the live one is `.reel-side img` at 38px. (3) DESIGN.md's "Technical stack" list omits `landing.css`/`landing.js`, which the brief treats as first-class.

---

### D → Shared public chrome: header, nav, language switch, footer (`landing.html`, `pricing.html`, `product.html`, `public_guide.html`)

**Job of this screen:** let a prospect move between "what it is", "how it works", and "what it costs", and let an existing host log in, from any public page and on any device.

**Current flow:** A sticky header (`landing.html:64-81`, copied by hand into all four templates) shows the 152px horizontal lockup, a nav with **Product** (`#product`, the demo on the home page) / **How it works** (`/jak-to-funguje`) / **Pricing** (`/cenik`) / **UbyPort** (`/pruvodce/hlaseni-cizincu-ubyport`), a `CZ | EN` pill, and a filled coral **Log in** pill. At ≤900px `.landing-nav { display: none; }` (`landing.css:870`, again at `:1258`) and nothing replaces it. At ≤480px `.landing-login { display: none; }` (`landing.css:912`), and no later rule turns it back on. The footer is also hand-copied, and each page has a different set of links.

**Friction found:**
- [high] **No mobile navigation at all.** Below 900px the nav is `display:none` and there is no menu, `<details>`, or second row to replace it. Below 480px the **Log in** link goes too. On a phone, the header is just logo + `CZ|EN`. A host who opens `ubyhost.com` on a phone to log in has to find the hero "Try UbyHost" button (it happens to go to `/login`) or scroll to the footer. On `/cenik`, the footer has **no login link at all** (`pricing.html:108-114`), so on a phone there is no path to log in from that page. A prospect on a phone can reach Pricing only from the footer.
- [high] **Two coral primaries in the first viewport.** The header **Log in** is a filled `--brand-action` pill (`landing.css:113-121`). On desktop it sits directly above the hero's filled **Try UbyHost** (`landing.html:89`), and both go to `/login`. On `/cenik` the header pill competes with **Ask about pricing**. Lens 1 fails: two buttons of equal weight.
- [medium] **Nav labels don't match what they open.** "Product" jumps to the home-page demo. "How it works" opens `product.html` (whose `<title>` is "UbyPort for Airbnb and Booking.com hosts"). "UbyPort" opens *our* guide, not UbyPort. The same page (`/jak-to-funguje`) has three names: "How it works" (nav), "See how it works" (hero secondary), and "Product details and common questions" (`landing.details.link`). The unused key `landing.nav.guides` ("Guides"/"Průvodce") already exists.
- [medium] **Footers differ on every page.** Landing: 9 links incl. Subprocessors, both guides, Host login. Pricing: 5, with no DPA, no subprocessors, no guides, no login. Product: 6, with no subprocessors and no login. Guide: 7. A visitor can't learn one place to find things (lens 7).
- [medium] **"UbyPort" as a bare nav/footer label** (`landing.nav.faq` = "UbyPort", `landing.html:72,211`) reads as a link to the official police system. Together with no independence statement on the home page (see hero), this edges toward implying an affiliation (LOGO.md: "must not imply official endorsement").
- [low] **The language switch is small and unlabelled for assistive tech.** `.landing-languages a { padding: 5px 8px }` (`landing.css:105`) makes a tap target of about 28px, under the 44px bar. `aria-label` sits on a plain `<div>` (`landing.html:75`), which AT ignores, and the active language has no `aria-current`. The label "CZ" is a country code (it is used product-wide via `lang.cs`, so this is consistency, not a defect).
- [low] **Some copy is hard-coded in templates instead of `landing_i18n.py`,** so the parity test can't see it: `landing.html:212` (`'Guest book' if lang == 'en' else 'Ubytovací kniha'`), `product.html:114-120` (both guide cards), and the demo weekday row `('M','T','W','T','F','S','S')` (`landing.html:120`), which renders in **English on the CS page**.
- [low] The four public templates each duplicate about 55 lines of `<head>` + header + footer. The drift above (footers, canonical handling) comes straight from this duplication.

**Dumbproof score (1–5):** 2 — on a phone, the most common device for a host, there is no nav and no login, and on desktop the two strongest buttons compete.

**Fix recommendation:**
1. Extract `templates/_public_header.html` and `_public_footer.html` (Jinja includes, no new tech) and use them in all four public templates. Pass `active` and `switch_path` so `aria-current` and the language links stay correct. One footer everywhere: How it works · Pricing · Guides · Legal notice · Terms · Privacy · DPA · Subprocessors · Host login · support@ubyhost.com.
2. Nav: **How it works** (`/jak-to-funguje`) · **Pricing** (`/cenik`) · **Guides** (`/pruvodce/hlaseni-cizincu-ubyport`, key `landing.nav.guides`). Drop the "Product" anchor and the bare "UbyPort" label.
3. Mobile: below 900px, render the same three links as a horizontally scrollable second header row, or as a no-JS `<details class="landing-menu"><summary>Menu</summary>…</details>`. New keys: `landing.nav.menu` EN "Menu" / CS "Menu". Never hide **Log in**; keep it visible at every width.
4. Demote **Log in** to a quiet text link (ink-secondary, no fill, ≥44px hit area). The coral fill belongs to the page's one primary CTA only.
5. Language pill: wrap it in `<nav aria-label="{{ t('lang.switch') }}">`, add `aria-current="true"` on the active link, and give links `min-height: 44px` at ≤600px.
6. Move the hard-coded strings into `landing_i18n.py`: `landing.footer.guestbook` EN "Guest book" / CS "Ubytovací kniha"; `landing.guide.ubyport.title|kicker|meta` and `landing.guide.book.*` (EN/CS as they are today); `landing.demo.weekdays` EN "M,T,W,T,F,S,S" / CS "Po,Út,St,Čt,Pá,So,Ne".

---

### D → Landing hero (`landing.html:84-93`)

**Job of this screen:** within 5 seconds, tell a Czech short-term-rental host what UbyHost does and who it's for, and give them one next step.

**Current flow:** An eyebrow pill reads "From Airbnb booking to UbyPort receipt" / "Od rezervace z Airbnb až po doručenku z UbyPortu". Then H1 "Guests fill it in. UbyHost reports it." / "Hosté vyplní. UbyHost nahlásí." Then the lede "The online guest book for Airbnb and Booking.com hosts — with guest forms and direct foreign-guest reporting to UbyPort." Then a primary **Try UbyHost** / **Vyzkoušet UbyHost** → `/login?lang=…`, a secondary **See how it works →** / **Jak to funguje →** → `/jak-to-funguje`, and a trust line "Built for apartments, holiday rentals, and small accommodation providers in Czechia."

**Friction found:**
- [blocker] **The primary CTA leads to a dead end for a prospect.** "Try UbyHost" goes to `/login`. That page is a username/password form whose only guidance is `login.footnote`: "No public sign-up. UbyHost is invite-only — ask your administrator for an account." A prospect has no "administrator", no account, and no link to request one. "Try" also promises a trial that doesn't exist. The same CTA and target appear five times (landing hero `:89`, landing final `:198`, product hero `product.html:65`, product final `:128`, guide checklist `public_guide.html:93`). The only real conversion path is the pricing page's `mailto:`. This is lens 1 and lens 4 on the site's primary task, so it's a blocker.
- [medium] **5-second test: passes on "who", partly on "what".** For a Czech host who knows UbyPort, eyebrow + lede answer both questions. The H1, though, uses "it" twice ("fill **it** in… reports **it**") without saying what "it" is. In CS, "Hosté vyplní. UbyHost nahlásí." has no object at all. The lede then opens with "online guest book", which frames the product as a book rather than as police reporting, the job hosts actually fear. Nothing in the first viewport says the product is private and independent.
- [medium] **CTA wording across the site** (lens 7): "Try UbyHost" (×5, → login), "Log in" (header, → login), "Host login" (footer, → login), "Ask about pricing" (pricing ×2, → mailto), and "See how it works" / "Product details and common questions" (→ the same page). Three verbs lead to two different places, and the one that looks like sign-up is actually log-in.
- [medium] **The locked tagline "Guest reporting, handled for you."** (LOGO.md) appears on no public page. It only appears as `login.hero_title`, and its CS there is "Hlášení hostů bez zbytečné práce." ("guest reporting without unnecessary work"), which is a different promise, not a translation. The landing final CTA instead says "Your guest paperwork, on autopilot." / "Evidence hostů na autopilota.", a third slogan, and "autopilot" oversells a flow that can require host review (DESIGN.md "Delayed" timing).
- [low] **Hero type is set too tight for Czech diacritics:** `line-height: .94; letter-spacing: -.058em` at weight 800 (`landing.css:957-963`). On two-line CS headings, accents (é, í, á) come close to or touch the descenders of the line above. On mobile the eyebrow is a bordered pill (`landing.css:949-956`) holding a 48-character CS sentence, which wraps inside the pill.

**Dumbproof score (1–5):** 2 — the message mostly lands, but the one button a prospect presses leads to "ask your administrator".

**Fix recommendation:**
- Change the primary CTA site-wide to what's actually true (invite-only):
  - Key `landing.cta` EN **"Request access"** / CS **"Požádat o přístup"**. Target: `mailto:support@ubyhost.com?subject=…` with a localized subject via a new key `landing.cta.subject` (EN "UbyHost access request" / CS "Žádost o přístup do UbyHostu"), URL-encoded in the template.
  - Put a visible line under every such button so it works without a mail client: `landing.cta.note` EN "Or write to support@ubyhost.com — we reply with next steps." / CS "Nebo napište na support@ubyhost.com — ozveme se s dalším postupem."
  - Apply the same key at all five call sites. Pricing uses the same verb (see Pricing).
  - Dependency, surface B: `login.footnote` should then say EN "No account yet? UbyHost is invite-only — request access at support@ubyhost.com." / CS "Ještě nemáte účet? UbyHost je jen na pozvání — o přístup požádejte na support@ubyhost.com." instead of "ask your administrator".
- H1: EN **"Guests fill in their details. UbyHost reports them to UbyPort."** / CS **"Hosté vyplní údaje. UbyHost je nahlásí do UbyPortu."** Keep the eyebrow. Lede (police reporting first, book second): EN "For Airbnb and Booking.com hosts in Czechia: guests fill in and sign a private online form, and UbyHost sends foreign-guest reports to UbyPort and keeps the guest book." / CS "Pro hostitele z Airbnb a Booking.com v Česku: hosté vyplní a podepíší soukromý online formulář, UbyHost nahlásí cizince do UbyPortu a povede ubytovací knihu." Then drop the trust line, since "who" is now in the lede, or keep it as the independence line below.
- Replace the trust line with the independence statement (new key `landing.independent`): EN "UbyHost is an independent private service. It is not operated or endorsed by the Czech Police or UbyPort." / CS "UbyHost je nezávislá soukromá služba. Neprovozuje ji ani nedoporučuje Policie ČR ani UbyPort."
- Tagline: use it as the landing final-CTA title, `landing.final.title` EN **"Guest reporting, handled for you."** / CS **"Hlášení hostů vyřídíme za vás."** Align `login.hero_title` CS to the same wording (surface B, same commit if Joe agrees, or flag to B).
- CSS: hero H1 `line-height: 1.02; letter-spacing: -.04em`. At ≤600px, render the eyebrow as plain uppercase text (no pill border).

---

### D → Landing product demo reel (`landing.html:95-173`, `landing.js`)

**Job of this screen:** show, without reading, the four-step flow (booking → guest form → queue → UbyPort receipt).

**Current flow:** A fake browser window (traffic-light dots, "ubyhost.com", a 34px pause button with glyph "Ⅱ"/"▶") auto-advances through four scenes every 3,000ms (`landing.js:13,47-50`), looping forever (`(active + 1) % scenes.length`). Each scene runs keyframe animations: `booking-drop` 650ms with overshoot `cubic-bezier(.2,1.4,.4,1)`, `type-reveal` 1.1s, `sign` 900ms, `ready-flip` 700ms rotateX, `receipt-pop` and `toast-in` with overshoot (`landing.css:1102-1181`). Scene crossfade is 400–500ms. Two floating chips, "✓ Guest form" and "UbyPort ✓", hover over the frame (`landing.html:96-97`). Behind it, two 36%-wide `filter: blur(60px)` colour blobs (`landing.css:996-1010`). The caption `<p aria-live="polite">` is rewritten on every tick (`landing.js:28`).

**Friction found:**
- [medium] **Motion breaks both the brief and DESIGN.md.** It loops without end (DESIGN.md: "no looping animations"; brief §4: "never loop"). Durations run 400–1,100ms against the 120–240ms guidance, with bouncy overshoot easings instead of `--ease-standard`. The loop runs next to, and competes with, the hero's primary action.
- [medium] **Screen-reader chatter.** `aria-live="polite"` on the caption announces a new sentence every 3 seconds for as long as the page is open (the only stops are pause or a hidden tab). AT users get interrupted while reading the rest of the page.
- [medium] **"Glow" and "stickers".** The blurred blobs behind the demo are glow by definition. The floating "✓ Guest form" / "UbyPort ✓" chips are the "floating badges, promo chips, stickers" DESIGN.md rejects for the guest picker, and that standard is meant to apply site-wide (brief §6.D).
- [low] **The mock receipt looks official.** "UBYPORT · 2026-09-19 / Accepted by UbyPort / CZ-UHP-849271" with a big green check (`landing.html:152-158`) reads like a real police receipt. It isn't labelled as an example.
- [low] **Pause control:** 34×34px (`landing.css:1027-1031`), under 44px. The glyph is a Roman numeral "Ⅱ" (U+2161), and "▶" (U+25B6) may render as a colour emoji on iOS/Android without VS15. You can't step to a specific scene: the progress bars are `aria-hidden` and not interactive.
- [low] **LOGO.md drift.** LOGO.md says the landing product-mock mark is `.product-shell aside img` at **28×28px**. `.product-shell` no longer exists in any template (dead CSS, `landing.css:247-272`). The live mock mark is `.reel-side img` at **38×38px** (`landing.css:1044`), hidden below 600px.
- Verified OK: `prefers-reduced-motion` is honoured both in JS (`landing.js:11,14,16,53-61`: shows the final scene, paused, listens for changes) and in CSS (`landing.css:1300-1313` kills animations/transitions). The loop also stops on `visibilitychange`.

**Dumbproof score (1–5):** 3 — it explains the flow well, but it's the loudest thing on the page and breaks the motion rules.

**Fix recommendation:**
- Play once and stop: advance through the four scenes a single time, then rest on scene 4. Show a quiet text button, `landing.demo.replay` (exists: "Replay demo" / "Přehrát znovu"). Scene transitions become `var(--motion-base)` (180ms) with `var(--ease-standard)`. Replace the overshoot beziers with `--ease-standard` and cap keyframes at 240ms, except the signature stroke, which may stay ≤600ms because it demonstrates the action.
- Move `aria-live` off the auto-advancing caption. Keep the caption visible but update it without `aria-live`; only announce when the user presses Replay.
- Delete `.demo-float` (both chips), the `.demo-wrap::before/::after` blur blobs, and the coloured shadow on the reel. Keep a 1px `--border-strong` frame.
- Add `landing.demo.example` EN "Example" / CS "Ukázka" as a small label on the receipt card, and change the code to an obviously fake value (e.g. "DEMO-000000").
- Toggle: 44×44px, CSS-drawn or inline-SVG icons (no Unicode glyphs). Update LOGO.md's table to `.reel-side img` at 28px (and set the CSS to 28px), or change the CSS to match the doc; they must agree.

---

### D → Landing body and final CTA (`landing.html:175-199`)

**Job of this screen:** reinforce the value in three beats and repeat the one CTA.

**Current flow:** "One simple flow". H2 "Less chasing. Less copying. More certainty." Three white cards (`.benefit-card`, border + shadow, `min-height: 270px`) with coloured icon tiles "▦", "✎", "✓" in blue/amber/green. Then "From booking to reported in three moves." with steps 01–03 and a link "Product details and common questions →". Final band: mark + "Your guest paperwork, on autopilot." + **Try UbyHost**.

**Friction found:**
- [medium] **Semantic colours used as decoration.** The benefit tiles are blue/amber/green (`landing.css:1219-1221`). The same pattern repeats on pricing factors (`factor-blue/yellow/green`) and product features (blue/yellow/purple/green). `tokens.css` header: "Semantic hues communicate state, urgency, or stable property identity — never decoration." Amber means *warning* in the app, yet here it tints "Guests do the typing".
- [medium] **Stacked white cards with borders and shadows** (`.benefit-card`, `.pricing-factor-grid article`, `.product-feature-row`, all `box-shadow: 0 1px 3px`, 250–270px min-height). This is the pattern DESIGN.md rejects ("Stacked white 'product cards' with heavy borders/shadows"), and the brief generalises that rejection. The content is one line each, so the cards are mostly empty.
- [low] **Copy error:** `landing.benefit.guest.body` EN "One private link collects and signs their details." A link can't sign; the guest signs. CS "Jeden soukromý odkaz údaje získá i podepíše." has the same error, and "údaje získá" is stiff.
- [low] **Final CTA mark is 56px, not the 64px LOGO.md locks.** The later rule `.landing-final img { width: 56px }` (`landing.css:1245`) overrides the documented 64px (`:730`). The old `.landing-final::before/::after` 54px coral rings (`:717-728`) still render because the override layer never resets them. The band also has a `linear-gradient(135deg, var(--brand-soft), …)` fill. That's atmosphere on top of the body wash.
- [low] **The body wash is stronger than the host app's.** `landing.css:11-14` uses a coral `rgba(200,90,82,.09)` at 28rem plus indigo. app.css's reference wash (`app.css:16-17`) uses the pale `--purple-bg`/`--blue-bg` tints. Coral at 9% is noticeably warmer and more saturated. On top of that come the blur blobs, the gradient final band, and the coloured drop shadow on the primary button (`box-shadow: 0 10px 30px rgba(173,73,66,.2)`, `landing.css:184`, i.e. a coral glow). Taken together, the site exceeds "the amount of atmosphere this brand allows".
- [low] **Emoji-like dingbats as icons** ("▦", "✎", "✓"). Not true emoji, but they carry the same "sticker" tone and render differently per OS.

**Dumbproof score (1–5):** 3 — clear and short, but decorated beyond the system's own rules.

**Fix recommendation:**
- Replace the three cards with one hairline-separated row list (the "lane" pattern): number in `--brand-ink` mono, title, one line of body, no shadows, no tinted tiles. Or merge "benefits" and "three moves" into a single section; they currently say the same thing twice.
- Body copy: `landing.benefit.guest.body` EN "Guests fill in and sign their details through one private link." / CS "Hosté vše vyplní a podepíší přes jeden soukromý odkaz."
- Final band: flat `--brand-soft` or `--surface`, no rings (delete `landing.css:717-728`). Mark at 64px per LOGO.md. Title uses the tagline (see hero). CTA uses `landing.cta` "Request access".
- Body background: reduce to a single `radial-gradient` using `color-mix(in srgb, var(--brand-soft) 60%, transparent)`, matching app.css's intensity. Primary button shadow becomes `none` (tokens: "Shadows are reserved for floating UI").

---

### D → Pricing (`pricing.html`)

**Job of this screen:** answer "what does it cost and how do I get it" in one read.

**Current flow:** Eyebrow "Simple agreement, no pretend pricing tiers" / "Jednoduchá domluva, žádné umělé tarify". H1 "Pricing that fits your accommodation." Lede "Tell us how you host…". A white card with a heavy shadow (`landing.css:1428-1435`) holds kicker "UbyHost workspace" / "Pracovní prostor UbyHost" + mark (44px), price "By agreement" / "Dle domluvy", note "A practical scope based on what you actually operate.", four ✓ includes, a coral **Ask about pricing →** (`mailto:support@ubyhost.com?subject=UbyHost%20pricing`), and "Write to us and we will reply with the next steps." Then "Three things shape the setup." (properties / volume / workflow cards) and a final band repeating **Ask about pricing**.

**Friction found:**
- [medium] **Pricing is statable in one sentence, but the sentence says nothing concrete.** "Price by agreement; e-mail us." There's no anchor (starting price, billing unit, or whether there's a setup fee or minimum term) and no answer to "can I try it first?", which the landing's "Try UbyHost" implied was yes. That contradiction between pages is the real cost: a prospect who pressed "Try" and got a login wall now reads "email us".
- [medium] **`mailto:`-only CTA with no visible address near it.** On a desktop without a configured mail client the button does nothing visible. The address is only in the footer. The subject is always English (`UbyHost%20pricing`), even on the CS page (`pricing.html:82,102`).
- [low] **Stiff CS copy:** "Pracovní prostor UbyHost" is a literal "workspace". "Praktický rozsah podle toho, co skutečně provozujete." reads like a contract. EN "no pretend pricing tiers" sounds snarky about competitors.
- [low] The card's mark is 44px (`landing.css:1448`), a placement LOGO.md doesn't list. The card itself is the heavy-shadow white product card DESIGN.md rejects. The factor cards use decorative semantic hues (see body).
- [low] The page's footer lacks login, DPA, subprocessors, and guides (see chrome).

**Dumbproof score (1–5):** 3 — honest and short, but it leaves the obvious next question ("what will it roughly cost / can I try it") unanswered, and it contradicts the landing CTA.

**Fix recommendation:**
- Add one plain answer sentence directly under the price. New key `pricing.card.summary`: EN "One plan with everything below. The monthly price depends on how many properties you run — write to us and we reply with a quote." / CS "Jeden tarif se vším níže. Měsíční cena závisí na počtu vašich ubytování — napište nám a pošleme nabídku." (If Joe can publish an anchor, e.g. "from X Kč per property per month", put it here instead; do not invent one.)
- Unify the CTA with the site: `pricing.card.cta` EN "Request access and a price" / CS "Požádat o přístup a cenu". Localized subject key `pricing.cta.subject` EN "UbyHost pricing" / CS "Cena UbyHostu". Add a visible line `landing.cta.note` (as in the hero) with the plain address. Update `tests/test_public_seo.py:118-131` expected strings in the same commit.
- Copy: `pricing.eyebrow` EN "One plan, priced for your properties" / CS "Jeden tarif, cena podle vašeho ubytování". `pricing.card.kicker` EN "What you get" / CS "Co dostanete". `pricing.card.note` EN "Priced for what you actually run." / CS "Cenu nastavíme podle toho, co skutečně provozujete."
- Visual: card border `--border`, no drop shadow. Drop the 44px mark or add the placement to LOGO.md. Factors become a hairline list.

---

### D → Product details / "How it works" (`product.html`, route `/jak-to-funguje`)

**Job of this screen:** give search visitors and serious prospects the full picture plus the UbyPort FAQ, then hand them to the same CTA.

**Current flow:** Eyebrow, then H1 "One flow from Airbnb booking to UbyPort receipt." and lede, then **Try UbyHost** (→ `/login`). Four feature cards, each with **two** numbers ("01" in the span plus "01 / Sync" in the kicker). FAQ as `<details>` ×4. An "Official information for accommodation providers" aside with a disclaimer and an `ipc.gov.cz ↗` link (opens in a new tab). Two guide cards (hard-coded copy). Final band "Ready to simplify guest reporting?" + **Try UbyHost**.

**Friction found:**
- [blocker → same item as the hero] Both CTAs go to `/login` (dead end for prospects). Fixed by the hero CTA item; listed here only so Phase 2 covers `product.html:65,128`.
- [low] **Double numbering** on feature rows: `<span>0{{ loop.index }}</span>` plus `landing.feature.*.icon` "01 / Sync". It renders as "01 01 / Napojení". Noise that has to be re-read.
- [low] **CS calques:** `product.page_title` "UbyPort pro Airbnb a Booking.com hostitele" (English word order). `product.faq.title` "Otázky k UbyPortu, jasně zodpovězené" (a literal "answered clearly"). `product.features.title` "Vše, čím hlášení hosta prochází" (awkward). `product.features.lede` "Čtyři propojené kroky bez tabulky mezi nimi." (a literal "no spreadsheet in between").
- [low] **Terminology drifts across pages:** "online guest book" (landing lede), "Online guest and house book" (pricing), "Online house book" (product feature 03), "Guest book" (footer). CS mixes "ubytovací kniha" and "domovní kniha" the same way. A host can't tell whether these are one feature or two (lens 7).
- Verified OK: the disclaimer "UbyHost is a technical tool, not legal advice…" and the official-source link are present here and on guides. The FAQ is native `<details>` (keyboard- and AT-friendly, no JS).

**Dumbproof score (1–5):** 3 — good depth and a proper disclaimer, but the CTA fails and the copy is noisy.

**Fix recommendation:**
- Remove the leading `<span>0N</span>` (`product.html:77`) and keep the kicker. Or keep the number and change the kicker keys to words only (EN "Sync / Collect / Keep / Report", CS "Napojení / Sběr / Evidence / Hlášení").
- CS copy:
  - `product.page_title` "UbyPort pro hostitele z Airbnb a Booking.com · UbyHost"
  - `product.faq.title` "Nejčastější otázky k UbyPortu" (EN "Common UbyPort questions")
  - `product.features.title` "Celá cesta hlášení na jednom místě" (EN "The whole reporting path in one place")
  - `product.features.lede` "Čtyři navazující kroky, žádné přepisování do tabulek." (EN "Four connected steps, no copying into spreadsheets.")
- Pick one public term: EN "guest book" / CS "ubytovací kniha" for the product feature, with "house book / domovní kniha" mentioned only where the legal distinction matters (guide copy). Needs owner confirmation of the legal naming; apply it in `landing_i18n.py` (`pricing.includes.3`, `landing.feature.book.title`) and the footer key.

---

### D → Public guide (`public_guide.html`, `public_guides.py`)

**Job of this screen:** answer a search query (e.g. "hlášení cizinců UbyPort") credibly, and offer the product as the next step.

**Current flow:** Breadcrumb "UbyHost / Guides" ("Guides" is plain text; no hub page exists). Hero H1 up to 5rem. Section headings and paragraphs, with a sticky "Checklist" aside on the right: ✓ items, **Try UbyHost** (→ `/login`), and "Product details and common questions →". Official-source aside, "Further reading", footer. JSON-LD Article with a hard-coded `datePublished`/`dateModified` "2026-09-19" (`public_guide.html:32-33`).

**Friction found:**
- [blocker → same item as the hero] Checklist CTA "Try UbyHost" → `/login` (`public_guide.html:93`). This is the conversion point for search traffic, and it hits the invite-only login wall.
- [low] **No visible "last updated" date** on a page whose whole value is "current rules". The date exists only in JSON-LD, hard-coded in the template instead of per guide in `public_guides.py`.
- [low] **Breadcrumb "Guides" is dead text** and there's no guides index. With only two guides that's acceptable, but it looks like a link target.
- Verified OK: EN/CS content structure parity is tested (`test_guide_translations_have_matching_content_structure`). The disclaimer and official `ipc.gov.cz` links are present. Paragraph measure (`max-width` + 1.75 line-height, `landing.css:815-821`) is comfortable. The checklist aside goes static on mobile.

**Dumbproof score (1–5):** 4 — calm, readable, well-sourced. It loses a point for the CTA and the missing freshness date.

**Fix recommendation:** Use the site CTA ("Request access"). Add `updated` per guide in `public_guides.py` (both languages) and render it under the lede with new key `guide.updated` EN "Last checked against official sources: %(date)s" / CS "Naposledy ověřeno podle oficiálních zdrojů: %(date)s". Feed the same value into JSON-LD. Render the breadcrumb's last crumb as the guide title with `aria-current="page"` instead of "Guides".

---

### D → Legal notice (`legal.html`, route `/legal`)

**Job of this screen:** say who operates UbyHost and how the operator's role differs from the host's.

**Current flow:** Extends the **host app** `base.html` with `show_nav=false`. There's no public header, no logo, no language switch, and no public footer. It shows a gradient page header (`app.css:427-437`, purple radial + coral linear), an operator `<dl>` panel, then five panels of `small muted` text. The only exits are a cross-link row ending in **Back to login**.

**Friction found:**
- [high] **Dead-end chrome for the public.** A visitor who clicks "Legal" in the landing footer leaves the marketing site's header and footer entirely. There's no logo link home, no way to switch EN/CS (rendered EN and CS: `lang-switch` count = 0 on all five legal pages), and the only way out is "Back to login". That's wrong for a prospect who never logged in. Direct visitors (e.g. from the login page's acceptance links, which open `/terms` in a new tab without `?lang`) get the cookie language or Czech, with no switch.
- [medium] **Host-app furniture in a public DOM.** Because it's `base.html`, the page ships the CSV-export dialog, command palette ("Search or jump to…"), keyboard-shortcut sheet ("g d Go to Overview"), `app.js`, and the confirm dialog to anonymous visitors (visible in the rendered text dump). It's harmless when closed, but it's noise for AT users who browse by landmarks/dialogs, and it's needless JS.
- [low] "ARES (public register)" is hard-coded English on the CS page (`legal.html:27`, also `terms.html:93`, `privacy.html:29`, `dpa.html:87`). The footer label `legal.footer_short` CS "Právní" is a bare adjective ("Legal…"); natural CS is "Právní informace". `legal.footer_short`/`legal.footer_nav_label` are defined **twice** in each language dict (`host_i18n.py:286-287` vs `:516-517`, `:1325-1326` vs `:1550-1551`), and the later value silently wins.

**Dumbproof score (1–5):** 2 — the content is fine, but it's a dead end with no way home and no language choice.

**Fix recommendation:** Create `templates/public_legal_base.html`: it reuses `_public_header.html`/`_public_footer.html` from the chrome item, loads `tokens.css` + `landing.css` only (no `app.js`/host dialogs), and has a reading column. Move all five legal templates onto it. Replace "Back to login" (`legal.back_login`) with a quiet "Back to UbyHost" (new `legal.back_home` EN "Back to UbyHost" / CS "Zpět na UbyHost") → `/?lang=…`. Keep "Host login" in the shared footer. Language links point to the same path (`/terms?lang=en`). New key `legal.registry_link` EN "ARES (public register)" / CS "ARES (veřejný rejstřík)". `legal.footer_short` CS "Právní informace". Delete the duplicate dict entries.

---

### D → Terms / Privacy / DPA (`terms.html`, `privacy.html`, `dpa.html`; copy in `terms_i18n.py`, `privacy_policy_i18n.py`, `dpa_i18n.py`)

**Job of this screen:** let a host (or their lawyer) read, find, and cite a specific clause; show the version in force.

**Current flow:** Same host-`base.html` shell as `/legal`. H1 + lede, then "Effective date: 19 September 2026. Version 1.5." (good). Operator panel, then **27** (Terms), **22** (Privacy), or **24** (DPA) sequential `.panel`s, each an `<h2>` + a single block of `.small.muted` text (13px, `--ink-muted`). In EN, Terms is about 17,000 characters of body. There's no table of contents, section `id`s, or "back to top". The page is 840px wide (`.no-nav .wrap` beats `.wrap.narrow` on source order, `app.css:425-426`), so 13px lines run about 110–120 characters. It ends with a "Professional review" panel and a cross-link row ending "Back to login".

**Friction found:**
- [high] **No navigation inside a 27-section document.** Hosts come to Terms/DPA to check one thing (liability, retention, sub-processing). With no TOC and no anchors, the only way to find §17 is to scroll through roughly 16 panels of 13px grey text. You can't link a colleague or lawyer to a clause. `TERMS_SECTION_IDS` etc. already exist in `routes/legal.py:12-15`, so anchors are free.
- [medium] **Long-form reading set as fine print.** `.small.muted` (13px, `#73736e`) was designed for secondary UI notes, not 17k-character reading. Combined with the long line length, it reads like it's hiding something, the exact impression the brief warns about (§6.B, §4 "must not look like a government form").
- [medium] **In-copy cross-references are raw paths, not links:** "…the data processing agreement at /dpa…", "…contact details on the /legal page" (e.g. `terms.s01_body`, `terms.s27_body`, `legal.dpa_body`). A reader has to retype the URL.
- [low] CS typo in `terms.page_lede` (`terms_i18n.py:308`): "poskytovateli ubytování, **kterí** službu používají" → "**kteří**".
- [low] The "Professional review" panel ("…not a substitute for advice from your own lawyer… have qualified counsel review them before relying on them") reads like a drafting note left in the published contract and weakens trust. Page UX only; the substance is the owner's call.
- Verified OK: effective date + version are shown at the top of each page (the "last updated" requirement is met). EN/CS structures match (section ID tuples are shared).

**Dumbproof score (1–5):** 2 — correct and versioned, but unnavigable at this length and styled as fine print.

**Fix recommendation (page UX only, no legal substance changes):**
- Give each section panel `id="s{{ sid }}"`. Under the effective date, add a compact TOC: `<nav aria-label="{{ t('legal.toc') }}">` with an `<ol>` of the section titles linking to `#sNN`. It collapses into `<details open>` on desktop and `<details>` closed on mobile. New key `legal.toc` EN "Contents" / CS "Obsah". Add `scroll-margin-top` so anchors clear the sticky header. Add a "Back to contents ↑" link every section or via a sticky mini-link, key `legal.back_to_toc` EN "Back to contents" / CS "Zpět na obsah".
- Body text: drop `small muted` on `.terms-section`. Use `--text-md` (16px), `--ink-secondary`, `line-height: 1.7`, `max-width: 70ch`. Panels become hairline-separated sections (no card per clause).
- Cross-references: render "/dpa", "/legal", "/privacy" as links. Preferred: a Jinja filter that linkifies exactly those four known paths in legal bodies, so the legal text stays untouched. If Joe prefers a copy edit instead, it needs his sign-off.
- Fix "kterí" → "kteří". Ask Joe whether "Professional review" stays public. If yes, move it to the end under a neutral title: EN "About these terms" / CS "K těmto podmínkám".

---

### D → Subprocessors (`subprocessors.html`, `subprocessors_i18n.py`)

**Job of this screen:** list who else processes guest data, for what, and where.

**Current flow:** Host `base.html` shell. H1, effective date "Version 1.0", a "Who engages these providers" panel, a scope panel, then a 4-column table (`table-cards`, which turns into cards on mobile via `data-label`), "changes" and "accuracy" panels, and the cross-links.

**Friction found:**
- [medium] Same chrome dead end as `/legal` (no header, no language switch, "Back to login" exit). Its footer row also omits Subprocessors' siblings inconsistently (it has no link to itself, which is fine, but the order differs from the other legal pages).
- [low] **Internal ops notes are published as public copy:** `subprocessors.scope_body` EN "Staging must contain demo or test data only. Exact enabled services, account regions, … must be verified before live use." CS "Staging smí obsahovat pouze ukázková nebo testovací data…". Also `render_purpose` "Staging/demo hosting only." A reader can't tell whether they apply to production. Page UX: reads as unfinished.
- Verified OK: the mobile table-to-card fallback via `data-label` is already right; don't rebuild it.

**Dumbproof score (1–5):** 3 — the table works on mobile, but the page is stranded outside the site.

**Fix recommendation:** Move it onto `public_legal_base.html` (same item as `/legal`). Flag the staging sentences to Joe for rewording or moving to an internal doc. No copy change without his OK, since it's DPA-incorporated text.

---

### D → SEO head (`_seo_head.html`, `seo.py`, `landing.html:10-13`)

**Job of this screen:** give each language its own indexable URL, so Czech hosts get the Czech page and English visitors the English one.

**Current flow:** `seo.head_links()` returns a self-referencing canonical (`/path?lang=xx`) and hreflang pairs for every `INDEXABLE_PATHS` entry. `pricing.html`/`product.html`/`public_guide.html` use it. `landing.html` hard-codes `<link rel="canonical" href="{{ public_base_url }}/">` for both languages.

**Friction found:**
- [low] `/?lang=en` declares `/` (the Czech default) as its canonical while also listing itself as the `hreflang="en"` alternate. Those signals conflict, and they contradict `seo.py`'s own docstring ("Each indexable page is offered in both languages under its own `?lang=` URL"). The English home page may drop out of the index.

**Dumbproof score (1–5):** 4 — solid system, one template bypasses it.

**Fix recommendation:** In `landing.html:10-13`, use `{{ canonical_url }}` and loop `alternate_urls` like the other pages (the context is already injected by `templating.render`).

---


## Surface E — Transactional e-mail

**How this was audited.** Every kind was built through the real code path, not just the builder functions: `claim.start_claim` (claim, claim_resend), `claim.maybe_notify_completion` (completion), `claim.sweep_reminders` with the clock at 10:00 (reminder_guest, reminder_host, both the claimed and unclaimed cases), and `mail_notify.build_submission_problem` (rejected and transport variants). Outbox rows were read back through `mail.delivery_body/delivery_html`, so the files show exactly what ships, with To/Cc/Reply-To, in EN and CS. Output: `/tmp/uby-2-audit/scratch_mail/<kind>_<lang>.{txt,html}` (script `render.py`). The PIN/claim-link test is `scratch_mail/pin_flow.py`. `PUBLIC_BASE_URL` was set to `https://ubyhost.com`.

**Actual `mail.KINDS`** (`App/app/mail.py:27-35`): `claim, claim_resend, reminder_guest, reminder_host, completion, dates_changed, submission_problem`. This matches the brief's list. **`dates_changed` has no builder, no call site and no copy anywhere in the repo**, although `docs/SES.md:19-20` says it "stays plain text". It's a mismatch under brief §0 rule 10 (see E → dates_changed below).

**Where the copy lives:** guest mail uses the `mail_*` keys in `App/app/i18n.py:485-541` (EN) and `:994-1047` (CS). Host mail uses `mail.reminder_host.*` / `mail.submission_problem.*` in `App/app/host_i18n.py:711-732` / `:1743-1764`. Fallback plain-text bodies are hard-coded in `App/app/claim.py:410-425, 540-549, 621-629`. The markup is `_shell` + `_block_*` in `App/app/mail_notify.py:187-375`.

**Contact-split check, every kind (as shipped):**

| kind | To | Cc | Reply-To | support@ in body? |
|---|---|---|---|---|
| claim / claim_resend | guest | – | legal-entity contact (`claim.py:293-295`) | no ✅ |
| completion | guest | entity contact (`claim.py:538`) | entity (`:562`) | no ✅ |
| reminder_guest | guest | – | entity (`:645-647`) | no ✅ |
| reminder_host | entity contact | – | none | no (host mail, allowed) |
| submission_problem | entity contact | – | none | yes, footer "Questions about UbyHost itself" (host mail, allowed ✅) |

The rule holds today in every kind. But Reply-To is set by hand at three call sites instead of by the shell. The invoice plan's new guest kinds (§9 table) don't mention Reply-To at all, so the next kind added is likely to break the rule (E-8 [UX-74]).

---

### E → Shared mail shell (`App/app/mail_notify.py` `_shell`, `_button`, `_block_*`, `_guest_footer_lines`)

**Job of this screen:** give every message one calm, branded, phone-readable card with one obvious action.

**Current flow:** the canvas `#f7f7f5` holds a table `width="600"` with `style="width:100%;max-width:600px"` (`:312-314`). Inside: the logo `ubyhost-logo.jpg` at `width="180"` (`:316`), an h1 at 22px, a 16px intro, a coral button (`:485-494`), a fallback URL (`:256-270`), uppercase section labels, and a muted 13px footer (`:319-322`). The preheader is a hidden div with the intro text (`:296-302`). There are no `@media` rules. At 375px the card is 351px and the content column is 287px because of 32px side padding.

**Friction found:**
- [medium] **The button fails AA contrast, and it's the only tap target that matters.** `_button` uses `BRAND #c85a52` (`mail_notify.py:45,489`), so white on it is **4.17:1**. The web app uses `--brand-action #ad4942` for every primary button (`app.css:1006`, `guest.css:564`), which gives 5.51:1. The comment at `:36` says the values are "copied from tokens.css", but it copied the identity colour, not the action colour. The same goes for the fallback link and the submission stay links (`#c85a52` on white, 4.17:1). The `_block_note` label is `#c85a52` on `#f9e9e7`, only **3.54:1**, and it's 13px uppercase.
- [medium] **The button is under 44px tall.** `padding:11px 20px; font:600 15px/1` gives about 37px (`:490`). Outlook desktop ignores padding on `<a>`, so there only the text is clickable.
- [medium] **The preheader repeats the first line, then the preview runs on into boilerplate.** `preheader=intro` in every builder (`:717, 767, 830, 894, 557`), with no spacer after it. The inbox snippet reads "Confirm your stay at Vinohrady Studio (…) by opening the link below. UbyHost Confirm your stay Confirm your stay at…". The one extra line of inbox real estate adds no information.
- [low] **The footer's host contact isn't tappable, and it sits under the word "UbyHost".** `_guest_footer_lines` (`:341-357`) prints `hello@… · +420…` as plain text in 13px muted type. `guest/_host.html` uses `mailto:`/`tel:` links. Guests have never heard of "UbyHost", and the first footer line doesn't say what it is.
- [low] **Uppercase, letter-spaced labels** ("WHAT HAPPENS NEXT", "PLEASE NOTE", "REGISTRATION LINK SENT TO") in `_block_section/_block_note/_block_fact` (`:220-221, 232-233, 244-245`). Brief §4 flags ALL CAPS labels as a government-form tell.
- [low] **32px side padding at 375px** leaves a 287px text column. It isn't broken, but there's no `@media`, so the same padding applies on phones.
- [low] **`color-scheme: light` is missing** in mail. `docs/DESIGN.md` ("What to do instead") asks for it on every document, and it stops Apple Mail and Outlook from auto-inverting the card. `tests/test_submission_mail.py:292` and `tests/test_guest_mail.py:295` deliberately assert `"color-scheme" not in html`, so this needs product-owner sign-off.

**Dumbproof score (1–5):** 4. The structure is right (table-based, inline styles, max-width, logo exactly per LOGO.md, text part always present). The primary control is below the contrast and tap-size bar.

**Fix recommendation:**
- `_button`: background `#ad4942` (`--brand-action`), `padding:14px 24px; font:600 16px/20px` (48px tall). Put the same `padding` on the `<td>` so Outlook's clickable area matches. Links: `#ad4942`. `_block_note` label: `#963e38` (`--brand-ink`, 5.86:1).
- `_shell`: accept a distinct `preheader` per kind (copy is in each block below). After it, append `&#8199;&#65279;&#847;` ×~40 so the client doesn't pull body text into the snippet.
- `_guest_footer_lines`: render the host e-mail and phone as `mailto:`/`tel:` links in the HTML part. Replace the bare "UbyHost" line with a new key `mail_guest_footer_about`:
  EN "UbyHost is the guest-registration service your host uses." / CS "UbyHost je služba pro registraci hostů, kterou váš hostitel používá."
- `_block_section/_fact/_note` labels: sentence case, `font:600 14px/1.4`, colour `INK` (drop `text-transform` and `letter-spacing`).
- Side padding 32 → 24px in every `_block_*` and the shell.
- `color-scheme`: optional. Add `<meta name="color-scheme" content="light only">` only if Joe agrees to update the two test assertions to "no dark variant" (`prefers-color-scheme` / `@media` still forbidden).

---

### E → claim (magic link) (`mail_notify.build_claim_link`, sent by `claim.start_claim`)

**Job of this screen:** get the guest to tap the private link within 30 minutes, so the stay is theirs and the form opens.

**Current flow:** the guest taps "Send me the form link" / "Pošlete mi odkaz na formulář" (`i18n.py:97`) and sees "Check your e-mail" (`:98`). The mail arrives From `UbyHost <noreply@ubyhost.com>`, Reply-To the entity. Rendered (`scratch_mail/claim_en.txt`, `claim_cs.txt`):
- Subject: **"Continue your Prague guest registration"** / **"Pokračujte v registraci hostů"**
- Preheader = intro
- H1 "Confirm your stay" / "Potvrďte svůj pobyt"
- "Confirm your stay at Vinohrady Studio (2026-09-25 – 2026-09-28) by opening the link below." / "Potvrďte pobyt v Vinohrady Studio (2026-09-25 – 2026-09-28) otevřením odkazu níže."
- Button "Confirm my stay" / "Potvrdit pobyt", then the fallback URL
- "WHAT HAPPENS NEXT: …about two minutes per guest…"
- Muted last line: "The link is valid for 30 minutes and stops working as soon as you confirm the stay."

The link `/l/{token}/{id}/claim#c=<secret>` opens `guest/confirm.html` ("Is this your reservation?" → "Yes, this is my stay"). `claim.js` reads the secret from `location.hash`.

**Friction found:**
- [**blocker**] **Opening the link in any browser without a PIN session silently kills the link.** This is the default case when a phone's mail app opens links in its own in-app browser (no shared cookies), or when the guest started on another device. `claim_landing` runs `_require_pin` first (`routes/guest.py:946-948`), and `GUEST_PIN_REQUIRED` defaults on (`config.py:129`). `_pin_page` sets `return_to = request.url.path (+query)` (`routes/guest.py:347-348`). The fragment never reaches the server, the PIN form posts without it (`guest/pin.html:7-9`), and `_safe_return_to` would strip it anyway (`routes/guest.py:301`, fragment `""`). After the PIN the guest lands on the confirm page with an empty secret. Tapping "Yes, this is my stay" then says "That confirmation link is invalid or has expired" (`i18n.py:127`). The link isn't expired: the secret was simply dropped. Verified: `scratch_mail/pin_flow.py` shows a fresh-client GET of the claim link returns the PIN page with `return_to=/l/pintok/1/claim` (no `#c=`). The mail says nothing about a PIN either.
- [high] **The subject fails the 40-unread-inbox test.** It doesn't name the property, it names a city the property may not be in ("Prague" is hard-coded at `i18n.py:485`, while hosts are Czech-wide), and the sender is "UbyHost", a brand the guest has never seen. That's close to the textbook shape of a phishing mail. It also says "Continue", while the heading and button say "Confirm" and the landing page says "Is this your reservation?". That's four names for one step, and the guest pages call the same thing "the form link" / "private link" / "secure link" (`i18n.py:97, 119-120`).
- [high] **Dates are raw ISO** ("2026-09-25 – 2026-09-28"). `claim._guest_mail_content` builds `dates = f"{date_from} – {date_to}"` (`claim.py:335`). Every guest page prints `date_cz` ("25.09.2026 – 28.09.2026", e.g. `guest/pick.html:10`), and `mail_notify.py:73-75` says "an e-mail, an alert and a page must never print the same stay differently". The code breaks its own documented rule.
- [medium] **The one time-critical fact comes last and reads as a threat.** "30 minutes" is in the final muted 14px line (`build_claim_link` puts `expiry` after "What happens next", `mail_notify.py:692-695`). "Stops working as soon as you confirm the stay" makes guests think they can't come back. In fact the device remembers them for 60 days (`routes/guest.py:264`).
- [medium] **CS grammar.** "pobyt **v Vinohrady Studio**" leaves the proper name undeclined after "v", and "v V…" should be "ve". The footer repeats it ("váš pobyt v Vinohrady Studio"). When a property has no name, `property_label` falls back to the "Your host" key (`mail_notify.py:662`), producing "Confirm your stay at **Your host**" / "Potvrďte pobyt **v Váš hostitel**" (`scratch_mail/claim_unnamed_*.txt`).
- [low] The plain-text fallback (`claim.py:410-425`) is English/Czech hard-coded outside `i18n.py`, uses "your host" in English inside the CS branch, and says "expires in 30 minutes until you confirm". It only ships when HTML composition throws.

**Dumbproof score (1–5):** 2. The body is clear and the button is singular, but the primary path fails silently for a common device situation. The inbox line also doesn't identify the stay.

**Fix recommendation:**
1. **E-1 [UX-6] (blocker): keep the secret across the PIN gate.**
   - In `routes/guest.py::_safe_return_to`, keep `split.fragment` (it's same-origin and inert).
   - In `static/signature.js` (already loaded on every guest page, `guest/base.html:48`), when `form[action*="/pin"] input[name=return_to]` exists and `location.hash` starts with `#c=`, append the hash to `return_to.value`.
   - A 303 whose Location carries `#c=…` puts the secret back where `claim.js` reads it.
   - Add a TestClient test: PIN page `return_to` round-trip keeps `#c=`.
   - Also add to `mail_claim_next_body`: EN "If you're asked for a PIN, use the one from your host's message." / CS "Pokud se stránka zeptá na PIN, použijte ten ze zprávy od hostitele."
2. **E-3 [UX-25] subjects** (the new copy uses `%(property)s`, which `build_claim_link` already has):
   - claim: EN "Confirm your stay at %(property)s (link valid 30 min)" / CS "Potvrďte svůj pobyt – %(property)s (odkaz platí 30 minut)"
   - claim_resend: EN "New link: confirm your stay at %(property)s" / CS "Nový odkaz: potvrďte svůj pobyt – %(property)s"
   - Preheader (new key `mail_claim_preheader`): EN "Tap the button, then fill in each guest — about 2 minutes per person." / CS "Klepněte na tlačítko a vyplňte údaje hostů – asi 2 minuty na osobu."
   - Optional, size M: `mail.display_from` per message as `"%(property)s via UbyHost" <noreply@…>`. This needs an RFC 2047-encoded display name for diacritics, because SES `Source` must be ASCII-safe.
3. **E-4 [UX-26] dates:** in `claim._guest_mail_content` use `validation.fmt_date_range(reservation["date_from"], reservation["date_to"])`.
4. **E-11 [UX-77] expiry:** move it directly under the button (before the fallback URL) as normal 15px text.
   - `mail_claim_expiry`: EN "The button works for 30 minutes. After you confirm, this phone or computer remembers your stay — you won't need the link again on it." / CS "Tlačítko funguje 30 minut. Po potvrzení si váš pobyt zapamatuje tento telefon nebo počítač – odkaz už na něm znovu potřebovat nebudete."
   - `mail_claim_expiry_resend`: EN "This new link replaces the previous one and works for 30 minutes." / CS "Tento nový odkaz nahrazuje předchozí a funguje 30 minut."
5. **E-13 [UX-79] CS cases:**
   - `mail_claim_intro` CS "Potvrďte svůj pobyt: %(property)s, %(dates)s. Stačí otevřít odkaz níže."
   - `mail_guest_footer_why` CS "Tento e-mail dostáváte, protože jste touto adresou potvrdili pobyt: %(property)s."
   - EN unchanged apart from dates.
   - `property_label` fallback: new key `mail_property_fallback` EN "your accommodation" / CS "vaše ubytování". Never the host label.
6. Button label, to match the subject and page: EN "Confirm my stay" (keep) / CS "Potvrdit můj pobyt".

---

### E → claim_resend (`build_claim_link(resend=True)`)

**Job of this screen:** replace a lost or expired link with a working one, and say that the old one is dead.

**Current flow:** identical to claim except the last line ("This is a new link and the previous one has stopped working…"). The subject is **identical** to the first mail (`claim.py:376`, `i18n.py:485`), so in a threaded inbox the guest can't tell which of the two is the live link. It's triggered from `guest/assigned.html` "Send me the link again", including for a stay whose forms are already complete. In that case the body still says "You will enter the details of every guest…".

**Friction found:**
- [high] Same subject as the dead link. The guest may well tap the older mail first and hit "invalid or expired". (Fixed by the E-3 [UX-25] claim_resend subject.)
- [medium] "This is a new link" is the last, muted line, but it's the most important fact in this mail. Put it in the heading.
- [low] "What happens next" is wrong when the stay is already complete.

**Dumbproof score (1–5):** 2. It inherits the claim blocker (E-1 [UX-6]), and nothing tells it apart from the mail it replaces.

**Fix recommendation:** add a `mail_claim_resend_heading` key, EN "Here is your new link" / CS "Tady je váš nový odkaz". Use it when `resend=True`, together with the E-3 [UX-25] subject and the E-11 [UX-77] resend expiry line. If `reporting.reservation_progress` is complete, swap `mail_claim_next_body` for a new key `mail_claim_next_done`: EN "Everyone is already registered — the link just opens your stay page." / CS "Všichni už jsou zaregistrovaní – odkaz jen otevře stránku vašeho pobytu."

---

### E → reminder_guest (`build_reminder_guest`, sent by `claim.sweep_reminders`)

**Job of this screen:** the day before arrival, get the remaining guests registered.

**Current flow** (`scratch_mail/reminder_guest_*.txt`):
- Sent once, after 09:00 the day before check-in, only when the stay is claimed and incomplete (`claim.py:613-619`).
- Subject: "Please finish your guest registration" / "Dokončete prosím registraci hostů"
- H1 "Your stay starts tomorrow"
- "Your stay at Vinohrady Studio starts tomorrow and the guest registration is not complete yet."
- Button "Finish the registration" → `/l/{token}/{id}` (the stay page, not a claim link, `mail_notify.py:785-787`)
- A coral note box: "ONE REMINDER ONLY — This is the only incomplete-registration reminder we will send."
- Muted: "If you have already sent everything, you can ignore this message."

**Friction found:**
- [medium] **It doesn't say what's missing.** The sweep has `progress` (filled/expected) in hand (`claim.py:607`), but the mail never says "1 of 2 guests done". The guest has to open the page to find out whether it's them or their partner who's missing.
- [medium] **Emphasis is inverted.** The loudest block (coral note) is a fact about UbyHost's sending policy. And "If you have already sent everything, ignore this" is false by construction: the mail is only sent when the stay is incomplete (`claim.py:618`).
- [medium] **The link is a stay page that only opens without friction on the device that claimed it.** On any other device the guest meets the PIN, then `guest/assigned.html` ("This reservation is already assigned"), then a resend, then a new mail. None of this is mentioned (it's in the `mail_notify.py:785-787` docstring, not in the copy).
- [medium] Raw ISO dates (E-4 [UX-26]) and CS "v Vinohrady Studio" (E-13 [UX-79]), as above.
- [low] The subject doesn't name the property or say "tomorrow". "Please finish…" reads like every other nag mail.

**Dumbproof score (1–5):** 3. There is one clear button, but the mail withholds the one fact that tells the guest whether it concerns them.

**Fix recommendation:**
- Pass `filled`/`expected` into `build_reminder_guest`.
- Subject: EN "Tomorrow at %(property)s: %(filled)s of %(expected)s guests registered" / CS "Zítra přijíždíte (%(property)s): zaregistrováno %(filled)s z %(expected)s hostů"
- Intro: EN "%(missing)s more guest(s) still need to fill in the form before you arrive." / CS "Před příjezdem ještě musí formulář vyplnit další hosté: %(missing)s." (a plain number avoids CS plural forms)
- Button: EN "Finish the registration" (keep) / CS "Dokončit registraci" (keep)
- Replace the note box with a muted line (new key `mail_reminder_guest_device`): EN "Open it on the phone or computer where you started. On another device you'll be asked for your host's PIN." / CS "Otevřete ho na telefonu nebo počítači, kde jste začali. Na jiném zařízení budete potřebovat PIN od hostitele."
- Delete `mail_reminder_guest_help`, and demote "One reminder only" to muted text without the box.

---

### E → completion (receipt) (`build_completion`, sent by `claim.maybe_notify_completion`)

**Job of this screen:** tell the guest, unmistakably, that they're done (and soon: what, if anything, to pay).

**Current flow** (`scratch_mail/completion_*.txt`):
- To the guest, **Cc the entity**, Reply-To the entity (`claim.py:537-569`)
- Subject: "Guest registration received" / "Registrace hostů byla přijata"
- H1 "Registration received"
- "Thank you. We have received the details for your stay at Vinohrady Studio (2026-09-25 – 2026-09-28)."
- Coral button "Open my stay" / "Otevřít můj pobyt", then the fallback URL
- Coral note box: "PLEASE NOTE — This receipt is not proof of police reporting. Depending on your host's settings, complete foreign-guest records may be sent to UbyPort automatically." / "UPOZORNĚNÍ — Toto potvrzení není důkazem hlášení policii. Podle nastavení ubytovatele mohou být kompletní záznamy cizinců odeslány do UbyPortu automaticky."

**Friction found:**
- [high] **It never says "you're done, nothing else to do"**, the one sentence brief §3 lens 6 requires. The most prominent block after the button is a legal disclaimer. It uses host-side jargon ("UbyPort", "foreign-guest records", "police reporting"), which brief §3 lens 2 says must not reach guests, and it opens with a negative ("not proof"). This is where the product most "reads like a government form".
- [medium] **A coral primary button with no real job.** "Open my stay" invites a click that achieves nothing. On a different device it leads to PIN, then the "already assigned" screen. Once the stay fee lands, a second coral button ("Pay 400 Kč online") will compete with it (PLAN_POPLATEK §10.3 step 3 inserts `_block_button` for the payment link). That gives two equal-weight primaries (lens 1).
- [medium] **The subject doesn't name the property and gives no closure.** "Registration received" reads as "pending". With the fee it would also hide the only thing still to do.
- [medium] CS mixes terms inside one mail: the note says "ubytovatele" and the footer says "Váš hostitel … s hostitelem". DESIGN.md's copy table fixes "Váš hostitel" for the guest's contact.
- [medium] Raw ISO dates (E-4 [UX-26]). CS "v Vinohrady Studio" (E-13 [UX-79]).

**Dumbproof score (1–5):** 3. It's delivered at the right moment to the right people, but it doesn't close the loop in plain words, and the layout has no reserved place for the money block that's landing next.

**Fix recommendation (E-7 [UX-29]), copy:**
- Subject, no fee: EN "You're registered for %(property)s — nothing else to do" / CS "Registrace hotová – %(property)s. Nic dalšího nemusíte dělat"
- Subject, fee due: EN "Registered — stay fee %(amount)s Kč to pay for %(property)s" / CS "Registrace hotová – zaplaťte poplatek z pobytu %(amount)s Kč (%(property)s)"
- H1: EN "You're all set" / CS "Hotovo"
- Intro: EN "Everyone for %(property)s (%(dates)s) is registered. There is nothing else you need to do." / CS "Všichni hosté pro %(property)s (%(dates)s) jsou zaregistrovaní. Nic dalšího dělat nemusíte." (when a fee is due, the second sentence becomes the `mail_fee_*` lead-in below)
- Replace the note box with a muted closing paragraph (`mail_completion_note`): EN "Your host takes care of the official registration with the authorities. This e-mail is your receipt, not an official confirmation." / CS "Úřední hlášení vyřizuje váš hostitel. Tento e-mail je potvrzení pro vás, nikoli úřední doklad."
- Demote "Open my stay" from `_block_button` to `_block_link` / a quiet text link: EN "See your stay page" / CS "Zobrazit stránku pobytu".

**Fix recommendation, block structure (E-22 [UX-73]), so the stay fee (PLAN_POPLATEK §1.1 G6, §10.3) and the invoice (PLAN_GUEST_INVOICE §0.5 G5, §9) slot in without a redesign.** Refactor `build_completion` (and later the invoice builders) into this fixed order. Each slot is optional, and **at most one slot may render a coral `_block_button`**:
1. `status`: H1 + intro, with the done/closure sentence above.
2. `money`: the new `_block_panel(title, rows, action)`. It's one bordered sub-card on `CANVAS` with sentence-case label/value rows, **one** primary button (Pay online if `payment_link`), and copy-friendly monospace values for IBAN/VS/reference. This is where `stay_fee` renders (total first, then transfer facts, then cash as muted text). The plan's `_block_fact` ×4 at the top level would otherwise scatter four uppercase facts through the card. Later, `invoice_issued` reuses the same panel (number, total, "Download invoice" as its one button).
3. `secondary_links`: quiet text links ("See your stay page" + the QR note from PLAN_POPLATEK: EN "The QR code for your banking app is on your stay page." / CS "QR kód pro bankovní aplikaci najdete na stránce pobytu.").
4. `closing_note`: the muted legal line.
5. Footer.

The plain-text part mirrors this order under `--` separators. Rule: if slot 2 has a button, slot 1 has none. Also, `mail_fee_body` in the plan's §13.1 CS table says "Ubytovatel vybírá…". Align it to "Váš hostitel vybírá…" or decide the term product-wide (E-15 [UX-59]).

---

### E → reminder_host (`build_reminder_host`, sent by `claim.sweep_reminders`)

**Job of this screen:** on check-in day, tell the host which stay is incomplete and the one thing to do about it.

**Current flow** (`scratch_mail/reminder_host_en_prod_{0,1}.txt`): sent after 09:00 on check-in day for every incomplete stay (`claim.py:661-686`), always in English (`claim.py:665-674` passes no `lang`, and the payload is hard-coded `"lang": "en"`).
- Subject: "Incomplete registration: Vinohrady 12 / 3B"
- "Vinohrady 12 / 3B has a check-in today (**2026-09-24**) and the guest registration is not complete yet."
- Fact "REGISTRATION LINK SENT TO: g***@e******.com", or for an unclaimed stay "REGISTRATION LINK SENT TO: **the guest has not claimed the stay yet**"
- "WHAT TO DO NEXT: The guest can still finish using their registration link. Open the stay to see what is missing **or to send a fresh link**."
- Button "Open the stay"

**Friction found:**
- [high] **It promises an action that doesn't exist.** The host stay page (`templates/reservation_detail.html:40-113`) offers *Copy link*, *Release assignment* and *Reopen guest access*. There's no "send a fresh link" control, and no host route calls `claim.start_claim` (the grep over `routes/admin*.py` finds none). The host opens the stay looking for a button that isn't there.
- [medium] **In the unclaimed case the copy reads as nonsense:** the label/value pair produces "Registration link sent to: the guest has not claimed the stay yet". The next step ("finish using their registration link") is also wrong, because no link was ever sent. The host actually needs to re-send the apartment link and PIN.
- [medium] The date is raw ISO (`claim.py:667`), while the host app prints `date_cz`. The mail has no count ("0 of 2 forms"), although the in-app alert has one (`alerts.checkin_incomplete_reason`, `test_notification_copy.py:55`).
- [medium] **English only** (known: `FOLLOWUPS.md:612-626`, no stored host language). But CS keys exist (`host_i18n.py:1756-1764`), so Czech hosts, the primary market, get English on the morning of check-in. `mail_notify.py:16-18` and `SES.md:24` document this as deliberate.
- [low] It borrows the guest catalogue for the fallback-link line (`mail_notify.py:859`, `_guest_text(... "mail_link_fallback")`). That works, but it crosses the catalogue boundary.

**Dumbproof score (1–5):** 3. There's one clear button and a good subject, but the next-step sentence sends the host looking for a missing control, and the unclaimed variant doesn't make sense.

**Fix recommendation (E-5 [UX-27]):**
- Split `next_steps` by case.
- Claimed, `mail.reminder_host.next_steps_claimed`: EN "%(filled)s of %(expected)s guests have registered. Open the stay to see who is missing — the guest can still finish from the device they started on." / CS "Zaregistrováno %(filled)s z %(expected)s hostů. Otevřete pobyt a podívejte se, kdo chybí – host může registraci dokončit na zařízení, kde začal."
- Unclaimed, `…next_steps_unclaimed`: EN "Nobody has opened the registration yet. Send the guest the registration link and PIN again — copy the link from the stay page." / CS "Registraci zatím nikdo neotevřel. Pošlete hostovi znovu odkaz k registraci a PIN – odkaz zkopírujete na stránce pobytu."
- Unclaimed case: drop the `_block_fact` entirely.
- Subject: EN "Check-in today, %(filled)s/%(expected)s registered: %(property)s" / CS "Dnes příjezd, registrováno %(filled)s/%(expected)s: %(property)s"
- Date through `validation.fmt_date`.
- Host language (E-14 [UX-80], product decision): until a stored preference exists, either default host mail to `host_i18n.PUBLIC_DEFAULT_LANGUAGE` ("cs"), or send the CS subject with EN in the body. Log the choice in FOLLOWUPS. Don't leave the CS keys dead.

---

### E → submission_problem (`build_submission_problem`, sent by `reporting.py:1039, 1255`)

**Job of this screen:** tell the host a police report didn't go through, why, and the one thing to do.

**Current flow** (`scratch_mail/submission_problem_{,transport_}{en,cs}.txt`):
- Subject "UbyPort did not accept your report - Vinohrady 12 / 3B"
- H1 "Your report was not accepted"
- Intro, then a coral note "WHAT UBYPORT REPORTED: <server text>"
- "WHAT TO DO NEXT: Open the stay, check the guest's nationality, date of birth and document number… then send the report again."
- Muted text about interrupted connections
- A stay list with "Open the stay" links, then the coral button "Open the Doručenka"
- Footer "You are receiving this because automatic reporting is on…", "Questions about UbyHost itself: support@ubyhost.com"

**Friction found:**
- [**blocker**] **The raw i18n key reaches the host in every transport-failure mail.** `_reason_text` returns `_text(lang, "mail.submission_problem.reason_transport")` (`mail_notify.py:180`), and that key exists in neither `host_i18n.STRINGS["en"]` nor `["cs"]` (a repo-wide grep hits only the call site). Both parts print `mail.submission_problem.reason_transport` under "What UbyPort reported:" (`scratch_mail/submission_problem_transport_en.txt`). `tests/test_submission_mail.py:198-219` checks the intro and the absence of the exception, but not this line.
- [high] **The transport variant uses the rejected variant's copy.** The subject says "UbyPort did not accept your report" when UbyPort never received it. The note label is "What UbyPort reported" when UbyPort reported nothing. The next step tells the host to re-check nationality, date of birth and document number, which is useless for a connection failure, and the guests are retried by the next sweep anyway (`reporting.py:1046`, "Guests stay pending so the next sweep retries them"). The host is told to do data work that isn't needed.
- [medium] **Two primaries.** Per-stay "Open the stay" links plus a coral "Open the Doručenka" button. The job ("fix the data") lives on the stay, but the button goes to the receipt.
- [low] The footer says "because automatic reporting is on", but the mail also goes out for manual sends (`reporting.py:1248-1251` comment). EN "Doručenka" is untranslated jargon for an EN-reading host. CS lowercases it ("doručenku"). Subjects use " - " rather than " – ".

**Dumbproof score (1–5):** 2 for the transport variant (raw key plus wrong instructions), 4 for the rejected variant (specific reason, specific fix, links to each stay).

**Fix recommendation:**
- E-2 [UX-7]: add `mail.submission_problem.reason_transport` to both catalogues. EN "The connection to UbyPort failed before the report was delivered." / CS "Spojení s UbyPortem selhalo dřív, než se hlášení podařilo doručit." Add an assertion that no `mail.` key text appears in either part.
- E-6 [UX-28]: give transport its own variant.
  - `…subject_transport`: EN "Report for %(property)s not delivered yet — retrying automatically" / CS "Hlášení pro %(property)s zatím nebylo doručeno – zkusíme to znovu automaticky"
  - `…reason_label_transport`: EN "What happened" / CS "Co se stalo"
  - `…next_steps_transport`: EN "Nothing to do now: UbyHost sends it again on the next run. If you get this e-mail again tomorrow, open the stay and send the report by hand." / CS "Teď nemusíte nic dělat: UbyHost hlášení při dalším běhu odešle znovu. Pokud vám tento e-mail přijde i zítra, otevřete pobyt a odešlete hlášení ručně."
- Rejected variant: make the single stay's "Open the stay" the coral button when there's one stay, and turn the Doručenka link into a quiet text link.
- Footer: EN "You are receiving this because a guest report for %(property)s was not accepted." / CS "Tento e-mail dostáváte, protože hlášení hostů pro %(property)s nebylo přijato."
- EN label "Open the report receipt (Doručenka)".

---

### E → dates_changed (`mail.KINDS` entry with no implementation)

**Job of this screen:** (intended, per `SES.md:19`) tell someone that a stay's dates moved.

**Current flow:** none. `"dates_changed"` is accepted by `mail.enqueue` (`mail.py:33`), but nothing builds or enqueues it (grep: only `mail.py:33` and `SES.md:19`). The real event (iCal moves a stay after the guest signed) raises the host-only alert `dates_changed_resign` (`icalsync.py:616`). The guest is never told, so they arrive with a signed form that names the old dates.

**Friction found:**
- [low] A doc/code mismatch (brief §0 rule 10): SES.md describes a kind that doesn't exist. There's a latent risk that someone "restores" it as a plain-text-only mail, against the LOGO.md/SES.md rule that every message carries HTML.

**Dumbproof score (1–5):** n/a (not shipped).

**Fix recommendation:** decide explicitly. **(a)** Remove `dates_changed` from `KINDS` and from `SES.md:19-20` (size S), or **(b)** build a guest mail on the shared shell: subject EN "Your dates at %(property)s changed — please check and sign again" / CS "Termín pobytu %(property)s se změnil – zkontrolujte ho a podepište znovu", one button to the stay page, Reply-To the entity. The recommendation is (a) now, and (b) as a separate product item, because it adds a guest step.

---

#### B — repo vs brief mismatches (summarised at the top)

- Brief §6.B says "Password reset / `account_password.html`". There is **no password-reset flow**. `account_password.html` only covers first-password and change-password, and accounts have no e-mail to reset against.
- `docs/LOGO.md` says `.auth-logo` is 220px and `.auth-hero-mark` 300px, but `app.css:2894` / `:2959` override them to 178px / 170px (B-21 [UX-125]).
- 2FA is mandatory **only when `DEPLOYMENT == "production"`** (`auth.py:287`). The brief's flow description assumes it everywhere, and the step counts in B-13 [UX-67] must be conditional.

---

# Closing sections

## Prioritized backlog (Phase 2 step list)

Order rule (brief §5, applied literally where it speaks and by tier where it doesn't): **all blockers first** — guest form, then auth, then e-mail, then the host-app and public-site blockers (these "clearly outrank" any non-blocker, per §5) — **then all highs, mediums and lows**, each tier in the same surface order A → B → E → C → D. Inside a surface, items keep the audit's severity order and respect listed dependencies (every "depends on" item comes earlier). One `UX-N` = one commit: `ux: UX-N <short title>`.

⚑ = needs a decision or sign-off from Joe before it's built (see *Decisions for Joe* at the top). Build the rest in order; skip a ⚑ item until it's decided rather than guessing.

| # | severity | surface | screen | fix | files touched | size | depends on / plan impact | audit id |
|---|---|---|---|---|---|---|---|---|
| **UX-1** | blocker | A · Guest form | Form · signature | Block "Continue" on the signature step until signed. If Submit finds no signature, reveal the signature step before showing the message; new `signature_missing` copy | `static/signature.js`, `i18n.py` | S | none | A-1 |
| **UX-2** | blocker | A · Guest form | Stay hub · all done | Remove the duplicate primary "Add another person" (`stay.html:113–117`). Keep a quiet in-card option; new done copy + `all_done_receipt` | `templates/guest/stay.html`, `routes/guest.py` (masked e-mail to context), `i18n.py`, `guest.css` | S | **prerequisite for PLAN_POPLATEK G5** (otherwise two coral buttons) | A-2 |
| **UX-3** | blocker | B · Auth | Recovery codes | Hide the language switch on the one-shot recovery page (block override) and move "can't be shown again" above the codes | `auth_base.html`, `two_factor_recovery.html`, `host_i18n.py` | S | No | B-1 |
| **UX-4** | blocker | B · Auth | 2FA code / chrome | Add `lang_next` so the switch on the 2FA page goes to `/login`; add `GET /login/2fa` → 303 `/login?notice=2fa_expired` so a JSON 405 can't appear | `auth_base.html`, `two_factor_login.html`, `routes/admin_accounts.py` | S | No (notice rendering is in B-12; the redirect alone works without it) | B-2 |
| **UX-5** | blocker | B · Auth | 2FA code | "Lost your phone? Use a recovery code" `<details>` with a text-keyboard recovery field, plus a "no codes? email support@" line | `two_factor_login.html`, `host_i18n.py`, `app.css` | S | No | B-3 |
| **UX-6** | blocker | E · E-mail | claim / claim_resend | Keep the `#c=` secret across the PIN gate: `_safe_return_to` preserves the fragment; `signature.js` appends `location.hash` to the PIN form's `return_to`; TestClient round-trip test. Add the "asked for a PIN?" line to `mail_claim_next_body` (EN/CS) | `routes/guest.py`, `static/signature.js`, `i18n.py`, `tests/test_claim_mail.py` | S | Same mechanism the invoice plan reuses for `/invoice/r/{token}` links if those are ever PIN-gated; no conflict | E-1 |
| **UX-7** | blocker | E · E-mail | submission_problem (transport) | Add the missing `mail.submission_problem.reason_transport` key EN/CS, plus a test that no raw `mail.` key text appears in either part | `host_i18n.py`, `tests/test_submission_mail.py` | S | no | E-2 |
| **UX-8** | blocker | C · Host app | Host guest form | Move the verify-identity `<form>` out of the main guest form (button uses `form="verify-{id}"`); add a nesting regression test | `templates/guest_form_admin.html`, `tests/test_host_guest_form.py` | S | Stay-fee plan adds a host guest-form field (§13.3 "host guest form"), so land C-1 first | C-1 |
| **UX-9** | blocker | D · Public site | Landing hero + product + guide + final CTAs | ⚑ Replace "Try UbyHost" → `/login` with "Request access" / "Požádat o přístup" → localized `mailto:support@…` plus a visible address line, at all 5 call sites | `landing_i18n.py`, `landing.html`, `product.html`, `public_guide.html`, `tests/test_public_seo.py` | S | No. Pairs with B's `login.footnote` rewording (surface B) | D-1 |
| **UX-10** | high | A · Guest form | Chrome · language | ⚑ Fall back to `Accept-Language` (cs/sk→cs, else en); endonym labels; 44 px pill | `routes/guest.py::_language`, `guest/base.html`, `guest.css`, `tests/test_guest_language.py` (intentional update) | S | none. **Needs Joe's OK** (current CS default is deliberate) | A-3 |
| **UX-11** | high | A · Guest form | Form · step 1/2 | Accent-folded country sort + "Most common" optgroup | `codelists.py`, `templates/guest/form.html`, `i18n.py` | S | none (also benefits the plan's invoice `buyer_country` select) | A-4 |
| **UX-12** | high | A · Guest form | Stay hub · saved | `just_reported` only when `submit_state == SENT`; revive the saved copy; new saved/locked strings | `routes/guest.py`, `i18n.py` | S | none | A-5 |
| **UX-13** | high | A · Guest form | Claim · sent | Remove the staging sentence; hide the form behind a "didn't arrive?" disclosure; show the masked address + PIN-again hint | `templates/guest/claim.html`, `i18n.py` | S | none | A-6 |
| **UX-14** | high | A · Guest form | Form · final step | "Check before you send" review list with per-row Change → step | `templates/guest/form.html`, `static/signature.js`, `guest.css`, `i18n.py` | M | none (review list should later include doc type from PLAN_POPLATEK §9.1) | A-7 |
| **UX-15** | high | A · Guest form | Form · DOB | New hint, live localized read-back, ISO paste fix | `static/signature.js`, `templates/guest/form.html`, `i18n.py` | S | none | A-8 |
| **UX-16** | high | A · Guest form | Form · passport | Show `passport_photo_missing` + focus Take photo when Continue fails on the hidden file input | `static/signature.js` | S | none | A-9 |
| **UX-17** | high | A · Guest form | Form · wizard | `history.pushState` per step + `popstate` → `show()`, so OS back gestures don't discard the form | `static/signature.js` | S | none | A-10 |
| **UX-18** | high | A · Guest form | Form · passport copy | Plain `passport_photo_help`/`_hint`/`_pending_nat`/`legal_notice_passport_body` | `i18n.py` | S | none | A-11a |
| **UX-19** | high | A · Guest form | Form · legal notice | ⚑ Plain-language legal bodies, remove disclaimer from the step, shorter ack; fix the sticky-submit selector | `i18n.py`, `templates/guest/_legal_notice.html`, `guest.css` | S | **ship before** PLAN_POPLATEK G3 (`legal_notice_stay_fee_*`); lawyer glance | A-11b |
| **UX-20** | high | A · Guest form | Unavailable · no stays | "Registration opens a few days before arrival" copy | `i18n.py` | S | none | A-14 |
| **UX-21** | high | B · Auth | Login, 2FA, setup, password | Move all auth error literals (routes + `auth.password_error`) to `auth.error.*` / `auth.password.*` keys with EN+CS | `routes/admin_accounts.py`, `auth.py`, `host_i18n.py`, templates | M | No | B-4 |
| **UX-22** | high | B · Auth | Login → first-run screens | Persist the resolved language cookie on successful login / 2FA so a Czech login doesn't flip to English | `routes/admin_accounts.py` | S | No (overlaps Surface C's language default; coordinate) | B-5 |
| **UX-23** | high | B · Auth | Login | "Forgot your password?" disclosure under the password field, pointing to `operator().email`; reword the footnote | `login.html`, `host_i18n.py`, `app.css` | S | No | B-6 |
| **UX-24** | high | B · Auth | 2FA setup | `otpauth://` "Add to authenticator app on this phone" button, setup key grouped in 4s with Copy, no "TOTP" jargon, localized QR alt | `two_factor_setup.html`, `routes/admin_accounts.py`, `host_i18n.py`, small auth JS | M | No | B-7 |
| **UX-25** | high | E · E-mail | claim, claim_resend | Subjects name the property, drop "Prague", distinguish resend; add `mail_claim_preheader` and `mail_claim_resend_heading` | `i18n.py`, `mail_notify.py` (subject formatting, heading switch), `claim.py:_guest_mail_subject`, tests asserting old subject | S | no | E-3 |
| **UX-26** | high | E · E-mail | all guest kinds + reminder_host | Format dates with `validation.fmt_date_range` / `fmt_date` in `claim.py` (lines 335, 667) | `claim.py`, `tests/test_guest_mail.py` fixtures | S | Stay-fee/invoice mails will reuse `_guest_mail_content` dates, so fix first | E-4 |
| **UX-27** | high | E · E-mail | reminder_host | Split next steps (claimed/unclaimed) and drop the non-existent "send a fresh link"; add filled/expected to subject and intro; drop the fact row when unclaimed | `host_i18n.py` (EN+CS), `mail_notify.build_reminder_host`, `claim.sweep_reminders` | S | no | E-5 |
| **UX-28** | high | E · E-mail | submission_problem (transport) | Transport-specific subject, label and next steps ("retrying automatically") | `host_i18n.py`, `mail_notify.build_submission_problem/_build_text/_build_html` | S | no | E-6 |
| **UX-29** | high | E · E-mail | completion | Closure copy ("You're all set — nothing else to do"), property in subject, disclaimer rewritten without "UbyPort" and demoted to a muted line, "Open my stay" demoted to a text link | `i18n.py`, `mail_notify.build_completion`, `claim.py` fallback text, tests | S | **Must land before PLAN_POPLATEK §10.3**; defines the no-fee baseline the fee variant branches from | E-7 |
| **UX-30** | high | C · Host app | Property form | Hidden first submit so Enter always saves; move Test/Refresh out of the main form or make them "Save and test" | `templates/apartment_form.html`, `routes/admin.py::test_connection`, `host_i18n.py` | S | Stay-fee §7.2 panel sits in the same `<form>`; do C-2 first | C-2 |
| **UX-31** | high | C · Host app | Stay detail | New `hint.all_reported` for reported stays; rewrite `hint.nothing_duty` / `hint.not_ready` (no passport requirement) | `reporting.py::send_controls`, `host_i18n.py` | S | — | C-3 |
| **UX-32** | high | C · Host app | Stay detail | State banner for cancelled, ignored or archived stays; hide copy-link primary and deadline when not active | `templates/reservation_detail.html`, `host_i18n.py` | S | — | C-4 |
| **UX-33** | high | C · Host app | Stay detail | `hint.missing_guests` with counts and an inline "Change guest count" link opening the settings | `reporting.py`, `templates/reservation_detail.html`, `host_i18n.py` | S | — | C-5 |
| **UX-34** | high | C · Host app | Cross-cutting | Translate all `_back(err=…)` / `msg=` literals via `_flash` keys (EN and CS) plus a grep test | `routes/admin.py`, `routes/onboarding.py`, `routes/exports.py`, `host_i18n.py`, new test | M | Stay-fee §11.3 and invoice §8 route stubs use EN literals (`msg="Saved."`, `err="No such guest."`); update the plans to use `_flash` keys | C-6 |
| **UX-35** | high | C · Host app | Property form / host guest form / stay detail | Share the CS validation-message table and localise `issue.message` on host renders | `routes/guest.py` → shared module, `routes/admin.py`, `templates/apartment_form.html`, `templates/guest_form_admin.html`, `templates/reservation_detail.html` | M | — | C-7 |
| **UX-36** | high | C · Host app | First run | Calendar step done by feed **or** manual stay; copy offers "Add a stay by hand" | `onboarding.py`, `host_i18n.py` | S | — | C-8 |
| **UX-37** | high | C · Host app | First run / Automation | Step 4 renamed "Police reporting details" → `/apartments/{id}#ubyport`; Automation card lists missing items with links | `onboarding.py`, `templates/automation.html`, `routes/admin.py::automation_view`, `host_i18n.py` | S | — | C-9 |
| **UX-38** | high | C · Host app | Overview | Zero-stay empty state: "Connect a calendar" when no feed; hide header sync until a feed exists; suppress "Finish setup" while the onboarding banner shows | `templates/dashboard.html`, `templates/_components.html`, `host_i18n.py` | S | — | C-10 |
| **UX-39** | high | C · Host app | Overview | Focus card first; onboarding finish card moves below the queue or shrinks to a one-line banner when something is overdue or urgent | `templates/dashboard.html`, `templates/_components.html`, `app.css` | S | — | C-11 |
| **UX-40** | high | C · Host app | Chrome | Cap the alert stack at 2 plus a "N more" link; merge alerts per reservation; move off the header zone (bottom-right desktop, strip under the app bar on mobile) | `templates/base.html`, `alerts.py::present_many`, `static/app.css`, `host_i18n.py` | M | Invoice plan adds the `invoice_requested` alert kind; the cap keeps it from stacking | C-12 |
| **UX-41** | high | C · Host app | Guest links | Bilingual (EN + CS) portal message whatever the UI language; "Copy English only" in the ⋯ menu | `templates/guest_links.html`, `templates/apartment_form.html`, `templates/_components.html` (finish card), `host_i18n.py` | S | — | C-13 |
| **UX-42** | high | C · Host app | Stays list | Collision-proof manual `uid` plus disable submit on submit (no 500 on double-click) | `routes/admin.py::reservation_create`, `static/app.js` | S | — | C-14 |
| **UX-43** | high | C · Host app | Property form | "Ready to invite guests" / "Ready to report" checklist replacing the run-on banner; tag reporting-required fields | `templates/apartment_form.html`, `routes/admin.py::apartment_detail`, `host_i18n.py`, `app.css` | M | Stay-fee §7.2 and invoice §3.5 add fields; the checklist must not count them as required | C-15 |
| **UX-44** | high | D · Public site | Shared chrome | Extract `_public_header.html` / `_public_footer.html` (one footer link set, incl. Host login) and include them in the 4 public templates | 4 public templates, 2 new partials | M | No | D-2 |
| **UX-45** | high | D · Public site | Shared chrome | Mobile nav: show nav as a scrollable second row or `<details>` menu below 900px; never hide Log in | `_public_header.html` (after D-2), `landing.css`, `landing_i18n.py` (`landing.nav.menu`) | S | Depends on D-2 | D-3 |
| **UX-46** | high | D · Public site | Shared chrome | Demote header "Log in" from coral pill to a quiet text link, so each viewport has one primary | `landing.css` | S | No | D-4 |
| **UX-47** | high | D · Public site | Legal notice / Terms / Privacy / DPA / Subprocessors | New `public_legal_base.html` (public header/footer, language switch, no host dialogs/app.js); "Back to UbyHost" replaces "Back to login" | 5 legal templates, new base, `host_i18n.py` (`legal.back_home`) | M | Depends on D-2 | D-5 |
| **UX-48** | high | D · Public site | Terms / Privacy / DPA | Section anchors + collapsible TOC + back-to-contents | `terms.html`, `privacy.html`, `dpa.html`, `host_i18n.py` (`legal.toc`, `legal.back_to_toc`), `app.css` or `landing.css` | S | Best after D-5 | D-6 |
| **UX-49** | medium | A · Guest form | Claim | Condensed `claim_title`/`help`/`email_help`/`cookie_help` (all DESIGN.md points kept); move `_why` below back | `i18n.py`, `templates/guest/claim.html`, `templates/guest/assigned.html` | S | none | A-12 |
| **UX-50** | medium | A · Guest form | All | `nights_label()` plural helper (EN 1 night; CS noc/noci/nocí) | `templating.py`, `i18n.py`, `templates/guest/{pick,claim,assigned,form,stay,confirm}.html` | S | PLAN_POPLATEK `fee_line` should reuse it | A-13 |
| **UX-51** | medium | A · Guest form | Form · chrome | Compact one-line stay/person header, step titles in the sticky bar, `_why` + host message as `.g-fold` | `templates/guest/form.html`, `static/signature.js`, `guest.css`, `i18n.py` | M | none | A-15 |
| **UX-52** | medium | A · Guest form | Stay hub · incomplete | Move "Add a person" under progress; always show plural-free `still_missing`; collapse summaries | `templates/guest/stay.html`, `guest.css`, `i18n.py` | M | **changes PLAN_POPLATEK §10.2 insertion anchor** (update plan text); sets the order ①–⑤ for fee + invoice | A-16 |
| **UX-53** | medium | A · Guest form | Form · passport | Skip the passport step for CZE (dynamic step list) | `static/signature.js`, `templates/guest/form.html` | S | none | A-17 |
| **UX-54** | medium | A · Guest form | Form · purpose + stay summary | Display purpose without code / sentence-case CS; summary country without "GBR-" | `codelists.py`, `validation.py` (display helper only), `routes/guest.py::_person_row` | S | none | A-18 |
| **UX-55** | medium | A · Guest form | Form · errors | Guest-side EN overrides + CS fixes so messages match labels; summary items link to fields/steps | `routes/guest.py`, `templates/guest/form.html`, `static/signature.js` | S | none | A-19 |
| **UX-56** | medium | A · Guest form | Form · child | Parent doc `required` when ticked; `note` issue mapped to the parent field; plain message | `static/signature.js`, `routes/guest.py`, `templates/guest/form.html` | S | none | A-20 |
| **UX-57** | medium | A · Guest form | Form · signature | Kept-signature reassurance as `hint`/`role=status`, new copy (+CS comma) | `templates/guest/form.html`, `static/signature.js`, `i18n.py` | S | none | A-21 |
| **UX-58** | medium | A · Guest form | Form · step 2 | Prefill person 2+ address from the device's last saved guest, with a "Copied from…" hint | `routes/guest.py::_form_context`, `templates/guest/form.html`, `i18n.py` | S | none | A-22 |
| **UX-59** | medium | A · Guest form | All guest pages + guest mail · CS term for the host | ⚑ One CS noun for the guest's contact. **Recommended: "hostitel" in all guest-facing UI and mail (matches DESIGN.md's PO copy table: "Váš hostitel"); "ubytovatel" only inside legal-notice sentences.** A's drafts use "ubytovatel" and must be adjusted if Joe keeps DESIGN.md as is. EN: "your host" everywhere. | `i18n.py`, `docs/DESIGN.md` (only if Joe picks "ubytovatel"), note to both plans' CS copy tables | S | aligns with plan CS copy; coordinate `mail_guest_footer_*` with Surface E | A-23 + E-15 |
| **UX-60** | medium | A · Guest form | `_why` | Fix EN/CS mismatch in `why_point_passport` | `i18n.py` | S | none | A-24 |
| **UX-61** | medium | A · Guest form | Chrome | 44 px targets: back link, Clear, host tel/mailto, message summary; strip `tel:` spaces | `guest.css`, `templates/guest/_host.html` | S | the plan's `.g-copy` buttons already `slim` (≥44 px ✓) | A-25 |
| **UX-62** | medium | B · Auth | Recovery codes | Don't regenerate codes on a re-POST when 2FA is already enabled (redirect to Settings) | `routes/admin_accounts.py` | S | No | B-8 |
| **UX-63** | medium | B · Auth | Recovery codes | Copy all + Print actions, `.auth-codes` class, print stylesheet, clearer lede (EN/CS) | `two_factor_recovery.html`, `app.css`, `host_i18n.py`, small auth JS | S | No (shares the JS with B-7) | B-9 |
| **UX-64** | medium | B · Auth | Login + chrome | ⚑ One short acceptance line under the button; remove the footer `legal.use_acceptance` paragraph from auth pages (legal sign-off) | `login.html`, `auth_base.html`, `host_i18n.py`, `app.css` | S | No | B-10 |
| **UX-65** | medium | B · Auth | Login | Keep `next` across failed attempts; move autofocus to the password field on error re-renders | `login.html`, `routes/admin_accounts.py` | S | No | B-11 |
| **UX-66** | medium | B · Auth | Chrome / Login / Logout | Coded notices (`?notice=form_expired | 2fa_expired | logged_out`) rendered in auth_base from i18n keys; point the CSRF-expired redirect and logout at them | `auth_base.html`, `security.py`, `routes/admin_accounts.py`, `host_i18n.py` | B-12 |
| **UX-67** | medium | B · Auth | First-run screens | "Step N of 3" in the ledes (production, 2FA pending) + "Not you? Log out" POST form in auth_base | `account_password.html`, `two_factor_setup.html`, `two_factor_recovery.html`, `auth_base.html`, `host_i18n.py` | S | No | B-13 |
| **UX-68** | medium | B · Auth | 2FA code | Localized lockout copy that says "log in again from the start" with a link; clock-drift hint on invalid code | `two_factor_login.html`, `host_i18n.py` | S | Depends on B-4 | B-14 |
| **UX-69** | medium | B · Auth | 2FA setup | Accept "123 456": strip spaces server-side, drop `pattern`, `maxlength=7` | `two_factor_setup.html`, `routes/admin_accounts.py` | S | No | B-15 |
| **UX-70** | medium | B · Auth | Password (both) | Field-level errors with `aria-invalid` / `aria-describedby`; hint linked; "Temporary password" label in forced mode | `account_password.html`, `routes/admin_accounts.py`, `host_i18n.py` | S | Depends on B-4 | B-16 |
| **UX-71** | medium | B · Auth | Admin hand-off (`users.html`) | Credential panel says 2FA was reset too, and gives the login URL + first-login steps | `users.html`, `host_i18n.py` | S | No (Surface C file; coordinate) | B-17 |
| **UX-72** | medium | B · Auth | Settings (C overlap) | Self-service "Move to a new phone" (re-enrol 2FA + new recovery codes, needs password + code) | `routes/admin_accounts.py`, `settings.html`, `two_factor_setup.html`, `host_i18n.py` | M | No | B-18 |
| **UX-73** | medium | E · E-mail | completion (+ future invoice) | Refactor `build_completion` into ordered slots (status / money panel / secondary links / closing note / footer) with a new `_block_panel` and a "max one coral button" rule; fee-due subject variant | `mail_notify.py`, `tests/test_guest_mail.py` | M | **Prerequisite for PLAN_POPLATEK §10.3 step 3 and PLAN_GUEST_INVOICE §9 `invoice_issued`**; update those plans to call `_block_panel` instead of four top-level `_block_fact`s | E-22 |
| **UX-74** | medium | E · E-mail | all guest kinds | Centralize Reply-To: `mail_notify.guest_payload(apartment, content, lang)` sets `reply_to` from the entity; `mail.GUEST_KINDS`; test that every guest-kind outbox row has `reply_to` when the entity has an e-mail and never contains `support@` | `mail_notify.py`, `mail.py`, `claim.py` (3 call sites), tests | S | **Protects PLAN_GUEST_INVOICE §9** `invoice_request_link` / `invoice_issued`, whose table omits Reply-To | E-8 |
| **UX-75** | medium | E · E-mail | shell | Button `#ad4942`, 48px tall (padding on td + a); links `#ad4942`; note label `#963e38` | `mail_notify.py` | S | Fee "Pay online" button inherits it | E-9 |
| **UX-76** | medium | E · E-mail | shell (all kinds) | Distinct per-kind preheader keys + invisible spacer so previews don't repeat the intro | `mail_notify.py`, `i18n.py`, `host_i18n.py` | S | Fee/invoice builders add their own preheader key | E-10 |
| **UX-77** | medium | E · E-mail | claim | Move the 30-minute expiry under the button; rewrite as reassurance, not threat (EN/CS) | `mail_notify.build_claim_link`, `i18n.py` | S | no | E-11 |
| **UX-78** | medium | E · E-mail | reminder_guest | Include "X of Y registered"; remove the false "ignore if done"; replace the coral note with the "open on the device where you started / PIN" line | `mail_notify.build_reminder_guest`, `claim.sweep_reminders`, `i18n.py` | S | no | E-12 |
| **UX-79** | medium | E · E-mail | all guest kinds (CS) | Rewrite CS "v %(property)s" constructions with colon/dash; add a `mail_property_fallback` key ("your accommodation" / "vaše ubytování") | `i18n.py`, `mail_notify.property_label` | S | Align PLAN_POPLATEK/INVOICE CS mail strings to the same construction | E-13 |
| **UX-80** | medium | E · E-mail | reminder_host, submission_problem | ⚑ Decide host-mail language (CS default or bilingual subject) until a stored preference exists; stop hard-coding `"lang": "en"` | `claim.py`, `mail_notify.py`, `FOLLOWUPS.md` | S (after decision) | Invoice `invoice_request_host` is specced in Czech ("Host X požádal o fakturu"), which conflicts with the EN-only rule; resolve together | E-14 |
| **UX-81** | medium | C · Host app | Stay detail | Adopt the page grammar (Now / Guests / Payments `#money` / Police reporting / Stay settings); merge the command panel with metrics; merge the two edit places | `templates/reservation_detail.html`, `app.css`, `host_i18n.py` | M | **Prerequisite for** PLAN_POPLATEK §11.2 and PLAN_GUEST_INVOICE §3.5: both insert into `#money` at the same anchor (`:272-274`); add a one-line note to both plans | C-16 |
| **UX-82** | medium | C · Host app | Stay detail | Failed state: fix-first copy, "Send again" button, not coral until an edit post-dates the rejection | `reporting.py`, `templates/reservation_detail.html`, `host_i18n.py` | S | — | C-17 |
| **UX-83** | medium | C · Host app | Stay detail / Stays / Reports | Raw-value leaks: `entered_by`, reservation status pill, "Manual entry" / "Reserved" summary, hard-coded "Doručenka", report mode | `templates/reservation_detail.html`, `templates/reservations.html`, `templates/submissions.html`, `routes/admin.py`, `host_i18n.py` | S | — | C-18 |
| **UX-84** | medium | C · Host app | Cross-cutting | `datetime_local` (Europe/Prague) filter for every displayed timestamp | `templating.py`, `templates/reservation_detail.html`, `submissions.html`, `submission_detail.html`, `guest_form_admin.html`, `_components.html` | S | Invoice list and stay-fee "paid on" should use it too | C-19 |
| **UX-85** | medium | C · Host app | Cross-cutting | Plural helper `tp()` (one/few/many) and fixes for nights, calendars, imported stays, ready counts; remove "(s)/(ů)" | `host_i18n.py`, `templating.py`, templates using those keys, `routes/admin.py` | M | Stay-fee `stay.fee.nights` / `to_review` need `.one/.few` too; the plan should use `tp()` | C-20 |
| **UX-86** | medium | C · Host app | Overview / Stay detail / lists | ⚑ Rename `not_required` "Exempt/Výjimka" to "No report needed / Nehlásí se" | `host_i18n.py` | S | **Conflicts with** the stay-fee "Exempt / Osvobodit" decision; ship before the stay fee | C-21 |
| **UX-87** | medium | C · Host app | Overview | `next_action` branches for reported and not_required; rename "Recently completed"; counts in section headings; column "When" | `templates/_components.html`, `templates/dashboard.html`, `host_i18n.py` | S | — | C-22 |
| **UX-88** | medium | C · Host app | Cross-cutting | Flash confirmations say what + next (stay created, saved, guest saved, property saved with missing fields, connection ok, claim released) | `routes/admin.py`, `host_i18n.py` | S | Stay-fee §11.3 `msg="Saved."` should adopt `stay.fee.saved` | C-23 |
| **UX-89** | medium | C · Host app | Status colours | "ID not checked" pill → blue "Ready to report" plus secondary note; setup-incomplete amber everywhere | `templates/_components.html`, `templates/apartments.html`, `templates/automation.html`, `host_i18n.py` | S | — | C-24 |
| **UX-90** | medium | C · Host app | Chrome | PIN-free regenerate flash (no secret in URL) | `routes/admin.py::regenerate_pin`, `host_i18n.py` | S | — | C-25 |
| **UX-91** | medium | C · Host app | First run / Property form | New property defaults to Manual; rewrite `automation.new_lede` | `templates/apartment_form.html`, `host_i18n.py` | S | — | C-26 |
| **UX-92** | medium | C · Host app | First run / Operators | Rename "Legal entity / Právnická osoba" to "Operator / Provozovatel" in host strings; mark seat, IČO and e-mail required; fix the "prepare" copy | `host_i18n.py`, `templates/entities.html` | S | Stay-fee §8 and invoice H1 extend `entities.html`; the rename should precede them so new strings use the new noun | C-27 |
| **UX-93** | medium | C · Host app | Stay detail / House book | CS labels: Státní občanství, hlavní host, Datum narození, guests note rewrite, email hint | `host_i18n.py` | S | — | C-28 |
| **UX-94** | medium | C · Host app | Property form | Section nav "Police reporting" → `#ubyport`; fix the automation-panel sentence about credentials | `templates/apartment_form.html`, `host_i18n.py` | S | Stay-fee §7.2(a) adds a nav link after `#communication`; keep order consistent (Payments after Guest link) | C-29 |
| **UX-95** | medium | C · Host app | Property form | ⚑ One "Payments / Platby" panel for stay fee plus invoice toggle (resolves the plan conflict) | docs only now (`PLAN_POPLATEK §7.2`, `PLAN_GUEST_INVOICE §3.5`) | S | **Conflict between the plans** on where the invoice toggle lives | C-30 |
| **UX-96** | medium | C · Host app | Reports detail | "Open the stay to fix" CTA; header-help link to the property; describe() fallback without "Doručenka" | `templates/submission_detail.html`, `routes/admin.py::submission_detail`, `ubyport/errors.py`, `host_i18n.py` | S | — | C-31 |
| **UX-97** | medium | C · Host app | Stays list / Properties | EN "Apartment" → "Property" in stays keys; the empty state names one first step (operator vs property) | `host_i18n.py`, `templates/apartments.html` | S | — | C-32 |
| **UX-98** | medium | C · Host app | Stays list | Hide toolbar and filters when there are no properties; gate the demo button on `demo_available` | `templates/reservations.html` | S | — | C-33 |
| **UX-99** | medium | C · Host app | First run | Onboarding "Do this now" not duplicated in the list; plainer welcome/finish copy (EN and CS drafts above) | `templates/_components.html`, `host_i18n.py` | S | — | C-34 |
| **UX-100** | medium | C · Host app | Settings | Operator diagnostics behind admin or a collapsed "Technical details" | `templates/settings.html` | S | — | C-35 |
| **UX-101** | medium | D · Public site | Terms / Privacy / DPA | Reading type: 16px ink-secondary, 70ch measure, hairline sections instead of a card per clause | CSS for `.terms-section` | S | After D-5 | D-7 |
| **UX-102** | medium | D · Public site | Landing demo reel | Play once then rest on scene 4 with Replay; transitions 180ms `--ease-standard`, no overshoot | `landing.js`, `landing.css` | S | No | D-8 |
| **UX-103** | medium | D · Public site | Landing demo reel | Move `aria-live` off the auto-advancing caption | `landing.html`, `landing.js` | S | No (can ship with D-8) | D-9 |
| **UX-104** | medium | D · Public site | Landing demo reel + body | Remove glow/sticker decoration: `.demo-float` chips, blur blobs, coloured button shadow, final-band rings; tone the body wash down to app.css level | `landing.html`, `landing.css` | S | No | D-10 |
| **UX-105** | medium | D · Public site | Landing hero | Concrete H1 + lede ("…reports them to UbyPort") EN/CS | `landing_i18n.py` | S | No | D-11 |
| **UX-106** | medium | D · Public site | Landing hero / chrome | ⚑ Add independence line "not operated or endorsed by the Czech Police or UbyPort"; rename bare "UbyPort" nav/footer labels to "Guides" | `landing_i18n.py`, `landing.html` (or partials) | S | No | D-12 |
| **UX-107** | medium | D · Public site | Landing final CTA | ⚑ Use the locked tagline "Guest reporting, handled for you." / "Hlášení hostů vyřídíme za vás." as the final title (replacing "autopilot") | `landing_i18n.py` (+ B: `login.hero_title` CS) | S | Coordinate with surface B | D-13 |
| **UX-108** | medium | D · Public site | Shared chrome | Nav labels = destinations: How it works / Pricing / Guides; one name for `/jak-to-funguje` | `landing_i18n.py`, header partial | S | After D-2 | D-14 |
| **UX-109** | medium | D · Public site | Pricing | One-sentence price summary under "By agreement"; CTA aligned to "Request access and a price"; localized mailto subject; visible address | `landing_i18n.py`, `pricing.html`, `tests/test_public_seo.py` | S | After D-1 (shares keys) | D-15 |
| **UX-110** | medium | D · Public site | Landing body / pricing / product | Replace decorative blue/amber/green/purple card tints + shadowed cards with a hairline list (tokens.css "never decoration") | `landing.html`, `pricing.html`, `product.html`, `landing.css` | M | No | D-16 |
| **UX-111** | medium | D · Public site | Legal pages | Linkify raw "/dpa", "/legal", "/privacy", "/terms" in legal bodies via a template filter (no copy change) | `templating.py` (filter), 4 legal templates | S | No | D-17 |
| **UX-112** | medium | D · Public site | Product / pricing / landing | ⚑ One public term for the guest book feature (EN/CS), owner-confirmed | `landing_i18n.py` | S | No | D-18 |
| **UX-113** | low | A · Guest form | Form · step 1 | Hide visa for CZE/EU/EEA/CH | `static/signature.js` | S | **frees room for** PLAN_POPLATEK §9.1 doc-type | A-26 |
| **UX-114** | low | A · Guest form | Assigned | Gate back/not-mine on `can_pick_other`; `date_cz` last-sent; single masked e-mail + new body | `templates/guest/assigned.html`, `i18n.py` | S | none | A-27 |
| **UX-115** | low | A · Guest form | Pick | "Not started yet"; "Arriving today"; muted status colour; drop the duplicate kicker | `templates/guest/pick.html`, `routes/guest.py`, `i18n.py`, `guest.css` | S | none | A-28 |
| **UX-116** | low | A · Guest form | Confirm | `claim_confirm_help` → "One tap to confirm it's really you." + nights | `i18n.py`, `templates/guest/confirm.html` | S | none | A-29 |
| **UX-117** | low | A · Guest form | Privacy | ⚑ Remove support@ from the processor paragraph; drop staging/Bot Fight jargon | `i18n.py` | S | none; lawyer glance | A-30 |
| **UX-118** | low | A · Guest form | Unavailable | `form_expired_help` without "Reload"; no `_why`; no "Start again" on locked/filed | `i18n.py`, `templates/guest/unavailable.html`, `routes/guest.py` | S | invoice plan §3.1 D wants an invoice link here → use the `show_invoice_link` flag | A-31 |
| **UX-119** | low | A · Guest form | PIN | `aria-invalid`/`describedby` on the PIN input when an error is shown | `templates/guest/pin.html` | S | none | A-32 |
| **UX-120** | low | A · Guest form | Chrome · CSS | Fix `--g-text`/`--g-border`; remove unused selectors; sentence-case kickers | `guest.css` | S | none | A-33 |
| **UX-121** | low | A · Guest form | Form · inputs | `spellcheck=false autocorrect=off` on doc/visa; `address-line1`; `autocomplete=country`; residence help w/o "abroad" | `templates/guest/form.html`, `i18n.py` | S | none | A-34 |
| **UX-122** | low | A · Guest form | All · dates | Optional: "." DOB separator + placeholder/messages to match displayed dates | `static/signature.js`, `i18n.py`, `routes/guest.py` | S | none | A-35 |
| **UX-123** | low | B · Auth | Chrome | 44px tap targets for the language switch and "Remember me" | `app.css` | S | No | B-19 |
| **UX-124** | low | B · Auth | Login | Swap h1/lede ("Log in to UbyHost" / "Přihlášení do UbyHostu"); fix "do UbyHostu" | `host_i18n.py` | S | No | B-20 |
| **UX-125** | low | B · Auth | Chrome | ⚑ Fix logo sizes to LOGO.md (220 / 300px) by removing the `app.css:2894` / `:2959` overrides, or update LOGO.md (owner's call) | `app.css` or `docs/LOGO.md` | S | No | B-21 |
| **UX-126** | low | B · Auth | 2FA setup / password | Explicit `_csrf` hidden inputs (no JS dependency); replace inline styles on the 2FA templates with classes | `two_factor_setup.html`, `account_password.html`, `two_factor_recovery.html`, `app.css` | S | No | B-22 |
| **UX-127** | low | B · Auth | Copy polish | Unify "Security code" naming; CS "relace" → "zařízení"; "autentizátor" rewording; "Use a different account" for Start over; change-password success → Settings | `host_i18n.py`, `routes/admin_accounts.py` | S | No | B-23 |
| **UX-128** | low | B · Auth | Login | Turnstile `data-language="{{ lang }}"` | `login.html` | S | No | B-24 |
| **UX-129** | low | B · Auth | First-run | Keep the "remember me" flag when re-issuing the session after password change / 2FA enable | `routes/admin_accounts.py` | S | No | B-25 |
| **UX-130** | low | B · Auth | Password (both) | Hidden `autocomplete="username"` field so password managers update the right entry | `account_password.html` | S | No | B-26 |
| **UX-131** | low | E · E-mail | shell footer | Host e-mail/phone as `mailto:`/`tel:` links; replace bare "UbyHost" with `mail_guest_footer_about` | `mail_notify._guest_footer_lines/_shell`, `i18n.py` | S | no | E-17 |
| **UX-132** | low | E · E-mail | shell | Sentence-case 14px labels instead of uppercase letter-spaced | `mail_notify.py` | S | Fee panel labels follow | E-18 |
| **UX-133** | low | E · E-mail | shell | Side padding 32 → 24px for the 375px column | `mail_notify.py` | S | no | E-24 |
| **UX-134** | low | E · E-mail | dates_changed | Remove the dead kind from `KINDS` and `SES.md` (or spec a real guest mail separately) | `mail.py`, `docs/SES.md` | S | no | E-16 |
| **UX-135** | low | E · E-mail | claim/completion/reminder fallbacks | Build the fallback plain text from the same i18n keys instead of hard-coded strings in `claim.py` | `claim.py` | S | no | E-19 |
| **UX-136** | low | E · E-mail | submission_problem | Accurate footer; EN "report receipt (Doručenka)"; single primary when one stay | `host_i18n.py`, `mail_notify.py` | S | no | E-20 |
| **UX-137** | low | E · E-mail | mail_failed alert | "E-mail could not be sent" (not "Guest") and a human kind label instead of raw `reminder_host` | `host_i18n.py:628,1662`, `mail.py:397-410` | S | Invoice kinds show up here too | E-21 |
| **UX-138** | low | E · E-mail | claim_resend | "Everyone is already registered" variant of next steps when the stay is complete | `mail_notify.py`, `i18n.py` | S | no | E-25 |
| **UX-139** | low | E · E-mail | shell | ⚑ `<meta name="color-scheme" content="light only">`, **only with PO sign-off**: two tests pin "no color-scheme" | `mail_notify._shell`, 2 test assertions | S | no | E-23 |
| **UX-140** | low | C · Host app | Guest links | "Preview as a guest" link | `templates/guest_links.html`, `host_i18n.py` | S | — | C-36 |
| **UX-141** | low | C · Host app | Stay detail | Placeholder rows for missing guests | `templates/reservation_detail.html`, `host_i18n.py` | S | Stay-fee headcount warning (§11.2) covers the same fact; keep one wording | C-37 |
| **UX-142** | low | C · Host app | Chrome | Support line on its own row; `lang.cs` "CS"; `aria-label` on the palette input; one `<h1>` on the zero state | `templates/base.html`, `templates/dashboard.html`, `host_i18n.py` | S | — | C-38 |
| **UX-143** | low | C · Host app | Properties | Automation column as plain text; icon in "Add a property" | `templates/apartments.html` | S | — | C-39 |
| **UX-144** | low | C · Host app | Users | `data-confirm` on disable user; de-jargon the lede | `templates/users.html`, `host_i18n.py` | S | — | C-40 |
| **UX-145** | low | C · Host app | Stays list | Filter "Apply" neutral, not coral | `templates/reservations.html` | S | — | C-41 |
| **UX-146** | low | C · Host app | Reports | Mode via `reports.mode.*`; Endpoint into Technical details; country names; receipts hint copy; empty transport table message | `templates/submissions.html`, `templates/submission_detail.html`, `host_i18n.py` | S | — | C-42 |
| **UX-147** | low | C · Host app | Overview | "0 / ?" → "—" with title; `action.ready_immediate` rewrite; CS guest-forms grammar | `templates/dashboard.html`, `templates/reservations.html`, `host_i18n.py` | S | — | C-43 |
| **UX-148** | low | C · Host app | CSS | Remove the blue glow shadow and the stale "Blue = send to the police" comment on `.btn.accent` (DESIGN: shadows only on floating UI) | `static/app.css` | S | Stay-fee "Mark as paid" uses `btn accent primary`; inherits the fix | C-44 |
| **UX-149** | low | C · Host app | Help | Align CS nouns with the UI (zkratka, odkaz pro hosty, hlavní host) | `host_i18n.py` (guide keys) | S | — | C-45 |
| **UX-150** | low | D · Public site | Shared chrome / demo / product | Move hard-coded template copy (footer "Guest book", guide cards, CS weekday row) into `landing_i18n.py` | `landing.html`, `product.html`, `landing_i18n.py` | S | No | D-19 |
| **UX-151** | low | D · Public site | Landing demo reel | Pause/replay control 44px with SVG icon; "Example"/"Ukázka" label + fake code on mock receipt | `landing.html`, `landing.css`, `landing_i18n.py` | S | After D-8 | D-20 |
| **UX-152** | low | D · Public site | Landing demo / final CTA | Reconcile LOGO.md with code: final mark 64px (not 56), mock mark 28px on `.reel-side img` (doc cites dead `.product-shell`); document or drop the pricing-card 44px mark | `landing.css`, `docs/LOGO.md` | S | No | D-21 |
| **UX-153** | low | D · Public site | Language switch | `<nav aria-label>` wrapper, `aria-current`, 44px tap height on mobile | header partial, `landing.css` | S | After D-2 | D-22 |
| **UX-154** | low | D · Public site | Landing hero | Hero H1 line-height/letter-spacing safe for CS diacritics; eyebrow not a pill on mobile | `landing.css` | S | No | D-23 |
| **UX-155** | low | D · Public site | Product | Remove double numbering on feature rows | `product.html` | S | No | D-24 |
| **UX-156** | low | D · Public site | Landing / pricing / product CS copy | Natural-CS rewrites (benefit.guest.body, pricing kicker/note/eyebrow, product titles) | `landing_i18n.py` | S | No | D-25 |
| **UX-157** | low | D · Public site | Terms | Typo "kterí" → "kteří" | `terms_i18n.py` | S | No | D-26 |
| **UX-158** | low | D · Public site | Legal notice | "ARES (public register)" localized; CS footer "Právní informace"; remove duplicate `legal.footer_*` keys | legal templates, `host_i18n.py` | S | No | D-27 |
| **UX-159** | low | D · Public site | Public guide | Visible per-guide "last checked" date; breadcrumb last crumb = guide title | `public_guides.py`, `public_guide.html`, `landing_i18n.py` | S | No | D-28 |
| **UX-160** | low | D · Public site | SEO head | Landing uses self-referencing canonical from `seo.head_links` | `landing.html` | S | No | D-29 |
| **UX-161** | low | D · Public site | Legal / Subprocessors | ⚑ Owner decision: keep or reword the public "Professional review" panel and the staging-only notes | `terms_i18n.py`, `privacy_policy_i18n.py`, `dpa_i18n.py`, `subprocessors_i18n.py` | S | Owner sign-off (legal text) | D-30 |
| **UX-162** | low | D · Public site | landing.css | Delete dead pre-2026 rules (`.product-window`, `.product-shell`, `.landing-product-stage`, `.landing-proof`, `.landing-how`, `.landing-feature-grid`, `.stage-note`, …) and unused `landing.mock.*`/`landing.proof.*`/`landing.how.*` keys | `landing.css`, `landing_i18n.py` | S | No. Do after D-10/D-16 so live overrides are visible | D-31 |


## What's already right — don't "fix" these

### What's already right (A)

- **Inline error pattern** in `form.html:3–13`: `err_for` + `bad` + `invalid()` produce `aria-invalid="true" aria-describedby="{field}-error"` with matching ids (verified on 4 fields in the rendered 422). The top summary plus `focusFirstError` land the guest on the first bad field, and the wizard opens the first failing step (`signature.js:190`). Covered by `test_guest_a11y.py`.
- **Contact split holds on every guest template.** `_host.html` is included once in `base.html:40`, so it appears on PIN, picker, claim, confirm, assigned, form, stay, privacy and unavailable. With no contact, it shows "Use the phone or e-mail in the message that contained this link", never UbyHost. (Only exception: the privacy processor paragraph, A-30 [UX-117].)
- **The arrival lane matches DESIGN.md:** IA order, always renders even for one stay, the whole row is the button, range cue, hairlines instead of shadows, a 220 ms stagger, coral accent on hover/focus, press settle, reduced motion, a 580 px single column.
- **`_why.html`** is a closed `<details>` on a quieter surface, secondary everywhere ✓ (hypothesis passes; A-15 [UX-51] only makes it more compact on the form).
- **The wizard progress bar is unhidden by JS** and shows visible "Step N of M" text, sticky, with `aria-live="polite"` ✓.
- **Smart, low-typing inputs:** a PIN with `inputmode=numeric` + `one-time-code`; DOB auto-slashing with a numeric keypad and paste normalisation; home country auto-copied from nationality; purpose preset from the property default; `party_size` with a numeric keypad.
- **Signature survives a failed submit** (repainted, with the [F33] validity guard in `_form_context`).
- 16 px inputs (no iOS zoom), whole-row `.checkline` targets, `g-btn` ≥ 44 px, visible `:focus-visible` rings, `color-scheme: light`.
- **The language switch keeps query flags** (`_lang_urls`, so `saved=1` isn't lost). The mail language follows the guest's explicit choice, not the page default (`_mail_language`).
- **Privacy between party members:** other people show only as "Person N — completed / not filled in".
- `_unavailable()` always states which case happened, and the host footer is always present. A Latin-script message points non-Latin names to the passport's MRZ lines.


### What's already right (B)

- **Autocomplete and keyboard hints are correct:** `username` + `autocapitalize=none` + `spellcheck=false` on the login name (`login.html:18-21`); `current-password` / `new-password` on every password field; `one-time-code` + `inputmode=numeric` on both OTP fields. Inputs are 16px (`app.css:2273`), so iOS doesn't zoom. Inputs and the submit are 50px tall (`app.css:2914-2932`).
- **Password rules are stated before the host types** (`account.password.rules` under "New password", both branches), and `minlength=12` stops the most common mistake client-side. Hypothesis §6.B passes.
- **Login is secure without being unfriendly:** one generic credential error (no username enumeration) and a timing-safe dummy hash (`auth.py:177-193`); the username is kept after a failure and the password is never echoed; the lockout is explicit and time-bound.
- **Recovery codes are forgiving on input:** case, dashes and spaces don't matter (`auth.py:64-68`).
- **Mandatory 2FA explains why in plain words** ("UbyHost contains identity documents…"), and the recovery page has one unmistakable action ("I saved them — continue").
- **Logo placements follow LOGO.md:** horizontal lockup in the form, stacked lockup only in the hero, hero hidden below 900px, `mix-blend-mode: multiply`, favicon/apple-touch-icon present, hero `aria-hidden`. Only the sizes drift (B-21 [UX-125]).
- **Accessibility basics are in place:** skip link, `html lang` follows the chosen language, every input has a `<label for>`, errors use `role="alert"`, global `:focus-visible` (`app.css:26`), and inputs have a visible focus ring. `color-scheme: light` and a light `theme-color` are set.
- **The contact is right:** `support@ubyhost.com` (via `operator().email`) is on every auth page, which is the correct contact for hosts per DESIGN.md. It just needs a label and a place in context (B-3 [UX-5], B-6 [UX-23]).
- **An admin recovery path exists** (Reset password also resets 2FA), so a lost device is never permanent. It only needs signposting.
- **Turnstile fails open for a bounded time** during Cloudflare outages (`turnstile.py:63-83`), and the CSP allows it (`main.py:147-152`).


### What's already right (C)

- **The contact split holds.** `support@ubyhost.com` is in the sidebar footer (`base.html:134-137`, defaulting through `config.OPERATOR_EMAIL`) and in Settings → Software operator (`settings.html:220-223`). No guest-facing link in the host chrome points guests at support.
- **Key parity is real.** `tests/test_host_i18n.py::test_english_and_czech_carry_the_same_keys` passes. A scan of every static `t('…')` in the 19 in-scope templates found **no key missing** in either language, and no raw i18n key renders. The leaks above are hard-coded literals and DB values, not missing keys.
- **The focus card** ("Past the deadline / Next up", `dashboard.html:98-142`) and the `reporting.queue_groups` single-bucket design put legal urgency first. Keep them; only move the onboarding card.
- **The "Next step" command panel on stay detail** (`reservation_detail.html:15-43`) is the right pattern: one sentence plus one coral action chosen by state. The fixes are copy and state coverage, not structure.
- **Create flows chain into the next step:** "Added X. Next, add your first property." then "Property created. Next, paste your … calendar link." landing on `#calendars`. That's exactly the what + next bar.
- **Every truly destructive action already goes through the `data-confirm` dialog.** The one exception is Disable user. Stay-row archive uses an **Undo toast** instead, which is better. The dialog uses the product tokens and `admin-dialog` styles.
- **Row actions live in overflow menus** (`row_menu_begin/end`), as DESIGN.md asks. Copy-guest-link is the one inline row action, which is justified (chasing a guest is one click).
- **The calendar CTA uses an everyday Czech verb**, "Aktualizovat kalendáře", with an icon (`sync_calendars_button`), matching the DESIGN.md example.
- **The mobile table → card transform** (`.table-cards` with `data-label`, `app.css:1705-1720`) keeps every list usable on a phone without separate templates.
- **`prefers-reduced-motion`** is honoured through the tokens (`--motion-*` collapse to 0.01 ms). No looping motion was found in `app.js`.
- **Accessibility basics:** labelled form controls on every rendered host page (html5lib scan; the only gaps are the palette search and one read-only permalink), a skip link, `aria-live` toasts, `aria-current` on the view switch, and 42 px icon buttons.
- **Plural-correct Czech already exists** in `alerts._plural_key` (one/few/many). Reuse it rather than inventing a new helper.
- **Technical XML on report detail is already tucked away** behind "Technical details". Good disclosure discipline.
- **Logo placements match LOGO.md:** the 28 px mark plus live "UbyHost" in the sidebar, the mark only in the mobile bar, and the onboarding mark.


### What's already right (D)

- **Reduced motion is really honoured** on the demo: JS (`landing.js:11-16,53-61`) jumps to the final scene, pauses, disables the toggle, and listens for preference changes. CSS (`landing.css:1300-1313`) kills every keyframe and transition. The loop also stops on hidden tabs.
- **Language handling is deliberate and tested.** Explicit `?lang=` beats the cookie, which beats the Czech default. `?lang` is remembered like the switcher (`templating.py:149`). Accept-Language is ignored so the canonical is stable (`tests/test_public_seo.py:143-182`). Every public page offers hreflang pairs (except the landing canonical bug, D-29 [UX-160]). Don't "fix" Accept-Language handling.
- **EN/CS key parity for landing copy and guide structure is test-enforced** (`test_landing_copy_has_matching_keys_in_both_languages`, `test_guide_translations_have_matching_content_structure`). No raw keys render on any public page in either language (verified in the renders).
- **Pricing is honest**: no fake tiers and no `Offer` JSON-LD (tested). Keep that stance while adding the summary line.
- **Disclaimers and official sources** ("technical tool, not legal advice" + `ipc.gov.cz` link, the FAQ "Does UbyHost replace UbyPort registration? No…") are on product and guide pages. The guides are careful not to overstate duties.
- **Skip link, landmark structure, and native `<details>` FAQ** on all public pages. The legal pages show the effective date and version.
- **Contact split is correct for this surface:** public pages address prospects and hosts, so `support@ubyhost.com` is the right contact here (DESIGN.md contact split). No guest-facing contact appears.
- **Logo usage:** horizontal lockup at 152px in header/footer (`landing.css:64-69`, stepping down to 132/126px on small screens), `mix-blend-mode: multiply` on every public logo, and no stacked lockup on public pages (tested in `test_logo_placements.py`).
- The subprocessors table's mobile card fallback (`table-cards` + `data-label`) already works.


### What's already right (E)

- **Contact split holds in every shipping kind.** Guest mail Reply-To is the legal-entity contact. The footer says "Your host: <entity>" plus "Reply to this e-mail to reach your host" only when an entity e-mail exists (`mail_notify.py:355`). `support@ubyhost.com` appears only in the host `submission_problem` footer. `tests/test_guest_mail.py:333-334` enforces this. Verified in the rendered outbox rows.
- **Logo exactly per LOGO.md:** `ubyhost-logo.jpg`, `width="180"` attribute plus inline `width:180px;max-width:100%;height:auto`, on a white card, no blend mode (`mail_notify.py:33-34, 316`).
- **Multipart is always sent:** the text part always carries absolute `https://ubyhost.com/...` links and never says "view in HTML". SES sends both parts (`mail.py:318-324`). There's no tracking pixel and no link rewriting.
- **Table-based, inline styles, `width:100%;max-width:600px`, no `@media`, no dark variant.** Nothing overflows at 375px. Long URLs have `word-break:break-all` (`:267`).
- **Magic-link secret hygiene:** the marker is in both parts, the secret is encrypted in the payload and substituted at send, and the console log stores the marker (`mail.py:183-223`).
- **Composer failure never costs the guest their link:** there's a plain-text fallback (`claim.py:311-370`), and host mail failures never fail a filing (`mail_notify.py:580-595`).
- **One-per-day de-dup for host failure mail** (`mail_notify.py:631-634`). There's exactly one guest reminder, and completion is sent once (`completion_notified_at`).
- **The rejected `submission_problem` variant is a good model:** a specific server reason (clamped to 1000 characters), a specific human next step, and a link per affected stay.
- **EN/CS parity for all `mail_*` keys**, enforced by name (`tests/test_guest_mail.py:28-66`).
- **The `From` display name is set** (`mail.display_from`).

## Not doing this — rejected on purpose

Every surface considered dark mode and rejected it, because DESIGN.md and brief §0 rule 2 make the product light-mode only. It's recorded here as a possible **future recommendation** only if Joe asks for it. The optional `color-scheme: light only` meta in mail (E-23) is the opposite of dark mode: it *prevents* inversion.

### Rejected / not doing (A)

- **Dark mode for 11 pm check-ins.** Rejected: §0 rule 2 / DESIGN.md, light mode only.
- **A searchable country combobox via a JS library.** Rejected: §0 rule 1 (no library/framework). Accent-folded sort plus a "Most common" optgroup solves it with a native `<select>`.
- **Preselecting nationality from the browser locale.** Rejected: locale ≠ nationality for travellers. It would create wrong-by-default police data and add a hidden decision (rule 7).
- **Native `<input type="date">` for date of birth.** Rejected: mobile date wheels make a 30–60-year scroll, which is more effort than 8 digits (rule 7). The read-back (A-8 [UX-15]) prevents swaps instead.
- **Splitting step 1 into two wizard steps.** Rejected: rule 7 (adds a step), and PLAN_POPLATEK §9 forbids new `data-guest-step`. A-26 [UX-113] removes a field instead.
- **Letting guests unlock and edit a saved form.** Not a UX call (a legal/record-integrity decision in `reporting.guest_form_locked`). A-7 [UX-14] prevents the mistake before the lock instead.
- **Hiding the whole legal notice behind a collapsed disclosure.** Rejected: DESIGN.md requires collection-time explanation, and the ack asserts "read above". We shorten and de-jargon instead.
- **Removing the confirm tap after the e-mail link.** Rejected: it's the anti-scanner control, not friction to optimise away.
- **Saving form drafts in `localStorage`.** Rejected: passport data would persist on shared or borrowed phones (privacy). The pushState fix (A-10 [UX-17]) covers the common back-gesture loss.
- **Falling back to `support@ubyhost.com` when the host has no contact.** Rejected: the DESIGN.md contact split.
- **Confetti, illustrations or emoji on the all-done screen.** Rejected: DESIGN.md / brief §4 ("motion is a whisper", no emoji).


### Rejected / not doing (B)

- **Dark-mode login for late-night check-ins:** rejected. Light mode only (brief §0.2, DESIGN.md).
- **A password-strength meter library (zxcvbn or similar):** rejected, §0.1 (no new frontend dependency). The static rules line up front already prevents the error. A tiny vanilla "rules met" tick list is possible later, but not needed.
- **Self-serve e-mail password reset or magic-link login:** not in this overhaul. It needs a new `user_account.email` column, a mail kind and a token flow, which is a product/security feature, not UX polish. It's recorded as a future recommendation; B-6 [UX-23] covers the gap with honest copy.
- **Dropping `inputmode=numeric` from the main 2FA field to "fix" recovery codes:** rejected. It would slow the 99% case. B-3 [UX-5] gives recovery codes their own field instead.
- **Replacing "EN / CZ" with flags or full language names:** not doing. It's a cosmetic change with no confusion removed, and flags are a known anti-pattern for language. Only the tap target is fixed (B-19 [UX-123]).
- **Removing the marketing hero from the 2FA/password screens:** not proposed. It's hidden on mobile, where the stress is, and `aria-hidden`. LOGO.md defines it as the login hero, and changing its scope is Joe's call.
- **Making 2FA optional in production to reduce friction:** rejected. The product stores identity documents, and the requirement is deliberate (`auth.py:287-290`).


### Rejected / not doing (C)

- **A dark-mode or "respect system theme" toggle for evening hosts:** rejected. §0 rule 2 and DESIGN.md lock the product to light mode only.
- **Replacing the long property form with a JS multi-step wizard or a component library:** rejected under §0 rule 1 (no framework or bundler). The readiness checklist (C-15 [UX-43]) and anchor links achieve the same "what's left" clarity with the existing server-rendered form.
- **Removing the alert bubbles altogether in favour of the Overview queue:** rejected. Appendix 5 §10.4(2) (cited in `alerts.py:3-6`) requires a prominent, every-screen warning for rejected records. C-12 [UX-40] caps and relocates the bubbles instead.
- **Auto-sending or auto-marking "ID checked" to clear the amber state:** rejected. DESIGN.md says verification "must never be fabricated merely because a report was sent". C-24 [UX-89] changes the colour and wording only.
- **Pointing guests at `support@ubyhost.com` in the bilingual portal message (C-13 [UX-41]):** rejected. DESIGN.md contact split: the message links only to the guest form, whose footer names the host.
- **Replacing the purple/blue `radial-gradient` body wash** (`app.css:15-18`) with brand coral: not doing. The brief cites it as the reference amount of atmosphere. Noted only: it uses semantic hues decoratively, which `tokens.css`'s header comment discourages.
- **Adding counts or colour chips to the Stays table for the stay fee:** rejected, per PLAN_POPLATEK §1.1 and DESIGN.md ("do not crowd tables with many colored chips").


### Rejected / not doing (D)

- **Dark-mode variant of the marketing site** (tempting for the dark "product demo" look competitors use). Rejected: brief §0.2 / DESIGN.md light-only.
- **Web fonts for a more "editorial" hero.** Rejected: §0.1, no CDN fonts. System stack only.
- **A JS hamburger / off-canvas menu library, or a carousel/animation library for the demo.** Rejected: §0.1, vanilla only. The `<details>` or second-row nav needs no JS.
- **A self-serve sign-up/trial flow to make "Try UbyHost" true.** Rejected for this overhaul: it's a product/business change (UbyHost is invite-only by owner decision, per `login.footnote`), not a UX fix. The honest CTA (D-1 [UX-9]) removes the dead end without it.
- **Inventing a published price or "from X Kč" anchor.** Rejected: only Joe can set pricing. D-15 [UX-109] leaves a slot for it.
- **Screenshot/visual-regression harness for the landing.** Rejected: §0.11.
- **Auto-detecting language from Accept-Language.** Rejected: current behaviour is intentional and tested for canonical stability.


### Rejected / not doing (E)

- **Dark-mode mail styles** (`prefers-color-scheme`, `@media (prefers-color-scheme: dark)`, dark logo swap): rejected, brief §0 rule 2 / DESIGN.md light-only. (The optional `color-scheme: light only` meta in E-23 [UX-139] *prevents* inversion; it doesn't add a theme.)
- **Embedding the stay-fee QR as an inline or CID image:** rejected, per PLAN_POPLATEK §10.3 ("inline images are unreliable"). The only remote resource stays the logo (LOGO.md). The mail links to the stay page for the QR.
- **Attaching invoice PDFs:** rejected, per PLAN_GUEST_INVOICE §9 (no attachment support; out of scope).
- **`@media` rules for a mobile-specific button or padding:** rejected. The shell is deliberately media-query-free (`mail_notify.py:283-287`, and tests assert `"@media" not in html`). Mobile fixes are done with fluid values instead (E-9 [UX-75], E-24 [UX-133]).
- **Pointing any guest mail at `support@ubyhost.com`,** even as "technical problems with this link": rejected, DESIGN.md contact split.
- **A second guest reminder, or reminders for unclaimed stays:** rejected. The privacy notice promises exactly one (`i18n.py:86-91`), and it would add guest touchpoints without removing any confusion (brief §0 rule 7).
- **Minting a fresh claim link inside reminder/completion mails** so they work on any device: rejected for now. A new `token_version` logs out the device that confirmed (`routes/guest.py:241-249`). Copy (E-12 [UX-78]) explains the device/PIN path instead.
- **Web fonts or a CSS framework in mail:** rejected, brief §0 rule 1.

## Deferred / future recommendations

- **Self-serve password reset or magic-link login for hosts.** This needs a `user_account.email` column, a mail kind and a token flow. It's a product and security feature, not UX polish. B-6 covers the gap with honest copy for now.
- **Self-serve sign-up or trial on the public site.** This is a business decision (invite-only today). D-1 removes the dead end without it.
- **A per-user host language preference** (stored), which would retire E-14's interim rule.
- **`dates_changed` guest mail.** Spec it properly or drop it from `KINDS` (E-16 removes it for now).
- **Dark mode.** Not recommended and not built, per the owner's standing decision. Listed only because the brief asks for such ideas to be written down, not shipped.
