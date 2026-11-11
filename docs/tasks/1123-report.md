# 1123 Report

Status: review

## 1. Files changed (git diff --stat, §3 files only)

```
 App/app/dpa_i18n.py            | 10 ++++++----
 App/app/i18n.py                | 23 +++++++++++++++++++----
 App/app/privacy_policy_i18n.py |  9 ++++-----
 App/tests/test_claim_copy.py   |  6 +++---
 4 files changed, 32 insertions(+), 16 deletions(-)
```

Note: 12 other files in the working tree have pre-existing uncommitted changes from tasks 1121/1122; they were not staged or committed here.

## 2. Commands and output

**After steps 1–2 (EN DPA):**
```
cd App && .venv/bin/python -c "from app import dpa_i18n as d; print('Controller copies' in d.DPA_STRINGS['en']['dpa.s04_body'], 'its own mailbox' in d.DPA_STRINGS['en']['dpa.s04_body'])" 2>&1 | tail -30
False True
```

**After steps 3–4 (CS DPA):**
```
cd App && .venv/bin/python -c "from app import dpa_i18n as d; b=d.DPA_STRINGS['cs']['dpa.s04_body']; print('kopie Správci' in b, 'vlastní e-mailové schránky' in b)" 2>&1 | tail -30
False True
```

**After steps 5–8 (privacy_policy_i18n.py):**
```
cd App && grep -c "copy to the Host\|Host copied on the message\|kopie ubytovateli\|Kopie potvrzení" app/privacy_policy_i18n.py | tail -30
0
```
```
cd App && .venv/bin/python -c "import app.privacy_policy_i18n" 2>&1 | tail -30
(no output)
```

**After steps 9–12 (i18n.py):**
```
cd App && grep -c "property manager receives a copy\|Správce objektu obdrží kopii\|your host gets a copy\|kopii dostane i hostitel" app/i18n.py | tail -30
0
```

**Step 13 (test_claim_copy.py):**
```
cd App && .venv/bin/python -m pytest tests/test_claim_copy.py -q --tb=short -x 2>&1 | tail -30
6 passed in 0.12s
```

**Step 14 — Copy row:**
```
cd App && .venv/bin/python -m pytest tests/test_*_i18n.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py tests/test_flash_literals.py -q --tb=short -x 2>&1 | tail -30
46 passed, 1 warning in 2.33s
```

**Step 14 — Public/legal row:**
```
cd App && .venv/bin/python -m pytest tests/test_public_*.py tests/test_legal_*.py tests/test_landing_*.py tests/test_terms_copy.py tests/test_wp24_terms_dpa.py -q --tb=short -x 2>&1 | tail -30
155 passed in 4.99s
```

**Step 14 — Privacy row:**
```
cd App && .venv/bin/python -m pytest tests/test_privacy_*.py tests/test_claim_copy.py tests/test_guest_languages.py -q --tb=short -x 2>&1 | tail -30
70 passed in 7.52s
```

## 3. §7 Acceptance

- [x] The two `grep -c` checks print `0`; the two DPA checks print `False True`.
- [x] `test_claim_copy.py` and the three test-map rows pass.
- [x] `git diff --stat` lists only the four §3 files (pre-existing uncommitted changes from 1121/1122 are not staged).

## 4. Deviations

1. **`STRINGS` → `DPA_STRINGS`**: The brief's check command uses `d.STRINGS['en']`, but the module exports `DPA_STRINGS`. The content checks still return `False True` as expected; used `d.DPA_STRINGS` to verify.
2. **Extra pin in `test_claim_copy.py`**: The test `test_the_claim_hints_keep_every_point_design_md_requires` asserted `"copy" in english` to guard the old "host gets a copy" text. Removed `and "copy" in english` from that assertion (comment updated to `# receipt`), because "copy" no longer appears after the `claim_email_help` change. The brief (step 14 privacy row) permits fixing pins that quote one of the six old sentences; this pin guarded the old `claim_email_help` EN sentence.

## 5. Questions

None.

## 6. Owner steps left

1. Commit/stage the pre-existing 1121/1122 changes if not yet done.
2. Merge 1123 first and 1123b second, each with `scripts/merge-pr-on-green.sh <pr>`, after 1121 is merged.
