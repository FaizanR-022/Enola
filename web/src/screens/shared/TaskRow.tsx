import type { Task } from "@/data";
import { cx } from "@/lib/cx";
import { dueLabel, dueTone } from "@/lib/format";
import { Badge, CardRow, Mono } from "@/ui";
import styles from "./TaskRow.module.css";

/** One task: checkbox, title, link badge, due. Used by Tasks and the dashboard. */
export function TaskRow({ task, onToggle, compact = false, busy = false }: { task: Task; onToggle: (task: Task) => void; compact?: boolean | undefined; busy?: boolean | undefined }) {
  const done = task.state === "done";
  const tone = done ? "muted" : dueTone(task.due_at);
  const link = task.links[0];
  return (
    <CardRow className={cx(styles["row"], done && styles["done"])}>
      <button
        type="button"
        className={cx(styles["check"], styles[`check-${tone}`], done && styles["checked"])}
        onClick={() => onToggle(task)}
        aria-label={done ? `Reopen ${task.title}` : `Complete ${task.title}`}
        disabled={busy}
      >
        <span className={styles["checkFill"]} />
      </button>
      <span className={styles["title"]}>{task.title}</span>
      {!compact && link && <Badge tone="neutral">{link.label || link.entity_type}</Badge>}
      <Mono size={10} tone={done ? "muted" : tone === "held" ? "held" : tone === "danger" ? "danger" : tone === "soft" ? "soft" : "muted"} className={styles["due"]}>
        {done ? "done" : dueLabel(task.due_at)}
      </Mono>
    </CardRow>
  );
}
