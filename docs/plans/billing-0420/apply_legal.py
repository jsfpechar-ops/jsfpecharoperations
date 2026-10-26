"""Brief 0420 step 2: Terms § 15, Privacy § 11 and one flash text for paid plans. Run from the repo root.

Each replacement must match exactly once (EN first, then CS), or nothing is written.
"""
import pathlib
import re

TERMS_EN = (
    "After a free trial of 30 days the Service is paid. The trial starts when the Host connects UbyPort or "
    "seven days after sign-up, whichever comes first. The Host chooses a plan and a monthly or yearly billing "
    "period on the plan page; prices per active apartment are published at ubyhost.com/cenik. The Operator "
    "invoices each billing period in advance; invoices are sent by e-mail and are payable by bank transfer "
    "within 14 days. The Operator is not a VAT payer; if that changes, prices are stated with VAT from the "
    "next billing period. An added apartment is billed from the day it becomes active: on a yearly plan by a "
    "supplementary invoice for the rest of the period, on a monthly plan from the next invoice. A lower plan, "
    "fewer apartments or a change from yearly to monthly takes effect from the next billing period. The Host "
    "may cancel at any time; the plan continues to the end of the paid period, and a started period is not "
    "refunded unless mandatory law requires otherwise. If an invoice is not paid when due, the Operator sends "
    "reminders; fourteen days after the due date the Account becomes read-only until the invoice is paid. "
    "Guest details already submitted continue to be reported to the police while the Account is read-only. "
    "The Operator may change prices for future billing periods with at least 30 days' notice. A founder "
    "price, where granted, stays for as long as the Host keeps the yearly plan without interruption."
)
TERMS_CS = (
    "Po 30denní zkušební době zdarma je Služba placená. Zkušební doba začíná připojením UbyPortu, nejpozději "
    "však sedm dní po registraci. Ubytovatel si v přehledu předplatného zvolí plán a měsíční nebo roční "
    "období; ceny za aktivní ubytování jsou zveřejněny na ubyhost.com/cenik. Provozovatel fakturuje každé "
    "období předem; faktury posílá e-mailem se splatností 14 dní a platí se převodem. Provozovatel není "
    "plátcem DPH; pokud se jím stane, ceny se od dalšího období uvádějí s DPH. Přidané ubytování se účtuje "
    "ode dne, kdy je aktivní: u ročního plánu doplatkovou fakturou za zbytek období, u měsíčního od další "
    "faktury. Nižší plán, méně ubytování nebo přechod z ročního na měsíční platí od dalšího období. "
    "Ubytovatel může předplatné kdykoli zrušit; plán trvá do konce zaplaceného období a za započaté období "
    "se peníze nevracejí, ledaže kogentní předpis stanoví jinak. Není-li faktura zaplacena včas, "
    "Provozovatel pošle připomínky; čtrnáct dní po splatnosti je Účet jen pro čtení, dokud faktura není "
    "zaplacena. Hosty, kteří už údaje vyplnili, hlásíme cizinecké policii i po tuto dobu. Provozovatel může "
    "ceny pro budoucí období změnit s oznámením nejméně 30 dní předem. Zakladatelská cena, byla-li "
    "přiznána, platí, dokud Ubytovatel bez přerušení pokračuje v ročním plánu."
)
PRIVACY = [
    ("logs are kept for 3 years. ",
     "logs are kept for 3 years. Invoices we issue to you and the bank payments for them are kept for 10 years "
     "from the end of the year of issue, as accounting law requires; your billing details are kept while the "
     "account exists and are shared with our accountant. "),
    ("Auditní záznamy se uchovávají 3 roky. ",
     "Auditní záznamy se uchovávají 3 roky. Faktury, které vám vystavíme, a platby k nim uchováváme 10 let od "
     "konce roku vystavení, jak vyžaduje zákon o účetnictví; fakturační údaje po dobu trvání účtu a předáváme "
     "je naší účetní. "),
]
FLASH = [
    ('%(unmatched)s not recognised, %(seen)s already imported."',
     '%(unmatched)s not recognised, %(seen)s already imported, %(ignored)s other payments skipped."'),
    ('nerozpoznáno %(unmatched)s, už načteno dříve %(seen)s."',
     'nerozpoznáno %(unmatched)s, už načteno dříve %(seen)s, jiné platby přeskočeny: %(ignored)s."'),
]


def _literal(text: str) -> str:
    """The body as the file writes it: a parenthesised run of string literals."""
    words, lines, line = text.split(" "), [], ""
    for word in words:
        if line and len(line) + len(word) > 90:
            lines.append(line)
            line = ""
        line += word + " "
    lines.append(line.rstrip())
    inner = "\n".join(f'            "{part}"' for part in lines)
    return f'"terms.s15_body": (\n{inner}\n        ),'


def main() -> None:
    terms = pathlib.Path("App/app/terms_i18n.py")
    text = terms.read_text(encoding="utf-8")
    blocks = list(re.finditer(r'"terms\.s15_body": \(\n.*?\n        \),', text, re.S))
    assert len(blocks) == 2, f"expected 2 terms.s15_body blocks, found {len(blocks)}"
    en, cs = blocks
    text = text[:en.start()] + _literal(TERMS_EN) + text[en.end():cs.start()] + _literal(TERMS_CS) + text[cs.end():]
    text = text.replace('"terms.s15_title": "15. Poplatky a platby"', '"terms.s15_title": "15. Ceny a platby"')

    privacy = pathlib.Path("App/app/privacy_policy_i18n.py")
    ptext = privacy.read_text(encoding="utf-8")
    for old, new in PRIVACY:
        assert ptext.count(old) == 1, f"privacy anchor not found once: {old!r}"
        ptext = ptext.replace(old, new)

    i18n = pathlib.Path("App/app/host_i18n.py")
    itext = i18n.read_text(encoding="utf-8")
    for old, new in FLASH:
        assert itext.count(old) == 1, f"flash anchor not found once: {old!r}"
        itext = itext.replace(old, new)

    terms.write_text(text, encoding="utf-8")
    privacy.write_text(ptext, encoding="utf-8")
    i18n.write_text(itext, encoding="utf-8")
    print("terms § 15 EN+CS, privacy § 11 EN+CS, 2 flash texts: done")


if __name__ == "__main__":
    main()
