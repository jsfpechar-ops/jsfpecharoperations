# 1031b Stay fee: every Prague spelling is exempt for a Prague flat; a minor too

Status: review. Executor: Claude (subagent). Branch `claude/stayfee-prague-districts`.

## Brief
Owner (2026-11-09): verify that a Czech resident who writes Prague in any common form pays 0 for a
Prague flat (apartment `addr_obec` "Praha" or only `city_en` "Prague"), and that a guest born 2010
pays 0, also after Change on the Check step. A bare district name ("Řepy") stays liable: the guest's
own fault (owner decision; no district alias table). Add tests; fix only a gap the tests find.

## Report
- Gap found and fixed: an en/em dash or minus sign without a number before it ("Praha – Řepy",
  "Praha–Řepy", "Praha—Řepy") was not folded to PRAHA (only "-" was). `stay_fee._obec_key` and the
  `signature.js` key() now treat U+2010–U+2015 and U+2212 as "-". Cache key `20261109-1031b`,
  `tests/static_versions.json` regenerated.
- Unit: `App/tests/test_stay_fee_prague_1031b.py`: Praha/Prague/Prag, Praha 1..22 (both cases),
  Praha 17 - Řepy (with/without diacritics, upper/lower, en dash, comma, brackets), Praha-Řepy,
  praha 6 – Dejvice, Hlavní město Praha, Hl. m. Praha, Prague 17, against apartment towns
  Praha / Prague / Hlavní město Praha / praha and city_en fallback: all exempt. Řepy, repy, REPY,
  Dejvice, Brno, Praha-východ, Praha-západ, Kladno, Pražmo, empty: liable. Non-Czech residence:
  liable. signature.js key() equals Python for every case (node).
- Browser (`test_1031b_prague_spellings_and_minor`, 390 px, both apartment variants): box hidden for
  every Prague form; Řepy and Brno show 150 CZK; Brno adult -> born 2010 hidden -> 2001 shows 150
  -> 2010 hidden again. Minors in every birth format were already covered by
  `test_stay_fee_sametown_1031.py`.
- Ran: `test_stay_fee*.py test_static_versions.py` 880 passed; `test_guest_browser_e2e.py -k 1031`
  5 passed 0 skipped; `test_guest_*.py` (non-e2e) 607 passed; context lint OK.
