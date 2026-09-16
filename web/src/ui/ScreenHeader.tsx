import type { ReactNode } from "react";
import { cx } from "@/lib/cx";
import styles from "./ScreenHeader.module.css";

export interface ScreenHeaderProps {
  title: ReactNode;
  subtitle?: ReactNode | undefined;
  actions?: ReactNode | undefined;
  /** Georgia serif. Academics only. */
  serif?: boolean | undefined;
  /** "← Pipeline" style link above the title. */
  back?: ReactNode | undefined;
  className?: string | undefined;
}

export function ScreenHeader({ title, subtitle, actions, serif = false, back, className }: ScreenHeaderProps) {
  return (
    <div className={cx(styles["wrap"], className)}>
      {back && <div className={styles["back"]}>{back}</div>}
      <div className={cx(styles["row"], serif && styles["serifRow"])}>
        <h1 className={cx(styles["title"], serif && styles["serif"])}>{title}</h1>
        {subtitle && <div className={styles["subtitle"]}>{subtitle}</div>}
        {actions && (
          <>
            <span className={styles["spacer"]} />
            <div className={styles["actions"]}>{actions}</div>
          </>
        )}
      </div>
    </div>
  );
}
