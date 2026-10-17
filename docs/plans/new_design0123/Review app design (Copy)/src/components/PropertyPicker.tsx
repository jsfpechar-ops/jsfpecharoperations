import { useEffect, useId, useRef, useState } from "react";
import type { Property } from "../types";
import Icon from "./Icon";

/** One property selector for every screen: compact trigger, searchable list, identity colour. */
export default function PropertyPicker({ properties, value, onChange, allowAll = true, label = "Ubytování" }: { properties: Property[]; value: string; onChange: (id: string) => void; allowAll?: boolean; label?: string }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [cursor, setCursor] = useState(0);
  const root = useRef<HTMLDivElement>(null);
  const search = useRef<HTMLInputElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const listId = useId();
  const current = properties.find((item) => item.id === value);
  const options = [
    ...(allowAll ? [{ id: "all", name: "Všechna ubytování", city: `${properties.length} ubytování`, color: "" }] : []),
    ...properties.filter((item) => `${item.name} ${item.city}`.toLowerCase().includes(query.toLowerCase())),
  ];

  useEffect(() => {
    if (!open) return;
    search.current?.focus();
    setCursor(Math.max(0, options.findIndex((item) => item.id === value)));
    const outside = (event: MouseEvent) => { if (!root.current?.contains(event.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", outside);
    return () => document.removeEventListener("mousedown", outside);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const close = () => { setOpen(false); setQuery(""); trigger.current?.focus(); };
  const choose = (id: string) => { onChange(id); close(); };
  const onKey = (event: React.KeyboardEvent) => {
    if (event.key === "Escape") { event.stopPropagation(); close(); }
    else if (event.key === "ArrowDown") { event.preventDefault(); setCursor((c) => Math.min(options.length - 1, c + 1)); }
    else if (event.key === "ArrowUp") { event.preventDefault(); setCursor((c) => Math.max(0, c - 1)); }
    else if (event.key === "Enter" && options[cursor]) { event.preventDefault(); choose(options[cursor].id); }
  };

  return <div className="picker" ref={root}>
    <span className="picker-label">{label}</span>
    <button ref={trigger} type="button" className={`picker-trigger ${open ? "is-open" : ""}`} aria-haspopup="listbox" aria-expanded={open} onClick={() => setOpen(!open)}>
      {current ? <span className={`identity-dot tone-${current.color}`} /> : <span className="identity-dot all" />}
      <span className="picker-value">{current ? current.name : "Všechna ubytování"}</span>
      <Icon name="chevron" size={15} />
    </button>
    {open && <div className="picker-pop" onKeyDown={onKey}>
      <div className="picker-search"><Icon name="search" size={16} /><input ref={search} value={query} onChange={(e) => { setQuery(e.target.value); setCursor(0); }} placeholder="Hledat ubytování" aria-label="Hledat ubytování" aria-controls={listId} aria-activedescendant={options[cursor] ? `${listId}-${options[cursor].id}` : undefined} /></div>
      <ul role="listbox" id={listId} aria-label={label}>
        {options.map((item, index) => <li key={item.id} id={`${listId}-${item.id}`} role="option" aria-selected={item.id === value} className={`${index === cursor ? "is-cursor" : ""} ${item.id === "all" ? "is-all" : ""}`} onMouseEnter={() => setCursor(index)} onClick={() => choose(item.id)}>
          <span className={item.id === "all" ? "identity-dot all" : `identity-dot tone-${item.color}`} />
          <span><strong>{item.name}</strong><small>{item.city}</small></span>
          {item.id === value && <Icon name="check" size={16} />}
        </li>)}
        {options.length === 0 && <li className="picker-empty">Nic nenalezeno</li>}
      </ul>
    </div>}
  </div>;
}
