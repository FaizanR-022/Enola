import { cx } from "@/lib/cx";
import styles from "./Wordmark.module.css";

/** A ring left open on one side: the gap is the approval that hasn't happened yet. */
export function Mark({ size = "sm", held = false, pulse = false }: { size?: "sm" | "md" | "lg" | undefined; held?: boolean | undefined; pulse?: boolean | undefined }) {
  return (
    <span className={cx(styles["mark"], styles[size], held && styles["held"])} aria-hidden>
      <span className={cx(styles["ring"], pulse && styles["pulse"])} />
    </span>
  );
}

export function Wordmark({ size = "sm" }: { size?: "sm" | "md" | "lg" | undefined }) {
  return (
    <span className={cx(styles["lockup"], styles[`lockup-${size}`])}>
      <Mark size={size} />
      <span className={styles["word"]}>enola</span>
    </span>
  );
}
