import { useOwner } from "@/lib/auth";
import { cx } from "@/lib/cx";
import { Mono } from "@/ui";
import { useShell } from "./ShellState";
import { Mark } from "./Wordmark";
import styles from "./Splash.module.css";

function greeting(hour: number): string {
  if (hour < 5) return "Still up";
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
}

/** Shown while the first screen loads. Click to skip. There is no timer: the bar
 *  moves when data arrives and the splash leaves the moment the dashboard is ready. */
export function Splash() {
  const { finishBoot } = useShell();
  const owner = useOwner();
  const stage = owner.isPending ? 0 : 1;
  const name = owner.data?.name;
  const label = stage === 0 ? "restoring session" : "daily brief";

  return (
    <button type="button" className={styles["splash"]} onClick={finishBoot} aria-label="Skip splash">
      <Mark size="lg" pulse />
      <div className={styles["word"]}>enola</div>
      <div className={styles["line"]}>
        {name ? `${greeting(new Date().getHours())}, ${name}. Pulling today together.` : "Pulling today together."}
      </div>
      <div className={styles["bar"]}>
        <div className={cx(styles["fill"], styles[`stage${stage}`])} />
      </div>
      <Mono className={styles["label"]}>{label}</Mono>
    </button>
  );
}
