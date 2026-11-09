# 1034: fix RÚIAN address suggestions (always empty today)

Status: todo
Depends on: none | Base: `origin/main` | Branch: `claude/project-thread-8ys90o`
Executor: Haiku 5.5, one run, 30 tool calls (checkpoint at 25: commit, report `Status: blocked`, list what is left). Backend only: no template, CSS or JS change, so rules 7 and 10 do not apply.
You commit locally and run the two test files. You do NOT push, open a PR, merge, or edit docs/context/*. The orchestrator pushes and opens the draft PR.

## 1. Problem (verified live against ČÚZK on 2026-11-09)

`App/app/ruian.py` calls the ČÚZK geocoder and gets candidates, but `_ATTR_KEYS` (StreetName, BuildingNumber, ...) do not exist in the real response. `_fields()` returns `{}` for every candidate and `suggest()` drops all of them, so the list is always empty (host apartment form `/apartments/ruian-suggest`, wizard, guest `/l/{token}/ruian-suggest`). Existing tests mock the wrong shape.

Real candidate (no structured address attributes):
```json
{"address":"Václavské náměstí 1306/55, Nové Město, 11000 Praha 1",
 "location":{"x":-742321.89,"y":-1043891.77,"spatialReference":{"wkid":102067}},
 "score":100,"attributes":{"Type":"AdresniMisto","Match_addr":"...","Score":100}}
```

## 2. Files

Edit only: `App/app/ruian.py`, `App/tests/test_ruian.py`, `App/tests/test_0911_guest_fee_ruian.py` (only if it mocks the old shape). Read `ruian.py` fully first (114 lines).

## 3. Design

Keep unchanged: the geocoder call and `UBYHOST_RUIAN_URL` override, `enabled()`, `usable_query`, rate limit, 24h `_CACHE`, 4 s timeouts, `User-Agent`, `{label, fields}` contract, `[]` on every failure (wrap everything in try/except).

Add one constant `_LAYER_BASE = "https://ags.cuzk.cz/arcgis/rest/services/RUIAN/Vyhledavaci_sluzba_nad_daty_RUIAN/MapServer"`; derive `_DEFAULT_URL` from it (`_LAYER_BASE + "/exts/GeocodeSOE/tables/1/findAddressCandidates"`). No new env var. Layer queries always use `_LAYER_BASE`.

Replace the two UNVERIFIED/TODO comments and `_ATTR_KEYS` with one note: "Verified against the live ČÚZK service on 2026-11-09. Geocoder candidates carry only label and S-JTSK (wkid 102067) point; structure comes from RÚIAN layer queries."

Pipeline in `suggest()`:
1. Geocoder as today. Keep candidates with `score >= _MIN_SCORE` (60) and, if `attributes.Type` is present, `Type == "AdresniMisto"`. Pass the typed text to the geocoder unchanged (no diacritic stripping; ČÚZK matches "Vaclavske namesti 1" itself). Max 6.
2. Resolve each candidate concurrently: `ThreadPoolExecutor(max_workers=_MAX_RESULTS)`, `futures.wait(..., timeout=4)` total deadline; unfinished or failed candidates are dropped. Keep the geocoder order in the output.
3. Per candidate (`_resolve(candidate) -> Optional[dict]`), all via `requests.get(f"{_LAYER_BASE}/{layer}/query", params=..., timeout=4, headers=UA)`:
   - Layer 1 (AdresniMisto): `geometry="x,y"`, `geometryType=esriGeometryPoint`, `inSR=102067`, `spatialRel=esriSpatialRelIntersects`, `distance=2`, `units=esriSRUnit_Meter`, `outFields=kod,cislodomovni,cisloorientacni,cisloorientacnipismeno,psc,ulice,adresa`, `returnGeometry=false`, `f=json`. Response `features[].attributes`. Pick the feature whose `adresa` equals the candidate `address` (compare after `.strip()`); none -> return None (drop candidate).
   - Map: `addr_house_no` = `cislodomovni`; `addr_orient_no` = `cisloorientacni` + `cisloorientacnipismeno` (letter appended, e.g. `55a`; omit when no orientation number); `addr_zip` = `psc` (string, no space).
   - Street: if `ulice` not null, layer 4 (Ulice) `where=kod=<ulice>` (int-cast `ulice` first, never format raw strings into `where`), `outFields=nazev`, `returnGeometry=false`, `f=json` -> `addr_street`. If `ulice` is null (village address without street) leave `addr_street` empty (omit the key).
   - Obec: layer 12 (Obec) point-in-polygon with the same geometry params (no distance), `outFields=nazev,okres` -> `addr_obec` = `nazev`. Okres: layer 15 (Okres) `where=kod=<okres>` (int-cast), `outFields=nazev` -> `addr_okres`. If the layer-15 lookup returns nothing and `addr_obec == "Praha"`, set `addr_okres = "Hlavní město Praha"`. If the Obec query returns nothing, omit both keys.
   - Obec part: layer 11 is a point layer, so do not query it. Only when the label (`address`) has exactly 3 comma segments `street+numbers, part, PSC Obec`, set `addr_obec_cast` to `segment[1].strip()` if it differs from `addr_obec`. Add a comment: "Narrow label use: only the middle segment of a 3-part label, only when it differs from the obec name; no other label parsing."
   - Omit empty values; return `{"label": address, "fields": fields}` only if `fields` has at least `addr_house_no` or `addr_street`.
4. Cache the final list as today (an empty result from a network failure must NOT be cached; cache only when the geocoder call succeeded).

Use small helpers (`_get_json(url, params)` returns dict or `{}` on any error/non-ok; `_layer_query`) so tests can monkeypatch one place. Follow `docs/context/executor.md` style; no new dependency (`concurrent.futures` is stdlib).

## 4. Tests (no network, fixtures inline, real response shapes)

In `App/tests/test_ruian.py`, drop tests that mock the old `StreetName` shape and add (mock `requests.get` or `_get_json`, clear `ruian._CACHE` per test):
1. Happy path: one real-shape candidate (Václavské náměstí 1306/55 above), layer-1 feature `{kod, cislodomovni:1306, cisloorientacni:55, cisloorientacnipismeno:null, psc:11000, ulice:123, adresa:<same string>}`, layer 4 `{nazev:"Václavské náměstí"}`, layer 12 `{nazev:"Praha", okres:3100}`, layer 15 empty -> fields equal `addr_street "Václavské náměstí"`, `addr_house_no "1306"`, `addr_orient_no "55"`, `addr_zip "11000"`, `addr_obec "Praha"`, `addr_okres "Hlavní město Praha"`, `addr_obec_cast "Nové Město"`; label unchanged.
2. Orientation letter appended (`55` + `a` -> `55a`).
3. Candidate with no layer-1 feature whose `adresa` matches is dropped (result `[]`).
4. Candidate with score 40, or `Type` other than `AdresniMisto`, is dropped.
5. Network error (`requests.get` raises) returns `[]` and is not cached; a non-ok response returns `[]`.
6. Village case: `ulice: null`, label `"12, Horní Lhota, 76001 Horní Lhota"` -> no `addr_street` key, `addr_obec_cast` absent (middle segment equals obec), `addr_house_no "12"`.
7. Query "Vaclavske namesti 1" reaches the geocoder `params["SingleLine"]` unchanged.
8. Existing tests for `enabled()`, `usable_query`, rate limit, cache (second identical call does not hit `requests.get` again) stay green.

`test_0911_guest_fee_ruian.py`: run it; edit only if it mocks the old candidate shape (then switch to the helper-level mock returning the final `{label, fields}`).

## 5. Check (only these)

From `App/`: `.venv/bin/python -m pytest tests/test_ruian.py tests/test_0911_guest_fee_ruian.py -q --tb=short -x 2>&1 | tail -30`. Do not run the full suite or the context lint.

JS/template check (read-only, do not edit): `App/app/static/ruian_suggest.js` only reads `item.label` and `item.fields` (lines ~79-126) and `guest/form.html` (~239, ~464) only hosts the list markup, so the `{label, fields}` contract is unchanged and no JS/template change is expected. If you find a dependency on another field shape, stop and report `Status: blocked`.

## 6. Report

Status, commit hash, test output tail (pass counts, 0 skipped), files changed. Privacy (rule 2) note for the PR, written by the orchestrator: no new personal data stored; outbound requests go to the same `ags.cuzk.cz` host, reason: structured RÚIAN lookup, sending only the typed text and public coordinates.
