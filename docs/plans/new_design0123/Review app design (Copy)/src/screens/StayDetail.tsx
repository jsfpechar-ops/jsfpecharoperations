import { useState } from "react";
import { properties } from "../data/mockData";
import type { Stay } from "../types";
import Icon from "../components/Icon";
import { Button, Status } from "../components/ui";

export default function StayDetail({ stay, back, resolved, resolve }: { stay: Stay; back: () => void; resolved: boolean; resolve: () => void }) {
  const [expanded, setExpanded] = useState(false);
  const property = properties.find((item) => item.id === stay.propertyId)!;
  const needsData = stay.id === "anna" && !resolved;
  const records = [
    ["Údaje hostů", needsData ? "Chybí údaje" : "Přijato", needsData ? "Čekáme na hosta" : "Dnes 10:18"],
    ["Hlášení policii", needsData ? "Blokováno" : stay.state, needsData ? "Po doplnění údajů" : stay.deadline],
    ["Kód dveří", "Naplánováno", `Platnost od ${property.checkIn}`],
    ["Faktura", "Připravená", stay.amount],
    ["Poplatek z pobytu", "Započítáno", "400 Kč"],
  ];
  return <div className="page detail-page">
    <button className="back-button" onClick={back}><Icon name="chevron" /> Zpět na pobyty</button>
    <header className="stay-header"><div><div className="stay-title"><h1>{stay.guest}</h1><Status tone={needsData ? "warning" : "success"}>{needsData ? "Čeká na údaje" : stay.state}</Status></div><p>{stay.range} · {property.name} · {stay.source} {stay.reference}</p></div><strong>{stay.amount}</strong></header>
    {needsData && <section className="issue-banner"><Icon name="alert" /><div><strong>Host nedokončil údaje pro hlášení policii</strong><span>Termín: dnes v 15:00</span></div><Button onClick={resolve}>Připomenout hosta</Button></section>}
    <section className="record-list" aria-labelledby="record-title"><h2 id="record-title">Stav pobytu</h2>{records.map(([name, state, meta], index) => <div className={`record-row ${index === 0 && needsData ? "current" : ""}`} key={name}><span className="record-icon">{index < 2 && !needsData ? <Icon name="check" /> : index === 0 && needsData ? <Icon name="alert" /> : <Icon name={index === 2 ? "settings" : "invoice"} />}</span><strong>{name}</strong><span>{meta}</span><Status tone={state === "Chybí údaje" || state === "Blokováno" ? "warning" : state === "Přijato" || state === "Odesláno" ? "success" : "neutral"}>{state}</Status></div>)}</section>
    <section className="disclosure"><button aria-expanded={expanded} onClick={() => setExpanded(!expanded)}>Kontaktní a finanční údaje <Icon name="chevron" /></button>{expanded && <div><dl><div><dt>E-mail</dt><dd>anna.mueller@email.de</dd></div><div><dt>Telefon</dt><dd>+49 151 234 5678</dd></div><div><dt>Hosté</dt><dd>{stay.guests}</dd></div><div><dt>Celkem</dt><dd>{stay.amount}</dd></div></dl></div>}</section>
  </div>;
}
