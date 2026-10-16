import { useEffect, useRef, type ReactNode } from "react";
import Icon, { type IconName } from "./Icon";

export function Button({ children, variant = "primary", icon, onClick, disabled, type = "button" }: { children: ReactNode; variant?: "primary" | "secondary" | "quiet" | "danger"; icon?: IconName; onClick?: () => void; disabled?: boolean; type?: "button" | "submit" }) {
  return <button type={type} className={`button button-${variant}`} onClick={onClick} disabled={disabled}>{icon && <Icon name={icon} size={17} />}{children}</button>;
}

export function Status({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "warning" | "danger" | "success" | "info" }) {
  return <span className={`status status-${tone}`}><span aria-hidden="true" />{children}</span>;
}

export function Toggle({ checked, onChange, label }: { checked: boolean; onChange: () => void; label: string }) {
  return <button type="button" className={`toggle ${checked ? "is-on" : ""}`} role="switch" aria-checked={checked} aria-label={label} onClick={onChange}><span /></button>;
}

export function PageHeader({ title, eyebrow, meta, action }: { title: string; eyebrow?: ReactNode; meta?: ReactNode; action?: ReactNode }) {
  return <header className="page-heading"><div>{eyebrow && <div className="page-eyebrow">{eyebrow}</div>}<h1>{title}</h1>{meta && <div className="page-meta">{meta}</div>}</div>{action && <div className="page-action">{action}</div>}</header>;
}

export function EmptyState({ title, body, action }: { title: string; body: string; action?: ReactNode }) {
  return <div className="empty-state"><strong>{title}</strong><p>{body}</p>{action}</div>;
}

export function Dialog({ title, children, onClose, triggerRef }: { title: string; children: ReactNode; onClose: () => void; triggerRef?: React.RefObject<HTMLButtonElement | null> }) {
  const dialogRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const prior = document.activeElement as HTMLElement | null;
    dialogRef.current?.focus();
    const close = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("keydown", close);
      (triggerRef?.current || prior)?.focus();
    };
  }, [onClose, triggerRef]);
  return <div className="dialog-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
    <div className="dialog" role="dialog" aria-modal="true" aria-labelledby="dialog-title" tabIndex={-1} ref={dialogRef}>
      <div className="dialog-head"><h2 id="dialog-title">{title}</h2><button className="icon-button" aria-label="Zavřít" onClick={onClose}><Icon name="close" /></button></div>
      {children}
    </div>
  </div>;
}

export function Toast({ children, onClose }: { children: ReactNode; onClose: () => void }) {
  return <div className="toast" role="status"><Icon name="check" size={16} /><span>{children}</span><button aria-label="Zavřít oznámení" onClick={onClose}><Icon name="close" size={16} /></button></div>;
}
