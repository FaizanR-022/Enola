import { Dot } from "@/ui";
import { urgencyDot, urgencyOf, type Urgency } from "./urgency";

/** The one urgency marker: filled red (overdue), outlined red (today), soft (this
 *  week), muted (later). Pass a due date or a precomputed tier. */
export function UrgencyDot({ due, urgency, size = 6 }: { due?: string | null | undefined; urgency?: Urgency | undefined; size?: 5 | 6 | 7 | 9 | undefined }) {
  const tier = urgency ?? urgencyOf(due);
  const { tone, hollow } = urgencyDot(tier);
  return <Dot tone={tone} hollow={hollow} size={size} />;
}

/** Mono tone that matches the dot, for the label beside it. */
export function urgencyMono(tier: Urgency): "danger" | "soft" | "muted" {
  return tier === "overdue" || tier === "today" ? "danger" : tier === "week" ? "soft" : "muted";
}
