# 0459 report: tenancy audit of host-facing routes (read-only)

Branch: `task/0459-tenancy-audit` (base `main`). No file under `App/` was edited.
Scope: `App/app/routes/*.py` except `admin*.py` and `signup.py`. Grep: `WHERE id = ?`, `WHERE id=?`, `WHERE slug = ?`, `WHERE token = ?`.
Hits in scope: 30 (cleaning 1, exports 4, guest 8, guest_guide 3, invoices 2, mail_unsubscribe 1, passkeys 2, payments 3, property_page 2, stay_fees 4).
Classes: OK 30, ADMIN 0, LEAK 0, WRITE-LEAK 0.

Notes on the classes:
- "Host" rows are reached with a host session (`auth.require_login`). "Guest" rows are reached through `/l/{token}` with a PIN, claim session and `_owned_ids` cookie. "Public" rows need no login.
- A helper row names the route(s) that call it. The ownership check is the one the caller runs before the helper, or the one inside the helper.
- Admin files are out of scope, so ADMIN is 0 by construction.

## Table

| # | file:line | route | method | table | id source | ownership check | class | fix (leaks only) |
|---|---|---|---|---|---|---|---|---|
| 1 | cleaning.py:323 | /cleaning/shares/{share_id}/revoke | POST | cleaning_share | path share_id | `AND {db.null_safe_eq('owner_user_id')}` on the continuation line, `access.owner_id(request)` as 3rd param | OK | |
| 2 | exports.py:247 | /submissions/{submission_id}/receipt.pdf | GET | submission | path | `access.submission()` at 246 gates the query | OK | |
| 3 | exports.py:265 | /submissions/{submission_id}/errors.pdf | GET | submission | path | `access.submission()` at 264 | OK | |
| 4 | exports.py:291 | /submissions/{submission_id}/{which}.xml | GET | submission | path | `access.submission()` at 285, 404 if not owned | OK | |
| 5 | exports.py:371 | /settings/workspace-export | POST | user_account | session owner_id | `access.owner_id()` | OK | |
| 6 | guest.py:398 | helper `_live_apartment` (guest link routes `/l/{token}...`) | GET | apartment | row found by token or permalink, re-read by its id | lookup is by the guest link itself | OK | |
| 7 | guest.py:596 | helper `_reservation_for_guest` (`/l/{token}/{reservation_id}`) | GET | reservation | path reservation_id | `apartment_id = ?` in SQL (apartment from token) | OK | |
| 8 | guest.py:632 | helper `_claimable_reservation` (`/l/{token}/{reservation_id}/claim`) | GET/POST | reservation | path reservation_id | `apartment_id = ?` in SQL | OK | |
| 9 | guest.py:821 | helper `_entity_details` (guest page builder, `/l/{token}`) | GET | legal_entity | apartment.legal_entity_id (server row, not request input) | none needed | OK | |
| 10 | guest.py:1630 | /l/{token}/{reservation_id}/edit/{guest_id} | GET | guest | path guest_id | `_owned_ids` at 1627 (403), `reservation_id = ?` in SQL | OK | |
| 11 | guest.py:1688 | /l/{token}/{reservation_id}/save | POST | guest | form guest_id | `candidate in _owned_ids` at 1682 | OK | |
| 12 | guest.py:1916 | /l/{token}/{reservation_id}/save | POST | reservation | path reservation_id | reservation resolved and claim guard run earlier in the route | OK | |
| 13 | guest.py:1925 | /l/{token}/{reservation_id}/save | POST | reservation | path reservation_id | same as row 12 | OK | |
| 14 | guest_guide.py:139 | /apartments/{apartment_id}/leon | GET | user_account | apartment.leon_terms_accepted_by (owned row) | `_home()` at 131 (404 if not owned) | OK | |
| 15 | guest_guide.py:158 | /apartments/{apartment_id}/leon | POST | apartment | path apartment_id | `_home()` at 154 (404 if not owned) | OK | |
| 16 | guest_guide.py:171 | /apartments/{apartment_id}/leon | POST | apartment | path apartment_id | `_home()` at 154 | OK | |
| 17 | invoices.py:59 | helper `_load_invoice` (`/invoices/{id}`, `.pdf`, `paid`, `send`, `cancel`) | GET/POST | invoice | path invoice_id | `owner_user_id` null-safe equality in SQL | OK | |
| 18 | invoices.py:813 | /invoices (issue) | POST | invoice | return value of `invoices.issue(owner_id)` | created for this owner in the same request | OK | |
| 19 | mail_unsubscribe.py:50 | /mail/unsubscribe/{token} | GET | user_account | signed token payload `u` | token signature, existence test only, no row data returned | OK | (public, no host session) |
| 20 | passkeys.py:65 | helper `_owner` (`/account/passkeys*`) | any | user_account | session `current_user` id | own account, never previewed | OK | |
| 21 | passkeys.py:138 | /account/passkeys | POST | user_account | `account["id"]` from `_owner` | session account | OK | |
| 22 | payments.py:248 | /apartments/{apartment_id}/page | GET | apartment | path apartment_id | `owner_user_id = ?` in SQL | OK | |
| 23 | payments.py:278 | /apartments/{apartment_id}/page | POST | apartment | path apartment_id | `owner_user_id = ?` in SQL | OK | |
| 24 | payments.py:315 | /apartments/{apartment_id}/page/photo-delete | POST | apartment | path apartment_id | `owner_user_id = ?` in SQL | OK | |
| 25 | property_page.py:81 | helper `_page_context` (`/p/{slug}`) | GET | apartment | slug resolved to apartment id | public published page | OK | (public) |
| 26 | property_page.py:218 | /p/{slug}/request | POST | apartment | apartment_id from slug resolution (lines 204-206) | public slug, public fields only | OK | (public) |
| 27 | stay_fees.py:409 | helper `_operator_line` (/stay-fees/{apartment_id}) | GET | legal_entity | apartment.legal_entity_id (owned row) | `access.apartment()` on the caller | OK | |
| 28 | stay_fees.py:444 | helper `_filing_for_action` (`/stay-fees/{apartment_id}/filings/{filing_id}/sent`, `paid`) | POST | stay_fee_filing | path filing_id | `access.apartment()` at 440, `apartment_id = ?` in SQL | OK | |
| 29 | stay_fees.py:457 | helper `_guest_lines` (/stay-fees/{apartment_id}) | GET | guest | guest_id from the period lines built for this apartment | ids are server-derived; no request input | OK | |
| 30 | stay_fees.py:660 | /stay-fees/{apartment_id}/adjustment/{adjustment_id}/undo | POST | stay_fee_adjustment | path adjustment_id | `access.apartment()` at 654, `apartment_id = ?` in SQL | OK | |

