# Poplatek z pobytu — notes for a future big update

Planning notes only. **Not implemented.** UbyHost today deliberately does not
calculate or remit municipal stay fees
(`App/README.md` → “What it deliberately does not do”).

Correct legal name (since 2020): **poplatek z pobytu** (local fee on short stays),
under zákon č. 565/1990 Sb. Older marketing/UI sometimes still says
“poplatek z ubytování” / Airbo’s **Poplatky** — treat those as the same product
area when talking to hosts.

---

## What Airbo shows (inspiration, not a copy brief)

On the property edit screen Airbo folds this into **one tab**:

> **Ubytovací kniha a hlášení poplatků**

On the apartments list they also expose a row action **Poplatky**.

Takeaways for UbyHost later:

- Hosts expect **fees next to the house book**, not a random Settings dump.
- Keep **our left sidebar** (Overview / Stays / Properties / …). Do not switch to
  Airbo’s top nav. A future Fees area can be:
  - a sidebar item, and/or
  - a section on the property page, and/or
  - a stay-level panel — but not a replacement chrome.
- One clear primary workflow beats scattering “fee bits” across calendar sync,
  UbyPort, and house book.

---

## Legal / product frame (for counsel to confirm)

Rough technical reading of the statute — **lawyer must approve** before UI copy
or automation ships:

| Topic | Working understanding |
|-------|------------------------|
| Who introduces it | The **municipality** via obecně závazná vyhláška (not every obec has it). |
| Who pays | Guest (**poplatník**) who is **not** registered as resident in that obec. |
| Who collects & remits | Host / provider (**plátce**) collects and remits to the obec. |
| Scope | Paid stay ≤ **60** consecutive calendar days with one provider. |
| Base | Started days of stay **except arrival day**. |
| Rate | Cap in law (currently up to **50 Kč**/day); actual rate is in the obec vyhláška. |
| Exemptions | Under-18, ZTP/P + guide, hospitalised, seasonal workers, etc. — list in statute. |
| Extra duty | Plátce must keep an **evidenční kniha** for each facility/place of paid stay. |
| Remittance | Period and due date come from the obec vyhláška (often monthly). |

This is **orthogonal to UbyPort / cizinecká policie**. A Czech guest may be
out of Police reporting but still fee-liable; a foreign guest may need both.

Compliance audit already flags that our single “domovní kniha” language may need
to separate Police house-book duties from any municipal fee register
(`docs/archive/TECHNICAL_COMPLIANCE_AUDIT.md`).

---

## What UbyHost already has that a Fees module can reuse

| Existing | Useful for fees because… |
|----------|---------------------------|
| Stays (`reservation` dates) | Night/day counts, arrival/departure |
| Guests (age, nationality, stay dates) | Exemptions, who was present which nights |
| Property + legal entity | Plátce identity, address / obec |
| House book export | Overlaps with evidenční kniha fields — do **not** assume they are identical |
| Sidebar IA | Natural home for a future **Poplatky** nav item without Airbo top-bar |

Gaps today (expected):

- No obec, vyhláška rate, bank account for remittance, or fee period settings
- No “liable / exempt / collected / remitted” state on a guest-night
- No monthly remittance draft or PDF for the obec
- No guest-facing “local fee” explanation on the registration form

---

## Suggested shape of the big update (when we build it)

Phase loosely; order can change after lawyer + owner priority:

1. **Property settings**
   - Obec / whether poplatek applies
   - Rate Kč/day from vyhláška
   - Remittance cadence + payment details
   - Optional link/text to the obec vyhláška

2. **Stay / guest calculation**
   - Auto-suggest nights = stay length − arrival day (statute base)
   - Mark exemptions (age &lt; 18 first; other exemptions host-confirmed)
   - Amount due per person / per stay; host can override with reason

3. **Evidence & remittance**
   - Period summary (e.g. calendar month): guests, nights, Kč, exemptions
   - Export (CSV/PDF) suitable for obec filing / accounting
   - Track “collected from guest” vs “remitted to obec”

4. **Guest UX (optional later)**
   - Short note on the form that a municipal fee may apply (host-configured)
   - Do not mix into Police/UbyPort copy

5. **IA (keep sidebar)**
   - Prefer: sidebar **Poplatky** (period overview) + property subsection for rates
   - Avoid: only burying fees inside apartment edit with no list/overview
   - Avoid: merging Fees into UbyPort “Automation” — different authority

---

## Explicit non-goals for v1 of that update

- Filing electronically into every obec portal (formats differ; start export + checklist)
- Replacing accounting software
- Guaranteeing the host’s legal compliance (same stance as UbyPort: tool assists)
- Renaming or dropping the Police house book to “look like Airbo’s combined tab”

---

## Open questions for the owner / lawyer before coding

1. Official product name in UI: **Poplatek z pobytu** vs host-familiar **Poplatky**?
2. Is the evidenční kniha for fees the same artefact as our house book, or a
   separate export with different columns?
3. First market: Praha only, or multi-obec rates from day one?
4. Should guests see the fee amount before submit, or is host-only enough for v1?
5. Retention: fee ledgers vs six-year house-book retention — same or shorter?

---

## Pointers in this repo

- Out of scope today: `App/README.md` (“Accommodation fees…”)
- House book implementation: `App/app/housebook.py`, `/housebook`
- Legal caution on registers: `docs/archive/TECHNICAL_COMPLIANCE_AUDIT.md` (domovní kniha row)
- UI policy (sidebar, light-only): `docs/DESIGN.md`
