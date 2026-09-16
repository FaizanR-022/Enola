import { useTheme } from "@/theme/theme";
import { cx } from "@/lib/cx";
import { Mono } from "@/ui";
import { useShell } from "./ShellState";
import type { Screen } from "./screens";
import styles from "./Header.module.css";

export function Header({ screen }: { screen: Screen }) {
  const { openPalette, toggleRail, railOpen, headerMeta } = useShell();
  const { theme, toggle } = useTheme();

  return (
    <header className={styles["header"]}>
      <div className={styles["title"]}>{screen.label}</div>
      {headerMeta && <Mono size={11}>{headerMeta}</Mono>}
      <span className={styles["spacer"]} />
      <button type="button" className={styles["search"]} onClick={() => openPalette()} aria-label="Search or ask Enola">
        <span className={styles["searchRing"]} aria-hidden />
        <span className={styles["searchText"]}>Search or ask Enola</span>
        <Mono className={styles["searchKbd"]}>⌘K</Mono>
      </button>
      <button type="button" className={styles["themeToggle"]} onClick={toggle} aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`} title="Theme">
        <Mono size={11} tone="soft">
          {theme === "dark" ? "light" : "dark"}
        </Mono>
      </button>
      <button type="button" className={cx(styles["rail"], railOpen && styles["railOn"])} onClick={toggleRail} aria-pressed={railOpen}>
        Chat rail
      </button>
    </header>
  );
}
