# Havel (AI): drafts for the owner's sign-off

> **LAWYER REVIEW.** Draft, not published. Reviewed by AI counsel on 2026-10-24, not by a licensed lawyer. Nothing here is live until the owner confirms the assumptions in section 7.

Source: plan `docs/plans/havel-support-assistant.md` section 10; code in briefs 0310 to 0320.

These drafts do not state that UbyHost complies with any law. They describe what the code sends and stores, and what the owner has to decide.

## 1. Subprocessor register, version 1.3

Effective line: "Effective date: <owner: date>. Version 1.3."

Owner (2026-10-24): no 30-day notice is needed before launch, because there are no production hosts yet. The register is updated before the first real host signs up.

| Subprocessor | Purpose | Data | Location | Transfer safeguard |
|---|---|---|---|---|
| Anthropic, PBC (Claude API) | AI support assistant and guest assistant | The host's question and up to 4 earlier turns, with e-mail addresses, phone numbers and ID-like numbers replaced by placeholders (names and street addresses are not removed); property ids, internal names and cities; the current page. Guest details only if the host types them. Not stored by UbyHost. | United States company. Processing may happen in any country where Anthropic operates (default setting, A1). <owner: confirmed 2026-10-24, global default> | Standard Contractual Clauses (2021, Module Two and Module Three) in Anthropic's DPA (A2). The EU-US Data Privacy Framework is not relied on (A3). |

Note under the table: the guest assistant is not built yet and is not in use. The row stays so the register is complete when it ships. <owner: decide whether the row says "not in use yet" or waits until the guest assistant ships>

Czech row (cs):

| Subprocesor | Účel | Údaje | Umístění | Záruka pro přenos |
|---|---|---|---|---|
| Anthropic, PBC (Claude API) | Asistent podpory s AI a asistent pro hosty | Dotaz hosta a až 4 předchozí zprávy; e-mailové adresy, telefonní čísla a čísla podobná identifikátorům jsou nahrazena zástupnými znaky (jména a ulice se neodstraňují); id nemovitostí, interní názvy a města; aktuální stránka. Údaje o hostech jen tehdy, když je host sám napíše. UbyHost je neukládá. | Spojené státy. Zpracování může probíhat v kterékoli zemi, kde Anthropic působí (výchozí nastavení, A1). | Standardní smluvní doložky (2021, moduly 2 a 3) v DPA společnosti Anthropic (A2). Rámec EU-USA pro ochranu údajů se nespoléhá (A3). |

## 2. Notice to hosts (DPA sections 11 and 20)

Sent to each account e-mail at least 30 days before the effective date, once the owner decides the date (see part 1).

**Subject (en):** Havel (AI): an optional AI assistant, and a new subprocessor

**Body (en, about 150 words):**

From <owner: date>, UbyHost offers Havel (AI), an optional AI assistant that answers questions about the app. You choose whether to use it. If you do not open Havel, nothing is sent to the AI provider.

When you use Havel, UbyHost sends your question and up to four earlier messages to Anthropic, PBC (USA). Our server first removes e-mail addresses, phone numbers and ID-like numbers. Names and street addresses are not removed. Please do not type your guests' names or other details into Havel. UbyHost does not store the chat.

Anthropic is added to our subprocessor list (version 1.3), effective <owner: date>. You may object on data-protection grounds by replying to support@ubyhost.com. If we cannot settle your objection, you may end the affected service as our Terms say.

Details: <owner: link to /dpa and /privacy>.

**Subject (cs):** Havel (AI): volitelný asistent s AI a nový subdodavatel

**Body (cs):**

Od <owner: datum> nabízí UbyHost Havela (AI), volitelného asistenta s AI, který odpovídá na otázky o aplikaci. Sami rozhodnete, zda ho použijete. Pokud Havela neotevřete, nic se neodešle poskytovateli AI.

Když Havela použijete, UbyHost odešle vaši otázku a až čtyři předchozí zprávy společnosti Anthropic, PBC (USA). Náš server nejdřív odstraní e-mailové adresy, telefonní čísla a čísla podobná identifikátorům. Jména a ulice se neodstraňují. Prosíme, nepište do Havela jména ani jiné údaje svých hostů. UbyHost chat neukládá.

