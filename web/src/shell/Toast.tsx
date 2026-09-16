import { Dot } from "@/ui";
import { useShell } from "./ShellState";
import styles from "./Toast.module.css";

export function Toast() {
  const { toast } = useShell();
  if (!toast) return null;
  return (
    <div className={styles["toast"]} role="status" aria-live="polite">
      <Dot size={6} tone="ok" />
      <span>{toast}</span>
    </div>
  );
}
