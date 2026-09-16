import type { ReactNode } from "react";
import { cx } from "@/lib/cx";
import styles from "./EmptyState.module.css";

export interface EmptyStateProps {
  title: ReactNode;
  hint?: ReactNode | undefined;
  action?: ReactNode | undefined;
  /** Compact variant for inside a card. */
  inline?: boolean | undefined;
  className?: string | undefined;
}

export function EmptyState({ title, hint, action, inline = false, className }: EmptyStateProps) {
  return (
    <div className={cx(styles["empty"], inline && styles["inline"], className)}>
      <div className={styles["title"]}>{title}</div>
      {hint && <div className={styles["hint"]}>{hint}</div>}
      {action && <div className={styles["action"]}>{action}</div>}
    </div>
  );
}
