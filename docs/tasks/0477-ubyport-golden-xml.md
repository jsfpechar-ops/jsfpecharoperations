# 0477: UbyPort request XML golden files before the Go port of filing
Status: todo
Depends on: none | Base commit: main | Branch: task/0477-ubyport-golden-xml
Executor: Haiku 5.5 | Fits one session: 25 tool calls, 70k tokens
## 1. Objective
Plan v4 step 17 (G5) says: before the submit path is ported, a snapshot test pins the exact request XML Python sends today. This brief adds committed golden files of the `ZapisUbytovane` envelope and a test that fails on any byte change. The Go port (G5) must later produce the same bytes from the same inputs. Test-only: no app code changes, no network, no `ws_uby_test` run.
## 2. Context
- `App/app/ubyport/soap.py`: `build_zapis_ubytovane` (line 104), `GUEST_FIELDS`, `HEADER_FIELDS`, `_node` (line 77, nil and escaping rules), `build_envelope` (line 88, the optional WS-Addressing header).
- `App/app/reporting.py`: `header_from_apartment` (line 115: trimming, upper-casing, truncation to 35/50/32/48 chars, `validation.normalise_zip`), `guest_payload` (line 142: dates as `YYYY-MM-DDT00:00:00`, stay dates falling back to the reservation, `compose_residence`, purpose as int only when all digits, upper-cased nationality, `cPlac`/`cSpz` always nil).
- `reporting.submit_batch` (line 1399) builds `header` and `guests` from DB rows and calls `client.submit`; `UbyportClient._post` (`App/app/ubyport/client.py` line 124) is the single place the envelope leaves the process.
- `App/tests/test_soap.py` shows the existing HEADER/GUEST dict style. Fixture pattern to copy: `App/scripts/crypto_fixtures.py` and `App/tests/test_crypto_fixtures.py` (generator script plus a byte-for-byte test).
- Rule 1 of AGENTS.md: filing correctness beats everything. A golden file that pins today's behaviour is the guard. Do not "fix" anything you notice; list it in the report instead.
## 3. Files
New: `App/scripts/ubyport_golden.py`, `App/tests/test_ubyport_golden.py`, `App/tests/golden/ubyport/*.xml` (one file per case), `App/tests/golden/ubyport/cases.json` (the inputs). Write `docs/tasks/0477-report.md`.
## 4. Steps
1. `cases.json`: a list of cases, each with `name`, `apartment` (dict of the columns `header_from_apartment` reads), `reservation` (`date_from`, `date_to`), `guests` (dicts of the columns `guest_payload` reads), `wsa` (bool). Cover at least:
   - `eu_single`: one EU adult, every field filled, purpose `"10"`.
   - `non_eu_visa`: nationality lower-case `"ua"`, visa number, residence with street and city.
   - `escaping`: surname and note containing `&`, `<`, `>`, `"` and `'`; first name with Czech diacritics (`Řehoř`), a facility name over 35 chars and a contact over 50 chars (to pin truncation).
   - `fallback_dates`: guest `stay_from`/`stay_to` empty, so the reservation dates are used; purpose `"abc"` (becomes nil); note empty (nil).
   - `batch_three`: three guests in one call, header with `addr_obec_cast` empty and a zip with a space (`"110 00"`).
   - `wsa_header`: `eu_single` inputs with `wsa: true`.
   Use only invented data (no real names, document numbers or addresses).
2. `App/scripts/ubyport_golden.py` (header in the style of `crypto_fixtures.py`: dev tool, never run in production, never reads `.env` or the database). For each case: `header_from_apartment(apartment)`, `[guest_payload(g, reservation) for g in guests]`, then `soap.build_zapis_ubytovane(header, guests, auth_code="GOLDEN-AUTH", include_wsa_header=wsa)`. Write `<name>.xml` as UTF-8, no trailing newline added. Print `golden files written: <n>`. Options: `--out DIR` (default `App/tests/golden/ubyport`). If `build_envelope` puts anything time- or random-based in the WSA header (a MessageID, for example), stop and report before going on (section 8).
3. `App/tests/test_ubyport_golden.py`:
   - Regenerating into `tmp_path` matches every committed file byte for byte, and the file count matches `cases.json`.
   - Each committed file parses with `xml.etree.ElementTree.fromstring`.
   - Through the real submit path: seed one apartment, reservation and guest in the test DB the way existing reporting tests do (copy the helper from the nearest test that calls `submit_batch`; grep `submit_batch` in `App/tests`). Monkeypatch `UbyportClient._post` to capture the envelope and return a minimal success response (copy one from an existing test). Assert the captured envelope equals the result of `build_zapis_ubytovane` for the same rows read back from the DB, so the decrypted document number reaches the wire unchanged. Leave the auth code as the test client's.
4. Run the generator once, commit its output, run the tests.
## 5. Do not touch
Everything under `App/app/`, `go/`, other tests, migrations, CI files.
## 6. Commands
From `App/` (create `.venv` with `python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt` if missing):
- `.venv/bin/python scripts/ubyport_golden.py | tail -3`
- `.venv/bin/python -m pytest tests/test_ubyport_golden.py tests/test_soap.py -q --tb=short -x 2>&1 | tail -30`, then check `${PIPESTATUS[0]}` is 0 before pushing.
- From the repo root: `python3 scripts/context_lint.py | tail -3`.
## 7. Acceptance
Six or more golden files committed; the test fails if one byte of any envelope changes; the DB-path test captures the envelope at `_post`. `git diff --stat origin/main...HEAD` lists only section 3 files.
## 8. Stop and ask
Stop if the envelope contains a timestamp, UUID or other value that changes per call, if a case needs an app change to run, or if you would need real personal data.
## 9. Report
`docs/tasks/0477-report.md`: generator output, test tail, the case list, and anything in the current XML that looks wrong to you (do not change it).
