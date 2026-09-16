import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { cx } from "@/lib/cx";
import { usePaletteSearch, type PaletteHit } from "@/lib/search";
import { Dot, Mono, Sheet } from "@/ui";
import { useShell } from "./ShellState";
import { SCREENS } from "./screens";
import styles from "./CommandPalette.module.css";

interface Group {
  label: string;
  items: PaletteHit[];
}

/** ⌘K. Doubles as global search and "ask Enola": a question is handed to the chat. */
export function CommandPalette() {
  const { paletteOpen, closePalette, paletteInitialQuery } = useShell();
  const [query, setQuery] = useState("");
  const [cursor, setCursor] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (paletteOpen) {
      setQuery(paletteInitialQuery);
      setCursor(0);
      window.setTimeout(() => inputRef.current?.focus(), 0);
    }
  }, [paletteOpen, paletteInitialQuery]);

  const trimmed = query.trim();
  const askMode = trimmed.length > 2;
  const search = usePaletteSearch(trimmed);

  const groups = useMemo<Group[]>(() => {
    const q = trimmed.toLowerCase();
    const screens: PaletteHit[] = SCREENS.filter((s) => !q || s.label.toLowerCase().includes(q)).map((s) => ({
      id: `screen:${s.id}`,
      label: s.label,
      meta: "screen",
      dot: s.dot,
      path: s.path,
    }));
    const out: Group[] = [];
    for (const hit of search.data ?? []) {
      let group = out.find((g) => g.label === hit.group);
      if (!group) {
        group = { label: hit.group ?? "Results", items: [] };
        out.push(group);
      }
      group.items.push(hit);
    }
    if (screens.length > 0) out.push({ label: "Go to", items: screens });
    return out;
  }, [trimmed, search.data]);

  const flat = useMemo(() => groups.flatMap((g) => g.items), [groups]);
  const ask = () => {
    closePalette();
    navigate("/chat", { state: { ask: trimmed } });
  };
  const open = (hit: PaletteHit) => {
    closePalette();
    navigate(hit.path);
  };

  const onKey = (event: React.KeyboardEvent) => {
    const total = flat.length + (askMode ? 1 : 0);
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setCursor((c) => (total ? (c + 1) % total : 0));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setCursor((c) => (total ? (c - 1 + total) % total : 0));
    } else if (event.key === "Enter") {
      event.preventDefault();
      if (event.metaKey || event.ctrlKey) {
        if (askMode) ask();
        return;
      }
      const index = askMode ? cursor - 1 : cursor;
      if (askMode && cursor === 0) ask();
      else {
        const hit = flat[index];
        if (hit) open(hit);
      }
    }
  };

  let position = askMode ? 1 : 0;

  return (
    <Sheet open={paletteOpen} onClose={closePalette} bare width="lg" placement="top">
      <div className={styles["palette"]} onKeyDown={onKey}>
        <div className={styles["inputRow"]}>
          <span className={styles["ring"]} aria-hidden />
          <input
            ref={inputRef}
            className={styles["input"]}
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setCursor(0);
            }}
            placeholder="Search everything, or type to ask Enola"
            aria-label="Search or ask Enola"
          />
          <Mono className={styles["kbd"]}>esc</Mono>
        </div>
        <div className={styles["results"]}>
          {askMode && (
            <button type="button" className={cx(styles["ask"], cursor === 0 && styles["cursor"])} onClick={ask}>
              <span className={styles["askMark"]} aria-hidden />
              <span className={styles["askText"]}>Ask Enola: “{trimmed}”</span>
              <Mono>↵</Mono>
            </button>
          )}
          {groups.map((group) => (
            <div key={group.label}>
              <Mono upper className={styles["groupLabel"]}>
                {group.label}
              </Mono>
              {group.items.map((hit) => {
                const index = position++;
                return (
                  <button key={hit.id} type="button" className={cx(styles["hit"], cursor === index && styles["cursor"])} onClick={() => open(hit)} onMouseEnter={() => setCursor(index)}>
                    <Dot tone={hit.dot} />
                    <span className={styles["hitLabel"]}>{hit.label}</span>
                    <Mono>{hit.meta}</Mono>
                  </button>
                );
              })}
            </div>
          ))}
          {search.isFetching && <Mono className={styles["status"]}>searching…</Mono>}
        </div>
        <div className={styles["foot"]}>
          <Mono>↑↓ move</Mono>
          <Mono>↵ open</Mono>
          <Mono>⌘↵ ask instead</Mono>
        </div>
      </div>
    </Sheet>
  );
}
