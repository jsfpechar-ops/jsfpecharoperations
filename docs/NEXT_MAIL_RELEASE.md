# Next mail production release (full backlog)

This is the product release plan for turning guest e-mail back on and shipping the related UX. Cursor also keeps a copy under Plans as `mail_go_live_next_release_422b841b`.

**Implementation is consolidated in [#88](https://github.com/jsfpechar-ops/jsfpecharoperations/pull/88). Do not merge or enable SES until the owner explicitly asks.** The former passport draft [#87](https://github.com/jsfpechar-ops/jsfpecharoperations/pull/87) has been folded into #88.

**Related:** [DESIGN.md](DESIGN.md) (Arrival-lane picker, assigned screen, PM contact footer).

## Status snapshot

| Item | Status |
|------|--------|
| SES `_send_ses` + boto3 on production | Done (`#86`); mail still **disabled** |
| Domain DKIM / MAIL FROM / DMARC | Done (ops); Essentials; no dedicated IP |
| Claim-mail abuse caps | Implemented in #88 |
| Arrival-lane picker | Implemented in #88; always shown, including one stay |
| SES flip to `ses` | Waiting on AWS production access |
| Assigned UX, PM/controller split, passport toggle | Implemented and tested in #88 |
| Full regression suite | 379 passed (includes `#89` late-registration tests) |

```mermaid
flowchart TD
  pin[PIN] --> pick[Stay picker always]
  pick --> claimOrForm[Claim email if mail on else form]
  claimOrForm --> assigned[Assigned screen if claimed]
  claimOrForm --> form[Guest form]
  form --> done[Stay hub]
```

---

## Already done

- SES sender + `boto3` on production (`#86` / `1e7edf3`); Lightsail healthy
- Production **`UBYHOST_MAIL_BACKEND=disabled`** (PIN → dates → form)
- Domain DNS: DKIM + MAIL FROM `mail.ubyhost.com` + DMARC `p=none`
- IAM keys may be staged in Lightsail `.env` while mail stays disabled
- `noreply@ubyhost.com` = From only (no mailbox required); Reply-To = legal entity

---

## Owner ops (block SES flip)

1. AWS production-access approval (Support reply with transactional use case if needed)
2. Confirm DKIM / MAIL FROM Verified; IAM can send
3. Only then: set `UBYHOST_MAIL_BACKEND=ses`, redeploy, smoke one claim email
4. Rollback: set `disabled` + redeploy

---

## Included in #88

### 1. Claim-mail abuse caps (before or with SES flip)

Implemented on `cursor/claim-mail-abuse-caps-3387` / [#88](https://github.com/jsfpechar-ops/jsfpecharoperations/pull/88):

- No re-send for same provisional email unless explicit Resend + **5 min** cooldown
- Per recipient **2/hour**, per reservation **3/hour**, IP+token **3/15 min**
- Production Turnstile on claim/resend (`guest_claim`)
- EN/CS errors: cooldown, recipient_rate, bot

### 2. Restore mail-backed guest features (when `ses` on)

Flipping SES turns these back on via `mail.mail_enabled()`:

- Email claim + magic-link confirm
- Masked email on assigned; none when locked
- Day-before guest reminder; host incomplete warnings
- Completion receipt + host CC; Reply-To = PM entity
- GDPR/cookie copy for claim email
- Contact split; custom host message; completion-based reporting
- Incomplete claimed forms stay open after check-in until the guest finishes or the host locks them (`#89`); stay-specific links recover past incomplete stays

**Stay off unless toggled:** passport (see §5).

### 3. Always show stay picker

The `len(reservations) == 1` redirect is removed. The picker renders after PIN when ≥1 stay. Empty stay → `/new` only **after** the guest taps a stay.

### 4. Stay picker redesign — “Arrival lane”

Implemented from [DESIGN.md](DESIGN.md). Summary:

1. Welcome + one legal sentence; **facility name** as hero signal
2. Soft welcome/accommodation band (not a card stack)
3. Chronological **arrival lane** rows: check-in→check-out range cue, nights, Ongoing badge, CTA **That’s my stay** / **To je můj pobyt**
4. PM footer: can’t find stay → contact host (legal-entity phone/email)

Motion: staggered entrance, range accent on focus, soft press. Not an Airbo clone.

### 5. Optional passport toggle (default Off)

Folded from [#87](https://github.com/jsfpechar-ops/jsfpecharoperations/pull/87): Off | Required for foreign guests. Default remains **Off**.

### 6. Assigned / already-claimed screen

- Property + location + dates summary
- Masked email + private-link guidance (optional last-sent date)
- **Send me the link again** (caps + Turnstile)
- Back / not my reservation
- Footer: **If there is any problem, feel free to contact your host** → **PM / legal-entity** phone + email (never `support@`)

### 7. PM = controller + PoC

- Default-ticked: “Property manager’s company is data controller (and guest PoC)”
- Unticked: select the alternate controller legal entity; the PM remains the guest stay contact
- UbyPort IČO may diverge from GDPR controller → counsel note

### 8. Docs / i18n

DESIGN picker + assigned notes and EN/CS strings are implemented. Staging stays `console`.

---

## Explicit non-goals this release

- Dedicated SES IPs / Pro plan / Auto Validation / SES tenants
- Cloning Airbo branding or pink-purple CTAs
- Dark mode
- Enabling SES before AWS production access and an owner-approved deployment

---

## Remaining release steps

1. Review and merge #88 when the owner asks; deploy with production mail still `disabled`
2. Receive AWS SES production access and credentials
3. Set `.env` to `UBYHOST_MAIL_BACKEND=ses`, redeploy, then smoke claim/resend/reminder/completion mail
4. Roll back to `disabled` immediately if delivery or configuration is unhealthy
