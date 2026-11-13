# 1203: CSV formula safety in billing exports, and fetch guards for listing photos

Status: todo
Depends on: none | Base commit: 42bf30ce | Branch: task/1203-csv-formula-safety-and-photo-fetch-guards
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

(a) The two platform-admin billing exports write host-controlled text (buyer name, display name, email, bank message) raw into CSV cells, so a value starting with `=`, `+`, `-` or `@` runs as a formula in Excel; wrap those text cells in `csv_safety.csv_safe`. (b) `property_page.download_listing_photos` fetches scraper-supplied https URLs with no private-address check, follows redirects and reads the whole body before the size check; reuse the iCal URL validator, refuse redirects, and stream with a size cut-off.

## 2. Context

Rules: AGENTS.md hard rules 3, 4 (no new dependency), 8 (never push to main; PR stays draft). A skipped photo must never fail the import. No new outbound request is added (the same photo GETs, now guarded); say so in the PR.

`App/app/csv_safety.py` (do not edit): `csv_safe(value)` prefixes `'` only when `value` is a `str` that starts (after leading spaces) with `= + - @ \t \r \n \xa0`. Ints, floats, dates and None are untouched. **Important:** the money cells in both exports come from `_kc(...)` (billing_admin) and `_cz(...)` (billing_analytics), which return STRINGS such as `-50,00` for a storno. Wrapping them would turn negative totals into text. So: wrap only the free-text cells listed in §4, never `_kc`/`_cz` output, dates, invoice numbers, VS or counts.

Excerpt 1, `App/app/billing_admin.py` (imports at lines 9-17, `from . import billing_invoices, db`; `export_csv` lines 88-99):
```python
        writer.writerow((
            row["number"], KIND_CS[row["kind"]], row["corrects_number"] or "", row["issue_date"][:10],
            row["due_date"][:10], row["period_from"][:10], row["period_to"][:10], row["buyer"]["name"],
            row["buyer"]["ico"], row["buyer"]["dic"], _kc(int(row["total_haler"])), row["vs"],
```
Excerpt 2, `App/app/billing_analytics.py` (imports at lines 9-15, `from . import billing, billing_admin, db`; `export_all_zip` from line 187):
```python
            c["display_name"], c["email"], c["status"], c["plan"], c["billing_interval"],
```
and in the payments block (about line 214):
```python
            r["bank_tx_id"], r["received_on"][:10], _cz(r["amount_haler"]), r["vs"] or "",
            r["counter_account"] or "", r["message"] or "", r["status"],
```
Excerpt 3, `App/app/property_page.py` imports (lines 205-211) and constants:
```python
import requests as _requests

from . import config as _config
from . import guide_photos as _guide_photos

MAX_PAGE_PHOTOS = 10
_PHOTO_TIMEOUT = (5, 30)
```
and the loop body in `download_listing_photos` (lines 250-259):
```python
    for url in [u for u in urls if isinstance(u, str) and u.startswith("https://")]:
        if len(already) + len(stored) >= MAX_PAGE_PHOTOS:
            break
        try:
            response = _requests.get(url, timeout=_PHOTO_TIMEOUT)
            if response.status_code != 200:
                continue
            path = store_photo(response.content)
        except (ValueError, _requests.RequestException):
            continue
        stored.append(path)
```
Validator chosen: `app.feed_url.validate_calendar_url(url) -> str`; it raises `feed_url.FeedUrlError` (alias `FeedError`) for bad scheme, credentials, blocked host names, and any resolved private/loopback/link-local/reserved/CGNAT/metadata address. It does one DNS lookup via `feed_url._resolve_host_ips`. In tests `UBYHOST_ICAL_ALLOW_PRIVATE=1` is set in conftest, which makes the validator allow private IPs unless a test sets `config.ICAL_ALLOW_PRIVATE` to False. Known limit (accepted, put it in the SECURITY line): `requests` does its own DNS lookup, so unlike the iCal fetch this is validated, not IP-pinned.

Size constant: `_guide_photos.MAX_UPLOAD_BYTES` (10 MiB, already used in `store_photo`).

