import { useMemo, useState } from "react";
import { cleanings, properties } from "../data/mockData";
import type { Cleaning as CleaningType } from "../types";
import Icon from "../components/Icon";
import PropertyPicker from "../components/PropertyPicker";
import { Button, EmptyState, PageHeader, Status } from "../components/ui";

export default function Cleaning({ openDetail, openBuilder }: { openDetail: (cleaning: CleaningType) => void; openBuilder: () => void }) {
  const [mode, setMode] = useState<"agenda" | "calendar">("agenda");
  const [property, setProperty] = useState("all");
  const [period, setPeriod] = useState("30");
  const visible = useMemo(() => cleanings.filter((item) => property === "all" || item.propertyId === property), [property]);
  const setCalendar = () => {
    setMode("calendar");
    if (property === "all") setProperty(properties[0].id);
  };
  return <div className="page">
    <PageHeader title="Úklid" meta="5 naplánovaných úklidů" action={<Button icon="link" onClick={openBuilder}>Sdílet úklidy</Button>} />
    <div className="toolbar cleaning-toolbar">
      <div className="segmented" aria-label="Zobrazení úklidu"><button className={mode === "agenda" ? "active" : ""} onClick={() => setMode("agenda")}>Agenda</button><button className={mode === "calendar" ? "active" : ""} onClick={setCalendar}>Kalendář</button></div>
      <div className="filter-fields">
        <label>Období<select value={period} onChange={(e) => setPeriod(e.target.value)}><option value="30">Příštích 30 dní</option><option value="7">Příštích 7 dní</option><option value="past">Minulé úklidy</option></select></label>
        <PropertyPicker properties={properties} value={property} onChange={(id) => { setProperty(id); if (mode === "calendar" && id === "all") setMode("agenda"); }} allowAll={mode === "agenda"} />
      </div>
    </div>
    {mode === "calendar" && <div className="scope-note"><Icon name="calendar" /> Kalendář zobrazuje jednu vybranou nemovitost. <button onClick={() => setMode("agenda")}>Zobrazit všechny v agendě</button></div>}
    {period === "past" ? <EmptyState title="V tomto období nejsou žádné úklidy" body="Změňte období nebo se vraťte k nadcházejícím úklidům." action={<Button variant="secondary" onClick={() => setPeriod("30")}>Zobrazit příštích 30 dní</Button>} /> :
      mode === "agenda" ? <div className="agenda-list">
        <div className="cleaning-list-head" aria-hidden="true"><span>Datum</span><span>Ubytování</span><span>Časy obratu</span><span>Stav a detail</span></div>
        {visible.map((item) => {
          const home = properties.find((p) => p.id === item.propertyId)!;
          return <button className={`cleaning-row ${item.conflict ? "has-conflict" : ""}`} key={item.id} onClick={() => openDetail(item)}>
            <time><b>{item.weekday}</b><strong>{item.dateLabel.split(" ")[0]}</strong><span>kvě</span></time>
            <div className="cleaning-property"><strong><span className={`identity-dot tone-${home.color}`} />{home.name}</strong><span>{home.city}</span>{item.conflict && <span className="mobile-conflict">Časový konflikt</span>}</div>
            <dl><div><dt>Úklid</dt><dd>{item.time || "Čas dle domluvy"}</dd></div><div><dt>Odjezd</dt><dd>{item.checkout}</dd></div><div><dt>Další příjezd</dt><dd>{item.nextCheckIn}</dd></div></dl>
            <div className="cleaning-state">{item.conflict && <Status tone="danger">Časový konflikt</Status>}<span>Detail <Icon name="chevron" /></span></div>
          </button>;
        })}
      </div> : <CleaningCalendar propertyId={property} openDetail={openDetail} />}
  </div>;
}

function CleaningCalendar({ propertyId, openDetail }: { propertyId: string; openDetail: (cleaning: CleaningType) => void }) {
  const home = properties.find((item) => item.id === propertyId)!;
  const events = cleanings.filter((item) => item.propertyId === propertyId);
  const [monthOffset, setMonthOffset] = useState(0);
  return <section className="cleaning-calendar">
    <div className="calendar-month"><button className="previous" aria-label="Předchozí měsíc" title="Předchozí měsíc" onClick={() => setMonthOffset(monthOffset - 1)}><Icon name="chevron" /></button><strong>{monthOffset === 0 ? "Květen 2025" : monthOffset > 0 ? "Červen 2025" : "Duben 2025"}</strong><button className="next" aria-label="Další měsíc" title="Další měsíc" onClick={() => setMonthOffset(monthOffset + 1)}><Icon name="chevron" /></button></div>
    {monthOffset !== 0 && <div className="calendar-shift"><span>V tomto měsíci nejsou naplánované úklidy.</span><button onClick={() => setMonthOffset(0)}>Vrátit na květen</button></div>}
    {monthOffset === 0 && <>
    <div className="month-grid">{["Po","Út","St","Čt","Pá","So","Ne"].map((d) => <span className="day-name" key={d}>{d}</span>)}{Array.from({ length: 35 }, (_, index) => {
      const day = index - 2;
      const event = events.find((item) => Number(item.date.slice(-2)) === day);
      return <div className={`day-cell ${day < 1 || day > 31 ? "outside" : ""}`} key={index}><span>{day > 0 && day <= 31 ? day : ""}</span>{event && <button className={event.conflict ? "conflict" : ""} onClick={() => openDetail(event)}><b>Úklid</b><small>{event.time || "Dle domluvy"}</small></button>}</div>;
    })}</div>
    <p className="calendar-caption">{home.name} · časy příjezdu a odjezdu se dědí z nastavení nemovitosti</p>
    </>}
  </section>;
}
