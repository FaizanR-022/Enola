import { useHeldCountQuery, useNotificationBadge } from "@/data";

/** The number of Held approvals. Ochre, and the only ochre badge in the app. */
export function useHeldCount(): number {
  const query = useHeldCountQuery();
  return query.data?.held ?? 0;
}

/** Unread in-app reminders. Neutral, shown on Home: informational, never urgent. */
export function useReminderCount(): number {
  const query = useNotificationBadge();
  return query.data?.unread ?? 0;
}