Existing tests in `App/tests/test_property_page_photos.py` use fake host `cdn.example.test` (does not resolve) and `_fake_get(urls_to_content, calls)` whose `get(url, timeout=None)` returns `_FakeResponse(content, status_code)` (class `_FakeResponse` near the top, only `.content` and `.status_code`). After the change these fakes must accept `allow_redirects`/`stream` kwargs and offer `iter_content`, `headers`, `close`, and DNS must be faked. If an excerpt is not found verbatim, STOP (§8).

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/billing_admin.py | edit | import `csv_safe`; wrap buyer name, ico, dic in `export_csv` |
| App/app/billing_analytics.py | edit | import `csv_safe`; wrap display_name, email in customers rows; counter_account, message in payments rows |
| App/app/property_page.py | edit | add `_fetch_photo_bytes`; use it in `download_listing_photos` |
| App/tests/test_billing_admin.py | edit | add formula and negative-amount tests |
| App/tests/test_billing_analytics.py | edit | add formula test for the bulk zip |
| App/tests/test_property_page_photos.py | edit | update fakes, add private-IP, redirect, oversize tests |
| docs/SECURITY.md | edit | one line after the "iCal SSRF" bullet (line 24) |

No other file may change.

## 4. Steps

1. `App/app/billing_admin.py`. Run `grep -nF "from . import billing_invoices, db" App/app/billing_admin.py`. Add directly below that line: `from .csv_safety import csv_safe`. In `export_csv`, replace `row["buyer"]["name"],` with `csv_safe(row["buyer"]["name"]),` and replace `row["buyer"]["ico"], row["buyer"]["dic"],` with `csv_safe(row["buyer"]["ico"]), csv_safe(row["buyer"]["dic"]),`. Leave everything else on those lines, including `_kc(...)`. Run `cd App && .venv/bin/python -m pytest tests/test_billing_admin.py -q --tb=short -x 2>&1 | tail -30`. Commit `1203 step 1`.

2. `App/app/billing_analytics.py`. Add below `from . import billing, billing_admin, db`: `from .csv_safety import csv_safe`. In `export_all_zip`: change `c["display_name"], c["email"],` to `csv_safe(c["display_name"]), csv_safe(c["email"]),`; change `r["counter_account"] or "", r["message"] or "",` to `csv_safe(r["counter_account"] or ""), csv_safe(r["message"] or ""),`. Do not touch `_csv_bytes`, `_cz`, or the invoices block. Run `cd App && .venv/bin/python -m pytest tests/test_billing_analytics.py -q --tb=short -x 2>&1 | tail -30`. Commit `1203 step 2`.

3. `App/tests/test_billing_admin.py`. Append at the end of the file (imports `csv`, `io`, `pytest`, `billing_admin` already exist at the top):
```python
@pytest.mark.parametrize("prefix", ["=", "+", "-", "@"])
def test_export_csv_neutralises_formula_buyer_names_and_keeps_amounts(monkeypatch, prefix):
    evil = prefix + "HYPERLINK(\"http://x.test\")"
    row = {
        "number": "2026001", "kind": "storno", "corrects_number": "", "issue_date": "2026-05-01",
        "due_date": "2026-05-15", "period_from": "2026-05-01", "period_to": "2026-05-31",
        "buyer": {"name": evil, "ico": "27074358", "dic": prefix + "CZ1"},
        "total_haler": -5000, "vs": "2026001", "paid_on": None, "paid_via": None, "voided": 0,
    }
    monkeypatch.setattr(billing_admin, "invoices", lambda month: [row])
    text = billing_admin.export_csv("2026-05").decode("utf-8-sig")
    cells = list(csv.reader(io.StringIO(text), delimiter=";"))[1]
    assert cells[7] == "'" + evil
    assert cells[9] == "'" + prefix + "CZ1"
    assert cells[10] == "-50,00"  # a storno total stays a plain number string
```
Run `cd App && .venv/bin/python -m pytest tests/test_billing_admin.py -q --tb=short -x 2>&1 | tail -30`. Commit `1203 step 3`.

