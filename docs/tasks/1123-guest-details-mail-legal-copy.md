# 1123: Guest details mail, part a: the legal copy (DPA, privacy policy, guest notice)

Status: todo
Depends on: 1121 | Base commit: 169ee203 | Branch: task/1123-guest-details-mail-legal-copy
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

**THIS PR STAYS A DRAFT until the lawyer confirms the wording.** Open the PR with `gh pr create --draft`. Never mark it ready and never run `scripts/merge-pr-on-green.sh` on it. The report must say: "DRAFT, waiting for the lawyer" in its first line.

Split note: the plan's brief 1123 would not fit 30 tool calls. It is two briefs: **1123 (this file)** is all the sentences; **[1123b](1123b-guest-details-mail-legal-docs.md)** is ROPA, RETENTION, the version bump and SES. 1123b depends on this one. Both stay draft.

## 1. Objective

Replace the statements that say "the host gets a copy of the receipt" (true until 1121, false after it) with one sentence per document that describes the new host mail: the host receives the registration details by e-mail, the guest receives a receipt, the host's own mailbox is outside our deletion. Wording below is a draft marked LAWYER REVIEW here; the markers are NOT part of the shipped strings.

## 2. Context

Copy rule (AGENTS rule 9): one explanation lives in one place. So each document gets its sentence by REPLACING the old "copy to the Host" sentence in the same place, never by adding a second one. The three sentences are one idea written for three readers (host contract, host-facing policy, guest). 1121 removes the host cc from the receipt, so the old sentences become wrong the moment it ships.

Legal notes for the lawyer (do not put in code): the host's instruction to us is the "configuration in the Service" already named in DPA section 3 (GDPR Art. 28(3)(a)); the switch is on by default and has no effect before the host accepts the DPA version of 1123b.

Wording (LAWYER REVIEW, all six):
- DPA en: `On the Controller's instruction, given by the Service setting "Guest details in the confirmation e-mail" (on by default, switchable in Settings), the Processor sends the guest details of each submitted registration by e-mail to the Controller's contact address; the Controller is responsible for the security of its own mailbox, which the Processor's deletion under Section 15 does not reach.`
- DPA cs: `Na pokyn Správce daný nastavením Služby „Údaje o hostech v potvrzovacím e-mailu“ (ve výchozím stavu zapnuto, lze vypnout v Nastavení) Zpracovatel posílá údaje hostů z každého odeslaného formuláře e-mailem na kontaktní adresu Správce; za zabezpečení vlastní e-mailové schránky odpovídá Správce a mazání Zpracovatele podle čl. 15 se na ni nevztahuje.`
- Privacy policy en: `On the Host's instruction, set in Settings, we e-mail the details of each submitted registration to the Host's contact address and a receipt to the Guest; the Host's own mailbox is outside our deletion.`
- Privacy policy cs: `Na pokyn ubytovatele daný v Nastavení posíláme údaje z každého odeslaného formuláře e-mailem na kontaktní adresu ubytovatele a hostovi potvrzení; schránka ubytovatele je mimo naše mazání.`
- Guest notice en: `Your host receives your registration details by e-mail.`
- Guest notice cs: `Ubytovatel obdrží vaše registrační údaje e-mailem.`
(The guest notice keeps "a completion receipt" earlier in the same paragraph, so the receipt is stated once.)

Out of scope, flagged: German, Spanish and French guest strings (`privacy_email_body`, `claim_email_help`) still say the host gets a copy; they need a translation brief after the lawyer fixes the wording. Terms and `docs/DESIGN.md` need no change.

Tests that pin copy: `App/tests/test_claim_copy.py` pins `claim_email_help` (step 9). Nothing else pins these strings (checked with grep for the old sentences in `App/tests`).

If an excerpt is not found verbatim, STOP (§8).

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/dpa_i18n.py | edit | `dpa.s04_body`, English and Czech (4 edits) |
| App/app/privacy_policy_i18n.py | edit | `privacy.s05_body` and the recipients sentence, English and Czech (4 edits) |
| App/app/i18n.py | edit | `privacy_email_body` and `claim_email_help`, English and Czech (4 edits) |
| App/tests/test_claim_copy.py | edit | the pinned `claim_email_help` strings |