Anthropic se přidává do seznamu subdodavatelů (verze 1.3) s účinností od <owner: datum>. Námitku z důvodu ochrany údajů můžete uplatnit odpovědí na support@ubyhost.com. Pokud se námitku nepodaří vyřešit, můžete ukončit dotčenou službu podle našich podmínek.

Podrobnosti: <owner: odkaz na /dpa a /privacy>.

## 3. DPA text change

New sentence after the Google Drive sentence in `dpa.s11_body` (en):

> Only if the Operator switches it on and the Controller's users use it: Anthropic (AI support assistant).

cs:

> Pouze pokud Provozovatel zapne tuto funkci a uživatelé Správce ji použijí: Anthropic (asistent podpory s AI).

New effective date under section 20: <owner: date>.

Section 17 needs no change, because the Standard Contractual Clauses are already named there (A3).

## 4. Privacy policy, host section

Section 4, "Categories of Host User data" (en):

> **Havel (AI).** Havel is an optional AI assistant that answers questions about the app. When a host uses it, UbyHost sends the host's question and up to four earlier messages of the same chat to Anthropic, PBC. UbyHost's own server first replaces e-mail addresses, phone numbers and ID-like numbers with placeholders. This does not remove names or street addresses, so please do not type your guests' names or details. UbyHost does not store the chat. If a host does not use Havel, nothing is sent. The lawful basis is in part 6 of the drafts.

Section 9, "Recipients and subprocessors" (en): Anthropic, PBC (USA) receives the text described in section 4 as a processor, only when a host uses Havel.

Section 10, "International transfers" (en): Anthropic may process requests in any country where it operates. Transfers are covered by the Standard Contractual Clauses in Anthropic's data processing addendum (A2, A3). <owner: confirm wording with counsel>

Section 11, "Retention" (en): Unanswered Havel questions (redacted, not linked to a user) are deleted after 90 days. Rate-limit records for Havel are kept for 32 days. A support e-mail that a host sends from Havel stays in UbyHost's support mailbox (see ROPA).

cs (sections 4, 9, 10, 11):

- Sekce 4: **Havel (AI).** Havel je volitelný asistent s AI, který odpovídá na otázky o aplikaci. Když jej host použije, UbyHost odešle dotaz hosta a až čtyři předchozí zprávy téhož chatu společnosti Anthropic, PBC. Náš server nejdřív nahradí e-mailové adresy, telefonní čísla a čísla podobná identifikátorům zástupnými znaky. Jména a ulice tím nejsou odstraněna, proto prosíme, nepište údaje svých hostů. UbyHost chat neukládá. Pokud Havela nepoužijete, nic se neodešle. Právní základ je v části 6 návrhů.
- Sekce 9: Anthropic, PBC (USA) přijímá text podle sekce 4 jako zpracovatel, jen když host použije Havela.
- Sekce 10: Anthropic může zpracovávat požadavky v kterékoli zemi, kde působí. Přenosy kryjí standardní smluvní doložky v jeho DPA (A2, A3). <owner: potvrdit znění>
- Sekce 11: Nezodpovězené otázky (zredigované, bez vazby na uživatele) se mažou po 90 dnech. Záznamy limitů pro Havela se uchovávají 32 dnů. E-mail podpory, který host odešle z Havela, zůstane ve schránce podpory UbyHostu (viz ROPA).

## 5. EU AI Act

AI counsel review (not a legal opinion): Article 50(1) of the EU AI Act says people must be told they are dealing with an AI, at the latest at the first interaction and clearly. The AI counsel review says this applies from 2 August 2026. The current labels are meant to meet it: the name "Havel (AI)", the intro and the line under the input box. All three must stay visible before the first message. <owner: lawyer to confirm the date and the wording>

Havel is not treated as a high-risk system (Annex III). The model duties sit with Anthropic. Article 4 (AI literacy): whoever answers Havel hand-offs should know that Havel's summaries can be wrong.

## 6. Lawful basis and minimisation

**Host data (question, earlier turns, page, property ids):** legitimate interest, Article 6(1)(f) GDPR. Balancing test, short:

