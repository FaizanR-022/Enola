/** Urgency by intensity, not hue. Overdue and today use the danger red at two weights,
 *  this week uses --tx2, later or undated uses --tx3 and dims the row. One tiering,
 *  used by tasks, deadlines, next actions and follow-ups. */

import { parseDate } from "@/lib/format";
import type { DotTone } from "@/ui";

export type Urgency = "overdue" | "today" | "week" | "later";

const DAY_MS = 86_400_000;

function dayDiff(value: string, now: Date): number {
  const date = parseDate(value);
  if (!date) return Number.POSITIVE_INFINITY;
  const a = new Date(now);
  a.setHours(0, 0, 0, 0);
  const b = new Date(date);
  b.setHours(0, 0, 0, 0);
  return Math.round((b.getTime() - a.getTime()) / DAY_MS);
}

export function urgencyOf(due: string | null | undefined, now = new Date()): Urgency {
  if (!due) return "later";
  const days = dayDiff(due, now);
  if (days < 0) return "overdue";
  if (days === 0) return "today";
  if (days < 7) return "week";
  return "later";
}

/** Dot props for a given urgency: filled red, outlined red, soft, muted. */
export function urgencyDot(urgency: Urgency): { tone: DotTone; hollow: boolean } {
  switch (urgency) {
    case "overdue":
      return { tone: "danger", hollow: false };
    case "today":
      return { tone: "danger", hollow: true };
    case "week":
      return { tone: "soft", hollow: false };
    default:
      return { tone: "muted", hollow: false };
  }
}