## Counts

| class | count |
|---|---|
| OK | 30 |
| ADMIN | 0 |
| LEAK | 0 |
| WRITE-LEAK | 0 |
| total | 30 |

## Findings

- Row 1 (cleaning.py:323) was first reported as WRITE-LEAK. That was a false positive: the UPDATE continues on the next line with `AND {db.null_safe_eq('owner_user_id')}` and binds `access.owner_id(request)`. Reclassified as OK.
- No host-reachable read or write leaks were found in scope.

## Method note

Hits were `WHERE id = ?`, `WHERE slug = ?` and `WHERE token = ?` in host-facing routes. A second scan by the orchestrator for `WHERE <alias>.id = ?`, `WHERE id IN`, `public_id` and `key` found one more read, invoices.py:887, reached only from an already owner-scoped invoice: OK. Tenancy is centralised in `App/app/access.py` with `owner_user_id IS ?`. Legacy NULL-owner rows are claimed at first login (`App/app/auth.py:779-782`).

## Coverage gaps (not covered by this brief's grep)

- Queries shaped differently, such as `WHERE r.id = ?` or `WHERE id IN (...)`, and generic helpers that take a table name and id (for example `db.update("apartment", id, ...)`). One example already seen: `payments.py:105` (`WHERE r.id = ? AND a.owner_user_id = ?`) is scoped. The orchestrator should decide whether a second grep is needed.
- The brief's count of about 63 bare lookups includes admin and signup files, which are out of scope here.
- The audit is read-only. Fix briefs are not written here.
