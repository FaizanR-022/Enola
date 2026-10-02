import { useEffect, useRef, useState } from "react";
import type { Task } from "@/data";
import { cx } from "@/lib/cx";
import { dueLabel } from "@/lib/format";
import { Badge, CardRow, Mono } from "@/ui";
import { urgencyOf, type Urgency } from "./urgency";
import styles from "./TaskRow.module.css";

const DISARM_MS = 4000;

/** One task: checkbox, title, link badge, due.
 *
 *  Completing takes two taps. The first arms the row (the box becomes a green confirm
 *  button, same size, so nothing moves); the second completes. Tapping elsewhere or
 *  four seconds idle disarms. Reopening a done task is a single tap: it is the safe
 *  direction.
 *
 *  `lead` marks a row that sits in a screen's one primary region: a step larger and
 *  heavier, so the focal region reads as one block. */
export function TaskRow({ task, onToggle, compact = false, busy = false, lead = false }: { task: Task; onToggle: (task: Task) => void; compact?: boolean | undefined; busy?: boolean | undefined; lead?: boolean | undefined }) {
  const done = task.state === "done";
  const urgency: Urgency = done ? "later" : urgencyOf(task.due_at);
  const link = task.links[0];
  const [armed, setArmed] = useState(false);
  const rowRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!armed) return;
    const timer = window.setTimeout(() => setArmed(false), DISARM_MS);
    const onPointer = (event: PointerEvent) => {
      if (rowRef.current && !rowRef.current.contains(event.target as Node)) setArmed(false);
    };
    window.addEventListener("pointerdown", onPointer, true);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener("pointerdown", onPointer, true);
    };
  }, [armed]);

  const tap = () => {
    if (done) {
      onToggle(task);
      return;
    }
    if (!armed) {
      setArmed(true);
      return;
    }
    setArmed(false);
    onToggle(task);
  };

  const toneClass = styles[`u-${urgency}`];
  return (
    <CardRow ref={rowRef} className={cx(styles["row"], toneClass, lead && styles["lead"], done && styles["done"], armed && styles["armed"])}>
      <button
        type="button"
        className={cx(styles["check"], done && styles["checked"], armed && styles["confirm"])}
        onClick={tap}
        aria-label={done ? `Reopen ${task.title}` : armed ? `Confirm complete ${task.title}` : `Complete ${task.title}`}
        aria-pressed={armed}
        disabled={busy}
      >
        <span className={styles["checkFill"]} />
      </button>
      <span className={styles["title"]}>{task.title}</span>
      {armed && (
        <Mono size={10} tone="ok" className={styles["armedHint"]}>
          tap again
        </Mono>
      )}
      {!compact && !armed && link && <Badge tone="neutral">{link.label || link.entity_type}</Badge>}
      <Mono size={10} tone={done ? "muted" : urgency === "overdue" || urgency === "today" ? "danger" : urgency === "week" ? "soft" : "muted"} className={styles["due"]}>
        {done ? "done" : dueLabel(task.due_at)}
      </Mono>
    </CardRow>
  );
}
