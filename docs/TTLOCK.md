# TTLock Open Platform: facts UbyHost relies on

Checked: 2026-10-07 by the orchestrator. Re-check before changing `App/app/ttlock.py`.

Sources (the orchestrator sandbox cannot reach the TTLock doc hosts, so every fact comes from material the owner supplied):

- **[G]** Official `/v3/keyboardPwd/get` page, pasted by the owner (`euapi.ttlock.com`).
- **[CD]** Official `/v3/keyboardPwd/change` and `/v3/keyboardPwd/delete` pages, pasted by the owner (`euapi.ttlock.com`).
- **[X]** "TTLock / Sciener Open Platform API Documentation", a markdown export the owner uploaded. It uses the host `api.sciener.com` and looks like an older doc version (see the conflict under "Random passcode").
- **[EU]** Official pages pasted by the owner, 2026-10-07: Get access token, Refresh access token, User register, Get the lock list, Get lock details, Get all created passcodes of a lock, Get a passcode, Get the eKey list of an account, Send ekey, Get one ekey, Get ekeys of a lock, Key authorization, Get the eKey unlocking link (all on `euapi.ttlock.com`).
- **[O]** Owner statement.

UbyHost uses the EU host `https://euapi.ttlock.com` for every call [G][CD].

## Request basics

- Every call is a form-encoded `POST` (`application/x-www-form-urlencoded`) and returns JSON [X][G].
- Every API call carries `clientId` and `accessToken`, plus `date`, the current time in ms [X].
- `date` must be within ±5 minutes of TTLock's server time, or the call fails with `80000` [X]. The server clock must be NTP-synced.
- Success on write calls is `{"errcode": 0, ...}`. Calls that return data (`get`, `add`) return the data with no `errcode` [X][G][CD].

## Auth and tokens

- `POST /oauth2/token` with `clientId`, `clientSecret`, `username`, `password` (MD5, 32 lowercase hex characters) [EU]. The EU page uses camelCase names. [X] uses `client_id` and `client_secret`. UbyHost uses the EU names.
- `username` is a TTLock app account, or the prefixed username returned by the User Register API. The developer account must not be used [EU].
- Response: `access_token`, `uid`, `expires_in` (default 7,776,000 s = 90 days), `refresh_token` [EU].
- An expired access token gives `10004` [EU].
- Refresh: the same URL with `clientId`, `clientSecret`, `grant_type=refresh_token`, `refresh_token`. The response carries `access_token`, `expires_in`, `refresh_token` [EU]. A refresh token is valid for 10 years from its creation [EU]. UbyHost always stores the returned pair.
- `POST /v3/user/register` with `clientId`, `clientSecret`, `username` (letters and digits only, for example a random hex string), MD5 `password`, `date`. Returns a prefixed `username` such as `abcd_c042f4db...`. The prefix is fixed per developer app and only namespaces its users. The token call then uses the prefixed name [EU]. The platform's intended use: the app keeps the mapping to its own users and TTLock never learns who they are [EU]. UbyHost therefore registers a random string, never the host's e-mail.
- An eKey can be sent to "an account registered in TTLock APP or user registered by cloud API: User register" [EU, Send ekey]. So a prefixed API user can receive a shared lock. The owner's own test used a normal app account [O]; sharing to a prefixed user from the app screen is still to be tried once.
- Send ekey's `createUser=1` makes an account whose password is the last 6 characters of the username [EU]. UbyHost never uses it.
- `POST /v3/user/delete` removes such a user [X].
- The monthly quota is 30,000 calls per developer app, shared by every UbyHost host [O]. Paid tiers (screenshot of the developer console, owner, 2026-10-07): 500,000 for US$88/year, 2,000,000 for US$188/year, and up to 80,000,000 for US$988/year. UbyHost stays on the free tier [O].
- No other rate limit is shown in the console [O]. `30006` still exists for a frequency limit [X].

## Secrets in TTLock responses (never store, never log)

