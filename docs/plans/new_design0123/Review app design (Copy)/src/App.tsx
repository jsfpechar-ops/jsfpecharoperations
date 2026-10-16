import { useEffect, useMemo, useState } from "react";
import AppShell from "./components/AppShell";
import CleaningDetail from "./components/CleaningDetail";
import { Toast } from "./components/ui";
import { properties as initialProperties, stays } from "./data/mockData";
import Dashboard from "./screens/Dashboard";
import Cleaning from "./screens/Cleaning";
import Collections from "./screens/Collections";
import LinkBuilder from "./screens/LinkBuilder";
import PropertySettings from "./screens/PropertySettings";
import SharedSchedule from "./screens/SharedSchedule";
import StayDetail from "./screens/StayDetail";
import type { Cleaning as CleaningType, LinkState, Property, Screen } from "./types";

export default function App() {
  const [screen, setScreen] = useState<Screen>("dashboard");
  const [selectedStay, setSelectedStay] = useState("anna");
  const [selectedCleaning, setSelectedCleaning] = useState<CleaningType | null>(null);
  const [resolved, setResolved] = useState(false);
  const [properties, setProperties] = useState<Property[]>(initialProperties);
  const [sharedCodes, setSharedCodes] = useState(true);
  const [selectedEvents, setSelectedEvents] = useState<string[]>(["c1", "c2", "c4"]);
  const [linkState, setLinkState] = useState<LinkState>("draft");
  const [toast, setToast] = useState("");

  useEffect(() => {
    if (!selectedCleaning) return;
    const close = (event: KeyboardEvent) => event.key === "Escape" && setSelectedCleaning(null);
    document.addEventListener("keydown", close);
    return () => document.removeEventListener("keydown", close);
  }, [selectedCleaning]);

  const stay = useMemo(() => stays.find((item) => item.id === selectedStay) || stays[0], [selectedStay]);
  const openStay = (id: string) => { setSelectedStay(id); setScreen("stay-detail"); };
  const notify = (message: string) => { setToast(message); window.setTimeout(() => setToast(""), 4200); };
  const updateProperty = (id: string, checkIn: string, checkOut: string) => setProperties((items) => items.map((item) => item.id === id ? { ...item, checkIn, checkOut } : item));

  if (screen === "shared") return <SharedSchedule selected={selectedEvents} properties={properties} showCodes={sharedCodes} revoked={linkState === "revoked"} exit={() => setScreen("link-builder")} />;

  let content;
  if (screen === "dashboard") content = <Dashboard openStay={openStay} resolved={resolved} resolve={() => { setResolved(true); notify("Připomínka byla odeslána hostovi."); }} toast={notify} />;
  else if (screen === "cleaning") content = <Cleaning openDetail={setSelectedCleaning} openBuilder={() => setScreen("link-builder")} />;
  else if (screen === "stays" || screen === "invoices" || screen === "fees") content = <Collections screen={screen} openStay={openStay} toast={notify} />;
  else if (screen === "properties") content = <PropertySettings properties={properties} updateProperty={updateProperty} sharedCodes={sharedCodes} setSharedCodes={setSharedCodes} toast={notify} />;
  else if (screen === "stay-detail") content = <StayDetail stay={stay} back={() => setScreen("stays")} resolved={resolved} resolve={() => { setResolved(true); notify("Připomínka byla odeslána."); }} />;
  else content = <LinkBuilder selected={selectedEvents} setSelected={setSelectedEvents} state={linkState} setState={setLinkState} openShared={() => setScreen("shared")} back={() => setScreen("cleaning")} toast={notify} />;

  return <AppShell screen={screen} go={setScreen}>
    {content}
    {selectedCleaning && <CleaningDetail cleaning={selectedCleaning} property={properties.find((item) => item.id === selectedCleaning.propertyId)!} close={() => setSelectedCleaning(null)} goSettings={() => { setSelectedCleaning(null); setScreen("properties"); }} toast={notify} />}
    {toast && <Toast onClose={() => setToast("")}>{toast}</Toast>}
  </AppShell>;
}
