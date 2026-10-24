# 0329: Havel (AI): legal drafts for the lawyer (LAWYER REVIEW, not published)

Status: todo
Depends on: 0320 (for the retention facts; the drafts can be written before it merges) | Base commit: 92646d3 (check `git rev-parse --short origin/main` first; if it differs, write the current one here) | Branch: task/0329-havel-legal-drafts
Executor: Haiku 5.5 | Fits one session: 12 tool calls, 25k tokens

## 1. Objective

The four texts plan section 10 lists, drafted for the owner's lawyer: subprocessor register v1.3 with Anthropic, the DPA change notice to hosts, the privacy-policy paragraph for hosts, and the ROPA and RETENTION lines. Docs only. **Nothing under `App/` changes**: the live register (`subprocessors_i18n.py`, "Version 1.2"), the DPA and `/privacy` stay as they are until the lawyer signs off and a later brief ships the approved text. Split from the plan's 0320 for the one-session limit.

## 2. Context

Facts to state (from the plan sections 3, 8, 10, 12 and briefs 0310 to 0320; do not add others):

- Provider: Anthropic (the Claude API). Purpose wording, exactly: "AI support assistant and guest assistant".
- Sent per host message: the fixed prompt, the Help & guide text, the list of app pages, the host's message and up to 4 earlier turns, both redacted (e-mail addresses, phone numbers and ID-like numbers replaced by placeholders), today's date, phone or computer, the host's property ids, internal names and cities, and the current page. Never sent: guest records, passwords, sign-in data, PINs, guest links, door codes, document numbers or photos, invoices, stay-fee figures, UbyPort credentials.
- Not stored by UbyHost: the chat. It lives in the host's browser page, signed, and is gone when the page closes.
- Stored by UbyHost: `ai_usage` (token counts per day and feature, no personal data); `havel_stats` (counts per day and kind, no personal data); `havel_gap` (redacted questions Havel could not answer, language, page, no user, no property, deleted after 90 days); `rate_limit_event` rows of the `havel_*` scopes (user id and time, kept 32 days so the weekly and monthly caps work); support requests the host sends with one tap go as e-mail to `support@ubyhost.com` (account e-mail, workspace, language, page, summary, note, last 4 host messages) and follow the outbox purge.
- Optional: off unless the operator switches it on (`UBYHOST_AI_FEATURES`); the host decides to use it. The name "Havel (AI)" and the line under the input box say it is an AI (EU AI Act transparency).
- Open for the lawyer: Anthropic's location and transfer safeguard (US company; SCCs or the EU-US Data Privacy Framework as Anthropic's commercial terms and DPA state), whether EU-only processing or zero data retention is available on the plan, Anthropic's own retention of API inputs, the lawful basis (contract or legitimate interest), and whether the guest assistant later needs a separate notice to guests.

Today (`grep -nF` 2026-10-24): `App/app/subprocessors_i18n.py` line 14 `        "subprocessors.effective": "Effective date: 4 October 2026. Version 1.2.",`, rows have `_provider`, `_purpose`, `_data`, `_location`, `_safeguard` keys (AWS Lightsail, SES, S3, Cloudflare, PostHog, Render, Google Drive). `App/app/dpa_i18n.py` `dpa.s11_body` promises to "inform the Controller of intended material changes at least 30 days in advance where practicable by updating the register and notifying account contacts, and allow the Controller to object". `privacy_policy_i18n.py` has sections `privacy.s04_title` "4. Categories of Host User data", `s09` "Recipients and subprocessors", `s10` "International transfers", `s11` "Retention". `docs/privacy/ROPA.md` section B table (columns Activity, Data, Purpose, Basis (to confirm), Retention) has the row that starts `| Security logs |` ending `rate-limit 24 h |`, and a list "## Open questions for counsel". `docs/privacy/RETENTION.md` line 28 `| Rate-limit events | `rate_limit_event` | created | 24 hours (G-D7) | `retention.py` rate-limit step | Security |`.

Style: plain English, short sentences, no em or en dashes, "no tracking cookies" never "no cookies" (rule 9). Every draft starts with the line `> **LAWYER REVIEW.** Draft, not published. Nothing here is live until counsel signs off.`

## 3. Files

| Path | Action | What |
|---|---|---|
| docs/privacy/drafts/havel-ai.md | new | drafts 1 to 3 and the counsel questions |
| docs/privacy/ROPA.md | edit | one row, one rate-limit retention, one question |
| docs/privacy/RETENTION.md | edit | two rows |

## 4. Steps

1. Create `docs/privacy/drafts/havel-ai.md` with this structure, writing each part from the facts in section 2:

