import type { HTMLAttributes } from "react";
import { cx } from "@/lib/cx";
import styles from "./Badge.module.css";

export type BadgeTone = "neutral" | "soft" | "accent" | "held" | "ok" | "danger";

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: BadgeTone | undefined;
  /** Filled pill (used for counts) instead of the default outlined tag. */
  solid?: boolean | undefined;
  pill?: boolean | undefined;
}

export function Badge({ tone = "neutral", solid = false, pill = false, className, ...rest }: BadgeProps) {
  return <span className={cx(styles["badge"], styles[tone], solid && styles["solid"], pill && styles["pill"], className)} {...rest} />;
}
