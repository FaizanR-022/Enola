import type { HTMLAttributes } from "react";
import { cx } from "@/lib/cx";
import styles from "./Screen.module.css";

export interface ScreenProps extends HTMLAttributes<HTMLDivElement> {
  /** Constrain reading-heavy screens (Tasks, Log, Memory) to a comfortable measure. */
  narrow?: boolean | undefined;
  /** Academics: warm surfaces. The only full mode shift in the app. */
  paper?: boolean | undefined;
  /** Full-height screens (Chat, Email) manage their own scrolling. */
  fill?: boolean | undefined;
}

/** The padded column every screen renders into. */
export function Screen({ narrow = false, paper = false, fill = false, className, children, ...rest }: ScreenProps) {
  return (
    <div className={cx(styles["screen"], narrow && styles["narrow"], fill && styles["fill"], className)} data-paper={paper ? "1" : undefined} {...rest}>
      {children}
    </div>
  );
}

/** Responsive card grid: auto-fit columns with a minimum width. */
export function Grid({ min = "280px", className, children, ...rest }: HTMLAttributes<HTMLDivElement> & { min?: string | undefined }) {
  return (
    <div className={cx(styles["grid"], className)} style={{ ["--grid-min" as string]: min }} {...rest}>
      {children}
    </div>
  );
}

/** Vertical stack of cards. */
export function Stack({ className, children, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cx(styles["stack"], className)} {...rest}>
      {children}
    </div>
  );
}
