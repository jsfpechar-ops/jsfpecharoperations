import { cleanings, properties } from "../data/mockData";
import type { LinkState } from "../types";
import Icon from "../components/Icon";
import { Button, PageHeader, Status } from "../components/ui";

export default function LinkBuilder({ selected, setSelected, state, setState, openShared, back, toast }: { selected: string[]; setSelected: (ids: string[]) => void; state: LinkState; setState: (state: LinkState) => void; openShared: () => void; back: () => void; toast: (message: string) => void }) {
  const toggle = (id: string) => {
    setSelected(selected.includes(id) ? selected.filter((item) => item !== id) : [...selected, id]);
    if (state !== "draft" && state !== "revoked") setState("updated");
  };
  const selectedEvents = cleanings.filter((item) => selected.includes(item.id));
  const generated = state !== "draft";
  return <div className="page">
    <button className="back-button" onClick={back}><Icon name="chevron" /> Zpět na úklid</button>
    <PageHeader title="Sdílet úklidy" meta="Vyberte pouze dny, které má úklidová firma vidět." />
    <div className="builder-layout">
      <section className="event-picker"><div className="picker-head"><h2>Vybrat úklidy</h2><span>{selected.length} vybráno</span></div>
        {cleanings.map((event) => {
          const home = properties.find((item) => item.id === event.propertyId)!;
          return <label className="select-event" key={event.id}><input type="checkbox" checked={selected.includes(event.id)} onChange={() => toggle(event.id)} /><time><strong>{event.weekday} {event.dateLabel}</strong><span>{event.time || "Čas dle domluvy"}</span></time><span><strong>{home.name}</strong><small>Odjezd {event.checkout} · další příjezd {event.nextCheckIn}</small></span></label>;
        })}
      </section>
      <aside className="share-review"><h2>Rozsah odkazu</h2><div className="selected-summary"><strong>{selected.length}</strong><span>vybrané úklidy</span><small>{selected.length ? `${selectedEvents[0]?.dateLabel} – ${selectedEvents.at(-1)?.dateLabel}` : "Bez vybraného období"}</small></div>
        <ul>{selectedEvents.map((event) => <li key={event.id}><span>{event.dateLabel}</span><strong>{properties.find((item) => item.id === event.propertyId)?.name}</strong></li>)}</ul>
        <label className="expiry">Platnost odkazu<select defaultValue="30"><option value="7">7 dní</option><option value="30">30 dní</option><option value="90">90 dní</option></select></label>
        {!generated ? <Button disabled={!selected.length} icon="link" onClick={() => setState("generated")}>Vygenerovat odkaz</Button> : <GeneratedLink state={state} setState={setState} openShared={openShared} toast={toast} />}
      </aside>
    </div>
  </div>;
}

function GeneratedLink({ state, setState, openShared, toast }: { state: LinkState; setState: (state: LinkState) => void; openShared: () => void; toast: (message: string) => void }) {
  if (state === "revoked") return <div className="revoked-state"><Status tone="danger">Zrušeno</Status><p>Tento odkaz už nelze otevřít.</p><Button variant="secondary" onClick={() => setState("generated")}>Vytvořit nový odkaz</Button></div>;
  return <div className="generated-link"><Status tone={state === "updated" ? "info" : "success"}>{state === "generated" ? "Vygenerováno" : state === "updated" ? "Aktualizováno" : "Aktivní"}</Status><p>Token se zobrazí jen nyní. Odkaz je pouze pro čtení a lze ho kdykoli zrušit.</p><code>ubyhost.cz/c/kh7Q••••••••9m</code><div className="link-actions"><Button variant="secondary" icon="copy" onClick={() => { setState("active"); toast("Odkaz byl zkopírován."); }}>Kopírovat odkaz</Button><Button variant="quiet" onClick={openShared}>Otevřít náhled</Button></div><button className="danger-link" onClick={() => setState("revoked")}><Icon name="trash" /> Zrušit odkaz</button></div>;
}
