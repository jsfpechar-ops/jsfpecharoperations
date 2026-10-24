# 0329: Havel (AI): legal drafts, AI counsel reviewed (LAWYER REVIEW, not published)

Status: todo
Depends on: 0320 (for the retention facts; the drafts can be written before it merges) | Base commit: f4c76d7 (check `git rev-parse --short origin/main` first; if it differs, write the current one here) | Branch: task/0329-havel-legal-drafts
Executor: Haiku 5.5 | Fits one session: 14 tool calls, 30k tokens

## 1. Objective

The texts plan section 10 lists, drafted for the owner's sign-off: subprocessor register v1.3 with Anthropic, the notice to hosts, the DPA text change, the privacy-policy paragraphs for hosts, the ROPA, RETENTION and DPIA lines. Docs only. **Nothing under `App/` changes**: the live register (`subprocessors_i18n.py`, "Version 1.2"), the DPA and `/privacy` stay as they are until the owner confirms section 2's assumptions and a later brief ships the approved text. The owner chose an AI counsel review instead of an external lawyer (plan section 15); its findings are at the end of this brief.

## 2. Context

Facts to state (plan sections 3, 8, 10, 12, briefs 0310 to 0320; add no others):

- Provider: Anthropic (the Claude API). Purpose wording, exactly: "AI support assistant and guest assistant". The guest assistant is not built yet; the row says so.
- Sent per host message: the fixed prompt, the Help & guide text, the list of app pages, the host's message and up to 4 earlier turns, both redacted (e-mail addresses, phone numbers and ID-like numbers replaced by placeholders; **names and street addresses are not redacted**), today's date, phone or computer, the host's property ids, internal names and cities, and the current page. Never sent: guest records from the database, passwords, sign-in data, PINs, guest links, door codes, document numbers or photos, invoices, stay-fee figures, UbyPort credentials. Guest details reach Anthropic only if the host types them.
- Not stored by UbyHost: the chat. It lives in the host's browser page, signed, and is gone when the page closes.
- Stored by UbyHost: `ai_usage` (token counts per day and feature, no personal data); `havel_stats` (counts per day and kind, no personal data); `havel_gap` (redacted questions Havel could not answer, language, page, no user, no property; the free text may still hold a name the host typed; deleted after 90 days); `rate_limit_event` rows of the `havel_*` scopes (user id and time, kept 32 days so the weekly and monthly caps work); support requests the host sends with one tap go as e-mail to `support@ubyhost.com` (account e-mail, workspace, language, page, summary, note, last 4 host messages as typed, not redacted). When a Havel limit is hit, the host's message is sent this way without a tap, and the page tells the host so (0333). The outbox row is deleted after 14 days (`mail.purge_old`, RETENTION.md "Mail rows"); **the delivered copy stays in the support mailbox**, whose retention is still open (ROPA "Support mailbox").
- Optional: off unless the operator switches it on (`UBYHOST_AI_FEATURES`); each host decides to use it. The name "Havel (AI)", the intro and the line under the input box say it is an AI.
- Facts about Anthropic, checked by the orchestrator on 2026-10-24 against Anthropic's own pages (owner asked: "check it yourself"); re-check them before the live texts change:
  A1 Anthropic, PBC (US) is the processor. API inference runs in "any available geography" by default (`inference_geo: "global"`); `inference_geo: "us"` keeps inference in the US at 1.1x price; there is no EU option (platform.claude.com/docs/en/manage-claude/data-residency).
  A2 The DPA "is incorporated into and forms part of the Anthropic Commercial Terms" and incorporates the 2021 SCCs, Module Two (controller to processor) and Module Three (processor to processor), Irish law (anthropic.com/legal/data-processing-addendum).
  A3 The DPA does not mention the EU-US Data Privacy Framework, and no DPF listing was found. Rely on the SCCs only; say so in the drafts and keep a short transfer impact assessment in `docs/vendors/`.
  A4 API inputs and outputs are deleted "within 30 days of receipt or generation" by default, longer only for Usage Policy enforcement (flagged content up to 2 years) or legal duty; retained data "is never used for model training without your express permission" (privacy.claude.com article 7996866; platform.claude.com/docs/en/manage-claude/api-and-data-retention). Haiku is not a "Covered Model" (those are the Mythos/Fable class).
  A5 Zero data retention exists for the Messages API but only by request to Anthropic sales, per organisation; structured outputs keep only the JSON schema up to 24 hours and prompt caching keeps cache data for its TTL. UbyHost does not have ZDR; the 30-day default applies.
  A6 Anthropic publishes its subprocessors at anthropic.com/subprocessors and gives notice before adding one, with 15 days to object (DPA section C.3).

