import { cx } from "@/lib/cx";
import { Dot, Mono } from "@/ui";
import styles from "./StepRail.module.css";

export type RailState = "held" | "approved" | "rejected" | "running";

/** The job stopped mid-flight: past steps filled, the Held step larger and ochre,
 *  the rest outlined. Held is the only state with a pulse. */
export function StepRail({ steps, index, state, label }: { steps: ReadonlyArray<string>; index: number; state: RailState; label?: string | undefined }) {
  return (
    <div className={styles["rail"]}>
      {label && (
        <Mono upper className={styles["label"]}>
          {label}
        </Mono>
      )}
      {steps.map((step, i) => {
        const past = i < index || state === "approved";
        const current = i === index && state !== "approved";
        const tone = past ? (state === "approved" ? "ok" : "accent") : current ? (state === "rejected" ? "danger" : state === "held" ? "held" : "accent") : "line";
        return (
          <span key={step} className={styles["step"]}>
            <Dot tone={tone} size={current && state === "held" ? 9 : 7} hollow={!past && !current} pulse={current && state === "held"} />
            <span className={cx(styles["stepLabel"], past && styles["past"], current && styles[`current-${state}`])}>{step}</span>
            {i < steps.length - 1 && <span className={styles["joiner"]} aria-hidden />}
          </span>
        );
      })}
    </div>
  );
}
