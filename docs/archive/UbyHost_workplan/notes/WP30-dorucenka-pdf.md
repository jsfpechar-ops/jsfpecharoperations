# WP30: Request and store the Doručenka PDF correctly

Base: `origin/main` 709076a (includes PR 230). Worktree `/tmp/wp/wp30`, branch `wp30`, commit b124b7f. Not stacked on any other WP.

## Summary

Root cause: the client sent `VracetPDF` as the last child of `Seznam`, after `uStr`. WCF's DataContractSerializer orders members by ordinal comparison, so `VracetPDF` belongs straight after `Ubytovani` and before `uCont`. It reads members strictly in that order and skips an element whose slot has already passed. The flag was therefore dropped and defaulted to false. UbyPort accepted the guests and returned the stamp (`PseudoRazitko`), but no `DokumentPotvrzeni`. That is the live symptom.

Fix: `VracetPDF` is now sent in its contract position. The parser checks the PDF before it is stored. The client logs the names of the response elements. The mock now reads `Seznam` like WCF does, so it would have caught this bug.

### Facts from the official documents

Source: "Technický popis webové služby Ubyport", Příloha č. 5 k Provoznímu řádu, update of 19. 6. 2019 (https://policie.gov.cz/soubor/ubytovani-dokumenty-ubyportpr5-pdf.aspx). Also the FAQ pro vývojáře.

- Methods (section 3): only `TestDostupnosti`, `MaximalniDelkaSeznamu`, `DejMiCiselnik` and `ZapisUbytovane`. `ZapisUbytovane` "Vloží seznam ubytovaných a vrátí záznam o zpracování a to jak formou seznamu chyb v datové třídě tak v PDF dokumentu." No method returns a PDF later, so no "Fetch Doručenka again" action was built.
- Class `SeznamUbytovanych` (section 4.2): "Boolean VracetPDF Příznak oznamující, že ubytovatel chce v odpovědi také PDF dokumenty *)" with "*) doplněno na základě změnového požadavku z prosince 2016". Members, in declaration order: VracetPDF, uIdub, uMark, uName, uCont, uOkr, uOb, uObCa, UStr/uStr, uHomN, uOriN, uPsc, Ubytovani.
- Wire format (section 5.1.1, a WCFTestClient capture): `<ZapisUbytovane xmlns="http://UBY.pcr.cz/WS_UBY"><Seznam xmlns:d4p1="http://schemas.datacontract.org/2004/07/WS_UBY" ...>` with children in this order: `d4p1:Ubytovani`, `uCont`, `uHomN`, `uIdub`, `uMark`, `uName`, `uOb`, `uObCa`, `uOkr`, `uOriN`, `uPsc`, `uStr`. That is ordinal order (upper case before lower case). The example has no `VracetPDF`; it predates the 2016 change.
- Class `Chyby` (section 4.2): "String DokumentPotvrzeni PDF dokument ve tvaru basecode64 obsahující potvrzení o zpracování dat"; "String DokumentChybyPotvrzeni PDF dokument ve tvaru basecode64 obsahující chyby ve zpracovaných datech"; "String PseudoRazitko Značka, která je obsažena v PDF dokumentu."
- Response (section 5.1.1): `ZapisUbytovaneResponse` / `ZapisUbytovaneResult xmlns:a="http://schemas.datacontract.org/2004/07/WS_UBY"`, with `a:ChybyHlavicky` and `a:ChybyZaznamu` (b:string items). Section 5.1.4 (XmlSerializer sample) shows `<DokumentPotvrzeni>JVBERi0x...</DokumentPotvrzeni>` with the base64 broken across lines, and spells the stamp `PseudoRazirko`.
- Section 7: "Nepřekládat názvy nodů SOAP, pokud je SOAP tělo vytvářeno jiným způsobem, než použitím přístupových tříd."
- FAQ: "Objekty „VracetPDF“, „uIdub“, „uMark“ a „Ubytovani“ jsou povinné".
- The WSDL (`?singleWsdl`, `?wsdl`, `?xsd=xsd0..xsd3` on ubyport.policie.cz) returned empty responses from this environment. I made no further attempts.

### Comparison with the code before WP30

| Area | Before | Contract | Verdict |
|---|---|---|---|
| Request, Seznam order | Ubytovani, uCont..uStr, **VracetPDF** | Ordinal: Ubytovani, **VracetPDF**, uCont..uStr | Wrong. Fixed |
| Request, names and namespaces | `http://UBY.pcr.cz/WS_UBY` for the method and Seznam, `.../2004/07/WS_UBY` for the members, `uStr` lower case | Same as 5.1.1 | Correct |
| Parser, element names | `DokumentPotvrzeni`, `DokumentChybyPotvrzeni`, `PseudoRazitko`/`PseudoRazirko`, matched by local name | Same | Correct |
| Parser, base64 | Stored raw, line breaks and all; not checked | base64 PDF, may be wrapped | Weak. Now normalised, checked as base64, must start with `%PDF`, 10 MB limit |
| Storage | `submission.receipt_pdf` TEXT holds base64; routes `b64decode` it | Fine | Correct, unchanged |
| Mock | Honoured `VracetPDF` anywhere; Chyby members out of order | Order matters | Wrong. Fixed |

## Files changed

- `App/app/ubyport/soap.py`: `VracetPDF` moved after `Ubytovani`; docstring cites the contract; adds `clean_pdf_base64` (normalise, validate, size limit) and `response_element_names`; parser reports `pdf_problems`.
- `App/app/ubyport/client.py`: logs one INFO line per ZapisUbytovane response (`ubyhost.ubyport`). It records element names, PDF sizes, problems and whether a stamp came back, never any values.
- `App/mock_ubyport/server.py`: reads `Seznam` members the way DataContractSerializer does (forward search, late elements skipped), so a misplaced `VracetPDF` gives no PDF. It returns the Chyby members in alphabetical order and sends a nil document when no PDF was asked for.
- `App/tests/test_soap.py`: the old test that required `VracetPDF` to be last is replaced by an ordinal-order test.
- `App/tests/test_ubyport_dorucenka.py`: new.

## Tests added

`tests/test_ubyport_dorucenka.py` (14 tests):
- Request: `VracetPDF` comes directly after `Ubytovani` and before `uCont`; the whole list is in ordinal order; namespaces are as documented; the value is `true`.
- Parser: with a fixture shaped like 5.1.1 plus a wrapped `DokumentPotvrzeni`, it extracts the PDF and stores it as canonical base64. The verbatim 5.1.1 response (no PDF) is handled. Invalid base64, non-PDF content, empty and oversized documents are dropped and the reason recorded.
- Logging: element names and size are logged; no surname, document number, stamp or PDF content appears in the log.
- Mock: a correctly ordered request returns a PDF and the result elements are sorted. The pre-WP30 order (`VracetPDF` last) returns a stamp but no PDF.
- Storage and download: running the real `submit_batch` against the documented response stores `receipt_pdf`, links `guest.receipt_submission_id`, and `/submissions/{id}/receipt.pdf` returns 200 `application/pdf` with the exact bytes. An accept without a PDF stores NULL, keeps the stamp, and the route returns 404.

## Test commands and results

All commands were run from `/tmp/wp/wp30/App` with `LD_LIBRARY_PATH=/tmp/libs/root/usr/lib/aarch64-linux-gnu /tmp/pr230/App/.venv/bin/python -m pytest -q`.
- Related: test_soap, test_ubyport_dorucenka, test_endtoend (real client against the mock, including the receipt download), duplicate_guard, report_detail_*, stale_submission, submission_mail, submission_retry_cap, ubyport_outcome_unknown, ubyport_sample_pdf, send_controls: 217 passed.
- Full suite in chunks: [a-c] 285 passed, 2 skipped; [d-f] 316 passed; [g-h] 373 passed; [i-o] 417 passed; [p-r] 276 passed; [s-t] 424 passed; [u-z] 101 passed. Total 2192 passed, 2 skipped, 0 failed.
- `ruff check app tests tools mock_ubyport --select E9,F63,F7,F82,F401,F841`: all checks passed.
- No templates or CSS were touched, so the browser and geometry tests were not rerun separately. They are part of the chunks.

## Deviations from the spec and why

- No "Fetch Doručenka again" action. The official method list has no read-only call that returns a PDF for a record that was already filed. The only way to get one is `ZapisUbytovane`, which files again, and that is forbidden.
- The new test file is named `test_ubyport_dorucenka.py`, and it deletes the rows it seeds. `test_endtoend.py` assumes an empty database, and a file sorting before it broke it.
- The stored `response_xml` still holds the PDF base64 (a second copy, purged after 90 days with the envelope). Left unchanged to keep this WP small.

## What Cursor must verify or adapt when applying on the real main

- The patch is against 709076a. Check that `build_zapis_ubytovane` still builds `Seznam` the same way and that nothing else asserts "VracetPDF last". `grep -rn VracetPDF`.
- What is verified and what is not:
  - Verified against the official document: element names, namespaces, the `DokumentPotvrzeni` base64 response field, the ordinal member order shown in 5.1.1, and the absence of any PDF-fetch method.
  - Not verified (the WSDL could not be fetched): the exact wire position of `VracetPDF`. It is inferred from standard DataContractSerializer rules plus the 5.1.1 example. It matches the live symptom (stamp returned, no PDF), and the 5.1.4 sample, which lists `VracetPDF` first in declaration order, suggests a plain member of the same class.
  - The one case where the inference would be wrong: if the service set an explicit `[DataMember(Order=...)]` on `VracetPDF`, it would belong last. The new order would then make WCF skip the header fields after it, including mandatory `uIdub` and `uMark`. That fails loudly with a header error, not silently, and nothing would be filed.

## Manual steps for the owner

1. Before production, file one test record against the test endpoint `https://ubyport.pcr.cz/ws_uby_test/ws_uby.svc`, or open `?singleWsdl` from a machine that can reach it. Check that the `SeznamUbytovanych` sequence lists `VracetPDF` right after `Ubytovani`.
2. On the next real filing, find the log line `ZapisUbytovane response: elements=...`. Expected: `ChybyHlavicky,ChybyZaznamu,DokumentChybyPotvrzeni,DokumentPotvrzeni,PseudoRazitko` and `receipt_pdf_bytes` > 0. If `DokumentPotvrzeni` is missing or nil, the order inference is wrong. Report it, with the element list.
3. Older submissions that have no PDF cannot be repaired from UbyPort through the web service. If written proof is needed, ask the police, or download it from the Ubyport web application if your account allows that.
