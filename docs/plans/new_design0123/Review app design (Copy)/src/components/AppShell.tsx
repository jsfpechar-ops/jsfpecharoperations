import { useEffect, useState, type ReactNode } from "react";
import type { Screen } from "../types";
import Icon, { type IconName } from "./Icon";

const nav: { screen: Screen; label: string; icon: IconName }[] = [
  { screen: "dashboard", label: "Přehled", icon: "overview" },
  { screen: "stays", label: "Pobyty", icon: "bed" },
  { screen: "properties", label: "Ubytování", icon: "property" },
  { screen: "cleaning", label: "Úklid", icon: "broom" },
  { screen: "invoices", label: "Faktury", icon: "receipt" },
  { screen: "fees", label: "Poplatky z pobytu", icon: "coins" },
];

export default function AppShell({ screen, go, children }: { screen: Screen; go: (screen: Screen) => void; children: ReactNode }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const active = screen === "stay-detail" ? "stays" : screen === "link-builder" ? "cleaning" : screen;
  const navigate = (next: Screen) => {
    go(next);
    setMenuOpen(false);
  };
  useEffect(() => {
    if (!menuOpen) return;
    const close = (event: KeyboardEvent) => event.key === "Escape" && setMenuOpen(false);
    document.addEventListener("keydown", close);
    return () => document.removeEventListener("keydown", close);
  }, [menuOpen]);
  return <div className="app-shell">
    <aside className="sidebar">
      <button className="wordmark" onClick={() => navigate("dashboard")} aria-label="UbyHost – přehled"><span className="brand-symbol">UH</span><strong>UbyHost</strong></button>
      <button className="command-search" onClick={() => navigate("stays")}><Icon name="search" /><span>Hledat pobyt</span><kbd>Ctrl K</kbd></button>
      <nav aria-label="Hlavní navigace">
        {nav.map((item) => <button key={item.screen} className={active === item.screen ? "active" : ""} onClick={() => navigate(item.screen)}><Icon name={item.icon} /><span>{item.label}</span>{item.screen === "cleaning" && <b>1</b>}</button>)}
      </nav>
      <div className="sidebar-foot">
        <button onClick={() => navigate("properties")}><Icon name="settings" /><span>Nastavení</span></button>
        <button className="account"><span className="avatar">MK</span><span><strong>Martin Král</strong><small>Král Apartments</small></span><Icon name="more" /></button>
      </div>
    </aside>
    <header className="mobile-appbar">
      <button className="icon-button" aria-label={menuOpen ? "Zavřít navigaci" : "Otevřít navigaci"} aria-expanded={menuOpen} onClick={() => setMenuOpen(!menuOpen)}><Icon name={menuOpen ? "close" : "menu"} /></button>
      <button className="mobile-brand" onClick={() => navigate("dashboard")} aria-label="UbyHost – přehled"><span>UH</span><strong>UbyHost</strong></button>
      <button className="icon-button" aria-label="Hledat pobyt" onClick={() => navigate("stays")}><Icon name="search" /></button>
    </header>
    {menuOpen && <div className="mobile-menu-backdrop" onMouseDown={(event) => event.target === event.currentTarget && setMenuOpen(false)}>
      <aside className="mobile-menu" aria-label="Mobilní navigace">
        <nav>{nav.map((item) => <button key={item.screen} className={active === item.screen ? "active" : ""} onClick={() => navigate(item.screen)}><Icon name={item.icon} /><span>{item.label}</span>{item.screen === "cleaning" && <b>1</b>}</button>)}</nav>
        <button className="mobile-settings" onClick={() => navigate("properties")}><Icon name="settings" /> Nastavení</button>
      </aside>
    </div>}
    <main className="main">{children}</main>
  </div>;
}