1. Purpose: an in-app help that the host chooses to use.
2. Need: the answer needs the host's question and some context. Redaction, no stored chat and the optional switch keep this small.
3. Balance: the host sees that it is an AI and can avoid it. The main risk is a guest's name typed by a host, so the drafts ask hosts not to type guest details.
**Hand-off e-mail to support:** contract, Article 6(1)(b), because the host asks for support.

**Guest details that a host types:** UbyHost processes them for the host under the DPA. Keeping redacted unanswered questions in `havel_gap` for UbyHost's own guide work is a UbyHost purpose. It is kept small by redaction, has no user link and is deleted after 90 days.

**Disclaimer:** recommend adding "or guests' details" to the Havel disclaimer text, so the host is told not to type them. <owner: decide>. Note: no `havel.disclaimer` key exists in `App/app/host_i18n.py`. The owner must name the key that holds the line under the input box before the text is changed in a later brief.

## 7. Assumptions and owner decisions

**Assumptions about Anthropic (checked by the orchestrator on 2026-10-24 against Anthropic's own pages; re-check before any live text changes):**

- **A1.** Anthropic, PBC (US) is the processor. API inference runs in "any available geography" by default (`inference_geo: "global"`). `inference_geo: "us"` keeps inference in the US at 1.1 times the price. There is no EU option. Check: platform.claude.com/docs/en/manage-claude/data-residency.
- **A2.** The DPA "is incorporated into and forms part of the Anthropic Commercial Terms". It incorporates the 2021 SCCs, Module Two (controller to processor) and Module Three (processor to processor), with Irish law. Check: anthropic.com/legal/data-processing-addendum.
- **A3.** The DPA does not mention the EU-US Data Privacy Framework, and no DPF listing was found. The drafts rely on the SCCs only. A short transfer impact assessment is needed in `docs/vendors/` (not written by this brief). Check: dataprivacyframework.gov.
- **A4.** API inputs and outputs are deleted "within 30 days of receipt or generation" by default. Longer only for Usage Policy enforcement (flagged content up to 2 years) or legal duty. Retained data "is never used for model training without your express permission". Haiku is not a "Covered Model". Check: privacy.claude.com article 7996866; platform.claude.com/docs/en/manage-claude/api-and-data-retention.
- **A5.** Zero data retention exists for the Messages API, but only by request to Anthropic sales, per organisation. Structured outputs keep only the JSON schema up to 24 hours, and prompt caching keeps cache data for its TTL. UbyHost does not have ZDR, so the 30-day default applies.
- **A6.** Anthropic publishes its subprocessors at anthropic.com/subprocessors and gives notice before adding one, with 15 days to object (DPA section C.3).

**Owner answers (2026-10-24):**

- A1 to A6 checked.
- `inference_geo`: the global default. The texts say the AI provider may process requests in any country where it operates, under the SCCs.
- No 30-day subprocessor notice before launch, because there are no production hosts yet.
- Whether to add "or guests' details" to the disclaimer: recommended, still open (part 6).
- Whether the register lists the guest assistant now or when it ships: the plan's wording keeps it, marked "not in use yet" (part 1).

**Open items found while drafting (owner to decide):**

- **Mistral backup (0334).** `App/app/ai.py` can send the same requests to Mistral when `UBYHOST_AI_PROVIDER=mistral` (default is `anthropic`). The plan calls Mistral (EU) the worst-case fallback. No decision line for Mistral exists in `docs/context/decisions.md`. If the switch is ever used, Mistral becomes a second subprocessor and needs its own row and terms check. <owner: decide whether the register lists Mistral as a conditional subprocessor>
- **Support mailbox.** The owner answered on 2026-10-24: the mailbox is Zoho Mail, retention 12 months. The ROPA retention cell still says "To be confirmed". This brief does not change that cell. <owner: a later brief writes the answer into ROPA>
- **Support mailbox copy.** The delivered copy of each Havel hand-off e-mail stays in the mailbox. Its outbox row is deleted after 14 days (RETENTION "Mail rows").
- **Disclaimer key.** See part 6.
