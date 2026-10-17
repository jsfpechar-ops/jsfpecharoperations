import { useEffect, useRef } from "react";
import type { Cleaning, Property } from "../types";
import Icon from "./Icon";
import { Button, Status } from "./ui";

export default function CleaningDetail({ cleaning, property, close, goSettings, toast }: { cleaning: Cleaning; property: Property; close: () => void; goSettings: () => void; toast: (message: string) => void }) {
  const drawerRef = useRef<HTMLElement>(null);
  useEffect(() => {
    const trigger = document.activeElement as HTMLElement | null;
    drawerRef.current?.focus();
    return () => trigger?.focus();
  }, []);
  return <div className="drawer-backdrop" onMouseDown={(event) => event.target === event.currentTarget && close()}>
    <aside className="detail-drawer" role="dialog" aria-modal="true" aria-labelledby="cleaning-detail-title" tabIndex={-1} ref={drawerRef}>
      <header><div><span>{cleaning.weekday} {cleaning.dateLabel}</span><h2 id="cleaning-detail-title">{property.name}</h2></div><button className="icon-button" aria-label="Zavřít detail úklidu" onClick={close}><Icon name="close" /></button></header>
      {cleaning.conflict && <div className="conflict-box"><Status tone="danger">Časový konflikt</Status><p>{cleaning.conflict} Další host přijíždí v {cleaning.nextCheckIn}.</p></div>}
      <dl className="detail-facts"><div><dt>Úklid</dt><dd>{cleaning.time || "Čas dle domluvy"}</dd></div><div><dt>Odjezd</dt><dd>{cleaning.checkout}</dd></div><div><dt>Další příjezd</dt><dd>{cleaning.nextCheckIn}</dd></div><div><dt>Dostupné okno</dt><dd>{cleaning.nextCheckIn === "—" ? "Bez dalšího příjezdu" : `${property.checkOut}–${property.checkIn}`}</dd></div></dl>
      <section><h3>Poznámka k události</h3><p>{cleaning.notes}</p></section>
      <section><h3>Instrukce nemovitosti</h3><p>{property.instructions}</p></section>
      <section className="manager-code"><div><h3>Trvalý kód pro úklid</h3><p>Není to PIN hosta.</p></div><code>{property.cleaningCode}</code></section>
      <div className="inherited-note">Časy příjezdu a odjezdu se dědí z nastavení nemovitosti. <button onClick={goSettings}>Upravit v nastavení nemovitosti</button></div>
      <footer><Button variant="secondary" onClick={() => toast("Úpravy úklidu byly otevřeny v prototypu.")}>Upravit úklid</Button><Button variant="danger" onClick={() => { toast("Úklid byl odebrán z náhledu."); close(); }}>Odebrat</Button></footer>
    </aside>
  </div>;
}
