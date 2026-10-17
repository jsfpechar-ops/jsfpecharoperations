import { useState } from "react";
import { properties, stays } from "../data/mockData";
import Icon from "./Icon";

const days = Array.from({ length: 15 }, (_, index) => index + 12);
const placement: Record<string, { start: number; span: number }> = {
  anna: { start: 1, span: 4 }, james: { start: 3, span: 4 }, lucie: { start: 7, span: 2 }, sophie: { start: 9, span: 5 }, petr: { start: 12, span: 3 },
};

export default function DashboardCalendar({ openStay }: { openStay: (id: string) => void }) {
  const [view, setView] = useState<"month" | "gantt">("gantt");
  const [period, setPeriod] = useState(0);
  return <section className="calendar-section" aria-labelledby="calendar-title">
    <div className="section-head">
      <div><h2 id="calendar-title">Kalendář pobytů</h2><span>Květen 2025 · všechny nemovitosti</span></div>
      <div className="calendar-controls">
        <div className="segmented compact" aria-label="Zobrazení kalendáře">
          <button className={view === "month" ? "active" : ""} onClick={() => setView("month")}>Měsíc</button>
          <button className={view === "gantt" ? "active" : ""} onClick={() => setView("gantt")}>Nemovitosti</button>
        </div>
        <button className="icon-button previous" aria-label="Předchozí období" title="Předchozí období" onClick={() => setPeriod(period - 1)}><Icon name="chevron" /></button>
        <button className="today-button" onClick={() => setPeriod(0)}>Dnes</button>
        <button className="icon-button next" aria-label="Další období" title="Další období" onClick={() => setPeriod(period + 1)}><Icon name="chevron" /></button>
      </div>
    </div>
    {period !== 0 ? <div className="calendar-shift"><span>Ukázkové období {period > 0 ? "červen" : "duben"} 2025</span><button onClick={() => setPeriod(0)}>Vrátit na květen</button></div> :
      <>
        <div className={`gantt ${view === "month" ? "month-mode" : ""}`}>
          <div className="gantt-corner">Nemovitost</div>
          <div className="gantt-days">{days.map((day) => <span key={day} className={day === 16 ? "today" : ""}>{day}<small>{["Po","Út","St","Čt","Pá","So","Ne"][(day + 2) % 7]}</small></span>)}</div>
          {properties.map((property) => <div className="gantt-row" key={property.id}>
            <div className="gantt-property"><strong><span className={`identity-dot tone-${property.color}`} />{property.name}</strong><span>{property.city}</span></div>
            <div className="gantt-track">
              {days.map((day) => <span key={day} className={day === 16 ? "today-line" : ""} />)}
              {stays.filter((stay) => stay.propertyId === property.id).map((stay) => {
                const place = placement[stay.id];
                return <button key={stay.id} className={`booking tone-${property.color} ${stay.state === "Chybí údaje" ? "needs-action" : ""}`} title={`${stay.guest} · ${stay.range}${stay.state === "Chybí údaje" ? " · chybí údaje" : ""}`} style={{ "--start": place.start, "--span": place.span } as React.CSSProperties} onClick={() => openStay(stay.id)}>
                  <strong>{stay.state === "Chybí údaje" && <Icon name="alert" size={12} />}{stay.guest}</strong><small>{stay.range} · {stay.guests} os.</small>
                </button>;
              })}
            </div>
          </div>)}
        </div>
        <div className="mobile-agenda">
          {stays.slice(0, 4).map((stay) => <button key={stay.id} onClick={() => openStay(stay.id)}><time>{stay.range}</time><span><strong>{stay.guest}</strong><small>{properties.find((p) => p.id === stay.propertyId)?.name}</small></span><Icon name="chevron" /></button>)}
        </div>
      </>}
    <p className="sync-line">Synchronizováno před 4 min</p>
  </section>;
}