No other file may change.

## 4. Steps

Use the Edit tool; each `old` must be found exactly once in that file, else STOP. After every pair of steps run that file's check command.

1. `App/app/dpa_i18n.py` (English): replace `completion receipts and Controller copies), transmission, encryption ` with `completion receipts), transmission, encryption `.

2. `App/app/dpa_i18n.py` (English): replace the line `            "check-in and never later than 30 days after upload."` with the two lines
```
            "check-in and never later than 30 days after upload. "
            "On the Controller's instruction, given by the Service setting \"Guest details in the confirmation e-mail\" (on by default, switchable in Settings), the Processor sends the guest details of each submitted registration by e-mail to the Controller's contact address; the Controller is responsible for the security of its own mailbox, which the Processor's deletion under Section 15 does not reach."
```
Command: `cd App && .venv/bin/python -c "from app import dpa_i18n as d; print('Controller copies' in d.STRINGS['en']['dpa.s04_body'], 'its own mailbox' in d.STRINGS['en']['dpa.s04_body'])" 2>&1 | tail -30`. Expected: `False True`. If `STRINGS` has another name or shape, STOP and report the error.

3. `App/app/dpa_i18n.py` (Czech): replace `potvrzení a kopie Správci), přenos` with `potvrzení), přenos`.

4. `App/app/dpa_i18n.py` (Czech): replace the line `            "nejpozději 30 dní od nahrání."` with
```
            "nejpozději 30 dní od nahrání. "
            "Na pokyn Správce daný nastavením Služby „Údaje o hostech v potvrzovacím e-mailu“ (ve výchozím stavu zapnuto, lze vypnout v Nastavení) Zpracovatel posílá údaje hostů z každého odeslaného formuláře e-mailem na kontaktní adresu Správce; za zabezpečení vlastní e-mailové schránky odpovídá Správce a mazání Zpracovatele podle čl. 15 se na ni nevztahuje."
```
Command: `cd App && .venv/bin/python -c "from app import dpa_i18n as d; b=d.STRINGS['cs']['dpa.s04_body']; print('kopie Správci' in b, 'vlastní e-mailové schránky' in b)" 2>&1 | tail -30`. Expected: `False True`.

5. `App/app/privacy_policy_i18n.py` (English, `privacy.s05_body`): replace `completion receipts (including a copy to the Host), and ` with `completion receipts, and `.

6. `App/app/privacy_policy_i18n.py` (English, recipients section): replace `Completion receipts may disclose the guest recipient address to the Host copied on the message.` with `On the Host's instruction, set in Settings, we e-mail the details of each submitted registration to the Host's contact address and a receipt to the Guest; the Host's own mailbox is outside our deletion.`

7. `App/app/privacy_policy_i18n.py` (Czech, `privacy.s05_body`): replace the line `            "(včetně kopie ubytovateli) a data pro přenos do UbyPortu či souvisejících systémů "` with `            "a data pro přenos do UbyPortu či souvisejících systémů "`.

8. `App/app/privacy_policy_i18n.py` (Czech, recipients section): replace the two lines
```
            "a případně podpora. Kopie potvrzení o dokončení může ubytovateli zpřístupnit adresu "
            "hosta uvedenou jako příjemce. Údaje hostů mohou být přeneseny do "
```
with
```
            "a případně podpora. Na pokyn ubytovatele daný v Nastavení posíláme údaje z každého odeslaného formuláře e-mailem na kontaktní adresu ubytovatele a hostovi potvrzení; schránka ubytovatele je mimo naše mazání. Údaje hostů mohou být přeneseny do "
```
Command (after 5 to 8): `cd App && grep -c "copy to the Host\|Host copied on the message\|kopie ubytovateli\|Kopie potvrzení" app/privacy_policy_i18n.py | tail -30`. Expected: `0`. Then `cd App && .venv/bin/python -c "import app.privacy_policy_i18n" 2>&1 | tail -30`. Expected: no output.

9. `App/app/i18n.py`, English `privacy_email_body`: replace `"The property manager receives a copy of the completion receipt. The full address "` with `"Your host receives your registration details by e-mail. The full address "`.

