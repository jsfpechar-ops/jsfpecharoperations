# TTLock Open Platform: facts UbyHost relies on

Checked: 2026-10-07 by the orchestrator. Re-check before changing `App/app/ttlock.py`.

Sources (the orchestrator sandbox cannot reach the TTLock doc hosts, so every fact comes from material the owner supplied):

- **[G]** Official `/v3/keyboardPwd/get` page, pasted by the owner (`euapi.ttlock.com`).
- **[CD]** Official `/v3/keyboardPwd/change` and `/v3/keyboardPwd/delete` pages, pasted by the owner (`euapi.ttlock.com`).
- **[X]** "TTLock / Sciener Open Platform API Documentation", a markdown export the owner uploaded. It uses the host `api.sciener.com` and looks like an older doc version (see the conflict under "Random passcode").
- **[EU]** Official pages pasted by the owner, 2026-10-07: Get access token, Refresh access token, User register, Get the lock list, Get lock details, Get all created passcodes of a lock, Get a passcode, Get the eKey list of an account, Send ekey, Get one ekey, Get ekeys of a lock, Key authorization, Get the eKey unlocking link (all on `euapi.ttlock.com`).
- **[FAQ]** Official FAQ, `https://euopen.ttlock.com/documentPages/htmlPages/example/FAQEn.html`, PDF supplied by the owner 2026-10-08. Cited as [FAQ x.y] by section and question.
- **[GW]** Official guide pages "Unlock via network (Gateway)" and "Lock Records Notify", pasted by the owner 2026-10-08.
- **[LT]** Official pages "Get lock time" and "Adjust lock time", pasted by the owner 2026-10-08.
- **[O]** Owner statement.

UbyHost uses the EU host `https://euapi.ttlock.com` for every call [G][CD].

## How the gateway fits

- UbyHost only ever talks to the TTLock cloud, and every call names the lock by `lockId`. No call takes a gateway id [EU].
- A TTLock Bluetooth lock cannot reach the internet itself. The gateway finds nearby locks of the **same administrator account** and pairs with them automatically. The server picks the gateway with the best signal for each remote operation. One gateway can serve any number of locks [GW].
- A random code from `get` does not travel through the gateway. The lock checks it by itself [EU].
- `add`, `change` and `delete` with type `2` go cloud, then gateway, then lock over Bluetooth [CD][GW].
- **Remote operations are slow.** The gateway may need several seconds to connect over Bluetooth. TTLock's own timeout for a remote operation is **30 seconds**; a client that gives up sooner may never see the answer [GW]. UbyHost uses 35 s for these calls and 5 s for cloud-only calls.
- **One remote operation per lock at a time.** A second request while the first is running "is destined to fail" [GW]. UbyHost sends gateway calls only from the worker, one at a time.
- A weak signal, or someone touching the keypad during the operation, makes it fail [GW]. UbyHost retries.
- Through the gateway, the cloud can also unlock and lock, read the lock state and battery, and **query and calibrate the lock time** [GW]. UbyHost uses none of these now; remote time calibration is a possible later fix for clock drift.
- Not yet proven on a real lock: that a remote delete of a never-used random code stops the lock accepting it (see "What the FAQ adds"). Owner test A settles it.

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
| `10004` | Token unauthorized, expired or revoked. For an authorized admin it can also mean the top admin revoked the rights [FAQ 2.9] | Refresh once, retry once. A second `10004` means access was revoked: pause door codes for that account, host mail |
| `10011` | Refresh token invalid | Account to `reauth_needed`, host mail, no retry |
| `10007` | Username or password wrong | Show on the connect form, no retry |
| `10000`, `10001` | Client id or secret wrong | Owner alert (server config), stop all calls |
| `10005`, `30001`, `-2018`, `20002` | No permission, or not the lock admin | Host mail ("UbyHost has no admin rights on this lock"), no retry |
| `30006` | API call frequency exceeded | Back off, owner alert |
| `80000` | `date` off by more than 5 minutes | Owner alert (server clock), retry later |
| `-2012` | Lock not connected to any gateway | Retry with backoff. For a delete, host mail after 1 h |
| `-3037` | Gateway busy, or offline and not yet noticed by the server [FAQ 5.4] | Retry with backoff |
| `-4056` | Lock storage full | Host mail |
| `90000`, `1` | TTLock internal error, generic failure | Retry with backoff |
| `-3` | Invalid parameter | Log, no retry (a UbyHost bug) |

Source for every code: [X], table "System Error Codes", plus [FAQ] where marked. The reactions are UbyHost design, not TTLock text.

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

## What the FAQ adds about codes

