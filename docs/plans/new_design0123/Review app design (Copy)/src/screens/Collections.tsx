import { useEffect, useMemo, useState } from "react";
import { fees, invoices, properties, stays } from "../data/mockData";
import Icon from "../components/Icon";
import PropertyPicker from "../components/PropertyPicker";
import { Button, EmptyState, PageHeader, Status } from "../components/ui";

type CollectionScreen = "stays" | "invoices" | "fees";

export default function Collections({ screen, openStay, toast }: { screen: CollectionScreen; openStay: (id: string) => void; toast: (message: string) => void }) {
  const [query, setQuery] = useState("");
  const [property, setProperty] = useState("all");
  const [period, setPeriod] = useState("may");
  const [state, setState] = useState("all");

  useEffect(() => {
    setQuery("");
    setProperty("all");
    setPeriod("may");
    setState("all");
  }, [screen]);

  const titles = { stays: "Pobyty", invoices: "Faktury", fees: "Poplatky z pobytu" };
  const searchLabels = { stays: "Hledat pobyt", invoices: "Hledat fakturu", fees: "Hledat poplatek" };
  const placeholders = { stays: "Host nebo ubytování", invoices: "Číslo, zákazník nebo ubytování", fees: "Název ubytování" };
  const stateOptions = screen === "stays"
    ? [["all", "Všechny stavy"], ["Chybí údaje", "Chybí údaje"], ["Připraveno", "Připraveno"], ["Odesláno", "Odesláno"]]
    : screen === "invoices"
      ? [["all", "Všechny stavy"], ["Vystavená", "Vystavená"], ["Koncept", "Koncept"]]
      : [["all", "Všechny stavy"], ["Připraveno", "Připraveno"], ["Chybí osvobození", "Chybí údaj"], ["Není nastaveno", "Není nastaveno"]];

  const visibleStays = useMemo(() => stays.filter((stay) => {
    const home = properties.find((item) => item.id === stay.propertyId)!;
    return period === "may" && (property === "all" || stay.propertyId === property) && (state === "all" || stay.state === state) && `${stay.guest} ${home.name} ${stay.reference}`.toLowerCase().includes(query.toLowerCase());
  }), [period, property, query, state]);

  const visibleInvoices = useMemo(() => invoices.filter((invoice) => {
    const home = properties.find((item) => item.id === invoice.propertyId)!;
    return period === "may" && (property === "all" || invoice.propertyId === property) && (state === "all" || invoice.state === state) && `${invoice.number} ${invoice.customer} ${home.name}`.toLowerCase().includes(query.toLowerCase());
  }), [period, property, query, state]);

  const visibleFees = useMemo(() => fees.filter((fee) => {
    const home = properties.find((item) => item.id === fee.propertyId)!;
    return period === "may" && (property === "all" || fee.propertyId === property) && (state === "all" || fee.state === state) && home.name.toLowerCase().includes(query.toLowerCase());
  }), [period, property, query, state]);

  const resultCount = screen === "stays" ? visibleStays.length : screen === "invoices" ? visibleInvoices.length : visibleFees.length;
  const clearFilters = () => { setQuery(""); setProperty("all"); setPeriod("may"); setState("all"); };

  return <div className="page collection-page">
    <PageHeader
      title={titles[screen]}
      action={screen === "stays" ? <Button onClick={() => toast("Formulář pro nový pobyt je připravený k otevření.")}>Přidat pobyt</Button> : undefined}
    />
    <CollectionToolbar
      searchLabel={searchLabels[screen]}
      placeholder={placeholders[screen]}
      query={query}
      setQuery={setQuery}
      property={property}
      setProperty={setProperty}
      period={period}
      setPeriod={setPeriod}
      state={state}
      setState={setState}
      stateOptions={stateOptions}
      resultCount={resultCount}
    />

    {resultCount === 0 && <EmptyState title="Žádné odpovídající záznamy" body="Změňte hledání, období nebo filtry." action={<Button variant="secondary" onClick={clearFilters}>Zrušit filtry</Button>} />}

    {screen === "stays" && resultCount > 0 && <div className="responsive-table collection-table stays-table" role="table" aria-label="Pobyty">
      <div className="table-head" role="row"><span>Host</span><span>Termín</span><span>Ubytování</span><span>Hosté</span><span>Hlášení</span><span>Termín / akce</span></div>
      {visibleStays.map((stay) => <button role="row" className="table-row" key={stay.id} onClick={() => openStay(stay.id)}>
        <span data-label="Host"><strong>{stay.guest}</strong><small>{stay.source} · {stay.reference}</small></span>
        <span data-label="Termín">{stay.range}</span>
        <span data-label="Ubytování"><Home id={stay.propertyId} /></span>
        <span data-label="Hosté">{stay.guests}</span>
        <span data-label="Hlášení"><Status tone={stay.state === "Chybí údaje" ? "warning" : stay.state === "Odesláno" ? "success" : "info"}>{stay.state}</Status></span>
        <span data-label="Termín / akce"><b>{stay.deadline}</b><Icon name="chevron" /></span>
      </button>)}
    </div>}

    {screen === "invoices" && resultCount > 0 && <div className="responsive-table collection-table invoice-table" role="table" aria-label="Faktury">
      <div className="table-head" role="row"><span>Číslo</span><span>Zákazník</span><span>Ubytování</span><span>Datum</span><span>Částka</span><span>Stav</span><span>Akce</span></div>
      {visibleInvoices.map((invoice) => <div role="row" className="table-row static" key={invoice.number}>
        <span data-label="Číslo"><strong>{invoice.number}</strong></span>
        <span data-label="Zákazník">{invoice.customer}</span>
        <span data-label="Ubytování"><Home id={invoice.propertyId} /></span>
        <span data-label="Datum">{invoice.date}</span>
        <span data-label="Částka"><strong>{invoice.amount}</strong></span>
        <span data-label="Stav"><Status tone={invoice.state === "Koncept" ? "neutral" : "success"}>{invoice.state}</Status></span>
        <span data-label="Akce"><Button variant="quiet" icon="download" onClick={() => toast(`PDF faktury ${invoice.number} je připravené.`)}>Stáhnout PDF</Button></span>
      </div>)}
    </div>}

    {screen === "fees" && resultCount > 0 && <div className="responsive-table collection-table fees-table" role="table" aria-label="Poplatky z pobytu">
      <div className="table-head" role="row"><span>Období</span><span>Ubytování</span><span>Částka</span><span>Stav</span><span>Co chybí</span><span>Akce</span></div>
      {visibleFees.map((fee) => {
        const home = properties.find((item) => item.id === fee.propertyId)!;
        const unconfigured = fee.state === "Není nastaveno";
        return <div role="row" className="table-row static" key={fee.propertyId}>
          <span data-label="Období">Květen 2025</span>
          <span data-label="Ubytování"><strong><Home id={home.id} /></strong></span>
          <span data-label="Částka">{unconfigured ? <span className="not-applicable">—</span> : <strong>{fee.amount}</strong>}</span>
          <span data-label="Stav"><Status tone={fee.state === "Připraveno" ? "success" : fee.state === "Není nastaveno" ? "neutral" : "warning"}>{fee.state}</Status></span>
          <span data-label="Co chybí">{fee.state === "Chybí osvobození" ? "Důvod osvobození" : unconfigured ? "Sazba poplatku" : "Nic"}</span>
          <span data-label="Akce"><Button variant={unconfigured ? "secondary" : "quiet"} onClick={() => toast(`${fee.action}: ${home.name}`)}>{fee.action}</Button></span>
        </div>;
      })}
    </div>}
  </div>;
}

