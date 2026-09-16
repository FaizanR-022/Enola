/** Date, money and label formatting. One place, so every screen agrees. */

const DAY_MS = 86_400_000;

export function parseDate(value: string | null | undefined): Date | null {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

function startOfDay(date: Date): Date {
  const copy = new Date(date);
  copy.setHours(0, 0, 0, 0);
  return copy;
}

/** "today", "Wed", "17 Sep", "3 Sep" — the short form used in task rows. */
export function dueLabel(value: string | null | undefined, now = new Date()): string {
  const date = parseDate(value);
  if (!date) return "—";
  const days = Math.round((startOfDay(date).getTime() - startOfDay(now).getTime()) / DAY_MS);
  if (days === 0) return "today";
  if (days === 1) return "tomorrow";
  if (days === -1) return "yesterday";
  if (days > 1 && days < 7) return date.toLocaleDateString(undefined, { weekday: "short" });
  return date.toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

export type DueTone = "danger" | "held" | "soft" | "muted";

/** Overdue is clay, today is ochre, this week is soft, later is muted. */
export function dueTone(value: string | null | undefined, now = new Date()): DueTone {
  const date = parseDate(value);
  if (!date) return "muted";
  const days = Math.round((startOfDay(date).getTime() - startOfDay(now).getTime()) / DAY_MS);
  if (days < 0) return "danger";
  if (days === 0) return "held";
  if (days < 7) return "soft";
  return "muted";
}

/** "41d", "5d", "today", "never" — the last-contact form. */
export function agoLabel(value: string | null | undefined, now = new Date()): string {
  const date = parseDate(value);
  if (!date) return "never";
  const days = Math.round((startOfDay(now).getTime() - startOfDay(date).getTime()) / DAY_MS);
  if (days <= 0) return "today";
  if (days === 1) return "yesterday";
  return `${days}d ago`;
}

/** "held 14m", "held 2h", "held 3d". */
export function heldAge(value: string, now = new Date()): string {
  const date = parseDate(value);
  if (!date) return "";
  const minutes = Math.max(0, Math.round((now.getTime() - date.getTime()) / 60_000));
  if (minutes < 60) return `${minutes}m`;
  if (minutes < 48 * 60) return `${Math.round(minutes / 60)}h`;
  return `${Math.round(minutes / 1440)}d`;
}

export function timeLabel(value: string | null | undefined): string {
  const date = parseDate(value);
  return date ? date.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", hour12: false }) : "";
}

export function dateLabel(value: string | null | undefined): string {
  const date = parseDate(value);
  return date ? date.toLocaleDateString(undefined, { day: "numeric", month: "short" }) : "";
}

export function dayHeading(value: string, now = new Date()): string {
  const date = parseDate(value);
  if (!date) return "";
  const days = Math.round((startOfDay(now).getTime() - startOfDay(date).getTime()) / DAY_MS);
  const full = date.toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "short" });
  return days === 0 ? `Today · ${full}` : days === 1 ? `Yesterday · ${full}` : full;
}

/** "PKR 2,400" or "2,400" — amounts are integers in practice. */
export function pkr(value: number | string, withCurrency = true): string {
  const n = typeof value === "string" ? Number(value) : value;
  const sign = n < 0 ? "−" : "";
  const body = Math.abs(Math.round(n)).toLocaleString("en-PK");
  return `${sign}${withCurrency ? "PKR " : ""}${body}`;
}

export function signedPkr(value: number | string): string {
  const n = typeof value === "string" ? Number(value) : value;
  return `${n > 0 ? "+" : n < 0 ? "−" : ""}${Math.abs(Math.round(n)).toLocaleString("en-PK")}`;
}

/** Today at 18:00 local, as an ISO string, for quick-add defaults. */
export function isoAt(daysFromNow: number, hour = 18): string {
  const date = new Date();
  date.setDate(date.getDate() + daysFromNow);
  date.setHours(hour, 0, 0, 0);
  return date.toISOString();
}

export function toDatetimeLocal(value: string | null | undefined): string {
  const date = parseDate(value);
  if (!date) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export function fromDatetimeLocal(value: string): string | null {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

export function plural(n: number, one: string, many = `${one}s`): string {
  return `${n} ${n === 1 ? one : many}`;
}
