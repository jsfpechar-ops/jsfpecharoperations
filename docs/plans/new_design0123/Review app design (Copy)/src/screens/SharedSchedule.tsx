import { useState } from "react";
import { cleanings } from "../data/mockData";
import type { Property } from "../types";
import Icon from "../components/Icon";
import { EmptyState, Status } from "../components/ui";

export default function SharedSchedule({ selected, properties, showCodes, revoked, exit }: { selected: string[]; properties: Property[]; showCodes: boolean; revoked: boolean; exit: () => void }) {
  const [property, setProperty] = useState("all");
  const [mode, setMode] = useState<"agenda" | "calendar">("agenda");
  const [revealed, setRevealed] = useState<Record<string, boolean>>({});
  const events = cleanings.filter((item) => selected.includes(item.id) && (property === "all" || item.propertyId === property));
  const propertyIds = [...new Set(cleanings.filter((item) => selected.includes(item.id)).map((item) => item.propertyId))];
  if (revoked) return <div className="shared-shell"><header className="shared-header"><span className="public-wordmark"><b>uby</b>host</span></header><main className="shared-main"><EmptyState title="Odkaz už není aktivní" body="Správce tento sdílený odkaz zrušil. Požádejte ho o nový odkaz." /></main></div>;
  return <div className="shared-shell">
    <header className="shared-header"><span className="public-wordmark"><b>uby</b>host</span><span>Plán úklidu · pouze pro čtení</span><button onClick={exit}>Zpět do správy</button></header>
    <main className="shared-main">
      <div className="shared-title"><div><h1>Nadcházející úklidy</h1><p>Aktualizováno dnes v 9:42</p></div><Status tone="success">Aktivní odkaz</Status></div>
      <div className="shared-filters"><label>Nemovitost<select value={property} onChange={(e) => { setProperty(e.target.value); if (e.target.value === "all") setMode("agenda"); }}><option value="all">Všechny v odkazu</option>{propertyIds.map((id) => <option value={id} key={id}>{properties.find((p) => p.id === id)?.name}</option>)}</select></label>{property !== "all" && <div className="segmented"><button className={mode === "agenda" ? "active" : ""} onClick={() => setMode("agenda")}>Agenda</button><button className={mode === "calendar" ? "active" : ""} onClick={() => setMode("calendar")}>Kalendář</button></div>}</div>
      {mode === "calendar" ? <div className="public-calendar"><Icon name="calendar" /><strong>Květen 2025 · {properties.find((p) => p.id === property)?.name}</strong>{events.map((event) => <button key={event.id} onClick={() => setMode("agenda")}>{event.dateLabel}<span>{event.time || "Čas dle domluvy"}</span></button>)}</div> :
      <div className="shared-agenda">{events.map((event) => {
        const home = properties.find((item) => item.id === event.propertyId)!;
        const open = revealed[event.id];
        return <article className="shared-event" key={event.id}><header><time><b>{event.weekday}</b><strong>{event.dateLabel}</strong></time><div><h2>{home.name}</h2><p>{home.city}</p></div></header><dl><div><dt>Okno pro úklid</dt><dd>{event.time || `Po ${event.checkout}, čas dle domluvy`}</dd></div><div><dt>Další příjezd</dt><dd>{event.nextCheckIn}</dd></div></dl><section><h3>Instrukce</h3><p>{home.instructions}</p>{event.notes && <p className="event-note"><b>Poznámka:</b> {event.notes}</p>}</section>{showCodes && <section className="code-section"><div><h3>Kód pro úklid</h3><p>Trvalý kód určený pouze pro úklid.</p></div><code aria-live="polite">{open ? home.cleaningCode : "••••"}</code><button className="icon-button" aria-label={open ? "Skrýt kód pro úklid" : "Zobrazit kód pro úklid"} aria-pressed={open} onClick={() => setRevealed({ ...revealed, [event.id]: !open })}><Icon name={open ? "eyeOff" : "eye"} /></button><details><summary>Zobrazit bez interaktivního tlačítka</summary><code>{home.cleaningCode}</code></details></section>}</article>;
      })}</div>}
    </main>
  </div>;
}
