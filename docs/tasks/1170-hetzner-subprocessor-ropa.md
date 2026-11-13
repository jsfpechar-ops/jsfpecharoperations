# 1170: Hetzner in the /subprocessors register and the ROPA (DR step 7)

Status: todo
Legal status: DRAFT, owner + lawyer must sign off, PR never marked ready (only the owner marks it ready after sign-off).
Depends on: none | Base commit: 142f89a | Branch: claude/dr-hetzner-subprocessor
Executor: Haiku 5.5 | Fits one session: 14 tool calls, 30k tokens
Tier: A (legal copy). Review: a fresh reviewer reads the full diff against this brief.

## 1. Objective

Add Hetzner Online GmbH as a conditional disaster-recovery subprocessor to the public `/subprocessors` register (English and Czech), bump the register to Version 1.3, and record it in the ROPA and the vendor evidence file. Owner decision 2 of 2026-11-12 (docs/plans/portable-disaster-recovery.md, step 7): Hetzner must be in the register and the ROPA before any real data goes there, the restore drill included.

## 2. Context

- AGENTS.md rule 2 (privacy first), rule 9 ("no tracking cookies", one explanation in one place). No em dashes or en dashes anywhere (`App/tests/test_no_em_dashes.py`): use only the plain hyphen `-` and the characters given below.
- The template `App/app/templates/subprocessors.html` loops over `subprocessor_ids` (`{% for sid in subprocessor_ids %}` ... `t('subprocessors.' ~ sid ~ '_provider')`), so a new row needs only the id in `SUBPROCESSOR_IDS` plus five string keys per language. **No template changes** (rule 7 would then apply).
- `App/app/subprocessors_i18n.py` comment (LD-4): backup rows must not call the off-site copies encrypted. The Hetzner strings below do not say "encrypt" / "šifrovan".
- `App/tests/test_privacy_legal_positions.py::test_the_register_lists_the_section_5_subprocessors_with_safeguards` already asserts that every id in `SUBPROCESSOR_IDS` renders all five fields in en and cs, and that the first five ids are unchanged. Hetzner goes last, so that test covers it once the keys exist.
- `App/tests/test_privacy_legal_positions.py::test_no_draft_markers_remain` forbids the words `DRAFT` / `NÁVRH` in `subprocessors_i18n.py`. Do not write them there.
- `App/tests/test_legal_contents.py::test_the_register_records_the_corrective_version` asserts `Version 1.2` / `Verze 1.2`; it changes to 1.3 here.
- **Version and effective date (orchestrator's choice and reason).** The register's own clause `subprocessors.change_body` and DPA section 11 (`App/app/dpa_i18n.py`, `dpa.s11_body`) promise: "notify Controller account contacts at least 30 days before a new Subprocessor handles live Guest Data", "where practicable", with a right to object. A drill with real backup data is Hetzner handling live Guest Data. So the register goes to **Version 1.3** with an effective date that is **at least 30 days after the notice to hosts**. This brief writes the proposed date **15 December 2026** (notice sent by 15 November 2026). The owner confirms or moves the date (Owner steps 3 and 4) before the PR leaves draft. No notice mailing is built here.
- Not changed here (open points for the lawyer, see Owner steps): DPA section 11 names the subprocessors one by one and does not name Hetzner; `docs/UbyHost_workplan/04_legal_positions.md` section 5 table; brief 0329 (docs-only, todo) also planned a "register v1.3" with Anthropic. Whichever ships second takes Version 1.4.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/routes/legal.py` | edit | add `"hetzner"` to `SUBPROCESSOR_IDS`, update the comment above it |
| `App/app/subprocessors_i18n.py` | edit | version/date line en + cs; five `hetzner_*` keys en + cs |
| `App/tests/test_legal_contents.py` | edit | version 1.3 assertion; new test that the Hetzner row renders in en and cs |
| `docs/privacy/ROPA.md` | edit | section A Transfers row, section B Backups row, one open question for counsel |
| `docs/vendors/README.md` | edit | one Hetzner row in the Subprocessors table |
| `docs/tasks/1170-report.md` | create | the report |

No other file may change.

## 4. Steps

Apply each edit with an exact search and replace. Before each, check the old text with `grep -nF` (first line of the old block is enough); not found: STOP (§8). Indentation is spaces, exactly as shown.

### Step 1: `App/app/routes/legal.py`

Old:
```
# WP09: the five rows of 04_legal_positions.md section 5 first, then the two
# conditional providers the repo still documents (Render demo, Drive backups).
SUBPROCESSOR_IDS = (
    "aws_lightsail",
    "aws_ses",
    "aws_s3",
    "cloudflare",
    "posthog",
    "render",
    "google",
)
```
New:
```
# WP09: the five rows of 04_legal_positions.md section 5 first, then the
# conditional providers the repo still documents (Render demo, Drive backups,
# Hetzner disaster-recovery host, brief 1170).
SUBPROCESSOR_IDS = (
    "aws_lightsail",
    "aws_ses",
    "aws_s3",
    "cloudflare",
    "posthog",
    "render",
    "google",
    "hetzner",
)
```
Commit `1170 step 1`.

### Step 2: `App/app/subprocessors_i18n.py`, English

2a. Old:
```
        "subprocessors.effective": "Effective date: 4 October 2026. Version 1.2.",
```
New:
```
        "subprocessors.effective": "Effective date: 15 December 2026. Version 1.3.",
```

2b. Old (exactly one line, English block):
```
        "subprocessors.recipients_title": "Recipients that are not subprocessors",
```
New:
```
        # Brief 1170 (DR plan step 7): conditional disaster-recovery host. The
        # effective date above is at least 30 days after the notice to hosts
        # (change_body); the owner confirms it.
        "subprocessors.hetzner_provider": "Hetzner Online GmbH",
        "subprocessors.hetzner_purpose": (
            "Disaster-recovery hosting: a replacement server used only if the main hosting is "
            "unavailable, and for restore drills."
        ),
        "subprocessors.hetzner_data": "All app data, including Guest Data, restored from backup.",
        "subprocessors.hetzner_location": (
            "EU, Germany or Finland. Conditional; used only during a recovery or a drill."
        ),
        "subprocessors.hetzner_safeguard": (
            "Hetzner data processing agreement under Art. 28 GDPR. No transfer outside the EU."
        ),
        "subprocessors.recipients_title": "Recipients that are not subprocessors",
```
Commit `1170 step 2`.

### Step 3: `App/app/subprocessors_i18n.py`, Czech

3a. Old:
```
        "subprocessors.effective": "Účinnost od: 4. října 2026. Verze 1.2.",
```
New:
```
        "subprocessors.effective": "Účinnost od: 15. prosince 2026. Verze 1.3.",
```

3b. Old (exactly one line, Czech block):
```
        "subprocessors.recipients_title": "Příjemci, kteří nejsou dalšími zpracovateli",
```
New:
```
        "subprocessors.hetzner_provider": "Hetzner Online GmbH",
        "subprocessors.hetzner_purpose": (
            "Hosting pro obnovu po havárii: náhradní server, který se použije jen tehdy, když "
            "hlavní hosting není dostupný, a pro zkoušky obnovy."
        ),
        "subprocessors.hetzner_data": "Všechna data aplikace včetně údajů hostů, obnovená ze zálohy.",
        "subprocessors.hetzner_location": (
            "EU, Německo nebo Finsko. Podmíněné použití; jen při obnově nebo zkoušce obnovy."
        ),
        "subprocessors.hetzner_safeguard": (
            "Smlouva Hetzner o zpracování osobních údajů podle čl. 28 GDPR. Bez předání mimo EU."
        ),
        "subprocessors.recipients_title": "Příjemci, kteří nejsou dalšími zpracovateli",
```
Commit `1170 step 3`.

### Step 4: `App/tests/test_legal_contents.py`

Old:
```
def test_the_register_records_the_corrective_version():
    client = _client()
    for lang, effective in (("en", "Version 1.2"), ("cs", "Verze 1.2")):
        assert effective in client.get(f"/subprocessors?lang={lang}").text, lang
```
New:
```
def test_the_register_records_the_corrective_version():
    client = _client()
    for lang, effective in (("en", "Version 1.3"), ("cs", "Verze 1.3")):
        assert effective in client.get(f"/subprocessors?lang={lang}").text, lang


# Brief 1170 (DR plan step 7): Hetzner is listed before any real data goes
# there, as a conditional EU disaster-recovery host.
def test_the_register_lists_hetzner_as_conditional_recovery_host():
    client = _client()
    for lang in ("en", "cs"):
        html = client.get(f"/subprocessors?lang={lang}").text
        assert "Hetzner Online GmbH" in html, lang
        for field in ("purpose", "data", "location", "safeguard"):
            value = SUBPROCESSOR_STRINGS[lang][f"subprocessors.hetzner_{field}"]
            assert value in html, (lang, field)
            for claim in ENCRYPTION_CLAIMS:
                assert claim not in value.lower(), (lang, field)
```
Commit `1170 step 4`.

### Step 5: `docs/privacy/ROPA.md`

5a. Old:
```
| Transfers | Cloudflare is a global edge network; AWS production is `eu-central-1`; see the register and LD-9 |
```
New:
```
| Transfers | Cloudflare is a global edge network; AWS production is `eu-central-1`; Hetzner Online GmbH (Germany or Finland, EU) is the conditional disaster-recovery host, used only if the main hosting is unavailable or for a restore drill, no transfer outside the EU; see the register and LD-9 |
```

5b. Old:
```
| Backups | Encrypted `age` snapshots of the database and key | Disaster recovery | Legal obligation / security | `UBYHOST_BACKUP_RETENTION_DAYS` (30) |
```
New:
```
| Backups | Encrypted `age` snapshots of the database and key; restored to Hetzner Online GmbH (EU) only during a recovery or a restore drill | Disaster recovery | Legal obligation / security | `UBYHOST_BACKUP_RETENTION_DAYS` (30) |
```

5c. Old:
```
- Door codes: ship the host-provider copy and confirm TTLock's platform terms ([DOOR_CODES_LEGAL](DOOR_CODES_LEGAL.md) section 9).
```
New:
```
- Door codes: ship the host-provider copy and confirm TTLock's platform terms ([DOOR_CODES_LEGAL](DOOR_CODES_LEGAL.md) section 9).
- Hetzner (disaster-recovery host, brief 1170): confirm the Hetzner data processing agreement, and whether adding a conditional recovery subprocessor needs the 30-day prior notice to hosts under DPA section 11 (and whether a real outage before the effective date counts as "not practicable"); whether DPA section 11, which names the subprocessors one by one, must name Hetzner.
```
Commit `1170 step 5`.

### Step 6: `docs/vendors/README.md`

Old:
```
| Google Drive | Optional off-site backup | **Workspace/Cloud only** — the Cloud Data Processing Addendum. A consumer account has no processor DPA | Retire unless it is a Workspace account (OPS-2) | TODO |
```
New:
```
| Google Drive | Optional off-site backup | **Workspace/Cloud only** — the Cloud Data Processing Addendum. A consumer account has no processor DPA | Retire unless it is a Workspace account (OPS-2) | TODO |
| Hetzner Online GmbH | Conditional disaster-recovery host (replacement server, restore drills) | Hetzner data processing agreement (Art. 28 GDPR), concluded in the Hetzner console | EU: Germany or Finland; record the server location here | TODO |
```
(The Google Drive line already contains a dash; copy it unchanged. Do not add new dashes.)
Commit `1170 step 6`.

### Step 7: tests (§6), then the report (§9).

## 5. Do not touch

- Any template (`App/app/templates/*`), CSS, `App/app/dpa_i18n.py`, `App/app/privacy_policy_i18n.py`, `docs/UbyHost_workplan/04_legal_positions.md`, `docs/plans/portable-disaster-recovery.md` (including its owner decision 4), deploy scripts, `scripts/`.
- No mailing or notice code. No new dependency (rule 4). Never push, merge or mark the PR ready.

## 6. Commands

From `App/`:
```
.venv/bin/python -m pytest tests/test_legal_contents.py tests/test_no_em_dashes.py tests/test_wp24_terms_dpa.py tests/test_privacy_legal_positions.py tests/test_ttlock_host_provider.py tests/test_owner_decisions.py tests/test_public_legal.py -q --tb=short -x 2>&1 | tail -30
```
Expected: all passed, 0 failed. Cloud clones have no `App/.venv`: use `python3 -m pytest` with the same arguments; if conftest imports fail, add `--noconftest` and say so in the report.

From the repo root:
```
python3 scripts/context_lint.py 2>&1 | tail -30
git diff --stat 142f89a 2>&1 | tail -30
```
Expected: lint clean; diff stat shows only the §3 files.

## 7. Acceptance

- [ ] `grep -c "hetzner_" App/app/subprocessors_i18n.py` prints 10.
- [ ] `grep -nF '"hetzner",' App/app/routes/legal.py` finds one line.
- [ ] `grep -c "Version 1.3\|Verze 1.3" App/app/subprocessors_i18n.py` prints 2.
- [ ] `grep -c Hetzner docs/privacy/ROPA.md` prints 3; `grep -c Hetzner docs/vendors/README.md` prints 1 (one line).
- [ ] The §6 tests pass; `git diff --stat` lists only §3 files.

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

Write `docs/tasks/1170-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `App/app/subprocessors_i18n.py`: EN and CS wording match each other and this brief; no dashes; no "encrypt"; no `DRAFT`.
- `App/app/routes/legal.py`: `hetzner` is last; the first five ids are unchanged.
- `docs/privacy/ROPA.md`, `docs/vendors/README.md`: only the lines in steps 5 and 6.

## Owner steps

1. Have the lawyer review the English and Czech Hetzner row and the version line (`App/app/subprocessors_i18n.py`), the three ROPA lines and the vendor row in the PR, and answer the new "Open questions for counsel" item (30-day notice; whether DPA section 11 must name Hetzner; brief 0329 also planned "register v1.3": whichever ships second becomes 1.4).
2. Sign the Hetzner data processing agreement (Art. 28 GDPR) in your Hetzner account (the data processing agreement page of the console; Hetzner calls it "AV-Vertrag"). Do this before this PR merges: the register says the agreement exists. When you create the Hetzner server, choose an EU location only (Falkenstein, Nuremberg or Helsinki): the register says "Server located in the EU only (Germany or Finland)". Write the date and the server location in the Hetzner row of `docs/vendors/README.md` (Checked column).
3. Send the notice to the host account contacts (if the lawyer confirms it is needed): Hetzner is added as a conditional disaster-recovery subprocessor in the EU, with the register link and the 30-day objection period. Note the date you sent it.
4. Set the date the Hetzner row applies from (the register itself stays effective from 4 October 2026) to at least 30 days after the notice date. If it is not 15 December 2026, tell the orchestrator the new date; it changes both lines in `App/app/subprocessors_i18n.py` (`subprocessors.effective`, en and cs).
5. Do not run a restore drill with real data on Hetzner before that effective date.
6. Only after steps 1 to 4: mark the PR ready and merge it with `scripts/merge-pr-on-green.sh`.
