import type { ReactNode } from "react";

export type IconName = "home" | "overview" | "bed" | "sparkle" | "broom" | "invoice" | "receipt" | "coins" | "building" | "property" | "settings" | "search" | "chevron" | "arrow" | "alert" | "calendar" | "clock" | "more" | "close" | "check" | "link" | "eye" | "eyeOff" | "copy" | "trash" | "menu" | "download" | "filter";

const paths: Record<IconName, ReactNode> = {
  home: <><path d="M3 11.5 12 4l9 7.5" /><path d="M5.5 10v10h13V10M9 20v-6h6v6" /></>,
  overview: <><rect x="4" y="4" width="6" height="6" rx="1" /><rect x="14" y="4" width="6" height="6" rx="1" /><rect x="4" y="14" width="6" height="6" rx="1" /><rect x="14" y="14" width="6" height="6" rx="1" /></>,
  bed: <><path d="M4 18v-7M20 18v-5a2 2 0 0 0-2-2H8v7M4 14h16M7 11V8h4a2 2 0 0 1 2 2v1" /></>,
  sparkle: <><path d="m12 3 1.4 4.6L18 9l-4.6 1.4L12 15l-1.4-4.6L6 9l4.6-1.4z" /><path d="m19 15 .7 2.3L22 18l-2.3.7L19 21l-.7-2.3L16 18l2.3-.7z" /></>,
  broom: <><path d="M21 3 13.5 10.5" /><path d="m11 9 4 4" /><path d="M11 9c-2.5 1-5.5 3.5-7 8.5l2.5 2.5c5-1.5 7.5-4.5 8.5-7" /><path d="M7.5 13.5 10 16M5.5 16.5 7.5 18.5" /><path d="M16 19.5h.01M19 17h.01M19.5 21h.01" /></>,
  invoice: <><path d="M6 3h12v18l-3-2-3 2-3-2-3 2z" /><path d="M9 8h6M9 12h6" /></>,
  receipt: <><path d="M6 3h12v18l-3-2-3 2-3-2-3 2z" /><path d="M9 8h6M9 12h6M9 16h3" /></>,
  coins: <><ellipse cx="9" cy="7" rx="5" ry="3" /><path d="M4 7v4c0 1.7 2.2 3 5 3s5-1.3 5-3V7M4 11v4c0 1.7 2.2 3 5 3 1.2 0 2.3-.2 3.1-.6" /><path d="M14 12c3.3 0 6 1.3 6 3s-2.7 3-6 3M14 12v6M20 15v3c0 1.7-2.7 3-6 3-1.7 0-3.2-.4-4.3-1" /></>,
  building: <><path d="M4 21V5l8-2v18M12 8h8v13M2 21h20" /><path d="M8 8v2M8 13v2M16 12h1M16 16h1" /></>,
  property: <><path d="M3 11.5 12 4l9 7.5" /><path d="M5.5 10v10h13V10M9 20v-5h6v5" /><path d="M8 11h2M14 11h2" /></>,
  settings: <><circle cx="12" cy="12" r="3" /><path d="M19 12a7 7 0 0 0-.1-1l2-1.5-2-3.4-2.4 1A7 7 0 0 0 15 6l-.3-2.6h-4L10.5 6A7 7 0 0 0 9 7.1l-2.4-1-2 3.4 2 1.5a7 7 0 0 0 0 2l-2 1.5 2 3.4 2.4-1a7 7 0 0 0 1.5 1.1l.3 2.6h4L15 18a7 7 0 0 0 1.5-1.1l2.4 1 2-3.4-2-1.5a7 7 0 0 0 .1-1Z" /></>,
  search: <><circle cx="11" cy="11" r="7" /><path d="m20 20-4-4" /></>,
  chevron: <path d="m9 18 6-6-6-6" />,
  arrow: <path d="M5 12h14m-5-5 5 5-5 5" />,
  alert: <><path d="M12 3 2.5 20h19z" /><path d="M12 9v4M12 17h.01" /></>,
  calendar: <><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M16 3v4M8 3v4M3 10h18" /></>,
  clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
  more: <><circle cx="5" cy="12" r="1" fill="currentColor" /><circle cx="12" cy="12" r="1" fill="currentColor" /><circle cx="19" cy="12" r="1" fill="currentColor" /></>,
  close: <path d="m6 6 12 12M18 6 6 18" />,
  check: <path d="m5 12 4 4L19 6" />,
  link: <><path d="M10 13a5 5 0 0 0 7.1.1l2-2A5 5 0 0 0 12 4l-1 1" /><path d="M14 11a5 5 0 0 0-7.1-.1l-2 2A5 5 0 0 0 12 20l1-1" /></>,
  eye: <><path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Z" /><circle cx="12" cy="12" r="2.5" /></>,
  eyeOff: <><path d="m3 3 18 18M10.7 6.1A10 10 0 0 1 12 6c6 0 9.5 6 9.5 6a17 17 0 0 1-2.1 2.7M6.6 6.6C4 8.3 2.5 12 2.5 12s3.5 6 9.5 6a9 9 0 0 0 3-.5" /></>,
  copy: <><rect x="8" y="8" width="11" height="12" rx="2" /><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h2" /></>,
  trash: <><path d="M4 7h16M9 7V4h6v3M7 7l1 14h8l1-14M10 11v6M14 11v6" /></>,
  menu: <path d="M4 7h16M4 12h16M4 17h16" />,
  download: <><path d="M12 3v12m-5-5 5 5 5-5M5 21h14" /></>,
  filter: <path d="M4 6h16M7 12h10M10 18h4" />,
};

export default function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  return <svg className="icon" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}
