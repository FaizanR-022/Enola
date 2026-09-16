import type { HTMLAttributes } from "react";
import { cx } from "@/lib/cx";
import styles from "./Mono.module.css";

export type MonoTone = "muted" | "soft" | "text" | "accent" | "held" | "ok" | "danger";

export interface MonoProps extends HTMLAttributes<HTMLSpanElement> {
  upper?: boolean | undefined;
  tone?: MonoTone | undefined;
  size?: 10 | 11 | 12 | undefined;
  bold?: boolean | undefined;
}

/** Small IBM Plex Mono label: 10–11px, letter-spaced when uppercase. */
export function Mono({ upper = false, tone = "muted", size = 10, bold = false, className, ...rest }: MonoProps) {
  return <span className={cx(styles["mono"], upper && styles["upper"], styles[tone], styles[`s${size}`], bold && styles["bold"], className)} {...rest} />;
}
