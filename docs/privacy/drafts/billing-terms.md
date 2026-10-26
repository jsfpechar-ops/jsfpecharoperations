# Draft: Terms § 15 and Privacy note for paid plans (billing phase 1)

Status: **draft for the owner and counsel.** Nothing here is live. Applying it is a Terms/Privacy text change, so it needs a version bump (1.6 → 1.7 in `App/app/config.py` defaults and `docs/ENVIRONMENT.md`), a new `UBYHOST_LEGAL_EFFECTIVE_DATE`, and notice to hosts at least 30 days before (Terms § 22). Today's § 15 already allows fees "on reasonable notice", so billing can be switched on for **new** hosts before this lands; existing ("OG") hosts are never billed by the code.

What the text must match (the code, briefs 0411–0419):

- 30-day trial, starting when UbyPort is connected or 7 days after sign-up, whichever is first.
- Price per active apartment, per /cenik; yearly or monthly, invoiced in advance; due 14 days after issue; "Nejsem plátce DPH".
- More apartments: billed from that day (a supplementary invoice on a yearly plan; on monthly, from the next invoice). Fewer apartments, a lower plan or monthly instead of yearly: from the next period.
- Cancel: the plan runs to the end of the paid period, then the account is read-only. No refund of a started period.
- Unpaid: reminders 1 and 7 days after the due date; read-only after 14 days. Guests who already filled in their details are still reported to the police. Paying opens the account again.
- Founder price: the first 100 yearly orders keep the founder price while the yearly plan continues.

## Terms § 15, English

**15. Fees and payment**

15.1 After a free trial of 30 days, the Service is paid. The trial starts when the Host connects UbyPort or seven days after sign-up, whichever comes first. The Host chooses a plan and a monthly or yearly billing period on the plan page; prices per active apartment are published at ubyhost.com/cenik.

15.2 The Operator invoices each billing period in advance. Invoices are sent by e-mail and are payable by bank transfer within 14 days. The Operator is not a VAT payer; if that changes, prices are stated with VAT from the next billing period.

15.3 An added apartment is billed from the day it becomes active: on a yearly plan by a supplementary invoice for the rest of the period, on a monthly plan from the next invoice. A lower plan, fewer apartments or a change from yearly to monthly takes effect from the next billing period.

15.4 The Host may cancel at any time; the plan continues to the end of the paid period and is not refunded for a started period, unless mandatory law requires otherwise.

15.5 If an invoice is not paid when due, the Operator sends reminders. Fourteen days after the due date the Account becomes read-only until the invoice is paid. Guest details already submitted continue to be reported to the police while the Account is read-only.

15.6 The Operator may change prices for future billing periods with at least 30 days' notice. A founder price, where granted, stays for as long as the Host keeps the yearly plan without interruption.

## Terms § 15, Czech

**15. Ceny a platby**

15.1 Po 30denní zkušební době zdarma je Služba placená. Zkušební doba začíná připojením UbyPortu, nejpozději však sedm dní po registraci. Ubytovatel si v přehledu předplatného zvolí plán a měsíční nebo roční období; ceny za aktivní ubytování jsou zveřejněny na ubyhost.com/cenik.

15.2 Provozovatel fakturuje každé období předem. Faktury posílá e-mailem se splatností 14 dní, platí se převodem. Provozovatel není plátcem DPH; pokud se jím stane, ceny se od dalšího období uvádějí s DPH.

15.3 Přidané ubytování se účtuje ode dne, kdy je aktivní: u ročního plánu doplatkovou fakturou za zbytek období, u měsíčního od další faktury. Nižší plán, méně ubytování nebo přechod z ročního na měsíční platí od dalšího období.

15.4 Ubytovatel může předplatné kdykoli zrušit; plán trvá do konce zaplaceného období a za započaté období se peníze nevracejí, ledaže kogentní předpis stanoví jinak.

15.5 Není-li faktura zaplacena včas, Provozovatel pošle připomínky. Čtrnáct dní po splatnosti je Účet jen pro čtení, dokud faktura není zaplacena. Hosty, kteří už údaje vyplnili, cizinecké policii hlásíme i po tuto dobu.

15.6 Provozovatel může ceny pro budoucí období změnit s oznámením nejméně 30 dní předem. Zakladatelská cena, byla-li přiznána, platí, dokud Ubytovatel bez přerušení pokračuje v ročním plánu.

## Privacy policy, addition (both languages, the operator's own processing)

EN: *Billing.* When you order a plan we keep your invoice details (name, address, IČO/DIČ, billing e-mail), your plan and the invoices we issue, and the bank payments for them (date, amount, variable symbol, payer account). We need them to perform the contract and, for invoices, to meet accounting law, which requires us to keep them for 10 years. We share them with our accountant. No card details: payment is by bank transfer.

CS: *Fakturace.* Když si objednáte plán, uchováváme fakturační údaje (jméno nebo název, adresu, IČO/DIČ, fakturační e-mail), plán, vystavené faktury a platby k nim (datum, částku, variabilní symbol, účet plátce). Potřebujeme je k plnění smlouvy a u faktur k plnění zákona o účetnictví, který vyžaduje uchovávat je 10 let. Předáváme je naší účetní. Údaje o kartách nemáme: platí se převodem.

## Questions for counsel

1. Is § 15.4 (no refund of a started period) fine for a consumer host (a natural person renting privately)?
2. Is the read-only pause in § 15.5 proportionate, given that police reporting continues?
3. Does the accountant need a processing agreement, or are they an independent controller under the accounting law?