function CollectionToolbar({ searchLabel, placeholder, query, setQuery, property, setProperty, period, setPeriod, state, setState, stateOptions, resultCount }: {
  searchLabel: string;
  placeholder: string;
  query: string;
  setQuery: (value: string) => void;
  property: string;
  setProperty: (value: string) => void;
  period: string;
  setPeriod: (value: string) => void;
  state: string;
  setState: (value: string) => void;
  stateOptions: string[][];
  resultCount: number;
}) {
  return <section className="collection-controls" aria-label="Filtry záznamů">
    <label className="search-control"><span>{searchLabel}</span><div><Icon name="search" /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={placeholder} /></div></label>
    <label><span>Období</span><select value={period} onChange={(event) => setPeriod(event.target.value)}><option value="may">Květen 2025</option><option value="april">Duben 2025</option></select></label>
    <PropertyPicker properties={properties} value={property} onChange={setProperty} />
    <label><span>Stav</span><select value={state} onChange={(event) => setState(event.target.value)}>{stateOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
    <strong className="result-count">{resultCount} {resultCount === 1 ? "záznam" : resultCount > 1 && resultCount < 5 ? "záznamy" : "záznamů"}</strong>
  </section>;
}

function Home({ id }: { id: string }) {
  const home = properties.find((item) => item.id === id)!;
  return <span className="identity"><span className={`identity-dot tone-${home.color}`} />{home.name}</span>;
}
