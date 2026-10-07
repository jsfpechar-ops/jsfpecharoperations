# TTLock Open Platform: facts UbyHost relies on

Checked: 2026-10-07 by the orchestrator. Re-check before changing `App/app/ttlock.py`.

Sources (the orchestrator sandbox cannot reach the TTLock doc hosts, so every fact comes from material the owner supplied):

- **[G]** Official `/v3/keyboardPwd/get` page, pasted by the owner (`euapi.ttlock.com`).
- **[CD]** Official `/v3/keyboardPwd/change` and `/v3/keyboardPwd/delete` pages, pasted by the owner (`euapi.ttlock.com`).
- **[X]** "TTLock / Sciener Open Platform API Documentation", a markdown export the owner uploaded. It uses the host `api.sciener.com` and looks like an older doc version (see the conflict under "Random passcode").
- **[O]** Owner statement.

UbyHost uses the EU host `https://euapi.ttlock.com` for every call [G][CD].

## Request basics

- Every call is a form-encoded `POST` (`application/x-www-form-urlencoded`) and returns JSON [X][G].
- Every API call carries `clientId` and `accessToken`, plus `date`, the current time in ms [X].
- `date` must be within ±5 minutes of TTLock's server time, or the call fails with `80000` [X]. The server clock must be NTP-synced.
- Success on write calls is `{"errcode": 0, ...}`. Calls that return data (`get`, `add`) return the data with no `errcode` [X][G][CD].

## Auth and tokens

- `POST /oauth2/token` with `client_id`, `client_secret`, `username`, `password` (MD5, 32 lowercase hex characters) [X].
- `username` is a TTLock app account, or a user created with the User Register API. The developer account must not be used [X].
- Response: `access_token`, `uid`, `expires_in` (default 7,776,000 s = 90 days), `scope` (for example `user,key,room`), `refresh_token` [X].
- Refresh: the same URL with `client_id`, `client_secret`, `grant_type=refresh_token`, `refresh_token`. The response carries a new `access_token`, `expires_in`, `scope` and a `refresh_token` [X]. Whether the old refresh token stops working is not stated, so UbyHost always stores the returned pair.
- `POST /v3/user/register` with `clientId`, `clientSecret`, `username` (letters and digits only, `30002`), MD5 `password`, `date` creates a user that belongs to the developer app. The returned `username` is what the token call uses [X].
- `POST /v3/user/delete` removes such a user [X].
- The monthly quota is 30,000 calls per developer app, shared by every UbyHost host [O]. Paid tiers (screenshot of the developer console, owner, 2026-10-07): 500,000 for US$88/year, 2,000,000 for US$188/year, and up to 80,000,000 for US$988/year. UbyHost stays on the free tier [O].
- No other rate limit is shown in the console [O]. `30006` still exists for a frequency limit [X].

## Error codes

| Code | Meaning | UbyHost reaction |
|---|---|---|
| `10003` | Token does not exist | Refresh once, retry once |
| `10004` | Token unauthorized, expired or revoked | Refresh once, retry once |
| `10011` | Refresh token invalid | Account to `reauth_needed`, host mail, no retry |
| `10007` | Username or password wrong | Show on the connect form, no retry |
| `10000`, `10001` | Client id or secret wrong | Owner alert (server config), stop all calls |
| `10005`, `30001`, `-2018`, `20002` | No permission, or not the lock admin | Host mail ("UbyHost has no admin rights on this lock"), no retry |
| `30006` | API call frequency exceeded | Back off, owner alert |
| `80000` | `date` off by more than 5 minutes | Owner alert (server clock), retry later |
| `-2012` | Lock not connected to any gateway | Retry with backoff. For a delete, host mail after 1 h |
| `-4056` | Lock storage full | Host mail |
| `90000`, `1` | TTLock internal error, generic failure | Retry with backoff |
| `-3` | Invalid parameter | Log, no retry (a UbyHost bug) |

Source for every code: [X], table "System Error Codes". The reactions are UbyHost design, not TTLock text.

## Random passcode (get)

- `POST /v3/keyboardPwd/get` with `clientId`, `accessToken`, `lockId`, `keyboardPwdType`, optional `keyboardPwdName`, `startDate`, `endDate`, `date` [G].
- Type `3` (period) must be used at least once within 24 h after the start time, or it is invalidated [G][X].
- The code is made by a cloud algorithm. No gateway is needed. It cannot be customised. Length is 6 to 9 digits and depends on the period [G].
- Validity is accurate to the hour. 19:20 becomes 19:00. Send whole hours [G]. Over one year, the period must be whole months [G][X].
- Response `{"keyboardPwd": "0563456", "keyboardPwdId": 10236}`. The code is a string and can start with 0 [G]. [X] shows `keyboardPwdId` as a string in its example, so parse it with `int()`.
- **Conflict:** [X] lists `keyboardPwdVersion` (4 on current locks) as required. The official EU page [G] does not list it. UbyHost sends `keyboardPwdVersion=4` only if a pilot call fails with `-3` or `20007` without it.

## Delete and change

- `POST /v3/keyboardPwd/delete` with `lockId`, `keyboardPwdId`, `deleteType=2` deletes a random or custom code remotely on a Wi-Fi lock or a lock with a gateway [CD][X]. Requires a V4 passcode lock [X].
- `POST /v3/keyboardPwd/change` with `lockId`, `keyboardPwdId`, `changeType=2` changes the name, the period (`startDate` and `endDate` together) or the code (`newKeyboardPwd`) remotely [CD][X]. Requires a V4 passcode lock [X].

## Admin sharing

- A second TTLock account that received a lock as **authorized admin** can create passcodes on it [O, tested in the TTLock app 2026-10-07]. UbyHost uses one dedicated TTLock account for the pilot, with the rental locks shared to it [O].

## Custom passcode (add), not used

- `POST /v3/keyboardPwd/add` with `keyboardPwd`, `startDate`, `endDate`, `addType=2` (gateway) returns `keyboardPwdId`. V4 passcode locks only [X]. UbyHost uses `get` instead [O].

## Unlock records, not used

- `POST /v3/lockRecord/list` with `lockId`, optional `startDate` and `endDate`, `pageNo`, `pageSize` (max 100) returns records with `recordType` (4 = passcode unlock), `success`, `keyboardPwd`, `lockDate`, `serverDate` [X]. No callback is documented [X].

## Not stated in the supplied docs

1. The lock list endpoint (`/v3/lock/list`) and its fields (lock id, name, gateway flag). Needed for the property lock picker.
2. A passcode list endpoint for one lock. Needed so a retry after a timeout can find a code it already made.
3. Whether an authorization-code (redirect) login exists. [X] lists the errors `10002` (invalid code), `10008` (invalid redirect_uri) and `10009` (unsupported response_type), which hints at one, but documents no endpoint.
4. Whether `change` can move the period of a random (`get`) code.
5. Who runs `euapi.ttlock.com`, where its data is stored, and the privacy policy URL.