Today (`grep -nF` 2026-10-24): `App/app/subprocessors_i18n.py` line 14 `        "subprocessors.effective": "Effective date: 4 October 2026. Version 1.2.",`, rows have `_provider`, `_purpose`, `_data`, `_location`, `_safeguard` keys. `App/app/dpa_i18n.py` `dpa.s11_body` names the subprocessors one by one ("AWS Lightsail, Amazon SES, Amazon S3 backups and Cloudflare. Only if used: Render ... and Google Drive ...") and promises to "inform the Controller of intended material changes at least 30 days in advance where practicable by updating the register and notifying account contacts, and allow the Controller to object"; `dpa.s17_body` "Standard Contractual Clauses or adequacy decisions"; `dpa.s20_body` posts DPA changes at /dpa with a new effective date, 30 days ahead where practicable. `privacy_policy_i18n.py` sections `privacy.s04_title` "4. Categories of Host User data", `s09` "Recipients and subprocessors", `s10` "International transfers", `s11` "Retention". `docs/privacy/ROPA.md` section B has rows starting `| Security logs |` (ending `rate-limit 24 h |`) and `| Support mailbox |` (Data cell `Messages to/from `support@ubyhost.com``), and "## Open questions for counsel". `docs/privacy/RETENTION.md` line 28 `| Rate-limit events | `rate_limit_event` | created | 24 hours (G-D7) | `retention.py` rate-limit step | Security |`. `docs/privacy/DPIA.md` starts `# Data protection impact assessment (Article 35 GDPR)`.

Style: plain English, short sentences, no em or en dashes, "no tracking cookies" never "no cookies" (rule 9). Every draft starts with `> **LAWYER REVIEW.** Draft, not published. Reviewed by AI counsel on 2026-10-24, not by a licensed lawyer. Nothing here is live until the owner confirms the assumptions in section 7.`

## 3. Files

| Path | Action | What |
|---|---|---|
| docs/privacy/drafts/havel-ai.md | new | drafts 1 to 7 |
| docs/privacy/ROPA.md | edit | one row, two cells, one question |
| docs/privacy/RETENTION.md | edit | two rows |
| docs/privacy/DPIA.md | edit | one screening section at the end |

## 4. Steps

1. Create `docs/privacy/drafts/havel-ai.md` with this structure, writing each part from section 2 (keep every `<owner: ...>` marker where an assumption decides the text):

