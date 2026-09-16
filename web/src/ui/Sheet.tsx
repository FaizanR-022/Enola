import { useEffect, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { cx } from "@/lib/cx";
import styles from "./Sheet.module.css";

export interface SheetProps {
  open: boolean;
  onClose: () => void;
  title?: ReactNode | undefined;
  children: ReactNode;
  footer?: ReactNode | undefined;
  /** Dialog width on desktop. Phones always get a bottom sheet. */
  width?: "sm" | "md" | "lg" | undefined;
  /** No title bar and no padding: the palette owns its own chrome. */
  bare?: boolean | undefined;
  /** Vertical placement on desktop. */
  placement?: "center" | "top" | undefined;
  className?: string | undefined;
}

/** A modal: centred dialog at desktop width, bottom sheet at phone width. */
export function Sheet({ open, onClose, title, children, footer, width = "md", bare = false, placement = "center", className }: SheetProps) {
  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = previous;
    };
  }, [open, onClose]);

  if (!open) return null;

  return createPortal(
    <div className={cx(styles["scrim"], styles[placement])} onMouseDown={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        className={cx(styles["panel"], styles[width], bare && styles["bare"], className)}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className={styles["grip"]} aria-hidden />
        {!bare && title && (
          <header className={styles["head"]}>
            <div className={styles["title"]}>{title}</div>
            <button type="button" className={styles["close"]} onClick={onClose} aria-label="Close">
              ✕
            </button>
          </header>
        )}
        <div className={cx(styles["body"], bare && styles["bodyBare"])}>{children}</div>
        {footer && <footer className={styles["foot"]}>{footer}</footer>}
      </div>
    </div>,
    document.body,
  );
}
