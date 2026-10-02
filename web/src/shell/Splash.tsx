import { useOwner } from "@/lib/auth";
import { cx } from "@/lib/cx";
import { greeting } from "@/lib/greeting";
import { Mono } from "@/ui";
import { useShell } from "./ShellState";
import { Mark } from "./Wordmark";
import styles from "./Splash.module.css";

/** Shown while the first screen loads, for at least VITE_SPLASH_MIN_MS. Click to skip.
 *  The bar is honest: it moves as data arrives, reaches full when the dashboard is
 *  ready, and holds there for whatever is left of the minimum. */
export function Splash() {
  const { skipBoot, dataReady } = useShell();
  const owner = useOwner();
  const stage = dataReady ? 2 : owner.isPending ? 0 : 1;
  const name = owner.data?.name;
  const label = stage === 0 ? "restoring session" : stage === 1 ? "daily brief" : "ready";

  return (
    <button type="button" className={styles["splash"]} onClick={skipBoot} aria-label="Skip splash">
      <Mark size="lg" pulse />
      <div className={styles["word"]}>enola</div>
      <div className={styles["line"]}>
        {name ? `${greeting()}, ${name}. Pulling today together.` : "Pulling today together."}
      </div>
      <div className={styles["bar"]}>
        <div className={cx(styles["fill"], styles[`stage${stage}`])} />
      </div>
      <Mono className={styles["label"]}>{label}</Mono>
    </button>
  );
}