```markdown
# Havel (AI): drafts for the owner's sign-off

> **LAWYER REVIEW.** (the line from section 2)

Source: plan `docs/plans/havel-support-assistant.md` section 10; code in briefs 0310 to 0320.

## 1. Subprocessor register, version 1.3

Effective line: "Effective date: <owner: date, at least 30 days after the notice>. Version 1.3."

| Subprocessor | Purpose | Data | Location | Transfer safeguard |
|---|---|---|---|---|
| Anthropic, PBC (Claude API) | AI support assistant and guest assistant. Only used while the operator switches it on; the guest assistant is not in use yet. | The host's question and up to 4 earlier messages with e-mail addresses, phone numbers and ID-like numbers removed; property ids, internal names and cities; the current page. Guest details only if the host types them. Not stored by UbyHost. | United States <owner: A1, A5> | <owner: A3> EU-US Data Privacy Framework (adequacy decision of 10 July 2023) if Anthropic is certified; otherwise the Standard Contractual Clauses in Anthropic's DPA <owner: A2>. |

Czech row: the same, translated (Účel: "Asistent podpory s AI a asistent pro hosty.").

## 2. Notice to hosts (DPA sections 11 and 20)

Subject and a body of at most 150 words, en and cs, sent to each account e-mail at least 30 days before the effective date: what is added and why, what is and is not sent, that guest details reach Anthropic only if the host types them (so: do not type them), that it is optional and nothing is sent if the host does not use Havel, the effective date, how to object on data-protection grounds (reply to support@ubyhost.com) and that, if unresolved, the host may end the affected service as the Terms say.

## 3. DPA text change

New `dpa.s11_body` sentence after the Google Drive one, en and cs: "Only if the Operator switches it on and the Controller's users use it: Anthropic (AI support assistant)." New effective date under section 20. Section 17 needs no change (the Data Privacy Framework is an adequacy decision).

## 4. Privacy policy, host section

One paragraph for section 4 (Host User data: Havel, what it sends, redaction, chats not stored, optional, the lawful basis from part 6), one sentence each for sections 9 (Anthropic as recipient), 10 (transfer to the US and the safeguard of part 1) and 11 (gap questions 90 days, Havel limit rows 32 days, support e-mails as the support mailbox), en and cs.

## 5. EU AI Act

Article 50(1), in force from 2 August 2026: people must be told they are dealing with an AI, at the latest at the first interaction, clearly. Met by the name "Havel (AI)", the intro and the line under the input box; keep all three visible before the first message. Havel is not a high-risk system (Annex III); the model duties are Anthropic's. Article 4: whoever answers Havel hand-offs knows that Havel's summaries can be wrong.

## 6. Lawful basis and minimisation

Host data: legitimate interest, Article 6(1)(f) (a working in-app help the host chooses to use), with a three-line balancing test here; the hand-off e-mail: contract, Article 6(1)(b) (the host asks for support). Guest details a host types: UbyHost processes them for the host under the DPA; keeping them in `havel_gap` for UbyHost's own guide work is a UbyHost purpose, kept small by redaction, no user link and 90 days. Recommend adding "or guests' details" to `havel.disclaimer` (<owner: decide>).

## 7. Assumptions and owner decisions

A1 to A6 from the brief, one bullet each, each with where to check it; then the owner decisions from the counsel review.
```

   Check: `grep -c 'LAWYER REVIEW' docs/privacy/drafts/havel-ai.md` prints at least `1`; `grep -c '<owner' docs/privacy/drafts/havel-ai.md` prints at least `4`.

2. In `docs/privacy/ROPA.md` section B, after the row that starts `| Support mailbox |`, add:

```markdown
| Host support assistant, Havel (AI) (**LAWYER REVIEW**, off until enabled) | Host's typed question and up to 4 earlier turns, redacted (names not removed), plus property ids, names and cities, sent to Anthropic per message and not stored by UbyHost; `havel_gap` (redacted question, language, page, no user; may hold a name the host typed); `rate_limit_event` `havel_*` rows (user id, time); one-tap support e-mails | Answer hosts' questions about the app; improve the guide; hand off to support | Legitimate interest, Art 6(1)(f) (balancing in `drafts/havel-ai.md` part 6); hand-off: contract | Chat not stored; `havel_gap` 90 days; Havel limit rows 32 days; support e-mail as the support mailbox. Processor: Anthropic, PBC, US (see `drafts/havel-ai.md`) |
```

   In the `| Security logs |` row change `rate-limit 24 h` to `rate-limit 24 h (Havel limits 32 days)`. In the `| Support mailbox |` row change `Messages to/from `support@ubyhost.com`` to `Messages to/from `support@ubyhost.com`, including Havel (AI) hand-offs (summary, note, last 4 host messages)`. Under `## Open questions for counsel` add `- Havel (AI): assumptions A1 to A6 about Anthropic and the support mailbox retention ([drafts/havel-ai.md](drafts/havel-ai.md) part 7).`

3. In `docs/privacy/RETENTION.md` replace line 28 with:

```markdown
| Rate-limit events | `rate_limit_event` | created | 24 hours (G-D7); `havel_*` scopes 32 days (Havel weekly and monthly caps, 0320) | `retention.py` rate-limit step | Security |
| Havel gap questions | `havel_gap` | created | 90 days (0320) | `retention.py` Havel gap step | Storage limitation |
```

4. Append to `docs/privacy/DPIA.md`:

```markdown

## Havel (AI) screening (LAWYER REVIEW, 2026-10-24)

New technology (an AI model) and a transfer to the US, but no systematic monitoring, no special-category data by design, no decision about people, and the host chooses to use it. Screening result: no full DPIA needed, provided redaction, the "do not type guests' details" line and the 90-day gap limit stay. Re-screen before the guest assistant ships. Details: [drafts/havel-ai.md](drafts/havel-ai.md).
```

