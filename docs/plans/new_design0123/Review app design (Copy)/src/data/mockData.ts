import type { Cleaning, Property, Stay } from "../types";

export const properties: Property[] = [
  {
    id: "lipova",
    color: "teal",
    name: "Lípová 12 · Byt 3",
    city: "Praha 2",
    checkIn: "15:00",
    checkOut: "10:00",
    cleaningCode: "7391",
    instructions: "Čisté prádlo je v horní skříni v chodbě. Klíče vraťte do schránky u výtahu.",
  },
  {
    id: "karoliny",
    color: "blue",
    name: "Karoliny Světlé 8 · Apartmán do dvora",
    city: "Praha 1",
    checkIn: "16:00",
    checkOut: "11:00",
    cleaningCode: "2846",
    instructions: "Doplňte dvě kapsle do kávovaru. Balkonové dveře musí zůstat zamčené.",
  },
  {
    id: "vinohradska",
    color: "purple",
    name: "Vinohradská 24 · Rodinný apartmán s výhledem",
    city: "Praha 2",
    checkIn: "15:00",
    checkOut: "10:00",
    cleaningCode: "5180",
    instructions: "Dětská postýlka zůstává složená ve velké ložnici. Zkontrolujte zavřená střešní okna.",
  },
  { id: "korunni", color: "amber", name: "Korunní 41 · Studio", city: "Praha 3", checkIn: "15:00", checkOut: "10:00", cleaningCode: "6613", instructions: "Klíč od sklepa visí v kuchyni." },
  { id: "manesova", color: "pink", name: "Mánesova 7 · Podkrovní byt", city: "Praha 2", checkIn: "14:00", checkOut: "10:00", cleaningCode: "4027", instructions: "Střešní okna zavírat klikou nahoru." },
  { id: "brno", color: "indigo", name: "Údolní 15 · Brno centrum", city: "Brno", checkIn: "15:00", checkOut: "11:00", cleaningCode: "9352", instructions: "Odpad třídit do dvora vlevo." },
];

export const stays: Stay[] = [
  { id: "anna", guest: "Anna Müller", propertyId: "lipova", from: "2025-05-12", to: "2025-05-16", range: "12.–16. 5.", guests: 2, source: "Airbnb", reference: "HM4R8K2", state: "Chybí údaje", deadline: "Dnes 15:00", amount: "18 420 Kč" },
  { id: "james", guest: "James Wilson", propertyId: "karoliny", from: "2025-05-14", to: "2025-05-18", range: "14.–18. 5.", guests: 3, source: "Booking.com", reference: "429183", state: "Připraveno", deadline: "Dnes 18:00", amount: "22 180 Kč" },
  { id: "lucie", guest: "Lucie Nováková", propertyId: "lipova", from: "2025-05-18", to: "2025-05-20", range: "18.–20. 5.", guests: 2, source: "Airbnb", reference: "LQ8A110", state: "Odesláno", deadline: "Odesláno 08:42", amount: "7 950 Kč" },
  { id: "sophie", guest: "Sophie Bernard", propertyId: "vinohradska", from: "2025-05-20", to: "2025-05-25", range: "20.–25. 5.", guests: 5, source: "Booking.com", reference: "782654", state: "Připraveno", deadline: "20. 5. 12:00", amount: "28 640 Kč" },
  { id: "petr", guest: "Petr Dvořák", propertyId: "karoliny", from: "2025-05-23", to: "2025-05-26", range: "23.–26. 5.", guests: 2, source: "Přímo", reference: "UH-1058", state: "Odesláno", deadline: "Odesláno 9. 5.", amount: "11 200 Kč" },
];

export const cleanings: Cleaning[] = [
  { id: "c1", propertyId: "lipova", date: "2025-05-16", dateLabel: "16. května", weekday: "Pá", time: "10:15–13:30", checkout: "10:00", nextCheckIn: "15:00", notes: "Vyměnit povlak na dekoračním polštáři v ložnici.", conflict: "Na úklid zbývají jen 3 h 30 min." },
  { id: "c2", propertyId: "karoliny", date: "2025-05-18", dateLabel: "18. května", weekday: "Ne", time: "11:30–15:00", checkout: "11:00", nextCheckIn: "16:00", notes: "Host žádal bezpéřové lůžkoviny." },
  { id: "c3", propertyId: "lipova", date: "2025-05-20", dateLabel: "20. května", weekday: "Út", checkout: "10:00", nextCheckIn: "—", notes: "Doplnit tablety do myčky." },
  { id: "c4", propertyId: "vinohradska", date: "2025-05-25", dateLabel: "25. května", weekday: "Ne", time: "10:30–14:00", checkout: "10:00", nextCheckIn: "15:00", notes: "Dlouhá instrukce pro kontrolu všech střešních oken, dětské postýlky, náhradních ručníků a bezpečnostní zábrany u schodiště." },
  { id: "c5", propertyId: "karoliny", date: "2025-05-26", dateLabel: "26. května", weekday: "Po", time: "11:15–14:00", checkout: "11:00", nextCheckIn: "16:00", notes: "Běžný obrat apartmánu." },
];

export const invoices = [
  { number: "2025-051", customer: "Anna Müller", propertyId: "lipova", date: "12. 5. 2025", amount: "18 420 Kč", state: "Vystavená" },
  { number: "2025-050", customer: "James Wilson", propertyId: "karoliny", date: "10. 5. 2025", amount: "22 180 Kč", state: "Koncept" },
  { number: "2025-049", customer: "Lucie Nováková", propertyId: "lipova", date: "8. 5. 2025", amount: "7 950 Kč", state: "Vystavená" },
];

export const fees = [
  { propertyId: "lipova", amount: "6 240 Kč", state: "Připraveno", action: "Otevřít výpočet" },
  { propertyId: "karoliny", amount: "4 880 Kč", state: "Chybí osvobození", action: "Doplnit údaj" },
  { propertyId: "vinohradska", state: "Není nastaveno", action: "Nastavit poplatek" },
];
