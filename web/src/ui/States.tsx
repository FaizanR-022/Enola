import type { ReactNode } from "react";
import { errorMessage } from "@/lib/api";
import { cx } from "@/lib/cx";
import { Button } from "./Button";
import { Mono } from "./Mono";
import styles from "./States.module.css";

/** Skeleton rows while a query is in flight. */
export function LoadingState({ rows = 3, label, className }: { rows?: number | undefined; label?: string | undefined; className?: string | undefined }) {
  return (
    <div className={cx(styles["loading"], className)} role="status" aria-live="polite" aria-label={label ?? "Loading"}>
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className={styles["bar"]} />
      ))}
    </div>
  );
}

export function ErrorState({ error, onRetry, className }: { error: unknown; onRetry?: (() => void) | undefined; className?: string | undefined }) {
  return (
    <div className={cx(styles["error"], className)} role="alert">
      <Mono upper tone="danger">
        Could not load
      </Mono>
      <div className={styles["message"]}>{errorMessage(error)}</div>
      {onRetry && (
        <Button size="sm" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}

/** Wrap a query: loading → skeleton, error → retry, else render. Keeps screens honest
 *  about every state without repeating the branches on each one. */
export function QueryState<T>({ status, error, data, onRetry, rows, children }: {
  status: "pending" | "error" | "success";
  error: unknown;
  data: T | undefined;
  onRetry?: (() => void) | undefined;
  rows?: number | undefined;
  children: (data: T) => ReactNode;
}) {
  if (status === "pending") return <LoadingState rows={rows} />;
  if (status === "error" || data === undefined) return <ErrorState error={error} onRetry={onRetry} />;
  return <>{children(data)}</>;
}
