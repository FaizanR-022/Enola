/** One definition of the time-of-day greeting.
 *
 *  Used by the splash and by the dashboard heading. Two copies would eventually
 *  disagree — the splash saying "Good evening" and the screen behind it saying
 *  something else is exactly the kind of seam that makes software feel assembled.
 */

export function greeting(now: Date = new Date()): string {
  const hour = now.getHours();
  if (hour < 5) return "Still up";
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
}

/** "Good evening, Faizan" — or just the greeting when the name is not loaded yet, so
 *  the heading never flashes a dangling comma. */
export function greet(name: string | null | undefined, now: Date = new Date()): string {
  const hello = greeting(now);
  return name ? `${hello}, ${name}` : hello;
}
