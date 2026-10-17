export type Screen =
  | "dashboard"
  | "cleaning"
  | "stays"
  | "invoices"
  | "fees"
  | "properties"
  | "stay-detail"
  | "link-builder"
  | "shared";

export type Property = {
  id: string;
  name: string;
  city: string;
  color: "teal" | "blue" | "purple" | "amber" | "pink" | "indigo";
  checkIn: string;
  checkOut: string;
  cleaningCode: string;
  instructions: string;
};

export type Stay = {
  id: string;
  guest: string;
  propertyId: string;
  from: string;
  to: string;
  range: string;
  guests: number;
  source: string;
  reference: string;
  state: "Chybí údaje" | "Připraveno" | "Odesláno";
  deadline: string;
  amount: string;
};

export type Cleaning = {
  id: string;
  propertyId: string;
  date: string;
  dateLabel: string;
  weekday: string;
  time?: string;
  checkout: string;
  nextCheckIn: string;
  notes: string;
  conflict?: string;
};

export type LinkState = "draft" | "generated" | "active" | "updated" | "revoked";