10. `App/app/i18n.py`, Czech `privacy_email_body`: replace `"dokončení. Správce objektu obdrží kopii potvrzení. Plná adresa je dostupná "` with `"dokončení. Ubytovatel obdrží vaše registrační údaje e-mailem. Plná adresa je dostupná "`.

11. `App/app/i18n.py`, English `claim_email_help`: replace `and a receipt (your host gets a copy). Shown masked elsewhere.` with `and a receipt. Shown masked elsewhere.`

12. `App/app/i18n.py`, Czech `claim_email_help`: replace `a potvrzení (kopii dostane i hostitel). Jinde se adresa zobrazuje zakrytě.` with `a potvrzení. Jinde se adresa zobrazuje zakrytě.`
Command (after 9 to 12): `cd App && grep -c "property manager receives a copy\|Správce objektu obdrží kopii\|your host gets a copy\|kopii dostane i hostitel" app/i18n.py | tail -30`. Expected: `0`.

13. `App/tests/test_claim_copy.py`: replace the line
```
        "receipt (your host gets a copy). Shown masked elsewhere.",
```
with `        "receipt. Shown masked elsewhere.",` and replace the line
```
        "potvrzení (kopii dostane i hostitel). Jinde se adresa zobrazuje "
```
with `        "potvrzení. Jinde se adresa zobrazuje "`.
Command: `cd App && .venv/bin/python -m pytest tests/test_claim_copy.py -q --tb=short -x 2>&1 | tail -30`. Expected: passed. If it fails on another string of `claim_email_help`, STOP.

14. Test-map rows, one command each (text-only change, no template or CSS, so no screenshots and no UX gate):
- Copy row: `cd App && .venv/bin/python -m pytest tests/test_*_i18n.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py tests/test_flash_literals.py -q --tb=short -x 2>&1 | tail -30`. Expected: passed.
- Public/legal row: `cd App && .venv/bin/python -m pytest tests/test_public_*.py tests/test_legal_*.py tests/test_landing_*.py tests/test_terms_copy.py tests/test_wp24_terms_dpa.py -q --tb=short -x 2>&1 | tail -30`. Expected: passed.
- Privacy row: `cd App && .venv/bin/python -m pytest tests/test_privacy_*.py tests/test_claim_copy.py tests/test_guest_languages.py -q --tb=short -x 2>&1 | tail -30`. Expected: passed. A failure about a pinned sentence you changed: fix the pin only if it quotes one of the six old sentences; otherwise STOP.

## 5. Do not touch

- `App/app/mail_notify.py` and `App/app/claim.py` (briefs 1121 and 1122 own them); `App/app/config.py` and every doc (that is 1123b); any template or CSS.
- No new dependency. SQL only through `db.py` helpers (none here). Public repo: no secrets, no real guest data.
- Copy rule 9: one explanation in one place (replace, never add a second sentence); write "no tracking cookies", never "no cookies". No em dashes. The words LAWYER REVIEW must not appear in any shipped string.
- Do not translate into German, Spanish or French.

## 6. Commands

As in the steps; all end `| tail -30`. No full suite.

## 7. Acceptance

- [ ] The two `grep -c` checks print `0`; the two dpa checks print `False True`.
- [ ] `test_claim_copy.py`, and the three test-map rows pass.
- [ ] `git diff --stat` lists only the four §3 files.
- [ ] PR opened as DRAFT; the report's first line says "DRAFT, waiting for the lawyer".

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1123-report.md` (600 tokens at most) and set `Status: review`. First line: "DRAFT, waiting for the lawyer". Then:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `App/app/dpa_i18n.py` `dpa.s04_body`: contract text; the lawyer reads both languages.
- `App/app/privacy_policy_i18n.py`: the recipients sentence replaced in place in both languages.
- German, Spanish, French still say "host gets a copy" until a translation brief.

## Owner steps

1. Send the six sentences in §2 (they are in this brief) to the lawyer with the three questions at the end of `docs/plans/guest-details-mail.md`.
2. When the lawyer answers, tell the orchestrator chat: "lawyer confirmed 1123" (or paste the changed wording).
3. Only then: open the PR on GitHub, click "Ready for review", and merge 1123 and 1123b together. Not before.