```markdown
# Havel (AI): drafts for counsel

> **LAWYER REVIEW.** Draft, not published. Nothing here is live until counsel signs off.

Source: plan `docs/plans/havel-support-assistant.md` section 10; code in briefs 0310 to 0320.

## 1. Subprocessor register, version 1.3 (new row and effective line)

Effective line: "Effective date: <date counsel approves>. Version 1.3."

| Subprocessor | Purpose | Data | Location | Transfer safeguard |
|---|---|---|---|---|
| Anthropic (Claude API) | AI support assistant and guest assistant. | <from section 2: what is sent; never guest records ...> | <counsel: US company; region per plan> | <counsel: Anthropic DPA, SCCs or DPF> |

Czech row: the same, translated (Účel: "Asistent podpory s AI a asistent pro hosty.").

## 2. Notice to hosts (DPA section 11, 30 days before the register changes)

Subject and a body of at most 150 words, en and cs: what is added, why, what is and is not sent, that it is optional, the date it takes effect, how to object (reply to support@ubyhost.com).

## 3. Privacy policy, host section

One paragraph for section 4 (Host User data) and one sentence each for sections 9 (recipients), 10 (transfers) and 11 (retention), en and cs.

## 4. Questions for counsel

The open points of section 2, one bullet each.
```

   Replace each `<...>` with text; keep the `<counsel: ...>` markers where the answer is the lawyer's. Check: `grep -c 'LAWYER REVIEW' docs/privacy/drafts/havel-ai.md` prints at least `1`; `grep -c '<counsel' docs/privacy/drafts/havel-ai.md` prints at least `2`.

2. In `docs/privacy/ROPA.md` section B, after the row that starts `| Support mailbox |`, add:

```markdown
| Host support assistant, Havel (AI) (**LAWYER REVIEW**, off until enabled) | Host's typed question and up to 4 earlier turns, redacted, plus property ids, names and cities, sent to Anthropic per message and not stored by UbyHost; `havel_gap` (redacted question, language, page, no user); `rate_limit_event` `havel_*` rows (user id, time); one-tap support e-mails | Answer hosts' questions about the app; hand off to support | Contract / legitimate interest (to confirm) | Chat not stored; `havel_gap` 90 days; Havel limit rows 32 days; support e-mail as the support mailbox. Processor: Anthropic (see `drafts/havel-ai.md`) |
```

   In the `| Security logs |` row change `rate-limit 24 h` to `rate-limit 24 h (Havel limits 32 days)`. Under `## Open questions for counsel` add `- Havel (AI): transfer safeguard, Anthropic's own retention and the lawful basis ([drafts/havel-ai.md](drafts/havel-ai.md) section 4).`

3. In `docs/privacy/RETENTION.md` replace line 28 with:

```markdown
| Rate-limit events | `rate_limit_event` | created | 24 hours (G-D7); `havel_*` scopes 32 days (Havel weekly and monthly caps, 0320) | `retention.py` rate-limit step | Security |
| Havel gap questions | `havel_gap` | created | 90 days (0320) | `retention.py` Havel gap step | Storage limitation |
```

4. Run section 6. Expected: OK, and `git diff --stat origin/main -- App | tail -1` prints nothing.

## 5. Do not touch

Everything under `App/`: `subprocessors_i18n.py`, `dpa_i18n.py`, `privacy_policy_i18n.py`, the templates, the version line. Other ROPA and RETENTION rows.

## 6. Commands (from the repo root)

- `python3 scripts/context_lint.py | tail -5`
- `grep -rn $'—\|–' docs/privacy/drafts/havel-ai.md | head -3` (expected: nothing)

## 7. Acceptance

- [ ] `docs/privacy/drafts/havel-ai.md` has the four parts, en and cs where asked, the LAWYER REVIEW line and the `<counsel: ...>` markers.
- [ ] Purpose wording is exactly "AI support assistant and guest assistant".
- [ ] ROPA and RETENTION rows added; no file under `App/` changed; lint OK.

## 8. Stop and ask

- A fact you need is not in section 2: write `<counsel: ...>` or `<owner: ...>` instead of guessing.

## 9. Report

Write `docs/tasks/0329-report.md` (300 tokens at most) and set `Status: review`: files changed, the lint's last line, section 7 ticked.

## Risk list (for the reviewer)

- The drafts must not be copied into the live texts before counsel answers section 4.

## Owner steps

1. Send `docs/privacy/drafts/havel-ai.md` to the lawyer (owner item 3) with the plan's section 10.
2. When the answers come back, give them to the orchestrator; a later brief updates `subprocessors_i18n.py` to v1.3, the privacy policy and the DPA, and sends the notice 30 days before Havel goes live for hosts.