4. `App/tests/test_billing_analytics.py`. Append at the end (this file's `setup` fixture, `login_as`, `TestClient`, `zipfile`, `csv`, `io`, `db`, `app` are already imported; `setup["host_id"]`: check with `grep -n 'yield' App/tests/test_billing_analytics.py`; if the fixture yields no `host_id`, STOP and report):
```python
@pytest.mark.parametrize("prefix", ["=", "+", "-", "@"])
def test_the_bulk_zip_neutralises_formula_display_names(setup, prefix):
    evil = prefix + "SUM(A1)"
    db.execute("UPDATE user_account SET display_name = ? WHERE id = ?", (evil, setup["host_id"]))
    client = TestClient(app)
    login_as(client, setup["admin"], url="/login?lang=cs")
    response = client.get("/admin/fakturace/export-vse")
    zf = zipfile.ZipFile(io.BytesIO(response.content))
    text = zf.read("zakaznici.csv").decode("utf-8-sig")
    names = [r[0] for r in csv.reader(io.StringIO(text), delimiter=";")][1:]
    assert "'" + evil in names and evil not in names
```
Run `cd App && .venv/bin/python -m pytest tests/test_billing_analytics.py -q --tb=short -x 2>&1 | tail -30`. Commit `1203 step 4`.

5. `App/app/property_page.py`. Below `from . import guide_photos as _guide_photos` add `from . import feed_url as _feed_url`. Directly above `def download_listing_photos` add:
```python
def _fetch_photo_bytes(url: str):
    """The photo's bytes, or None to skip it: a private or reserved address,
    a redirect, a non-200 answer or a body over the upload cap. The body is
    streamed and the connection closed as soon as the cap is passed."""
    try:
        _feed_url.validate_calendar_url(url)
    except _feed_url.FeedUrlError:
        return None
    response = _requests.get(
        url, timeout=_PHOTO_TIMEOUT, allow_redirects=False, stream=True
    )
    try:
        if response.status_code != 200:
            return None
        limit = _guide_photos.MAX_UPLOAD_BYTES
        body = bytearray()
        for chunk in response.iter_content(chunk_size=64 * 1024):
            body.extend(chunk)
            if len(body) > limit:
                return None
        return bytes(body)
    finally:
        response.close()
```
In the loop, replace
```python
            response = _requests.get(url, timeout=_PHOTO_TIMEOUT)
            if response.status_code != 200:
                continue
            path = store_photo(response.content)
```
with
```python
            content = _fetch_photo_bytes(url)
            if content is None:
                continue
            path = store_photo(content)
```
Keep the `except (ValueError, _requests.RequestException): continue` as is. Do not run tests yet (existing fakes break until step 6). Commit `1203 step 5`.

6. `App/tests/test_property_page_photos.py`. (a) Find both with `grep -n "class _FakeResponse\|def _fake_get" App/tests/test_property_page_photos.py` and replace the whole class and the whole function with:
```python
class _FakeResponse:
    def __init__(self, content: bytes, status_code: int = 200):
        self.content = content
        self.status_code = status_code
        self.headers = {}
        self.closed = False
        self.chunks_read = 0

    def iter_content(self, chunk_size=1):
        for i in range(0, len(self.content), chunk_size):
            self.chunks_read += 1
            yield self.content[i:i + chunk_size]

    def close(self):
        self.closed = True


def _fake_get(urls_to_content, calls):
    def get(url, timeout=None, **kwargs):
        calls.append((url, kwargs))
        return _FakeResponse(urls_to_content.get(url, b""))
    return get


@pytest.fixture(autouse=True)
def _public_dns(monkeypatch):
    """No real DNS: every photo host resolves to a public address."""
    import ipaddress
    monkeypatch.setattr("app.feed_url._resolve_host_ips",
                        lambda host: [ipaddress.ip_address("93.184.216.34")])
```
(b) Existing tests only use `calls` with `append`/ignore; confirm with `grep -n "calls" App/tests/test_property_page_photos.py` that none compares `calls` to a list of URLs; if one does, adapt it to `[c[0] for c in calls]`. (c) Append three tests:
```python
def test_download_skips_private_addresses_without_fetching(owner, monkeypatch):
    import ipaddress
    from app import config
    monkeypatch.setattr(config, "ICAL_ALLOW_PRIVATE", False)
    monkeypatch.setattr("app.feed_url._resolve_host_ips",
                        lambda host: [ipaddress.ip_address("169.254.169.254")])
    calls = []
    monkeypatch.setattr("app.property_page._requests.get", _fake_get({}, calls))
    assert property_page.download_listing_photos(owner, ["https://cdn.example.test/a.jpg"]) == 0
    assert calls == []


def test_download_refuses_redirects(owner, monkeypatch):
    calls = []
    def get(url, timeout=None, **kwargs):
        calls.append(kwargs)
        return _FakeResponse(b"", 302)
    monkeypatch.setattr("app.property_page._requests.get", get)
    assert property_page.download_listing_photos(owner, ["https://cdn.example.test/a.jpg"]) == 0
    assert calls and calls[0]["allow_redirects"] is False and calls[0]["stream"] is True


def test_download_stops_reading_an_oversized_body(owner, monkeypatch):
    big = _FakeResponse(b"x" * (property_page._guide_photos.MAX_UPLOAD_BYTES + 5 * 64 * 1024))
    monkeypatch.setattr("app.property_page._requests.get", lambda url, timeout=None, **kw: big)
    assert property_page.download_listing_photos(owner, ["https://cdn.example.test/a.jpg"]) == 0
    assert big.closed is True
    assert big.chunks_read < (len(big.content) // (64 * 1024))  # stopped early
```
Run `cd App && .venv/bin/python -m pytest tests/test_property_page_photos.py -q --tb=short -x 2>&1 | tail -30`. Commit `1203 step 6`.

7. `docs/SECURITY.md`. Run `grep -nF "**iCal SSRF**" docs/SECURITY.md`. Insert one new bullet directly after that bullet:
`- **Listing photo fetch**: the host's own import re-hosts OTA photos only after \`feed_url.validate_calendar_url\` accepts the URL (no private, loopback, link-local, metadata addresses); redirects are not followed, the body is streamed and cut at the 10 MiB upload cap. Validated but not IP-pinned (\`requests\` resolves again).`
(Write it without the backslashes before backticks.) Run `python3 scripts/context_lint.py 2>&1 | tail -30` from the repo root. Commit `1203 step 7`.

## 5. Do not touch

`App/app/csv_safety.py`, `App/app/feed_url.py`, `App/app/feed_fetch.py`, `App/app/guest_guide_import.py`, `_csv_bytes`, `_kc`, `_cz`, any template or CSS, `docs/context/known-issues.md`. No new dependency. No host allowlist. Do not wrap money, date, number, invoice number or VS cells. Hard rule 2: no new outbound request.

## 6. Commands

From `App/`, each ending `2>&1 | tail -30`:

- `.venv/bin/python -m pytest tests/test_billing_admin.py tests/test_billing_analytics.py -q --tb=short -x 2>&1 | tail -30` expect all pass (test-map row "Platform billing": `test_billing_*.py`; run only these two plus the next).
- `.venv/bin/python -m pytest tests/test_property_page_photos.py tests/test_guest_guide_import.py -q --tb=short -x 2>&1 | tail -30` expect all pass (test-map row "Public property pages" photo file; guide import test mocks the download).
- Repo root: `python3 scripts/context_lint.py 2>&1 | tail -30` expect no error.

## 7. Acceptance

- [ ] `grep -n "csv_safe" App/app/billing_admin.py App/app/billing_analytics.py | tail -30` shows the import and the wrapped cells; `_kc`/`_cz` calls are not wrapped.
- [ ] New CSV tests pass for `=`, `+`, `-`, `@`; the storno total stays `-50,00`.
- [ ] `grep -n "allow_redirects=False" App/app/property_page.py` and `grep -n "stream=True" App/app/property_page.py` each match once.
- [ ] Private-IP, redirect and oversize photo tests pass with no real network; existing photo tests still pass.
- [ ] SECURITY.md has the new bullet; context lint passes.
- [ ] `git diff --stat` shows only the §3 files.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear (for example the analytics `setup` fixture has no `host_id`);
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1203-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

Open one draft PR. PR text: state that no new outbound request is added (same photo GETs, now guarded), no new dependency, no schema change.

## Risk list (for the reviewer)

- `App/app/property_page.py` (`_fetch_photo_bytes`: validator, redirect refusal, stream cut-off).
- `App/app/billing_admin.py` and `App/app/billing_analytics.py` (only text cells wrapped; money strings untouched).
- `App/tests/test_property_page_photos.py` (autouse DNS fake, new fakes).

## Owner steps

1. Open the draft PR on GitHub and read the diff of the three app files above.
2. When CI is green and you are happy, mark the PR ready.
3. Merge with `scripts/merge-pr-on-green.sh <PR number>`; the green merge deploys by itself.