5. Run section 6. Expected: OK, and `git diff --stat origin/main -- App | tail -1` prints nothing.

## 5. Do not touch

Everything under `App/`: `subprocessors_i18n.py`, `dpa_i18n.py`, `privacy_policy_i18n.py`, the templates, the version line. ROPA and RETENTION rows other than those named in steps 2 and 3.

## 6. Commands (from the repo root)

- `python3 scripts/context_lint.py | tail -5`
- `grep -rn $'—\|–' docs/privacy/drafts/havel-ai.md | head -3` (expected: nothing)

## 7. Acceptance

- [ ] `docs/privacy/drafts/havel-ai.md` has parts 1 to 7, en and cs where asked, the LAWYER REVIEW line and the `<owner: ...>` markers; no Anthropic fact is stated without its A-number.
- [ ] Purpose wording is exactly "AI support assistant and guest assistant".
- [ ] ROPA, RETENTION and DPIA edits made; no file under `App/` changed; lint OK.

## 8. Stop and ask

- A fact you need is not in section 2: write `<owner: ...>` instead of guessing.

## 9. Report

Write `docs/tasks/0329-report.md` (300 tokens at most) and set `Status: review`: files changed, the lint's last line, section 7 ticked.

## Risk list (for the reviewer)

- A1 to A6 were checked on 2026-10-24 (above). The drafts may be copied into the live texts; they must say processing may happen in any country where Anthropic operates (owner kept the global default).

## Owner steps

1. Check A1 to A6 in Anthropic's current Commercial Terms, DPA and subprocessor list, and on `dataprivacyframework.gov`; write the answers in part 7 of the drafts.
2. Decide the owner items in the counsel review below, then give the drafts to the orchestrator; a later brief updates `subprocessors_i18n.py` to v1.3, the DPA and the privacy policy, and sends the notice 30 days before Havel goes live for hosts.

## Counsel review (AI, 2026-10-24)

Not a licensed lawyer's opinion (plan section 15, item 3).

Findings:

1. **Anthropic is a subprocessor of guest data, not only a processor of host data.** Redaction removes e-mails, phones and ID numbers but not names, so a host can send a guest's name. DPA section 11 therefore applies in full: 30 days' notice, a right to object, and section 11 itself names each subprocessor, so its text must change too (new part 3, with a section 20 effective date).
2. **Transfer to the US.** Never state DPF or SCC cover as fact. It depends on A2 and A3. With SCCs only, a short transfer impact assessment belongs in `docs/vendors/`. The DPF has faced court challenges, so SCCs are the fallback.
3. **Lawful basis.** Contract (6(1)(b)) is weak for an optional assistant. The draft now uses legitimate interest for host data and contract for the hand-off e-mail.
4. **Retention was overstated.** "Deleted with the outbox after 14 days" holds only for UbyHost's database. The delivered copy stays in the support mailbox, whose retention is still open.
5. **Minimisation.** `havel_gap` can hold a typed name, so ROPA no longer implies it has no personal data. It is kept small by no user link and 90 days.
6. **AI Act Article 50** applies from 2 August 2026, so it already applies at launch. The current labels meet it. Part 5 records why.
7. **DPIA:** a screening note, no full DPIA (step 4).

Changes made in this brief: findings 1 to 7 above; Anthropic facts turned into assumptions A1 to A6; draft parts 3, 5, 6 and 7 added; ROPA basis, Support mailbox and DPIA lines.

Owner decisions: A1 to A6 checked 2026-10-24; `inference_geo`: owner chose the global default (2026-10-24), so the privacy texts say the AI provider may process requests in any country where it operates, under the SCCs; the support mailbox retention: answered 2026-10-24, the support mailbox is Zoho Mail, 12 months (owner accepted the recommendation); the 30-day subprocessor notice is not needed before launch, because there are no production hosts yet (owner, 2026-10-24), so the register is updated before the first real host signs up; whether to add "or guests' details" to `havel.disclaimer` (recommended); whether the register lists the guest assistant now or when it ships (the plan's exact wording keeps it, marked "not in use yet").
