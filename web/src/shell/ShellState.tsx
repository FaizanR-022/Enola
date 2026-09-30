/** Shell-wide UI state: rail, palette, boot, toast, header meta. Server state lives in
 *  TanStack Query, never here. */

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

export type RailMode = "closed" | "rail" | "full";

export interface ToastAction {
  label: string;
  onClick: () => void;
}

export interface ToastState {
  message: string;
  action?: ToastAction | undefined;
}

interface ShellState {
  railMode: RailMode;
  railOpen: boolean;
  cycleRail: () => void;
  setRailMode: (mode: RailMode) => void;
  paletteOpen: boolean;
  openPalette: (query?: string) => void;
  closePalette: () => void;
  paletteInitialQuery: string;
  bootDone: boolean;
  dataReady: boolean;
  finishBoot: () => void;
  skipBoot: () => void;
  toast: ToastState | null;
  say: (message: string, action?: ToastAction, durationMs?: number) => void;
  dismissToast: () => void;
  headerMeta: string | null;
  setHeaderMeta: (meta: string | null) => void;
  settingsOpen: boolean;
  setSettingsOpen: (open: boolean) => void;
}

const Ctx = createContext<ShellState | null>(null);
const RAIL_KEY = "enola.rail";

function readSplashMin(): number {
  const raw = import.meta.env["VITE_SPLASH_MIN_MS"];
  const parsed = typeof raw === "string" ? Number(raw) : NaN;
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : 3000;
}

function readRailMode(): RailMode {
  try {
    const stored = window.sessionStorage.getItem(RAIL_KEY);
    if (stored === "rail" || stored === "full" || stored === "closed") return stored;
  } catch {
    /* ignore */
  }
  return "closed";
}

export function ShellStateProvider({ children }: { children: ReactNode }) {
  const [railMode, setRailModeState] = useState<RailMode>(readRailMode);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [paletteInitialQuery, setPaletteInitialQuery] = useState("");
  const [dataReady, setDataReady] = useState(false);
  const [minElapsed, setMinElapsed] = useState(false);
  const [skipped, setSkipped] = useState(false);
  const [toast, setToast] = useState<ToastState | null>(null);
  const [headerMeta, setHeaderMeta] = useState<string | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const toastTimer = useRef<number | null>(null);

  // The splash leaves at max(dataReady, minDuration). Click skips both.
  useEffect(() => {
    const timer = window.setTimeout(() => setMinElapsed(true), readSplashMin());
    return () => window.clearTimeout(timer);
  }, []);
  const bootDone = skipped || (dataReady && minElapsed);
  const finishBoot = useCallback(() => setDataReady(true), []);
  const skipBoot = useCallback(() => setSkipped(true), []);

  const setRailMode = useCallback((mode: RailMode) => {
    setRailModeState(mode);
    try {
      window.sessionStorage.setItem(RAIL_KEY, mode);
    } catch {
      /* ignore */
    }
  }, []);
  const cycleRail = useCallback(() => {
    setRailMode(railMode === "closed" ? "rail" : railMode === "rail" ? "full" : "closed");
  }, [railMode, setRailMode]);

  const openPalette = useCallback((query = "") => {
    setPaletteInitialQuery(query);
    setPaletteOpen(true);
  }, []);
  const closePalette = useCallback(() => setPaletteOpen(false), []);

  const dismissToast = useCallback(() => {
    if (toastTimer.current !== null) window.clearTimeout(toastTimer.current);
    setToast(null);
  }, []);
  const say = useCallback((message: string, action?: ToastAction, durationMs = 3200) => {
    if (toastTimer.current !== null) window.clearTimeout(toastTimer.current);
    setToast({ message, action });
    toastTimer.current = window.setTimeout(() => setToast(null), action ? Math.max(durationMs, 6000) : durationMs);
  }, []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setPaletteOpen((open) => !open);
      }
      if (event.key === "Escape" && railMode === "full" && !paletteOpen) {
        setRailMode("rail");
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [railMode, paletteOpen, setRailMode]);

  const value = useMemo<ShellState>(
    () => ({
      railMode,
      railOpen: railMode !== "closed",
      cycleRail,
      setRailMode,
      paletteOpen,
      openPalette,
      closePalette,
      paletteInitialQuery,
      bootDone,
      dataReady,
      finishBoot,
      skipBoot,
      toast,
      say,
      dismissToast,
      headerMeta,
      setHeaderMeta,
      settingsOpen,
      setSettingsOpen,
    }),
    [railMode, cycleRail, setRailMode, paletteOpen, openPalette, closePalette, paletteInitialQuery, bootDone, dataReady, finishBoot, skipBoot, toast, say, dismissToast, headerMeta, settingsOpen],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useShell(): ShellState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useShell must be used inside ShellStateProvider");
  return ctx;
}

/** Screens call this to put a short mono line next to the title in the header. */
export function useHeaderMeta(meta: string | null | undefined): void {
  const { setHeaderMeta } = useShell();
  useEffect(() => {
    setHeaderMeta(meta ?? null);
    return () => setHeaderMeta(null);
  }, [meta, setHeaderMeta]);
}

/** Screens that do not gate the splash call this on mount; the dashboard calls it
 *  once its data has arrived. The bar reaches full at that point and holds until the
 *  minimum duration has passed. */
export function useFinishBoot(ready = true): void {
  const { finishBoot } = useShell();
  useEffect(() => {
    if (ready) finishBoot();
  }, [ready, finishBoot]);
}
