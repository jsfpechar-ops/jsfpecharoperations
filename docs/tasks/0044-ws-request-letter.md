# 0044: "I don't have web-service credentials yet" letter

Status: done; superseded by [0097](0097-reporting-help.md) (generator removed, one line links the Foreign Police page)
Depends on: 0043 merged | Branch: task/0044-ws-request-letter
Executor: Cursor local agent | Fits one session

## 1. Objective
In the property's Police reporting section, a host without UbyPort web-service credentials gets a ready request text with their IDUB filled in, which they copy into their data box or download. This removes the step where most hosts get stuck.

## 2. Context
- `App/app/templates/apartment_form.html`, `<details ... id="ubyport">`: it already links the sample protocol PDF (`/static/docs/ubyport-ws-credential-sample.pdf`) and uses `copy_inline` from `_components.html`.
- Copy rule 9: one explanation in one place; no sentence that the button already says.
- Recipient and channel come from the owner (§8.1). Do not invent an address.

## 3. Files
| Path | Action | What |
|---|---|---|
| App/app/templates/apartment_form.html | edit | add a `<details>` "I don't have web-service credentials yet" under the WS login row |
| App/app/routes/admin.py | edit | GET `/apartments/{id}/ws-request.txt` → text/plain attachment |
| App/app/host_i18n.py | edit | EN + CS keys: summary, 2-line intro, subject, body template |
| App/tests/test_ws_request_letter.py | new | tests |

## 4. Steps
1. Body template (CS for the letter itself, because it goes to the Czech Police; EN UI explains it):
   "Dobrý den, pro ubytovací zařízení s IDUB {idub} žádám o vytvoření účtu pro robotické zasílání dat (webové služby UbyPort) pro aplikaci UbyHost. Děkuji. {operator_name}"
   ("Hello, for the accommodation facility with IDUB {idub} I request an account for robotic data submission (UbyPort web services) for the UbyHost application. Thank you. {operator_name}") Use `[doplňte IDUB]` ("[fill in IDUB]") when the IDUB is empty. `operator_name` = the assigned entity name, else `[jméno provozovatele]` ("[operator name]").
2. In the details block: recipient line and subject from §8.1, the body in a read-only textarea with `copy_inline`, and a "Download .txt" link to the new route. It works without JavaScript (the textarea is selectable).
3. Route: owner-scoped like the other `/apartments/{id}` routes (reuse the same access check), `Content-Disposition: attachment; filename=ubyport-ws-zadost.txt`. No logging of the body.
4. Tests: body contains the IDUB when set and the placeholder when empty; another owner gets 404; the page renders the block closed when `uby_ws_user` is set and open when it is empty.

## 5. Do not touch
Submission code, migrations, guest pages, CSS tokens.

## 6. Commands
From App/: `.venv/bin/python -m pytest tests -q`. Root: `python3 scripts/context_lint.py`. Browser and geometry tests 0 skipped.

## 7. Acceptance
- [ ] Screenshots at 360, 390 and 1280 px with the block open.
- [ ] The downloaded file opens as UTF-8 with Czech diacritics intact.

## 8. Stop and ask
1. OWNER: give the recipient (data-box ID of the Foreign Police directorate) and the subject line exactly as the Police publish them. Until then render "Příjemce: Ředitelství služby cizinecké policie" ("Recipient: Foreign Police Directorate") without an ID.
2. The access-check helper for `/apartments/{id}` routes can't be reused as-is.

## 9. Report
Files changed, test tail, screenshots.
