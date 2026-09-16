/** The screen inventory. Nav, palette, phone tabs and the header all read from here. */

import type { DotTone } from "@/ui";

export type ScreenId =
  | "home"
  | "approvals"
  | "tasks"
  | "log"
  | "email"
  | "chat"
  | "jobs"
  | "people"
  | "projects"
  | "learning"
  | "academics"
  | "finance"
  | "memory";

export interface Screen {
  id: ScreenId;
  label: string;
  path: string;
  dot: DotTone;
  /** Shown in the nav badge slot when > 0. Only Approvals has one. */
  badge?: "held";
}

export interface NavSection {
  label: string;
  items: ReadonlyArray<Screen>;
}

export const SCREENS: ReadonlyArray<Screen> = [
  { id: "home", label: "Home", path: "/", dot: "accent" },
  { id: "approvals", label: "Approvals", path: "/approvals", dot: "held", badge: "held" },
  { id: "tasks", label: "Tasks", path: "/tasks", dot: "muted" },
  { id: "log", label: "Log", path: "/log", dot: "muted" },
  { id: "email", label: "Email", path: "/email", dot: "muted" },
  { id: "chat", label: "Chat", path: "/chat", dot: "muted" },
  { id: "jobs", label: "Jobs", path: "/jobs", dot: "accent" },
  { id: "people", label: "People", path: "/people", dot: "muted" },
  { id: "projects", label: "Projects", path: "/projects", dot: "muted" },
  { id: "learning", label: "Self-learning", path: "/learning", dot: "muted" },
  { id: "academics", label: "Academics", path: "/academics", dot: "paper" },
  { id: "finance", label: "Finance", path: "/finance", dot: "muted" },
  { id: "memory", label: "Memory", path: "/memory", dot: "muted" },
];

function pick(...ids: ScreenId[]): Screen[] {
  return ids.map((id) => {
    const screen = SCREENS.find((s) => s.id === id);
    if (!screen) throw new Error(`unknown screen ${id}`);
    return screen;
  });
}

/** Four groups named after what you are doing, not what the data is. */
export const NAV_SECTIONS: ReadonlyArray<NavSection> = [
  { label: "Today", items: pick("home", "approvals", "tasks", "log", "email", "chat") },
  { label: "Pursuit", items: pick("jobs", "people", "projects", "learning") },
  { label: "Study", items: pick("academics") },
  { label: "Life", items: pick("finance") },
];

/** Phone: four tabs at the bottom, the rest behind "more". */
export const PHONE_TABS: ReadonlyArray<Screen> = pick("home", "approvals", "chat");
export const PHONE_MORE: ReadonlyArray<Screen> = pick(
  "tasks",
  "jobs",
  "academics",
  "finance",
  "people",
  "log",
  "email",
  "projects",
  "learning",
  "memory",
);

export function screenForPath(pathname: string): Screen {
  const match = SCREENS.filter((s) => s.path === "/" ? pathname === "/" : pathname === s.path || pathname.startsWith(`${s.path}/`)).sort(
    (a, b) => b.path.length - a.path.length,
  )[0];
  return match ?? SCREENS[0]!;
}
