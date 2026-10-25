# Leon (AI): opt-in screen, terms and legal notes

Prepared 2026-10-25 by AI counsel (not a licensed Czech lawyer), in the same way as `docs/privacy/DOOR_CODES_LEGAL.md` and `docs/privacy/drafts/havel-ai.md`. Reuses the Havel positions: Anthropic, PBC is a UbyHost subprocessor; facts A1 to A6 (global inference, 2021 SCCs Modules 2 and 3, no DPF reliance, 30-day API retention, no training, no ZDR) are relied on as stated there and must be re-checked before live text changes. AI Act Art 50(1) applies from 2 August 2026, as in Havel part 5.

Facts from the code (`App/app/leon.py`, `retention.py`, `RETENTION.md`):
- Sent to Anthropic per model call: the fixed `CHARACTER` prompt; the guide block (all cards for that door and level, host text, property name); up to 6 earlier turns (guest messages, Leon's answers, **host answers as typed**); the new guest message with page language. Guest messages are redacted (`redact`: e-mails, phones, runs of 6+ chars with 4+ digits) before storing and sending; **names, health words and addresses are not removed**. No guest name or registration data is sent.
- Stored: `guest_chat`, `guest_chat_message`, `guest_question`, cookie `ubyhost_leon` (30 days); purged 30 days after checkout (stay) or last message (QR), `leon.purge`. Logs: ids, kinds, counts, reason codes only, never message text.
- Caps: 20 model answers per stay, 10 per QR chat, burst limits, 3 refusals then 24 h pause; past cap/budget/outage the message goes to the host unread by Leon. Emergencies get fixed copy with 112/150/155/158.
- Leon refuses to promise prices, refunds, dates etc. (`ask_host`), and every "answer" must cite existing cards and only use numbers from them.
- Live register is still version 1.2 (no Anthropic); the Havel v1.3 draft row says the guest assistant is "not in use yet".

---

## 1. Host screen warnings (above the checkbox)

**English**
- Leon is an AI. It can misunderstand a question or give a wrong answer. You stay responsible for what your guests are told.
- Leon answers only from your guide cards. Keep them correct and current, and use only text you have the right to use.
- Do not rely on Leon for safety, emergencies, health or getting in. Keep that information elsewhere too and stay reachable.
- Leon cannot promise prices, discounts, refunds or date changes. It passes such requests to you.
- Guest messages, your guide cards and your replies go to our AI provider, Anthropic (USA). Chats are deleted 30 days after the stay.
- Guests can type anything. Do not put other people's personal data in your cards without their permission.

**Česky**
- Leon je umělá inteligence. Může otázku špatně pochopit nebo odpovědět chybně. Za to, co se hosté dozvědí, odpovídáte vy.
- Leon odpovídá jen z vašich karet průvodce. Udržujte je správné a aktuální a používejte jen texty, k nimž máte práva.
- Nespoléhejte na Leona v otázkách bezpečnosti, nouze, zdraví ani vstupu do ubytování. Tyto informace mějte i jinde a buďte k zastižení.
- Leon nemůže slíbit ceny, slevy, vrácení peněz ani změnu termínu. Takové žádosti předá vám.
- Zprávy hostů, vaše karty a vaše odpovědi jdou našemu poskytovateli AI, společnosti Anthropic (USA). Chaty mažeme 30 dní po pobytu.
- Hosté mohou napsat cokoli. Do karet nepište osobní údaje jiných lidí bez jejich souhlasu.

## 2. Checkbox

One checkbox is enough. A second box for "I will inform guests" is **not** needed: UbyHost itself shows the AI label in the chat and adds the Leon paragraph to the property's guest privacy notice (as for door codes), and the host's remaining duty is covered by terms item 10. Two boxes would add friction without adding proof. The terms link must open the full text (anchor `/guide#leon-terms`) and the box must be unticked by default; the Switch-on button stays disabled until it is ticked.

- **en:** I have read the [Leon (AI) terms](/guide#leon-terms) (version 2026-10-25) and accept them for this property. I stay responsible for my guide and for what my guests are told.
- **cs:** Přečetl(a) jsem si [podmínky pro Leona (AI)](/guide#leon-terms) (verze 2026-10-25) a přijímám je pro toto ubytování. Za svého průvodce a za to, co se hosté dozvědí, odpovídám já.

(If the UI avoids "(a)", use: "Souhlasím s [podmínkami pro Leona (AI)](/guide#leon-terms) (verze 2026-10-25) pro toto ubytování. Za svého průvodce a za to, co se hosté dozvědí, odpovídám já.")

Why the warnings and the box matter under Czech law: in B2B standard terms a clause the other party could not reasonably expect is ineffective unless expressly accepted (§ 1753 Civil Code). Items 2 to 4 shift responsibility for AI answers to the host, so they must be shown before acceptance and accepted expressly. The screen does that.

## 3. Leon (AI) terms, version 2026-10-25 (`/guide#leon-terms`)

Suggested keys: `guide.leon.terms1`..`terms12`, `guide.leon.terms_title` ("Leon (AI) terms" / "Podmínky pro Leona (AI)"), `guide.leon.terms_version` ("Version %(version)s" / "Verze %(version)s"), constant `leon.LEON_TERMS_VERSION = "2026-10-25"`.

**English**

1. Leon (AI) is optional and you switch it on per property. Leon is a chatbot that answers guests on the stay page and the QR guide page, only from the guide cards you write or import for that property. It runs on Claude, an AI model of Anthropic, PBC.
2. AI can be wrong. Leon may misunderstand a question or give an incomplete or wrong answer, even when your guide is correct. You stay responsible for your communication with guests and for the accuracy of your guide, so check your Leon chats from time to time.
3. Do not rely on Leon for safety, medical, legal or access-critical matters. Keep check-in, key, door code and emergency information on the stay page or in your messages as well, and stay reachable. Leon points emergencies to 112 and tells you, but it never calls anyone.
4. Leon does not make offers or decisions for you. It is told never to agree to prices, discounts, refunds, date changes, early check-in or other promises, and passes them to you. If a guest believes Leon promised something, you settle it with the guest. UbyHost is not a party to your contract with the guest, and liability follows section 17 of the Terms.
5. You are responsible for your guide cards. Use only text you have the right to use, including text imported from your Booking.com or Airbnb listing. Do not put other people's personal data, such as a cleaner's private phone number, into cards without their permission.
6. For each guest message that Leon answers, UbyHost sends Anthropic the guide cards for that page, the property name, the guest's message and up to six earlier messages of the same chat, including your replies. E-mail addresses, phone numbers and long numbers are removed from guest messages first; names and other words are not. Leon never gets guests' names or registration details from UbyHost.
7. Anthropic is UbyHost's subprocessor for Leon. It is a US company and may process requests in any country where it operates, under the EU Standard Contractual Clauses. It deletes them within 30 days, keeps them longer only to enforce its usage rules or where the law requires, and does not use them to train its models.
8. Guests can type anything, including health or other sensitive details. Leon gives no advice on these and passes them to you. Treat such messages with care, and never ask guests for sensitive data, payment or ID details through Leon.
9. UbyHost stores the chats and deletes them 30 days after the stay ends, or 30 days after a QR guide chat was last used. You and the team members who can access the property see the chats. UbyHost staff open them only for support you ask for, for security or where the law requires. Our app logs never hold message text.
10. Guests see in every chat that Leon is an AI, and the privacy notice of each property with Leon on gets a paragraph about it. Under the EU AI Act UbyHost provides Leon and you use it; do not hide from guests that they are talking to an AI. As the controller of your guests' data you answer their data requests, and UbyHost helps you, for example by deleting a chat early.
11. Leon has message limits per stay and per QR chat, and it stops when the AI budget is spent or the provider is down; messages then go to you unread by Leon. UbyHost may change the limits and may pause Leon for a property or for everyone, for example for misuse, safety, cost or legal reasons, and tells you when it can. Any price for Leon is set in the price list, and we tell you before it changes.
12. You can switch Leon off at any time for each property; chats already stored are deleted on the schedule above. If these terms change in a way that matters to you, we ask you to accept the new version, and Leon stays off for that property until you do.

**Česky**

1. Leon (AI) je volitelný a zapínáte ho u každého ubytování zvlášť. Leon je chatbot, který odpovídá hostům na stránce pobytu a na stránce průvodce z QR kódu, a to jen z karet průvodce, které pro dané ubytování napíšete nebo naimportujete. Běží na Claude, modelu umělé inteligence společnosti Anthropic, PBC.
2. Umělá inteligence se může mýlit. Leon může otázku špatně pochopit nebo odpovědět neúplně či chybně, i když je váš průvodce správný. Za komunikaci s hosty a za správnost průvodce odpovídáte vy, proto chaty s Leonem občas zkontrolujte.
3. Nespoléhejte na Leona ve věcech bezpečnosti, zdraví, práva ani vstupu do ubytování. Informace o příjezdu, klíčích, kódech ke dveřím a nouzových situacích mějte i na stránce pobytu nebo ve svých zprávách a buďte k zastižení. Leon při nouzi odkáže na 112 a dá vám vědět, ale nikomu nevolá.
4. Leon za vás nic nenabízí ani nerozhoduje. Má pokyn nikdy neslibovat ceny, slevy, vrácení peněz, změny termínu, dřívější příjezd ani jiné sliby a takové žádosti předá vám. Pokud si host myslí, že mu Leon něco slíbil, vyřešíte to s hostem vy. UbyHost není stranou vaší smlouvy s hostem a odpovědnost se řídí článkem 17 obchodních podmínek.
5. Za své karty průvodce odpovídáte vy. Používejte jen texty, k nimž máte práva, včetně textu naimportovaného z vaší nabídky na Booking.com nebo Airbnb. Do karet nepište osobní údaje jiných lidí, například soukromé číslo uklízečky, bez jejich souhlasu.
6. Ke každé zprávě hosta, na kterou Leon odpovídá, pošle UbyHost společnosti Anthropic karty průvodce pro danou stránku, název ubytování, zprávu hosta a až šest předchozích zpráv téhož chatu včetně vašich odpovědí. Ze zpráv hostů se nejdřív odstraní e-mailové adresy, telefonní čísla a dlouhá čísla; jména a ostatní slova ne. Jména hostů ani údaje z registrace Leon od UbyHostu nikdy nedostává.
7. Anthropic je pro Leona dalším zpracovatelem UbyHostu. Je to americká společnost a požadavky může zpracovávat v kterékoli zemi, kde působí, na základě standardních smluvních doložek EU. Maže je do 30 dnů, déle je uchovává jen kvůli dodržování svých pravidel použití nebo kde to vyžaduje zákon, a nepoužívá je k trénování svých modelů.
8. Hosté mohou napsat cokoli, i údaje o zdraví nebo jiné citlivé údaje. Leon k nim nedává rady a předá je vám. S takovými zprávami zacházejte opatrně a nikdy po hostech přes Leona nežádejte citlivé údaje, platební údaje ani doklady.
9. UbyHost chaty ukládá a maže je 30 dní po konci pobytu nebo 30 dní po posledním použití chatu na stránce průvodce z QR kódu. Chaty vidíte vy a členové týmu s přístupem k ubytování. Pracovníci UbyHostu je otevřou jen kvůli podpoře, o kterou požádáte, kvůli bezpečnosti nebo kde to vyžaduje zákon. Naše aplikační záznamy nikdy neobsahují text zpráv.
10. Hosté v každém chatu vidí, že Leon je umělá inteligence, a informace o ochraně osobních údajů každého ubytování se zapnutým Leonem obsahují odstavec o něm. Podle evropského aktu o umělé inteligenci Leona poskytuje UbyHost a vy ho používáte; nezastírejte před hosty, že mluví s umělou inteligencí. Jako správce údajů svých hostů vyřizujete jejich žádosti a UbyHost vám pomůže, například předčasným smazáním chatu.
11. Leon má limit zpráv na pobyt a na chat z QR kódu a přestane odpovídat, když se vyčerpá rozpočet na AI nebo poskytovatel nefunguje; zprávy pak jdou vám, aniž by je Leon četl. UbyHost může limity měnit a může Leona pozastavit u jednoho ubytování nebo u všech, například kvůli zneužití, bezpečnosti, nákladům nebo právním důvodům, a když to jde, dá vám vědět. Případnou cenu za Leona stanoví ceník a o její změně vám dáme vědět předem.
12. Leona můžete kdykoli vypnout u každého ubytování zvlášť; už uložené chaty se smažou podle lhůt výše. Pokud se tyto podmínky změní způsobem, na kterém vám záleží, požádáme vás o přijetí nové verze a do té doby zůstane Leon u daného ubytování vypnutý.

Notes on the positions behind the terms:
- **Roles (GDPR).** Host = controller, UbyHost = processor (ROPA A, legal positions decision 5), Anthropic = UbyHost's subprocessor under Art 28(2)/(4). Unlike TTLock, UbyHost chose and contracts Anthropic, so the TTLock "host's own provider" route is not available. The host's acceptance is both a documented instruction (Art 28(3)(a)) and informed agreement to this subprocessor, but the general DPA §11 mechanism (register, notice, objection) still applies.
- **Legal basis (host's, stated in the guest notice).** Stay page: Art 6(1)(b), information the guest needs for the accommodation contract. QR page (visitor may not be the booker): Art 6(1)(f), answering people at the property quickly; balance favours it (optional, labelled AI, guest chooses to write, short retention).
- **Art 9.** Leon is not designed to collect special-category data and guests are asked not to send it. Incidental data typed by a guest is not used for any other purpose, is passed to the host and deleted on schedule. Emergencies: Art 9(2)(c) vital interests for passing it on. Residual risk: after CJEU C-252/21 (Meta) and C-21/23 (Lindenapotheke) the court reads Art 9 broadly, so an authority could say storage of a typed health detail needs an Art 9(2) ground. Mitigation is the guest-side line in §5 and the 30-day purge. Accepted as low.
- **AI Act.** Anthropic provides the general-purpose model. UbyHost builds Leon, names it and puts it into service, so UbyHost is the **provider** of the AI system (Art 3(3)) and owns the Art 50(1) duty to make people aware they talk to an AI. The host is the **deployer** (Art 3(4)), with Art 4 AI-literacy duties only; Art 50(3)/(4) deployer duties do not apply (no emotion recognition, no deepfakes, no public-interest publishing). Not high-risk (Annex III). Art 50(2) (machine-readable marking of AI-generated text) applies to providers of systems generating synthetic text; whether a chat reply already labelled "Leon (AI)" needs extra marking, and whether the Digital Omnibus grace period applies, is **unverified**: owner to confirm with counsel (SHOULD).
- **Consumer angle.** Guests are consumers of the host. Statements Leon makes on the host's page are likely to be attributed to the host (misleading practices under zákon 634/1992 Sb. and UCPD), which is why item 4 keeps responsibility with the host and the prompt blocks commitments. UbyHost liability toward the host stays in Terms §17, as for door codes.

## 4. Proof of acceptance

**On the property (`apartment`):** `leon_terms_version` (text, "2026-10-25"), `leon_terms_accepted_at` (UTC ISO timestamp), `leon_terms_accepted_by` (user id of the person who ticked). Keep them when Leon is switched off (they describe the last acceptance), and compare `leon_terms_version` with `LEON_TERMS_VERSION` in `switched_on()` so a stale version means off.

**Audit row** (like `door_code_terms_accepted` in `routes/admin.py`): action `leon_terms_accepted`, actor user id, `owner_user_id`, apartment id, version, UI language shown, time, IP if the audit table stores it. Also audit `leon_enabled` / `leon_disabled` (who, when) so the period Leon was on for a property can be shown.

**Text of each version:** freeze each published version (keep the old i18n strings or a copy in `docs/legal/leon-terms/2026-10-25.md`), or store a SHA-256 of the rendered en/cs text in the audit detail. A version string alone proves little if the old text is gone.

**Is the audit retention enough?** No, not as built. `_audit_retention_step` deletes every audit row older than `AUDIT_RETENTION_DAYS` (1095 days, 3 years) except `action = 'legal_accepted'`. A `leon_terms_accepted` row (and today's `door_code_terms_accepted` row) would expire after 3 years while the host may still use Leon under that version, and Czech claims can run up to 10 years (§ 629, § 636 Civil Code). Fix either way: write the acceptance as `legal_accepted` with detail `doc=leon_terms;version=...;apartment=...`, or add `leon_terms_accepted` and `door_code_terms_accepted` to the exclusion so they follow `_acceptance_retention_step` (deleted only for long-inactive disabled accounts). The property columns alone are not enough because they keep only the latest acceptance and go when the property is deleted.

## 5. Changes needed elsewhere (do not edit in this brief)

| # | Where | Change | Priority |
|---|---|---|---|
| 1 | Subprocessor register (`subprocessors_i18n.py`, v1.3 draft in `drafts/havel-ai.md` part 1) | Purpose "AI support assistant (Havel) and guest assistant (Leon)"; drop "not in use yet"; add to Data: "for Leon: guests' chat messages (e-mails, phones, long numbers removed; names not removed), up to 6 earlier turns including host replies, the property's guide cards and name". Publish before the first host other than the owner can switch Leon on. | MUST |
| 2 | DPA §11 (`dpa_i18n.py`) | Havel draft sentence covers only the support assistant. Use: "Only if the Operator switches it on and the Controller uses it: Anthropic (AI support assistant and, per property the Controller chooses, the Leon (AI) guest assistant)." New §20 effective date. 30-day notice to existing hosts per §11 (owner said none are in production yet; re-confirm at rollout). | MUST |
| 3 | ROPA section A (processor record) | Add to data categories: "Leon (AI) chats: free text guests type (may incidentally include special-category data), Leon replies, host replies, QR browser id". Processing operations: "AI answers from the host's guide (Leon), passing questions to the host". Recipients and Transfers: Anthropic, PBC, subprocessor, global inference under SCCs (A1 to A3), deletion within 30 days at Anthropic (A4). Retention: RETENTION row "Guest chats with Leon". | MUST |
| 4 | Guest privacy notice (`privacy_leon_title` / `privacy_leon_body` in every guest language, shown when `leon_enabled`, modelled on `privacy_door_code_body`) | Draft below. Also link the notice from the Leon chat on the QR guide page, whose visitors may never see the stay page. | MUST |
| 5 | Guest chat UI (`i18n.py`) | Keep "Leon" + "AI" tag and `leon_about` visible before the first message on both doors (Art 50(1)); add one line under the input: en "Leon is an AI and can make mistakes. Please don't share health, payment or ID details. Emergency: 112." cs "Leon je umělá inteligence a může se mýlit. Nesdílejte prosím údaje o zdraví, platbách ani dokladech. V nouzi volejte 112." | MUST |
| 6 | `retention.py` audit exclusion | See part 4: keep `leon_terms_accepted` (and `door_code_terms_accepted`) with the acceptance evidence. | MUST |
| 7 | DPIA (`docs/privacy/DPIA.md`) | Havel screening said "re-screen before the guest assistant ships". Leon is guest-facing, free text, possible Art 9 data, transfer outside the EEA: write the re-screening (likely result: no full DPIA if items 4, 5 and the purge stay; host-side the host is controller, so give hosts a short summary they can rely on). | MUST |
| 8 | Transfer impact assessment (`docs/vendors/`) | Still open from Havel A3; now covers guest data too. | MUST |
| 9 | AI provider switch (`App/app/ai.py`, `UBYHOST_AI_PROVIDER=mistral`) | Leon must not run on Mistral until Mistral has its own register row; either pin Leon to Anthropic or add the row. | MUST |
| 10 | Privacy policy, host section (`privacy_policy_i18n.py` s04/s09/s10/s11) | One sentence: host replies in Leon chats and the guide cards are sent to Anthropic when Leon answers; acceptance evidence of feature terms kept as `legal_accepted`. | SHOULD |
| 11 | RETENTION.md | Add a row "Leon terms acceptance: `apartment.leon_terms_*` (life of property), audit `leon_terms_accepted` (as acceptance evidence, G-D7)"; add to the Leon chat row "Anthropic deletes API data within 30 days (A4)". | SHOULD |
| 12 | ROPA section B | Mention feature-terms acceptance under "Host accounts" or "Security logs". | SHOULD |
| 13 | Host DSR tooling | Let the host delete one chat early and copy a chat's text for an access request, if not already possible (Art 28(3)(e)). | SHOULD |
| 14 | Guide `/guide#leon-terms` | Publish the terms with version line; archive older versions (part 4). | MUST (with the feature) |
| 15 | Copy tone | Soften "Your 24/7 concierge" (`leon_role`, `leon_welcome`) and the prompt line "the host can always be reached through you"; see part 6. | SHOULD |
| 16 | AI Act Art 50(2) | Counsel to confirm whether chat replies need machine-readable AI marking and from when. | SHOULD |

**Guest privacy notice paragraph (draft)**

- **en, "Leon (AI)":** This property offers Leon, a chatbot that answers questions from the host's guide. Leon is an AI, not a person. When you write to Leon, your message (with e-mail addresses, phone numbers and long numbers removed), the last few messages of the chat and the host's guide are sent to Anthropic, PBC (USA), the AI provider UbyHost uses for the host. Anthropic may process them in any country where it operates, under the EU Standard Contractual Clauses, and deletes them within 30 days. Please do not write health, payment or ID details. Questions Leon cannot answer go to the host. The chat is deleted 30 days after your stay ends, or, on the guide page, 30 days after you last used it; a cookie keeps that chat on your device for 30 days. Legal basis: giving you information about your stay (Art 6(1)(b) GDPR), or for guide-page visitors the host's legitimate interest in answering quickly (Art 6(1)(f)).
- **cs, "Leon (AI)":** Toto ubytování nabízí Leona, chatbota, který odpovídá na otázky z průvodce hostitele. Leon je umělá inteligence, ne člověk. Když Leonovi napíšete, vaše zpráva (bez e-mailových adres, telefonních čísel a dlouhých čísel), několik posledních zpráv chatu a průvodce hostitele se odešlou společnosti Anthropic, PBC (USA), poskytovateli AI, kterého UbyHost pro hostitele využívá. Anthropic je může zpracovávat v kterékoli zemi, kde působí, na základě standardních smluvních doložek EU, a maže je do 30 dnů. Nepište prosím údaje o zdraví, platbách ani dokladech. Otázky, na které Leon neodpoví, jdou hostiteli. Chat se smaže 30 dní po konci pobytu, na stránce průvodce 30 dní po posledním použití; soubor cookie uchovává tento chat ve vašem zařízení 30 dní. Právní základ: poskytnutí informací o vašem pobytu (čl. 6 odst. 1 písm. b) GDPR), u návštěvníků stránky průvodce oprávněný zájem hostitele rychle odpovídat (čl. 6 odst. 1 písm. f)).

The `ubyhost_leon` cookie is strictly necessary for a chat the visitor asks for (§ 89(3) zákon 127/2005 Sb. exemption); no consent banner needed.

## 6. Legal risks in current Leon behaviour

1. **Register and DPA lag the code.** Leon sends guest data to Anthropic, but the live register is v1.2 without Anthropic and the v1.3 draft calls the guest assistant "not in use". Today Leon is gated by `ai.owner_on_test_list`, so only the owner's properties are exposed; do not widen that list before items 1 to 4 and 6 to 9 of part 5 ship.
2. **No guest-side "don't share sensitive data / can be wrong" line.** Art 50(1) itself looks met ("Leon" + "AI" tag, `leon_about`), but without item 5 the Art 9 and reliance risks rise.
3. **Over-promising copy.** "Your 24/7 concierge", "always there for the guest, day or night" and "the host can always be reached through you" invite reliance the service cannot guarantee (caps, budget stop, outages, a host who sleeps). In a consumer dispute this reads as the host's promise. Suggest "Ask me about your stay, any time" and drop "always".
4. **Host replies go to the AI.** `_history` sends the host's answers verbatim (not redacted) to Anthropic. A host may type a guest's name, a door code or a phone number there. Covered by terms item 6; consider running host text through `redact` too.
5. **Redaction is partial.** Names, addresses, health words and short numbers stay in stored chats and in what Anthropic receives (and Anthropic may keep flagged content up to 2 years, A4). Do not describe it as anonymisation anywhere.
6. **Secrets in cards.** Cards may hold Wi-Fi passwords or key-box codes; they go to Anthropic with every call and Leon may quote them to anyone who sees that level (the QR page is open to anyone holding the QR). The prompt blocks door codes only. Consider a host-facing hint on cards: "Anything here can be shown by Leon to guests who see this card."
7. **Acceptance evidence expires after 3 years** (part 4); the same gap already exists for door codes.
