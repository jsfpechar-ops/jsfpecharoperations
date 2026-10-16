import { useState } from "react";
import type { Property } from "../types";
import Icon from "../components/Icon";
import PropertyPicker from "../components/PropertyPicker";
import { Button, PageHeader, Toggle } from "../components/ui";

export default function PropertySettings({ properties, updateProperty, sharedCodes, setSharedCodes, toast }: { properties: Property[]; updateProperty: (id: string, checkIn: string, checkOut: string) => void; sharedCodes: boolean; setSharedCodes: (value: boolean) => void; toast: (message: string) => void }) {
  const [selected, setSelected] = useState(properties[0].id);
  const property = properties.find((item) => item.id === selected)!;
  const [checkIn, setCheckIn] = useState(property.checkIn);
  const [checkOut, setCheckOut] = useState(property.checkOut);
  const selectProperty = (id: string) => {
    const next = properties.find((item) => item.id === id)!;
    setSelected(id); setCheckIn(next.checkIn); setCheckOut(next.checkOut);
  };
  return <div className="page">
    <PageHeader title="Ubytování" meta={`${properties.length} ubytování`} />
    <div className="settings-picker"><PropertyPicker properties={properties} value={selected} onChange={selectProperty} allowAll={false} label="Nastavení pro" /><span>{property.city} · kód pro úklid ••••</span></div>
    <div className="property-settings-layout">
      <div className="settings-sections">
        <section id="arrival"><div className="settings-title"><div><h2>Příjezd a odjezd</h2><p>Výchozí časy pro nemovitost.</p></div><span className="saved-label">Autoritativní nastavení</span></div>
          <div className="time-fields"><label>Čas příjezdu<input type="time" value={checkIn} onChange={(e) => setCheckIn(e.target.value)} /></label><label>Čas odjezdu<input type="time" value={checkOut} onChange={(e) => setCheckOut(e.target.value)} /></label></div>
          <Button onClick={() => { updateProperty(selected, checkIn, checkOut); toast("Časy příjezdu a odjezdu byly uloženy."); }}>Uložit časy</Button>
        </section>
        <section><div className="settings-title"><div><h2>Úklid</h2><p>Úklidy používají výchozí časy příjezdu a odjezdu.</p></div></div>
          <div className="inherited-row"><span>Odjezd</span><strong>{property.checkOut}</strong><em>Z nastavení nemovitosti</em></div><div className="inherited-row"><span>Příjezd</span><strong>{property.checkIn}</strong><em>Z nastavení nemovitosti</em></div>
          <button className="text-link" onClick={() => document.getElementById("arrival")?.scrollIntoView()}>Upravit v nastavení nemovitosti <Icon name="arrow" /></button>
        </section>
        <section><div className="settings-title"><div><h2>Kódy dveří</h2><p>Platnost kódů hostů vychází ze stejných časů.</p></div></div>
          <div className="inherited-row"><span>Platný od</span><strong>{property.checkIn}</strong><em>Z nastavení nemovitosti</em></div><div className="inherited-row"><span>Platný do</span><strong>{property.checkOut}</strong><em>Z nastavení nemovitosti</em></div>
          <button className="text-link" onClick={() => document.getElementById("arrival")?.scrollIntoView()}>Upravit v nastavení nemovitosti <Icon name="arrow" /></button>
        </section>
        <section><div className="setting-toggle"><div><h2>Sdílené odkazy pro úklid</h2><p>Zobrazovat přístupové kódy ve sdílených odkazech</p><small>Platí pro existující i budoucí odkazy. Kódy hostů ani jejich PINy se nemění.</small></div><Toggle checked={sharedCodes} onChange={() => { setSharedCodes(!sharedCodes); toast(!sharedCodes ? "Kódy jsou ve sdílených odkazech zapnuté." : "Kódy byly ze sdílených odkazů odebrány."); }} label="Zobrazovat přístupové kódy ve sdílených odkazech pro úklid" /></div></section>
      </div>
    </div>
  </div>;
}
