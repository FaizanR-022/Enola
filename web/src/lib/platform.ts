/** Which modifier key to show.
 *
 *  The shortcut handler accepts either (metaKey || ctrlKey), so it has always worked on
 *  both. Only the label was wrong: "⌘K" printed on Windows tells you to press a key the
 *  keyboard does not have.
 */

interface UserAgentData {
  platform?: string;
}

function platformString(): string {
  const data = (navigator as Navigator & { userAgentData?: UserAgentData }).userAgentData;
  return data?.platform || navigator.platform || navigator.userAgent || "";
}

export const isMac = /mac|iphone|ipad|ipod/i.test(platformString());

/** "⌘K" on a Mac, "Ctrl K" everywhere else. */
export const modK = isMac ? "⌘K" : "Ctrl K";

/** The modifier alone, for combinations like Enter. */
export const modKey = isMac ? "⌘" : "Ctrl ";
