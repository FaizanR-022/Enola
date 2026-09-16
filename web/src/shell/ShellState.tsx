/** Shell-wide UI state: rail, palette, boot, toast, header meta. Server state lives in
 *  TanStack Query, never here. */

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

interface ShellState {
  railOpen: boolean;
  toggleRail: () => void;
  setRailOpen: (open: boolean) => void;
  paletteOpen: boolean;
  openPalette: (query?: string) => void;
  closePalette: () => void;
  paletteInitialQuery: string;
  bootDone: boolean;
  finishBoot: () => void;
  toast: string | null;
  say: (message: string) => void;
  headerMeta: string | null;
  setHeaderMeta: (meta: string | null) => void;
}

const Ctx = createContext<ShellState | null>(null);

export function ShellStateProvider({ children }: { children: ReactNode }) {
  const [railOpen, setRailOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [paletteInitialQuery, setPaletteInitialQuery] = useState("");
  const [bootDone, setBootDone] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [headerMeta, setHeaderMeta] = useState<string | null>(null);
  const toastTimer = useRef<number | null>(null);

  const toggleRail = useCallback(() => setRailOpen((v) => !v), []);
  const openPalette = useCallback((query = "") => {
    setPaletteInitialQuery(query);
    setPaletteOpen(true);
  }, []);
  const closePalette = useCallback(() => setPaletteOpen(false), []);
  const finishBoot = useCallback(() => setBootDone(true), []);

  const say = useCallback((message: string) => {
    if (toastTimer.current !== null) window.clearTimeout(toastTimer.current);
    setToast(message);
    toastTimer.current = window.setTimeout(() => setToast(null), 3200);
  }, []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setPaletteOpen((open) => !open);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const value = useMemo<ShellState>(
    () => ({
      railOpen,
      toggleRail,
      setRailOpen,
      paletteOpen,
      openPalette,
      closePalette,
      paletteInitialQuery,
      bootDone,
      finishBoot,
      toast,
      say,
      headerMeta,
      setHeaderMeta,
    }),
    [railOpen, toggleRail, paletteOpen, openPalette, closePalette, paletteInitialQuery, bootDone, finishBoot, toast, say, headerMeta],
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
 *  once its data has arrived. The splash never waits on a timer. */
export function useFinishBoot(ready = true): void {
  const { finishBoot } = useShell();
  useEffect(() => {
    if (ready) finishBoot();
  }, [ready, finishBoot]);
}
