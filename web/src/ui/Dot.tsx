import { cx } from "@/lib/cx";
import styles from "./Dot.module.css";

export type DotTone = "line" | "muted" | "soft" | "accent" | "held" | "ok" | "danger" | "paper";

export interface DotProps {
  tone?: DotTone | undefined;
  /** The slow Held pulse. Use only for Held. */
  pulse?: boolean | undefined;
  size?: 5 | 6 | 7 | 9 | undefined;
  /** Outlined instead of filled (a step not yet reached). */
  hollow?: boolean | undefined;
  className?: string | undefined;
}

export function Dot({ tone = "muted", pulse = false, size = 5, hollow = false, className }: DotProps) {
  return <span aria-hidden className={cx(styles["dot"], styles[tone], styles[`s${size}`], pulse && styles["pulse"], hollow && styles["hollow"], className)} />;
}
