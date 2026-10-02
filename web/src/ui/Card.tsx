import { forwardRef, type HTMLAttributes, type ReactNode } from "react";
import { cx } from "@/lib/cx";
import { Mono } from "./Mono";
import styles from "./Card.module.css";

export type CardEdge = "none" | "held" | "accent" | "ok" | "danger";

export interface CardProps extends Omit<HTMLAttributes<HTMLDivElement>, "title"> {
  /** Small uppercase mono label in the header row. */
  title?: ReactNode | undefined;
  /** Right-aligned mono text or a control in the header row. */
  meta?: ReactNode | undefined;
  /** Quiet footer note, e.g. "Enola never notifies for these." */
  note?: ReactNode | undefined;
  edge?: CardEdge | undefined;
  /** Remove inner padding: use when children are CardRows. */
  flush?: boolean | undefined;
  dashed?: boolean | undefined;
  tone?: "raised" | "flat" | undefined;
  /** Demoted a step: smaller type, --tx2, tighter rows. For everything that is not the primary region. */
  quiet?: boolean | undefined;
}

export function Card({ title, meta, note, edge = "none", flush = false, dashed = false, tone = "raised", quiet = false, className, children, ...rest }: CardProps) {
  return (
    <section
      className={cx(styles["card"], styles[`edge-${edge}`], dashed && styles["dashed"], tone === "flat" && styles["flat"], quiet && styles["quiet"], className)}
      {...rest}
    >
      {(title || meta) && (
        <header className={styles["head"]}>
          {title && (
            <Mono upper size={quiet ? 10 : 11} tone={quiet ? "muted" : "accent"}>
              {title}
            </Mono>
          )}
          <span className={styles["spacer"]} />
          {meta && <span className={styles["meta"]}>{meta}</span>}
        </header>
      )}
      <div className={cx(styles["body"], flush && styles["flush"])}>{children}</div>
      {note && <footer className={styles["note"]}>{note}</footer>}
    </section>
  );
}

export interface CardRowProps extends HTMLAttributes<HTMLDivElement> {
  interactive?: boolean | undefined;
  align?: "center" | "start" | "baseline" | undefined;
  muted?: boolean | undefined;
}

/** A bordered row inside a flush Card. Clickable when `interactive`. */
export const CardRow = forwardRef<HTMLDivElement, CardRowProps>(function CardRow({ interactive = false, align = "center", muted = false, className, children, onClick, ...rest }, ref) {
  return (
    <div
      ref={ref}
      className={cx(styles["row"], styles[`align-${align}`], interactive && styles["interactive"], muted && styles["muted"], className)}
      role={interactive ? "button" : undefined}
      tabIndex={interactive ? 0 : undefined}
      onClick={onClick}
      onKeyDown={
        interactive && onClick
          ? (event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                onClick(event as unknown as React.MouseEvent<HTMLDivElement>);
              }
            }
          : undefined
      }
      {...rest}
    >
      {children}
    </div>
  );
});
