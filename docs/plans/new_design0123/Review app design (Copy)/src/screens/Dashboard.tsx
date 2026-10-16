import { properties, stays } from "../data/mockData";
import DashboardCalendar from "../components/DashboardCalendar";
import Icon from "../components/Icon";
import { Button, PageHeader } from "../components/ui";
import type { Stay } from "../types";

type QueueItem = { stay: Stay; task: string; tone: "action" | "ready"; due: string; primary: { label: string; run: () => void }; secondary?: { label: string; run: () => void } };

export default function Dashboard({ openStay, resolved, resolve, toast }: { openStay: (id: string) => void; resolved: boolean; resolve: () => void; toast: (message: string) => void }) {
  const byId = (id: string) => stays.find((item) => item.id === id)!;
  const queue: QueueItem[] = [
    ...(!resolved ? [{ stay: byId("anna"), task: "Chybí údaje 1 hosta pro hlášení policii", tone: "action" as const, due: "Termín dnes 15:00", primary: { label: "Připomenout hosta", run: resolve }, secondary: { label: "Otevřít pobyt", run: () => openStay("anna") } }] : []),
    { stay: byId("james"), task: "Hlášení je připraveno k odeslání", tone: "ready", due: "Termín dnes 18:00", primary: { label: "Zkontrolovat a odeslat", run: () => openStay("james") } },
  ];
  return <div className="page">
    <PageHeader title="Přehled" eyebrow="Pondělí 12. května" action={<div className="dashboard-actions"><Button variant="secondary" icon="calendar" onClick={() => toast("Kalendáře byly právě aktualizovány.")}>Aktualizovat kalendáře</Button><Button onClick={() => toast("Formulář pro nový pobyt je připravený k otevření.")}>Přidat pobyt</Button></div>} />
    <nav className="stat-tiles" aria-label="Provozní souhrn">
      <a href="#queue-title" className={`stat-tile action ${resolved ? "" : "is-positive"}`}><strong>{resolved ? 0 : 1}</strong><span>Vyžaduje akci</span></a>
      <a href="#queue-title" className="stat-tile ready is-positive"><strong>2</strong><span>Připraveno k odeslání</span></a>
      <a href="#queue-title" className="stat-tile overdue"><strong>0</strong><span>Po termínu</span></a>
    </nav>
    <DashboardCalendar openStay={openStay} />
    <section className="work-queue" aria-labelledby="queue-title">
      <div className="section-head"><div><h2 id="queue-title">K vyřízení</h2><span>Seřazeno podle nejbližšího termínu</span></div><button className="text-link" onClick={() => openStay("anna")}>Všechny pobyty <Icon name="arrow" size={16} /></button></div>
      <div className="queue-list">
        {queue.map(({ stay, task, tone, due, primary, secondary }) => {
          const home = properties.find((item) => item.id === stay.propertyId)!;
          return <article key={stay.id} className={`queue-row tone-${tone}`}>
            <button className="queue-main" onClick={() => openStay(stay.id)} aria-label={`${stay.guest}, ${home.name}, ${task}`}>
              <span className="queue-dates">{stay.range} · {stay.guests} {stay.guests < 5 ? "hosté" : "hostů"} · {stay.source}</span>
              <span className="queue-who"><strong>{stay.guest}</strong><span className="identity"><span className={`identity-dot tone-${home.color}`} />{home.name}</span></span>
              <span className="queue-task"><span className={`pill pill-${tone}`}>{tone === "action" && <Icon name="alert" size={13} />}{task}</span><span className="queue-due">{due}</span></span>
            </button>
            <div className="row-actions">
              {secondary && <Button variant="quiet" onClick={secondary.run}>{secondary.label}</Button>}
              <Button variant={tone === "action" ? "primary" : "secondary"} onClick={primary.run}>{primary.label}</Button>
            </div>
          </article>;
        })}
      </div>
      {resolved && <div className="inline-success"><Icon name="check" /> Připomínka byla odeslána Anně Müller. Pobyt se vrátí sem, až host údaje doplní.</div>}
    </section>
  </div>;
}
