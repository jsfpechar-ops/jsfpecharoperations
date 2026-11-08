# 1031 report: Prague district forms of the property obec

Status: review

## What changed

- `App/app/stay_fee.py` `_obec_key`: after `fold_text`, strips a leading `HLAVNI MESTO `, `HL. M. `, `HL.M. `, `STATUTARNI MESTO ` or `MESTO ` prefix. A statutory base (`STATUTORY_DISTRICT_BASES`) then folds when it is followed by end, an optional space and digits, then end, a hyphen, a comma or an opening parenthesis. `OBEC_ALIASES` (PRAGUE to PRAHA) applies last.
- A hyphen followed by VYCHOD or ZAPAD (Praha-vychod, Praha-zapad) does not fold; the text stays as written.
- `App/tests/test_stay_fee_obec_forms_1031.py` (new): 33 tests, pure `_obec_key` cases plus `same_obec_resident` with `res_city` Prague.

## Test runs

- `tests/test_stay_fee*.py` plus the 1025 and 1026 files: 336 passed, 0 skipped.
- New file alone: 33 passed.

## Deviations from the brief

- After a base, a space must be followed by digits and then end, a hyphen, a comma or a parenthesis. A plain space is not enough: the existing test `test_same_obec_matching_rules` expects "Praha 5 Brno" NOT to match "Praha".
- Consequence of the prefix strip: "Mesto Kladno" now folds to KLADNO (was MESTO KLADNO).
- Commit trailer uses the Haiku 5.5 co-author line required by the session attribution rule, not Sonnet 5.5 as the brief said.
- No PR opened, per the brief.

## Before and after `_obec_key`

| Form | Before | After |
|---|---|---|
| Praha 1 - Staré Město | PRAHA 1 - STARE MESTO | PRAHA |
| Praha 3 - Žižkov | PRAHA 3 - ZIZKOV | PRAHA |
| Hlavní město Praha | HLAVNI MESTO PRAHA | PRAHA |
| Hl. m. Praha | HL. M. PRAHA | PRAHA |
| Praha, Staré Město | PRAHA, STARE MESTO | PRAHA |
| Praha 5 (Smíchov) | PRAHA 5 (SMICHOV) | PRAHA |
| Statutární město Brno | STATUTARNI MESTO BRNO | BRNO |
| Praha-východ | PRAHA | PRAHA-VYCHOD |
| Praha-západ | PRAHA | PRAHA-ZAPAD |
| Praha-Smichov | PRAHA | PRAHA |
| Prague | PRAHA | PRAHA |