- `/v3/lock/detail` returns `noKeyPwd`, the lock's **super passcode**, which opens the door at any time [EU]. UbyHost never calls this endpoint.
- `/v3/lock/list`, `/v3/key/list` and `/v3/key/get` return `lockData`, "used to operate the lock" [EU]. `/v3/key/list` and `/v3/key/get` also return `noKeyPwd` (the super passcode), and the doc example shows it even on a common, authorized eKey [EU]. UbyHost keeps only the fields it needs while parsing and never logs a raw response.
- `/v3/key/getUnlockLink` makes a link that opens the door remotely, if the eKey has remote unlock enabled [EU]. UbyHost never calls it.
- `/v3/lock/listKeyboardPwd` returns every code's digits (`keyboardPwd`) [EU]. UbyHost reads only `keyboardPwdId`, `keyboardPwdName`, `startDate` and `endDate` from it.

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

- `POST /v3/keyboardPwd/get` with `clientId`, `accessToken`, `lockId`, `keyboardPwdType`, optional `keyboardPwdName`, `startDate` (required), optional `endDate`, `date` [EU].
- No `keyboardPwdVersion` on the EU page [EU]. [X] lists it as required, but [X] is the older doc. UbyHost does not send it.
- Type `3` (period) must be used at least once within 24 h after the start time, or it is invalidated [EU].
- The code is made by a cloud algorithm. No gateway is needed. It cannot be customised. Length is 6 to 9 digits and depends on the period [EU].
- Validity is accurate to the hour. 19:20 becomes 19:00. Send whole hours. Over one year, the period must be whole months [EU].
- Response `{"keyboardPwd": "0563456", "keyboardPwdId": 10236}`. The code is a string and can start with 0 [EU].

## Finding locks and codes

- `/v3/key/list` (form POST) with `pageNo`, `pageSize` (max 1000), optional `lockAlias`, `groupId` lists every eKey the caller holds, including locks others shared with it [EU]. This is the lock picker's source for the UbyHost user.
- `/v3/key/list` item fields UbyHost reads: `lockId`, `lockAlias` (the name the host sees), `keyRight` (1 = authorized admin, so it may create codes), `keyStatus` (`110401` = normal; `110405` frozen, `110408` deleted, `110410` reset), `startDate`, `endDate` (the eKey's own validity), `remoteEnable` (1 yes, 2 no), `electricQuantity` (battery), `timezoneRawOffset` [EU]. It does **not** carry `hasGateway` [EU].
- A lock is offered in the picker only if `keyRight = 1` and `keyStatus = 110401`. If a later refresh shows another status or the lock is gone, door codes for that property pause and the host gets a mail.
- `timezoneRawOffset` should be 3,600,000 (Prague without daylight saving). Any other value shows a warning next to the lock in the picker, at no extra call.
- `/v3/lock/list` returns only locks where the caller is the **top administrator** [EU], so UbyHost does not use it.
- `/v3/lock/list` fields, for reference: `lockId`, `lockName`, `lockAlias`, `lockMac`, `electricQuantity`, `featureValue`, `hasGateway`, `lockData`, `groupId`, `groupName`, `date` [EU].
- `/v3/lock/listKeyboardPwd` with `lockId`, `pageNo`, `pageSize` (max 200), `orderBy` (required: 0 by name, 1 newest first, 2 by name reversed), optional `searchStr` (fuzzy match on the code name, or exact match on the code) [EU]. A retry after a timeout searches `searchStr=UH-<door_code.id>` and adopts the match.
- Item fields: `keyboardPwdId`, `lockId`, `keyboardPwd`, `keyboardPwdName`, `keyboardPwdType`, `startDate`, `endDate`, `sendDate`, `isCustom`, `senderUsername` [EU].
- `timezoneRawOffset` is the lock's offset from UTC in ms [EU]. The `/v3/lock/detail` example shows UTC+8, a common factory default. A lock set to the wrong time zone would shift every code window. The pilot still tests a code at the exact start hour.

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

1. Whether the TTLock app's share screen accepts a prefixed API user (the API's Send ekey does).
2. Whether an authorization-code (redirect) login exists. [X] lists the errors `10002`, `10008` and `10009`, which hints at one, but documents no endpoint. Not needed with the UbyHost-made user (plan §8.2).
3. Whether `change` can move the period of a random (`get`) code.
4. Whether the lock applies daylight saving time on its own, or only the raw offset.
5. Who runs `euapi.ttlock.com`, where its data is stored, and the privacy policy URL.