- **A random code is unknown to the lock until its first use.** Deleting a never-used random code over Bluetooth answers "data does not exist", because "the random password must be used once on the lock to be recorded" [FAQ 4.1]. So a remote delete of an unused random code may not stop the lock accepting it later. Owner test A settles this (plan §12).
- **One random timed code per time range.** For type 3, "only one password can be generated within the same time range", and an expired timed code and a new one cannot share a range [FAQ 4.4, 4.5]. Codes on different days must differ by at least one hour at the start or the end. A stay cancelled and rebooked for the same dates and hours therefore cannot get a fresh random code without shifting the window.
- Rounding: a same-day range rounds to half hours, a multi-day range to whole hours, a range over a year to months [FAQ 4.4].
- **Custom codes** (`add`) are timed or permanent, accurate to the minute, have **no 24 h first-use rule**, and have no limit per time range [FAQ 4.4]. They stay on the lock after they expire until deleted. When the lock's memory is full, the oldest code is pushed out [FAQ 4.6]. Adding a code that already exists on the lock fails with "same password already exists" [FAQ 4.7]. With `addType=2` the lock must be online (gateway or Wi-Fi) [FAQ 4.8].
- **Lock clock.** A wrong lock time makes codes invalid. Fix: TTLock app, lock, Settings, Lock Time, calibrate [FAQ 4.2, 4.8]. Unlocking with the app over Bluetooth also calibrates it [FAQ 1.10].
- Gateway status: the server notices an offline gateway after about 10 minutes, and the app notifies the admin after 30 minutes offline [FAQ 5.8, 5.11].
- Authorized admins have every right except deleting the lock, re-authorizing, and changing the admin's own unlock code [FAQ 1.9].
- The monthly call limit is per application [FAQ 2.7].

## Lock clock

- The lock checks every code against its own clock. A wrong clock can make a valid code fail [LT][FAQ 4.2].
- `/v3/lock/queryDate` (`lockId`) returns the lock's time as `date` in ms. `/v3/lock/updateDate` (`lockId`, `date`) sets it and returns the new time. Both need a gateway or a Wi-Fi lock [LT], so they count as gateway calls (35 s, worker only).
- Not in the allowlist yet. Proposed: one `queryDate` per lock per week, and `updateDate` only when the drift is over 2 minutes.

## Delete and change

- `POST /v3/keyboardPwd/delete` with `lockId`, `keyboardPwdId`, `deleteType=2` deletes a random or custom code remotely on a Wi-Fi lock or a lock with a gateway [CD][X]. Requires a V4 passcode lock [X].
- `POST /v3/keyboardPwd/change` with `lockId`, `keyboardPwdId`, `changeType=2` changes the name, the period (`startDate` and `endDate` together) or the code (`newKeyboardPwd`) remotely [CD][X]. Requires a V4 passcode lock [X].

## Admin sharing

- A second TTLock account that received a lock as **authorized admin** can create passcodes on it [O, tested in the TTLock app 2026-10-07]. UbyHost uses one dedicated TTLock account for the pilot, with the rental locks shared to it [O].

## Custom passcode (add), not used

- `POST /v3/keyboardPwd/add` with `keyboardPwd`, `startDate`, `endDate`, `addType=2` (gateway) returns `keyboardPwdId`. V4 passcode locks only [X]. UbyHost uses `get` instead [O].

## Unlock records, not used

- `POST /v3/lockRecord/list` with `lockId`, optional `startDate` and `endDate`, `pageNo`, `pageSize` (max 100) returns records with `recordType` (4 = passcode unlock), `success`, `keyboardPwd`, `lockDate`, `serverDate` [X]. The developer console has a per-app **Callback URL** that pushes unlock records to a URL [O, console screenshot 2026-10-08]. UbyHost leaves it empty: unlock times say when guests come and go, and no feature needs them. The callback receives each record with `username` (the code's name or the app user), `keyboardPwd` (the digits) and `lockDate` [GW], so it would hold guests' comings and goings plus codes. It only works for locks whose administrator got a token with UbyHost's client id [GW].

## Not stated in the supplied docs

1. Whether the TTLock app's share screen accepts a prefixed API user (the API's Send ekey does).
2. Whether an authorization-code (redirect) login exists. [X] lists the errors `10002`, `10008` and `10009`, which hints at one, but documents no endpoint. Not needed with the UbyHost-made user (plan §8.2).
3. Whether `change` can move the period of a random (`get`) code.
4. Whether the lock applies daylight saving time on its own, or only the raw offset.
5. Who runs `euapi.ttlock.com`, where its data is stored, and the privacy policy URL.
